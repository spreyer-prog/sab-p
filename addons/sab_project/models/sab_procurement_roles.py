from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command


class SabEmployeeProfileProcurementRoles(models.Model):
    _inherit = "sab.employee.profile"

    purchasing_access = fields.Boolean(
        string="Einkauf",
        default=False,
        tracking=True,
        help="Darf freigegebene Fehlbestände sammeln, Bestellvorschläge erstellen und Bestellungen versenden.",
    )
    purchase_approval_access = fields.Boolean(
        string="Bestellfreigabe",
        default=False,
        tracking=True,
        help="Darf Gesamtstücklisten zur Beschaffung und fertige Lieferantenbestellungen freigeben.",
    )
    warehouse_access = fields.Boolean(
        string="Lager / Wareneingang",
        default=False,
        tracking=True,
        help="Darf Lagerbestände einsehen, Wareneingänge buchen und Material projektbezogen kommissionieren.",
    )

    def _desired_group_commands(self, user):
        commands = list(super()._desired_group_commands(user))
        desired = {
            self.env.ref("sab_project.group_sab_purchasing"): self.purchasing_access,
            self.env.ref("sab_project.group_sab_purchase_approver"): self.purchase_approval_access,
            self.env.ref("sab_project.group_sab_warehouse"): self.warehouse_access,
        }
        for group, enabled in desired.items():
            if enabled and group not in user.group_ids:
                commands.append(Command.link(group.id))
            elif not enabled and group in user.group_ids:
                commands.append(Command.unlink(group.id))
        return commands


class SabProjectBomPurchaseApproval(models.Model):
    _inherit = ["sab.project.bom", "mail.thread", "mail.activity.mixin"]

    def _sab_check_project_manager(self):
        """Compatibility method: approval now follows the employee profile role."""
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchase_approver")
        ):
            return True
        raise AccessError(
            "Die Bestellfreigabe darf nur durch einen im Mitarbeiterprofil "
            "festgelegten Bestellfreigeber erteilt werden."
        )

    def write(self, vals):
        procurement_fields = {
            "purchase_release_state",
            "purchase_released_at",
            "purchase_released_by_id",
        }
        if vals and set(vals).issubset(procurement_fields):
            # The technical BOM lock remains active for all technical fields.
            # Only the later procurement approval metadata may be written.
            return models.Model.write(self, vals)
        return super().write(vals)


class SabPurchaseRequirementApproval(models.Model):
    _inherit = "sab.purchase.requirement"

    expected_delivery_date = fields.Date(
        related="purchase_order_line_id.expected_delivery_date",
        string="Voraussichtlicher Liefertermin",
        store=True,
        readonly=True,
    )

    def action_create_purchase_orders(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Bestellvorschläge dürfen nur durch einen im Mitarbeiterprofil "
                "freigeschalteten Einkaufsmitarbeiter erzeugt werden."
            )
        not_released = self.exists().filtered(
            lambda requirement: requirement.bom_id.purchase_release_state != "released"
        )
        if not_released:
            raise ValidationError(
                "Bestellungen dürfen erst nach Freigabe der Gesamtstückliste "
                "durch einen hinterlegten Bestellfreigeber erzeugt werden."
            )
        return super().action_create_purchase_orders()


