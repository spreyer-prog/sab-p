from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabOfferReuseLibrary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Wiederverwendung"})
        cls.project = cls.env["project.project"].create(
            {"name": "Projekt Wiederverwendung", "partner_id": cls.partner.id}
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "Leistungsschalter Wiederverwendung",
                "manufacturer_article_number": "REUSE-100",
                "price_mode": "fixed",
                "fixed_purchase_price": 25.0,
            }
        )
        cls.calculation_item = cls.env["sab.calculation.item"].create(
            {
                "name": "Abgang Wiederverwendung",
                "quotation_text": "Abgang mit Leistungsschalter",
                "product_line_ids": [
                    (
                        0,
                        0,
                        {
                            "position_type": "normal",
                            "product_id": cls.product.id,
                            "quantity": 1.0,
                        },
                    )
                ],
            }
        )
        cls.first_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "lv",
            }
        )
        cls.source_section = cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.first_order.id,
                "line_type": "section",
                "description": "Bauteil Einspeisung",
                "lv_position": "01.01",
                "sequence": 10,
            }
        )
        cls.source_item = cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.first_order.id,
                "calculation_item_id": cls.calculation_item.id,
                "quantity": 2.0,
                "description": "Einspeisung komplett",
                "lv_position": "01.01.03",
                "sequence": 20,
            }
        )
        cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.first_order.id,
                "line_type": "section_end",
                "sequence": 30,
            }
        )
        cls.first_order.sab_calculation_line_ids._normalize_section_membership()
        cls.second_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "lv",
            }
        )

    def test_panel_payload_lists_project_lv_positions_and_components(self):
        payload = self.second_order.sab_offer_reuse_payload()
        self.assertTrue(payload["editable"])
        self.assertEqual(payload["project"], self.project.display_name)
        self.assertIn("01.01.03", [item["position"] for item in payload["lv_positions"]])
        source_components = [
            item for item in payload["project_components"] if item["id"] == self.source_section.id
        ]
        self.assertEqual(len(source_components), 1)
        self.assertIn("01.01", source_components[0]["positions"])
        self.assertIn("01.01.03", source_components[0]["positions"])
        self.assertEqual(source_components[0]["line_count"], 1)

    def test_single_lv_position_can_be_added_from_panel(self):
        mapping = self.env["sab.project.lv.mapping"].search(
            [
                ("project_id", "=", self.project.id),
                ("calculation_item_id", "=", self.calculation_item.id),
            ],
            limit=1,
        )
        result = self.second_order.sab_offer_add_reuse_entry("lv", mapping.id)
        self.assertIn("01.01.03", result["message"])
        added = self.second_order.sab_calculation_line_ids.filtered(
            lambda line: line.line_type == "item"
        )
        self.assertEqual(len(added), 1)
        self.assertEqual(added.calculation_item_id, self.calculation_item)
        self.assertEqual(added.lv_position, "01.01.03")
        self.assertTrue(added.lv_position_locked)

    def test_complete_project_component_is_copied_with_project_positions(self):
        result = self.second_order.sab_offer_add_reuse_entry(
            "project_component", self.source_section.id
        )
        self.assertIn("vollständig übernommen", result["message"])
        copied_section = self.second_order.sab_calculation_line_ids.filtered(
            lambda line: line.line_type == "section"
        )
        copied_item = self.second_order.sab_calculation_line_ids.filtered(
            lambda line: line.line_type == "item"
        )
        self.assertEqual(len(copied_section), 1)
        self.assertEqual(copied_section.description, "Bauteil Einspeisung")
        self.assertEqual(copied_section.lv_position, "01.01")
        self.assertEqual(len(copied_item), 1)
        self.assertEqual(copied_item.parent_section_id, copied_section)
        self.assertEqual(copied_item.lv_position, "01.01.03")
        self.assertAlmostEqual(copied_item.quantity, 2.0)

    def test_component_can_be_saved_to_database_without_lv_and_reused(self):
        result = self.second_order.sab_offer_save_component_template(self.source_section.id)
        template = self.env["sab.calculation.component.template"].browse(
            result["template_id"]
        )
        self.assertEqual(template.name, "Bauteil Einspeisung")
        self.assertEqual(template.source_section_line_id, self.source_section)
        self.assertEqual(len(template.line_ids), 1)
        self.assertEqual(template.line_ids.calculation_item_id, self.calculation_item)
        self.assertAlmostEqual(template.line_ids.quantity, 2.0)
        self.assertNotIn("lv_position", template._fields)
        self.assertNotIn("lv_position", template.line_ids._fields)
        self.assertNotIn("schematic_reference", template.line_ids._fields)

        second_result = self.second_order.sab_offer_save_component_template(
            self.source_section.id
        )
        self.assertEqual(second_result["template_id"], template.id)
        self.assertEqual(
            self.env["sab.calculation.component.template"].search_count(
                [("source_section_line_id", "=", self.source_section.id)]
            ),
            1,
        )

        self.second_order.sab_offer_add_reuse_entry("library_component", template.id)
        inserted_section = self.second_order.sab_calculation_line_ids.filtered(
            lambda line: line.line_type == "section"
        )
        inserted_item = self.second_order.sab_calculation_line_ids.filtered(
            lambda line: line.line_type == "item"
        )
        self.assertFalse(inserted_section.lv_position)
        self.assertEqual(inserted_item.lv_position, "01.01.03")
        self.assertEqual(inserted_item.parent_section_id, inserted_section)

    def test_form_contains_right_side_reuse_widget(self):
        view = self.env.ref("sab_project.sab_sale_order_form_reuse_panel")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        widgets = arch.xpath("//xpath[@expr='//chatter']/widget[@name='sab_offer_reuse_panel']")
        self.assertEqual(len(widgets), 1)
