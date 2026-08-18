from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabUiContracts(TransactionCase):

    def _assert_button_label(self, view_xmlid, button_name, expected_label):
        view = self.env.ref(view_xmlid)
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        matches = arch.xpath(f"//button[@name='{button_name}'][@string='{expected_label}']")
        self.assertTrue(
            matches,
            f"{view_xmlid}: Button {button_name!r} muss als {expected_label!r} beschriftet sein",
        )

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
        self.assertIn("nur freie arbeitsschritte", str(action.help).lower())

    def test_controlling_action_exposes_list_pivot_graph_and_form(self):
        action = self.env.ref("sab_project.action_sab_project_controlling")
        self.assertEqual(action.res_model, "sab.project.controlling")
        self.assertEqual(action.view_mode, "list,pivot,graph,form")

        list_arch = etree.fromstring(self.env.ref("sab_project.view_sab_project_controlling_list").arch_db.encode("utf-8"))
        pivot_arch = etree.fromstring(self.env.ref("sab_project.view_sab_project_controlling_pivot").arch_db.encode("utf-8"))
        graph_arch = etree.fromstring(self.env.ref("sab_project.view_sab_project_controlling_graph").arch_db.encode("utf-8"))

        self.assertTrue(list_arch.xpath("/list/field[@name='contribution_margin']"))
        self.assertTrue(list_arch.xpath("/list/field[@name='contribution_margin_percent']"))
        for measure in ("offer_amount", "actual_direct_cost", "contribution_margin", "actual_hours", "calculated_hours"):
            self.assertTrue(pivot_arch.xpath(f"/pivot/field[@name='{measure}'][@type='measure']"))
        for measure in ("offer_amount", "actual_direct_cost", "contribution_margin"):
            self.assertTrue(graph_arch.xpath(f"/graph/field[@name='{measure}'][@type='measure']"))

    def test_sale_portal_extension_inherits_odoo19_content_template(self):
        """The order line table lives in sale_order_portal_content in Odoo 19."""
        inherited = self.env.ref("sab_project.sab_sale_order_portal_calculation")
        parent = self.env.ref("sale.sale_order_portal_content")
        self.assertEqual(inherited.inherit_id, parent)
        arch = etree.fromstring(inherited.arch_db.encode("utf-8"))
        self.assertEqual(len(arch.xpath("//xpath[@expr=\"//table[@id='sales_order_table']\"]")), 2)

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
            ("sab_project.view_sab_purchase_requirement_form", "action_mark_ordered", "Als bestellt markieren"),
            ("sab_project.view_sab_purchase_requirement_form", "action_mark_received", "Als geliefert markieren"),
            ("sab_project.view_sab_production_order_form", "action_start", "Fertigung starten"),
            ("sab_project.view_sab_production_order_form", "action_mark_done", "Fertigungsauftrag abschließen"),
            ("sab_project.view_sab_employee_profile_form", "action_create_or_update_user", "Zugang anlegen / aktualisieren"),
            ("sab_project.view_sab_employee_profile_form", "action_send_invitation", "Einladung / Passwortlink senden"),
            ("sab_project.view_sab_employee_profile_form", "action_apply_permissions", "Rechte übernehmen"),
            ("sab_project.view_sab_employee_profile_form", "action_deactivate", "Mitarbeiter deaktivieren"),
            ("sab_project.view_sab_employee_profile_form", "action_activate", "Mitarbeiter aktivieren"),
            ("sab_project.view_sab_employee_step_form", "action_claim", "Arbeit übernehmen"),
            ("sab_project.view_sab_employee_step_form", "action_start", "Start / Fortsetzen"),
            ("sab_project.view_sab_employee_step_form", "action_pause", "Pause"),
            ("sab_project.view_sab_employee_step_form", "action_open_time_entry", "Zeit erfassen"),
            ("sab_project.view_sab_employee_step_form", "action_open_feedback", "Rückmeldung / Foto / Material"),
            ("sab_project.view_sab_employee_step_form", "action_done", "Fertig melden"),
            ("sab_project.view_sab_employee_time_entry_form", "action_confirm", "Zeit buchen"),
            ("sab_project.view_sab_project_document_form", "action_release", "Dokument intern freigeben"),
            ("sab_project.view_sab_project_document_form", "action_release_to_customer", "Für Kundenportal freigeben"),
            ("sab_project.view_sab_project_document_form", "action_withdraw_customer_release", "Kundenfreigabe zurückziehen"),
            ("sab_project.view_sab_project_document_form", "action_create_revision", "Neue Revision"),
            ("sab_project.view_sab_employee_feedback_form", "action_mark_processed", "Als bearbeitet markieren"),
            ("sab_project.view_sab_employee_feedback_form", "action_release_to_customer", "Foto für Kunden freigeben"),
            ("sab_project.view_sab_employee_feedback_form", "action_withdraw_customer_release", "Kundenfreigabe zurückziehen"),
            ("sab_project.view_sab_customer_status_form", "action_apply_suggestion", "Internen Stand übernehmen"),
            ("sab_project.view_sab_customer_status_form", "action_release", "Für Kunden freigeben"),
            ("sab_project.view_sab_customer_status_form", "action_withdraw", "Freigabe zurückziehen"),
            ("sab_project.view_sab_datanorm_import_form", "action_import", "DATANORM importieren"),
        )
        for view_xmlid, button_name, expected_label in expected:
            with self.subTest(view=view_xmlid, button=button_name):
                self._assert_button_label(view_xmlid, button_name, expected_label)
