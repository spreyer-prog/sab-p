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
