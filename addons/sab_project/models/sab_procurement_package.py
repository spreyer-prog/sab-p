import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabProjectBomProcurementPackage(models.Model):
    _inherit = "sab.project.bom"

    procurement_reference = fields.Char(
        string="Materialanforderung",
        readonly=True,
        copy=False,
        index=True,
    )
    source_cabinet_bom_ids = fields.Many2many(
        "sab.project.bom",
        relation="sab_procurement_package_cabinet_rel",
        column1="package_bom_id",
        column2="cabinet_bom_id",
        string="Enthaltene Schaltschränke",
        copy=False,
        readonly=True,
    )
    source_cabinet_count = fields.Integer(
        string="Schaltschränke",
        compute="_compute_source_cabinet_count",
    )
    procurement_acknowledged = fields.Boolean(
        string="Vom Einkauf geöffnet",
        default=False,
        copy=False,
        index=True,
    )
    procurement_acknowledged_at = fields.Datetime(
        string="Vom Einkauf geöffnet am",
        readonly=True,
        copy=False,
    )
    procurement_acknowledged_by_id = fields.Many2one(
        "res.users",
        string="Vom Einkauf geöffnet durch",
        readonly=True,
        copy=False,
    )
    picking_user_id = fields.Many2one(
        "res.users",
        string="Kommissionierung zugewiesen an",
        copy=False,
        domain="[('active','=',True),('share','=',False)]",
    )
    picking_state = fields.Selection(
        [
            ("not_assigned", "Nicht zugewiesen"),
            ("assigned", "Zugewiesen"),
            ("partial", "Teilweise kommissioniert"),
            ("done", "Aktuell vollständig kommissioniert"),
        ],
        string="Kommissionierstatus",
        default="not_assigned",
        required=True,
        copy=False,
        index=True,
    )
    picking_assigned_at = fields.Datetime(
        string="Kommissionierung zugewiesen am",
        readonly=True,
        copy=False,
    )
    picking_assigned_by_id = fields.Many2one(
        "res.users",
        string="Kommissionierung zugewiesen durch",
        readonly=True,
        copy=False,
    )
    picking_completed_at = fields.Datetime(
        string="Zuletzt kommissioniert am",
        readonly=True,
        copy=False,
    )
    picking_completed_by_id = fields.Many2one(
        "res.users",
        string="Zuletzt kommissioniert durch",
        readonly=True,
        copy=False,
    )

    @api.depends("source_cabinet_bom_ids")
    def _compute_source_cabinet_count(self):
        for package in self:
            package.source_cabinet_count = len(package.source_cabinet_bom_ids)

    @api.constrains(
        "bom_scope",
        "source_cabinet_bom_ids",
        "order_id",
        "project_id",
    )
    def _check_procurement_package_sources(self):
        for package in self.filtered(
            lambda record: getattr(record, "bom_scope", "total") == "procurement"
        ):
            if not package.source_cabinet_bom_ids:
                raise ValidationError(
                    "Ein Beschaffungspaket benötigt mindestens einen ausgewählten Schaltschrank."
                )
            invalid = package.source_cabinet_bom_ids.filtered(
                lambda cabinet: cabinet.bom_scope != "cabinet"
                or cabinet.state != "released"
                or cabinet.order_id != package.order_id
                or cabinet.project_id != package.project_id
            )
            if invalid:
                raise ValidationError(
                    "Ein Beschaffungspaket darf ausschließlich technisch freigegebene "
                    "Schaltschrank-Stücklisten desselben Auftrags und Projekts enthalten."
                )

    def _sab_released_bom_allowed_fields(self):
        return super()._sab_released_bom_allowed_fields() | {
            "procurement_acknowledged",
            "procurement_acknowledged_at",
            "procurement_acknowledged_by_id",
            "picking_user_id",
            "picking_state",
            "picking_assigned_at",
            "picking_assigned_by_id",
            "picking_completed_at",
            "picking_completed_by_id",
        }

    def action_generate_purchase_requirements(self):
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            return super().action_generate_purchase_requirements()
        if self.state != "released":
            raise ValidationError(
                "Einkaufsbedarf kann erst aus einem freigegebenen Beschaffungspaket erzeugt werden."
            )
        Requirement = self.env["sab.purchase.requirement"]
        existing_line_ids = set(
            self.purchase_requirement_ids.mapped("bom_line_id").ids
        )
        for line in self.line_ids.filtered(lambda item: not item.optional):
            if line.id not in existing_line_ids:
                Requirement.create({"bom_line_id": line.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Materialanforderung – %s")
            % (self.procurement_reference or self.name),
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [("bom_id", "=", self.id)],
            "target": "current",
        }

    def action_release_for_purchase(self):
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            return super().action_release_for_purchase()
        if not (
            self.env.is_superuser()
            or self.env.user.has_group(
                "sab_project.group_sab_purchase_approver"
            )
        ):
            raise AccessError(
                "Das Beschaffungspaket darf nur durch einen im Mitarbeiterprofil "
                "hinterlegten Bestellfreigeber freigegeben werden."
            )
        if self.state != "released":
            raise ValidationError(
                "Das Beschaffungspaket muss technisch freigegeben sein."
            )
        if not self.line_ids:
            raise ValidationError(
                "Ein leeres Beschaffungspaket kann nicht freigegeben werden."
            )

        purchasing_group = self.env.ref(
            "sab_project.group_sab_purchasing",
            raise_if_not_found=False,
        )
        purchasing_users = (
            purchasing_group.user_ids.filtered("active")
            if purchasing_group
            else self.env["res.users"]
        )
        if not purchasing_users:
            raise ValidationError(
                "Es ist kein aktiver Einkaufsmitarbeiter im Mitarbeiterprofil hinterlegt."
            )

        obsolete = self.env["sab.purchase.requirement"].sudo().search(
            [
                ("order_id", "=", self.order_id.id),
                ("bom_id", "!=", self.id),
                ("bom_id.bom_scope", "in", ("total", "cabinet")),
                ("state", "=", "open"),
                ("purchase_order_line_id", "=", False),
            ]
        )
        if obsolete:
            obsolete._release_project_reservation()
            obsolete.unlink()

        self.with_context(
            sab_procurement_release=True
        ).action_generate_purchase_requirements()
        requirements = self.purchase_requirement_ids.filtered(
            lambda requirement: not requirement.optional
            and requirement.state == "open"
        )
        requirements._reserve_available_stock()
        requirements._sab_prepare_order_quantities()
        self.write(
            {
                "purchase_release_state": "released",
                "purchase_released_at": fields.Datetime.now(),
                "purchase_released_by_id": self.env.user.id,
            }
        )

        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if activity_type:
            model_id = self.env["ir.model"]._get_id(self._name)
            for user in purchasing_users:
                existing = self.env["mail.activity"].search_count(
                    [
                        ("res_model_id", "=", model_id),
                        ("res_id", "=", self.id),
                        ("user_id", "=", user.id),
                        ("summary", "=", "Beschaffungspaket bearbeiten"),
                    ]
                )
                if not existing:
                    self.env["mail.activity"].create(
                        {
                            "activity_type_id": activity_type.id,
                            "res_model_id": model_id,
                            "res_id": self.id,
                            "user_id": user.id,
                            "summary": "Beschaffungspaket bearbeiten",
                            "note": (
                                f"{self.procurement_reference or self.name} wurde "
                                "zur Beschaffung freigegeben. Bitte Fehlbestände "
                                "prüfen und Bestellvorschläge erzeugen."
                            ),
                        }
                    )
        return self.action_open_procurement_workspace()

    def _check_picking_operator(self):
        self.ensure_one()
        allowed = (
            self.env.is_superuser()
            or self.env.user == self.picking_user_id
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
            or self.env.user.has_group("project.group_project_manager")
        )
        if not allowed:
            raise AccessError(
                "Die Kommissionierung darf nur durch den zugewiesenen Mitarbeiter, "
                "Lager, Einkauf oder Projektleitung bearbeitet werden."
            )
        return True

    def action_assign_picking(self):
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            raise ValidationError(
                "Eine Kommissionierung kann nur einem Beschaffungspaket zugewiesen werden."
            )
        if not self.picking_user_id:
            raise ValidationError(
                "Bitte zuerst einen Mitarbeiter für die Kommissionierung auswählen."
            )
        if not (
            self.picking_user_id.has_group("sab_project.group_sab_warehouse")
            or self.picking_user_id.has_group("sab_project.group_sab_purchasing")
            or self.picking_user_id.has_group("project.group_project_manager")
        ):
            raise ValidationError(
                "Der ausgewählte Mitarbeiter benötigt die Berechtigung Lager, Einkauf "
                "oder Projektleitung."
            )
        self.write(
            {
                "picking_state": "assigned",
                "picking_assigned_at": fields.Datetime.now(),
                "picking_assigned_by_id": self.env.user.id,
            }
        )
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if activity_type:
            model_id = self.env["ir.model"]._get_id(self._name)
            existing = self.env["mail.activity"].search_count(
                [
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", self.id),
                    ("user_id", "=", self.picking_user_id.id),
                    ("summary", "=", "Material kommissionieren"),
                ]
            )
            if not existing:
                self.env["mail.activity"].create(
                    {
                        "activity_type_id": activity_type.id,
                        "res_model_id": model_id,
                        "res_id": self.id,
                        "user_id": self.picking_user_id.id,
                        "summary": "Material kommissionieren",
                        "note": (
                            f"Bitte Lagerware für {self.procurement_reference or self.name} "
                            "nach Verteilerzuordnung kommissionieren."
                        ),
                    }
                )
        return True

    def action_print_picking_list(self):
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            raise ValidationError(
                "Eine Kommissionierliste kann nur für ein Beschaffungspaket gedruckt werden."
            )
        self._sab_push_to_procurement_workspace()
        return self.env.ref(
            "sab_project.action_report_sab_procurement_picking"
        ).report_action(self)

    def action_complete_picking(self):
        self.ensure_one()
        self._check_picking_operator()
        if not self.picking_user_id:
            raise ValidationError(
                "Die Kommissionierung muss vor der Buchung einem Mitarbeiter zugewiesen werden."
            )
        requirements = self.purchase_requirement_ids.filtered(
            lambda requirement: requirement.state != "cancel"
            and not requirement.optional
        )
        requirements.invalidate_recordset()
        Movement = self.env["sab.stock.movement"]
        booked = False
        for requirement in requirements:
            open_for_picking = max(
                (requirement.quantity or 0.0)
                - (requirement.commissioned_quantity or 0.0),
                0.0,
            )
            quantity = min(
                max(requirement.project_reserved_quantity or 0.0, 0.0),
                open_for_picking,
            )
            if quantity <= 0:
                continue
            product_values = requirement._movement_product_values()
            common = {
                **product_values,
                "quantity": quantity,
                "unit": requirement.unit,
                "project_id": requirement.project_id.id,
                "purchase_requirement_id": requirement.id,
                "source_cabinet_bom_id": requirement.source_cabinet_bom_id.id
                or False,
            }
            Movement.create(
                {
                    **common,
                    "movement_type": "release",
                    "note": (
                        f"Reservierung zur Kommissionierung freigegeben: "
                        f"{self.procurement_reference or self.name}"
                    ),
                }
            )
            Movement.create(
                {
                    **common,
                    "movement_type": "issue",
                    "note": (
                        f"Kommissioniert für "
                        f"{requirement.source_cabinet_bom_id.name or self.project_id.display_name}"
                    ),
                }
            )
            booked = True

        if not booked:
            raise ValidationError(
                "Für dieses Beschaffungspaket ist aktuell keine reservierte Lagerware zu kommissionieren."
            )

        requirements.invalidate_recordset()
        requirements._sab_prepare_order_quantities()
        self.write(
            {
                "picking_state": "done",
                "picking_completed_at": fields.Datetime.now(),
                "picking_completed_by_id": self.env.user.id,
            }
        )
        model_id = self.env["ir.model"]._get_id(self._name)
        activities = self.env["mail.activity"].search(
            [
                ("res_model_id", "=", model_id),
                ("res_id", "=", self.id),
                ("summary", "=", "Material kommissionieren"),
            ]
        )
        if activities:
            activities.sudo().unlink()
        return True

    def action_open_extra_line_wizard(self):
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            raise ValidationError(
                "Zusatzpositionen können nur einem Beschaffungspaket hinzugefügt werden."
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Zusatzposition zur Beschaffung"),
            "res_model": "sab.procurement.extra.line.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_procurement_bom_id": self.id,
            },
        }


