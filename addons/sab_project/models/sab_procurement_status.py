from odoo import fields, models


PROCUREMENT_STATUS_ADDITIONS = [
    ("proposal", "Bestellvorschlag"),
    ("approval", "Zur Bestellfreigabe"),
    ("approved", "Freigegeben – noch nicht versendet"),
]
PROCUREMENT_STATUS_ONDELETE = {
    "proposal": "set null",
    "approval": "set null",
    "approved": "set null",
}


class SabPurchaseRequirementDetailedStatus(models.Model):
    _inherit = "sab.purchase.requirement"

    stock_status = fields.Selection(
        selection_add=PROCUREMENT_STATUS_ADDITIONS,
        ondelete=PROCUREMENT_STATUS_ONDELETE,
    )

    def _compute_procurement_quantities(self):
        super()._compute_procurement_quantities()
        for requirement in self:
            line = requirement.purchase_order_line_id
            order = requirement.purchase_order_id
            if not line or requirement.state == "cancel":
                continue
            if line.quantity_remaining <= 0:
                requirement.stock_status = "received"
            elif line.quantity_received > 0:
                requirement.stock_status = "partial_received"
            elif order.state == "draft":
                requirement.stock_status = "proposal"
            elif order.state == "to_approve":
                requirement.stock_status = "approval"
            elif order.state == "approved":
                requirement.stock_status = "approved"
            elif order.state in ("sent", "partial", "done"):
                requirement.stock_status = "ordered"


class SabProjectBomLineDetailedProcurementStatus(models.Model):
    _inherit = "sab.project.bom.line"

    procurement_status = fields.Selection(
        selection_add=PROCUREMENT_STATUS_ADDITIONS,
        ondelete=PROCUREMENT_STATUS_ONDELETE,
    )
