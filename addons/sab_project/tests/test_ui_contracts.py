from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabUiContracts(TransactionCase):

    def test_employee_mobile_ui_uses_employee_profile(self):
        action = self.env.ref("sab_project.action_sab_employee_my_steps")
        self.assertIn("sab_employee_profile_id", action.domain)
        view = self.env.ref("sab_project.view_sab_production_step_employee_form")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='responsible_employee_id']"))

    def test_production_ui_uses_work_area_and_employee_profile(self):
        view = self.env.ref("sab_project.view_sab_production_step_form")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='work_area_id']"))
        self.assertTrue(arch.xpath("//field[@name='responsible_employee_id']"))

    def test_free_work_action_relies_on_record_rule_for_qualification(self):
        action = self.env.ref("sab_project.action_sab_employee_free_steps")
        self.assertNotIn("work_area_id", action.domain)

    def test_employee_admin_exposes_invitation_and_access_status(self):
        view = self.env.ref("sab_project.view_sab_employee_profile_form")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='access_status']"))
        self.assertTrue(arch.xpath("//button[@name='action_send_invitation']"))

    def test_project_number_is_mandatory_first_overview_column(self):
        view = self.env.ref("sab_project.view_sab_project_overview_list")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        fields = arch.xpath("/list/field")
        self.assertTrue(fields)
        self.assertEqual(fields[0].get("name"), "sab_project_reference")
        self.assertNotEqual(fields[0].get("optional"), "hide")

    def test_project_overview_action_uses_sab_list_view(self):
        action = self.env.ref("sab_project.action_sab_project_overview")
        self.assertEqual(action.view_id, self.env.ref("sab_project.view_sab_project_overview_list"))

    def test_standard_odoo_project_list_is_extended_with_project_number(self):
        view = self.env.ref("sab_project.sab_project_project_list_inherit")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='name'][@position='before']/field[@name='sab_project_reference']"))

    def test_controlling_action_exposes_list_pivot_graph_and_form(self):
        action = self.env.ref("sab_project.action_sab_project_controlling")
        self.assertIn("list", action.view_mode)
        self.assertIn("pivot", action.view_mode)
        self.assertIn("graph", action.view_mode)
        self.assertIn("form", action.view_mode)

        list_view = self.env.ref("sab_project.view_sab_project_controlling_list")
        pivot_view = self.env.ref("sab_project.view_sab_project_controlling_pivot")
        graph_view = self.env.ref("sab_project.view_sab_project_controlling_graph")
        list_arch = etree.fromstring(list_view.arch_db.encode("utf-8"))
        pivot_arch = etree.fromstring(pivot_view.arch_db.encode("utf-8"))
        graph_arch = etree.fromstring(graph_view.arch_db.encode("utf-8"))

        self.assertTrue(list_arch.xpath("/list/field[@name='contribution_margin']"))
        self.assertTrue(list_arch.xpath("/list/field[@name='contribution_margin_percent']"))
        for measure in ("offer_amount", "actual_direct_cost", "contribution_margin", "actual_hours", "calculated_hours"):
            self.assertTrue(pivot_arch.xpath(f"/pivot/field[@name='{measure}'][@type='measure']"))
        for measure in ("offer_amount", "actual_direct_cost", "contribution_margin"):
            self.assertTrue(graph_arch.xpath(f"/graph/field[@name='{measure}'][@type='measure']"))

    def test_sale_portal_extension_keeps_odoo_table_in_dom_and_renders_sub_lines(self):
        """Odoo portal JS needs its own table while SAB-P displays the LV hierarchy."""
        inherited = self.env.ref("sab_project.sab_sale_order_portal_calculation")
        parent = self.env.ref("sale.sale_order_portal_content")
        self.assertEqual(inherited.inherit_id, parent)
        arch = etree.fromstring(inherited.arch_db.encode("utf-8"))
        xpath_nodes = arch.xpath("//xpath[@expr=\"//table[@id='sales_order_table']\"]")
        self.assertEqual(len(xpath_nodes), 2)
        attrs = xpath_nodes[0].xpath("./attribute[@name='t-attf-class']")
        self.assertEqual(len(attrs), 1)
        self.assertIn("d-none", attrs[0].text or "")
        self.assertFalse(xpath_nodes[0].xpath("./attribute[@name='t-if']"))
        item_templates = arch.xpath("//t[@t-elif=\"line.line_type == 'item'\"]")
        self.assertEqual(len(item_templates), 1)
        hierarchy_marker = item_templates[0].xpath(
            ".//span[@t-if='line.parent_section_id or line.parent_cabinet_id']"
        )
        self.assertTrue(hierarchy_marker)
        style_cells = item_templates[0].xpath(".//td[contains(@t-att-style, 'padding-left')]")
        self.assertTrue(style_cells)
        self.assertIn("line.parent_section_id", style_cells[0].get("t-att-style") or "")
        self.assertIn("line.parent_cabinet_id", style_cells[0].get("t-att-style") or "")

    def test_primary_button_labels_match_documented_ui_contract(self):
        """Keep the user manual's SAB-P button names tied to the actual XML views."""
        expected = (
            ("sab_project.sab_project_project_form_inherit", "action_create_sab_quotation", "Neues Angebot"),
            ("sab_project.sab_project_project_form_inherit", "action_view_sab_quotations", "Angebote"),
            ("sab_project.sab_project_project_form_inherit", "action_assign_sab_project_reference", "Projektnummer vergeben"),
            ("sab_project.sab_sale_order_form_inherit", "action_create_sab_revision", "Neue Revision"),
            ("sab_project.sab_sale_order_form_inherit", "action_generate_sab_bom", "Stückliste erzeugen"),
            ("sab_project.view_sab_project_bom_form", "action_release", "Stückliste freigeben"),
            ("sab_project.view_sab_project_bom_form", "action_create_production_order", "Fertigungsauftrag erzeugen"),
            ("sab_project.view_sab_project_bom_form", "action_generate_purchase_requirements", "Einkaufsbedarf erzeugen"),
        )
        for view_xmlid, method, label in expected:
            view = self.env.ref(view_xmlid)
            arch = etree.fromstring(view.arch_db.encode("utf-8"))
            buttons = arch.xpath(f"//button[@name='{method}']")
            self.assertTrue(buttons, f"{method} missing in {view_xmlid}")
            self.assertEqual(buttons[0].get("string"), label)
