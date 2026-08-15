from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabTimeEntry(models.Model):
    _name = "sab.time.entry"
    _description = "SAB-P Zeitbuchung"
    _order = "work_date desc, id desc"

    name = fields.Char(string="Tätigkeit", required=True)
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projekt",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Mitarbeiter",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    work_date = fields.Date(
        string="Datum",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    activity_type = fields.Selection(
        selection=[
            ("engineering", "Planung / Technik"),
            ("mechanical", "Mechanische Fertigung"),
            ("wiring", "Verdrahtung"),
            ("testing", "Prüfung"),
            ("service", "Service / Montage"),
            ("documentation", "Dokumentation"),
            ("other", "Sonstiges"),
        ],
        string="Tätigkeitsart",
        required=True,
        default="other",
        index=True,
    )
    hours = fields.Float(string="Stunden", required=True, digits=(16, 2))
    hourly_cost = fields.Float(string="Kostensatz / h", required=True, digits=(16, 2), default=0.0)
    cost_total = fields.Float(string="Kosten gesamt", compute="_compute_cost_total", store=True, digits=(16, 2))
    note = fields.Text(string="Bemerkung")

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

    @api.model
    def _sync_project_hours(self, projects):
        for project in projects.exists():
            entries = self.search([("project_id", "=", project.id)])
            project.sab_required_hours = sum(entries.mapped("hours"))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._sync_project_hours(records.mapped("project_id"))
        return records

    def write(self, vals):
        projects_before = self.mapped("project_id")
        result = super().write(vals)
        self._sync_project_hours(projects_before | self.mapped("project_id"))
        return result

    def unlink(self):
        projects = self.mapped("project_id")
        result = super().unlink()
        self._sync_project_hours(projects)
        return result
