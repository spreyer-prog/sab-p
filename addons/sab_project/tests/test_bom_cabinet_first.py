"""Cabinet-first engineering workflow. Requires the complete Odoo registry."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.fields import Command
from lxml import etree


class TestCabinetFirstBom(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Cabinet first customer'})
        cls.project = cls.env['project.project'].create({'name': 'Cabinet first project', 'partner_id': cls.partner.id})
        cls.product = cls.env['sab.product'].create({
            'name': 'Original material', 'price_mode': 'fixed', 'fixed_purchase_price': 10})
        cls.replacement = cls.env['sab.product'].create({
            'name': 'Technical replacement', 'price_mode': 'fixed', 'fixed_purchase_price': 17})
        cls.item = cls.env['sab.calculation.item'].create({
            'name': 'Initial cabinet calculation', 'quotation_text': 'Initial calculation',
            'product_line_ids': [Command.create({'product_id': cls.product.id, 'quantity': 2, 'unit': 'pcs'})],
        })

    def order(self, names=('UV1', 'UV2')):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id, 'sab_project_id': self.project.id,
            'sab_calculation_source': 'schematic',
        })
        Line = self.env['sab.offer.calculation.line']
        for i, name in enumerate(names):
            offset = i * 100
            Line.create({'order_id': order.id, 'line_type': 'cabinet', 'description': name, 'sequence': offset + 10})
            Line.create({'order_id': order.id, 'calculation_item_id': self.item.id, 'quantity': 3, 'sequence': offset + 20})
            Line.create({'order_id': order.id, 'line_type': 'cabinet_end', 'sequence': offset + 30})
        order.action_sab_release_offer()
        order.write({'state': 'sale'})
        return order

    def cabinets(self, order):
        order.action_generate_sab_cabinet_boms()
        return order.sab_bom_ids.filtered(lambda b: b.bom_scope == 'cabinet').sorted('id')

    def wizard(self, order, cabinets):
        return self.env['sab.procurement.package.wizard'].create({
            'order_id': order.id, 'sab_cabinet_first': True,
            'cabinet_bom_ids': [Command.set(cabinets.ids)],
        })

    def package(self, order, cabinets):
        action = self.wizard(order, cabinets).action_create_procurement_package()
        return self.env['sab.project.bom'].browse(action['res_id'])

    def test_initial_generation_creates_only_one_list_per_cabinet(self):
        order = self.order(); boms = self.cabinets(order)
        self.assertTrue(order.sab_bom_cabinet_first)
        self.assertEqual(len(boms), 2)
        self.assertEqual(len(order.sab_bom_ids), 2)
        self.assertEqual(set(boms.mapped('state')), {'draft'})
        self.assertEqual(set(boms.mapped('sab_engineering_status')), {'editing'})
        self.assertFalse(order.sab_bom_ids.filtered(lambda b: b.bom_scope != 'cabinet'))
        self.assertEqual(boms[0].line_ids.quantity, 6)

    def test_regeneration_preserves_all_technical_edits_and_record_ids(self):
        order = self.order(); boms = self.cabinets(order)
        row = boms[0].line_ids
        row.write({'quantity': 9, 'note': 'Technically checked'})
        original_id = row.id
        self.cabinets(order)
        self.assertEqual(boms[0].line_ids.id, original_id)
        self.assertEqual(row.quantity, 9)
        self.assertEqual(row.note, 'Technically checked')
        self.assertEqual(len(order.sab_bom_ids), 2)
        row.unlink()
        self.cabinets(order)
        self.assertFalse(boms[0].line_ids)  # Do not refill a work-in-progress list.

    def test_legacy_button_routes_to_single_lists_after_activation(self):
        order = self.order(); boms = self.cabinets(order)
        order.action_generate_sab_bom()
        self.assertEqual(set(order.sab_bom_ids.ids), set(boms.ids))
        self.assertFalse(order.sab_bom_ids.filtered(lambda b: b.bom_scope == 'total'))

    def test_material_substitution_and_quantity_do_not_write_quote_or_catalogue(self):
        order = self.order(); boms = self.cabinets(order)
        quote_lines = order.sab_calculation_line_ids
        before = [(r.id, r.quantity, r.recommended_net_price, r.component_snapshot_ids.ids) for r in quote_lines]
        row = boms[0].line_ids
        row.write({'odoo_product_id': self.replacement.odoo_product_id.id, 'quantity': 11})
        self.assertFalse(row.product_id)
        self.assertEqual(row.odoo_product_id, self.replacement.odoo_product_id)
        self.assertEqual(row.unit_purchase_price, 17)
        self.assertFalse(row.supplier_product_id)
        self.assertEqual(boms[1].line_ids.odoo_product_id, self.product.odoo_product_id)
        self.assertEqual([(r.id, r.quantity, r.recommended_net_price, r.component_snapshot_ids.ids) for r in quote_lines], before)
        self.assertEqual(self.item.product_line_ids.product_id, self.product)
        self.assertEqual(self.item.product_line_ids.quantity, 2)

    def test_legacy_product_selection_keeps_both_identities_consistent(self):
        row = self.cabinets(self.order())[0].line_ids
        row.write({'product_id': self.replacement.id, 'odoo_product_id': self.replacement.odoo_product_id.id})
        self.assertEqual(row.product_id, self.replacement)
        self.assertEqual(row.odoo_product_id, self.replacement.odoo_product_id)
        self.assertEqual(row.unit_purchase_price, 17)

    def test_individual_release_marks_ready_but_does_not_release_other_cabinets(self):
        order = self.order(); boms = self.cabinets(order)
        boms[0].action_release()
        self.assertEqual(boms[0].sab_engineering_status, 'ready')
        self.assertTrue(boms[0].sab_technical_released_at)
        self.assertEqual(boms[0].sab_technical_released_by_id, self.env.user)
        self.assertEqual(boms[1].state, 'draft')
        self.assertFalse(order.sab_bom_ids.mapped('purchase_requirement_ids'))

    def test_released_material_is_immutable(self):
        bom = self.cabinets(self.order())[0]; bom.action_release()
        for operation in (
            lambda: bom.line_ids.write({'quantity': 99}),
            lambda: bom.line_ids.write({'odoo_product_id': self.replacement.odoo_product_id.id}),
            lambda: bom.line_ids.unlink(),
            lambda: self.env['sab.project.bom.line'].create({'bom_id': bom.id, 'product_id': self.product.id}),
        ):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                operation()

    def test_empty_and_zero_quantity_are_rejected_at_technical_release(self):
        boms = self.cabinets(self.order())
        boms[0].line_ids.unlink()
        boms[1].line_ids.quantity = 0
        for bom in boms:
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                bom.action_release()
        self.assertEqual(set(boms.mapped('state')), {'draft'})

    def test_only_selected_green_lists_form_the_package(self):
        order = self.order(); boms = self.cabinets(order)
        boms.action_release()
        boms[0].line_ids.invalidate_recordset()
        package = self.package(order, boms[0])
        self.assertEqual(package.source_cabinet_bom_ids, boms[0])
        self.assertEqual(package.line_ids.quantity, 6)
        self.assertEqual(package.line_ids.source_cabinet_line_id, boms[0].line_ids)
        self.assertEqual(boms[0].sab_handover_package_id, package)
        self.assertFalse(boms[1].sab_handover_package_id)
        self.assertEqual(boms[1].sab_engineering_status, 'ready')
        self.assertFalse(package.purchase_requirement_ids)
        self.assertEqual(package.purchase_release_state, 'not_released')

    def test_summary_uses_engineered_values_not_offer_snapshot(self):
        order = self.order(); boms = self.cabinets(order)
        boms[0].line_ids.quantity = 9
        boms[1].line_ids.quantity = 4
        boms.action_release()
        package = self.package(order, boms)
        self.assertEqual(sum(package.line_ids.mapped('quantity')), 13)
        self.assertEqual(set(package.line_ids.mapped('source_cabinet_bom_id').ids), set(boms.ids))
        self.assertIn('13', package.sab_material_summary)
        self.assertEqual(len(package.line_ids), 2)  # Exact provenance is retained.

    def test_unreleased_list_is_rejected_even_when_optional_legacy_flag_is_false(self):
        order = self.order(); boms = self.cabinets(order)
        boms[0].action_release()
        wizard = self.wizard(order, boms)
        wizard.require_individual_cabinet_release = False
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            wizard.action_create_procurement_package()
        self.assertEqual(boms[1].state, 'draft')

    def test_duplicate_package_is_rejected(self):
        order = self.order(); boms = self.cabinets(order); boms.action_release()
        first = self.package(order, boms[0])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.package(order, boms)
        self.assertEqual(boms[0].sab_handover_package_id, first)
        self.assertFalse(boms[1].sab_handover_package_id)
        self.assertTrue(self.package(order, boms[1]))

    def test_order_and_project_mixing_are_rejected(self):
        first = self.order(); a = self.cabinets(first); a.action_release()
        second = self.order(); b = self.cabinets(second); b.action_release()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.package(first, a | b)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            (a | b).action_combine_released_cabinets()

    def test_explicit_selection_is_not_expanded_by_wizard_defaults(self):
        order = self.order(); boms = self.cabinets(order); boms.action_release()
        action = boms[0].action_combine_released_cabinets()
        wizard = self.env['sab.procurement.package.wizard'].with_context(**action['context']).create({})
        self.assertEqual(wizard.cabinet_bom_ids, boms[0])
        self.assertTrue(wizard.sab_cabinet_first)
        action = order.action_open_procurement_package_wizard()
        blank = self.env['sab.procurement.package.wizard'].with_context(**action['context']).default_get(['order_id', 'cabinet_bom_ids', 'sab_cabinet_first'])
        self.assertEqual(blank['cabinet_bom_ids'], [Command.set([])])

    def test_legacy_total_does_not_auto_approve_unchecked_cabinets_in_new_flow(self):
        order = self.order()
        # Simulate existing old documents. They are preserved, not deleted.
        order.action_generate_sab_bom()
        total = order.sab_bom_ids.filtered(lambda b: b.bom_scope == 'total')
        self.assertTrue(total)
        before = total.line_ids.ids
        cabinets = self.cabinets(order)
        self.assertEqual(total.line_ids.ids, before)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            total.action_release()
        self.assertEqual(set(cabinets.mapped('state')), {'draft'})

    def test_direct_cabinet_purchasing_stays_blocked(self):
        bom = self.cabinets(self.order())[0]; bom.action_release()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            bom.action_generate_purchase_requirements()

    def test_meta_and_workflow_cannot_be_forged_or_reset(self):
        order = self.order(); bom = self.cabinets(order)[0]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.write({'sab_bom_cabinet_first': False})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            bom.write({'sab_technical_released_by_id': self.env.user.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            bom.write({'sab_handover_package_id': bom.id})

    def test_released_list_cannot_receive_a_moved_draft_line(self):
        boms = self.cabinets(self.order()); boms[0].action_release()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            boms[1].line_ids.write({'bom_id': boms[0].id})

    def test_new_generation_has_no_purchase_or_stock_side_effects(self):
        before = self.env['purchase.order'].search_count([])
        cabinets = self.cabinets(self.order()); cabinets.action_release()
        self.package(cabinets[0].order_id, cabinets)
        self.assertEqual(self.env['purchase.order'].search_count([]), before)
        self.assertFalse(cabinets.mapped('purchase_requirement_ids'))

    def test_ui_uses_new_generation_and_exposes_green_selection(self):
        arch = etree.fromstring(self.env['sale.order'].get_view(
            view_id=self.env.ref('sale.view_order_form').id, view_type='form')['arch'].encode())
        self.assertTrue(arch.xpath("//button[@name='action_generate_sab_cabinet_boms']"))
        self.assertFalse(arch.xpath("//button[@name='action_generate_sab_bom']"))
        arch = etree.fromstring(self.env['sab.project.bom'].get_view(
            view_id=self.env.ref('sab_project.view_sab_project_bom_list').id, view_type='list')['arch'].encode())
        self.assertTrue(arch.xpath("//header/button[@name='action_combine_released_cabinets']"))
        self.assertIn('released', arch.get('decoration-success'))

    def test_purchasing_workspace_waits_for_explicit_handover(self):
        order = self.order(); boms = self.cabinets(order); boms.action_release()
        package = self.package(order, boms)
        self.assertFalse(package.purchase_requirement_ids)
        package._sab_push_to_procurement_workspace()
        self.assertFalse(package.purchase_requirement_ids)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            package.action_open_procurement_workspace()

    def test_explicit_handover_creates_requirements_once_without_supplier_order(self):
        order = self.order(); boms = self.cabinets(order); boms.action_release()
        package = self.package(order, boms)
        before = self.env['purchase.order'].search_count([])
        package.action_release_for_purchase()
        self.assertEqual(package.purchase_release_state, 'released')
        self.assertEqual(len(package.purchase_requirement_ids), 2)
        ids = set(package.purchase_requirement_ids.ids)
        package.action_open_procurement_workspace()
        self.assertEqual(set(package.purchase_requirement_ids.ids), ids)
        self.assertEqual(self.env['purchase.order'].search_count([]), before)

    def test_direct_state_write_cannot_bypass_technical_release(self):
        order = self.order(); bom = self.cabinets(order)[0]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            bom.with_context(sab_cabinet_first_release=True).write({'state': 'released'})
        self.assertEqual(bom.state, 'draft')
        bom.action_release()
        self.assertEqual(bom.state, 'released')