class SabPurchaseOrderApproval(models.Model):
    _inherit = "sab.purchase.order"

    next_delivery_date = fields.Date(
        string="Nächster Liefertermin",
        compute="_compute_next_delivery_date",
        store=True,
    )

    @api.depends(
        "line_ids.expected_delivery_date",
        "line_ids.quantity_remaining",
        "state",
    )
    def _compute_next_delivery_date(self):
        for order in self:
            dates = order.line_ids.filtered(
                lambda line: line.quantity_remaining > 0 and line.expected_delivery_date
            ).mapped("expected_delivery_date")
            order.next_delivery_date = min(dates) if dates else False

    def _check_purchasing_user(self):
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            return True
        raise AccessError(
            "Diese Funktion ist einem im Mitarbeiterprofil "
            "freigeschalteten Einkaufsmitarbeiter vorbehalten."
        )

    def _check_receiving_user(self):
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            return True
        raise AccessError(
            "Wareneingänge dürfen nur durch im Mitarbeiterprofil "
            "freigeschaltete Lager- oder Einkaufsmitarbeiter gebucht werden."
        )

    def _check_project_manager(self):
        """Compatibility method: approval now follows the employee profile role."""
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchase_approver")
        ):
            return True
        raise AccessError(
            "Die Bestellung muss durch einen im Mitarbeiterprofil "
            "festgelegten Bestellfreigeber freigegeben werden."
        )

    def action_submit_for_approval(self):
        approver_group = self.env.ref(
            "sab_project.group_sab_purchase_approver",
            raise_if_not_found=False,
        )
        approvers = approver_group.user_ids.filtered("active") if approver_group else self.env["res.users"]
        if not approvers:
            raise ValidationError(
                "Es ist kein aktiver Bestellfreigeber im Mitarbeiterprofil hinterlegt."
            )
        result = super().action_submit_for_approval()
        approver_group = self.env.ref(
            "sab_project.group_sab_purchase_approver",
            raise_if_not_found=False,
        )
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if not approver_group or not activity_type:
            return result

        model_id = self.env["ir.model"]._get_id(self._name)
        for order in self:
            for user in approvers:
                existing = self.env["mail.activity"].search_count([
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", order.id),
                    ("user_id", "=", user.id),
                    ("summary", "=", "Lieferantenbestellung freigeben"),
                ])
                if not existing:
                    self.env["mail.activity"].create({
                        "activity_type_id": activity_type.id,
                        "res_model_id": model_id,
                        "res_id": order.id,
                        "user_id": user.id,
                        "summary": "Lieferantenbestellung freigeben",
                        "note": (
                            f"Bestellung {order.name} an {order.supplier_id.name} "
                            "wurde zur Freigabe vorgelegt."
                        ),
                    })
        return result

    def action_approve(self):
        result = super().action_approve()
        model_id = self.env["ir.model"]._get_id(self._name)
        activities = self.env["mail.activity"].search([
            ("res_model_id", "=", model_id),
            ("res_id", "in", self.ids),
            ("summary", "=", "Lieferantenbestellung freigeben"),
        ])
        if activities:
            activities.sudo().unlink()
        return result

    def action_send_order_email(self):
        for order in self:
            if order.state != "approved":
                raise ValidationError(
                    "Die Bestellung muss vor dem Versand durch einen "
                    "hinterlegten Bestellfreigeber freigegeben werden."
                )
        return super().action_send_order_email()


class SabPurchaseOrderLineDelivery(models.Model):
    _inherit = "sab.purchase.order.line"

    expected_delivery_date = fields.Date(
        string="Voraussichtlicher Liefertermin",
        copy=False,
        index=True,
        help="Vom Lieferanten bestätigter oder erwarteter Liefertermin dieser Produktposition.",
    )

    def write(self, vals):
        if "expected_delivery_date" in vals and any(
            line.order_id.state in ("done", "cancel") for line in self
        ):
            raise ValidationError(
                "Bei abgeschlossenen oder stornierten Bestellungen darf der "
                "Liefertermin nicht mehr geändert werden."
            )
        return super().write(vals)


