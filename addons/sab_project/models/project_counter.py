from odoo import fields, models


class SabProjectYearCounter(models.Model):
    _name = "sab.project.year.counter"
    _description = "SAB-P Projektzähler je Jahr"
    _order = "year desc"

    year = fields.Integer(required=True, index=True)
    next_number = fields.Integer(
        required=True,
        default=1,
        help="Nächste zu vergebende laufende Projektnummer.",
    )

    _year_unique = models.Constraint(
        "UNIQUE(year)",
        "Für jedes Jahr darf nur ein Projektzähler existieren.",
    )
