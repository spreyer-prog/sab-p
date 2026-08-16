from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabUiContracts(TransactionCase):

    def test_project_overview_action_uses_sab_list_view(self):
        action = self.env.ref("sab_project.sab_project_overview_action")
        view = self.env.ref("sab_project.sab_project_overview_list")
        self.assertEqual(action.res_model, "project.project")
        self.assertEqual(action.view_mode, "list,form")
        self.assertEqual(action.view_id, view)
        self.assertIn((view.id, "list"), action.views)

    def test_project_number_is_mandatory_first_overview_column(self):
        view = self.env.ref("sab_project.sab_project_overview_list")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        fields = arch.xpath("/list/field")
        self.assertTrue(fields)
        self.assertEqual(fields[0].get("name"), "sab_project_reference")
        self.assertIsNone(fields[0].get("optional"))

    def test_standard_odoo_project_list_is_extended_with_project_number(self):
        inherited = self.env.ref("sab_project.sab_standard_project_list_inherit")
        standard = self.env.ref("project.view_project")
        self.assertEqual(inherited.inherit_id, standard)
        arch = etree.fromstring(inherited.arch_db.encode("utf-8"))
        inserted = arch.xpath("//field[@name='name']/field[@name='sab_project_reference']")
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted[0].get("string"), "Projekt-Nr.")

    def test_employee_admin_exposes_invitation_and_access_status(self):
        view = self.env.ref("sab_project.view_sab_employee_profile_form")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertEqual(len(arch.xpath("//button[@name='action_send_invitation']")), 1)
        self.assertEqual(len(arch.xpath("//field[@name='user_state']")), 1)
        self.assertEqual(len(arch.xpath("//field[@name='last_login']")), 1)
        self.assertEqual(len(arch.xpath("//field[@name='work_area_ids']")), 1)

    def test_production_ui_uses_work_area_and_employee_profile(self):
        view = self.env.ref("sab_project.view_sab_production_order_form")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='step_ids']//field[@name='work_area_id']"))
        self.assertTrue(arch.xpath("//field[@name='step_ids']//field[@name='responsible_employee_id']"))

    def test_employee_mobile_ui_uses_employee_profile(self):
        kanban = self.env.ref("sab_project.view_sab_employee_step_kanban")
        arch = etree.fromstring(kanban.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='work_area_id']"))
        self.assertTrue(arch.xpath("//field[@name='responsible_employee_id']"))
        self.assertEqual(len(arch.xpath("//button[@name='action_claim']")), 1)
        self.assertEqual(len(arch.xpath("//button[@name='action_open_time_entry']")), 1)
        self.assertEqual(len(arch.xpath("//button[@name='action_open_feedback']")), 1)

    def test_free_work_action_relies_on_record_rule_for_qualification(self):
        action = self.env.ref("sab_project.action_sab_employee_open_steps")
        self.assertIn("('responsible_user_id', '=', False)", action.domain)
        self.assertIn("('state', '=', 'pending')", action.domain)
        self.assertNotIn("work_area_ids", action.domain)
        self.assertIn("nur freie arbeitsschritte", action.help.lower())