class SabProjectBomLineProcurementSource(models.Model):
    _inherit = "sab.project.bom.line"

    source_cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler / Schaltschrank",
        ondelete="restrict",
        index=True,
    )
    source_cabinet_line_id = fields.Many2one(
        "sab.project.bom.line",
        string="Ursprüngliche Verteilerposition",
        ondelete="restrict",
        index=True,
    )

    @api.constrains(
        "bom_id",
        "source_cabinet_bom_id",
        "source_cabinet_line_id",
    )
    def _check_procurement_source(self):
        for line in self.filtered(
            lambda record: getattr(record.bom_id, "bom_scope", "total")
            == "procurement"
        ):
            if line.source_cabinet_bom_id and (
                line.source_cabinet_bom_id.bom_scope != "cabinet"
                or line.source_cabinet_bom_id
                not in line.bom_id.source_cabinet_bom_ids
            ):
                raise ValidationError(
                    "Die Verteilerzuordnung einer Beschaffungsposition passt nicht zum Beschaffungspaket."
                )
            if line.source_cabinet_line_id and (
                line.source_cabinet_line_id.bom_id
                != line.source_cabinet_bom_id
            ):
                raise ValidationError(
                    "Die ursprüngliche Stücklistenposition gehört nicht zum angegebenen Verteiler."
                )


