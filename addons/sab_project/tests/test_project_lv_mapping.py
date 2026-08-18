from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabProjectLvMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde LV-Mapping"})
        cls.project = cls.env["project.project"].create({
            "name": "Projekt LV-Mapping",
            "partner_id": cls.partner.id,
        })
        cls.item = cls.env["sab.calculation.item"].create({
            "name": "Kalkulationsartikel LV-Mapping",
            "quotation_text": "Kalkulationsartikel für projektweite LV-Position",
        })

    def _order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": self.project.id,
            "sab_calculation_source": "lv",
        })

    def test_first_draft_lv_position_is_remembered_in_next_offer_and_locked(self):
        first = self._order()
        first_line = self.env["sab.offer.calculation.line"].create({
            "order_id": first.id,
            "calculation_item_id": self.item.id,
            "quantity": 1.0,
        })
        self.assertFalse(first_line.lv_position_locked)

        first_line.write({"lv_position": "01.01.03"})
        mapping = self.env["sab.project.lv.mapping"].search([
            ("project_id", "=", self.project.id),
            ("calculation_item_id", "=", self.item.id),
        ])
        self.assertEqual(len(mapping), 1)
        self.assertEqual(mapping.position_code, "01.01.03")
        self.assertEqual(mapping.first_order_id, first)
        self.assertTrue(first_line.lv_position_locked)

        second = self._order()
        second_line = self.env["sab.offer.calculation.line"].create({
            "order_id": second.id,
            "calculation_item_id": self.item.id,
            "quantity": 2.0,
        })
        self.assertEqual(second_line.lv_position, "01.01.03")
        self.assertTrue(second_line.lv_position_locked)

        with self.assertRaises(ValidationError):
            second_line.write({"lv_position": "99.99.99"})

    def test_mapping_also_applies_to_item_inside_component_section(self):
        first = self._order()
        section = self.env["sab.offer.calculation.line"].create({
            "order_id": first.id,
            "line_type": "section",
            "description": "Bauteil 1",
            "quantity": 1.0,
            "sequence": 10,
        })
        first_line = self.env["sab.offer.calculation.line"].create({
            "order_id": first.id,
            "calculation_item_id": self.item.id,
            "quantity": 1.0,
            "sequence": 20,
            "lv_position": "01.01.04",
        })
        first_line._normalize_section_membership()
        self.assertEqual(first_line.parent_section_id, section)

        second = self._order()
        second_section = self.env["sab.offer.calculation.line"].create({
            "order_id": second.id,
            "line_type": "section",
            "description": "Bauteil 2",
            "quantity": 1.0,
            "sequence": 10,
        })
        second_line = self.env["sab.offer.calculation.line"].create({
            "order_id": second.id,
            "calculation_item_id": self.item.id,
            "quantity": 1.0,
            "sequence": 20,
        })
        second_line._normalize_section_membership()
        self.assertEqual(second_line.parent_section_id, second_section)
        self.assertEqual(second_line.lv_position, "01.01.04")
        self.assertTrue(second_line.lv_position_locked)
