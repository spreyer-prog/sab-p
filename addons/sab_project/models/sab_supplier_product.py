from odoo import fields, models


class SabSupplierProduct(models.Model):
    _name = "sab.supplier.product"
    _description = "SAB-P Lieferantenartikel"
    _order = "supplier_id, supplier_article_number, id"
    _rec_name = "supplier_article_number"

    active = fields.Boolean(
        string="Aktiv",
        default=True,
    )

    supplier_id = fields.Many2one(
        comodel_name="sab.supplier",
        string="Lieferant",
        required=True,
        ondelete="restrict",
        index=True,
    )

    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="SAB-P Produkt",
        required=True,
        ondelete="cascade",
        index=True,
    )

    supplier_article_number = fields.Char(
        string="Lieferantenartikelnummer",
        required=True,
        index=True,
    )

    datanorm_number = fields.Char(
        string="DATANORM-Nummer",
        index=True,
    )

    purchase_price = fields.Float(
        string="Einkaufspreis",
        digits=(16, 4),
        default=0.0,
    )

    discount_percent = fields.Float(
        string="Rabatt (%)",
        digits=(16, 3),
        default=0.0,
    )

    packaging_quantity = fields.Float(
        string="Verpackungseinheit",
        digits=(16, 3),
        default=1.0,
    )

    minimum_order_quantity = fields.Float(
        string="Mindestbestellmenge",
        digits=(16, 3),
        default=1.0,
    )

    unit = fields.Selection(
        selection=[
            ("pcs", "Stück"),
            ("m", "Meter"),
            ("kg", "kg"),
            ("set", "Satz"),
            ("pack", "Packung"),
            ("other", "Sonstiges"),
        ],
        string="Mengeneinheit",
        required=True,
        default="pcs",
    )

    delivery_time_days = fields.Integer(
        string="Lieferzeit in Tagen",
        default=0,
    )

    valid_from = fields.Date(
        string="Gültig ab",
    )

    valid_until = fields.Date(
        string="Gültig bis",
    )

    preferred = fields.Boolean(
        string="Bevorzugter Lieferant",
        default=False,
    )

    note = fields.Text(
        string="Interne Hinweise",
    )