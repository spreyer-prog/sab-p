"""Odoo/PostgreSQL regressions for the installation and package-source fixes."""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase

from . import test_bom_cabinet_first


class TestBomLoadFix(TransactionCase):
    # Reuse the established fixture actions without inheriting/duplicating
    # the entire original test class.
    order = test_bom_cabinet_first.TestCabinetFirstBom.order
    cabinets = test_bom_cabinet_first.TestCabinetFirstBom.cabinets
    wizard = test_bom_cabinet_first.TestCabinetFirstBom.wizard
    package = test_bom_cabinet_first.TestCabinetFirstBom.package

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'BOM load regression customer'})
        cls.project = cls.env['project.project'].create({
            'name': 'BOM load regression project', 'partner_id': cls.partner.id})
        cls.product = cls.env['sab.product'].create({
            'name': 'BOM load material', 'price_mode': 'fixed', 'fixed_purchase_price': 10})
        cls.item = cls.env['sab.calculation.item'].create({
            'name': 'BOM load calculation', 'quotation_text': 'Material',
            'product_line_ids': [Command.create({
                'product_id': cls.product.id, 'quantity': 2, 'unit': 'pcs'})]})

    def test_material_access_records_load_with_unchanged_roles(self):
        expected = [
            ('group_user', 'sab.bom.material.group', 'base.group_user', (1, 0, 0, 0)),
            ('change_user', 'sab.bom.material.change', 'base.group_user', (1, 0, 0, 0)),
            ('edit_purchase', 'sab.bom.material.edit', 'sab_project.group_sab_purchasing', (1, 1, 1, 1)),
            ('edit_admin', 'sab.bom.material.edit', 'base.group_system', (1, 1, 1, 1)),
            ('edit_line_purchase', 'sab.bom.material.edit.line', 'sab_project.group_sab_purchasing', (1, 1, 1, 1)),
            ('edit_line_admin', 'sab.bom.material.edit.line', 'base.group_system', (1, 1, 1, 1)),
            ('review_manager', 'sab.bom.material.review', 'project.group_project_manager', (1, 1, 1, 1)),
            ('review_admin', 'sab.bom.material.review', 'base.group_system', (1, 1, 1, 1)),
            ('review_approver', 'sab.bom.material.review', 'sab_project.group_sab_purchase_approver', (1, 1, 1, 1)),
        ]
        for suffix, model, group, permissions in expected:
            access = self.env.ref('sab_project.access_material_' + suffix)
            self.assertEqual(access._name, 'ir.model.access')
            self.assertEqual(access.model_id.model, model)
            self.assertEqual(access.group_id, self.env.ref(group))
            self.assertEqual(tuple(int(access[f]) for f in
                ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')), permissions)

    def test_package_sources_exist_when_each_material_row_is_created(self):
        order = self.order()
        cabinets = self.cabinets(order)
        cabinets.action_release()
        Line = self.env['sab.project.bom.line']
        original_create = type(Line).create
        seen = []

        def checked_create(records, values):
            for vals in values if isinstance(values, list) else [values]:
                bom = records.env['sab.project.bom'].browse(vals.get('bom_id'))
                if bom.bom_scope == 'procurement':
                    self.assertEqual(set(bom.source_cabinet_bom_ids.ids), set(cabinets.ids))
                    self.assertIn(vals['source_cabinet_bom_id'], bom.source_cabinet_bom_ids.ids)
                    seen.append(vals['source_cabinet_line_id'])
            return original_create(records, values)

        with patch.object(type(Line), 'create', checked_create):
            package = self.package(order, cabinets)
        self.assertEqual(set(seen), set(cabinets.mapped('line_ids').ids))
        self.assertEqual(len(package.line_ids), len(seen))
        self.assertEqual(set(package.line_ids.mapped('source_cabinet_bom_id').ids), set(cabinets.ids))
        self.assertFalse(package.purchase_requirement_ids)

    def test_failed_material_creation_rolls_back_header_and_source_claims(self):
        order = self.order()
        cabinets = self.cabinets(order)
        cabinets.action_release()
        wizard = self.wizard(order, cabinets)
        Bom = self.env['sab.project.bom']
        Line = self.env['sab.project.bom.line']
        original_create = type(Line).create
        before = Bom.search_count([('order_id', '=', order.id)])
        message = 'Injected package-line failure'

        def fail_package_line(records, values):
            for vals in values if isinstance(values, list) else [values]:
                bom = records.env['sab.project.bom'].browse(vals.get('bom_id'))
                if bom.bom_scope == 'procurement':
                    raise ValidationError(message)
            return original_create(records, values)

        caught = False
        with patch.object(type(Line), 'create', fail_package_line):
            # Intentionally no test-level savepoint/assertRaises: verify that
            # the production method's own savepoint rolls back its new header.
            try:
                wizard.action_create_procurement_package()
            except ValidationError as error:
                self.assertEqual(str(error), message)
                caught = True
        self.assertTrue(caught)
        self.assertEqual(Bom.search_count([('order_id', '=', order.id)]), before)
        cabinets.invalidate_recordset(['sab_handover_package_id'])
        self.assertFalse(cabinets.mapped('sab_handover_package_id'))
        self.assertFalse(cabinets.mapped('purchase_requirement_ids'))

    def _draft_package_and_cabinets(self):
        order = self.order()
        cabinets = self.cabinets(order)
        cabinets.action_release()
        draft = self.env['sab.project.bom'].create({
            'name': 'Source validation regression', 'order_id': order.id,
            'project_id': order.sab_project_id.id, 'bom_scope': 'procurement',
            'source_cabinet_bom_ids': [Command.set(cabinets[:1].ids)]})
        return draft, cabinets

    def test_cabinet_outside_package_is_still_rejected(self):
        draft, cabinets = self._draft_package_and_cabinets()
        with self.assertRaisesRegex(ValidationError, 'Verteilerzuordnung'), self.env.cr.savepoint():
            self.env['sab.project.bom.line'].create({
                'bom_id': draft.id, 'product_id': self.product.id, 'quantity': 1,
                'source_cabinet_bom_id': cabinets[1].id,
                'source_cabinet_line_id': cabinets[1].line_ids.id})

    def test_source_line_from_another_cabinet_is_still_rejected(self):
        draft, cabinets = self._draft_package_and_cabinets()
        with self.assertRaisesRegex(ValidationError, 'ursprüngliche Stücklistenposition'), self.env.cr.savepoint():
            self.env['sab.project.bom.line'].create({
                'bom_id': draft.id, 'product_id': self.product.id, 'quantity': 1,
                'source_cabinet_bom_id': cabinets[0].id,
                'source_cabinet_line_id': cabinets[1].line_ids.id})
