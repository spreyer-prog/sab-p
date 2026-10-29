from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sab_project_id = fields.Many2one(
        comodel_name="project.project",
        string="SAB-P Projekt",
        copy=True,
        index=True,
        ondelete="restrict",
        help="Projekt, zu dem dieses Angebot gehört.",
    )
    sab_offer_reference = fields.Char(
        string="SAB-P Angebotsnummer",
        readonly=True,
        copy=False,
        index=True,
        help="Automatisch vergebene, unveränderliche Angebotsnummer.",
    )
    sab_offer_release_state = fields.Selection(
        [
            ("draft", "In Bearbeitung"),
            ("released", "Zum Verschicken freigegeben"),
        ],
        string="Angebotsfreigabe",
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    sab_offer_released_at = fields.Datetime(
        string="Angebot freigegeben am",
        readonly=True,
        copy=False,
    )
    sab_offer_released_by_id = fields.Many2one(
        "res.users",
        string="Angebot freigegeben durch",
        readonly=True,
        copy=False,
    )

    sab_calculation_line_ids = fields.One2many(
        comodel_name="sab.offer.calculation.line",
        inverse_name="order_id",
        string="SAB-P Kalkulation",
        copy=True,
    )
    sab_material_purchase_total = fields.Monetary(
        string="Material-EK",
        currency_field="currency_id",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_mechanical_hours = fields.Float(
        string="Mechanikstunden",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_wiring_hours = fields.Float(
        string="Verdrahtungsstunden",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_testing_hours = fields.Float(
        string="Prüfstunden",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_calculated_hours = fields.Float(
        string="Kalkulierte Zeit",
        compute="_compute_sab_calculation_totals",
        store=True,
        help="Automatische Summe der SAB-P Angebotskalkulation.",
    )
    sab_space_units = fields.Float(
        string="Platzeinheiten",
        compute="_compute_sab_calculation_totals",
        store=True,
    )

    sab_material_factor = fields.Float(
        string="Materialfaktor",
        default=lambda self: self._sab_float_param("sab_project.material_factor", 1.0),
        copy=True,
    )
    sab_aux_material_factor = fields.Float(
        string="Hilfsmaterialfaktor",
        default=lambda self: self._sab_float_param("sab_project.aux_material_factor", 1.15),
        copy=True,
    )
    sab_hourly_rate = fields.Float(
        string="Kalkulatorischer Stundenlohn",
        default=lambda self: self._sab_float_param("sab_project.hourly_rate", 80.0),
        copy=True,
    )
    sab_time_factor = fields.Float(
        string="Zeitfaktor",
        default=lambda self: self._sab_float_param("sab_project.time_factor", 1.25),
        copy=True,
    )
    sab_difficulty_factor = fields.Float(
        string="Schwierigkeitsfaktor",
        default=lambda self: self._sab_float_param("sab_project.difficulty_factor", 1.0),
        copy=True,
    )
    sab_planning_surcharge_factor = fields.Float(
        string="Planungszuschlag",
        default=lambda self: self._sab_float_param(
            "sab_project.planning_surcharge_factor", 1.15
        ),
        copy=True,
    )
    sab_packaging_factor = fields.Float(
        string="Verpackung / Transport",
        default=lambda self: self._sab_float_param("sab_project.packaging_factor", 1.03),
        copy=True,
    )
    sab_skonto_factor = fields.Float(
        string="Skonto",
        default=lambda self: self._sab_float_param("sab_project.skonto_factor", 1.03),
        copy=True,
    )
    sab_margin_factor = fields.Float(
        string="Marge",
        default=lambda self: self._sab_float_param("sab_project.margin_factor", 1.25),
        copy=True,
    )
    sab_rebate_factor = fields.Float(
        string="Rabatt",
        default=lambda self: self._sab_float_param("sab_project.rebate_factor", 1.125),
        copy=True,
    )

    sab_material_cost = fields.Monetary(
        string="Material kalkulatorisch",
        currency_field="currency_id",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_labor_cost = fields.Monetary(
        string="Lohn kalkulatorisch",
        currency_field="currency_id",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_direct_cost = fields.Monetary(
        string="Kalkulatorische Basiskosten",
        currency_field="currency_id",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_commercial_factor = fields.Float(
        string="Kaufmännischer Gesamtfaktor",
        compute="_compute_sab_calculation_totals",
        store=True,
    )
    sab_recommended_net_price = fields.Monetary(
        string="Kalkulatorischer Netto-Richtwert",
        currency_field="currency_id",
        compute="_compute_sab_calculation_totals",
        store=True,
        help=(
            "Transparenter Richtwert aus Material, Zeit und den im Angebot "
            "gespeicherten Faktoren. Er überschreibt den Odoo-Angebotspreis nicht automatisch."
        ),
    )

    sab_revision_of_id = fields.Many2one(
        comodel_name="sale.order",
        string="Revision von",
        copy=False,
        readonly=True,
        ondelete="set null",
        index=True,
    )
    sab_revision_ids = fields.One2many(
        comodel_name="sale.order",
        inverse_name="sab_revision_of_id",
        string="Angebotsrevisionen",
    )
    sab_revision_reason = fields.Char(string="Revisionsgrund", copy=False)
    sab_revision_count = fields.Integer(
        string="Anzahl Revisionen",
        compute="_compute_sab_revision_count",
    )

    sab_bom_ids = fields.One2many(
        comodel_name="sab.project.bom",
        inverse_name="order_id",
        string="SAB-P Stücklisten",
        copy=False,
    )
    sab_bom_count = fields.Integer(
        string="Stücklisten",
        compute="_compute_sab_bom_count",
    )

    _sab_offer_reference_unique = models.Constraint(
        "UNIQUE(sab_offer_reference)",
        "Die Angebotsnummer ist bereits vergeben.",
    )

    @api.model
    def _sab_float_param(self, key, default):
        raw = self.env["ir.config_parameter"].sudo().get_param(key, str(default))
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    @api.depends(
        "sab_calculation_line_ids.material_purchase_total",
        "sab_calculation_line_ids.mechanical_time_minutes",
        "sab_calculation_line_ids.wiring_time_minutes",
        "sab_calculation_line_ids.testing_time_minutes",
        "sab_calculation_line_ids.total_time_minutes",
        "sab_calculation_line_ids.space_units",
        "sab_material_factor",
        "sab_aux_material_factor",
        "sab_hourly_rate",
        "sab_time_factor",
        "sab_difficulty_factor",
        "sab_packaging_factor",
        "sab_skonto_factor",
        "sab_margin_factor",
        "sab_rebate_factor",
    )
    def _compute_sab_calculation_totals(self):
        for order in self:
            lines = order.sab_calculation_line_ids
            material_purchase_total = sum(lines.mapped("material_purchase_total"))
            total_minutes = sum(lines.mapped("total_time_minutes"))
            order.sab_material_purchase_total = material_purchase_total
            order.sab_mechanical_hours = (
                sum(lines.mapped("mechanical_time_minutes")) / 60.0
            )
            order.sab_wiring_hours = sum(lines.mapped("wiring_time_minutes")) / 60.0
            order.sab_testing_hours = sum(lines.mapped("testing_time_minutes")) / 60.0
            order.sab_calculated_hours = total_minutes / 60.0
            order.sab_space_units = sum(lines.mapped("space_units"))
            order.sab_material_cost = (
                material_purchase_total
                * (order.sab_material_factor or 0.0)
                * (order.sab_aux_material_factor or 0.0)
            )
            order.sab_labor_cost = (
                order.sab_calculated_hours
                * (order.sab_hourly_rate or 0.0)
                * (order.sab_time_factor or 0.0)
                * (order.sab_difficulty_factor or 0.0)
            )
            order.sab_direct_cost = order.sab_material_cost + order.sab_labor_cost
            order.sab_commercial_factor = (
                (order.sab_packaging_factor or 0.0)
                * (order.sab_skonto_factor or 0.0)
                * (order.sab_margin_factor or 0.0)
                * (order.sab_rebate_factor or 0.0)
            )
            order.sab_recommended_net_price = (
                order.sab_direct_cost * order.sab_commercial_factor
            )

    @api.depends("sab_revision_ids")
    def _compute_sab_revision_count(self):
        for order in self:
            order.sab_revision_count = len(order.sab_revision_ids)

    @api.depends("sab_bom_ids")
    def _compute_sab_bom_count(self):
        for order in self:
            order.sab_bom_count = len(order.sab_bom_ids)

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            project_id = vals.get("sab_project_id")
            if project_id:
                project = self.env["project.project"].browse(project_id).exists()
                if not project:
                    raise ValidationError(_("Das ausgewählte Projekt existiert nicht."))
                offer_reference = project._sab_allocate_offer_reference()
                vals["sab_offer_reference"] = offer_reference
                vals["name"] = offer_reference
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)

    @api.model
    def _sab_released_offer_protected_fields(self):
        return {
            "partner_id",
            "partner_invoice_id",
            "partner_shipping_id",
            "sab_project_id",
            "sab_calculation_source",
            "validity_date",
            "payment_term_id",
            "sab_material_factor",
            "sab_aux_material_factor",
            "sab_hourly_rate",
            "sab_time_factor",
            "sab_difficulty_factor",
            "sab_planning_surcharge_factor",
            "sab_packaging_factor",
            "sab_skonto_factor",
            "sab_margin_factor",
            "sab_rebate_factor",
            "sab_object_discount_percent",
            "sab_vat_rate",
            "sab_transport_cost",
            "sab_delivery_time_text",
            "sab_payment_text",
            "sab_service_description",
            "sab_documentation_text",
            "sab_transport_text",
            "sab_reservations_text",
            "sab_additional_terms_text",
        }

    def write(self, vals):
        if not self.env.context.get("sab_offer_release_write"):
            protected = self._sab_released_offer_protected_fields()
            if protected.intersection(vals) and any(
                order.sab_offer_release_state == "released" for order in self
            ):
                raise ValidationError(
                    _(
                        "Ein zum Verschicken freigegebenes Angebot ist festgeschrieben. "
                        "Bitte für Änderungen eine neue Revision anlegen."
                    )
                )
        if "sab_project_id" in vals:
            for order in self:
                new_project_id = vals.get("sab_project_id")
                if (
                    order.sab_project_id
                    and new_project_id
                    and new_project_id != order.sab_project_id.id
                ):
                    raise ValidationError(
                        _(
                            "Das Projekt eines bereits nummerierten Angebots darf nicht geändert werden."
                        )
                    )
        if "sab_offer_reference" in vals:
            for order in self:
                if (
                    order.sab_offer_reference
                    and vals.get("sab_offer_reference") != order.sab_offer_reference
                ):
                    raise ValidationError(
                        _("Eine vergebene Angebotsnummer darf nicht geändert werden.")
                    )
        if "name" in vals:
            for order in self:
                if order.sab_offer_reference and vals.get("name") != order.name:
                    raise ValidationError(
                        _("Eine vergebene Angebotsnummer darf nicht geändert werden.")
                    )
        return super().write(vals)

    def copy_data(self, default=None):
        result = super().copy_data(default)
        for values in result:
            values.pop("sab_offer_reference", None)
            values.pop("sab_bom_ids", None)
            values.pop("sab_offer_release_state", None)
            values.pop("sab_offer_released_at", None)
            values.pop("sab_offer_released_by_id", None)
            if values.get("sab_project_id"):
                values["name"] = "/"
        return result

    def action_create_sab_revision(self):
        self.ensure_one()
        if not self.sab_project_id:
            raise ValidationError(
                _("Eine Revision kann nur für ein SAB-P Projektangebot erstellt werden.")
            )
        revision = self.copy(
            {
                "sab_revision_of_id": self.id,
                "sab_revision_reason": False,
                "sab_offer_release_state": "draft",
                "sab_offer_released_at": False,
                "sab_offer_released_by_id": False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Angebotsrevision"),
            "res_model": "sale.order",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }

    def _sab_check_offer_released(self):
        for order in self:
            if order.sab_project_id and order.sab_offer_release_state != "released":
                raise ValidationError(
                    _(
                        "Das Angebot ist noch nicht zum Verschicken freigegeben. "
                        "Bitte zuerst 'Angebot zum Verschicken freigeben' ausführen."
                    )
                )
        return True

    def _sab_check_offer_output_release(self):
        self.ensure_one()
        self._sab_check_offer_released()
        return True

    def action_sab_release_offer(self):
        for order in self:
            if order.sab_offer_release_state == "released":
                continue
            if order.state not in ("draft", "sent"):
                raise ValidationError(
                    _("Nur ein Angebot oder gesendetes Angebot kann freigegeben werden.")
                )
            if not order.sab_project_id:
                raise ValidationError(_("Das Angebot benötigt ein SAB-P Projekt."))
            if not order.sab_calculation_line_ids:
                raise ValidationError(
                    _("Ein leeres Angebot kann nicht zum Verschicken freigegeben werden.")
                )

            order.sab_calculation_line_ids._normalize_section_membership()
            if order.sab_calculation_source == "lv":
                order._sab_validate_and_lock_lv()
            elif order.sab_calculation_source == "schematic":
                order._sab_validate_schematic_lv_basis()
                order._sab_validate_switchboard_structure()

            order.sab_calculation_line_ids._sync_customer_order_lines()
            order.with_context(sab_offer_release_write=True).write(
                {
                    "sab_offer_release_state": "released",
                    "sab_offer_released_at": fields.Datetime.now(),
                    "sab_offer_released_by_id": self.env.user.id,
                }
            )
            order.message_post(
                body=_(
                    "Angebot %s wurde zum Verschicken freigegeben und festgeschrieben."
                )
                % (order.sab_offer_reference or order.name)
            )
        return True

    def action_generate_sab_bom(self):
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise ValidationError(
                _("Die SAB-P Stückliste kann erst aus einem bestätigten Auftrag erzeugt werden.")
            )
        if not self.sab_project_id:
            raise ValidationError(_("Dem Auftrag ist kein SAB-P Projekt zugeordnet."))
        if not self.sab_calculation_line_ids:
            raise ValidationError(
                _("Der Auftrag enthält keine SAB-P Kalkulationspositionen.")
            )
        bom = self.sab_bom_ids[:1]
        if bom and bom.state == "released":
            return {
                "type": "ir.actions.act_window",
                "res_model": "sab.project.bom",
                "res_id": bom.id,
                "view_mode": "form",
                "target": "current",
            }
        aggregated = {}
        for calc_line in self.sab_calculation_line_ids:
            for component in calc_line.component_snapshot_ids:
                qty = component.quantity_per_unit or 0.0
                if not component.fixed_quantity:
                    qty *= calc_line.quantity or 0.0
                key = (
                    component.product_id.id,
                    component.unit,
                    component.optional,
                    component.supplier_product_id.id or False,
                    component.unit_purchase_price or 0.0,
                )
                if key not in aggregated:
                    aggregated[key] = {
                        "product_id": component.product_id.id,
                        "quantity": 0.0,
                        "unit": component.unit,
                        "optional": component.optional,
                        "supplier_product_id": component.supplier_product_id.id
                        or False,
                        "unit_purchase_price": component.unit_purchase_price or 0.0,
                        "note": component.note,
                    }
                aggregated[key]["quantity"] += qty
        if not aggregated:
            raise ValidationError(
                _(
                    "Aus den Kalkulations-Snapshots konnten keine Stücklistenpositionen erzeugt werden."
                )
            )
        line_commands = []
        for sequence, values in enumerate(aggregated.values(), start=1):
            values = dict(values)
            values["sequence"] = sequence * 10
            line_commands.append((0, 0, values))
        if bom:
            bom.write(
                {
                    "generated_at": fields.Datetime.now(),
                    "generated_by_id": self.env.user.id,
                    "line_ids": [(5, 0, 0)] + line_commands,
                }
            )
        else:
            bom = self.env["sab.project.bom"].create(
                {
                    "name": f"STL {self.sab_offer_reference or self.name}",
                    "order_id": self.id,
                    "project_id": self.sab_project_id.id,
                    "line_ids": line_commands,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("SAB-P Stückliste"),
            "res_model": "sab.project.bom",
            "res_id": bom.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_confirm(self):
        self._sab_check_offer_released()
        result = super().action_confirm()
        projects = self.mapped("sab_project_id")
        if projects:
            projects.write({"sab_status": "won"})
        return result

    def action_cancel(self):
        result = super().action_cancel()
        for project in self.mapped("sab_project_id"):
            active_orders = project.sab_sale_order_ids.filtered(
                lambda order: order.state != "cancel"
            )
            if not active_orders and project.sab_status != "lost":
                project.sab_status = "offer_open"
        return result
