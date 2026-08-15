from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DEFAULT_PRODUCTION_STEPS = [
    (10, "Mechanische Fertigung"),
    (20, "Mechanischer Aufbau"),
    (30, "Bestückung Geräte"),
    (40, "Bestückung Klemmen"),
    (50, "Vorbereitung Verdrahtung"),
    (60, "Elektrische Fertigung"),
    (70, "Prüfung"),
    (80, "Endkontrolle"),
]


class SabProductionOrder(models.Model):
    _name = "sab.production.order"
    _description = "SAB-P Fertigungsauftrag"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Fertigungsauftrag", required=True, readonly=True, copy=False, tracking=True)
    bom_id = fields.Many2one(comodel_name="sab.project.bom", string="Stückliste", required=True, ondelete="restrict", index=True, tracking=True)
    order_id = fields.Many2one(related="bom_id.order_id", string="Kundenauftrag", store=True, readonly=True)
    project_id = fields.Many2one(related="bom_id.project_id", string="Projekt", store=True, readonly=True)
    state = fields.Selection(selection=[("planned", "Geplant"), ("in_progress", "In Fertigung"), ("done", "Fertig"), ("cancel", "Storniert")], string="Status", required=True, default="planned", tracking=True, index=True)
    responsible_user_id = fields.Many2one(comodel_name="res.users", string="Verantwortlich", default=lambda self: self.env.user, tracking=True)
    planned_start = fields.Datetime(string="Geplanter Start", tracking=True)
    started_at = fields.Datetime(string="Tatsächlicher Start", readonly=True, tracking=True)
    finished_at = fields.Datetime(string="Fertiggestellt am", readonly=True, tracking=True)
    delivery_date = fields.Date(related="project_id.sab_delivery_date", string="Liefertermin", readonly=True)
    step_ids = fields.One2many(comodel_name="sab.production.step", inverse_name="production_order_id", string="Fertigungsschritte", copy=True)
    progress_percent = fields.Float(string="Fortschritt (%)", compute="_compute_progress", store=True)
    note = fields.Html(string="Fertigungshinweise")

    _bom_unique = models.Constraint("UNIQUE(bom_id)", "Für diese Stückliste existiert bereits ein Fertigungsauftrag.")

    @api.depends("step_ids.state", "state")
    def _compute_progress(self):
        for record in self:
            if record.state == "done":
                record.progress_percent = 100.0
                continue
            steps = record.step_ids.filtered(lambda step: step.state != "skipped")
            if not steps:
                record.progress_percent = 0.0
                continue
            record.progress_percent = len(steps.filtered(lambda step: step.state == "done")) * 100.0 / len(steps)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            bom_id = vals.get("bom_id")
            if bom_id:
                bom = self.env["sab.project.bom"].browse(bom_id).exists()
                if not bom:
                    raise ValidationError(_("Die ausgewählte Stückliste existiert nicht."))
                if bom.state != "released":
                    raise ValidationError(_("Ein Fertigungsauftrag darf nur aus einer freigegebenen Stückliste erstellt werden."))
            if not vals.get("step_ids"):
                vals["step_ids"] = [(0, 0, {"sequence": sequence, "name": name}) for sequence, name in DEFAULT_PRODUCTION_STEPS]
            prepared.append(vals)
        return super().create(prepared)

    def action_start(self):
        for record in self:
            if record.state != "planned":
                continue
            if record.bom_id.state != "released":
                raise ValidationError(_("Die Fertigung kann nur mit einer freigegebenen Stückliste gestartet werden."))
            record.write({"state": "in_progress", "started_at": record.started_at or fields.Datetime.now()})
        return True

    def action_mark_done(self):
        for record in self:
            if record.state == "done":
                continue
            if record.state == "cancel":
                raise ValidationError(_("Ein stornierter Fertigungsauftrag kann nicht abgeschlossen werden."))
            if record.step_ids.filtered(lambda step: step.state not in ("done", "skipped")):
                raise ValidationError(_("Der Fertigungsauftrag kann erst abgeschlossen werden, wenn alle Fertigungsschritte erledigt oder übersprungen sind."))
            record.write({"state": "done", "started_at": record.started_at or fields.Datetime.now(), "finished_at": fields.Datetime.now()})
        return True

    def write(self, vals):
        if any(record.state == "done" for record in self):
            allowed = {"responsible_user_id", "note"}
            if set(vals) - allowed:
                raise ValidationError(_("Ein abgeschlossener Fertigungsauftrag ist gesperrt."))
        return super().write(vals)


