from odoo import fields, models


class SabInquiryType(models.Model):
    _name = "sab.inquiry.type"
    _description = "SAB-P Art der Anfrage"
    _order = "sequence, name"

    name = fields.Char(string="Bezeichnung", required=True, translate=True)
    sequence = fields.Integer(string="Reihenfolge", default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Diese Art der Anfrage ist bereits vorhanden.",
    )


class SabTechnology(models.Model):
    _name = "sab.technology"
    _description = "SAB-P Technik"
    _order = "sequence, name"

    name = fields.Char(string="Bezeichnung", required=True, translate=True)
    sequence = fields.Integer(string="Reihenfolge", default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Diese Technik ist bereits vorhanden.",
    )


class SabServiceType(models.Model):
    _name = "sab.service.type"
    _description = "SAB-P Leistungsart"
    _order = "sequence, name"

    name = fields.Char(string="Bezeichnung", required=True, translate=True)
    sequence = fields.Integer(string="Reihenfolge", default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Diese Leistungsart ist bereits vorhanden.",
    )
