from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabSystemAdminFullAccess(TransactionCase):
    def test_system_admin_gets_full_employee_profile_and_all_sab_groups(self):
        admin = self.env["res.users"].create(
            {
                "name": "SAB-P Volladministrator Test",
                "login": "sab-full-admin@example.invalid",
            }
        )
        self.env.ref("base.group_system").write(
            {"user_ids": [Command.link(admin.id)]}
        )

        self.env["res.users"]._sab_bootstrap_system_admins()
        admin.invalidate_recordset()

        for xmlid in (
            "sab_project.group_sab_employee",
            "sab_project.group_sab_purchasing",
            "sab_project.group_sab_purchase_approver",
            "sab_project.group_sab_warehouse",
            "sab_project.group_sab_customer_release",
            "sab_project.group_sab_confidential_hr",
            "project.group_project_manager",
        ):
            self.assertTrue(
                admin.has_group(xmlid),
                "%s wurde dem Systemadministrator nicht zugewiesen" % xmlid,
            )

        profile = self.env["sab.employee.profile"].search(
            [("user_id", "=", admin.id)],
            limit=1,
        )
        self.assertTrue(profile)
        self.assertTrue(profile.active)
        self.assertTrue(profile.mobile_access)
        self.assertTrue(profile.customer_release_access)
        self.assertTrue(profile.project_manager_access)
        self.assertTrue(profile.purchasing_access)
        self.assertTrue(profile.purchase_approval_access)
        self.assertTrue(profile.warehouse_access)
        self.assertEqual(
            set(profile.work_area_ids.ids),
            set(self.env["sab.work.area"].search([("active", "=", True)]).ids),
        )
