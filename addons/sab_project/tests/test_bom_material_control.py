"""These regression cases need Odoo 19 + PostgreSQL; not isolated helper tests."""
from lxml import etree
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestMaterialControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Material control customer'})
        cls.project = cls.env['project.project'].create({'name': 'Material control project', 'partner_id': cls.partner.id})
        cls.product = cls.env['sab.product'].create({'name': 'Material A', 'price_mode': 'fixed', 'fixed_purchase_price': 10})
        cls.replacement = cls.env['sab.product'].create({'name': 'Material B', 'price_mode': 'fixed', 'fixed_purchase_price': 17})
        cls.item = cls.env['sab.calculation.item'].create({'name': 'Material calculation', 'quotation_text': 'Material',
            'product_line_ids': [Command.create({'product_id': cls.product.id, 'quantity': 2, 'unit': 'pcs'})]})

    def order(self, names=('UV1', 'UV2')):
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'sab_project_id': self.project.id,
            'sab_calculation_source': 'schematic'})
        Line = self.env['sab.offer.calculation.line']
        for i, name in enumerate(names):
            Line.create({'order_id': order.id, 'line_type': 'cabinet', 'description': name, 'sequence': i*100+10})
            Line.create({'order_id': order.id, 'calculation_item_id': self.item.id, 'quantity': 3, 'sequence': i*100+20})
            Line.create({'order_id': order.id, 'line_type': 'cabinet_end', 'sequence': i*100+30})
        order.action_sab_release_offer(); order.write({'state': 'sale'})
        return order

    def cabinets(self, order):
        order.action_generate_sab_cabinet_boms()
        return order.sab_bom_ids.filtered(lambda b: b.bom_scope == 'cabinet').sorted('id')

    def package(self, order, cabinets):
        cabinets.action_release()
        wizard = self.env['sab.procurement.package.wizard'].create({'order_id': order.id,
            'sab_cabinet_first': True, 'cabinet_bom_ids': [Command.set(cabinets.ids)]})
        return self.env['sab.project.bom'].browse(wizard.action_create_procurement_package()['res_id'])

    def edit(self, group):
        return self.env['sab.bom.material.edit'].create({'group_id': group.id, 'reason': 'Technischer Mengenabgleich'})

    def apply(self, wizard):
        wizard.confirm_allocation = True
        return wizard.action_apply()

    def test_01_original_material_ek_is_frozen(self):
        cabinet = self.cabinets(self.order())[0]
        self.assertTrue(cabinet.sab_material_baseline_known)
        self.assertEqual(cabinet.sab_material_calculated_ek, 60)
        self.assertEqual(cabinet.sab_material_current_ek, 60)
        cabinet.line_ids.quantity = 9
        self.assertEqual(cabinet.sab_material_calculated_ek, 60)
        self.assertEqual(cabinet.sab_material_current_ek, 90)
        self.assertEqual(cabinet.sab_material_delta, 30)
        self.assertEqual(cabinet.sab_material_delta_percent, 50)

    def test_02_replacement_changes_current_ek_only(self):
        cabinet = self.cabinets(self.order())[0]
        cabinet.line_ids.odoo_product_id = self.replacement.odoo_product_id
        self.assertEqual(cabinet.sab_material_current_ek, 102)
        self.assertEqual(cabinet.sab_material_calculated_ek, 60)
        cabinet.action_release()
        self.assertEqual(cabinet.sab_material_release_ek, 102)

    def test_03_repeat_generation_does_not_reset_cost_basis(self):
        order = self.order(); cabinets = self.cabinets(order)
        cabinets[0].line_ids.quantity = 12
        self.cabinets(order)
        self.assertEqual(cabinets[0].sab_material_calculated_ek, 60)
        self.assertEqual(cabinets[0].sab_material_current_ek, 120)

    def test_04_native_article_is_one_group_with_both_cabinets(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        self.assertEqual(len(package.sab_material_group_ids),1)
        group=package.sab_material_group_ids
        self.assertEqual(group.quantity,12)
        self.assertEqual(group.purchase_total,120)
        self.assertIn('UV1: 6',group.allocation_text);self.assertIn('UV2: 6',group.allocation_text)
        self.assertEqual(len(package.line_ids),2)  # provenance, not duplicated purchasing display

    def test_05_optional_lv_survives_handover(self):
        order=self.order(); cabinets=self.cabinets(order)
        cabinets[0].line_ids.sab_lv_position='1.1.1'
        cabinets[1].line_ids.sab_lv_position='NTG 2'
        package=self.package(order,cabinets)
        self.assertEqual(set(package.line_ids.mapped('sab_lv_position')),{'1.1.1','NTG 2'})
        self.assertIn('1.1.1',package.sab_material_group_ids.allocation_text)
        self.assertIn('NTG 2',package.sab_material_group_ids.allocation_text)

    def test_06_missing_lv_is_not_a_release_error(self):
        order=self.order(); cabinets=self.cabinets(order)
        self.assertFalse(any(cabinets.mapped('line_ids.sab_lv_position')))
        package=self.package(order,cabinets)
        self.assertEqual(package.sab_material_current_ek,120)

    def test_07_quantity_change_updates_exact_source_and_costs(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids)
        first=wizard.line_ids.filtered(lambda r:r.cabinet_bom_id==cabinets[0])
        first.quantity=9; self.apply(wizard)
        self.assertEqual(cabinets[0].line_ids.quantity,9)
        self.assertEqual(cabinets[1].line_ids.quantity,6)
        self.assertEqual(package.sab_material_group_ids.quantity,15)
        self.assertEqual(package.sab_material_current_ek,150)
        self.assertEqual(package.sab_material_calculated_ek,120)
        self.assertTrue(cabinets[0].sab_material_recheck)
        self.assertFalse(cabinets[1].sab_material_recheck)
        self.assertEqual(cabinets[0].sab_engineering_status,'recheck')
        self.assertEqual(len(package.sab_material_change_ids),1)

    def test_08_product_exchange_splits_display_without_losing_provenance(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids)
        first=wizard.line_ids.filtered(lambda r:r.cabinet_bom_id==cabinets[0])
        first.write({'odoo_product_id':self.replacement.odoo_product_id.id,'unit_purchase_price':17})
        self.apply(wizard)
        self.assertEqual(cabinets[0].line_ids.odoo_product_id,self.replacement.odoo_product_id)
        self.assertEqual(cabinets[1].line_ids.odoo_product_id,self.product.odoo_product_id)
        self.assertEqual(len(package.sab_material_group_ids),2)
        self.assertEqual(package.sab_material_current_ek,162)
        self.assertEqual(package.sab_material_calculated_ek,120)

    def test_09_noop_dialog_has_no_revision_side_effect(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids); self.apply(wizard)
        self.assertEqual(package.sab_material_revision,0)
        self.assertFalse(package.sab_material_change_ids)
        self.assertFalse(package.sab_material_recheck_required)

    def test_10_missing_acknowledgement_is_rejected(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids);wizard.line_ids[0].quantity=9
        with self.assertRaises(ValidationError),self.env.cr.savepoint():wizard.action_apply()
        self.assertEqual(sum(cabinets.mapped('line_ids.quantity')),12)

    def test_11_existing_assignment_cannot_be_redirected(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids)
        wizard.line_ids[0].cabinet_bom_id=cabinets[1]
        with self.assertRaises(ValidationError),self.env.cr.savepoint():self.apply(wizard)

    def test_12_explicit_new_allocation_in_selected_cabinet(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids)
        wizard.write({'line_ids':[Command.create({'cabinet_bom_id':cabinets[0].id,
            'odoo_product_id':self.product.odoo_product_id.id,'quantity':4,'unit':'pcs','unit_purchase_price':10,
            'lv_position':'1.1.7'})]})
        self.apply(wizard)
        self.assertEqual(sum(cabinets[0].line_ids.mapped('quantity')),10)
        self.assertEqual(package.sab_material_group_ids.quantity,16)
        self.assertIn('1.1.7',package.sab_material_group_ids.allocation_text)
        self.assertEqual(cabinets[0].sab_material_calculated_ek,60)

    def test_13_stale_dialog_does_not_overwrite_new_revision(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        first=self.edit(package.sab_material_group_ids);second=self.edit(package.sab_material_group_ids)
        first.line_ids[0].quantity=9;self.apply(first)
        second.line_ids[0].quantity=14
        with self.assertRaises(ValidationError),self.env.cr.savepoint():self.apply(second)
        self.assertEqual(package.sab_material_group_ids.quantity,15)

    def test_14_public_release_guards_stay_closed(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        for row in (cabinets[0].line_ids | package.line_ids):
            with self.assertRaises(ValidationError),self.env.cr.savepoint():row.write({'quantity':99})
            with self.assertRaises(AccessError),self.env.cr.savepoint():row._sab_apply_controlled_values({'quantity':99})

    def test_15_base_ek_cannot_be_forged(self):
        cabinet=self.cabinets(self.order())[0]
        with self.assertRaises(ValidationError),self.env.cr.savepoint():
            cabinet.with_context(sab_material_control_service=True).write({'sab_material_baseline':[]})
        self.assertEqual(cabinet.sab_material_calculated_ek,60)

    def test_16_audit_record_is_immutable(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids);wizard.line_ids[0].quantity=9;self.apply(wizard)
        audit=package.sab_material_change_ids
        with self.assertRaises(AccessError),self.env.cr.savepoint():audit.sudo().write({'reason':'erase'})
        with self.assertRaises(AccessError),self.env.cr.savepoint():audit.sudo().unlink()

    def test_17_pending_technical_revision_blocks_purchase(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids);wizard.line_ids[0].quantity=9;self.apply(wizard)
        with self.assertRaises(ValidationError),self.env.cr.savepoint():package.action_release_for_purchase()
        cabinets.filtered('sab_material_recheck').action_release()
        self.assertFalse(package.sab_material_recheck_required)

    def test_18_price_only_change_preserves_technical_approval(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        wizard=self.edit(package.sab_material_group_ids);wizard.line_ids[0].unit_purchase_price=12;self.apply(wizard)
        self.assertFalse(package.sab_material_recheck_required)
        self.assertEqual(package.sab_material_current_ek,132)
        self.assertEqual(package.sab_material_calculated_ek,120)

    def test_19_cost_review_rejects_stale_material(self):
        cabinet=self.cabinets(self.order())[0]
        review=self.env['sab.bom.material.review'].create({'bom_id':cabinet.id})
        cabinet.line_ids.quantity=9
        with self.assertRaises(ValidationError),self.env.cr.savepoint():review.action_confirm()
        self.assertEqual(cabinet.state,'draft')

    def test_20_zero_price_requires_explicit_cost_acknowledgement(self):
        cabinet=self.cabinets(self.order())[0]
        cabinet.line_ids.unit_purchase_price=0
        review=self.env['sab.bom.material.review'].create({'bom_id':cabinet.id})
        with self.assertRaises(ValidationError),self.env.cr.savepoint():review.action_confirm()
        review.acknowledge_unknown=True;review.action_confirm()
        self.assertEqual(cabinet.state,'released')

    def test_21_quote_and_catalogue_are_not_changed_by_purchasing(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        before=[(r.id,r.quantity,r.recommended_net_price,r.lv_position) for r in order.sab_calculation_line_ids]
        wizard=self.edit(package.sab_material_group_ids);wizard.line_ids[0].quantity=9;self.apply(wizard)
        self.assertEqual(before,[(r.id,r.quantity,r.recommended_net_price,r.lv_position) for r in order.sab_calculation_line_ids])
        self.assertEqual(self.item.product_line_ids.quantity,2)
        self.assertEqual(self.product.fixed_purchase_price,10)

    def test_22_existing_production_blocks_retroactive_revision(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        cabinets[0].action_create_production_order()
        with self.assertRaises(ValidationError),self.env.cr.savepoint():self.edit(package.sab_material_group_ids)

    def test_23_display_and_release_actions_are_in_compiled_view(self):
        arch=etree.fromstring(self.env['sab.project.bom'].get_view(
            view_id=self.env.ref('sab_project.view_sab_project_bom_form').id,view_type='form')['arch'].encode())
        for name in ('sab_material_current_ek','sab_material_calculated_ek','sab_material_delta','sab_material_group_ids'):
            self.assertTrue(arch.xpath("//field[@name='%s']"%name))
        for name in ('action_review_material_costs','action_review_purchase_costs'):
            self.assertTrue(arch.xpath("//button[@name='%s']"%name))

    def test_24_new_user_without_purchasing_role_cannot_open_edit(self):
        order=self.order(); cabinets=self.cabinets(order); package=self.package(order,cabinets)
        user=self.env['res.users'].with_context(no_reset_password=True).create({'name':'Material read only',
            'login':'sab-material-read-only','group_ids':[Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):package.sab_material_group_ids.with_user(user).action_edit_allocations()

    def test_25_old_bom_without_captured_baseline_is_explicitly_unknown(self):
        order=self.order();order.action_generate_sab_bom()
        cabinet=order.sab_bom_ids.filtered(lambda b:b.bom_scope=='cabinet')[0]
        self.assertFalse(cabinet.sab_material_comparison_known)
        self.assertEqual(cabinet.sab_material_current_ek,60)

    def test_26_total_keeps_original_ek_when_a_source_line_is_deleted_in_draft(self):
        order=self.order();cabinets=self.cabinets(order)
        row=cabinets[0].line_ids
        self.env['sab.project.bom.line'].create({'bom_id':cabinets[0].id,'product_id':self.replacement.id,
            'quantity':2,'unit':'pcs','unit_purchase_price':17})
        row.unlink()
        self.assertEqual(cabinets[0].sab_material_current_ek,34)
        self.assertEqual(cabinets[0].sab_material_calculated_ek,60)

    def test_27_lv_reference_is_copied_from_generated_offer_position(self):
        lv=self.env['sale.order'].create({'partner_id':self.partner.id,'sab_project_id':self.project.id,
            'sab_calculation_source':'lv','sab_calculation_line_ids':[Command.create({
                'calculation_item_id':self.item.id,'quantity':1,'lv_position':'1.1.1'})]})
        lv.action_sab_release_offer()
        cabinets=self.cabinets(self.order())
        self.assertEqual(set(cabinets.mapped('line_ids.sab_lv_position')),{'1.1.1'})

    def test_28_after_handover_open_requirement_tracks_revised_cabinet(self):
        order=self.order();cabinets=self.cabinets(order);package=self.package(order,cabinets)
        action=package.action_release_for_purchase()
        self.assertEqual(action['res_model'],'sab.bom.material.group')
        wizard=self.edit(package.sab_material_group_ids)
        first=wizard.line_ids.filtered(lambda r:r.cabinet_bom_id==cabinets[0])
        first.quantity=9;self.apply(wizard)
        req=package.purchase_requirement_ids.filtered(lambda r:r.source_cabinet_bom_id==cabinets[0])
        self.assertEqual(req.quantity,9)
        with self.assertRaises(ValidationError),self.env.cr.savepoint():req.action_create_purchase_orders()
        cabinets[0].action_release()
        self.assertFalse(package.sab_material_recheck_required)
        self.assertEqual(package.sab_material_current_ek,150)

    def test_29_reservations_are_released_and_rebuilt_after_technical_review(self):
        self.env['sab.stock.movement'].create({'product_id':self.product.id,
            'odoo_product_id':self.product.odoo_product_id.id,'movement_type':'receipt',
            'quantity':20,'unit':'pcs','unit_cost':10})
        order=self.order();cabinets=self.cabinets(order);package=self.package(order,cabinets)
        package.action_release_for_purchase()
        wizard=self.edit(package.sab_material_group_ids)
        first=wizard.line_ids.filtered(lambda r:r.cabinet_bom_id==cabinets[0])
        req=package.purchase_requirement_ids.filtered(lambda r:r.source_cabinet_bom_id==cabinets[0])
        self.assertEqual(req.project_reserved_quantity,6)
        first.quantity=9;self.apply(wizard)
        req.invalidate_recordset()
        self.assertEqual(req.project_reserved_quantity,0)
        cabinets[0].action_release()
        req.invalidate_recordset()
        self.assertEqual(req.project_reserved_quantity,9)
