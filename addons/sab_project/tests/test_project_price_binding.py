"""Integration tests: these require an actual Odoo 19 test database."""
from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestSabProjectPriceBinding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'Binding test customer'})
        cls.project = cls.env['project.project'].create({'name': 'Binding test project', 'partner_id': cls.customer.id})
        cls.item = cls.env['sab.calculation.item'].create({
            'name': 'Binding 30 minutes', 'quotation_text': 'Binding test',
            'legacy_time_minutes': 30, 'mechanical_factor': 100,
            'wiring_factor': 0, 'testing_factor': 0,
        })
        cls.factors = {
            'sab_hourly_rate': 80.0, 'sab_material_factor': 1.0,
            'sab_aux_material_factor': 1.15, 'sab_time_factor': 1.25,
            'sab_difficulty_factor': 1.0, 'sab_packaging_factor': 1.03,
            'sab_skonto_factor': 1.03, 'sab_margin_factor': 1.35,
            'sab_rebate_factor': 1.125, 'sab_vat_rate': 19.0,
        }

    def order(self, **overrides):
        values = dict(self.factors, partner_id=self.customer.id,
                      sab_project_id=self.project.id, sab_calculation_source='lv',
                      currency_id=self.env.ref('base.EUR').id)
        values.update(overrides)
        return self.env['sale.order'].create(values)

    def line(self, order, code='1.1.1', item=None, quantity=1):
        return self.env['sab.offer.calculation.line'].create({
            'order_id': order.id, 'calculation_item_id': (item or self.item).id,
            'quantity': quantity, 'lv_position': code,
        })

    def test_first_normal_save_captures_project_unit_price(self):
        order = self.order(); line = self.line(order)
        self.assertTrue(line.sab_project_price_bound)
        self.assertEqual(line.sab_project_unit_price, 80.56)
        self.assertEqual(order.sab_offer_release_state, 'draft')
        self.assertFalse(self.env['sab.project.lv.mapping'].search([('project_id', '=', self.project.id)]))

    def test_new_occurrence_ignores_changed_master_time_and_target_factors(self):
        first = self.order(); source = self.line(first)
        self.item.legacy_time_minutes = 60
        target_order = self.order(sab_hourly_rate=140, sab_margin_factor=2)
        target = self.line(target_order, code=False, quantity=3)
        self.assertEqual(target.lv_position, '1.1.1')
        self.assertEqual(target.unit_total_minutes, 60)
        self.assertEqual(target.unit_recommended_net_price, 80.56)
        self.assertEqual(target.recommended_net_price, 241.68)
        self.assertEqual(source.unit_total_minutes, 30)
        self.assertEqual(source.unit_recommended_net_price, 80.56)

    def test_factor_edit_does_not_reprice_existing_line_but_new_code_uses_it(self):
        order = self.order(); old = self.line(order)
        order.write({'sab_hourly_rate': 160})
        self.assertEqual(old.unit_recommended_net_price, 80.56)
        new = self.line(order, code='1.1.2')
        self.assertEqual(new.unit_recommended_net_price, 161.12)
        self.assertEqual(order.sab_offer_subtotal, 241.68)

    def test_quantity_zero_fraction_and_roundtrip_keep_fixed_unit(self):
        line = self.line(self.order())
        for quantity in (3, 0, 4, 0.25, 1):
            line.quantity = quantity
            self.assertEqual(line.unit_recommended_net_price, 80.56)
            self.assertEqual(line.recommended_net_price, line.currency_id.round(80.56 * quantity))

    def test_zero_is_a_real_bound_price(self):
        self.item.legacy_time_minutes = 0
        first = self.line(self.order())
        self.assertTrue(first.sab_project_price_bound)
        self.assertEqual(first.sab_project_unit_price, 0)
        self.item.legacy_time_minutes = 60
        repeat = self.line(self.order(), code=False)
        self.assertTrue(repeat.sab_project_price_bound)
        self.assertEqual(repeat.unit_recommended_net_price, 0)

    def test_other_project_has_independent_price(self):
        source = self.line(self.order())
        other = self.env['project.project'].create({'name': 'Other price project', 'partner_id': self.customer.id})
        target = self.line(self.order(sab_project_id=other.id, sab_hourly_rate=160))
        self.assertEqual(target.unit_recommended_net_price, 161.12)
        self.assertEqual(source.unit_recommended_net_price, 80.56)

    def test_other_customer_is_not_assigned_first_customer_price(self):
        self.line(self.order())
        customer = self.env['res.partner'].create({'name': 'Different price customer'})
        target = self.line(self.order(partner_id=customer.id, sab_hourly_rate=160))
        self.assertEqual(target.unit_recommended_net_price, 161.12)

    def test_currency_mismatch_is_not_silent_conversion(self):
        self.line(self.order())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.line(self.order(currency_id=self.env.ref('base.USD').id))

    def test_copy_and_suboffer_keep_price_after_master_change(self):
        order = self.order(); source = self.line(order, quantity=3)
        self.item.legacy_time_minutes = 60
        copied = self.env['sale.order'].browse(order.action_create_sab_revision()['res_id'])
        child = self.env['sale.order'].browse(order.action_sab_create_suboffer()['res_id'])
        reused = self.line(child, code=False, quantity=4)
        self.assertEqual(copied.sab_calculation_line_ids.unit_recommended_net_price, 80.56)
        self.assertEqual(copied.sab_calculation_line_ids.recommended_net_price, 241.68)
        self.assertEqual(reused.recommended_net_price, 322.24)
        self.assertEqual(source.recommended_net_price, 241.68)

    def test_ntg_price_is_preserved_on_further_reuse(self):
        self.line(self.order())
        new_item = self.item.copy({'name': 'New NTG article', 'legacy_time_minutes': 60})
        second = self.order(); ntg = self.line(second, code=False, item=new_item)
        self.assertEqual(ntg.lv_position, 'NTG 1')
        price = ntg.unit_recommended_net_price
        new_item.legacy_time_minutes = 120
        repeated = self.line(self.order(sab_hourly_rate=200), code=False, item=new_item)
        self.assertEqual(repeated.lv_position, 'NTG 1')
        self.assertEqual(repeated.unit_recommended_net_price, price)

    def test_direct_snapshot_write_and_fake_context_are_rejected(self):
        line = self.line(self.order())
        for values in ({'sab_project_unit_price': 1}, {'sab_project_price_bound': False},
                       {'unit_recommended_net_price': 1}, {'recommended_net_price': 1}):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                line.with_context(sab_offer_release_write=True, skip_section_normalize=True).write(values)

    def test_incoming_snapshot_does_not_override_server_price(self):
        source = self.line(self.order())
        order = self.order()
        target = self.env['sab.offer.calculation.line'].create({
            'order_id': order.id, 'calculation_item_id': self.item.id,
            'quantity': 1, 'lv_position': '1.1.1',
            'sab_project_price_bound': True, 'sab_project_unit_price': 1,
            'sab_project_price_currency_id': order.currency_id.id,
        })
        self.assertEqual(target.sab_project_unit_price, source.sab_project_unit_price)

    def test_bound_price_survives_source_line_deletion(self):
        source = self.line(self.order()); target = self.line(self.order())
        source.unlink()
        target.quantity = 3
        self.assertEqual(target.unit_recommended_net_price, 80.56)
        self.assertEqual(target.recommended_net_price, 241.68)

    def test_existing_draft_renumber_does_not_rewrite_suboffer(self):
        source = self.line(self.order()); target = self.line(self.order())
        source.lv_position = '1.1.2'
        self.assertEqual(source.unit_recommended_net_price, 80.56)
        self.assertEqual(target.lv_position, '1.1.1')
        self.assertEqual(target.unit_recommended_net_price, 80.56)

    def test_bound_scope_cannot_be_changed(self):
        order = self.order(); self.line(order)
        other = self.env['res.partner'].create({'name': 'Scope change customer'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.partner_id = other
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.currency_id = self.env.ref('base.USD')

    def test_bound_direct_article_cannot_be_silently_replaced(self):
        line = self.line(self.order())
        other = self.item.copy({'name': 'Replacement'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.calculation_item_id = other
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.action_refresh_from_calculation_item()

    def test_preview_reads_fixed_price_without_database_writes(self):
        source = self.line(self.order())
        self.item.legacy_time_minutes = 60
        order = self.order(sab_hourly_rate=160)
        count = self.env['sab.offer.calculation.line'].search_count([])
        form = Form(order, view='sale.view_order_form')
        with form.sab_calculation_line_ids.new() as row:
            row.calculation_item_id = self.item
            row.quantity = 3
            self.assertEqual(row.lv_position, '1.1.1')
            self.assertEqual(row.unit_recommended_net_price, 80.56)
            self.assertEqual(row.recommended_net_price, 241.68)
        self.assertEqual(self.env['sab.offer.calculation.line'].search_count([]), count)
        saved = form.save()
        self.assertEqual(saved.sab_calculation_line_ids.unit_recommended_net_price, 80.56)
        self.assertEqual(source.unit_recommended_net_price, 80.56)

    def test_customer_order_line_and_totals_match_fixed_price(self):
        first = self.order(); self.line(first)
        self.item.legacy_time_minutes = 60
        second = self.order(sab_margin_factor=2)
        target = self.line(second, code=False, quantity=3)
        sale_line = second.order_line.filtered('sab_generated_from_calculation')
        self.assertEqual(sale_line.price_unit, 80.56)
        self.assertEqual(sale_line.product_uom_qty, 3)
        self.assertEqual(target.recommended_net_price, 241.68)
        self.assertEqual(second.sab_offer_net_total, 241.68)

    def test_legacy_rounding_is_not_implicitly_migrated(self):
        line = self.line(self.order(sab_price_rounding_version='legacy'), quantity=3)
        self.assertFalse(line.sab_project_price_bound)
        self.assertEqual(line.recommended_net_price, 241.69)

    def test_bauteil_children_do_not_get_direct_article_position_binding(self):
        order = self.order()
        section = self.env['sab.offer.calculation.line'].create({
            'order_id': order.id, 'line_type': 'section', 'description': 'Assembly',
            'lv_position': '2.1', 'sequence': 10,
        })
        child = self.env['sab.offer.calculation.line'].create({
            'order_id': order.id, 'calculation_item_id': self.item.id,
            'parent_section_id': section.id, 'sequence': 20,
        })
        self.assertFalse(child.sab_project_price_bound)

    def test_registry_keeps_price_after_all_offer_rows_are_deleted(self):
        order = self.order(); source = self.line(order)
        source.unlink()
        self.item.legacy_time_minutes = 60
        target = self.line(self.order(), code='1.1.1')
        self.assertEqual(target.unit_recommended_net_price, 80.56)

    def test_public_registry_operations_are_rejected_even_with_sudo(self):
        self.line(self.order())
        prices = self.env['sab.project.position.price'].sudo().search([('project_id', '=', self.project.id)])
        self.assertEqual(len(prices), 1)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            prices.write({'unit_price': 1})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            prices.unlink()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['sab.project.position.price'].sudo().create({})

    def test_untouched_old_unit_first_price_is_not_silently_rewritten(self):
        source = self.line(self.order())
        target = self.line(self.order())
        # Simulate an inconsistent pre-feature stored row without calling the
        # protected public writer. Production code never performs this backfill.
        from odoo import models
        models.Model.write(target, {'sab_project_price_bound': False})
        # A direct stored-price discrepancy is intentionally made by SQL only
        # inside this test fixture, not by an installation/migration.
        target.flush_recordset()
        self.env.cr.execute('UPDATE sab_offer_calculation_line SET unit_recommended_net_price = 90 WHERE id = %s', [target.id])
        target.invalidate_recordset(['unit_recommended_net_price'])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            target.quantity = 3
        self.assertEqual(source.unit_recommended_net_price, 80.56)
