from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabOfferCalculation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({"name": "Kunde Kalkulation"})
        cls.project = cls.env["project.project"].create({
            "name": "Testprojekt Angebotskalkulation",
            "partner_id": cls.partner.id,
        })
        cls.manufacturer = cls.env["sab.manufacturer"].create({
            "name": "Hersteller Angebotstest",
        })
        cls.supplier = cls.env["sab.supplier"].create({
            "name": "Lieferant Angebotstest",
        })
        cls.product = cls.env["sab.product"].create({
            "name": "Produkt Angebotstest",
            "manufacturer_id": cls.manufacturer.id,
            "manufacturer_article_number": "ANG-100",
            "space_units": 0.5,
            "mechanical_time_minutes": 2.0,
            "wiring_time_minutes": 3.0,
            "testing_time_minutes": 1.0,
        })
        cls.supplier_product = cls.env["sab.supplier.product"].create({
            "supplier_id": cls.supplier.id,
            "product_id": cls.product.id,
            "supplier_article_number": "L-ANG-100",
            "purchase_price": 10.0,
            "preferred": True,
        })
        cls.calculation_item = cls.env["sab.calculation.item"].create({
            "name": "Kalkulationsartikel Angebotstest",
            "quotation_text": "Kompletter Angebotsartikel",
            "product_line_ids": [(0, 0, {
                "product_id": cls.product.id,
                "quantity": 2.0,
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

    def test_offer_calculation_totals_and_guideline(self):
        order = self._order()

        self.assertAlmostEqual(order.sab_material_purchase_total, 60.0)
        self.assertAlmostEqual(order.sab_calculated_hours, 0.6)
        self.assertAlmostEqual(order.sab_mechanical_hours, 0.2)
        self.assertAlmostEqual(order.sab_wiring_hours, 0.3)
        self.assertAlmostEqual(order.sab_testing_hours, 0.1)
        self.assertAlmostEqual(order.sab_space_units, 3.0)

        # Defaultwerte aus der bereitgestellten SAB-P Altkalkulation:
        # Material 60 * 1.00 * 1.15 = 69 EUR
        # Lohn 0.6 h * 80 EUR * 1.25 = 60 EUR
        self.assertAlmostEqual(order.sab_material_cost, 69.0)
        self.assertAlmostEqual(order.sab_labor_cost, 60.0)
        self.assertAlmostEqual(order.sab_direct_cost, 129.0)
        self.assertAlmostEqual(order.sab_commercial_factor, 1.491890625)
        # Monetary-Felder werden von Odoo auf die Währungsgenauigkeit (EUR: 0,01) gerundet.
        self.assertAlmostEqual(order.sab_recommended_net_price, 192.45, places=2)

    def test_offer_uses_snapshot_not_live_master_data(self):
        order = self._order()
        original_material = order.sab_material_purchase_total
        original_hours = order.sab_calculated_hours

        # Stammdaten ändern sich später z. B. durch DATANORM oder Zeitpflege.
        self.supplier_product.purchase_price = 100.0
        self.product.mechanical_time_minutes = 20.0

        self.assertNotAlmostEqual(
            self.calculation_item.purchase_total,
            original_material / 3.0,
        )
        self.assertAlmostEqual(order.sab_material_purchase_total, original_material)
        self.assertAlmostEqual(order.sab_calculated_hours, original_hours)

    def test_global_factor_changes_do_not_change_existing_offer(self):
        order = self._order()
        old_factor = order.sab_hourly_rate
        old_guideline = order.sab_recommended_net_price

        self.env["ir.config_parameter"].sudo().set_param(
            "sab_project.hourly_rate", "125.0"
        )

        self.assertAlmostEqual(order.sab_hourly_rate, old_factor)
        self.assertAlmostEqual(order.sab_recommended_net_price, old_guideline)

        new_order = self._order()
        self.assertAlmostEqual(new_order.sab_hourly_rate, 125.0)

    def test_revision_gets_new_offer_number_and_copies_snapshot(self):
        order = self._order()
        action = order.action_create_sab_revision()
        revision = self.env["sale.order"].browse(action["res_id"])

        self.assertEqual(revision.sab_project_id, order.sab_project_id)
        self.assertEqual(revision.sab_revision_of_id, order)
        self.assertNotEqual(revision.sab_offer_reference, order.sab_offer_reference)
        self.assertEqual(len(revision.sab_calculation_line_ids), 1)
        self.assertAlmostEqual(
            revision.sab_material_purchase_total,
            order.sab_material_purchase_total,
        )
        self.assertAlmostEqual(
            revision.sab_recommended_net_price,
            order.sab_recommended_net_price,
        )

    def test_confirmed_offer_calculation_is_locked(self):
        order = self._order()
        line = order.sab_calculation_line_ids
        order.state = "sale"

        with self.assertRaises(ValidationError):
            line.write({"quantity": 4.0})
