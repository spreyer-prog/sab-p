from odoo import api, fields, models, _


class ProjectProjectProcurementDetail(models.Model):
    _inherit = "project.project"

    sab_procurement_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Beschaffungswährung",
        readonly=True,
    )
    sab_material_requirement_count = fields.Integer(
        string="Materialpositionen",
        compute="_compute_procurement_overview",
    )
    sab_material_required_value = fields.Monetary(
        string="Materialbedarf (EK)",
        currency_field="sab_procurement_currency_id",
        compute="_compute_procurement_overview",
    )
    sab_material_available_value = fields.Monetary(
        string="Physisch verfügbar / reserviert (EK)",
        currency_field="sab_procurement_currency_id",
        compute="_compute_procurement_overview",
    )
    sab_material_procured_value = fields.Monetary(
        string="Verfügbar oder bestellt (EK)",
        currency_field="sab_procurement_currency_id",
        compute="_compute_procurement_overview",
    )
    sab_material_received_value = fields.Monetary(
        string="Aus Bestellungen geliefert (EK)",
        currency_field="sab_procurement_currency_id",
        compute="_compute_procurement_overview",
    )
    sab_material_procured_percent = fields.Float(
        string="Beschaffung gesichert (%)",
        compute="_compute_procurement_overview",
    )

    @api.depends(
        "sab_bom_ids.bom_scope",
        "sab_bom_ids.state",
        "sab_bom_ids.purchase_release_state",
        "sab_purchase_requirement_ids.quantity",
        "sab_purchase_requirement_ids.unit_purchase_price",
        "sab_purchase_requirement_ids.project_reserved_quantity",
        "sab_purchase_requirement_ids.state",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_ordered",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_received",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_remaining",
        "sab_purchase_requirement_ids.purchase_order_id.state",
    )
    def _compute_procurement_overview(self):
        super()._compute_procurement_overview()
        for project in self:
            requirements = project.sab_purchase_requirement_ids.filtered(
                lambda requirement: not requirement.optional
                and requirement.state != "cancel"
                and getattr(requirement.bom_id, "bom_scope", "total") == "total"
            )

            required_value = 0.0
            available_value = 0.0
            procured_value = 0.0
            received_value = 0.0
            available_ratios = []
            procured_ratios = []

            for requirement in requirements:
                required_quantity = max(requirement.quantity or 0.0, 0.0)
                if required_quantity <= 0:
                    continue

                unit_price = max(requirement.unit_purchase_price or 0.0, 0.0)
                reserved_quantity = min(
                    max(requirement.project_reserved_quantity or 0.0, 0.0),
                    required_quantity,
                )
                order_line = requirement.purchase_order_line_id
                ordered_open = 0.0
                received_from_order = 0.0
                if order_line:
                    received_from_order = min(
                        max(order_line.quantity_received or 0.0, 0.0),
                        required_quantity,
                    )
                    if requirement.purchase_order_id.state in (
                        "approved",
                        "sent",
                        "partial",
                        "done",
                    ):
                        ordered_open = max(
                            order_line.quantity_remaining or 0.0,
                            0.0,
                        )

                procured_quantity = min(
                    reserved_quantity + ordered_open,
                    required_quantity,
                )
                available_ratio = reserved_quantity / required_quantity
                procured_ratio = procured_quantity / required_quantity
                available_ratios.append(available_ratio)
                procured_ratios.append(procured_ratio)

                line_value = required_quantity * unit_price
                required_value += line_value
                available_value += line_value * available_ratio
                procured_value += line_value * procured_ratio
                received_value += min(
                    received_from_order,
                    required_quantity,
                ) * unit_price

            if required_value > 0:
                available_percent = available_value / required_value * 100.0
                procured_percent = procured_value / required_value * 100.0
            else:
                available_percent = (
                    sum(available_ratios) / len(available_ratios) * 100.0
                    if available_ratios
                    else 0.0
                )
                procured_percent = (
                    sum(procured_ratios) / len(procured_ratios) * 100.0
                    if procured_ratios
                    else 0.0
                )

            project.sab_material_requirement_count = len(requirements)
            project.sab_material_required_value = required_value
            project.sab_material_available_value = available_value
            project.sab_material_procured_value = procured_value
            project.sab_material_received_value = received_value
            project.sab_material_available_percent = min(
                max(available_percent, 0.0),
                100.0,
            )
            project.sab_material_missing_percent = max(
                100.0 - project.sab_material_available_percent,
                0.0,
            )
            project.sab_material_procured_percent = min(
                max(procured_percent, 0.0),
                100.0,
            )

            orders = project.sab_purchase_order_ids
            total_boms = project.sab_bom_ids.filtered(
                lambda bom: getattr(bom, "bom_scope", "total") == "total"
            )
            purchase_released = any(
                bom.purchase_release_state == "released" for bom in total_boms
            )
            if requirements and project.sab_material_available_percent >= 99.999:
                state = "complete"
            elif any(order.state == "partial" for order in orders) or any(
                requirement.purchase_order_line_id.quantity_received > 0
                for requirement in requirements
            ):
                state = "partial"
            elif any(order.state in ("sent", "done") for order in orders):
                state = "ordered"
            elif any(
                order.state in ("draft", "to_approve", "approved")
                for order in orders
            ):
                state = "preparing"
            elif purchase_released:
                state = "released"
            else:
                state = "not_started"
            project.sab_procurement_state = state

    def action_view_sab_material_requirements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Gesamtmaterial – %s") % self.display_name,
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [
                ("project_id", "=", self.id),
                ("bom_id.bom_scope", "=", "total"),
                ("state", "!=", "cancel"),
            ],
            "context": {
                "search_default_open": 0,
                "search_default_group_project": 0,
            },
            "target": "current",
        }
