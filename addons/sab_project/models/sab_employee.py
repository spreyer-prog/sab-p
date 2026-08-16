from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.fields import Command


class SabWorkArea(models.Model):
    _name = "sab.work.area"
    _description = "SAB-P Arbeitsbereich"
    _order = "sequence, name"

    name = fields.Char(string="Arbeitsbereich", required=True)
    code = fields.Char(string="Code", required=True, index=True)
    sequence = fields.Integer(string="Reihenfolge", default=10)
    active = fields.Boolean(default=True)
    employee_ids = fields.Many2many(
        comodel_name="sab.employee.profile",
        relation="sab_employee_work_area_rel",
        column1="work_area_id",
        column2="employee_id",
        string="Freigegebene Mitarbeiter",
        readonly=True,
    )

    _code_unique = models.Constraint("UNIQUE(code)", "Der Arbeitsbereich-Code muss eindeutig sein.")


class SabEmployeeProfile(models.Model):
    _name = "sab.employee.profile"
    _description = "SAB-P Mitarbeiter"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True, tracking=True)
    login = fields.Char(string="Login", required=True, tracking=True, help="Anmeldename für den Odoo-Zugang.")
    email = fields.Char(string="E-Mail", tracking=True)
    active = fields.Boolean(string="Aktiv", default=True, tracking=True)
    user_id = fields.Many2one(comodel_name="res.users", string="Odoo-Benutzer", readonly=True, copy=False, ondelete="restrict", tracking=True)
    user_state = fields.Selection(related="user_id.state", string="Zugangsstatus", readonly=True)
    last_login = fields.Datetime(related="user_id.login_date", string="Letzte Anmeldung", readonly=True)
    work_area_ids = fields.Many2many(comodel_name="sab.work.area", relation="sab_employee_work_area_rel", column1="employee_id", column2="work_area_id", string="Arbeitsbereiche", tracking=True)
    mobile_access = fields.Boolean(string="Mitarbeiter-App", default=True, tracking=True)
    customer_release_access = fields.Boolean(string="Kundenfreigaben", default=False, tracking=True)
    project_manager_access = fields.Boolean(string="Projektleiter", default=False, tracking=True)
    note = fields.Text(string="Hinweis")

    _login_unique = models.Constraint("UNIQUE(login)", "Der Mitarbeiter-Login muss eindeutig sein.")
    _user_unique = models.Constraint("UNIQUE(user_id)", "Ein Odoo-Benutzer darf nur einem SAB-P Mitarbeiter zugeordnet sein.")

    @api.constrains("user_id")
    def _check_internal_user(self):
        for record in self:
            if record.user_id and record.user_id.share:
                raise ValidationError(_("Ein SAB-P Mitarbeiter benötigt einen internen Odoo-Benutzer, keinen Portalbenutzer."))

    def _desired_group_commands(self, user):
        employee_group = self.env.ref("sab_project.group_sab_employee")
        release_group = self.env.ref("sab_project.group_sab_customer_release")
        manager_group = self.env.ref("project.group_project_manager")
        commands = []
        desired = {employee_group: self.mobile_access, release_group: self.customer_release_access, manager_group: self.project_manager_access}
        for group, enabled in desired.items():
            if enabled and group not in user.group_ids:
                commands.append(Command.link(group.id))
            elif not enabled and group in user.group_ids:
                commands.append(Command.unlink(group.id))
        return commands

    def action_create_or_update_user(self):
        self.ensure_one()
        if not self.active:
            raise ValidationError(_("Ein inaktiver Mitarbeiter kann keinen aktiven Zugang erhalten."))

        user = self.user_id
        if not user:
            existing = self.env["res.users"].sudo().search([("login", "=", self.login)], limit=1)
            if existing:
                other_profile = self.search([("user_id", "=", existing.id), ("id", "!=", self.id)], limit=1)
                if other_profile:
                    raise ValidationError(_("Der Login ist bereits einem anderen SAB-P Mitarbeiter zugeordnet."))
                user = existing
            else:
                user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
                    "name": self.name,
                    "login": self.login,
                    "email": self.email or False,
                    "active": True,
                    "group_ids": [Command.link(self.env.ref("base.group_user").id)],
                })
            self.user_id = user

        values = {"name": self.name, "login": self.login, "email": self.email or False, "active": self.active}
        commands = self._desired_group_commands(user)
        if commands:
            values["group_ids"] = commands
        user.sudo().write(values)
        return True

    def action_send_invitation(self):
        self.ensure_one()
        if not self.user_id:
            self.action_create_or_update_user()
        if not self.email:
            raise ValidationError(_("Für die Einladung muss beim Mitarbeiter eine E-Mail-Adresse hinterlegt sein."))
        self.action_create_or_update_user()
        return self.user_id.sudo().with_context(create_user=True).action_reset_password()

    def action_apply_permissions(self):
        for record in self:
            if not record.user_id:
                raise ValidationError(_("Bitte zuerst den Odoo-Zugang für den Mitarbeiter anlegen."))
            record.action_create_or_update_user()
        return True

    def action_deactivate(self):
        for record in self:
            record.active = False
            if record.user_id:
                record.user_id.sudo().active = False
        return True

    def action_activate(self):
        for record in self:
            record.active = True
            if record.user_id:
                record.user_id.sudo().active = True
        return True
