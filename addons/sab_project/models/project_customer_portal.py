from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProjectCustomerPortal(models.Model):
    _inherit = "project.project"

    sab_customer_status_ids = fields.One2many(
        comodel_name="sab.customer.project.status",
        inverse_name="project_id",
        string="Kundenstatus",
        copy=False,
    )
    sab_customer_status_count = fields.Integer(
        string="Anzahl Kundenstatus",
        compute="_compute_sab_customer_status_count",
    )

    @api.depends("sab_customer_status_ids")
    def _compute_sab_customer_status_count(self):
        for project in self:
            project.sab_customer_status_count = len(project.sab_customer_status_ids)

    def action_open_sab_customer_status(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Bitte zuerst einen Kunden im Projekt hinterlegen."))
        status = self.sab_customer_status_ids[:1]
        if not status:
            status = self.env["sab.customer.project.status"].create({
                "project_id": self.id,
                "milestone": "order_received",
            })
        return {
            "type": "ir.actions.act_window",
            "name": _("Kundenstatus %s") % (self.sab_project_reference or self.name),
            "res_model": "sab.customer.project.status",
            "res_id": status.id,
            "view_mode": "form",
            "target": "current",
        }

    def write(self, vals):
        old_partner_ids = {project.id: project.partner_id.id for project in self}
        result = super().write(vals)

        if "partner_id" in vals:
            changed_projects = self.filtered(
                lambda project: old_partner_ids.get(project.id) != project.partner_id.id
            )
            if changed_projects:
                # Ein Kundenwechsel darf niemals bestehende Portal-Freigaben auf
                # einen anderen Kunden übertragen. Freigaben werden deshalb
                # automatisch zurückgezogen und müssen bewusst neu erteilt werden.
                changed_projects.mapped("sab_customer_status_ids").write({"released": False})
                self.env["sab.project.document"].search([
                    ("project_id", "in", changed_projects.ids),
                    ("customer_visible", "=", True),
                ]).write({"customer_visible": False})
                self.env["sab.employee.feedback"].search([
                    ("project_id", "in", changed_projects.ids),
                    ("customer_visible", "=", True),
                ]).write({"customer_visible": False})
        return result
