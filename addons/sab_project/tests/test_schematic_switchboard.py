from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabSchematicSwitchboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Schaltplan"})
        cls.project = cls.env["project.project"].create({
            "name": "Projekt Schaltplan",
            "partner_id": cls.partner.id,
        })
        cls.normal_product = cls.env["sab.product"].create({
            "name": "Leistungsschalter",
            "manufacturer_article_number": "LS-100",
            "price_mode": "fixed",
            "fixed_purchase_price": 100.0,
        })
        cls.aux_product = cls.env["sab.product"].create({
            "name": "Hilfsmaterial Verdrahtung",
            "manufacturer_article_number": "HILF-100",
            "price_mode": "fixed",
            "fixed_purchase_price": 5.0,
        })
        cls.item_known = cls.env["sab.calculation.item"].create({
            "name": "Abgang bekannt",
            "quotation_text": "Abgang Leistungsschalter",
            "product_line_ids": [
                (0, 0, {
                    "position_type": "normal",
                    "product_id": cls.normal_product.id,
                    "quantity": 2.0,
                }),
                (0, 0, {
                    "position_type": "auxiliary_material",
                    "product_id": cls.aux_product.id,
                    "quantity": 1.0,
                }),
            ],
        })
        cls.item_new = cls.env["sab.calculation.item"].create({
            "name": "Neuer Abgang",
            "quotation_text": "Neuer Abgang",
            "product_line_ids": [
                (0, 0, {
                    "position_type": "normal",
                    "product_id": cls.normal_product.id,
                    "quantity": 1.0,
                }),
            ],
        })

    def _order(self, source="lv"):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": self.project.id,
            "sab_calculation_source": source,
        })

    def _prepare_priced_lv(self):
        order = self._order("lv")
        line = self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "calculation_item_id": self.item_known.id,
            "quantity": 1.0,
        })
        line.write({"lv_position": "01.01.03"})
        order.write({"state": "sent"})
        return order

    def test_schematic_reuses_lv_and_new_position_becomes_ntg(self):
        self._prepare_priced_lv()
        order = self._order("schematic")
        cabinet = self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "line_type": "cabinet",
            "description": "QV1",
            "sequence": 10,
        })
        known = self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "calculation_item_id": self.item_known.id,
            "quantity": 1.0,
            "sequence": 20,
        })
        new = self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "calculation_item_id": self.item_new.id,
            "quantity": 1.0,
            "sequence": 30,
        })
        self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "line_type": "cabinet_end",
            "sequence": 40,
        })
        order.sab_calculation_line_ids._normalize_section_membership()

        self.assertEqual(known.lv_position, "01.01.03")
        self.assertFalse(known.is_ntg)
        self.assertTrue(new.lv_position.startswith("NTG "))
        self.assertTrue(new.is_ntg)
        self.assertEqual(known.parent_cabinet_id, cabinet)
        self.assertEqual(new.parent_cabinet_id, cabinet)
        self.assertAlmostEqual(cabinet.cabinet_total, known.recommended_net_price + new.recommended_net_price)

    def test_bom_only_from_schematic_and_excludes_auxiliary_material(self):
        lv_order = self._prepare_priced_lv()
        lv_order.write({"state": "sale"})
        with self.assertRaises(ValidationError):
            lv_order.action_generate_sab_bom()

        order = self._order("schematic")
        cabinet = self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "line_type": "cabinet",
            "description": "UV1",
            "sequence": 10,
        })
        item_line = self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "calculation_item_id": self.item_known.id,
            "quantity": 3.0,
            "sequence": 20,
        })
        self.env["sab.offer.calculation.line"].create({
            "order_id": order.id,
            "line_type": "cabinet_end",
            "sequence": 30,
        })
        order.sab_calculation_line_ids._normalize_section_membership()
        self.assertEqual(item_line.parent_cabinet_id, cabinet)
        self.assertEqual(len(item_line.component_snapshot_ids), 1)
        self.assertEqual(item_line.component_snapshot_ids.product_id, self.normal_product)

        order.write({"state": "sale"})
        action = order.action_generate_sab_bom()
        self.assertEqual(action["res_model"], "sab.project.bom")
        boms = order.sab_bom_ids
        self.assertEqual(len(boms), 2)
        cabinet_bom = boms.filtered(lambda bom: bom.bom_scope == "cabinet")
        total_bom = boms.filtered(lambda bom: bom.bom_scope == "total")
        self.assertEqual(cabinet_bom.cabinet_line_id, cabinet)
        self.assertEqual(len(cabinet_bom.line_ids), 1)
        self.assertEqual(len(total_bom.line_ids), 1)
        self.assertEqual(cabinet_bom.line_ids.product_id, self.normal_product)
        self.assertEqual(cabinet_bom.line_ids.odoo_product_id, self.normal_product.odoo_product_id)
        self.assertAlmostEqual(cabinet_bom.line_ids.quantity, 6.0)
        self.assertAlmostEqual(total_bom.line_ids.quantity, 6.0)

    def test_schematic_requires_priced_lv_offer(self):
        other_project = self.env["project.project"].create({
            "name": "Projekt ohne LV",
            "partner_id": self.partner.id,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": other_project.id,
            "sab_calculation_source": "schematic",
        })
        with self.assertRaises(ValidationError):
            self.env["sab.offer.calculation.line"].create({
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 1.0,
            })
