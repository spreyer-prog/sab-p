from odoo import api, models


class PurchaseOrderLineSabManualTextLines(models.Model):
    _inherit = "purchase.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            if vals.get("display_type") in ("line_section", "line_note"):
                # Odoo 19 keeps product_qty NOT NULL on purchase.order.line.
                # Normal UI onchanges provide 0.0 automatically, but direct
                # creation (and some imports) may omit it. Text/section lines
                # are intentionally non-material lines and therefore use 0.0.
                vals.setdefault("product_qty", 0.0)
            prepared.append(vals)
        return super().create(prepared)