class SabPurchaseRequirementProcurementPackage(models.Model):
    _inherit = "sab.purchase.requirement"

    source_cabinet_bom_id = fields.Many2one(
        related="bom_line_id.source_cabinet_bom_id",
        string="Verteiler / Schaltschrank",
        store=True,
        readonly=True,
    )
    source_cabinet_line_id = fields.Many2one(
        related="bom_line_id.source_cabinet_line_id",
        string="Ursprüngliche Verteilerposition",
        store=True,
        readonly=True,
    )
    commissioned_quantity = fields.Float(
        string="Kommissioniert",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    stock_status = fields.Selection(
        [
            ("in_stock", "Vollständig im Lager / reserviert"),
            ("partial", "Teilbestand – Rest bestellen"),
            ("partial_commissioned", "Teilweise kommissioniert"),
            ("commissioned", "Vollständig kommissioniert"),
            ("missing", "Nicht im Lager"),
            ("ordered", "Bestellt"),
            ("partial_received", "Teilgeliefert"),
            ("received", "Vollständig geliefert"),
            ("cancel", "Storniert"),
        ],
        string="Materialstatus",
        compute="_compute_procurement_quantities",
    )

    @api.depends(
        "quantity",
        "state",
        "supplier_product_id.packaging_quantity",
        "supplier_product_id.minimum_order_quantity",
        "stock_movement_ids.movement_type",
        "stock_movement_ids.quantity",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_id.state",
    )
    def _compute_procurement_quantities(self):
        for requirement in self:
            on_hand, reserved_total, available = (
                requirement._product_stock_totals()
            )
            own_movements = requirement.stock_movement_ids
            own_reserved = (
                sum(
                    own_movements.filtered(
                        lambda movement: movement.movement_type == "reserve"
                    ).mapped("quantity")
                )
                - sum(
                    own_movements.filtered(
                        lambda movement: movement.movement_type == "release"
                    ).mapped("quantity")
                )
            )
            commissioned = sum(
                own_movements.filtered(
                    lambda movement: movement.movement_type == "issue"
                ).mapped("quantity")
            )
            fulfilled = own_reserved + commissioned
            shortage = max(
                (requirement.quantity or 0.0) - fulfilled,
                0.0,
            )
            supplier_product = requirement.supplier_product_id
            packaging = (
                max(
                    supplier_product.packaging_quantity or 1.0,
                    0.000001,
                )
                if supplier_product
                else 1.0
            )
            minimum = (
                max(supplier_product.minimum_order_quantity or 0.0, 0.0)
                if supplier_product
                else 0.0
            )
            order_base = max(shortage, minimum) if shortage else 0.0
            suggested = (
                math.ceil(order_base / packaging - 1e-9) * packaging
                if order_base
                else 0.0
            )

            requirement.warehouse_on_hand = on_hand
            requirement.warehouse_reserved = reserved_total
            requirement.warehouse_available = available
            requirement.project_reserved_quantity = own_reserved
            requirement.commissioned_quantity = commissioned
            requirement.shortage_quantity = shortage
            requirement.suggested_order_quantity = suggested

            order_line = requirement.purchase_order_line_id
            if requirement.state == "cancel":
                status = "cancel"
            elif commissioned >= (requirement.quantity or 0.0) - 1e-9:
                status = "commissioned"
            elif order_line and order_line.quantity_remaining <= 0:
                status = "received"
            elif order_line and order_line.quantity_received > 0:
                status = "partial_received"
            elif order_line and requirement.purchase_order_id.state in (
                "to_approve",
                "approved",
                "sent",
                "partial",
                "done",
            ):
                status = "ordered"
            elif shortage <= 0:
                status = "in_stock"
            elif commissioned > 0:
                status = "partial_commissioned"
            elif own_reserved > 0:
                status = "partial"
            else:
                status = "missing"
            requirement.stock_status = status


class SabProjectBomLineProcurementPackageStatus(models.Model):
    _inherit = "sab.project.bom.line"

    @api.depends(
        "bom_id.project_id",
        "bom_id.order_id",
        "bom_id.bom_scope",
        "product_id",
        "odoo_product_id",
        "source_cabinet_line_id",
        "bom_id.project_id.sab_purchase_requirement_ids.state",
        "bom_id.project_id.sab_purchase_requirement_ids.project_reserved_quantity",
        "bom_id.project_id.sab_purchase_requirement_ids.shortage_quantity",
        "bom_id.project_id.sab_purchase_requirement_ids.stock_status",
        "bom_id.project_id.sab_purchase_requirement_ids.expected_delivery_date",
    )
    def _compute_procurement_status_fields(self):
        handled = self.filtered(
            lambda line: getattr(line.bom_id, "bom_scope", "total")
            in ("procurement", "cabinet")
        )
        remaining = self - handled
        if remaining:
            super(
                SabProjectBomLineProcurementPackageStatus,
                remaining,
            )._compute_procurement_status_fields()

        Requirement = self.env["sab.purchase.requirement"].sudo()
        for line in handled:
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


class SabProjectBomProcurementPackageSummary(models.Model):
    _inherit = "sab.project.bom"

    @api.depends(
        "bom_scope",
        "purchase_requirement_ids.quantity",
        "purchase_requirement_ids.unit_purchase_price",
        "purchase_requirement_ids.project_reserved_quantity",
        "purchase_requirement_ids.commissioned_quantity",
        "purchase_requirement_ids.shortage_quantity",
        "purchase_requirement_ids.stock_status",
        "purchase_requirement_ids.expected_delivery_date",
    )
    def _compute_sab_procurement_summary(self):
        packages = self.filtered(
            lambda bom: getattr(bom, "bom_scope", "total") == "procurement"
        )
        remaining = self - packages
        if remaining:
            super(
                SabProjectBomProcurementPackageSummary,
                remaining,
            )._compute_sab_procurement_summary()

        for package in packages:
            requirements = package.purchase_requirement_ids.filtered(
                lambda requirement: not requirement.optional
                and requirement.state != "cancel"
                and (requirement.quantity or 0.0) > 0
            )
            weighted_total = 0.0
            weighted_available = 0.0
            fallback_ratios = []
            delivery_dates = []
            for requirement in requirements:
                available_quantity = min(
                    max(
                        (requirement.project_reserved_quantity or 0.0)
                        + (requirement.commissioned_quantity or 0.0),
                        0.0,
                    ),
                    requirement.quantity,
                )
                ratio = available_quantity / requirement.quantity
                fallback_ratios.append(ratio)
                line_value = max(
                    (requirement.quantity or 0.0)
                    * (requirement.unit_purchase_price or 0.0),
                    0.0,
                )
                weighted_total += line_value
                weighted_available += line_value * ratio
                if (
                    requirement.stock_status
                    not in ("in_stock", "commissioned", "received")
                    and requirement.expected_delivery_date
                ):
                    delivery_dates.append(
                        requirement.expected_delivery_date
                    )

            if weighted_total > 0:
                available_percent = (
                    weighted_available / weighted_total * 100.0
                )
            elif fallback_ratios:
                available_percent = (
                    sum(fallback_ratios) / len(fallback_ratios) * 100.0
                )
            else:
                available_percent = 0.0

            package.sab_material_available_percent = min(
                max(available_percent, 0.0),
                100.0,
            )
            package.sab_material_missing_percent = max(
                100.0 - package.sab_material_available_percent,
                0.0,
            )
            package.sab_expected_delivery_date = (
                max(delivery_dates) if delivery_dates else False
            )


class ProjectProjectProcurementPackageOverview(models.Model):
    _inherit = "project.project"

    def _sab_current_procurement_requirements(self):
        self.ensure_one()
        package_requirements = self.sab_purchase_requirement_ids.filtered(
            lambda requirement: requirement.bom_id.bom_scope == "procurement"
            and requirement.bom_id.state == "released"
            and requirement.state != "cancel"
            and not requirement.optional
        )
        if package_requirements:
            return package_requirements
        return self.sab_purchase_requirement_ids.filtered(
            lambda requirement: requirement.bom_id.bom_scope == "total"
            and requirement.state != "cancel"
            and not requirement.optional
        )

    @api.depends(
        "sab_bom_ids.bom_scope",
        "sab_bom_ids.state",
        "sab_bom_ids.purchase_release_state",
        "sab_bom_ids.source_cabinet_bom_ids",
        "sab_purchase_requirement_ids.quantity",
        "sab_purchase_requirement_ids.unit_purchase_price",
        "sab_purchase_requirement_ids.project_reserved_quantity",
        "sab_purchase_requirement_ids.commissioned_quantity",
        "sab_purchase_requirement_ids.state",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_ordered",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_received",
        "sab_purchase_requirement_ids.purchase_order_line_id.quantity_remaining",
        "sab_purchase_requirement_ids.purchase_order_id.state",
    )
    def _compute_procurement_overview(self):
        super()._compute_procurement_overview()
        PurchaseOrder = self.env["sab.purchase.order"]
        for project in self:
            packages = project.sab_bom_ids.filtered(
                lambda bom: bom.bom_scope == "procurement"
                and bom.state == "released"
            )
            if not packages:
                continue
            requirements = project._sab_current_procurement_requirements()
            orders = PurchaseOrder.search(
                [
                    ("line_ids.project_id", "=", project.id),
                    ("state", "!=", "cancel"),
                ]
            )

            required_value = 0.0
            available_value = 0.0
            procured_value = 0.0
            received_value = 0.0
            required_quantity = 0.0
            available_quantity_total = 0.0
            ordered_quantity = 0.0
            received_quantity = 0.0
            available_ratios = []
            procured_ratios = []

            for requirement in requirements:
                quantity = max(requirement.quantity or 0.0, 0.0)
                if quantity <= 0:
                    continue
                unit_price = max(
                    requirement.unit_purchase_price or 0.0,
                    0.0,
                )
                available_quantity = min(
                    max(
                        (requirement.project_reserved_quantity or 0.0)
                        + (requirement.commissioned_quantity or 0.0),
                        0.0,
                    ),
                    quantity,
                )
                order_line = requirement.purchase_order_line_id
                ordered_open = 0.0
                received_from_order = 0.0
                if order_line:
                    ordered_quantity += order_line.quantity_ordered or 0.0
                    received_from_order = min(
                        max(order_line.quantity_received or 0.0, 0.0),
                        quantity,
                    )
                    received_quantity += received_from_order
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
                secured_quantity = min(
                    available_quantity + ordered_open,
                    quantity,
                )
                available_ratio = available_quantity / quantity
                procured_ratio = secured_quantity / quantity
                available_ratios.append(available_ratio)
                procured_ratios.append(procured_ratio)

                line_value = quantity * unit_price
                required_quantity += quantity
                available_quantity_total += available_quantity
                required_value += line_value
                available_value += line_value * available_ratio
                procured_value += line_value * procured_ratio
                received_value += received_from_order * unit_price

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

            project.sab_purchase_order_ids = orders
            project.sab_switchboard_count = len(
                packages.mapped("source_cabinet_bom_ids")
            )
            project.sab_purchase_order_count = len(orders)
            project.sab_material_requirement_count = len(requirements)
            project.sab_material_required_quantity = required_quantity
            project.sab_material_reserved_quantity = available_quantity_total
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
            elif any(
                package.purchase_release_state == "released"
                for package in packages
            ):
                state = "released"
            else:
                state = "not_started"
            project.sab_procurement_state = state

    def action_view_sab_material_requirements(self):
        self.ensure_one()
        requirements = self._sab_current_procurement_requirements()
        if not requirements:
            return super().action_view_sab_material_requirements()
        return {
            "type": "ir.actions.act_window",
            "name": _("Materialanforderungen – %s") % self.display_name,
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [("id", "in", requirements.ids)],
            "context": {
                "search_default_open": 0,
                "search_default_group_project": 0,
            },
            "target": "current",
        }


class SabStockMovementProcurementSource(models.Model):
    _inherit = "sab.stock.movement"

    source_cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler / Schaltschrank",
        ondelete="set null",
        index=True,
    )


