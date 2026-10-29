from odoo import fields, models


class SabProjectBomLineProcurementStatusSelection(models.Model):
    _inherit = "sab.project.bom.line"

    procurement_status = fields.Selection(
        selection_add=[
            ("partial_commissioned", "Teilweise kommissioniert"),
            ("commissioned", "Vollständig kommissioniert"),
        ],
        ondelete={
            "partial_commissioned": "set null",
            "commissioned": "set null",
        },
    )
