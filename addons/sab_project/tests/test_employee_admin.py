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
