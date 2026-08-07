from odoo import api, fields, models


class SabCalculationItemLine(models.Model):
    _name = "sab.calculation.item.line"
    _description = "SAB-P Kalkulationszeile"
    _order = "sequence, id"

    # ---------------------------------------------------------
    # Zugehöriger Kalkulationsartikel
    # ---------------------------------------------------------

    calculation_item_id = fields.Many2one(
        comodel_name="sab.calculation.item",
        string="Kalkulationsartikel",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # ---------------------------------------------------------
    # Position / Struktur
    # ---------------------------------------------------------

    sequence = fields.Integer(
        string="Pos.",
        default=10,
        index=True,
    )

    position_type = fields.Selection(
        selection=[
            ("normal", "Normal"),
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

    # ---------------------------------------------------------
    # Produkt
    # ---------------------------------------------------------

    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Standardprodukt",
        ondelete="restrict",
        index=True,
    )

    alternative_product_ids = fields.Many2many(
        comodel_name="sab.product",
        relation="sab_calculation_line_alternative_product_rel",
        column1="calculation_line_id",
        column2="product_id",
        string="Alternativprodukte",
    )

    # ---------------------------------------------------------
    # Menge
    # ---------------------------------------------------------

    quantity = fields.Float(
        string="Menge",
        required=True,
        default=1.0,
        digits=(16, 3),
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

    fixed_quantity = fields.Boolean(
        string="Festmenge",
        default=False,
        help=(
            "Bei aktivierter Festmenge wird die Menge später "
            "nicht mit einer übergeordneten Projekt- oder "
            "Anlagenmenge vervielfacht."
        ),
    )

    # ---------------------------------------------------------
    # Optionen
    # ---------------------------------------------------------

    optional = fields.Boolean(
        string="Optional",
        default=False,
    )

    note = fields.Char(
        string="Bemerkung",
    )

    # ---------------------------------------------------------
    # Automatische Positionsnummer
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            calculation_item_id = vals.get("calculation_item_id")

            if calculation_item_id and not vals.get("sequence"):
                last_line = self.search(
                    [
                        (
                            "calculation_item_id",
                            "=",
                            calculation_item_id,
                        )
                    ],
                    order="sequence desc, id desc",
                    limit=1,
                )

                vals["sequence"] = (
                    last_line.sequence + 10
                    if last_line
                    else 10
                )

        return super().create(vals_list)