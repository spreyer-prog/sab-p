from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


CUSTOMER_MILESTONES = [
    ("order_received", "Auftrag eingegangen"),
    ("planning", "Planung"),
    ("procurement", "Materialbeschaffung"),
    ("mechanical", "Mechanische Fertigung"),
    ("wiring", "Verdrahtung"),
    ("testing", "Prüfung"),
    ("ready", "Fertig / versandbereit"),
    ("delivered", "Ausgeliefert"),
]


class SabCustomerProjectStatus(models.Model):
    _name = "sab.customer.project.status"
    _description = "SAB-P Kundenprojektstatus"
    _order = "project_id, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    project_id = fields.Many2one(comodel_name="project.project", string="Projekt", required=True, ondelete="cascade", index=True, tracking=True)
    partner_id = fields.Many2one(related="project_id.partner_id", string="Kunde", store=True, readonly=True, index=True)
    milestone = fields.Selection(selection=CUSTOMER_MILESTONES, string="Kundenstatus", required=True, default="order_received", tracking=True, index=True)
    suggested_milestone = fields.Selection(selection=CUSTOMER_MILESTONES, string="Vorschlag aus internem Stand", compute="_compute_suggested_milestone")
    progress_percent = fields.Integer(string="Fortschritt (%)", compute="_compute_progress", store=True)
    released = fields.Boolean(string="Für Kunden freigegeben", default=False, tracking=True, help="Nur freigegebene Statusstände dürfen im Kundenportal angezeigt werden.")
    released_at = fields.Datetime(string="Freigegeben am", readonly=True)
    released_by_id = fields.Many2one(comodel_name="res.users", string="Freigegeben von", readonly=True)
    note_customer = fields.Text(string="Hinweis für Kunden")
    note_internal = fields.Text(string="Interner Hinweis")

    _project_unique = models.Constraint("UNIQUE(project_id)", "Für dieses Projekt existiert bereits ein Kundenstatus.")

    def _check_release_permission(self):
        if not self.env.user.has_group("sab_project.group_sab_customer_release"):
            raise AccessError(_("Sie haben keine Berechtigung für Kundenportal-Freigaben."))

    def is_portal_visible_to(self, partner):
        """Return True only for an explicitly released status of the same commercial customer."""
        self.ensure_one()
        commercial_partner = partner.commercial_partner_id if partner else self.env["res.partner"]
        return bool(
            self.released
            and self.partner_id
            and commercial_partner
            and self.partner_id.commercial_partner_id == commercial_partner
        )

    @api.depends("milestone")
    def _compute_progress(self):
        order = [key for key, _label in CUSTOMER_MILESTONES]
        maximum = max(len(order) - 1, 1)
        for record in self:
            try:
                position = order.index(record.milestone)
            except ValueError:
                position = 0
            record.progress_percent = round(position * 100 / maximum)

    @api.depends("project_id.sab_sale_order_ids.state", "project_id.sab_sale_order_ids.sab_bom_ids.state", "project_id.sab_sale_order_ids.sab_bom_ids.production_order_ids.state", "project_id.sab_sale_order_ids.sab_bom_ids.production_order_ids.step_ids.state", "project_id.sab_sale_order_ids.sab_bom_ids.production_order_ids.step_ids.name")
    def _compute_suggested_milestone(self):
        for record in self:
            project = record.project_id
            orders = project.sab_sale_order_ids.filtered(lambda order: order.state in ("sale", "done"))
            if not orders:
                record.suggested_milestone = "order_received"
                continue
            boms = orders.mapped("sab_bom_ids")
            productions = boms.mapped("production_order_ids")
            if not boms:
                record.suggested_milestone = "planning"
                continue
            if not productions:
                record.suggested_milestone = "procurement"
                continue
            if all(production.state == "done" for production in productions):
                record.suggested_milestone = "ready"
                continue
            steps = productions.mapped("step_ids")
            active_names = " ".join(steps.filtered(lambda step: step.state in ("in_progress", "done")).mapped("name")).lower()
            if "prüfung" in active_names or "endkontrolle" in active_names:
                record.suggested_milestone = "testing"
            elif "verdraht" in active_names or "elektr" in active_names:
                record.suggested_milestone = "wiring"
            else:
                record.suggested_milestone = "mechanical"

    def action_apply_suggestion(self):
        for record in self:
            if record.suggested_milestone:
                record.write({"milestone": record.suggested_milestone, "released": False})
        return True

    def action_release(self):
        self._check_release_permission()
        for record in self:
            if not record.project_id.partner_id:
                raise ValidationError(_("Vor der Kundenfreigabe muss dem Projekt ein Kunde zugeordnet sein."))
            record.write({"released": True, "released_at": fields.Datetime.now(), "released_by_id": self.env.user.id})
        return True

    def action_withdraw(self):
        self._check_release_permission()
        self.write({"released": False})
        return True

    def write(self, vals):
        if vals.get("released"):
            self._check_release_permission()
        if "milestone" in vals and "released" not in vals:
            vals = dict(vals, released=False)
        return super().write(vals)
