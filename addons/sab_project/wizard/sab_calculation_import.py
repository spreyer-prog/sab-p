from odoo import fields, models


class SabCalculationImport(models.TransientModel):
    _name = "sab.calculation.import"
    _description = "SAB-P Kalkulationsdatenbank importieren"

    file_data = fields.Binary(
        string="Excel-Datei",
        required=True,
        attachment=False,
    )

    filename = fields.Char(
        string="Dateiname",
    )

    def action_import(self):
        return {"type": "ir.actions.act_window_close"}