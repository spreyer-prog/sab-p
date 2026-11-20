"""Isolated validation/summary/structural checks. NOT an Odoo integration run."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from lxml import etree
from markupsafe import Markup

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models/sab_bom_cabinet_first.py'
TREE = ast.parse(MODEL.read_text())

def method(name):
    node = next(n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef) and n.name == name)
    import copy
    node = copy.deepcopy(node); node.decorator_list = []
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {'math': math, 'Markup': Markup, '_': lambda text: text}
    exec(compile(ast.fix_missing_locations(module), str(MODEL), 'exec'), namespace)
    return namespace[name]

positive = method('_positive')
summary = method('_compute_material_summary')

class Product(SimpleNamespace):
    def __init__(self, ident=1, name='Product'):
        super().__init__(id=ident, display_name=name, _name='product.product')


def row(qty, product=None, unit='pcs', optional=False):
    return SimpleNamespace(odoo_product_id=product or Product(), product_id=None,
                           quantity=qty, unit=unit, optional=optional)

def render(rows):
    bom = SimpleNamespace(line_ids=rows)
    summary([bom])
    return bom.sab_material_summary

class TestIsolatedCabinetFlow(unittest.TestCase):
    def test_positive_integer(self): self.assertTrue(positive(3))
    def test_positive_fraction(self): self.assertTrue(positive(.125))
    def test_zero_invalid(self): self.assertFalse(positive(0))
    def test_negative_invalid(self): self.assertFalse(positive(-1))
    def test_infinity_invalid(self): self.assertFalse(positive(float('inf')))
    def test_nan_invalid(self): self.assertFalse(positive(float('nan')))
    def test_summary_same_product_adds_quantities(self):
        doc=etree.HTML(str(render([row(9),row(4)])))
        self.assertEqual(doc.xpath('//tbody/tr/td[last()]/text()'),['13'])
    def test_summary_different_units_not_merged(self):
        doc=etree.HTML(str(render([row(9),row(4,unit='m')])))
        self.assertEqual(len(doc.xpath('//tbody/tr')),2)
    def test_summary_optional_not_mixed(self):
        doc=etree.HTML(str(render([row(9),row(4,optional=True)])))
        self.assertEqual(len(doc.xpath('//tbody/tr')),2)
    def test_summary_distinct_products_not_mixed(self):
        doc=etree.HTML(str(render([row(9),row(4,Product(2))])))
        self.assertEqual(len(doc.xpath('//tbody/tr')),2)
    def test_product_name_is_escaped(self):
        doc=etree.HTML(str(render([row(1,Product(name='<script>alert(1)</script>'))])))
        self.assertFalse(doc.xpath('//script'))
        self.assertIn('<script>', ''.join(doc.xpath('//td[1]/text()')))
    def test_empty_summary(self): self.assertFalse(render([]))
    def test_generator_has_no_total_creation(self):
        node=next(n for n in ast.walk(TREE) if isinstance(n,ast.FunctionDef) and n.name=='action_generate_sab_cabinet_boms')
        text=ast.unparse(node)
        self.assertNotIn("'total'",text)
        self.assertIn('existing',text)
        self.assertNotIn('.unlink()',text)
    def test_package_keeps_explicit_source_line_links(self):
        node=next(n for n in ast.walk(TREE) if isinstance(n,ast.FunctionDef) and n.name=='action_create_procurement_package')
        text=ast.unparse(node)
        self.assertIn("'source_cabinet_line_id': line.id",text)
        self.assertIn("'quantity': line.quantity",text)
        self.assertNotIn('component_snapshot',text)
    def test_staged_handover_guard_present(self):
        node=next(n for n in ast.walk(TREE) if isinstance(n,ast.FunctionDef) and n.name=='_sab_push_to_procurement_workspace')
        self.assertIn('purchase_release_state',ast.unparse(node))
    def test_views_are_well_formed_and_selection_action_exists(self):
        doc=etree.parse(str(ROOT/'views/sab_bom_cabinet_first_views.xml'))
        self.assertTrue(doc.xpath("//header/button[@name='action_combine_released_cabinets']"))
    def test_new_view_is_loaded_last(self):
        manifest=ast.literal_eval((ROOT/'__manifest__.py').read_text())
        self.assertEqual(manifest['data'][-1],'views/sab_bom_cabinet_first_views.xml')
    def test_model_import_after_existing_models(self):
        text=(ROOT/'__init__.py').read_text()
        self.assertTrue(text.rstrip().endswith('from .models import sab_bom_cabinet_first'))
    def test_integration_tests_registered(self):
        self.assertIn('from . import test_bom_cabinet_first',(ROOT/'tests/__init__.py').read_text())

if __name__=='__main__': unittest.main(verbosity=2)
