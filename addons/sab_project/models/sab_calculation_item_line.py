from odoo import api, fields, models


class SabCalculationItemLine(models.Model):
    _name = "sab.calculation.item.line"
    _description = "SAB-P Kalkulationszeile"
    _order = "sequence, id"

    calculation_item_id = fields.Many2one(
        comodel_name="sab.calculation.item",
        string="Kalkulationsartikel",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(
        string="Pos.",
        default=10,
        index=True,
    )

    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Standardprodukt",
        required=True,
        ondelete="restrict",
        index=True,
    )

    quantity = fields.Float(
        string="Menge",
        required=True,
        default=1.0,
        digits=(16, 3),
    )

    alternative_product_ids = fields.Many2many(
        comodel_name="sab.product",
        relation="sab_calculation_line_alternative_product_rel",
        column1="calculation_line_id",
        column2="product_id",
        string="Alternativprodukte",
    )

    optional = fields.Boolean(
        string="Optional",
        default=False,
    )

    note = fields.Char(
        string="Bemerkung",
    )

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