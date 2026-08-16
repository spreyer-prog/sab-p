from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DEFAULT_PRODUCTION_STEPS = [
    (10, "Mechanische Fertigung", "sab_project.sab_work_area_mechanical_fabrication"),
    (20, "Mechanischer Aufbau", "sab_project.sab_work_area_mechanical_assembly"),
    (30, "Bestückung Geräte", "sab_project.sab_work_area_device_assembly"),
    (40, "Bestückung Klemmen", "sab_project.sab_work_area_terminal_assembly"),
    (50, "Vorbereitung Verdrahtung", "sab_project.sab_work_area_wiring_preparation"),
    (60, "Elektrische Fertigung", "sab_project.sab_work_area_electrical"),
    (70, "Prüfung", "sab_project.sab_work_area_testing"),
    (80, "Endkontrolle", "sab_project.sab_work_area_final_inspection"),
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
            record.progress_percent = len(steps.filtered(lambda step: step.state == "done")) * 100.0 / len(steps) if steps else 0.0

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
                commands = []
                for sequence, name, work_area_xmlid in DEFAULT_PRODUCTION_STEPS:
                    work_area = self.env.ref(work_area_xmlid, raise_if_not_found=False)
                    commands.append((0, 0, {"sequence": sequence, "name": name, "work_area_id": work_area.id if work_area else False}))
                vals["step_ids"] = commands
            prepared.append(vals)
        return super().create(prepared)

    def action_start(self):
        for record in self:
            if record.state == "planned":
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
        if any(record.state == "done" for record in self) and set(vals) - {"responsible_user_id", "note"}:
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
    work_area_id = fields.Many2one(comodel_name="sab.work.area", string="Arbeitsbereich", ondelete="restrict", index=True)
    state = fields.Selection(selection=[("pending", "Offen"), ("in_progress", "In Arbeit"), ("paused", "Pausiert"), ("done", "Fertig"), ("skipped", "Entfällt")], string="Status", required=True, default="pending", index=True)
    responsible_employee_id = fields.Many2one(comodel_name="sab.employee.profile", string="Mitarbeiter", ondelete="restrict", index=True, domain="[('active', '=', True), ('mobile_access', '=', True), ('user_id', '!=', False), ('work_area_ids', 'in', work_area_id)]")
    responsible_user_id = fields.Many2one(comodel_name="res.users", string="Technischer Benutzer", index=True, readonly=True)
    started_at = fields.Datetime(string="Begonnen am", readonly=True)
    paused_at = fields.Datetime(string="Pausiert am", readonly=True)
    finished_at = fields.Datetime(string="Fertig am", readonly=True)
    checked_by_id = fields.Many2one(comodel_name="res.users", string="Geprüft von")
    note = fields.Char(string="Bemerkung")

    @api.constrains("responsible_employee_id", "work_area_id")
    def _check_employee_qualification(self):
        for record in self:
            employee = record.responsible_employee_id.sudo()
            if not employee:
                continue
            if not employee.active or not employee.mobile_access or not employee.user_id or not employee.user_id.active:
                raise ValidationError(_("Der ausgewählte Mitarbeiter besitzt keinen aktiven SAB-P Mitarbeiterzugang."))
            if record.work_area_id and record.work_area_id not in employee.work_area_ids:
                raise ValidationError(_("Der Mitarbeiter %s ist nicht für den Arbeitsbereich %s freigegeben.") % (employee.name, record.work_area_id.name))

    @api.model
    def _legacy_work_area_by_name(self, name):
        normalized = (name or "").strip().lower()
        for _sequence, default_name, xmlid in DEFAULT_PRODUCTION_STEPS:
            if normalized == default_name.lower():
                return self.env.ref(xmlid, raise_if_not_found=False)
        return self.env["sab.work.area"]

    def action_migrate_legacy_assignment(self):
        """Upgrade helper: enrich old steps without changing historical assignment."""
        for record in self.sudo():
            values = {}
            if not record.work_area_id:
                area = self._legacy_work_area_by_name(record.name)
                if area:
                    values["work_area_id"] = area.id
            if record.responsible_user_id and not record.responsible_employee_id:
                profile = self.env["sab.employee.profile"].sudo().search([("user_id", "=", record.responsible_user_id.id)], limit=1)
                if profile:
                    values["responsible_employee_id"] = profile.id
            if values:
                record.with_context(sab_legacy_migration=True).write(values)
        return True

    @api.onchange("responsible_employee_id")
    def _onchange_responsible_employee_id(self):
        for record in self:
            employee = record.responsible_employee_id.sudo()
            record.responsible_user_id = employee.user_id if employee else False

    @api.onchange("work_area_id")
    def _onchange_work_area_id(self):
        for record in self:
            employee = record.responsible_employee_id.sudo()
            if employee and record.work_area_id not in employee.work_area_ids:
                record.responsible_employee_id = False
                record.responsible_user_id = False

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            employee_id = vals.get("responsible_employee_id")
            if employee_id:
                employee = self.env["sab.employee.profile"].sudo().browse(employee_id).exists()
                vals["responsible_user_id"] = employee.user_id.id if employee and employee.user_id else False
            prepared.append(vals)
        return super().create(prepared)

    def _ensure_editable(self):
        for record in self:
            if record.production_order_id.state in ("done", "cancel"):
                raise ValidationError(_("Ein abgeschlossener oder stornierter Fertigungsauftrag ist gesperrt."))
            if record.production_order_id.bom_id.state != "released":
                raise ValidationError(_("Fertigungsschritte benötigen eine freigegebene Stückliste."))

    def _employee_for_user(self, user):
        return self.env["sab.employee.profile"].sudo().search([("user_id", "=", user.id), ("active", "=", True), ("mobile_access", "=", True)], limit=1)

    def _ensure_user_can_work(self):
        if self.env.user.has_group("project.group_project_manager"):
            return
        employee = self._employee_for_user(self.env.user)
        if not employee:
            raise ValidationError(_("Für Ihren Benutzer ist kein aktiver SAB-P Mitarbeiter mit App-Zugriff hinterlegt."))
        for record in self:
            if record.work_area_id and record.work_area_id not in employee.work_area_ids:
                raise ValidationError(_("Sie sind für den Arbeitsbereich %s nicht freigegeben.") % record.work_area_id.name)
            if record.responsible_user_id and record.responsible_user_id != self.env.user:
                raise ValidationError(_("Dieser Arbeitsschritt ist einem anderen Mitarbeiter zugewiesen."))

    def _claim_for_current_employee(self):
        employee = self._employee_for_user(self.env.user)
        if employee:
            for record in self:
                if not record.responsible_employee_id:
                    record.write({"responsible_employee_id": employee.id})
            return
        if self.env.user.has_group("project.group_project_manager"):
            for record in self:
                if not record.responsible_user_id:
                    record.with_context(sab_legacy_migration=True).write({"responsible_user_id": self.env.user.id})
            return
        raise ValidationError(_("Für Ihren Benutzer ist kein aktiver SAB-P Mitarbeiter mit App-Zugriff hinterlegt."))

    def action_claim(self):
        self._ensure_editable(); self._ensure_user_can_work()
        for record in self:
            if record.state not in ("pending", "in_progress", "paused"):
                raise ValidationError(_("Nur offene, laufende oder pausierte Arbeitsschritte können übernommen werden."))
        self._claim_for_current_employee(); return True

    def action_start(self):
        self._ensure_editable(); self._ensure_user_can_work(); self._claim_for_current_employee()
        for record in self:
            if record.state not in ("pending", "paused"):
                raise ValidationError(_("Nur offene oder pausierte Arbeitsschritte können gestartet werden."))
            record.write({"state": "in_progress", "started_at": record.started_at or fields.Datetime.now(), "paused_at": False})
            if record.production_order_id.state == "planned":
                record.production_order_id.write({"state": "in_progress", "started_at": record.production_order_id.started_at or fields.Datetime.now()})
        return True

    def action_pause(self):
        self._ensure_editable(); self._ensure_user_can_work()
        for record in self:
            if record.state != "in_progress":
                raise ValidationError(_("Nur laufende Arbeitsschritte können pausiert werden."))
            record.write({"state": "paused", "paused_at": fields.Datetime.now()})
        return True

    def action_open_time_entry(self):
        self.ensure_one(); self._ensure_editable(); self._ensure_user_can_work(); self._claim_for_current_employee()
        view = self.env.ref("sab_project.view_sab_employee_time_entry_form")
        return {"type": "ir.actions.act_window", "name": _("Arbeitszeit erfassen"), "res_model": "sab.time.entry", "views": [(view.id, "form")], "target": "current", "context": {"default_production_step_id": self.id, "default_project_id": self.project_id.id, "default_user_id": self.env.user.id, "default_name": self.name}}

    def action_open_feedback(self):
        self.ensure_one(); self._ensure_editable(); self._ensure_user_can_work(); self._claim_for_current_employee()
        view = self.env.ref("sab_project.view_sab_employee_feedback_form")
        return {"type": "ir.actions.act_window", "name": _("Rückmeldung erfassen"), "res_model": "sab.employee.feedback", "views": [(view.id, "form")], "target": "current", "context": {"default_production_step_id": self.id, "default_user_id": self.env.user.id, "default_name": self.name}}

    def action_done(self):
        self._ensure_editable(); self._ensure_user_can_work(); self._claim_for_current_employee()
        for record in self:
            if record.state not in ("pending", "in_progress", "paused"):
                raise ValidationError(_("Nur offene, laufende oder pausierte Arbeitsschritte können fertiggemeldet werden."))
            record.write({"state": "done", "started_at": record.started_at or fields.Datetime.now(), "paused_at": False, "finished_at": fields.Datetime.now()})
            if record.production_order_id.state == "planned":
                record.production_order_id.action_start()
        return True

    def action_skip(self):
        self._ensure_editable(); self._ensure_user_can_work()
        for record in self:
            record.write({"state": "skipped", "paused_at": False, "finished_at": fields.Datetime.now()})
        return True

    def write(self, vals):
        if any(record.production_order_id.state in ("done", "cancel") for record in self):
            raise ValidationError(_("Fertigungsschritte eines abgeschlossenen oder stornierten Fertigungsauftrags sind gesperrt."))
        vals = dict(vals)
        if "responsible_employee_id" in vals:
            employee = self.env["sab.employee.profile"].sudo().browse(vals.get("responsible_employee_id")).exists() if vals.get("responsible_employee_id") else False
            vals["responsible_user_id"] = employee.user_id.id if employee and employee.user_id else False
        return super().write(vals)
