from odoo import fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineReleaseMapping(models.Model):
    _inherit = "sab.offer.calculation.line"

    component_origin_id = fields.Many2one(
        "sab.offer.calculation.line",
        string="Ursprüngliches Projektbauteil",
        copy=True,
        readonly=True,
        ondelete="set null",
        index=True,
        help=(
            "Verbindet dasselbe vollständig übernommene Bauteil über mehrere "
            "Projektangebote, ohne seine LV-Position mehrfach aufzulisten."
        ),
    )

    def _sab_create_mapping_from_line(self):
        """Persist direct LV/NTG positions only during explicit offer release."""
        if not self.env.context.get("sab_offer_release_mapping"):
            return True

        Mapping = self.env["sab.project.lv.mapping"]
        for line in self:
            if (
                line.line_type != "item"
                or line.parent_section_id
                or line.order_id.sab_calculation_source not in ("lv", "schematic")
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
                    values["position_code"] = f"NTG {values['ntg_number']}"
                    line.with_context(
                        sab_inherit_section_position=True,
                        skip_section_normalize=True,
                        skip_sale_line_sync=True,
                        sab_offer_release_write=True,
                    ).write(
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

    def sab_lock_lv_positions(self):
        return self.with_context(
            sab_offer_release_mapping=True
        )._sab_create_mapping_from_line()


class SaleOrderReleaseMapping(models.Model):
    _inherit = "sale.order"

    def action_sab_release_offer(self):
        result = super().action_sab_release_offer()
        released_lines = self.filtered(
            lambda order: order.sab_offer_release_state == "released"
        ).mapped("sab_calculation_line_ids")
        if released_lines:
            released_lines.sab_lock_lv_positions()
        return result

    def _sab_offer_reuse_create_component(
        self,
        section_values,
        item_values_list,
        end_sequence,
    ):
        """Create the section first so every child inherits one component position."""
        self.ensure_one()
        Line = self.env["sab.offer.calculation.line"].with_context(
            skip_section_normalize=True,
            skip_sale_line_sync=True,
        )

        section_vals = dict(section_values)
        section_vals.update(
            {
                "order_id": self.id,
                "line_type": "section",
            }
        )
        section = Line.create(section_vals)

        prepared_items = []
        for incoming in item_values_list:
            values = dict(incoming)
            values.update(
                {
                    "order_id": self.id,
                    "line_type": "item",
                    "parent_section_id": section.id,
                    "lv_position": section.lv_position or False,
                    "is_ntg": bool(section.is_ntg),
                }
            )
            prepared_items.append(values)
        items = Line.create(prepared_items) if prepared_items else Line

        end_line = Line.create(
            {
                "order_id": self.id,
                "line_type": "section_end",
                "sequence": end_sequence,
            }
        )

        all_lines = self.env["sab.offer.calculation.line"].search(
            [("order_id", "=", self.id)],
            order="sequence, id",
        )
        all_lines._normalize_section_membership()
        all_lines._sync_customer_order_lines()
        return section | items | end_line

    def _sab_offer_reuse_clone_project_component(self, source_section):
        self.ensure_one()
        sequence = self._sab_offer_reuse_prepare_insertion(adding_component=True)
        children = source_section.child_line_ids.filtered(
            lambda item: item.line_type == "item"
            and (item.calculation_item_id or item.odoo_product_id)
        ).sorted(key=lambda item: (item.sequence, item.id))
        if not children:
            raise ValidationError(
                "Das ausgewählte Bauteil enthält keine wiederverwendbaren Positionen."
            )

        origin = source_section.component_origin_id or source_section
        section_values = {
            "sequence": sequence,
            "description": source_section.description,
            "lv_position": source_section.lv_position or False,
            "is_ntg": bool(source_section.is_ntg),
            "schematic_reference": source_section.schematic_reference or False,
            "note": source_section.note or False,
            "component_origin_id": origin.id,
        }
        item_values = []
        for child in children:
            sequence += 10
            item_values.append(
                self._sab_offer_reuse_item_values(
                    child,
                    sequence,
                    keep_project_positions=False,
                )
            )
        sequence += 10
        return self._sab_offer_reuse_create_component(
            section_values,
            item_values,
            sequence,
        )

    def _sab_offer_reuse_add_template(self, template):
        self.ensure_one()
        sequence = self._sab_offer_reuse_prepare_insertion(adding_component=True)
        template_lines = template.line_ids.sorted(
            key=lambda item: (item.sequence, item.id)
        )
        if not template_lines:
            raise ValidationError("Das Kalkulationsbauteil enthält keine Positionen.")

        section_values = {
            "sequence": sequence,
            "description": template.name,
            "note": template.note or False,
        }
        item_values = []
        for template_line in template_lines:
            sequence += 10
            values = {
                "sequence": sequence,
                "quantity": template_line.quantity,
                "description": template_line.description or False,
                "note": template_line.note or False,
            }
            if template_line.calculation_item_id:
                values["calculation_item_id"] = template_line.calculation_item_id.id
            else:
                values["odoo_product_id"] = template_line.odoo_product_id.id
            item_values.append(values)
        sequence += 10
        return self._sab_offer_reuse_create_component(
            section_values,
            item_values,
            sequence,
        )

    @staticmethod
    def _sab_component_payload_signature(section):
        children = section.child_line_ids.filtered(
            lambda item: item.line_type == "item"
            and (item.calculation_item_id or item.odoo_product_id)
        ).sorted(key=lambda item: (item.sequence, item.id))
        return tuple(
            (
                "calculation" if child.calculation_item_id else "product",
                child.calculation_item_id.id or child.odoo_product_id.id,
                round(child.quantity or 0.0, 6),
            )
            for child in children
        )

    def sab_offer_reuse_payload(self):
        self.ensure_one()
        payload = super().sab_offer_reuse_payload()
        raw_components = payload.get("project_components", [])
        if not raw_components:
            return payload

        Section = self.env["sab.offer.calculation.line"]
        grouped = {}
        for item in raw_components:
            section = Section.browse(item["id"]).exists()
            if not section:
                continue
            if (
                section.order_id != self
                and section.order_id.sab_offer_release_state != "released"
            ):
                # Draft components from other quotations are not project master data.
                continue

            position = (section.lv_position or "").strip()
            signature = self._sab_component_payload_signature(section)
            if position:
                key = (
                    "position",
                    position,
                    (section.description or "").strip().casefold(),
                    signature,
                )
            elif section.component_origin_id:
                key = ("origin", section.component_origin_id.id)
            else:
                key = ("section", section.id)

            offer = section.order_id.sab_offer_reference or section.order_id.name or ""
            current = section.order_id == self
            existing = grouped.get(key)
            if not existing:
                existing = dict(item)
                existing.update(
                    {
                        "offers": [],
                        "offers_text": "",
                        "is_current": current,
                    }
                )
                grouped[key] = existing
            elif current and not existing.get("is_current"):
                # Prefer the current occurrence as the representative card.
                offers = existing["offers"]
                existing.update(dict(item))
                existing["offers"] = offers
                existing["is_current"] = True

            if offer and offer not in existing["offers"]:
                existing["offers"].append(offer)
            existing["is_current"] = existing.get("is_current", False) or current
            if item.get("saved_template_id") and not existing.get("saved_template_id"):
                existing["saved_template_id"] = item["saved_template_id"]
                existing["saved_template_name"] = item.get(
                    "saved_template_name",
                    "",
                )

        components = []
        for item in grouped.values():
            item["offers"].sort()
            item["offers_text"] = ", ".join(item["offers"])
            item["offer"] = item["offers"][0] if item["offers"] else ""
            components.append(item)
        components.sort(
            key=lambda item: (
                0 if item.get("is_current") else 1,
                item.get("positions") or "",
                item.get("name") or "",
            )
        )
        payload["project_components"] = components
        return payload
