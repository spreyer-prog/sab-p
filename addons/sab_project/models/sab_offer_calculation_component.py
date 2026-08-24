from odoo import fields, models


class SabOfferCalculationComponent(models.Model):
    _name = "sab.offer.calculation.component"
    _description = "SAB-P Angebotskalkulation Komponenten-Snapshot"
    _order = "sequence, id"

    offer_calculation_line_id = fields.Many2one(
        comodel_name="sab.offer.calculation.line",
        string="Angebotskalkulationszeile",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Produkt (Altbestand)",
        ondelete="restrict",
        index=True,
    )
    odoo_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Odoo-Produkt",
        ondelete="restrict",
        index=True,
    )
    position_type = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("auxiliary_material", "Hilfsmaterial"),
            ("alternative", "Alternative"),
            ("information", "Information"),
            ("heading", "Überschrift"),
            ("subtotal", "Zwischensumme"),
        ],
        string="Positionstyp",
        required=True,
        default="normal",
        index=True,
    )
    quantity_per_unit = fields.Float(
        string="Menge je Kalkulationseinheit",
        required=True,
        digits=(16, 3),
        default=1.0,
    )
    unit = fields.Selection(
        selection=[
            ("pcs", "Stück"),
            ("m", "Meter"),
            ("kg", "kg"),
            ("min", "Minute"),
            ("h", "Stunde"),
            ("flat", "Pauschal"),
        ],
        string="Einheit",
        required=True,
        default="pcs",
    )
    fixed_quantity = fields.Boolean(string="Festmenge", default=False)
    optional = fields.Boolean(string="Optional", default=False)
    source_calculation_line_id = fields.Many2one(
        comodel_name="sab.calculation.item.line",
        string="Ursprüngliche Kalkulationszeile",
        readonly=True,
        ondelete="set null",
    )
    supplier_product_id = fields.Many2one(
        comodel_name="sab.supplier.product",
        string="Lieferantenartikel beim Snapshot",
        readonly=True,
        ondelete="set null",
    )
    unit_purchase_price = fields.Float(
        string="EK je Einheit beim Snapshot",
        digits=(16, 4),
        readonly=True,
    )
    note = fields.Char(string="Bemerkung", readonly=True)
