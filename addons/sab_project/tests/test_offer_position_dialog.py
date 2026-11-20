"""Odoo integration tests; requires an actual Odoo 19 database."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from lxml import etree


class TestSabOfferPositionDialog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'LV picker customer'})
        cls.project = cls.env['project.project'].create({'name': 'LV picker project', 'partner_id': cls.customer.id})
        cls.item = cls.env['sab.calculation.item'].create({
            'name': 'Picker montage', 'quotation_text': 'Montage test', 'legacy_time_minutes': 30,
            'mechanical_factor': 100, 'wiring_factor': 0, 'testing_factor': 0,
        })

    def order(self, **values):
        defaults = {'partner_id': self.customer.id, 'sab_project_id': self.project.id,
            'sab_calculation_source': 'lv', 'sab_hourly_rate': 80, 'sab_time_factor': 1.25,
            'sab_difficulty_factor': 1, 'sab_packaging_factor': 1.03, 'sab_skonto_factor': 1.03,
            'sab_margin_factor': 1.35, 'sab_rebate_factor': 1.125}
        defaults.update(values)
        return self.env['sale.order'].create(defaults)

    def line(self, order, code=False, mode='auto', **values):
        defaults = {'order_id': order.id, 'calculation_item_id': self.item.id,
                    'lv_position': code, 'sab_position_choice': mode, 'quantity': 3}
        defaults.update(values)
        return self.env['sab.offer.calculation.line'].create(defaults)

    def options(self, order, **values):
        args = {'order_id': order.id, 'calculation_item_id': self.item.id}
        args.update(values)
        return self.env['sab.offer.calculation.line'].sab_position_dialog_options(args)

    def test_options_show_each_code_not_one_row_per_article(self):
        first = self.order()
        self.line(first, '1.1.1'); self.line(first, '1.1.4')
        second = self.order()
        result = self.options(second)
        self.assertEqual([row['code'] for row in result['positions']], ['1.1.1', '1.1.4'])
        self.assertTrue(result['can_new_lv']); self.assertTrue(result['can_new_ntg'])
        self.assertEqual(result['positions'][0]['price'], 80.56)

    def test_options_read_does_not_create_lines_or_prices(self):
        first = self.order(); self.line(first, '1.1.1'); second = self.order()
        models = ('sale.order', 'sab.offer.calculation.line', 'sab.project.lv.mapping', 'sab.project.position.price')
        before = tuple(self.env[name].sudo().search_count([]) for name in models)
        self.options(second)
        after = tuple(self.env[name].sudo().search_count([]) for name in models)
        self.assertEqual(after, before)

    def test_unsaved_order_can_read_existing_positions(self):
        first = self.order(); self.line(first, '1.1.1')
        result = self.env['sab.offer.calculation.line'].sab_position_dialog_options({
            'project_id': self.project.id, 'company_id': first.company_id.id,
            'partner_id': self.customer.id, 'calculation_item_id': self.item.id,
        })
        self.assertEqual(result['positions'][0]['code'], '1.1.1')
        self.assertTrue(result['can_new_ntg'])

    def test_pending_onchange_does_not_choose_unique_source(self):
        first = self.order(); self.line(first, '1.1.1'); second = self.order()
        virtual = self.env['sab.offer.calculation.line'].new({
            'order_id': second.id, 'line_type': 'item', 'calculation_item_id': self.item.id,
            'sab_position_choice': 'pending', 'quantity': 3,
        })
        virtual._onchange_sab_saved_project_position()
        self.assertFalse(virtual.lv_position)
        self.assertFalse(virtual.is_ntg)

    def test_pending_save_waits_for_choice_instead_of_new_ntg(self):
        first = self.order(); self.line(first, '1.1.1'); second = self.order()
        target = self.line(second, mode='pending')
        self.assertFalse(target.lv_position)
        self.assertFalse(target.sab_project_price_bound)
        target.write({'lv_position': '1.1.1', 'is_ntg': False, 'sab_position_choice': 'existing'})
        self.assertEqual(target.lv_position, '1.1.1')
        self.assertEqual(target.recommended_net_price, 241.68)
        self.assertEqual(len(second.sab_calculation_line_ids), 1)

    def test_choose_second_position_keeps_quantity_and_own_text(self):
        first = self.order(); self.line(first, '1.1.1'); self.line(first, '1.1.4')
        second = self.order()
        target = self.line(second, mode='pending', description='Eigener Text', quantity=4)
        target.write({'sab_position_choice': 'existing', 'lv_position': '1.1.4', 'is_ntg': False})
        self.assertEqual(target.quantity, 4)
        self.assertEqual(target.description, 'Eigener Text')
        self.assertEqual(target.recommended_net_price, 322.24)
        self.assertEqual(len(second.sab_calculation_line_ids), 1)

    def test_explicit_new_ntg_even_when_article_has_existing_lv(self):
        first = self.order(); self.line(first, '1.1.1')
        second = self.order(); target = self.line(second, mode='new_ntg')
        self.assertEqual(target.lv_position, 'NTG 1')
        self.assertTrue(target.is_ntg)
        target.quantity = 4
        self.assertEqual(target.lv_position, 'NTG 1')
        self.assertEqual(target.sab_position_choice, 'existing')

    def test_pending_saved_row_can_choose_new_ntg(self):
        first = self.order(); self.line(first, '1.1.1'); first.action_sab_release_offer()
        second = self.order(); target = self.line(second, mode='pending')
        target.write({'sab_position_choice': 'new_ntg', 'lv_position': False, 'is_ntg': False})
        self.assertEqual(target.lv_position, 'NTG 1')
        self.assertEqual(first.sab_calculation_line_ids.lv_position, '1.1.1')

    def test_explicit_new_lv_does_not_reuse_first_article_code(self):
        first = self.order(); self.line(first, '1.1.1'); second = self.order()
        target = self.line(second, code='1.1.4', mode='new_lv')
        self.assertEqual(target.lv_position, '1.1.4'); self.assertFalse(target.is_ntg)

    def test_new_lv_requires_unused_number(self):
        first = self.order(); self.line(first, '1.1.1'); second = self.order()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.line(second, code='1.1.1', mode='new_lv')

    def test_cancelled_choice_can_be_completed_by_manual_lv_input(self):
        target = self.line(self.order(), mode='pending')
        target.write({'lv_position': '3.2.1'})
        self.assertEqual(target.lv_position, '3.2.1')
        self.assertEqual(target.sab_position_choice, 'existing')

    def test_first_offer_does_not_allow_new_ntg(self):
        order = self.order()
        self.assertFalse(self.options(order)['can_new_ntg'])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.line(order, mode='new_ntg')

    def test_schematic_offer_has_same_choices(self):
        first = self.order(); self.line(first, '1.1.1'); self.line(first, '1.1.4')
        schematic = self.order(sab_calculation_source='schematic')
        self.assertEqual(len(self.options(schematic)['positions']), 2)
        target = self.line(schematic, mode='new_ntg')
        self.assertTrue(target.is_ntg)

    def test_component_children_keep_component_position(self):
        first = self.order(); self.line(first, '1.1.1')
        second = self.order()
        section = self.env['sab.offer.calculation.line'].create({
            'order_id': second.id, 'line_type': 'section', 'description': 'Existing Bauteil',
            'lv_position': '2.1', 'sequence': 10,
        })
        target = self.line(second, mode='pending', parent_section_id=section.id, sequence=20)
        self.assertEqual(target.lv_position, '2.1')
        self.assertFalse(target.is_ntg)
        self.assertFalse(target.sab_project_price_bound)
        with self.assertRaises(ValidationError):
            self.options(second, line_id=target.id)

    def test_other_customer_positions_not_exposed(self):
        first = self.order(); self.line(first, '1.1.1')
        other = self.env['res.partner'].create({'name': 'Other picker customer'})
        target = self.order(partner_id=other.id)
        self.assertFalse(self.options(target)['positions'])

    def test_view_uses_unsaved_client_picker_not_object_button(self):
        result = self.env['sale.order'].get_view(view_id=self.env.ref('sale.view_order_form').id, view_type='form')
        arch = etree.fromstring(result['arch'].encode())
        root = arch.xpath("//field[@name='sab_calculation_line_ids']/list")[0]
        self.assertFalse(root.xpath(".//button[@name='action_sab_choose_lv_position']"))
        self.assertEqual(root.xpath("./field[@name='sab_position_choice']/@widget"), ['sab_position_picker'])
        self.assertEqual(root.xpath("./field[@name='calculation_item_id']/@widget"), ['sab_position_article'])
