from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabProjectBomProcurementRegressionFix(models.Model):
    _inherit = "sab.project.bom"

    def action_print_picking_list(self):
        """Print directly instead of opening Odoo's layout configurator.

        Odoo 19 returns the external-layout setup window for administrators when
        no company report layout has been configured yet. A warehouse picking
        list is an operational document and must therefore always trigger the
        report action directly.
        """
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            raise ValidationError(
                "Eine Kommissionierliste kann nur für ein Beschaffungspaket gedruckt werden."
            )
        self._sab_push_to_procurement_workspace()
        return self.env.ref(
            "sab_project.action_report_sab_procurement_picking"
        ).report_action(self, config=False)


class SabPurchaseRequirementProcurementRegressionFix(models.Model):
    _inherit = "sab.purchase.requirement"

    # sab_procurement_package historically replaced the complete selection after
    # sab_procurement_status had added these workflow values. Re-add them at the
    # end of the model chain so computed purchase stages remain valid values.
    stock_status = fields.Selection(
        selection_add=[
            ("proposal", "Bestellvorschlag"),
            ("approval", "Zur Bestellfreigabe"),
            ("approved", "Freigegeben – noch nicht versendet"),
        ],
        ondelete={
            "proposal": "set null",
            "approval": "set null",
            "approved": "set null",
        },
    )

    @api.depends(
        "quantity",
        "state",
        "stock_movement_ids.movement_type",
        "stock_movement_ids.quantity",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_line_id.quantity_remaining",
        "purchase_order_line_id.order_id.state",
        "purchase_order_id.state",
    )
    def _compute_procurement_quantities(self):
        """Finalize quantities and status after all procurement extensions.

        The package extension is loaded after the detailed purchase-status
        extension. Without a final reconciliation, a draft purchase order can be
        overwritten with the stock status ``missing``. This method keeps the
        real project shortage and gives the actual purchase-order stage priority.
        """
        super()._compute_procurement_quantities()
        for requirement in self:
            on_hand, reserved_total, available = (
                requirement._product_stock_totals()
            )
            own_movements = requirement.stock_movement_ids
            own_reserved = max(
                sum(
                    own_movements.filtered(
                        lambda movement: movement.movement_type == "reserve"
                    ).mapped("quantity")
                )
                - sum(
                    own_movements.filtered(
                        lambda movement: movement.movement_type == "release"
                    ).mapped("quantity")
                ),
                0.0,
            )
            commissioned = max(
                sum(
                    own_movements.filtered(
                        lambda movement: movement.movement_type == "issue"
                    ).mapped("quantity")
                ),
                0.0,
            )
            required_quantity = max(requirement.quantity or 0.0, 0.0)
            shortage = max(
                required_quantity - own_reserved - commissioned,
                0.0,
            )

            requirement.warehouse_on_hand = on_hand
            requirement.warehouse_reserved = reserved_total
            requirement.warehouse_available = available
            requirement.project_reserved_quantity = own_reserved
            requirement.commissioned_quantity = commissioned
            requirement.shortage_quantity = shortage
            # Der automatische Vorschlag ist ausschließlich der reale Fehlbestand.
            requirement.suggested_order_quantity = shortage

            order_line = requirement.purchase_order_line_id
            order_state = order_line.order_id.state if order_line else False
            if requirement.state == "cancel" or order_state == "cancel":
                status = "cancel"
            elif order_line and order_line.quantity_remaining <= 1e-9:
                status = "received"
            elif order_line and order_line.quantity_received > 1e-9:
                status = "partial_received"
            elif order_line and order_state == "draft":
                status = "proposal"
            elif order_line and order_state == "to_approve":
                status = "approval"
            elif order_line and order_state == "approved":
                status = "approved"
            elif order_line and order_state in ("sent", "partial", "done"):
                status = "ordered"
            elif required_quantity > 0 and commissioned >= required_quantity - 1e-9:
                status = "commissioned"
            elif commissioned > 1e-9:
                status = "partial_commissioned"
            elif shortage <= 1e-9:
                status = "in_stock"
            elif own_reserved > 1e-9:
                status = "partial"
            else:
                status = "missing"
            requirement.stock_status = status


class SabProjectBomLineProcurementRegressionFix(models.Model):
    _inherit = "sab.project.bom.line"

    @api.depends(
        "bom_id.project_id",
        "bom_id.order_id",
        "bom_id.bom_scope",
        "product_id",
        "odoo_product_id",
        "source_cabinet_line_id",
        "bom_id.project_id.sab_purchase_requirement_ids.state",
        "bom_id.project_id.sab_purchase_requirement_ids.bom_line_id",
        "bom_id.project_id.sab_purchase_requirement_ids.source_cabinet_line_id",
        "bom_id.project_id.sab_purchase_requirement_ids.product_id",
        "bom_id.project_id.sab_purchase_requirement_ids.odoo_product_id",
        "bom_id.project_id.sab_purchase_requirement_ids.project_reserved_quantity",
        "bom_id.project_id.sab_purchase_requirement_ids.shortage_quantity",
        "bom_id.project_id.sab_purchase_requirement_ids.stock_status",
        "bom_id.project_id.sab_purchase_requirement_ids.expected_delivery_date",
    )
    def _compute_procurement_status_fields(self):
        """Prefer package requirements but retain the total-BOM fallback.

        Existing projects and the interval before a material package is created
        still obtain their delivery status from the released total BOM. As soon
        as a selected-cabinet package exists, its position-specific requirement
        takes precedence.
        """
        super()._compute_procurement_status_fields()
        Requirement = self.env["sab.purchase.requirement"].sudo()

        for line in self.filtered(
            lambda record: record.bom_id
            and record.bom_id.bom_scope in ("procurement", "cabinet")
        ):
            if line.bom_id.bom_scope == "procurement":
                requirement = Requirement.search(
                    [
                        ("bom_line_id", "=", line.id),
                        ("state", "!=", "cancel"),
                    ],
                    limit=1,
                )
            else:
                requirement = Requirement.search(
                    [
                        ("bom_id.bom_scope", "=", "procurement"),
                        ("source_cabinet_line_id", "=", line.id),
                        ("state", "!=", "cancel"),
                    ],
                    order="create_date desc, id desc",
                    limit=1,
                )
                if not requirement:
                    domain = [
                        ("project_id", "=", line.bom_id.project_id.id),
                        ("bom_id.order_id", "=", line.bom_id.order_id.id),
                        ("bom_id.bom_scope", "=", "total"),
                        ("state", "!=", "cancel"),
                    ]
                    if line.odoo_product_id:
                        domain.append(
                            ("odoo_product_id", "=", line.odoo_product_id.id)
                        )
                    elif line.product_id:
                        domain.append(("product_id", "=", line.product_id.id))
                    else:
                        domain = []
                    requirement = (
                        Requirement.search(domain, limit=1)
                        if domain
                        else Requirement
                    )

            line.purchase_requirement_id = requirement
            line.procurement_status = (
                requirement.stock_status if requirement else False
            )
            line.expected_delivery_date = (
                requirement.expected_delivery_date if requirement else False
            )
            line.project_reserved_quantity = (
                requirement.project_reserved_quantity if requirement else 0.0
            )
            line.shortage_quantity = (
                requirement.shortage_quantity if requirement else 0.0
            )
