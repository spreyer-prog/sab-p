from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineLv(models.Model):
    _inherit = "sab.offer.calculation.line"

    lv_position_locked = fields.Boolean(
        string="LV-Position projektweit festgeschrieben",
        compute="_compute_lv_position_locked",
    )

    def _sab_lv_mapping(
        self,
        order=None,
        calculation_item_id=False,
        odoo_product_id=False,
    ):
        order = order or self.order_id
        if not order or not order.sab_project_id:
            return self.env["sab.project.lv.mapping"]
        domain = [("project_id", "=", order.sab_project_id.id)]
        if calculation_item_id:
            domain.append(("calculation_item_id", "=", calculation_item_id))
        elif odoo_product_id:
            domain.append(("odoo_product_id", "=", odoo_product_id))
        else:
            return self.env["sab.project.lv.mapping"]
        return self.env["sab.project.lv.mapping"].search(domain, limit=1)

    def _sab_parent_section_from_values(self, vals):
        section_id = vals.get("parent_section_id")
        if section_id:
            return self.env["sab.offer.calculation.line"].browse(section_id).exists()
        if len(self) == 1 and self.parent_section_id:
            return self.parent_section_id
        return self.env["sab.offer.calculation.line"]

    @api.depends(
        "order_id.sab_project_id",
        "order_id.sab_calculation_source",
        "order_id.sab_offer_release_state",
        "calculation_item_id",
        "odoo_product_id",
        "lv_position",
        "parent_section_id",
        "parent_section_id.lv_position",
        "parent_section_id.is_ntg",
    )
    def _compute_lv_position_locked(self):
        for line in self:
            if line.line_type == "item" and line.parent_section_id:
                # A Bauteil child never owns an independent LV-/NTG-position.
                # Its position is always controlled by the Bauteil heading.
                line.lv_position_locked = True
                continue
            mapping = (
                line._sab_lv_mapping(
                    line.order_id,
                    line.calculation_item_id.id,
                    line.odoo_product_id.id,
                )
                if line.line_type == "item"
                and line.order_id.sab_calculation_source == "lv"
                else self.env["sab.project.lv.mapping"]
            )
            line.lv_position_locked = bool(mapping)

    @staticmethod
    def _sab_has_prior_lv_offer(order):
        """Only an explicitly released LV quotation establishes the project basis."""
        return bool(
            order
            and order.sab_project_id
            and order.env["sale.order"].search_count(
                [
                    ("sab_project_id", "=", order.sab_project_id.id),
                    ("id", "!=", order.id or 0),
                    ("sab_calculation_source", "=", "lv"),
                    ("sab_offer_release_state", "=", "released"),
                    ("state", "!=", "cancel"),
                ]
            )
        )

    def _sab_apply_project_position(self, vals, order):
        if self.env.context.get("sab_inherit_section_position"):
            return vals
        if (
            not order
            or order.sab_calculation_source != "lv"
            or not order.sab_project_id
        ):
            return vals
        if vals.get("line_type", "item") != "item":
            if (
                vals.get("line_type") == "section"
                and (vals.get("lv_position") or "")
                .strip()
                .upper()
                .startswith("NTG")
            ):
                vals["is_ntg"] = True
            return vals

        parent_section = self._sab_parent_section_from_values(vals)
        if parent_section:
            vals["lv_position"] = parent_section.lv_position or False
            vals["is_ntg"] = bool(
                parent_section.lv_position and parent_section.is_ntg
            )
            return vals

        calculation_item_id = vals.get("calculation_item_id")
        product_id = vals.get("odoo_product_id")
        mapping = self._sab_lv_mapping(
            order,
            calculation_item_id,
            product_id,
        )
        if mapping:
            vals["lv_position"] = mapping.position_code
            vals["is_ntg"] = mapping.is_ntg
            return vals
        if self._sab_has_prior_lv_offer(order) and (
            calculation_item_id or product_id
        ):
            Mapping = self.env["sab.project.lv.mapping"]
            number = Mapping.next_ntg_number(order.sab_project_id)
            code = f"NTG {number}"
            map_vals = {
                "project_id": order.sab_project_id.id,
                "position_code": code,
                "is_ntg": True,
                "ntg_number": number,
                "first_order_id": order.id,
            }
            if calculation_item_id:
                map_vals["calculation_item_id"] = calculation_item_id
            else:
                map_vals["odoo_product_id"] = product_id
            Mapping.create(map_vals)
            vals["lv_position"] = code
            vals["is_ntg"] = True
        return vals

    def _sab_create_mapping_from_line(self):
        """Persist LV positions only when the quotation is explicitly released.

        Draft input remains editable and must not become project master data.
        Items contained in a Bauteil deliberately do not create a product-level
        mapping. Their effective LV-/NTG-position is the position of the Bauteil.
        """
        Mapping = self.env["sab.project.lv.mapping"]
        for line in self:
            if (
                line.line_type != "item"
                or line.parent_section_id
                or line.order_id.sab_calculation_source != "lv"
                or line.order_id.sab_offer_release_state == "released"
                or not line.order_id.sab_project_id
                or not (line.lv_position or "").strip()
                or not (line.calculation_item_id or line.odoo_product_id)
            ):
                continue
            mapping = line._sab_lv_mapping(
                line.order_id,
                line.calculation_item_id.id,
                line.odoo_product_id.id,
            )
            if mapping:
                if (
                    mapping.position_code != line.lv_position
                    or mapping.is_ntg != line.is_ntg
                ):
                    raise ValidationError(
                        f"Die LV-/NTG-Position {mapping.position_code} ist für diesen "
                        "Artikel im Projekt festgeschrieben und darf nicht geändert werden."
                    )
                continue
            position_code = line.lv_position.strip()
            is_ntg = bool(
                line.is_ntg or position_code.upper().startswith("NTG")
            )
            values = {
                "project_id": line.order_id.sab_project_id.id,
                "position_code": position_code,
                "is_ntg": is_ntg,
                "first_order_id": line.order_id.id,
            }
            if is_ntg:
                try:
                    values["ntg_number"] = int(position_code.split()[-1])
                except (ValueError, IndexError):
                    values["ntg_number"] = Mapping.next_ntg_number(
                        line.order_id.sab_project_id
                    )
                    values["position_code"] = (
                        f"NTG {values['ntg_number']}"
                    )
                    super(SabOfferCalculationLineLv, line).write(
                        {
                            "lv_position": values["position_code"],
                            "is_ntg": True,
                        }
                    )
            if line.calculation_item_id:
                values["calculation_item_id"] = line.calculation_item_id.id
            else:
                values["odoo_product_id"] = line.odoo_product_id.id
            Mapping.create(values)
        return True

    def _sab_cleanup_child_only_auto_mapping(self, previous_position):
        """Remove an NTG mapping created only while a line was temporarily direct."""
        Line = self.env["sab.offer.calculation.line"]
        for line in self.filtered(
            lambda item: item.line_type == "item" and item.parent_section_id
        ):
            code = (previous_position or "").strip()
            if not code or not (
                line.calculation_item_id or line.odoo_product_id
            ):
                continue
            mapping = line._sab_lv_mapping(
                line.order_id,
                line.calculation_item_id.id,
                line.odoo_product_id.id,
            )
            if (
                not mapping
                or not mapping.is_ntg
                or mapping.first_order_id != line.order_id
                or mapping.position_code != code
            ):
                continue
            domain = [
                ("id", "!=", line.id),
                (
                    "order_id.sab_project_id",
                    "=",
                    line.order_id.sab_project_id.id,
                ),
                ("line_type", "=", "item"),
                ("parent_section_id", "=", False),
                ("lv_position", "=", mapping.position_code),
            ]
            if line.calculation_item_id:
                domain.append(
                    ("calculation_item_id", "=", line.calculation_item_id.id)
                )
            else:
                domain.append(("odoo_product_id", "=", line.odoo_product_id.id))
            if not Line.search_count(domain):
                mapping.sudo().unlink()
        return True

    def _sab_sync_section_positions(self):
        """Make the Bauteil position authoritative for every contained item."""
        for order in self.mapped("order_id"):
            sections = order.sab_calculation_line_ids.filtered(
                lambda line: line.line_type == "section"
            )
            for section in sections:
                desired_position = (section.lv_position or "").strip() or False
                desired_ntg = bool(
                    desired_position
                    and (
                        section.is_ntg
                        or desired_position.upper().startswith("NTG")
                    )
                )
                if section.is_ntg != desired_ntg:
                    section.with_context(
                        sab_inherit_section_position=True,
                        skip_section_normalize=True,
                        skip_sale_line_sync=True,
                        sab_offer_release_write=True,
                    ).write({"is_ntg": desired_ntg})
                children = section.child_line_ids.filtered(
                    lambda line: line.line_type == "item"
                )
                for child in children:
                    previous_position = child.lv_position
                    child._sab_cleanup_child_only_auto_mapping(previous_position)
                    values = {}
                    if (child.lv_position or False) != desired_position:
                        values["lv_position"] = desired_position
                    if child.is_ntg != desired_ntg:
                        values["is_ntg"] = desired_ntg
                    if values:
                        child.with_context(
                            sab_inherit_section_position=True,
                            skip_section_normalize=True,
                            skip_sale_line_sync=True,
                            sab_offer_release_write=True,
                        ).write(values)
        return True

    def sab_lock_lv_positions(self):
        # Mapping creation deliberately happens only during the explicit release
        # button. At that moment the offer is still in release_state=draft.
        self._sab_create_mapping_from_line()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            order = (
                self.env["sale.order"].browse(values.get("order_id")).exists()
                if values.get("order_id")
                else self.env["sale.order"]
            )
            values = self._sab_apply_project_position(values, order)
            prepared.append(values)
        records = super().create(prepared)
        records._sab_sync_section_positions()
        return records

    def write(self, vals):
        if self.env.context.get("sab_inherit_section_position"):
            return super().write(vals)

        if len(self) == 1:
            record = self
            values = dict(vals)
            if record.line_type == "item" and record.parent_section_id:
                inherited_position = record.parent_section_id.lv_position or False
                inherited_ntg = bool(
                    inherited_position
                    and (
                        record.parent_section_id.is_ntg
                        or inherited_position.upper().startswith("NTG")
                    )
                )
                if (
                    "lv_position" in values
                    and (values.get("lv_position") or False)
                    != inherited_position
                ):
                    raise ValidationError(
                        "Eine Position innerhalb eines Bauteils übernimmt die "
                        "LV-/NTG-Position des Bauteils. Bitte die Position in der "
                        "Bauteilzeile ändern."
                    )
                if (
                    "is_ntg" in values
                    and bool(values.get("is_ntg")) != inherited_ntg
                ):
                    raise ValidationError(
                        "Die NTG-Kennzeichnung einer Bauteilposition wird vom Bauteil vorgegeben."
                    )
                values["lv_position"] = inherited_position
                values["is_ntg"] = inherited_ntg
            else:
                calculation_item_id = values.get(
                    "calculation_item_id",
                    record.calculation_item_id.id,
                )
                product_id = values.get(
                    "odoo_product_id",
                    record.odoo_product_id.id,
                )
                mapping = record._sab_lv_mapping(
                    record.order_id,
                    calculation_item_id,
                    product_id,
                )
                if mapping and (
                    "lv_position" in values or "is_ntg" in values
                ):
                    position = values.get(
                        "lv_position",
                        record.lv_position,
                    )
                    is_ntg = values.get("is_ntg", record.is_ntg)
                    if (
                        position != mapping.position_code
                        or is_ntg != mapping.is_ntg
                    ):
                        raise ValidationError(
                            f"Die LV-/NTG-Position {mapping.position_code} ist "
                            "projektbezogen festgeschrieben und darf nicht geändert werden."
                        )
                values = self._sab_apply_project_position(
                    values,
                    record.order_id,
                )
            result = super().write(values)
            record._sab_sync_section_positions()
            return result

        result = super().write(vals)
        self._sab_sync_section_positions()
        return result
