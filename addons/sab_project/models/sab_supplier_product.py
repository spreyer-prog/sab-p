from odoo import api, fields, models


class SabSupplierProduct(models.Model):
    _name = "sab.supplier.product"
    _description = "SAB-P Lieferantenartikel"
    _order = "supplier_id, supplier_article_number, id"
    _rec_name = "supplier_article_number"

    active = fields.Boolean(string="Aktiv", default=True)

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
    datanorm_number = fields.Char(string="DATANORM-Nummer", index=True)
    datanorm_type_name = fields.Char(string="Herstellertyp", index=True)
    ean = fields.Char(string="EAN", index=True)

    list_price = fields.Float(
        string="Listenpreis",
        digits=(16, 4),
        default=0.0,
        help="Hersteller-/Lieferantenlistenpreis vor individuellen Rabatten.",
    )
    datanorm_price = fields.Float(
        string="DATANORM-Rohpreis",
        digits=(16, 4),
        default=0.0,
        help="Originaler Preiswert aus dem DATANORM-A-Satz. Er wird zusätzlich als Listenpreis gespeichert.",
    )
    datanorm_price_code = fields.Char(
        string="DATANORM-Preiskennzeichen",
        help="Preis-/Einheitenkennzeichen aus dem DATANORM-A-Satz, z. B. V2.",
    )

    purchase_price = fields.Float(
        string="Rabattbasis / EK vor Rabatt",
        digits=(16, 4),
        default=0.0,
        help="Basis für die Rabattberechnung. Beim Rabattlistenimport wird hierfür standardmäßig der Listenpreis verwendet.",
    )
    discount_percent = fields.Float(
        string="Rabatt (%)",
        digits=(16, 3),
        default=0.0,
    )
    net_purchase_price = fields.Float(
        string="Netto-Einkaufspreis",
        digits=(16, 4),
        compute="_compute_net_purchase_price",
        store=True,
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
    delivery_time_days = fields.Integer(string="Lieferzeit in Tagen", default=0)
    valid_from = fields.Date(string="Gültig ab")
    valid_until = fields.Date(string="Gültig bis")
    preferred = fields.Boolean(string="Bevorzugter Lieferant", default=False)
    note = fields.Text(string="Interne Hinweise")

    datanorm_surcharge_ids = fields.One2many(
        comodel_name="sab.datanorm.surcharge",
        inverse_name="supplier_product_id",
        string="DATANORM Zu-/Abschläge",
    )

    @api.depends("purchase_price", "discount_percent")
    def _compute_net_purchase_price(self):
        for record in self:
            discount = min(max(record.discount_percent or 0.0, 0.0), 100.0)
            record.net_purchase_price = (
                (record.purchase_price or 0.0) * (1.0 - discount / 100.0)
            )
