"""Run with Odoo's TransactionCase; no live company data required."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabMontageTime(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({"name": "Montage Regression Kunde"})
        cls.project = cls.env["project.project"].create({
            "name": "Montage Regression", "partner_id": cls.customer.id,
        })
        cls.product = cls.env["sab.product"].create({
            "name": "Montage Regression Material", "price_mode": "fixed",
            "fixed_purchase_price": 10.0, "mechanical_time_minutes": 4.0,
        })

    def _item(self, minutes, with_material=True):
        values = {"name": "Artikel mit Montage", "quotation_text": "Artikel mit Montage",
                  "legacy_time_minutes": minutes,
                  "mechanical_factor": 98.0, "wiring_factor": 0.0, "testing_factor": 2.0}
        if with_material:
            values["product_line_ids"] = [(0, 0, {"product_id": self.product.id, "quantity": 1.0})]
        return self.env["sab.calculation.item"].create(values)

    def _quote(self, item, quantity=1.0, margin=1.0):
        return self.env["sale.order"].create({
            "partner_id": self.customer.id, "sab_project_id": self.project.id,
            "sab_calculation_source": "lv", "sab_hourly_rate": 94.95,
            "sab_material_factor": 1.0, "sab_aux_material_factor": 1.0,
            "sab_time_factor": 1.0, "sab_difficulty_factor": 1.0,
            "sab_packaging_factor": 1.0, "sab_skonto_factor": 1.0,
            "sab_margin_factor": margin, "sab_rebate_factor": 1.0,
            "sab_calculation_line_ids": [(0, 0, {
                "calculation_item_id": item.id, "quantity": quantity, "lv_position": "10",
            })],
        })

    def test_zero_minutes_adds_no_time_product(self):
        item = self._item(0)
        self.assertFalse(item.product_line_ids.filtered("is_auto_montage_time"))
        self.assertEqual(len(item.product_line_ids), 1)

    def test_positive_minutes_adds_exactly_one_minute_position(self):
        item = self._item(12.5)
        line = item.product_line_ids.filtered("is_auto_montage_time")
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.quantity, 12.5)
        self.assertEqual(line.unit, "min")
        self.assertEqual(line.odoo_product_id, self.env.ref("sab_project.product_montage_time_minute"))
        self.assertFalse(line.odoo_product_id.purchase_ok)
        self.assertEqual(line.odoo_product_id.uom_id, self.env.ref("uom.product_uom_minute"))
        self.assertAlmostEqual(line.purchase_total, 0)
        self.assertAlmostEqual(item.purchase_total, 10)

    def test_repeated_sync_updates_one_row_without_duplicates(self):
        item = self._item(10)
        original_id = item.product_line_ids.filtered("is_auto_montage_time").id
        item.write({"legacy_time_minutes": 20})
        item._sync_auto_montage_time()
        line = item.product_line_ids.filtered("is_auto_montage_time")
        self.assertEqual(line.id, original_id)
        self.assertAlmostEqual(line.quantity, 20)
        self.assertEqual(len(item.product_line_ids), 2)

    def test_zeroing_time_preserves_all_material_positions(self):
        item = self._item(12)
        material_id = item.product_line_ids.filtered(lambda row: not row.is_auto_montage_time).id
        item.legacy_time_minutes = 0
        self.assertFalse(item.product_line_ids.filtered("is_auto_montage_time"))
        self.assertEqual(item.product_line_ids.id, material_id)
        self.assertAlmostEqual(item.purchase_total, 10)

    def test_explicit_article_minutes_are_not_added_to_product_times(self):
        item = self._item(60)
        self.assertAlmostEqual(item.mechanical_time_minutes, 58.8)
        self.assertAlmostEqual(item.wiring_time_minutes, 0)
        self.assertAlmostEqual(item.testing_time_minutes, 1.2)
        self.assertAlmostEqual(item.total_time_minutes, 60)

    def test_one_hour_at_9495_with_material_and_no_extra_factors(self):
        order = self._quote(self._item(60))
        line = order.sab_calculation_line_ids
        self.assertAlmostEqual(line.unit_total_minutes, 60)
        self.assertAlmostEqual(line.total_hours, 1)
        self.assertAlmostEqual(line.unit_material_purchase, 10)
        self.assertAlmostEqual(line.unit_recommended_net_price, 104.95)
        self.assertEqual(len(line.component_snapshot_ids), 1)
        self.assertEqual(line.component_snapshot_ids.odoo_product_id, self.product.odoo_product_id)

    def test_fractional_minutes_are_not_rounded_to_158_per_minute(self):
        order = self._quote(self._item(0.125, with_material=False), quantity=480)
        line = order.sab_calculation_line_ids
        self.assertAlmostEqual(line.total_time_minutes, 60)
        self.assertAlmostEqual(line.recommended_net_price, 94.95)
        self.assertFalse(line.component_snapshot_ids)

    def test_existing_margin_applies_once_to_time_and_material(self):
        order = self._quote(self._item(60), quantity=2, margin=1.15)
        line = order.sab_calculation_line_ids
        self.assertAlmostEqual(line.recommended_net_price, (10 + 94.95) * 2 * 1.15)
        self.assertAlmostEqual(order.sab_offer_subtotal, line.recommended_net_price)

    def test_existing_offer_is_not_repriced_when_master_time_or_settings_change(self):
        item = self._item(60)
        order = self._quote(item)
        line = order.sab_calculation_line_ids
        old_price = line.unit_recommended_net_price
        order.action_sab_release_offer()
        item.legacy_time_minutes = 90
        self.env["ir.config_parameter"].sudo().set_param("sab_project.hourly_rate", "200")
        self.assertAlmostEqual(line.unit_total_minutes, 60)
        self.assertAlmostEqual(order.sab_hourly_rate, 94.95)
        self.assertAlmostEqual(line.unit_recommended_net_price, old_price)

    def test_item_copy_keeps_minutes_and_one_managed_row(self):
        item = self._item(25)
        copied = item.copy()
        self.assertAlmostEqual(copied.legacy_time_minutes, 25)
        self.assertEqual(len(copied.product_line_ids.filtered("is_auto_montage_time")), 1)
        self.assertEqual(len(copied.product_line_ids), 2)

    def test_invalid_time_is_rejected(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._item(-1)

    def test_upgrade_reconciliation_preserves_quote_and_material(self):
        item = self._item(30)
        order = self._quote(item)
        price = order.sab_calculation_line_ids.unit_recommended_net_price
        item._initialize_auto_montage_time()
        item._initialize_auto_montage_time()
        self.assertEqual(len(item.product_line_ids.filtered("is_auto_montage_time")), 1)
        self.assertAlmostEqual(order.sab_calculation_line_ids.unit_recommended_net_price, price)

    def test_legacy_helper_numbers_are_never_interpreted_as_time_percentages(self):
        item = self._item(30)
        item.write({"mechanical_factor": 2475, "wiring_factor": 3000, "testing_factor": 200})
        self.assertTrue(item.montage_time_allocation_missing)
        self.assertAlmostEqual(item.total_time_minutes, 30)
        self.assertAlmostEqual(item.mechanical_time_minutes, 0)
        self.assertAlmostEqual(item.wiring_time_minutes, 0)
        self.assertAlmostEqual(item.testing_time_minutes, 0)

    def test_missing_allocation_does_not_erase_original_minutes(self):
        item = self._item(3)
        item.write({"mechanical_factor": 0, "wiring_factor": 0, "testing_factor": 0})
        self.assertTrue(item.montage_time_allocation_missing)
        self.assertAlmostEqual(item.total_time_minutes, 3)
        self.assertAlmostEqual(item.product_line_ids.filtered("is_auto_montage_time").quantity, 3)

    def test_time_service_cannot_be_sold_as_zero_priced_direct_material(self):
        order = self._quote(self._item(0))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["sab.offer.calculation.line"].create({
                "order_id": order.id, "line_type": "item", "quantity": 1,
                "odoo_product_id": self.env.ref("sab_project.product_montage_time_minute").id,
            })
