"""Actual pure arithmetic/allocation tests. These are not Odoo integration tests."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('material_logic', ROOT/'models/sab_material_logic.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def row(id=1, qty=6, price=10, cabinet=1, product=10, lv='1.1.1', **kw):
    return dict(id=id, source_id=id, odoo_product_id=product, product_id=False,
                quantity=qty, unit_purchase_price=price, unit='pcs', optional=False,
                cabinet_id=cabinet, cabinet=f'UV{cabinet}', lv=lv, **kw)

class TestMaterialArithmetic(unittest.TestCase):
    def test_unchanged_material(self):
        self.assertEqual(m.comparison([row()], [row()])['delta'], 0)
    def test_quantity_difference(self):
        v=m.comparison([row()], [row(qty=9)])
        self.assertEqual((v['base'],v['current'],v['delta'],v['percent']),(60,90,30,50))
    def test_substitution_difference(self):
        v=m.comparison([row()], [row(product=11,price=17)])
        self.assertEqual((v['base'],v['current'],v['delta']),(60,102,42))
    def test_combined_two_cabinets(self):
        self.assertEqual(m.totals([row(),row(id=2,cabinet=2)])['normal'],120)
    def test_optional_not_in_normal(self):
        r=row();r['optional']=True
        self.assertEqual(m.totals([row(),r]),{'normal':60,'optional':60,'zero_prices':0})
    def test_removed_not_in_current(self):
        self.assertEqual(m.totals([row(removed=True)])['normal'],0)
    def test_zero_price_warning(self):
        self.assertEqual(m.totals([row(price=0)])['zero_prices'],1)
    def test_optional_zero_not_warned_as_mandatory(self):
        r=row(price=0);r['optional']=True
        self.assertEqual(m.totals([r])['zero_prices'],0)
    def test_unknown_historical_baseline_not_invented(self):
        v=m.comparison([], [row()],False)
        self.assertIsNone(v['base']);self.assertIsNone(v['delta']);self.assertIsNone(v['percent'])
    def test_zero_baseline_no_divide_by_zero(self):
        v=m.comparison([row(price=0)],[row()])
        self.assertEqual(v['delta'],60);self.assertIsNone(v['percent'])
    def test_fractional_unit_price_not_rounded_early(self):
        self.assertEqual(m.totals([row(qty=1000,price=.3333)])['normal'],333.3)
    def test_data_is_not_mutated(self):
        data=[row(),row(id=2,cabinet=2)];old=copy.deepcopy(data)
        m.aggregate(data);m.comparison(data,data);m.fingerprint(data)
        self.assertEqual(data,old)
    def test_no_labour_or_margin_formula_in_cost(self):
        r=row();r.update(hourly_rate=80,margin_factor=1.35,tax=19)
        self.assertEqual(m.totals([r])['normal'],60)
    def test_nan_is_rejected(self):
        with self.assertRaises(ValueError):m.totals([row(qty=float('nan'))])
    def test_infinite_price_is_rejected(self):
        with self.assertRaises(ValueError):m.totals([row(price=float('inf'))])
    def test_negative_price_is_rejected(self):
        with self.assertRaises(ValueError):m.totals([row(price=-1)])
    def test_grouping_yields_one_product(self):
        v=m.aggregate([row(),row(id=2,cabinet=2)])
        self.assertEqual(len(v),1);self.assertEqual(v[0]['quantity'],12)
    def test_all_cabinet_allocations_visible(self):
        v=m.aggregate([row(),row(id=2,cabinet=2,qty=8)])
        self.assertEqual(v[0]['allocation_text'],'UV1: 6 [LV 1.1.1]; UV2: 8 [LV 1.1.1]')
    def test_missing_lv_is_allowed(self):
        v=m.aggregate([row(lv='')]);self.assertEqual(v[0]['allocation_text'],'UV1: 6')
    def test_different_lv_in_same_cabinet_preserved(self):
        v=m.aggregate([row(),row(id=2,lv='1.1.2')])
        self.assertEqual(len(v),1);self.assertIn('1.1.1',v[0]['allocation_text']);self.assertIn('1.1.2',v[0]['allocation_text'])
    def test_same_cabinet_lv_summed(self):
        self.assertEqual(m.aggregate([row(),row(id=2)])[0]['allocation_text'],'UV1: 12 [LV 1.1.1]')
    def test_price_difference_does_not_duplicate_product(self):
        v=m.aggregate([row(qty=2,price=10),row(id=2,qty=3,price=20)])
        self.assertEqual(len(v),1);self.assertEqual(v[0]['cost'],80);self.assertEqual(v[0]['unit_price'],16)
    def test_different_units_not_summed_without_conversion(self):
        a=row();b=row(id=2);b['unit']='m'
        self.assertEqual(len(m.aggregate([a,b])),2)
    def test_optional_distinct_from_required(self):
        a=row();b=row(id=2);b['optional']=True
        self.assertEqual(len(m.aggregate([a,b])),2)
    def test_aliases_share_native_identity(self):
        a=row();b=row(id=2);b['product_id']=99
        self.assertEqual(len(m.aggregate([a,b])),1)
    def test_different_products_separate(self):
        self.assertEqual(len(m.aggregate([row(),row(id=2,product=11)])),2)
    def test_valid_explicit_changes(self):
        self.assertTrue(m.validate_change([row(qty=10),row(id=2,cabinet=2,qty=14)],{1,2},{1,2}))
    def test_foreign_cabinet_rejected(self):
        with self.assertRaises(ValueError):m.validate_change([row(cabinet=99)],{1,2},{1})
    def test_missing_cabinet_rejected(self):
        with self.assertRaises(ValueError):m.validate_change([row(cabinet=None)],{1,2},{1})
    def test_missing_original_allocation_rejected(self):
        with self.assertRaises(ValueError):m.validate_change([row()],{1,2},{1,2})
    def test_duplicate_source_rejected(self):
        with self.assertRaises(ValueError):m.validate_change([row(),row()],{1},{1})
    def test_new_allocated_line_allowed(self):
        r=row(id=3,cabinet=2);r['source_id']=False
        self.assertTrue(m.validate_change([row(),r],{1,2},{1}))
    def test_explicit_remove_allowed(self):
        self.assertTrue(m.validate_change([row(removed=True)],{1},{1}))
    def test_zero_requires_explicit_remove(self):
        with self.assertRaises(ValueError):m.validate_change([row(qty=0)],{1},{1})
    def test_fingerprint_detects_quantity(self):
        self.assertNotEqual(m.fingerprint([row()]),m.fingerprint([row(qty=7)]))
    def test_fingerprint_detects_assignment(self):
        self.assertNotEqual(m.fingerprint([row()]),m.fingerprint([row(cabinet=2)]))
    def test_fingerprint_order_stable(self):
        a,b=row(),row(id=2)
        self.assertEqual(m.fingerprint([a,b]),m.fingerprint([b,a]))
    def test_price_only_is_not_technical_change(self):
        before=row();after={**before,'unit_purchase_price':17,'sab_material_removed':False}
        self.assertFalse(m.technical_change(after,before))
    def test_quantity_is_technical_change(self):
        before=row();after={**before,'quantity':9,'sab_material_removed':False}
        self.assertTrue(m.technical_change(after,before))
    def test_product_is_technical_change(self):
        before=row();after={**before,'odoo_product_id':11,'sab_material_removed':False}
        self.assertTrue(m.technical_change(after,before))
    def test_sql_injection_not_applicable_to_values(self):
        r=row(lv="1'); DROP TABLE x; --")
        self.assertIn(r['lv'],m.aggregate([r])[0]['allocation_text'])

class TestSourceContracts(unittest.TestCase):
    def test_model_compiles(self):
        compile((ROOT/'models/sab_bom_material_control.py').read_text(),'model','exec')
    def test_views_parse(self):
        for p in (ROOT/'views').glob('*.xml'):etree.parse(str(p))
    def test_role_checks_and_atomicity_present(self):
        s=(ROOT/'models/sab_bom_material_control.py').read_text()+(ROOT/'models/sab_bom_material_wizards.py').read_text()
        for token in ('_purchaser(self.env)','FOR UPDATE','self.env.cr.savepoint()',
                      'expected_fingerprint != self._current_fingerprint()',
                      'req._release_project_reservation()',"'sab_material_recheck':"):
            self.assertIn(token,s)
    def test_no_quote_or_master_writes_in_revision(self):
        tree=ast.parse((ROOT/'models/sab_bom_material_wizards.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='action_apply')
        text=ast.unparse(method)
        self.assertNotIn("env['sale.order']",text);self.assertNotIn("env['sab.calculation.item']",text)
    def test_allocations_never_automatic_proportion(self):
        s=(ROOT/'models/sab_bom_material_control.py').read_text()+(ROOT/'models/sab_bom_material_wizards.py').read_text()
        self.assertIn("'quantity': 0.0 if self.remove else self.quantity",s)
        self.assertNotIn('proportion',s)
    def test_no_translatable_view_selectors(self):
        doc=etree.parse(str(ROOT/'views/sab_bom_material_control_views.xml'))
        for node in doc.xpath('//xpath'):
            self.assertNotIn('@string',node.get('expr'))
    def test_cost_review_exposed_for_both_release_steps(self):
        doc=etree.parse(str(ROOT/'views/sab_bom_material_control_views.xml'))
        attrs=doc.xpath("//attribute[@name='name']/text()")
        self.assertIn('action_review_material_costs',attrs)
        self.assertIn('action_review_purchase_costs',attrs)

if __name__=='__main__':unittest.main(verbosity=2)
