from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabEmployeeFeedback(models.Model):
    _name = "sab.employee.feedback"
    _description = "SAB-P Mitarbeiter-Rückmeldung"
    _order = "create_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Rückmeldung", required=True, tracking=True)
    production_step_id = fields.Many2one(
        comodel_name="sab.production.step",
        string="Fertigungsschritt",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        related="production_step_id.project_id",
        string="Projekt",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Mitarbeiter",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    feedback_type = fields.Selection(
        selection=[
            ("note", "Hinweis"),
            ("photo", "Foto / Dokumentation"),
            ("problem", "Problem / Mangel"),
            ("material", "Materialbedarf"),
        ],
        string="Art",
        required=True,
        default="note",
        index=True,
        tracking=True,
    )
    description = fields.Text(string="Beschreibung", required=True)
    photo = fields.Binary(string="Foto", attachment=True)
    photo_filename = fields.Char(string="Dateiname")
    material_product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Benötigtes Material",
        ondelete="restrict",
    )
    material_quantity = fields.Float(string="Menge", digits=(16, 3), default=1.0)
    material_unit = fields.Selection(
        selection=[
            ("pcs", "Stück"),
            ("m", "Meter"),
            ("kg", "kg"),
            ("flat", "Pauschal"),
        ],
        string="Einheit",
        default="pcs",
    )
    state = fields.Selection(
        selection=[
            ("open", "Offen"),
            ("processed", "Bearbeitet"),
        ],
        string="Status",
        required=True,
        default="open",
        tracking=True,
        index=True,
    )
    processed_by_id = fields.Many2one(comodel_name="res.users", string="Bearbeitet von", readonly=True)
    processed_at = fields.Datetime(string="Bearbeitet am", readonly=True)

    @api.constrains("feedback_type", "photo", "material_product_id", "material_quantity")
    def _check_feedback_content(self):
        for record in self:
            if record.feedback_type == "photo" and not record.photo:
                raise ValidationError(_("Bei einer Foto-Rückmeldung muss ein Foto hochgeladen werden."))
            if record.feedback_type == "material":
                if not record.material_product_id:
                    raise ValidationError(_("Bei Materialbedarf muss ein Produkt ausgewählt werden."))
                if record.material_quantity <= 0:
                    raise ValidationError(_("Die Materialmenge muss größer 0 sein."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            step = self.env["sab.production.step"].browse(vals.get("production_step_id")).exists()
            if not step:
                raise ValidationError(_("Eine Rückmeldung benötigt einen gültigen Fertigungsschritt."))
            if (
                not self.env.user.has_group("project.group_project_manager")
                and step.responsible_user_id
                and step.responsible_user_id != self.env.user
            ):
                raise ValidationError(_("Rückmeldungen dürfen nur zur eigenen Arbeit erfasst werden."))
            vals.setdefault("user_id", self.env.user.id)
        return super().create(vals_list)

    def action_mark_processed(self):
        for record in self:
            record.write({
                "state": "processed",
                "processed_by_id": self.env.user.id,
                "processed_at": fields.Datetime.now(),
            })
        return True
