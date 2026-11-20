from odoo import fields, models


class SabManufacturer(models.Model):
    _name = "sab.manufacturer"
    _description = "SAB Hersteller"
    _order = "name"

    active = fields.Boolean(
        string="Aktiv",
        default=True,
    )

    name = fields.Char(
        string="Hersteller",
        required=True,
        index=True,
    )

    short_name = fields.Char(
        string="Kurzname",
        index=True,
    )

    website = fields.Char(
        string="Website",
    )

    note = fields.Text(
        string="Bemerkung",
    )