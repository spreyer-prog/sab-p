from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabProjectBomProcurementWorkspace(models.Model):
    _inherit = "sab.project.bom"

    def _sab_notify_purchasing_about_released_bom(self):
        purchasing_group = self.env.ref(
            "sab_project.group_sab_purchasing",
            raise_if_not_found=False,
        )
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if not purchasing_group or not activity_type:
            return True

        model_id = self.env["ir.model"]._get_id(self._name)
        for bom in self:
            for user in purchasing_group.user_ids.filtered("active"):
                existing = self.env["mail.activity"].search_count(
                    [
                        ("res_model_id", "=", model_id),
                        ("res_id", "=", bom.id),
                        ("user_id", "=", user.id),
                        ("summary", "=", "Neue freigegebene Stückliste prüfen"),
                    ]
                )
                if not existing:
                    self.env["mail.activity"].create(
                        {
                            "activity_type_id": activity_type.id,
                            "res_model_id": model_id,
                            "res_id": bom.id,
                            "user_id": user.id,
                            "summary": "Neue freigegebene Stückliste prüfen",
                            "note": (
                                f"Projekt {bom.project_id.display_name}: Die technische "
                                "Gesamtstückliste wurde freigegeben. Lagerbestand, "
                                "Reservierung und Fehlbestand können jetzt im "
                                "Einkaufs-Dashboard bearbeitet werden."
                            ),
                        }
                    )
        return True

    def _sab_push_to_procurement_workspace(self):
        total_boms = self.filtered(
            lambda bom: bom.state == "released"
            and getattr(bom, "bom_scope", "total") == "total"
        )
        for bom in total_boms:
            bom.with_context(
                sab_procurement_release=True
            ).action_generate_purchase_requirements()
            requirements = bom.purchase_requirement_ids.filtered(
                lambda requirement: not requirement.optional
                and requirement.state == "open"
            )
            requirements._reserve_available_stock()
            requirements._sab_prepare_order_quantities()
        total_boms._sab_notify_purchasing_about_released_bom()
        return True

    def action_release(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("project.group_project_manager")
        ):
            raise AccessError(
                "Die technische Stücklistenfreigabe ist der Projektleitung vorbehalten."
            )
        result = super().action_release()
        self._sab_push_to_procurement_workspace()
        return result

    def action_open_procurement_workspace(self):
        self.ensure_one()
        if self.state != "released":
            raise ValidationError(
                "Der Einkaufsbereich steht erst nach technischer Freigabe der Stückliste zur Verfügung."
            )
        if getattr(self, "bom_scope", "total") != "total":
            raise ValidationError(
                "Der projektweite Einkaufsbereich wird aus der Gesamtstückliste erzeugt."
            )
        self._sab_push_to_procurement_workspace()
        return {
            "type": "ir.actions.act_window",
            "name": _("Einkaufsbearbeitung – %s") % self.project_id.display_name,
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [
                ("bom_id", "=", self.id),
                ("state", "!=", "cancel"),
            ],
            "context": {
                "search_default_group_project": 0,
                "search_default_open": 1,
            },
            "target": "current",
        }


