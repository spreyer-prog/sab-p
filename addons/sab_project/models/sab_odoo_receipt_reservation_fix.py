from odoo import models


class SabPurchaseRequirementReceiptReservation(models.Model):
    _inherit = "sab.purchase.requirement"

    def _reserve_available_stock(self):
        """Reserve available stock also after an Odoo purchase receipt.

        A requirement is normally already `ordered` when the supplier receipt is
        posted. The reservation therefore must not be limited to `open` demand.
        """
        Movement = self.env["sab.stock.movement"]
        eligible = self.filtered(
            lambda requirement: requirement.state in ("open", "ordered", "received")
            and not requirement.optional
        )
        for requirement in eligible:
            requirement.invalidate_recordset()
            needed = max(
                (requirement.quantity or 0.0)
                - (requirement.project_reserved_quantity or 0.0)
                - (requirement.commissioned_quantity or 0.0),
                0.0,
            )
            available = max(requirement.warehouse_available or 0.0, 0.0)
            reserve_qty = min(needed, available)
            if reserve_qty <= 1e-9:
                continue

            values = requirement._movement_product_values()
            values.update(
                {
                    "movement_type": "reserve",
                    "quantity": reserve_qty,
                    "unit": requirement.unit,
                    "project_id": requirement.project_id.id,
                    "purchase_requirement_id": requirement.id,
                    "note": f"Projektreservierung aus {requirement.bom_id.name}",
                }
            )
            Movement.create(values)
            requirement.invalidate_recordset()
        return True
