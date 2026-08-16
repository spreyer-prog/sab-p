import base64

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSabSecurityPermissions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.normal_user = cls.env["res.users"].create({"name": "SAB Mitarbeiter ohne Freigabe", "login": "sab.no.release@test.local"})
        cls.other_employee = cls.env["res.users"].create({"name": "SAB anderer Mitarbeiter", "login": "sab.other.employee@test.local"})
        cls.release_user = cls.env["res.users"].create({"name": "SAB Kundenfreigeber", "login": "sab.release@test.local"})
        cls.env.ref("base.group_user").write({"user_ids": [(4, cls.normal_user.id), (4, cls.other_employee.id), (4, cls.release_user.id)]})
        cls.env.ref("sab_project.group_sab_employee").write({"user_ids": [(4, cls.normal_user.id), (4, cls.other_employee.id)]})
        cls.env.ref("sab_project.group_sab_customer_release").write({"user_ids": [(4, cls.release_user.id)]})
        all_areas = cls.env["sab.work.area"].search([]).ids
        cls.normal_profile = cls.env["sab.employee.profile"].create({
            "name": "SAB Mitarbeiter ohne Freigabe", "login": cls.normal_user.login,
            "user_id": cls.normal_user.id, "work_area_ids": [(6, 0, all_areas)], "mobile_access": True,
        })
        cls.other_profile = cls.env["sab.employee.profile"].create({
            "name": "SAB anderer Mitarbeiter", "login": cls.other_employee.login,
            "user_id": cls.other_employee.id, "work_area_ids": [(6, 0, all_areas)], "mobile_access": True,
        })

        cls.partner = cls.env["res.partner"].create({"name": "Sicherheitskunde"})
        cls.project = cls.env["project.project"].create({"name": "Sicherheitsprojekt", "partner_id": cls.partner.id})
        cls.status = cls.env["sab.customer.project.status"].create({"project_id": cls.project.id})
        cls.document = cls.env["sab.project.document"].create({
            "name": "Freigabetest", "project_id": cls.project.id, "document_type": "test_report",
            "file_name": "test.pdf", "file_data": base64.b64encode(b"test"),
        })
        cls.document.action_release()

        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id, "sab_project_id": cls.project.id})
        cls.bom = cls.env["sab.project.bom"].create({"name": "STL Security", "order_id": cls.order.id, "project_id": cls.project.id})
        cls.bom.state = "released"
        cls.production = cls.env["sab.production.order"].create({"name": "FA Security", "bom_id": cls.bom.id})
        steps = cls.production.step_ids.sorted("sequence")
        cls.own_step = steps[0]
        cls.other_step = steps[1]
        cls.free_step = steps[2]
        cls.own_step.responsible_user_id = cls.normal_user
        cls.other_step.responsible_user_id = cls.other_employee

    def test_customer_release_role_does_not_grant_project_manager(self):
        self.assertTrue(self.release_user.has_group("sab_project.group_sab_customer_release"))
        self.assertFalse(self.release_user.has_group("project.group_project_manager"))

    def test_non_employee_internal_user_has_no_employee_workflow_access(self):
        with self.assertRaises(AccessError):
            self.env["sab.production.step"].with_user(self.release_user).check_access_rights("read")
        with self.assertRaises(AccessError):
            self.env["sab.time.entry"].with_user(self.release_user).check_access_rights("read")
        with self.assertRaises(AccessError):
            self.env["sab.employee.feedback"].with_user(self.release_user).check_access_rights("read")

    def test_employee_can_read_only_own_profile(self):
        self.normal_profile.with_user(self.normal_user).check_access("read")
        with self.assertRaises(AccessError):
            self.other_profile.with_user(self.normal_user).check_access("read")

    def test_normal_internal_user_cannot_publish_customer_content(self):
        with self.assertRaises(AccessError):
            self.status.with_user(self.normal_user).action_release()
        with self.assertRaises(AccessError):
            self.document.with_user(self.normal_user).action_release_to_customer()

    def test_release_user_can_publish_customer_content(self):
        self.status.with_user(self.release_user).action_release()
        self.assertTrue(self.status.released)
        self.document.with_user(self.release_user).action_release_to_customer()
        self.assertTrue(self.document.customer_visible)

    def test_employee_sees_only_own_or_matching_free_steps(self):
        visible = self.env["sab.production.step"].with_user(self.normal_user).search([
            ("production_order_id", "=", self.production.id),
        ])
        self.assertIn(self.own_step, visible)
        self.assertIn(self.free_step, visible)
        self.assertNotIn(self.other_step, visible)

    def test_employee_cannot_read_other_employee_step_directly(self):
        with self.assertRaises(AccessError):
            self.other_step.with_user(self.normal_user).check_access("read")
