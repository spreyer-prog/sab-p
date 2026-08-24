from odoo.tests.common import TransactionCase


class TestSabCalculationCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.manufacturer = cls.env["sab.manufacturer"].create({
            "name": "ABB Test",
        })
        cls.supplier_a = cls.env["sab.supplier"].create({
            "name": "Lieferant A",
        })
        cls.supplier_b = cls.env["sab.supplier"].create({
            "name": "Lieferant B",
        })
        cls.product = cls.env["sab.product"].create({
            "name": "S201-B16 Test",
            "manufacturer_id": cls.manufacturer.id,
            "manufacturer_article_number": "S201-B16",
            "space_units": 0.5,
            "mechanical_time_minutes": 2.0,
            "wiring_time_minutes": 3.0,
            "testing_time_minutes": 1.0,
        })

    def test_supplier_net_price(self):
        supplier_product = self.env["sab.supplier.product"].create({
            "supplier_id": self.supplier_a.id,
            "product_id": self.product.id,
            "supplier_article_number": "A-100",
            "purchase_price": 10.0,
            "discount_percent": 20.0,
        })
        self.assertAlmostEqual(supplier_product.net_purchase_price, 8.0)

    def test_preferred_supplier_wins(self):
        self.env["sab.supplier.product"].create({
            "supplier_id": self.supplier_a.id,
            "product_id": self.product.id,
            "supplier_article_number": "A-100",
            "purchase_price": 10.0,
            "discount_percent": 0.0,
        })
        preferred = self.env["sab.supplier.product"].create({
            "supplier_id": self.supplier_b.id,
            "product_id": self.product.id,
            "supplier_article_number": "B-100",
            "purchase_price": 12.0,
            "discount_percent": 0.0,
            "preferred": True,
        })

        line = self.env["sab.calculation.item.line"].new({
            "product_id": self.product.id,
            "quantity": 2.0,
        })
        line._compute_purchase_values()

        self.assertEqual(line.selected_supplier_product_id, preferred)
        self.assertAlmostEqual(line.unit_purchase_price, 12.0)
        self.assertAlmostEqual(line.purchase_total, 24.0)

    def test_calculation_factors_and_purchase_total(self):
        self.env["sab.supplier.product"].create({
            "supplier_id": self.supplier_a.id,
            "product_id": self.product.id,
            "supplier_article_number": "A-200",
            "purchase_price": 10.0,
            "discount_percent": 20.0,
            "preferred": True,
        })

        item = self.env["sab.calculation.item"].create({
            "name": "Test Kalkulationsartikel",
            "quotation_text": "Test",
            "mechanical_factor": 50.0,
            "wiring_factor": 100.0,
            "testing_factor": 200.0,
            "space_factor": 1.5,
            "product_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 2.0,
            })],
        })

        self.assertAlmostEqual(item.space_units, 1.5)
        self.assertAlmostEqual(item.mechanical_time_minutes, 2.0)
        self.assertAlmostEqual(item.wiring_time_minutes, 6.0)
        self.assertAlmostEqual(item.testing_time_minutes, 4.0)
        self.assertAlmostEqual(item.total_time_minutes, 12.0)
        self.assertAlmostEqual(item.purchase_total, 16.0)

    def test_product_variant_bridge_is_searchable(self):
        template = self.product.odoo_product_id.product_tmpl_id
        found = self.env["product.template"].search([
            ("product_variant_id", "=", self.product.odoo_product_id.id),
        ])
        self.assertIn(template, found)
