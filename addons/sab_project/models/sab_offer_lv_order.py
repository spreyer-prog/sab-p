from odoo import models
from odoo.exceptions import ValidationError


class SaleOrderLvRules(models.Model):
    _inherit = "sale.order"

    def _sab_validate_and_lock_lv(self):
        for order in self:
            if order.sab_calculation_source != "lv" or not order.sab_calculation_line_ids:
                continue
            order.sab_calculation_line_ids._normalize_section_membership()
            visible = order.sab_calculation_line_ids.filtered(
                lambda line: line.line_type == "section" or (line.line_type == "item" and not line.parent_section_id)
            )
            missing = visible.filtered(lambda line: not (line.lv_position or "").strip())
            if missing:
                names = ", ".join((line.description or line.calculation_item_id.name or line.odoo_product_id.display_name or "Position")[:80] for line in missing[:5])
                raise ValidationError(
                    "Bei einem LV-Angebot benötigt jede im Kundenangebot sichtbare Position eine LV-Position. "
                    "Neue Nachtragspositionen müssen als NTG geführt werden. Fehlend bei: " + names
                )
            order.sab_calculation_line_ids.sab_lock_lv_positions()
        return True

    def action_quotation_send(self):
        self._sab_validate_and_lock_lv()
        return super().action_quotation_send()

    def action_confirm(self):
        self._sab_validate_and_lock_lv()
        return super().action_confirm()
