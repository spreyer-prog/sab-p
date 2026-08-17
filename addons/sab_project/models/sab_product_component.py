from odoo import api, fields, models


class SabProductComponent(models.Model):
    _name = "sab.product.component"
    _description = "SAB-P Produkt-Baugruppenposition"
    _order = "sequence, id"

    sequence = fields.Integer(string="Pos.", default=10)
    product_id = fields.Many2one(
        "sab.product", string="Produkt", required=True, ondelete="cascade", index=True
    )
    supplier_product_id = fields.Many2one(
        "sab.supplier.product",
        string="Lieferantenartikel",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(string="Menge", default=1.0, required=True, digits=(16, 2))
    unit_price = fields.Float(
        string="EK je Einheit",
        compute="_compute_prices",
        digits=(16, 2),
    )
    total_price = fields.Float(
        string="EK gesamt",
        compute="_compute_prices",
        digits=(16, 2),
    )

    @api.depends("supplier_product_id.net_purchase_price", "quantity")
    def _compute_prices(self):
        for record in self:
            record.unit_price = record.supplier_product_id.net_purchase_price or 0.0
            record.total_price = record.unit_price * (record.quantity or 0.0)
