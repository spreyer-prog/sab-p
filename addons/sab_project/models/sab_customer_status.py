from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projekt",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related="project_id.partner_id",
        string="Kunde",
        store=True,
        readonly=True,
        index=True,
    )
    milestone = fields.Selection(
        selection=CUSTOMER_MILESTONES,
        string="Kundenstatus",
        required=True,
        default="order_received",
        tracking=True,
        index=True,
    )
    progress_percent = fields.Integer(
        string="Fortschritt (%)",
        compute="_compute_progress",
        store=True,
    )
    released = fields.Boolean(
        string="Für Kunden freigegeben",
        default=False,
        tracking=True,
        help="Nur freigegebene Statusstände dürfen später im Kundenportal angezeigt werden.",
    )
    released_at = fields.Datetime(string="Freigegeben am", readonly=True)
    released_by_id = fields.Many2one(comodel_name="res.users", string="Freigegeben von", readonly=True)
    note_customer = fields.Text(string="Hinweis für Kunden")
    note_internal = fields.Text(string="Interner Hinweis")

    _project_unique = models.Constraint(
        "UNIQUE(project_id)",
        "Für dieses Projekt existiert bereits ein Kundenstatus.",
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

    def action_release(self):
        for record in self:
            if not record.project_id.partner_id:
                raise ValidationError(_("Vor der Kundenfreigabe muss dem Projekt ein Kunde zugeordnet sein."))
            record.write({
                "released": True,
                "released_at": fields.Datetime.now(),
                "released_by_id": self.env.user.id,
            })
        return True

    def action_withdraw(self):
        self.write({"released": False})
        return True

    def write(self, vals):
        # Eine Statusänderung wird nie stillschweigend veröffentlicht.
        if "milestone" in vals and "released" not in vals:
            vals = dict(vals, released=False)
        return super().write(vals)
