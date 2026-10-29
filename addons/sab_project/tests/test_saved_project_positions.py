from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from ..models.sab_offer_draft_positions import choose_position


class TestSavedProjectPositions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Saved LV test'})
        cls.project = cls.env['project.project'].create({'name': 'Saved LV project', 'partner_id': cls.partner.id})
        cls.item = cls.env['sab.calculation.item'].create({'name': 'Saved LV item', 'quotation_text': 'Saved LV item'})
        cls.new_item = cls.env['sab.calculation.item'].create({'name': 'New LV item', 'quotation_text': 'New LV item'})

    def order(self, project=None):
        return self.env['sale.order'].create({'partner_id': self.partner.id,
            'sab_project_id': (project or self.project).id, 'sab_calculation_source': 'lv'})

    def line(self, order, item=None, code=False, quantity=1):
        return self.env['sab.offer.calculation.line'].create({'order_id': order.id,
            'calculation_item_id': (item or self.item).id, 'lv_position': code,
            'quantity': quantity})

    def test_unique_saved_draft_is_reused_without_freezing_source(self):
        first = self.order(); source = self.line(first, code='1.1.1')
        target = self.line(self.order())
        self.assertEqual(target.lv_position, '1.1.1')
        self.assertFalse(target.is_ntg)
        self.assertFalse(source.lv_position_locked)
        self.assertFalse(self.env['sab.project.lv.mapping'].search([('project_id', '=', self.project.id)]))
        self.assertEqual(first.sab_offer_release_state, 'draft')

    def test_sidebar_exposes_saved_draft_and_freeze_replaces_duplicate(self):
        first = self.order(); source = self.line(first, code='1.1.1')
        second = self.order()
        entries = second.sab_offer_reuse_payload()['lv_positions']
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['id'], -source.id)
        self.assertEqual(entries[0]['position_status'], 'Entwurf')
        first.action_sab_release_offer()
        entries = second.sab_offer_reuse_payload()['lv_positions']
        self.assertEqual(len(entries), 1)
        self.assertGreater(entries[0]['id'], 0)
        self.assertEqual(entries[0]['position_status'], 'Festgeschrieben')

    def test_multiple_positions_require_choice_not_new_ntg(self):
        first = self.order(); a = self.line(first, code='1.1.1'); b = self.line(first, code='1.1.2')
        second = self.order(); target = self.line(second, quantity=4)
        self.assertFalse(target.lv_position)
        self.assertFalse(target.is_ntg)
        self.assertTrue(target.sab_lv_choice_required)
        before = (target.unit_recommended_net_price, target.recommended_net_price)
        second.sab_offer_add_reuse_entry('lv', -b.id)
        self.assertEqual(target.lv_position, '1.1.2')
        self.assertEqual(target.quantity, 4)
        self.assertEqual(len(second.sab_calculation_line_ids), 1)
        self.assertEqual((target.unit_recommended_net_price, target.recommended_net_price), before)
        self.assertEqual(a.lv_position, '1.1.1')

    def test_choice_dialog_can_select_an_exact_source(self):
        first = self.order(); a = self.line(first, code='1.1.1'); self.line(first, code='1.1.2')
        target = self.line(self.order())
        action = target.action_sab_choose_lv_position()
        self.assertEqual(action['target'], 'new')
        a.with_context(sab_lv_target_line_id=target.id).action_sab_apply_lv_choice()
        self.assertEqual(target.lv_position, '1.1.1')

    def test_new_item_in_suboffer_gets_ntg_before_original_release(self):
        first = self.order(); self.line(first, code='1.1.1')
        target = self.line(self.order(), item=self.new_item)
        self.assertEqual(target.lv_position, 'NTG 1')
        self.assertTrue(target.is_ntg)
        target.quantity = 5
        self.assertEqual(target.lv_position, 'NTG 1')
        repeat = self.line(target.order_id, item=self.new_item)
        self.assertEqual(repeat.lv_position, 'NTG 1')
        self.assertFalse(self.env['sab.project.lv.mapping'].search([('project_id', '=', self.project.id)]))

    def test_first_lv_and_empty_predecessor_do_not_invent_ntg(self):
        self.order()
        target = self.line(self.order())
        self.assertFalse(target.lv_position)
        self.assertFalse(target.is_ntg)

    def test_other_projects_and_cancelled_drafts_are_not_sources(self):
        first = self.order(); self.line(first, code='1.1.1'); first.state = 'cancel'
        other = self.env['project.project'].create({'name': 'Unrelated project', 'partner_id': self.partner.id})
        other_order = self.order(other); self.line(other_order, code='9.9.9')
        second = self.order(); target = self.line(second)
        self.assertFalse(target.lv_position)
        self.assertFalse(second.sab_offer_reuse_payload()['lv_positions'])
        foreign = other_order.sab_calculation_line_ids
        with self.assertRaises(ValidationError):
            second.sab_offer_add_reuse_entry('lv', -foreign.id)

    def test_two_different_lv_positions_for_one_article_can_be_released(self):
        first = self.order(); self.line(first, code='1.1.1'); self.line(first, code='1.1.2')
        first.action_sab_release_offer()
        mappings = self.env['sab.project.lv.mapping'].search([('project_id', '=', self.project.id)])
        self.assertEqual(set(mappings.mapped('position_code')), {'1.1.1', '1.1.2'})
        second = self.order(); target = self.line(second)
        self.assertFalse(target.lv_position)
        selected = mappings.filtered(lambda m: m.position_code == '1.1.2')
        second.sab_offer_add_reuse_entry('lv', selected.id)
        self.assertEqual(target.lv_position, '1.1.2')
        with self.assertRaises(ValidationError):
            target.write({'lv_position': '7.7.7'})

    def test_saved_draft_changes_do_not_rewrite_existing_suboffer(self):
        first = self.order(); source = self.line(first, code='1.1.1')
        target = self.line(self.order()); old_price = target.unit_recommended_net_price
        source.lv_position = '1.1.2'
        self.assertEqual(target.lv_position, '1.1.1')
        self.assertEqual(target.unit_recommended_net_price, old_price)

    def test_release_guard_survives_sidebar_and_choice_actions(self):
        first = self.order(); source = self.line(first, code='1.1.1')
        target_order = self.order(); self.line(target_order)
        target_order.action_sab_release_offer()
        with self.assertRaises(ValidationError):
            target_order.sab_offer_add_reuse_entry('lv', -source.id)

    def test_onchange_suggests_but_does_not_create_mapping(self):
        first = self.order(); self.line(first, code='1.1.1')
        second = self.order()
        virtual = self.env['sab.offer.calculation.line'].new({'order_id': second.id,
            'line_type': 'item', 'calculation_item_id': self.item.id, 'quantity': 1})
        virtual._onchange_sab_saved_project_position()
        self.assertEqual(virtual.lv_position, '1.1.1')
        self.assertFalse(self.env['sab.project.lv.mapping'].search([('project_id', '=', self.project.id)]))

    def test_choice_helper_never_chooses_first_of_several(self):
        self.assertIsNone(choose_position([('1.1.1', False), ('1.1.2', False)]))
        self.assertEqual(choose_position([('1.1.1', False)] * 4), ('1.1.1', False))
        self.assertEqual(choose_position([('NTG 1', True)]), ('NTG 1', True))
