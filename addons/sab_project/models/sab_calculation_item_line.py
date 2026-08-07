from odoo import fields, models


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
    # Reihenfolge
    # ---------------------------------------------------------

    sequence = fields.Integer(
        string="Position",
        default=10,
    )

    # ---------------------------------------------------------
    # Produkt
    # ---------------------------------------------------------

    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Standardprodukt",
        required=True,
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