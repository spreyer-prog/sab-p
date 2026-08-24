from odoo import api, fields, models


class SabProductComponent(models.Model):
    _name = "sab.product.component"
    _description = "SAB-P Produkt-Baugruppenposition"
    _order = "sequence, id"

    sequence = fields.Integer(string="Pos.", default=10)
    odoo_product_id = fields.Many2one(
        "product.product", string="Produkt", ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "sab.product", string="Produkt (Altbestand)", ondelete="cascade", index=True
    )
    supplier_product_id = fields.Many2one(
        "sab.supplier.product",
        string="Lieferantenartikel",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(string="Menge", default=1.0, required=True, digits=(16, 2))
    unit_price = fields.Float(string="EK je Einheit", compute="_compute_prices", digits=(16, 2))
    total_price = fields.Float(string="EK gesamt", compute="_compute_prices", digits=(16, 2))

    @api.depends("supplier_product_id.net_purchase_price", "quantity")
    def _compute_prices(self):
        for record in self:
            record.unit_price = record.supplier_product_id.net_purchase_price or 0.0
            record.total_price = record.unit_price * (record.quantity or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("odoo_product_id") and vals.get("product_id"):
                legacy = self.env["sab.product"].browse(vals["product_id"])
                if legacy.odoo_product_id:
                    vals["odoo_product_id"] = legacy.odoo_product_id.id
        return super().create(vals_list)
