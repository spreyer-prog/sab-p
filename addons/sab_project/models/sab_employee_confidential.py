from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabEmployeeConfidentialNote(models.Model):
    _name = "sab.employee.confidential.note"
    _description = "SAB-P Vertrauliche Personalnotiz"
    _order = "event_date desc, id desc"

    employee_id = fields.Many2one(
        comodel_name="sab.employee.profile",
        string="Mitarbeiter",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_date = fields.Date(string="Datum", required=True, default=fields.Date.context_today, index=True)
    note_type = fields.Selection(
        selection=[
            ("lateness", "Verspätung"),
            ("absence", "Fehlzeit / Abwesenheit"),
            ("positive", "Positives Ereignis"),
            ("negative", "Negatives Ereignis"),
            ("salary_review", "Gehaltsgespräch / Beurteilung"),
            ("other", "Sonstige Personalnotiz"),
        ],
        string="Art",
        required=True,
        default="other",
        index=True,
    )
    title = fields.Char(string="Kurzbezeichnung", required=True)
    facts = fields.Text(
        string="Sachverhalt",
        required=True,
        help="Sachlich und zweckbezogen dokumentieren. Keine medizinischen Diagnosen oder unnötigen privaten Details eintragen.",
    )
    assessment = fields.Text(
        string="Bewertung / Relevanz",
        help="Optional: Bedeutung für Führung, Beurteilung oder ein späteres Personalgespräch.",
    )
    follow_up_date = fields.Date(string="Wiedervorlage")
    salary_review_relevant = fields.Boolean(string="Für nächstes Gehaltsgespräch berücksichtigen")
    active = fields.Boolean(string="Aktiv", default=True)

    @api.model
    def _check_confidential_access(self):
        if not self.env.user.has_group("sab_project.group_sab_confidential_hr"):
            raise AccessError(_("Sie haben keine Berechtigung für die vertrauliche Personalakte."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_confidential_access()
        return super().create(vals_list)

    def write(self, vals):
        self._check_confidential_access()
        return super().write(vals)

    def unlink(self):
        self._check_confidential_access()
        return super().unlink()

    @api.constrains("facts")
    def _check_facts(self):
        for record in self:
            if record.facts and len(record.facts.strip()) < 5:
                raise ValidationError(_("Der Sachverhalt muss nachvollziehbar dokumentiert werden."))


class SabEmployeeProfile(models.Model):
    _inherit = "sab.employee.profile"

    confidential_note_count = fields.Integer(
        string="Vertrauliche Personalnotizen",
        compute="_compute_confidential_note_count",
        groups="sab_project.group_sab_confidential_hr",
    )

    def _compute_confidential_note_count(self):
        Note = self.env["sab.employee.confidential.note"]
        allowed = self.env.user.has_group("sab_project.group_sab_confidential_hr")
        for employee in self:
            employee.confidential_note_count = Note.search_count([("employee_id", "=", employee.id)]) if allowed else 0

    def action_open_confidential_notes(self):
        self.ensure_one()
        if not self.env.user.has_group("sab_project.group_sab_confidential_hr"):
            raise AccessError(_("Sie haben keine Berechtigung für die vertrauliche Personalakte."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Vertrauliche Personalakte – %s") % self.name,
            "res_model": "sab.employee.confidential.note",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
            "target": "current",
        }
