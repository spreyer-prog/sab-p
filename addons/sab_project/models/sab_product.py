from odoo import api, fields, models


class SabProduct(models.Model):
    _name = "sab.product"
    _description = "SAB-P Produkt"
    _order = "manufacturer_id, manufacturer_article_number, name"
    _rec_name = "name"

    active = fields.Boolean(string="Aktiv", default=True)

    product_type = fields.Selection(
        selection=[
            ("material", "Material"),
            ("mechanical", "Mechanik"),
            ("wiring", "Verdrahtung"),
            ("testing", "Prüfung"),
            ("labeling", "Beschriftung"),
            ("documentation", "Dokumentation"),
            ("transport", "Transport"),
            ("packaging", "Verpackung"),
            ("other", "Sonstiges"),
        ],
        string="Produkttyp",
        required=True,
        default="material",
        index=True,
    )
    name = fields.Char(string="Bezeichnung", required=True, index=True)
    manufacturer_id = fields.Many2one(comodel_name="sab.manufacturer", string="Hersteller", ondelete="restrict", index=True)
    manufacturer_article_number = fields.Char(string="Herstellerartikelnummer", index=True)
    datanorm_number = fields.Char(string="DATANORM-Nummer", index=True)
    supplier_product_ids = fields.One2many(comodel_name="sab.supplier.product", inverse_name="product_id", string="Lieferantenartikel")

    stock_movement_ids = fields.One2many(
        comodel_name="sab.stock.movement",
        inverse_name="product_id",
        string="Lagerbewegungen",
    )
    stock_on_hand = fields.Float(
        string="Lagerbestand",
        digits=(16, 3),
        compute="_compute_stock_balances",
    )
    stock_reserved = fields.Float(
        string="Reserviert",
        digits=(16, 3),
        compute="_compute_stock_balances",
    )
    stock_available = fields.Float(
        string="Verfügbar",
        digits=(16, 3),
        compute="_compute_stock_balances",
    )

    space_units = fields.Float(string="Platzeinheiten", default=0.0)
    mechanical_time_minutes = fields.Float(string="Mechanikzeit in Minuten", default=0.0)
    wiring_time_minutes = fields.Float(string="Verdrahtungszeit in Minuten", default=0.0)
    testing_time_minutes = fields.Float(string="Prüfzeit in Minuten", default=0.0)
    notes = fields.Text(string="Interne Hinweise")

    @api.depends("stock_movement_ids.movement_type", "stock_movement_ids.quantity")
    def _compute_stock_balances(self):
        for product in self:
            movements = product.stock_movement_ids
            receipts = sum(movements.filtered(lambda m: m.movement_type == "receipt").mapped("quantity"))
            issues = sum(movements.filtered(lambda m: m.movement_type == "issue").mapped("quantity"))
            reservations = sum(movements.filtered(lambda m: m.movement_type == "reserve").mapped("quantity"))
            releases = sum(movements.filtered(lambda m: m.movement_type == "release").mapped("quantity"))
            product.stock_on_hand = receipts - issues
            product.stock_reserved = reservations - releases
            product.stock_available = product.stock_on_hand - product.stock_reserved
