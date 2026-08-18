from odoo import api, fields, models, _


class ProjectProjectProcurement(models.Model):
    _inherit = "project.project"

    sab_bom_ids = fields.One2many(
        "sab.project.bom",
        "project_id",
        string="Stücklisten und Verteiler",
        readonly=True,
    )
    sab_purchase_requirement_ids = fields.One2many(
        "sab.purchase.requirement",
        "project_id",
        string="Materialbedarf",
        readonly=True,
    )
    sab_purchase_order_ids = fields.Many2many(
        "sab.purchase.order",
        string="Lieferantenbestellungen",
        compute="_compute_procurement_overview",
    )
    sab_switchboard_count = fields.Integer(
        string="Verteiler",
        compute="_compute_procurement_overview",
    )
    sab_purchase_order_count = fields.Integer(
        string="Bestellungen",
        compute="_compute_procurement_overview",
    )
    sab_material_required_quantity = fields.Float(
        string="Materialbedarf gesamt",
        digits=(16, 3),
        compute="_compute_procurement_overview",
    )
    sab_material_reserved_quantity = fields.Float(
        string="Material verfügbar / reserviert",
        digits=(16, 3),
        compute="_compute_procurement_overview",
    )
    sab_material_ordered_quantity = fields.Float(
        string="Bestellt",
        digits=(16, 3),
        compute="_compute_procurement_overview",
    )
    sab_material_received_quantity = fields.Float(
        string="Geliefert",
        digits=(16, 3),
        compute="_compute_procurement_overview",
    )
    sab_material_available_percent = fields.Float(
        string="Material vorhanden (%)",
        compute="_compute_procurement_overview",
    )
    sab_material_missing_percent = fields.Float(
        string="Material fehlt (%)",
        compute="_compute_procurement_overview",
    )
    sab_procurement_state = fields.Selection(
        [
            ("not_started", "Noch nicht freigegeben"),
            ("released", "Bestellfreigabe erteilt"),
            ("preparing", "Bestellung in Vorbereitung"),
            ("ordered", "Bestellt – Lieferung offen"),
            ("partial", "Teilweise geliefert"),
            ("complete", "Material vollständig"),
        ],
        string="Materialstatus",
        compute="_compute_procurement_overview",
    )

    @api.depends(
        "sab_bom_ids.bom_scope",
        "sab_bom_ids.state",
        "sab_bom_ids.purchase_release_state",
        "sab_purchase_requirement_ids.quantity",
        "sab_purchase_requirement_ids.project_reserved_quantity",
        "sab_purchase_requirement_ids.state",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_ordered",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_received",
        "sab_purchase_requirement_ids.purchase_order_id.state",
    )
    def _compute_procurement_overview(self):
        PurchaseOrder = self.env["sab.purchase.order"]
        for project in self:
            switchboards = project.sab_bom_ids.filtered(
                lambda bom: getattr(bom, "bom_scope", "total") == "cabinet"
            )
            requirements = project.sab_purchase_requirement_ids.filtered(
                lambda requirement: not requirement.optional
                and requirement.state != "cancel"
                and getattr(requirement.bom_id, "bom_scope", "total") == "total"
            )
            orders = PurchaseOrder.search([
                ("line_ids.project_id", "=", project.id),
                ("state", "!=", "cancel"),
            ])

            required = sum(requirements.mapped("quantity"))
            reserved = sum(
                min(requirement.project_reserved_quantity or 0.0, requirement.quantity or 0.0)
                for requirement in requirements
            )
            ordered = sum(
                line.quantity_ordered
                for order in orders.filtered(lambda record: record.state in ("sent", "partial", "done"))
                for line in order.line_ids.filtered(lambda item: item.project_id == project)
            )
            received = sum(
                line.quantity_received
                for order in orders
                for line in order.line_ids.filtered(lambda item: item.project_id == project)
            )
            available_percent = min(reserved / required * 100.0, 100.0) if required else 0.0
            missing_percent = max(100.0 - available_percent, 0.0) if required else 0.0

            project.sab_purchase_order_ids = orders
            project.sab_switchboard_count = len(switchboards)
            project.sab_purchase_order_count = len(orders)
            project.sab_material_required_quantity = required
            project.sab_material_reserved_quantity = reserved
            project.sab_material_ordered_quantity = ordered
            project.sab_material_received_quantity = received
            project.sab_material_available_percent = available_percent
            project.sab_material_missing_percent = missing_percent

            total_boms = project.sab_bom_ids.filtered(
                lambda bom: getattr(bom, "bom_scope", "total") == "total"
            )
            purchase_released = any(
                bom.purchase_release_state == "released" for bom in total_boms
            )
            if required and available_percent >= 100.0:
                state = "complete"
            elif any(order.state == "partial" for order in orders) or received > 0:
                state = "partial"
            elif any(order.state in ("sent", "done") for order in orders):
                state = "ordered"
            elif any(order.state in ("draft", "to_approve", "approved") for order in orders):
                state = "preparing"
            elif purchase_released:
                state = "released"
            else:
                state = "not_started"
            project.sab_procurement_state = state

    def action_view_sab_switchboards(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Verteiler – %s") % self.display_name,
            "res_model": "sab.project.bom",
            "view_mode": "list,form",
            "domain": [
                ("project_id", "=", self.id),
                ("bom_scope", "=", "cabinet"),
            ],
            "target": "current",
        }

    def action_view_sab_purchase_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellungen – %s") % self.display_name,
            "res_model": "sab.purchase.order",
            "view_mode": "list,form",
            "domain": [("line_ids.project_id", "=", self.id)],
            "target": "current",
        }
