from odoo import api, models
from odoo.fields import Command


class ResUsersSabSystemAdminBootstrap(models.Model):
    _inherit = "res.users"

    @api.model
    def _sab_bootstrap_system_admins(self):
        """Make every active Odoo system administrator a full SAB-P administrator.

        The employee profile remains the source of truth for operational SAB-P
        roles. System administrators therefore receive a matching profile instead
        of relying on ad-hoc approval bypasses.
        """
        system_group = self.env.ref("base.group_system", raise_if_not_found=False)
        if not system_group:
            return True

        sab_groups = [
            self.env.ref(xmlid, raise_if_not_found=False)
            for xmlid in (
                "sab_project.group_sab_employee",
                "sab_project.group_sab_purchasing",
                "sab_project.group_sab_purchase_approver",
                "sab_project.group_sab_warehouse",
                "sab_project.group_sab_customer_release",
                "sab_project.group_sab_confidential_hr",
                "project.group_project_manager",
            )
        ]
        sab_groups = [group for group in sab_groups if group]
        work_areas = self.env["sab.work.area"].sudo().search([("active", "=", True)])
        Profile = self.env["sab.employee.profile"].sudo()

        admins = system_group.user_ids.sudo().filtered(
            lambda user: user.active and not user.share
        )
        for user in admins:
            missing_groups = [group.id for group in sab_groups if group not in user.group_ids]
            if missing_groups:
                user.sudo().write({
                    "group_ids": [Command.link(group_id) for group_id in missing_groups]
                })

            profile = Profile.search([("user_id", "=", user.id)], limit=1)
            if not profile:
                profile = Profile.search([("login", "=", user.login)], limit=1)

            values = {
                "name": user.name or user.login,
                "login": user.login,
                "email": user.email or False,
                "active": True,
                "mobile_access": True,
                "customer_release_access": True,
                "project_manager_access": True,
                "purchasing_access": True,
                "purchase_approval_access": True,
                "warehouse_access": True,
            }
            if work_areas:
                values["work_area_ids"] = [Command.set(work_areas.ids)]

            if profile:
                if not profile.user_id:
                    values["user_id"] = user.id
                profile.write(values)
            else:
                values["user_id"] = user.id
                Profile.create(values)
        return True
