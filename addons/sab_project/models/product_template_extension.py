from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sab_product_type = fields.Selection(
        [
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
        default="material",
        required=True,
        index=True,
    )
    sab_manufacturer_supplier_id = fields.Many2one(
        "sab.supplier",
        string="Datenquelle / Lieferant",
        ondelete="restrict",
        index=True,
    )
    sab_manufacturer_id = fields.Many2one(
        "sab.manufacturer",
        string="Hersteller",
        ondelete="restrict",
        index=True,
    )
    sab_manufacturer_article_number = fields.Char(
        string="Herstellerartikelnummer",
        index=True,
    )
    sab_datanorm_number = fields.Char(string="DATANORM-Nummer", index=True)

    sab_price_mode = fields.Selection(
        [
            ("supplier", "Lieferantenartikel"),
            ("fixed", "Fixpreis"),
            ("assembly", "Baugruppe"),
        ],
        string="Preisermittlung",
        default="supplier",
        required=True,
    )
    sab_fixed_purchase_price = fields.Float(
        string="Fixpreis EK",
        digits=(16, 4),
        default=0.0,
    )
    sab_space_units = fields.Float(string="Platzeinheiten", default=0.0)
    sab_mechanical_time_minutes = fields.Float(
        string="Mechanikzeit in Minuten",
        default=0.0,
    )
    sab_wiring_time_minutes = fields.Float(
        string="Verdrahtungszeit in Minuten",
        default=0.0,
    )
    sab_testing_time_minutes = fields.Float(
        string="Prüfzeit in Minuten",
        default=0.0,
    )
    sab_notes = fields.Text(string="Interne Hinweise")

    sab_supplier_product_ids = fields.One2many(
        related="product_variant_id.sab_supplier_product_ids",
        string="Lieferantenartikel",
        readonly=False,
    )
    sab_component_ids = fields.One2many(
        related="product_variant_id.sab_component_ids",
        string="Baugruppenpositionen",
        readonly=False,
    )
    sab_calculated_purchase_price = fields.Float(
        related="product_variant_id.sab_calculated_purchase_price",
        string="Kalkulatorischer EK",
        readonly=True,
    )

    sab_stock_on_hand = fields.Float(
        string="Lagerbestand",
        digits=(16, 3),
        compute="_compute_sab_stock",
    )
    sab_stock_reserved = fields.Float(
        string="Reserviert",
        digits=(16, 3),
        compute="_compute_sab_stock",
    )
    sab_stock_available = fields.Float(
        string="Verfügbar",
        digits=(16, 3),
        compute="_compute_sab_stock",
    )
    sab_stock_movement_ids = fields.Many2many(
        "sab.stock.movement",
        string="Lagerbewegungen",
        compute="_compute_sab_stock",
    )

    @api.depends("product_variant_id")
    def _compute_sab_stock(self):
        """Use the Odoo product link for all old and newly imported articles."""
        Movement = self.env["sab.stock.movement"].sudo()
        variants = self.mapped("product_variant_id")
        movements = Movement.search([("odoo_product_id", "in", variants.ids)])
        grouped = {}
        for movement in movements:
            grouped.setdefault(movement.odoo_product_id.id, Movement)
            grouped[movement.odoo_product_id.id] |= movement

        for template in self:
            product_movements = grouped.get(
                template.product_variant_id.id,
                Movement,
            )
            receipts = sum(
                product_movements.filtered(
                    lambda movement: movement.movement_type == "receipt"
                ).mapped("quantity")
            )
            issues = sum(
                product_movements.filtered(
                    lambda movement: movement.movement_type == "issue"
                ).mapped("quantity")
            )
            reserves = sum(
                product_movements.filtered(
                    lambda movement: movement.movement_type == "reserve"
                ).mapped("quantity")
            )
            releases = sum(
                product_movements.filtered(
                    lambda movement: movement.movement_type == "release"
                ).mapped("quantity")
            )
            template.sab_stock_on_hand = receipts - issues
            template.sab_stock_reserved = reserves - releases
            template.sab_stock_available = (
                template.sab_stock_on_hand - template.sab_stock_reserved
            )
            template.sab_stock_movement_ids = product_movements
