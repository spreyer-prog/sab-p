from odoo import models


class StockWarehouseSabCommissioningPickingType(models.Model):
    _inherit = "stock.warehouse"

    def _sab_ensure_commissioning_picking_type(self):
        PickingType = self.env["stock.picking.type"].sudo()
        Location = self.env["stock.location"].sudo()
        for warehouse in self:
            existing = PickingType.search(
                [
                    ("code", "=", "internal"),
                    ("warehouse_id", "=", warehouse.id),
                ],
                limit=1,
            )
            if existing:
                continue

            destination = Location.search(
                [
                    ("usage", "=", "production"),
                    ("company_id", "in", [False, warehouse.company_id.id]),
                ],
                order="company_id desc, id",
                limit=1,
            )
            if not destination:
                warehouse.company_id.sudo()._create_production_location()
                destination = Location.search(
                    [
                        ("usage", "=", "production"),
                        ("company_id", "=", warehouse.company_id.id),
                    ],
                    limit=1,
                )

            PickingType.create(
                {
                    "name": "SAB-P Kommissionierung",
                    "code": "internal",
                    "sequence_code": "SABKOM",
                    "warehouse_id": warehouse.id,
                    "company_id": warehouse.company_id.id,
                    "default_location_src_id": warehouse.lot_stock_id.id,
                    "default_location_dest_id": destination.id,
                    "reservation_method": "at_confirm",
                }
            )
        return True

    def init(self):
        super().init()
        self.sudo().search([])._sab_ensure_commissioning_picking_type()
