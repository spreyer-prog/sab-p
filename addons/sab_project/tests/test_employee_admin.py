from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabEmployeeAdmin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.regular_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Normaler interner Benutzer",
            "login": "sab_employee_admin_regular",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
        })
        cls.profile = cls.env["sab.employee.profile"].create({
            "name": "Mitarbeiter Verwaltungstest",
            "login": "sab_employee_admin_target",
            "email": "employee-admin@example.invalid",
        })

    def test_regular_internal_user_cannot_create_employee_login(self):
        with self.assertRaises(AccessError):
            self.profile.with_user(self.regular_user).action_create_or_update_user()

    def test_regular_internal_user_cannot_apply_employee_permissions(self):
        with self.assertRaises(AccessError):
            self.profile.with_user(self.regular_user).action_apply_permissions()

    def test_regular_internal_user_cannot_deactivate_employee(self):
        with self.assertRaises(AccessError):
            self.profile.with_user(self.regular_user).action_deactivate()

    def test_project_manager_can_create_employee_login_without_auto_invitation(self):
        self.profile.action_create_or_update_user()
        self.assertTrue(self.profile.user_id)
        self.assertFalse(self.profile.user_id.share)
        self.assertIn(self.env.ref("sab_project.group_sab_employee"), self.profile.user_id.group_ids)

    def test_employee_permissions_follow_profile_settings(self):
        self.profile.write({
            "mobile_access": True,
            "project_manager_access": False,
            "customer_release_access": True,
        })
        self.profile.action_create_or_update_user()
        user = self.profile.user_id
        self.assertIn(self.env.ref("sab_project.group_sab_employee"), user.group_ids)
        self.assertIn(self.env.ref("sab_project.group_sab_customer_release"), user.group_ids)
        self.assertNotIn(self.env.ref("project.group_project_manager"), user.group_ids)

        self.profile.write({"customer_release_access": False, "project_manager_access": True})
        self.profile.action_apply_permissions()
        self.assertNotIn(self.env.ref("sab_project.group_sab_customer_release"), user.group_ids)
        self.assertIn(self.env.ref("project.group_project_manager"), user.group_ids)

    def test_employee_deactivation_disables_login_and_reactivation_restores_it(self):
        self.profile.action_create_or_update_user()
        user = self.profile.user_id
        self.assertTrue(user.active)

        self.profile.action_deactivate()
        self.assertFalse(self.profile.active)
        self.assertFalse(user.active)

        self.profile.action_activate()
        self.assertTrue(self.profile.active)
        self.assertTrue(user.active)
