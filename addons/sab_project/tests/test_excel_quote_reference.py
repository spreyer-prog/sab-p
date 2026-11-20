"""Synthetic examples only. Never publish uploaded customer files in Git."""
from dataclasses import replace
from decimal import Decimal
from odoo.tests.common import TransactionCase

from ..models.excel_quote_reference import QuoteFactors, calculate_quote_reference, dec


class TestExcelQuoteReference(TransactionCase):
    def factors(self):
        return QuoteFactors(
            material=dec('1.05'), material_discount=dec(1), auxiliary=dec('1.15'),
            terminal_material_deduction=dec(0), hourly_rate=dec('94.95'),
            time=dec(1), difficulty=dec(1), planning_hourly_rate=dec('94.95'),
            planning=dec(1), terminal_time_deduction=dec(0), metal=dec(1),
            packaging=dec('1.03'), transport=dec('1.03'), margin=dec('1.15'),
            sales=dec('1.10'), supplement=dec('1.10'), trade=(dec('1.25'),)*6,
        )

    def result(self, **changes):
        values=dict(factors=self.factors(), material_price=100, price_unit=1,
                    discount_factor='0.35', minutes=0, auxiliary=0)
        values.update(changes)
        return calculate_quote_reference(**values)

    def test_commercial_factor_adds_packaging_and_transport_first(self):
        self.assertEqual(self.factors().commercial, Decimal('1.34090'))
        self.assertNotEqual(self.factors().commercial, dec('1.03')*dec('1.03')*dec('1.15')*dec('1.10'))

    def test_rebate_multiplier_not_discount_percent(self):
        self.assertEqual(self.result()['net_material'], dec(35))
        self.assertEqual(self.result(discount_factor=None)['net_material'], dec(100))
        self.assertEqual(self.result(discount_factor=0)['net_material'], dec(0))

    def test_one_minute_uses_15825_not_158(self):
        self.assertEqual(self.result(minutes=1)['Z'], dec('1.5825'))
        self.assertEqual(self.result(minutes=60)['Z'], dec('94.95'))

    def test_trade_mode_uses_its_own_branch_not_normal_assembly_price(self):
        r=self.result(mode='H1', minutes=60)
        self.assertEqual(r['U'], dec('43.75'))
        self.assertNotEqual(r['U'], r['AC'])
        self.assertEqual(self.result(mode='h1', minutes=60)['U'], r['U'])

    def test_planning_suppression_and_optional_line(self):
        f=replace(self.factors(), planning=dec('1.15'))
        self.assertEqual(self.result(factors=f, mode='O', minutes=60)['AA'], dec(0))
        self.assertEqual(self.result(factors=f, mode='A', minutes=60)['V'], dec(0))

    def test_quantity_and_supplement_do_not_reprice_unit(self):
        r=self.result(quantity=3)
        self.assertEqual(r['V'],3*r['U'])
        self.assertEqual(self.result(supplement=True)['U'],r['AC']*dec('1.10'))

    def test_invalid_price_unit_is_not_silently_replaced(self):
        with self.assertRaises(ValueError):self.result(price_unit=0)
