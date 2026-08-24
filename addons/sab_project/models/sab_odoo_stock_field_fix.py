from odoo import fields, models


class StockMoveSabAssignmentFieldFix(models.Model):
    _inherit = "stock.move"

    sab_purchase_requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="SAB-P Materialposition",
        related=False,
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_project_id = fields.Many2one(
        "project.project",
        string="SAB-P Projekt",
        related=False,
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_procurement_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Materialanforderung",
        related=False,
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_source_cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler / Schaltschrank",
        related=False,
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
