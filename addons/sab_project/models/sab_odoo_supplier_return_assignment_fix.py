from odoo import models


class StockReturnPickingSabSupplierReturnAssignment(models.TransientModel):
    _inherit = "stock.return.picking"

    def action_create_returns(self):
        result = super().action_create_returns()
        return_picking_id = result.get("res_id") if isinstance(result, dict) else False
        if not return_picking_id:
            return result

        return_picking = self.env["stock.picking"].browse(return_picking_id).exists()
        for move in return_picking.move_ids:
            source_move = move.origin_returned_move_id
            requirement = (
                source_move.sab_purchase_requirement_id
                or move.purchase_line_id.sab_purchase_requirement_id
            )
            if not requirement:
                continue

            values = {
                "sab_purchase_requirement_id": requirement.id,
                "sab_project_id": requirement.project_id.id or False,
                "sab_procurement_bom_id": requirement.bom_id.id or False,
                "sab_source_cabinet_bom_id": (
                    requirement.source_cabinet_bom_id.id or False
                ),
            }
            move.sudo().write(values)

        return result


class StockPickingSabSupplierReturnFinalize(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        result = super()._action_done()

        for picking in self:
            supplier_return_moves = picking.move_ids.filtered(
                lambda move: move.state == "done"
                and move.sab_purchase_requirement_id
                and (
                    move.location_dest_id.usage == "supplier"
                    or move._is_purchase_return()
                )
            )
            for move in supplier_return_moves:
                picking._sab_bridge_done_purchase_move(move)

        return result
