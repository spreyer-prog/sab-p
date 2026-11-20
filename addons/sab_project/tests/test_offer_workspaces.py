from lxml import etree

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabOfferCalculationWorkspaces(TransactionCase):
    """One commercial record, two workspaces; no data deletion or extra totals."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "UI Testkunde"})
        cls.project = cls.env["project.project"].create({
            "name": "UI Angebotsprojekt", "partner_id": cls.partner.id,
        })
        cls.product = cls.env["sab.product"].create({
            "name": "UI Material", "price_mode": "fixed", "fixed_purchase_price": 12.0,
        })
        cls.article = cls.env["sab.calculation.item"].create({
            "name": "UI Kalkulationsartikel", "quotation_text": "UI Artikel komplett",
            "product_line_ids": [(0, 0, {"product_id": cls.product.id, "quantity": 1.0})],
        })

    def _order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": self.project.id,
            "sab_calculation_source": "lv",
            "sab_material_factor": 1.05,
            "sab_aux_material_factor": 1.0,
            "sab_hourly_rate": 94.95,
            "sab_time_factor": 1.0,
            "sab_difficulty_factor": 1.0,
            "sab_packaging_factor": 1.0,
            "sab_skonto_factor": 1.0,
            "sab_margin_factor": 1.15,
            "sab_rebate_factor": 1.0,
        })

    def _add_material(self, order):
        order.write({"sab_material_calculation_line_ids": [(0, 0, {
            "line_type": "item",
            "odoo_product_id": self.product.odoo_product_id.id,
            "quantity": 2.0,
            "lv_position": "20",
            "schematic_reference": "PLAN-1",
        })]})
        return order.sab_material_calculation_line_ids

    def _combined_arch(self):
        result = self.env["sale.order"].get_view(
            view_id=self.env.ref("sale.view_order_form").id, view_type="form",
        )
        return etree.fromstring(result["arch"].encode())

    def test_material_workspace_keeps_one_canonical_record_and_total(self):
        order = self._order()
        self.env["sab.offer.calculation.line"].create({
            "order_id": order.id, "calculation_item_id": self.article.id,
            "quantity": 1.0, "lv_position": "10",
        })
        line = self._add_material(order)
        self.assertEqual(len(line), 1)
        self.assertEqual(len(order.sab_calculation_line_ids), 2)
        self.assertIn(line, order.sab_calculation_line_ids)
        self.assertAlmostEqual(
            order.sab_offer_subtotal,
            sum(order.sab_calculation_line_ids.mapped("recommended_net_price")),
        )
        self.assertAlmostEqual(line.material_purchase_total, 24.0)
        line.quantity = 3.0
        self.assertAlmostEqual(line.material_purchase_total, 36.0)
        self.assertEqual(len(order.sab_calculation_line_ids), 2)

    def test_copy_does_not_duplicate_filtered_material_lines(self):
        order = self._order()
        source = self._add_material(order)
        original_price = source.unit_recommended_net_price
        action = order.action_create_sab_revision()
        revision = self.env["sale.order"].browse(action["res_id"])
        self.assertEqual(len(revision.sab_calculation_line_ids), 1)
        self.assertEqual(len(revision.sab_material_calculation_line_ids), 1)
        self.assertNotEqual(revision.sab_material_calculation_line_ids.id, source.id)
        self.assertAlmostEqual(
            revision.sab_material_calculation_line_ids.unit_recommended_net_price,
            original_price,
        )
        self.assertAlmostEqual(source.unit_recommended_net_price, original_price)

    def test_new_suboffer_is_empty_and_copies_commercial_header_not_global_defaults(self):
        order = self._order()
        line = self._add_material(order)
        order.action_sab_release_offer()
        price_before = line.unit_recommended_net_price
        source_reference = order.sab_offer_reference
        self.env["ir.config_parameter"].sudo().set_param("sab_project.material_factor", "8.0")
        self.env["ir.config_parameter"].sudo().set_param("sab_project.hourly_rate", "200.0")
        action = order.action_sab_create_suboffer()
        created = self.env["sale.order"].browse(action["res_id"])
        self.assertEqual(created.sab_project_id, order.sab_project_id)
        self.assertEqual(created.partner_id, order.partner_id)
        self.assertNotEqual(created.sab_offer_reference, source_reference)
        self.assertFalse(created.sab_revision_of_id)
        self.assertFalse(created.order_line)
        self.assertFalse(created.sab_calculation_line_ids)
        self.assertFalse(created.sab_material_calculation_line_ids)
        self.assertFalse(created.sab_calculation_group_ids)
        self.assertEqual(created.state, "draft")
        self.assertEqual(created.sab_offer_release_state, "draft")
        self.assertAlmostEqual(created.sab_material_factor, order.sab_material_factor)
        self.assertAlmostEqual(created.sab_hourly_rate, 94.95)
        self.assertAlmostEqual(created.sab_margin_factor, order.sab_margin_factor)
        self.assertEqual(order.sab_offer_reference, source_reference)
        self.assertEqual(order.sab_offer_release_state, "released")
        self.assertAlmostEqual(line.unit_recommended_net_price, price_before)

    def test_material_workspace_does_not_bypass_release_or_lv_checks(self):
        order = self._order()
        line = self._add_material(order)
        line.lv_position = False
        with self.assertRaises(ValidationError):
            order.action_sab_release_offer()
        line.lv_position = "20"
        order.action_sab_release_offer()
        with self.assertRaises(ValidationError):
            line.quantity = 4.0
        with self.assertRaises(ValidationError):
            self._add_material(order)

    def test_basis_switch_does_not_clear_hidden_product_or_schematic_value(self):
        order = self._order()
        line = self._add_material(order)
        original_id = line.id
        original_price = line.unit_recommended_net_price
        order.sab_calculation_source = "schematic"
        order.sab_calculation_source = "lv"
        self.assertEqual(line.id, original_id)
        self.assertEqual(line.odoo_product_id, self.product.odoo_product_id)
        self.assertEqual(line.schematic_reference, "PLAN-1")
        self.assertAlmostEqual(line.unit_recommended_net_price, original_price)

    def test_compiled_view_has_conditional_columns_and_separate_material_tab(self):
        arch = self._combined_arch()
        pages = arch.xpath("//sheet/notebook/page")
        names = [page.get("name") for page in pages]
        self.assertEqual(names[0], "sab_calculation")
        self.assertEqual(names[1], "sab_material_calculation")
        calc = arch.xpath("//page[@name='sab_calculation']")[0]
        schematic = calc.xpath(".//field[@name='schematic_reference']")[0]
        product = calc.xpath(".//field[@name='odoo_product_id']")[0]
        self.assertEqual(schematic.get("column_invisible"), "parent.sab_calculation_source != 'schematic'")
        self.assertEqual(product.get("column_invisible"), "parent.sab_calculation_source == 'lv'")
        material = arch.xpath("//page[@name='sab_material_calculation']")[0]
        for hidden in ("lv_position", "schematic_reference", "is_ntg", "calculation_item_id"):
            self.assertFalse(material.xpath(".//field[@name='%s']" % hidden))
        self.assertTrue(material.xpath(".//field[@name='odoo_product_id'][@required='1']"))
        material_field = material.xpath(".//field[@name='sab_material_calculation_line_ids']")[0]
        self.assertIn("sab_offer_release_state", material_field.get("readonly"))
        copy = arch.xpath("//header/button[@name='action_create_sab_revision']")[0]
        self.assertEqual(copy.get("string"), "Angebot kopieren / bearbeiten")
        new = arch.xpath("//header/button[@name='action_sab_create_suboffer']")
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].get("string"), "Neues Angebot erstellen")
