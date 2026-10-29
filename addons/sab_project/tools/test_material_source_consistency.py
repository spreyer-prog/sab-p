"""Run the actual wizard comparison in isolation, not a full Odoo/DB test.

The AST extraction keeps these cases tied to the production guard, rather than
reimplementing a second comparator which could conceal a regression.
"""
import ast
from copy import deepcopy
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKED_FIELDS = ('quantity', 'unit', 'optional', 'unit_purchase_price', 'sab_lv_position')


def guard_code():
    tree = ast.parse((ROOT / 'models/sab_bom_material_wizards.py').read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'action_apply')
    loops = [n for n in ast.walk(method) if isinstance(n, ast.For)
             and isinstance(n.iter, ast.Tuple)
             and tuple(x.value for x in n.iter.elts if isinstance(x, ast.Constant)) == CHECKED_FIELDS]
    if len(loops) != 1:
        raise AssertionError('Expected exactly one material-source comparison guard.')
    return compile(ast.fix_missing_locations(ast.Module(body=loops, type_ignores=[])), '<actual-source-guard>', 'exec')


class Row(dict):
    _fields = {key: SimpleNamespace(string=key) for key in CHECKED_FIELDS}


def row(lv=False):
    return Row(quantity=6.0, unit='pcs', optional=False, unit_purchase_price=10.0, sab_lv_position=lv)


class TestMaterialSourceConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = guard_code()

    def check(self, source, target):
        exec(self.code, {'source': source, 'old_line': target,
                         '_': lambda text: text, 'ValidationError': ValueError})

    def test_01_empty_representations_are_equivalent(self):
        for left, right in product(('', False, None), repeat=2):
            with self.subTest(left=left, right=right):
                self.check(row(left), row(right))

    def test_02_matching_lv_and_ntg_are_preserved(self):
        for code in ('1.1.1', 'NTG 2', '0', '01.01.001'):
            with self.subTest(code=code):
                self.check(row(code), row(code))

    def test_03_real_lv_difference_is_rejected(self):
        for left, right in (('1.1.1', '1.1.2'), ('NTG 1', 'NTG 2'),
                            ('0', ''), ('1.1.1', False), ('', '1.1.1'), (' ', '')):
            with self.subTest(left=left, right=right):
                with self.assertRaisesRegex(ValueError, 'sab_lv_position'):
                    self.check(row(left), row(right))

    def test_04_real_material_differences_are_rejected_even_without_lv(self):
        for key, value in (('quantity', 9.0), ('unit', 'm'),
                           ('optional', True), ('unit_purchase_price', 12.0)):
            with self.subTest(key=key):
                source, target = row(''), row(False)
                target[key] = value
                with self.assertRaisesRegex(ValueError, key):
                    self.check(source, target)

    def test_05_comparison_never_writes_or_invents_lv(self):
        source, target = row(''), row(False)
        before = deepcopy((source, target))
        self.check(source, target)
        self.assertEqual((source, target), before)
        self.assertIs(target['sab_lv_position'], False)
        self.assertEqual(source['sab_lv_position'], '')

    def test_06_zero_price_is_valid_and_not_missing(self):
        source, target = row(''), row(False)
        source['unit_purchase_price'] = target['unit_purchase_price'] = 0.0
        self.check(source, target)
        target['unit_purchase_price'] = 0.01
        with self.assertRaisesRegex(ValueError, 'unit_purchase_price'):
            self.check(source, target)


if __name__ == '__main__':
    unittest.main(verbosity=2)