class SabProductionStep(models.Model):
    _name = "sab.production.step"
    _description = "SAB-P Fertigungsschritt"
    _order = "sequence, id"

    production_order_id = fields.Many2one(comodel_name="sab.production.order", string="Fertigungsauftrag", required=True, ondelete="cascade", index=True)
    project_id = fields.Many2one(related="production_order_id.project_id", string="Projekt", store=True, readonly=True)
    delivery_date = fields.Date(related="production_order_id.delivery_date", string="Liefertermin", readonly=True)
    production_state = fields.Selection(related="production_order_id.state", string="Fertigungsstatus", readonly=True)
    sequence = fields.Integer(string="Reihenfolge", default=10, index=True)
    name = fields.Char(string="Abteilung / Tätigkeit", required=True)
    state = fields.Selection(selection=[("pending", "Offen"), ("in_progress", "In Arbeit"), ("done", "Fertig"), ("skipped", "Entfällt")], string="Status", required=True, default="pending", index=True)
    responsible_user_id = fields.Many2one(comodel_name="res.users", string="Mitarbeiter", index=True)
    started_at = fields.Datetime(string="Begonnen am", readonly=True)
    finished_at = fields.Datetime(string="Fertig am", readonly=True)
    checked_by_id = fields.Many2one(comodel_name="res.users", string="Geprüft von")
    note = fields.Char(string="Bemerkung")

    def _ensure_editable(self):
        for record in self:
            if record.production_order_id.state == "done":
                raise ValidationError(_("Ein abgeschlossener Fertigungsauftrag ist gesperrt."))
            if record.production_order_id.state == "cancel":
                raise ValidationError(_("Ein stornierter Fertigungsauftrag ist gesperrt."))
            if record.production_order_id.bom_id.state != "released":
                raise ValidationError(_("Fertigungsschritte benötigen eine freigegebene Stückliste."))

    def _ensure_user_can_work(self):
        if self.env.user.has_group("project.group_project_manager"):
            return
        for record in self:
            if record.responsible_user_id and record.responsible_user_id != self.env.user:
                raise ValidationError(_("Dieser Arbeitsschritt ist einem anderen Mitarbeiter zugewiesen."))

    def action_claim(self):
        self._ensure_editable()
        self._ensure_user_can_work()
        for record in self:
            if record.state not in ("pending", "in_progress"):
                raise ValidationError(_("Nur offene oder laufende Arbeitsschritte können übernommen werden."))
            if not record.responsible_user_id:
                record.responsible_user_id = self.env.user
        return True

    def action_start(self):
        self._ensure_editable()
        self._ensure_user_can_work()
        for record in self:
            record.write({"state": "in_progress", "responsible_user_id": record.responsible_user_id.id or self.env.user.id, "started_at": record.started_at or fields.Datetime.now()})
            if record.production_order_id.state == "planned":
                record.production_order_id.write({"state": "in_progress", "started_at": record.production_order_id.started_at or fields.Datetime.now()})
        return True

    def action_open_time_entry(self):
        self.ensure_one()
        self._ensure_editable()
        self._ensure_user_can_work()
        if not self.responsible_user_id:
            self.responsible_user_id = self.env.user
        employee_view = self.env.ref("sab_project.view_sab_employee_time_entry_form")
        return {
            "type": "ir.actions.act_window",
            "name": _("Arbeitszeit erfassen"),
            "res_model": "sab.time.entry",
            "views": [(employee_view.id, "form")],
            "target": "current",
            "context": {
                "default_production_step_id": self.id,
                "default_project_id": self.project_id.id,
                "default_user_id": self.env.user.id,
                "default_name": self.name,
            },
        }

    def action_done(self):
        self._ensure_editable()
        self._ensure_user_can_work()
        for record in self:
            record.write({"state": "done", "responsible_user_id": record.responsible_user_id.id or self.env.user.id, "started_at": record.started_at or fields.Datetime.now(), "finished_at": fields.Datetime.now()})
            if record.production_order_id.state == "planned":
                record.production_order_id.write({"state": "in_progress", "started_at": record.production_order_id.started_at or fields.Datetime.now()})
        return True

    def action_skip(self):
        self._ensure_editable()
        self._ensure_user_can_work()
        for record in self:
            record.write({"state": "skipped", "finished_at": fields.Datetime.now()})
        return True

    def write(self, vals):
        if any(record.production_order_id.state in ("done", "cancel") for record in self):
            raise ValidationError(_("Fertigungsschritte eines abgeschlossenen oder stornierten Fertigungsauftrags sind gesperrt."))
        return super().write(vals)
