"""Local structural regressions; no Odoo runtime or database is simulated."""
import ast
from pathlib import Path
import unittest
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
ACL = ROOT / 'security/sab_material_control_access.xml'


class TestBomLoadContracts(unittest.TestCase):
    def test_acl_manifest_uses_explicit_model_xml(self):
        data = ast.literal_eval((ROOT / '__manifest__.py').read_text())['data']
        self.assertNotIn('security/sab_material_control_access.csv', data)
        self.assertIn('security/sab_material_control_access.xml', data)
        self.assertLess(data.index('security/sab_material_control_access.xml'),
                        data.index('views/sab_bom_material_control_views.xml'))

    def test_all_nine_access_ids_are_preserved(self):
        doc = etree.parse(str(ACL))
        expected = {'access_material_' + suffix for suffix in (
            'group_user', 'change_user', 'edit_purchase', 'edit_admin',
            'edit_line_purchase', 'edit_line_admin', 'review_manager',
            'review_admin', 'review_approver')}
        self.assertEqual(set(doc.xpath('//record/@id')), expected)
        self.assertEqual(len(doc.xpath('//record')), 9)
        self.assertEqual(set(doc.xpath('//record/@model')), {'ir.model.access'})

    def test_access_does_not_grant_write_to_read_only_groups(self):
        doc = etree.parse(str(ACL))
        for record in doc.xpath('//record'):
            group = record.find("field[@name='group_id']").get('ref')
            self.assertTrue(group)
            values = tuple(int(record.find("field[@name='%s']" % field).get('eval'))
                           for field in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink'))
            self.assertEqual(values, (1, 0, 0, 0) if group == 'base.group_user' else (1, 1, 1, 1))

    def _method(self):
        tree = ast.parse((ROOT / 'models/sab_bom_cabinet_first.py').read_text())
        return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == 'action_create_procurement_package')

    def test_source_header_is_created_without_nested_material_lines(self):
        creates = [node for node in ast.walk(self._method()) if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'package' for t in node.targets)]
        self.assertEqual(len(creates), 1)
        keys = {key.value for key in creates[0].value.args[0].keys}
        self.assertIn('source_cabinet_bom_ids', keys)
        self.assertNotIn('line_ids', keys)
        body = ast.unparse(self._method())
        self.assertLess(body.index("package.write({'line_ids': values})"),
                        body.index("cabinets.write({'sab_handover_package_id': package.id})"))
        self.assertLess(body.index("package.write({'line_ids': values})"), body.index('package.action_release()'))

    def test_header_and_lines_share_one_savepoint(self):
        method = self._method()
        block = next(node for node in ast.walk(method) if isinstance(node, ast.With)
                     and any('self.env.cr.savepoint()' == ast.unparse(item.context_expr)
                             for item in node.items))
        text = ast.unparse(block)
        for token in ("package = self.env['sab.project.bom'].create(",
                      "package.write({'line_ids': values})", 'package.action_release()'):
            self.assertIn(token, text)
        self.assertNotIn('.commit(', ast.unparse(method))

    def test_odoo_regression_suite_is_registered_and_compiles(self):
        self.assertIn('from . import test_bom_load_fix', (ROOT / 'tests/__init__.py').read_text())
        p = ROOT / 'tests/test_bom_load_fix.py'
        compile(p.read_text(), str(p), 'exec')
        tree = ast.parse(p.read_text())
        self.assertEqual(len([node for node in ast.walk(tree)
                              if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]), 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
