from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabUiContracts(TransactionCase):

    def test_project_overview_action_uses_sab_list_view(self):
        action = self.env.ref("sab_project.sab_project_overview_action")
        view = self.env.ref("sab_project.sab_project_overview_list")

        self.assertEqual(action.res_model, "project.project")
        self.assertTrue(action.view_ids.filtered(lambda item: item.view_id == view and item.view_mode == "list"))

    def test_project_number_is_mandatory_first_overview_column(self):
        view = self.env.ref("sab_project.sab_project_overview_list")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        fields = arch.xpath("/list/field")

        self.assertTrue(fields)
        self.assertEqual(fields[0].get("name"), "sab_project_reference")
        self.assertIsNone(fields[0].get("optional"))