class SabPurchaseOrderLineProcurementSource(models.Model):
    _inherit = "sab.purchase.order.line"

    procurement_bom_id = fields.Many2one(
        related="requirement_id.bom_id",
        string="Beschaffungspaket",
        store=True,
        readonly=True,
    )
    source_cabinet_bom_id = fields.Many2one(
        related="requirement_id.source_cabinet_bom_id",
        string="Verteiler / Schaltschrank",
        store=True,
        readonly=True,
    )

    def _post_receipt(self):
        Movement = self.env["sab.stock.movement"]
        touched_packages = self.env["sab.project.bom"]
        for line in self:
            quantity = line.quantity_to_receive or 0.0
            if quantity <= 0:
                continue
            if quantity > line.quantity_remaining + 1e-9:
                raise ValidationError(
                    f"Bei {line.supplier_article_number or line.requirement_id.name} "
                    "wurden mehr Teile als noch offen eingegeben."
                )
            product_values = line.requirement_id._movement_product_values()
            common = {
                **product_values,
                "quantity": quantity,
                "unit": line.unit,
                "project_id": line.project_id.id,
                "purchase_requirement_id": line.requirement_id.id,
                "purchase_order_line_id": line.id,
                "source_cabinet_bom_id": line.source_cabinet_bom_id.id
                or False,
            }
            Movement.create(
                {
                    **common,
                    "movement_type": "receipt",
                    "unit_cost": line.unit_purchase_price,
                    "note": f"Wareneingang {line.order_id.name}",
                }
            )
            Movement.create(
                {
                    **common,
                    "movement_type": "reserve",
                    "note": (
                        f"Kommissionierung "
                        f"{line.source_cabinet_bom_id.name or line.project_id.display_name} "
                        f"aus {line.order_id.name}"
                    ),
                }
            )
            line.write(
                {
                    "quantity_received": line.quantity_received + quantity,
                    "quantity_to_receive": 0.0,
                }
            )
            if line.quantity_remaining <= 0:
                line.requirement_id.state = "received"
            if line.procurement_bom_id.bom_scope == "procurement":
                touched_packages |= line.procurement_bom_id

        for package in touched_packages:
            if package.picking_user_id:
                package.write({"picking_state": "partial"})
                activity_type = self.env.ref(
                    "mail.mail_activity_data_todo",
                    raise_if_not_found=False,
                )
                if activity_type:
                    model_id = self.env["ir.model"]._get_id(
                        "sab.project.bom"
                    )
                    existing = self.env["mail.activity"].search_count(
                        [
                            ("res_model_id", "=", model_id),
                            ("res_id", "=", package.id),
                            ("user_id", "=", package.picking_user_id.id),
                            ("summary", "=", "Nachlieferung kommissionieren"),
                        ]
                    )
                    if not existing:
                        self.env["mail.activity"].create(
                            {
                                "activity_type_id": activity_type.id,
                                "res_model_id": model_id,
                                "res_id": package.id,
                                "user_id": package.picking_user_id.id,
                                "summary": "Nachlieferung kommissionieren",
                                "note": (
                                    f"Für {package.procurement_reference or package.name} "
                                    "ist weitere Ware eingegangen und projektbezogen reserviert."
                                ),
                            }
                        )
        return True


