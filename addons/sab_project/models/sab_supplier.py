from odoo import fields, models


class SabSupplier(models.Model):
    _name = "sab.supplier"
    _description = "SAB-P Lieferant"
    _order = "name"
    _rec_name = "name"

    active = fields.Boolean(
        string="Aktiv",
        default=True,
    )

    name = fields.Char(
        string="Lieferant",
        required=True,
        index=True,
    )

    supplier_number = fields.Char(
        string="Lieferantennummer",
        index=True,
    )

    datanorm_identifier = fields.Char(
        string="DATANORM-Kennung",
        index=True,
    )

    website = fields.Char(
        string="Website",
    )

    note = fields.Text(
        string="Interne Hinweise",
    )