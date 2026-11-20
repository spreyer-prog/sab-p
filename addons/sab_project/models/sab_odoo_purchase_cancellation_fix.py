from odoo import models


class PurchaseOrderSabCancellationFix(models.Model):
    _inherit = "purchase.order"

    def button_cancel(self):
        requirements = self.order_line.mapped("sab_purchase_requirement_id")
        result = super().button_cancel()
        reopen = requirements.filtered(
            lambda requirement: not requirement.odoo_purchase_line_id
            and requirement.state == "ordered"
        )
        if reopen:
            reopen.write({"state": "open"})
            reopen._sab_prepare_order_quantities(force=True)
        return result