class SabProjectBomLineProcurementStatus(models.Model):
    _inherit = "sab.project.bom.line"

    purchase_requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="Projektweiter Einkaufsbedarf",
        compute="_compute_purchase_requirement_id",
    )
    procurement_status = fields.Selection(
        related="purchase_requirement_id.stock_status",
        string="Materialstatus",
        readonly=True,
    )
    expected_delivery_date = fields.Date(
        related="purchase_requirement_id.expected_delivery_date",
        string="Voraussichtlicher Liefertermin",
        readonly=True,
    )
    project_reserved_quantity = fields.Float(
        related="purchase_requirement_id.project_reserved_quantity",
        string="Projektweit reserviert",
        readonly=True,
    )
    shortage_quantity = fields.Float(
        related="purchase_requirement_id.shortage_quantity",
        string="Projektweiter Fehlbestand",
        readonly=True,
    )

    @api.depends(
        "bom_id.project_id",
        "bom_id.bom_scope",
        "product_id",
        "odoo_product_id",
    )
    def _compute_purchase_requirement_id(self):
        Requirement = self.env["sab.purchase.requirement"]
        for line in self:
            requirement = Requirement
            if line.bom_id and line.bom_id.bom_scope == "total":
                requirement = Requirement.search([
                    ("bom_line_id", "=", line.id),
                    ("state", "!=", "cancel"),
                ], limit=1)
            elif line.bom_id and line.bom_id.project_id:
                domain = [
                    ("project_id", "=", line.bom_id.project_id.id),
                    ("bom_id.bom_scope", "=", "total"),
                    ("state", "!=", "cancel"),
                ]
                if line.odoo_product_id:
                    domain.append(("odoo_product_id", "=", line.odoo_product_id.id))
                elif line.product_id:
                    domain.append(("product_id", "=", line.product_id.id))
                else:
                    domain = []
                if domain:
                    requirement = Requirement.search(domain, limit=1)
            line.purchase_requirement_id = requirement


class SabProjectBomProcurementSummary(models.Model):
    _inherit = "sab.project.bom"

    sab_material_available_percent = fields.Float(
        string="Material vorhanden (%)",
        compute="_compute_sab_procurement_summary",
    )
    sab_material_missing_percent = fields.Float(
        string="Material fehlt (%)",
        compute="_compute_sab_procurement_summary",
    )
    sab_expected_delivery_date = fields.Date(
        string="Spätester offener Liefertermin",
        compute="_compute_sab_procurement_summary",
    )

    @api.depends(
        "line_ids.quantity",
        "line_ids.unit_purchase_price",
        "line_ids.purchase_requirement_id.project_reserved_quantity",
        "line_ids.purchase_requirement_id.quantity",
        "line_ids.purchase_requirement_id.expected_delivery_date",
        "line_ids.purchase_requirement_id.stock_status",
    )
    def _compute_sab_procurement_summary(self):
        for bom in self:
            weighted_total = 0.0
            weighted_available = 0.0
            fallback_ratios = []
            delivery_dates = []
            for line in bom.line_ids.filtered(lambda item: not item.optional):
                requirement = line.purchase_requirement_id
                if not requirement or not requirement.quantity:
                    ratio = 0.0
                else:
                    ratio = min(
                        max(
                            (requirement.project_reserved_quantity or 0.0)
                            / requirement.quantity,
                            0.0,
                        ),
                        1.0,
                    )
                fallback_ratios.append(ratio)
                line_value = max(
                    (line.quantity or 0.0) * (line.unit_purchase_price or 0.0),
                    0.0,
                )
                weighted_total += line_value
                weighted_available += line_value * ratio
                if (
                    requirement
                    and requirement.stock_status not in ("in_stock", "received")
                    and requirement.expected_delivery_date
                ):
                    delivery_dates.append(requirement.expected_delivery_date)

            if weighted_total > 0:
                available_percent = weighted_available / weighted_total * 100.0
            elif fallback_ratios:
                available_percent = (
                    sum(fallback_ratios) / len(fallback_ratios) * 100.0
                )
            else:
                available_percent = 0.0

            bom.sab_material_available_percent = min(
                max(available_percent, 0.0),
                100.0,
            )
            bom.sab_material_missing_percent = max(
                100.0 - bom.sab_material_available_percent,
                0.0,
            )
            bom.sab_expected_delivery_date = (
                max(delivery_dates) if delivery_dates else False
            )