class SabPurchaseOrderProcurementExtra(models.Model):
    _inherit = "sab.purchase.order"

    def action_open_extra_line_wizard(self):
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(
                "Zusatzpositionen können nur einem Bestellentwurf hinzugefügt werden."
            )
        packages = self.line_ids.mapped("procurement_bom_id").filtered(
            lambda package: package.bom_scope == "procurement"
        )
        if len(packages) != 1:
            raise ValidationError(
                "Der Bestellentwurf muss eindeutig zu einem Beschaffungspaket gehören."
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Zusatzposition zum Bestellentwurf"),
            "res_model": "sab.procurement.extra.line.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_procurement_bom_id": packages.id,
                "default_purchase_order_id": self.id,
                "default_supplier_id": self.supplier_id.id,
            },
        }


class SaleOrderProcurementPackageAction(models.Model):
    _inherit = "sale.order"

    def action_open_procurement_package_wizard(self):
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise ValidationError(
                "Schaltschränke können erst nach 'Auftrag erhalten' an den Einkauf übergeben werden."
            )
        if self.sab_calculation_source != "schematic":
            raise ValidationError(
                "Beschaffungspakete werden ausschließlich aus Schaltplan-Aufträgen mit einzelnen Schaltschränken erzeugt."
            )
        cabinets = self.sab_bom_ids.filtered(
            lambda bom: bom.bom_scope == "cabinet"
            and bom.state == "released"
        )
        if not cabinets:
            raise ValidationError(
                "Es ist noch keine technisch freigegebene Schaltschrank-Stückliste vorhanden."
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Schaltschränke an Einkauf übergeben"),
            "res_model": "sab.procurement.package.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_cabinet_bom_ids": cabinets.ids,
            },
        }
