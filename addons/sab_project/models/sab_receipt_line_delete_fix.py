from odoo import Command, api, models


class PurchaseOrderSabReceiptLineRepair(models.Model):
    _inherit = "purchase.order"

    @api.model
    def _sab_repair_open_receipt_moves(self):
        """Recreate receipt moves that were deleted before this fix existed."""
        orders = self.sudo().search(
            [
                ("sab_is_suite_order", "=", True),
                ("state", "in", ("purchase", "done")),
                ("receipt_status", "!=", "full"),
            ]
        )
        for order in orders:
            order_lines = order.order_line
            moves_before_repair = order_lines.move_ids
            order._create_picking()
            order_lines.invalidate_recordset(["move_ids"])
            repaired_moves = (order_lines.move_ids - moves_before_repair).filtered(
                lambda move: move.state not in ("done", "cancel")
            )
            if repaired_moves:
                repaired_moves.write({"quantity": 0.0})
        return True


class StockPickingSabReceiptLineDeleteFix(models.Model):
    _inherit = "stock.picking"

    def _sab_keep_open_receipt_move_commands(self, commands):
        """Treat a deleted receipt row as received quantity zero.

        Removing the stock move itself breaks Odoo's purchase/backorder chain.
        Keeping its ordered demand and setting only the processed quantity to
        zero lets the standard backorder flow create the next receipt with the
        exact remaining product and quantity.
        """
        self.ensure_one()
        normalized = []
        for command in commands:
            operation = command[0]
            move_id = command[1] if len(command) > 1 else False
            move = self.env["stock.move"].browse(move_id).exists()
            keep_open = (
                operation in (Command.DELETE, Command.UNLINK)
                and move
                and move.picking_id == self
                and move.purchase_line_id
                and move.purchase_line_id.order_id.sab_is_suite_order
                and self.picking_type_id.code == "incoming"
                and self.state not in ("done", "cancel")
            )
            if keep_open:
                normalized.append(Command.update(move.id, {"quantity": 0.0}))
            else:
                normalized.append(command)
        return normalized

    def write(self, values):
        if len(self) != 1 or not self.sab_is_suite_receipt:
            return super().write(values)

        normalized = dict(values)
        for field_name in ("move_ids", "move_ids_without_package"):
            if field_name in normalized:
                normalized[field_name] = self._sab_keep_open_receipt_move_commands(
                    normalized[field_name]
                )
        return super().write(normalized)
