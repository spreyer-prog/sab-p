from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabOfferUnitRounding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Unit rounding test customer"})
        cls.project = cls.env["project.project"].create({
            "name": "Unit rounding test project", "partner_id": cls.partner.id,
        })
        cls.item = cls.env["sab.calculation.item"].create({
            "name": "Test 30 minutes", "quotation_text": "Test 30 minutes",
            "legacy_time_minutes": 30.0, "mechanical_factor": 100.0,
            "wiring_factor": 0.0, "testing_factor": 0.0,
        })

    def _quote(self, quantity=1.0, policy=None, **overrides):
        values = {
            "partner_id": self.partner.id, "sab_project_id": self.project.id,
            "sab_calculation_source": "lv", "currency_id": self.env.ref("base.EUR").id,
            "sab_hourly_rate": 80.0, "sab_material_factor": 1.0,
            "sab_aux_material_factor": 1.15, "sab_time_factor": 1.25,
            "sab_difficulty_factor": 1.0, "sab_packaging_factor": 1.03,
            "sab_skonto_factor": 1.03, "sab_margin_factor": 1.35,
            "sab_rebate_factor": 1.125, "sab_vat_rate": 19.0,
            "sab_object_discount_percent": 0.0, "sab_transport_cost": 0.0,
            "sab_calculation_line_ids": [(0, 0, {
                "calculation_item_id": self.item.id, "quantity": quantity,
                "lv_position": "1.1.1",
            })],
        }
        if policy:
            values["sab_price_rounding_version"] = policy
        values.update(overrides)
        return self.env["sale.order"].create(values)

    def test_new_project_uses_unit_first(self):
        order = self._quote()
        self.assertEqual(order.sab_price_rounding_version, "unit_v1")
        self.assertEqual(order.sab_calculation_line_ids.unit_recommended_net_price, 80.56)
        self.assertEqual(order.sab_calculation_line_ids.recommended_net_price, 80.56)
        self.assertEqual(order.sab_hourly_rate, 80.0)

    def test_quantity_three_is_24168_not_24169(self):
        order = self._quote()
        line = order.sab_calculation_line_ids
        line.quantity = 3
        self.assertEqual(line.unit_recommended_net_price, 80.56)
        self.assertEqual(line.recommended_net_price, 241.68)
        self.assertEqual(line.total_time_minutes, 90.0)
        self.assertEqual(order.sab_offer_subtotal, 241.68)
        self.assertEqual(order.sab_recommended_net_price, 241.68)
        self.assertEqual(order.sab_offer_net_total, 241.68)
        self.assertEqual(order.sab_offer_vat_total, 45.92)
        self.assertEqual(order.sab_offer_gross_total, 287.60)
        generated = order.order_line.filtered("sab_generated_from_calculation")
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated.price_unit, 80.56)
        self.assertEqual(generated.product_uom_qty, 3)

    def test_quantity_roundtrip_and_zero_do_not_recalculate_unit_from_total(self):
        order = self._quote()
        line = order.sab_calculation_line_ids
        for quantity in (3, 1, 0, 3.5, 0.25, 20, 1):
            line.quantity = quantity
            self.assertEqual(line.unit_recommended_net_price, 80.56)
            self.assertEqual(line.recommended_net_price, order.currency_id.round(80.56 * quantity))

    def test_legacy_recomputation_keeps_historical_amounts(self):
        order = self._quote(3, policy="legacy")
        line = order.sab_calculation_line_ids
        self.assertEqual(line.unit_recommended_net_price, 80.56)
        self.assertEqual(line.recommended_net_price, 241.69)
        line._compute_price()
        self.assertEqual(line.unit_recommended_net_price, 80.56)
        self.assertEqual(line.recommended_net_price, 241.69)

    def test_both_legacy_and_new_families_retain_policy_in_copies_and_suboffers(self):
        for policy in ("legacy", "unit_v1"):
            project = self.env["project.project"].create({
                "name": "Rounding family " + policy, "partner_id": self.partner.id,
            })
            order = self._quote(3, policy=policy, sab_project_id=project.id)
            original_price = order.sab_calculation_line_ids.unit_recommended_net_price
            original_total = order.sab_calculation_line_ids.recommended_net_price
            copy = self.env["sale.order"].browse(order.action_create_sab_revision()["res_id"])
            child = self.env["sale.order"].browse(order.action_sab_create_suboffer()["res_id"])
            self.assertEqual(copy.sab_price_rounding_version, policy)
            self.assertEqual(child.sab_price_rounding_version, policy)
            self.assertEqual(copy.sab_calculation_line_ids.unit_recommended_net_price, original_price)
            self.assertEqual(copy.sab_calculation_line_ids.recommended_net_price, original_total)
            self.assertEqual(order.sab_calculation_line_ids.recommended_net_price, original_total)

    def test_new_suboffer_via_project_respects_legacy_family(self):
        old = self._quote(policy="legacy")
        child = self._quote(3)
        self.assertEqual(child.sab_price_rounding_version, old.sab_price_rounding_version)
        self.assertEqual(child.sab_calculation_line_ids.recommended_net_price, 241.69)

    def test_mixed_rounding_in_same_project_is_rejected(self):
        self._quote(policy="legacy")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._quote(policy="unit_v1")

    def test_policy_changes_are_rejected_including_released_offer(self):
        order = self._quote()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.write({"sab_price_rounding_version": "legacy"})
        order.action_sab_release_offer()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.with_context(sab_offer_release_write=True).write({"sab_price_rounding_version": "legacy"})

    def test_global_rate_and_master_changes_do_not_reprice_existing_quote(self):
        order = self._quote(3)
        old_price = order.sab_calculation_line_ids.unit_recommended_net_price
        self.item.legacy_time_minutes = 90
        self.env["ir.config_parameter"].sudo().set_param("sab_project.hourly_rate", "94.95")
        self.assertEqual(order.sab_hourly_rate, 80.0)
        self.assertEqual(order.sab_calculation_line_ids.unit_total_minutes, 30.0)
        self.assertEqual(order.sab_calculation_line_ids.unit_recommended_net_price, old_price)
        self.assertEqual(order.sab_calculation_line_ids.recommended_net_price, 241.68)

    def test_one_hour_base_80_is_not_replaced_with_sales_rate(self):
        self.item.legacy_time_minutes = 60
        order = self._quote(1, sab_time_factor=1, sab_packaging_factor=1,
                            sab_skonto_factor=1, sab_margin_factor=1, sab_rebate_factor=1)
        self.assertEqual(order.sab_calculation_line_ids.unit_recommended_net_price, 80.0)
        self.assertEqual(order.sab_labor_cost, 80.0)

    def test_fractional_minutes_are_precise_before_unit_selling_price_rounding(self):
        self.item.legacy_time_minutes = 0.125
        order = self._quote(480, sab_hourly_rate=94.95, sab_time_factor=1,
                            sab_packaging_factor=1, sab_skonto_factor=1,
                            sab_margin_factor=1, sab_rebate_factor=1)
        line = order.sab_calculation_line_ids
        self.assertEqual(line.unit_total_minutes, 0.125)
        self.assertEqual(line.total_time_minutes, 60)
        self.assertEqual(order.sab_labor_cost, 94.95)
        # 480 separately priced units, not one sale of a whole hour.
        self.assertEqual(line.unit_recommended_net_price, 0.20)
        self.assertEqual(line.recommended_net_price, 96.0)

    def test_margin_and_material_are_applied_once(self):
        self.item.legacy_time_minutes = 60
        order = self._quote(2, sab_hourly_rate=94.95, sab_time_factor=1,
                            sab_packaging_factor=1, sab_skonto_factor=1,
                            sab_margin_factor=1.15, sab_rebate_factor=1)
        line = order.sab_calculation_line_ids
        line.unit_material_purchase = 10.0
        self.assertEqual(line.unit_recommended_net_price, 120.69)
        self.assertEqual(line.recommended_net_price, 241.38)
        self.assertEqual(order.sab_labor_cost, 189.90)
