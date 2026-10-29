from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestSabNumbering(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Testkunde"})

    def test_project_and_offer_numbering(self):
        project_1 = self.env["project.project"].create({"name": "Projekt Eins"})
        project_2 = self.env["project.project"].create({"name": "Projekt Zwei"})

        self.assertRegex(project_1.sab_project_reference, r"^A\d{2}\.\d{4}$")
        self.assertNotEqual(project_1.sab_project_reference, project_2.sab_project_reference)

        offer_1 = self.env["sale.order"].create({"partner_id": self.partner.id, "sab_project_id": project_1.id})
        offer_2 = self.env["sale.order"].create({"partner_id": self.partner.id, "sab_project_id": project_1.id})
        self.assertEqual(offer_1.name, f"{project_1.sab_project_reference}-01")
        self.assertEqual(offer_2.name, f"{project_1.sab_project_reference}-02")

    def test_project_number_resets_for_new_calendar_year(self):
        Project = self.env["project.project"]
        counter = self.env["sab.project.year.counter"].sudo()
        counter.search([("year", "in", [2026, 2027])]).unlink()

        with patch("odoo.fields.Date.context_today", return_value=date(2026, 12, 31)):
            project_2026_1 = Project.create({"name": "Jahresende 1"})
            project_2026_2 = Project.create({"name": "Jahresende 2"})

        with patch("odoo.fields.Date.context_today", return_value=date(2027, 1, 1)):
            project_2027_1 = Project.create({"name": "Jahresanfang 1"})
            project_2027_2 = Project.create({"name": "Jahresanfang 2"})

        self.assertEqual(project_2026_1.sab_project_reference, "A26.0001")
        self.assertEqual(project_2026_2.sab_project_reference, "A26.0002")
        self.assertEqual(project_2027_1.sab_project_reference, "A27.0001")
        self.assertEqual(project_2027_2.sab_project_reference, "A27.0002")
        self.assertEqual(counter.search([("year", "=", 2026)]).next_number, 3)
        self.assertEqual(counter.search([("year", "=", 2027)]).next_number, 3)

    def test_configurable_project_and_offer_number_format(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("sab_project.project_prefix", "P")
        params.set_param("sab_project.year_digits", "4")
        params.set_param("sab_project.project_separator", "/")
        params.set_param("sab_project.project_digits", "5")
        params.set_param("sab_project.project_start_number", "42")
        params.set_param("sab_project.offer_separator", ".")
        params.set_param("sab_project.offer_digits", "3")

        self.env["sab.project.year.counter"].sudo().search([("year", "=", 2028)]).unlink()
        with patch("odoo.fields.Date.context_today", return_value=date(2028, 1, 2)):
            project = self.env["project.project"].create({"name": "Konfiguriertes Projekt"})

        self.assertEqual(project.sab_project_reference, "P2028/00042")
        quotation = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": project.id,
        })
        self.assertEqual(quotation.sab_offer_reference, "P2028/00042.001")
        self.assertEqual(quotation.name, "P2028/00042.001")

    def test_project_status_default(self):
        project = self.env["project.project"].create({"name": "Statusprojekt"})
        self.assertEqual(project.sab_status, "offer_open")

    def test_default_bearbeiter_and_classification(self):
        project = self.env["project.project"].create({"name": "Bearbeiterprojekt"})
        self.assertEqual(project.user_id, self.env.user)
        self.assertEqual(project.sab_inquiry_type_id, self.env.ref("sab_project.sab_inquiry_type_electrician"))
        self.assertEqual(project.sab_technology_id, self.env.ref("sab_project.sab_technology_energy_distribution"))
        self.assertEqual(project.sab_service_type_id, self.env.ref("sab_project.sab_service_type_new_installation"))

    def test_offer_totals_are_summed(self):
        project = self.env["project.project"].create({"name": "Summenprojekt"})
        order_1 = self.env["sale.order"].create({"partner_id": self.partner.id, "sab_project_id": project.id})
        order_2 = self.env["sale.order"].create({"partner_id": self.partner.id, "sab_project_id": project.id})
        order_1.order_line = [(0, 0, {"name": "Pos 1", "product_uom_qty": 1, "price_unit": 1000.0})]
        order_2.order_line = [(0, 0, {"name": "Pos 2", "product_uom_qty": 1, "price_unit": 500.0})]
        project.invalidate_recordset(["sab_offer_amount", "sab_calculated_hours"])
        self.assertEqual(project.sab_offer_amount, 1500.0)

    def test_custom_classification_can_be_added(self):
        custom_type = self.env["sab.inquiry.type"].create({"name": "Industriekunde"})
        project = self.env["project.project"].create({"name": "Kundenprojekt", "sab_inquiry_type_id": custom_type.id})
        self.assertEqual(project.sab_inquiry_type_id, custom_type)

    def test_project_file_fields(self):
        project = self.env["project.project"].create({"name": "Projektakte", "sab_commission": "Campus", "sab_offer_identifier": "AV", "sab_customer_order_reference": "PO-1001", "sab_site_address": "Baustelle Köln"})
        self.assertEqual(project.sab_commission, "Campus")
        self.assertEqual(project.sab_offer_identifier, "AV")
        self.assertEqual(project.sab_customer_order_reference, "PO-1001")
        self.assertEqual(project.sab_site_address, "Baustelle Köln")

    def test_create_quotation_action_prefills_project_and_customer(self):
        project = self.env["project.project"].create({"name": "Angebotsprojekt", "partner_id": self.partner.id})
        action = project.action_create_sab_quotation()
        self.assertEqual(action["res_model"], "sale.order")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["context"]["default_sab_project_id"], project.id)
        self.assertEqual(action["context"]["default_partner_id"], self.partner.id)
        defaults = self.env["sale.order"].with_context(**action["context"]).default_get(["sab_project_id", "partner_id"])
        quotation = self.env["sale.order"].create(defaults)
        self.assertEqual(quotation.sab_project_id, project)
        self.assertEqual(quotation.partner_id, self.partner)
        self.assertEqual(quotation.sab_offer_reference, f"{project.sab_project_reference}-01")
        self.assertEqual(project.sab_sale_order_count, 1)

    def test_legacy_project_gets_number_on_first_sab_use(self):
        project = self.env["project.project"].create({"name": "Altprojekt", "partner_id": self.partner.id})
        self.env.cr.execute("UPDATE project_project SET sab_project_reference = NULL WHERE id = %s", [project.id])
        project.invalidate_recordset(["sab_project_reference"])
        self.assertFalse(project.sab_project_reference)
        project.action_create_sab_quotation()
        self.assertRegex(project.sab_project_reference, r"^A\d{2}\.\d{4}$")

    def test_project_number_is_forced_visible_in_both_lists(self):
        sab_view = self.env.ref("sab_project.sab_project_overview_list")
        standard_inherit = self.env.ref("sab_project.sab_standard_project_list_inherit")
        self.assertIn('name="sab_project_reference"', sab_view.arch_db)
        self.assertNotIn('name="sab_project_reference" string="Projekt-Nr." optional="hide"', sab_view.arch_db)
        self.assertIn('name="sab_project_reference"', standard_inherit.arch_db)
        self.assertEqual(standard_inherit.inherit_id, self.env.ref("project.view_project"))
