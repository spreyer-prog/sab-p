from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabTimeEntry(models.Model):
    _name = "sab.time.entry"
    _description = "SAB-P Zeitbuchung"
    _order = "work_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Tätigkeit", required=True, tracking=True)
    project_id = fields.Many2one(comodel_name="project.project", string="Projekt", required=True, ondelete="cascade", index=True, tracking=True)
    production_step_id = fields.Many2one(
        comodel_name="sab.production.step",
        string="Fertigungsschritt",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    production_order_id = fields.Many2one(
        related="production_step_id.production_order_id",
        string="Fertigungsauftrag",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(comodel_name="res.users", string="Mitarbeiter", required=True, default=lambda self: self.env.user, index=True, tracking=True)
    work_date = fields.Date(string="Datum", required=True, default=fields.Date.context_today, index=True)
    activity_type = fields.Selection(
        selection=[
            ("engineering", "Planung / Technik"),
            ("mechanical", "Mechanische Fertigung"),
            ("wiring", "Verdrahtung"),
            ("testing", "Prüfung"),
            ("service", "Service / Montage"),
            ("travel", "Fahrtzeit"),
            ("documentation", "Dokumentation"),
            ("other", "Sonstiges"),
        ],
        string="Tätigkeitsart", required=True, default="service", index=True,
    )
    hours = fields.Float(string="Stunden", required=True, digits=(16, 2), tracking=True)
    hourly_cost = fields.Float(string="Kostensatz / h", required=True, digits=(16, 2), default=lambda self: self._default_hourly_cost(), tracking=True)
    cost_total = fields.Float(string="Kosten gesamt", compute="_compute_cost_total", store=True, digits=(16, 2))
    state = fields.Selection(selection=[("draft", "Entwurf"), ("confirmed", "Gebucht")], string="Status", required=True, default="draft", tracking=True, index=True)
    note = fields.Text(string="Bemerkung")

    @api.model
    def _default_hourly_cost(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("sab_project.hourly_rate", "80.0")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 80.0

    @api.onchange("production_step_id")
    def _onchange_production_step_id(self):
        if self.production_step_id:
            self.project_id = self.production_step_id.project_id
            self.name = self.production_step_id.name

    @api.depends("hours", "hourly_cost")
    def _compute_cost_total(self):
        for record in self:
            record.cost_total = (record.hours or 0.0) * (record.hourly_cost or 0.0)

    @api.constrains("hours", "hourly_cost")
    def _check_values(self):
        for record in self:
            if record.hours <= 0:
                raise ValidationError(_("Eine Zeitbuchung benötigt eine Dauer größer 0 Stunden."))
            if record.hourly_cost < 0:
                raise ValidationError(_("Der Kostensatz darf nicht negativ sein."))

    @api.constrains("production_step_id", "project_id", "user_id")
    def _check_production_step_context(self):
        for record in self.filtered("production_step_id"):
            step = record.production_step_id
            if record.project_id != step.project_id:
                raise ValidationError(_("Projekt und Fertigungsschritt der Zeitbuchung passen nicht zusammen."))
            if step.responsible_user_id and step.responsible_user_id != record.user_id and not self.env.user.has_group("project.group_project_manager"):
                raise ValidationError(_("Zeit darf auf diesen Fertigungsschritt nur vom zugewiesenen Mitarbeiter gebucht werden."))

    @api.model
    def _sync_project_hours(self, projects):
        for project in projects.exists():
            entries = self.search([("project_id", "=", project.id), ("state", "=", "confirmed")])
            project.sab_required_hours = sum(entries.mapped("hours"))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            step_id = vals.get("production_step_id")
            if step_id:
                step = self.env["sab.production.step"].browse(step_id).exists()
                if step:
                    vals.setdefault("project_id", step.project_id.id)
                    vals.setdefault("name", step.name)
                    vals.setdefault("user_id", self.env.user.id)
            prepared.append(vals)
        records = super().create(prepared)
        self._sync_project_hours(records.mapped("project_id"))
        return records

    def action_confirm(self):
        for record in self:
            if record.state == "draft":
                record.state = "confirmed"
        self._sync_project_hours(self.mapped("project_id"))
        return True

    def write(self, vals):
        projects_before = self.mapped("project_id")
        protected = {"project_id", "production_step_id", "user_id", "work_date", "activity_type", "hours", "hourly_cost"}
        if any(record.state == "confirmed" for record in self) and protected.intersection(vals):
            raise ValidationError(_("Gebuchte Zeiten dürfen nicht nachträglich verändert werden."))
        result = super().write(vals)
        self._sync_project_hours(projects_before | self.mapped("project_id"))
        return result

    def unlink(self):
        if any(record.state == "confirmed" for record in self):
            raise ValidationError(_("Gebuchte Zeiten dürfen nicht gelöscht werden."))
        projects = self.mapped("project_id")
        result = super().unlink()
        self._sync_project_hours(projects)
        return result
