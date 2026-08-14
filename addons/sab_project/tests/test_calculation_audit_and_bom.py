from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabCalculationAuditAndBom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Stückliste"})
        cls.project = cls.env["project.project"].create({
            "name": "Projekt Stückliste",
            "partner_id": cls.partner.id,
        })
        cls.manufacturer = cls.env["sab.manufacturer"].create({"name": "Hersteller Stückliste"})
        cls.supplier = cls.env["sab.supplier"].create({"name": "Lieferant Stückliste"})
        cls.product = cls.env["sab.product"].create({
            "name": "Stücklistenprodukt",
            "manufacturer_id": cls.manufacturer.id,
            "manufacturer_article_number": "BOM-100",
            "mechanical_time_minutes": 1.0,
        })
        cls.supplier_product = cls.env["sab.supplier.product"].create({
            "supplier_id": cls.supplier.id,
            "product_id": cls.product.id,
            "supplier_article_number": "SUP-BOM-100",
            "purchase_price": 5.0,
            "preferred": True,
        })
        cls.calculation_item = cls.env["sab.calculation.item"].create({
            "name": "Kalkulationsartikel Stückliste",
            "quotation_text": "Stücklistenartikel",
            "product_line_ids": [(0, 0, {
                "product_id": cls.product.id,
                "quantity": 2.0,
                "unit": "pcs",
            })],
        })

    def _order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": self.project.id,
            "sab_calculation_line_ids": [(0, 0, {
                "calculation_item_id": self.calculation_item.id,
                "quantity": 3.0,
            })],
        })

    def test_component_snapshot_is_stable(self):
        order = self._order()
        calc_line = order.sab_calculation_line_ids
        self.assertEqual(len(calc_line.component_snapshot_ids), 1)
        self.assertAlmostEqual(calc_line.component_snapshot_ids.quantity_per_unit, 2.0)

        source_line = self.calculation_item.product_line_ids
        source_line.quantity = 9.0
        self.assertAlmostEqual(calc_line.component_snapshot_ids.quantity_per_unit, 2.0)

    def test_confirmed_order_generates_bom_from_snapshot(self):
        order = self._order()
        order.state = "sale"
        action = order.action_generate_sab_bom()
        bom = self.env["sab.project.bom"].browse(action["res_id"])

        self.assertEqual(bom.order_id, order)
        self.assertEqual(bom.project_id, self.project)
        self.assertEqual(len(bom.line_ids), 1)
        self.assertEqual(bom.line_ids.product_id, self.product)
        self.assertAlmostEqual(bom.line_ids.quantity, 6.0)
        self.assertAlmostEqual(bom.line_ids.unit_purchase_price, 5.0)
        self.assertAlmostEqual(bom.line_ids.purchase_total, 30.0)

        bom.action_release()
        with self.assertRaises(ValidationError):
            bom.line_ids.write({"quantity": 7.0})

    def test_calculation_setting_requires_code_and_creates_log(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("sab_project.calculation_change_code", "1111")
        params.set_param("sab_project.material_factor", "1.0")

        settings = self.env["res.config.settings"].create({
            "sab_material_factor": 1.2,
            "sab_calculation_change_code": "1111",
        })
        with self.assertRaises(ValidationError):
            settings.set_values()

        settings.sab_calculation_change_code_confirm = "1111"
        settings.set_values()
        self.assertAlmostEqual(float(params.get_param("sab_project.material_factor")), 1.2)

        log = self.env["sab.calculation.change.log"].search([
            ("parameter_key", "=", "sab_project.material_factor"),
        ], order="id desc", limit=1)
        self.assertTrue(log)
        self.assertEqual(log.old_value, "1.0")
        self.assertEqual(log.new_value, "1.2")
