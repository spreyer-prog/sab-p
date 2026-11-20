from odoo import models


class StockPickingSabReturnBridgeFix(models.Model):
    _inherit = "stock.picking"

    def _sab_bridge_done_purchase_move(self, move):
        requirement = move.sab_purchase_requirement_id
        is_supplier_return = bool(
            requirement
            and move.quantity > 0
            and (
                move.location_dest_id.usage == "supplier"
                or move._is_purchase_return()
            )
        )
        if not is_supplier_return:
            return super()._sab_bridge_done_purchase_move(move)

        quantity = self._sab_move_quantity_in_requirement_uom(
            move,
            requirement,
        )
        if quantity <= 0:
            return

        requirement.invalidate_recordset(
            ["project_reserved_quantity", "commissioned_quantity"]
        )
        release_quantity = min(
            quantity,
            max(requirement.project_reserved_quantity or 0.0, 0.0),
        )
        if release_quantity > 0:
            self._sab_create_bridge_movement(
                move=move,
                requirement=requirement,
                event="return_release",
                movement_type="release",
                quantity=release_quantity,
                note=(
                    "Projektreservierung wegen Lieferantenrücksendung "
                    f"freigegeben: {move.picking_id.name}"
                ),
            )

        # Die Bestandsentnahme wird absichtlich nicht mit dem Einkaufsbedarf
        # verknüpft, damit sie nicht als Fertigungs-Kommissionierung zählt. Für
        # Produkt, Einheit und Projekt werden dennoch die Werte des Bedarfs
        # übernommen.
        Movement = self.env["sab.stock.movement"].sudo()
        domain = [
            ("odoo_stock_move_id", "=", move.id),
            ("odoo_bridge_event", "=", "return_issue"),
        ]
        if not Movement.search_count(domain):
            Movement.create(
                {
                    "product_id": requirement.product_id.id or False,
                    "odoo_product_id": move.product_id.id,
                    "movement_type": "issue",
                    "quantity": quantity,
                    "unit": requirement.unit,
                    "project_id": requirement.project_id.id or False,
                    "purchase_requirement_id": False,
                    "odoo_stock_move_id": move.id,
                    "odoo_bridge_event": "return_issue",
                    "note": (
                        "Lieferantenrücksendung aus Odoo: "
                        f"{move.picking_id.name}"
                    ),
                }
            )
        requirement.invalidate_recordset()
