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

        offer_1 = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": project_1.id,
        })
        offer_2 = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": project_1.id,
        })

        self.assertEqual(offer_1.name, f"{project_1.sab_project_reference}-01")
        self.assertEqual(offer_2.name, f"{project_1.sab_project_reference}-02")

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
        project = self.env["project.project"].create({
            "name": "Projektakte",
            "sab_commission": "Campus",
            "sab_offer_identifier": "AV",
            "sab_customer_order_reference": "PO-1001",
            "sab_site_address": "Baustelle Köln",
        })
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

        # Odoo wendet default_* beim Öffnen der Formularansicht via default_get an.
        # Im Unit-Test bilden wir diesen Formularweg explizit nach.
        defaults = self.env["sale.order"].with_context(**action["context"]).default_get([
            "sab_project_id", "partner_id"
        ])
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
