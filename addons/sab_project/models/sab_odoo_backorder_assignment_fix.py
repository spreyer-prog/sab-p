from odoo import models


class StockMoveSabBackorderAssignment(models.Model):
    _inherit = "stock.move"

    def _prepare_move_split_vals(self, uom_qty):
        values = super()._prepare_move_split_vals(uom_qty)
        # Odoo erzeugt Backorders durch Splitten der ursprünglichen Bewegung.
        # Die SAB-P-Zuordnungen sind bewusst copy=False, damit normale Kopien
        # keine Projekt-/Bedarfsbindung erben. Beim echten Backorder müssen sie
        # jedoch erhalten bleiben, sonst geht die Rückverfolgbarkeit der
        # Restlieferung verloren.
        values.update(
            {
                "sab_purchase_requirement_id": (
                    self.sab_purchase_requirement_id.id or False
                ),
                "sab_project_id": self.sab_project_id.id or False,
                "sab_procurement_bom_id": (
                    self.sab_procurement_bom_id.id or False
                ),
                "sab_source_cabinet_bom_id": (
                    self.sab_source_cabinet_bom_id.id or False
                ),
            }
        )
        return values
