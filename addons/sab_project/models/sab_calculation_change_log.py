from odoo import fields, models
from odoo.exceptions import ValidationError


class SabCalculationChangeLog(models.Model):
    _name = "sab.calculation.change.log"
    _description = "SAB-P Änderungsprotokoll Kalkulationsparameter"
    _order = "changed_at desc, id desc"
    _rec_name = "parameter_label"

    parameter_key = fields.Char(string="Parameter", required=True, readonly=True, index=True)
    parameter_label = fields.Char(string="Bezeichnung", required=True, readonly=True)
    old_value = fields.Char(string="Alter Wert", readonly=True)
    new_value = fields.Char(string="Neuer Wert", readonly=True)
    changed_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Geändert von",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    changed_at = fields.Datetime(
        string="Geändert am",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )
    note = fields.Char(string="Hinweis", readonly=True)

    def write(self, vals):
        raise ValidationError("Einträge des Kalkulations-Änderungsprotokolls sind unveränderlich.")

    def unlink(self):
        raise ValidationError("Einträge des Kalkulations-Änderungsprotokolls dürfen nicht gelöscht werden.")
