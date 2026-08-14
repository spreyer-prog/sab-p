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

    # ---------------------------------------------------------
    # Angebotskalkulation
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Angebotsrevisionen
    # ---------------------------------------------------------

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
        string="Revisionen",
    )
    sab_revision_reason = fields.Char(
        string="Revisionsgrund",
        copy=False,
    )
    sab_revision_count = fields.Integer(
        string="Revisionen",
        compute="_compute_sab_revision_count",
    )

    _sab_offer_reference_unique = models.Constraint(
        "UNIQUE(sab_offer_reference)",
        "Die Angebotsnummer ist bereits vergeben.",
    )

    @api.depends(
        "sab_calculation_line_ids.material_purchase_total",
        "sab_calculation_line_ids.mechanical_time_minutes",
        "sab_calculation_line_ids.wiring_time_minutes",
        "sab_calculation_line_ids.testing_time_minutes",
        "sab_calculation_line_ids.total_time_minutes",
        "sab_calculation_line_ids.space_units",
    )
    def _compute_sab_calculation_totals(self):
        for order in self:
            lines = order.sab_calculation_line_ids
            order.sab_material_purchase_total = sum(
                lines.mapped("material_purchase_total")
            )
            order.sab_mechanical_hours = sum(
                lines.mapped("mechanical_time_minutes")
            ) / 60.0
            order.sab_wiring_hours = sum(
                lines.mapped("wiring_time_minutes")
            ) / 60.0
            order.sab_testing_hours = sum(
                lines.mapped("testing_time_minutes")
            ) / 60.0
            order.sab_calculated_hours = sum(
                lines.mapped("total_time_minutes")
            ) / 60.0
            order.sab_space_units = sum(lines.mapped("space_units"))

    @api.depends("sab_revision_ids")
    def _compute_sab_revision_count(self):
        for order in self:
            order.sab_revision_count = len(order.sab_revision_ids)

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

    def write(self, vals):
        if "sab_project_id" in vals:
            for order in self:
                new_project_id = vals.get("sab_project_id")
                if (
                    order.sab_project_id
                    and new_project_id
                    and new_project_id != order.sab_project_id.id
                ):
                    raise ValidationError(
                        _("Das Projekt eines bereits nummerierten Angebots darf nicht geändert werden.")
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
            if values.get("sab_project_id"):
                values["name"] = "/"
        return result

    def action_create_sab_revision(self):
        self.ensure_one()
        if not self.sab_project_id:
            raise ValidationError(
                _("Eine Revision kann nur für ein SAB-P Projektangebot erstellt werden.")
            )

        revision = self.copy({
            "sab_revision_of_id": self.id,
            "sab_revision_reason": False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Angebotsrevision"),
            "res_model": "sale.order",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_confirm(self):
        result = super().action_confirm()
        projects = self.mapped("sab_project_id")
        if projects:
            projects.write({"sab_status": "won"})
        return result

    def action_cancel(self):
        result = super().action_cancel()
        for project in self.mapped("sab_project_id"):
            active_orders = project.sab_sale_order_ids.filtered(
                lambda order: order.state not in ("cancel",)
            )
            if not active_orders and project.sab_status == "won":
                project.sab_status = "offer_open"
        return result
