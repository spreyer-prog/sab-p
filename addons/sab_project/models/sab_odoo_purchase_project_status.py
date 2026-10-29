from odoo import api, models, _


class ProjectProjectSabOdooProcurementStatus(models.Model):
    _inherit = "project.project"

    @api.depends(
        "sab_bom_ids.bom_scope",
        "sab_bom_ids.state",
        "sab_bom_ids.purchase_release_state",
        "sab_purchase_requirement_ids.bom_id.bom_scope",
        "sab_purchase_requirement_ids.quantity",
        "sab_purchase_requirement_ids.unit_purchase_price",
        "sab_purchase_requirement_ids.project_reserved_quantity",
        "sab_purchase_requirement_ids.commissioned_quantity",
        "sab_purchase_requirement_ids.state",
        "sab_purchase_requirement_ids.odoo_purchase_line_id.product_qty",
        "sab_purchase_requirement_ids.odoo_purchase_line_id.qty_received",
        "sab_purchase_requirement_ids.odoo_purchase_line_id.qty_invoiced",
        "sab_purchase_requirement_ids.odoo_purchase_order_id.state",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_ordered",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_received",
        "sab_purchase_requirement_ids.purchase_order_id.state",
    )
    def _compute_procurement_overview(self):
        super()._compute_procurement_overview()
        for project in self:
            active_requirements = project.sab_purchase_requirement_ids.filtered(
                lambda requirement: not requirement.optional
                and requirement.state != "cancel"
            )
            package_requirements = active_requirements.filtered(
                lambda requirement: requirement.bom_id.bom_scope == "procurement"
            )
            requirements = package_requirements or active_requirements.filtered(
                lambda requirement: requirement.bom_id.bom_scope == "total"
            )

            required_quantity = 0.0
            available_quantity = 0.0
            ordered_quantity = 0.0
            received_quantity = 0.0
            required_value = 0.0
            available_value = 0.0
            procured_value = 0.0
            received_value = 0.0
            available_ratios = []
            procured_ratios = []

            standard_orders = self.env["purchase.order"]
            legacy_orders = self.env["sab.purchase.order"]

            for requirement in requirements:
                required = max(requirement.quantity or 0.0, 0.0)
                if required <= 0:
                    continue
                price = max(requirement.unit_purchase_price or 0.0, 0.0)
                commissioned = max(
                    getattr(requirement, "commissioned_quantity", 0.0) or 0.0,
                    0.0,
                )
                physically_available = min(
                    max(requirement.project_reserved_quantity or 0.0, 0.0)
                    + commissioned,
                    required,
                )

                standard_line = requirement.odoo_purchase_line_id
                standard_ordered_open = 0.0
                standard_received = 0.0
                if standard_line and standard_line.order_id.state != "cancel":
                    standard_orders |= standard_line.order_id
                    standard_received = min(
                        max(standard_line.qty_received or 0.0, 0.0),
                        required,
                    )
                    if standard_line.order_id.state == "purchase":
                        standard_ordered_open = max(
                            (standard_line.product_qty or 0.0)
                            - (standard_line.qty_received or 0.0),
                            0.0,
                        )

                legacy_line = requirement.purchase_order_line_id
                legacy_ordered_open = 0.0
                legacy_received = 0.0
                if legacy_line and legacy_line.order_id.state != "cancel":
                    legacy_orders |= legacy_line.order_id
                    legacy_received = min(
                        max(legacy_line.quantity_received or 0.0, 0.0),
                        required,
                    )
                    if legacy_line.order_id.state in (
                        "approved",
                        "sent",
                        "partial",
                        "done",
                    ):
                        legacy_ordered_open = max(
                            legacy_line.quantity_remaining or 0.0,
                            0.0,
                        )

                ordered_open = (
                    standard_ordered_open
                    if standard_line
                    else legacy_ordered_open
                )
                received = standard_received if standard_line else legacy_received
                procured = min(physically_available + ordered_open, required)

                required_quantity += required
                available_quantity += physically_available
                ordered_quantity += min(ordered_open, required)
                received_quantity += received

                line_value = required * price
                available_ratio = physically_available / required
                procured_ratio = procured / required
                required_value += line_value
                available_value += line_value * available_ratio
                procured_value += line_value * procured_ratio
                received_value += received * price
                available_ratios.append(available_ratio)
                procured_ratios.append(procured_ratio)

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
            project.sab_material_required_quantity = required_quantity
            project.sab_material_reserved_quantity = available_quantity
            project.sab_material_ordered_quantity = ordered_quantity
            project.sab_material_received_quantity = received_quantity
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
            project.sab_purchase_order_count = (
                len(standard_orders) if standard_orders else len(legacy_orders)
            )

            released_boms = project.sab_bom_ids.filtered(
                lambda bom: bom.bom_scope in ("procurement", "total")
                and bom.purchase_release_state == "released"
            )
            if requirements and project.sab_material_available_percent >= 99.999:
                state = "complete"
            elif any(
                requirement.odoo_purchase_line_id.qty_received > 1e-9
                for requirement in requirements
            ) or any(
                requirement.purchase_order_line_id.quantity_received > 1e-9
                for requirement in requirements
            ):
                state = "partial"
            elif any(order.state == "purchase" for order in standard_orders) or any(
                order.state in ("sent", "partial", "done")
                for order in legacy_orders
            ):
                state = "ordered"
            elif any(
                order.state in ("draft", "sent", "to approve")
                for order in standard_orders
            ) or any(
                order.state in ("draft", "to_approve", "approved")
                for order in legacy_orders
            ):
                state = "preparing"
            elif released_boms:
                state = "released"
            else:
                state = "not_started"
            project.sab_procurement_state = state

    def action_view_sab_material_requirements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Materialbedarf – %s") % self.display_name,
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [
                ("project_id", "=", self.id),
                ("bom_id.bom_scope", "in", ("procurement", "total")),
                ("state", "!=", "cancel"),
            ],
            "context": {
                "search_default_open": 0,
                "search_default_group_project": 0,
            },
            "target": "current",
        }

    def action_view_sab_purchase_orders(self):
        self.ensure_one()
        standard_orders = self.sab_purchase_requirement_ids.mapped(
            "odoo_purchase_order_id"
        )
        if standard_orders:
            return self.action_view_sab_standard_purchase_orders()
        return super().action_view_sab_purchase_orders()