class SabPurchaseRequirementWorkspace(models.Model):
    _inherit = "sab.purchase.requirement"

    company_currency_id = fields.Many2one(
        related="project_id.company_id.currency_id",
        string="Unternehmenswährung",
        readonly=True,
    )
    warehouse_unit_value = fields.Monetary(
        string="Durchschnittlicher Lager-EK",
        currency_field="company_currency_id",
        compute="_compute_warehouse_stock_value",
    )
    warehouse_stock_value = fields.Monetary(
        string="Aktueller Lagerwert",
        currency_field="company_currency_id",
        compute="_compute_warehouse_stock_value",
    )
    quantity_to_order = fields.Float(
        string="Jetzt zu bestellen",
        digits=(16, 3),
        default=0.0,
        copy=False,
        help=(
            "Wird aus Fehlbestand, Mindestbestellmenge und Verpackungseinheit "
            "vorgeschlagen und kann vor der Bestellerzeugung angepasst werden. "
            "Mit 0 wird die Position aus der aktuellen Bestellung ausgeschlossen."
        ),
    )
    quantity_to_order_manual = fields.Boolean(
        string="Bestellmenge manuell festgelegt",
        default=False,
        copy=False,
    )

    def _compute_warehouse_stock_value(self):
        Movement = self.env["sab.stock.movement"].sudo()
        for requirement in self:
            legacy, product = requirement._stock_identity()
            if product:
                movements = Movement.search(
                    [("odoo_product_id", "=", product.id)]
                )
            elif legacy:
                movements = Movement.search([("product_id", "=", legacy.id)])
            else:
                movements = Movement

            receipts = movements.filtered(
                lambda movement: movement.movement_type == "receipt"
            )
            issues = movements.filtered(
                lambda movement: movement.movement_type == "issue"
            )
            on_hand = sum(receipts.mapped("quantity")) - sum(
                issues.mapped("quantity")
            )
            stock_value = sum(receipts.mapped("total_value")) - sum(
                issues.mapped("total_value")
            )
            requirement.warehouse_stock_value = max(stock_value, 0.0)
            requirement.warehouse_unit_value = (
                max(stock_value / on_hand, 0.0) if on_hand > 0 else 0.0
            )

    def _sab_prepare_order_quantities(self, force=False):
        for requirement in self.filtered(
            lambda record: record.state == "open"
            and not record.optional
            and not record.purchase_order_line_id
        ):
            requirement.invalidate_recordset(
                [
                    "suggested_order_quantity",
                    "shortage_quantity",
                    "project_reserved_quantity",
                ]
            )
            if force or not requirement.quantity_to_order_manual:
                requirement.with_context(
                    sab_prepare_order_quantity=True
                ).write(
                    {
                        "quantity_to_order": requirement.suggested_order_quantity
                        or 0.0,
                        "quantity_to_order_manual": False,
                    }
                )
        return True

    def _reserve_available_stock(self):
        result = super()._reserve_available_stock()
        self._sab_prepare_order_quantities()
        return result

    def write(self, vals):
        values = dict(vals)
        if (
            "quantity_to_order" in values
            and not self.env.context.get("sab_prepare_order_quantity")
        ):
            values["quantity_to_order_manual"] = True
        return super().write(values)

    def action_reset_order_quantity_to_suggestion(self):
        self.with_context(sab_prepare_order_quantity=True).write(
            {
                "quantity_to_order_manual": False,
            }
        )
        self._sab_prepare_order_quantities(force=True)
        return True

    def action_create_purchase_orders(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Bestellvorschläge dürfen nur durch einen im Mitarbeiterprofil "
                "freigeschalteten Einkaufsmitarbeiter erzeugt werden."
            )

        requirements = self.exists().filtered(
            lambda requirement: requirement.state == "open"
            and not requirement.optional
            and requirement.shortage_quantity > 0
            and not requirement.purchase_order_line_id
            and requirement.quantity_to_order > 0
        )
        if not requirements:
            raise ValidationError(
                "In der Auswahl befindet sich keine offene Position mit einer "
                "Bestellmenge größer 0."
            )

        not_released = requirements.filtered(
            lambda requirement: requirement.bom_id.purchase_release_state
            != "released"
        )
        if not_released:
            raise ValidationError(
                "Die Gesamtstückliste muss vor der Bestellerzeugung durch einen "
                "hinterlegten Bestellfreigeber zur Beschaffung freigegeben werden."
            )

        without_supplier = requirements.filtered(
            lambda requirement: not requirement.supplier_product_id.supplier_id
        )
        if without_supplier:
            names = ", ".join(
                without_supplier.mapped("odoo_product_id.display_name")
                or without_supplier.mapped("product_id.name")
                or without_supplier.mapped("name")
            )
            raise ValidationError(
                f"Für folgende Positionen fehlt ein Lieferantenartikel: {names}."
            )

        grouped = defaultdict(lambda: self.env["sab.purchase.requirement"])
        for requirement in requirements:
            grouped[requirement.supplier_id.id] |= requirement

        created_orders = self.env["sab.purchase.order"]
        for supplier_id, supplier_requirements in grouped.items():
            order = self.env["sab.purchase.order"].create(
                {
                    "supplier_id": supplier_id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "requirement_id": requirement.id,
                                "quantity_ordered": requirement.quantity_to_order,
                                "unit_purchase_price": requirement.unit_purchase_price,
                            },
                        )
                        for requirement in supplier_requirements.sorted(
                            key=lambda record: (
                                record.project_id.sab_project_reference or "",
                                record.sequence,
                                record.id,
                            )
                        )
                    ],
                }
            )
            created_orders |= order

        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellvorschläge"),
            "res_model": "sab.purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created_orders.ids)],
            "target": "current",
        }
