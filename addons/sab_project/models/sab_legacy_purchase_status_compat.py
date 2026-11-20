from odoo import api, models


class SabPurchaseRequirementLegacyStatusCompat(models.Model):
    _inherit = "sab.purchase.requirement"

    @api.depends(
        "purchase_order_line_id.order_id.state",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_line_id.quantity_remaining",
        "odoo_purchase_line_id.order_id.state",
    )
    def _compute_procurement_quantities(self):
        super()._compute_procurement_quantities()
        for requirement in self:
            if requirement.odoo_purchase_line_id:
                continue
            legacy_line = requirement.purchase_order_line_id
            if not legacy_line or requirement.state == "cancel":
                continue

            order_state = legacy_line.order_id.state
            if order_state == "cancel":
                requirement.stock_status = "cancel"
            elif legacy_line.quantity_remaining <= 1e-9 and legacy_line.quantity_ordered > 0:
                requirement.stock_status = "received"
            elif legacy_line.quantity_received > 1e-9:
                requirement.stock_status = "partial_received"
            elif order_state == "draft":
                requirement.stock_status = "proposal"
            elif order_state == "to_approve":
                requirement.stock_status = "approval"
            elif order_state == "approved":
                requirement.stock_status = "approved"
            elif order_state in ("sent", "partial", "done"):
                requirement.stock_status = "ordered"
