from odoo import api, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineSchematicLv(models.Model):
    _inherit = "sab.offer.calculation.line"

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
                line.lv_position_locked = True
                continue
            mapping = self.env["sab.project.lv.mapping"]
            if (
                line.line_type == "item"
                and line.order_id.sab_calculation_source in ("lv", "schematic")
                and line.order_id.sab_project_id
                and (
                    line.order_id.sab_calculation_source == "lv"
                    or self._sab_has_prior_lv_offer(line.order_id)
                )
            ):
                mapping = line._sab_lv_mapping(
                    line.order_id,
                    line.calculation_item_id.id,
                    line.odoo_product_id.id,
                )
            line.lv_position_locked = bool(mapping)

    def _sab_apply_project_position(self, vals, order):
        if self.env.context.get("sab_inherit_section_position"):
            return vals
        if not order or not order.sab_project_id:
            return vals

        line_type = vals.get("line_type", "item")
        has_lv_basis = self._sab_has_prior_lv_offer(order)

        # A schematic/switchboard quotation may be the first quotation in a
        # project. In that case there is deliberately no LV/NTG history and no
        # synthetic project position must be created. Any copied/default
        # position is cleared so the offer remains a genuine non-LV offer.
        if order.sab_calculation_source == "schematic" and not has_lv_basis:
            vals["lv_position"] = False
            vals["is_ntg"] = False
            return vals

        # A new Bauteil is one commercial LV/NTG position. Once a project has
        # an established LV basis, a new schematic component receives exactly
        # one provisional NTG number for the whole component. Child products
        # inherit it and never receive individual NTG mappings.
        if line_type == "section":
            position = (vals.get("lv_position") or "").strip()
            if not position and (
                (order.sab_calculation_source == "schematic" and has_lv_basis)
                or (
                    order.sab_calculation_source == "lv"
                    and has_lv_basis
                )
            ):
                number = self.env["sab.project.lv.mapping"].next_ntg_number(
                    order.sab_project_id
                )
                position = f"NTG {number}"
                vals["lv_position"] = position
                vals["is_ntg"] = True
            elif position.upper().startswith("NTG"):
                vals["is_ntg"] = True
            return vals

        if line_type != "item":
            return vals

        parent_section = self._sab_parent_section_from_values(vals)
        if parent_section:
            vals["lv_position"] = parent_section.lv_position or False
            vals["is_ntg"] = bool(
                parent_section.lv_position
                and (
                    parent_section.is_ntg
                    or parent_section.lv_position.upper().startswith("NTG")
                )
            )
            return vals

        calculation_item_id = vals.get("calculation_item_id")
        product_id = vals.get("odoo_product_id")
        if not (calculation_item_id or product_id):
            return vals

        mapping = self._sab_lv_mapping(
            order,
            calculation_item_id,
            product_id,
        )
        if mapping:
            vals["lv_position"] = mapping.position_code
            vals["is_ntg"] = mapping.is_ntg
            return vals

        if (order.sab_calculation_source == "schematic" and has_lv_basis) or (
            order.sab_calculation_source == "lv"
            and has_lv_basis
        ):
            # The code is provisional until this quotation is explicitly
            # released. It is therefore not entered in the project mapping yet.
            number = self.env["sab.project.lv.mapping"].next_ntg_number(
                order.sab_project_id
            )
            vals["lv_position"] = f"NTG {number}"
            vals["is_ntg"] = True
        return vals


class SaleOrderSchematicLvRules(models.Model):
    _inherit = "sale.order"

    def _sab_validate_schematic_lv_basis(self):
        """Validate only the rules that are actually tied to an LV basis.

        A schematic/switchboard offer is allowed as the first quotation in a
        project. Only a genuine LV quotation requires LV position numbers.
        """
        for order in self:
            if order.sab_calculation_source != "lv":
                continue

            missing = order.sab_calculation_line_ids.filtered(
                lambda line: line.line_type in ("section", "item")
                and (
                    line.line_type == "section"
                    or line.calculation_item_id
                    or line.odoo_product_id
                )
                and not (line.lv_position or "").strip()
            )
            if missing:
                labels = []
                for line in missing[:5]:
                    labels.append(
                        line.description
                        or line.calculation_item_id.display_name
                        or line.odoo_product_id.display_name
                        or "Position"
                    )
                suffix = "" if len(missing) <= 5 else " …"
                raise ValidationError(
                    "Bei einem LV-Angebot muss vor der Freigabe für jede "
                    "relevante LV-Position eine LV-Nummer eingetragen sein. "
                    "Fehlend: %s%s" % (", ".join(labels), suffix)
                )
        return True

    def action_sab_release_offer(self):
        self._sab_validate_schematic_lv_basis()
        return super().action_sab_release_offer()
