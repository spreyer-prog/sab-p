from odoo import models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineReleaseMapping(models.Model):
    _inherit = "sab.offer.calculation.line"

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
