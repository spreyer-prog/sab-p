from odoo import api, models


class StockPickingSabCommissioningContextFix(models.Model):
    _inherit = "stock.picking"

    @api.depends(
        "move_ids.sab_purchase_requirement_id",
        "move_ids.sab_project_id",
        "move_ids.sab_source_cabinet_bom_id",
        "move_ids.purchase_line_id.order_id.sab_is_suite_order",
        "sab_is_suite_commissioning",
    )
    def _compute_sab_purchase_context(self):
        super()._compute_sab_purchase_context()
        for picking in self.filtered("sab_is_suite_commissioning"):
            picking.sab_project_ids = picking.move_ids.mapped("sab_project_id")
            picking.sab_source_cabinet_bom_ids = picking.move_ids.mapped(
                "sab_source_cabinet_bom_id"
            )
