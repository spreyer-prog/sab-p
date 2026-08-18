from odoo import api, fields, models


class SabSupplierProduct(models.Model):
    _name = "sab.supplier.product"
    _description = "SAB-P Lieferantenartikel"
    _order = "supplier_id, supplier_article_number, id"
    _rec_name = "supplier_article_number"

    active = fields.Boolean(string="Aktiv", default=True)
    supplier_id = fields.Many2one("sab.supplier", string="Lieferant", required=True, ondelete="restrict", index=True)

    # Zielmodell: normaler Odoo-Produktstamm.
    odoo_product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        ondelete="cascade",
        index=True,
        help="Produkt aus dem normalen Odoo-Produktstamm.",
    )
    # Nur noch für Altbestände während der Migration vorhanden.
    product_id = fields.Many2one(
        "sab.product",
        string="SAB-P Produkt (Altbestand)",
        ondelete="cascade",
        index=True,
    )

    supplier_article_number = fields.Char(string="Lieferantenartikelnummer", required=True, index=True)
    datanorm_number = fields.Char(string="DATANORM-Nummer", index=True)
    datanorm_type_name = fields.Char(string="Herstellertyp", index=True)
    ean = fields.Char(string="EAN", index=True)
    list_price = fields.Float(string="Listenpreis", digits=(16, 4), default=0.0)
    datanorm_price = fields.Float(string="DATANORM-Rohpreis", digits=(16, 4), default=0.0)
    datanorm_price_code = fields.Char(string="DATANORM-Preiskennzeichen")
    purchase_price = fields.Float(string="Rabattbasis / EK vor Rabatt", digits=(16, 4), default=0.0)
    discount_percent = fields.Float(string="Rabatt (%)", digits=(16, 3), default=0.0)
    net_purchase_price = fields.Float(string="Netto-Einkaufspreis", digits=(16, 4), compute="_compute_net_purchase_price", store=True)
    packaging_quantity = fields.Float(string="Verpackungseinheit", digits=(16, 3), default=1.0)
    minimum_order_quantity = fields.Float(string="Mindestbestellmenge", digits=(16, 3), default=1.0)
    unit = fields.Selection([
        ("pcs", "Stück"), ("m", "Meter"), ("kg", "kg"), ("set", "Satz"),
        ("pack", "Packung"), ("other", "Sonstiges")
    ], string="Mengeneinheit", required=True, default="pcs")
    delivery_time_days = fields.Integer(string="Lieferzeit in Tagen", default=0)
    valid_from = fields.Date(string="Gültig ab")
    valid_until = fields.Date(string="Gültig bis")
    preferred = fields.Boolean(string="Bevorzugter Lieferant", default=False)
    note = fields.Text(string="Interne Hinweise")
    datanorm_surcharge_ids = fields.One2many("sab.datanorm.surcharge", "supplier_product_id", string="DATANORM Zu-/Abschläge")

    @api.depends("purchase_price", "discount_percent")
    def _compute_net_purchase_price(self):
        for record in self:
            discount = min(max(record.discount_percent or 0.0, 0.0), 100.0)
            record.net_purchase_price = (record.purchase_price or 0.0) * (1.0 - discount / 100.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("odoo_product_id") and vals.get("product_id"):
                legacy = self.env["sab.product"].browse(vals["product_id"])
                if legacy.odoo_product_id:
                    vals["odoo_product_id"] = legacy.odoo_product_id.id
        return super().create(vals_list)
