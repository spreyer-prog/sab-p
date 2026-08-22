from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabSchematicSwitchboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Schaltplan"})
        cls.project = cls.env["project.project"].create(
            {"name": "Projekt Schaltplan", "partner_id": cls.partner.id}
        )
        cls.normal_product = cls.env["sab.product"].create(
            {
                "name": "Leistungsschalter",
                "manufacturer_article_number": "LS-100",
                "price_mode": "fixed",
                "fixed_purchase_price": 100.0,
            }
        )
        cls.aux_product = cls.env["sab.product"].create(
            {
                "name": "Hilfsmaterial Verdrahtung",
                "manufacturer_article_number": "HILF-100",
                "price_mode": "fixed",
                "fixed_purchase_price": 5.0,
            }
        )
        cls.item_known = cls.env["sab.calculation.item"].create(
            {
                "name": "Abgang bekannt",
                "quotation_text": "Abgang Leistungsschalter",
                "product_line_ids": [
                    (
                        0,
                        0,
                        {
                            "position_type": "normal",
                            "product_id": cls.normal_product.id,
                            "quantity": 2.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "position_type": "auxiliary_material",
                            "product_id": cls.aux_product.id,
                            "quantity": 1.0,
                        },
                    ),
                ],
            }
        )
        cls.item_new = cls.env["sab.calculation.item"].create(
            {
                "name": "Neuer Abgang",
                "quotation_text": "Neuer Abgang",
                "product_line_ids": [
                    (
                        0,
                        0,
                        {
                            "position_type": "normal",
                            "product_id": cls.normal_product.id,
                            "quantity": 1.0,
                        },
                    )
                ],
            }
        )

    def _order(self, source="lv", project=None):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": (project or self.project).id,
                "sab_calculation_source": source,
            }
        )

    def _prepare_priced_lv(self):
        order = self._order("lv")
        line = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 1.0,
            }
        )
        line.write({"lv_position": "01.01.03"})
        order.action_sab_release_offer()
        order.write({"state": "sent"})
        return order

    def test_schematic_without_prior_lv_is_allowed_and_has_no_lv_ntg(self):
        project = self.env["project.project"].create(
            {"name": "Projekt ohne LV", "partner_id": self.partner.id}
        )
        order = self._order("schematic", project=project)
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "UV DIREKT",
                "sequence": 10,
            }
        )
        section = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "section",
                "description": "Bauteil ohne LV",
                "lv_position": "01.01.01",
                "sequence": 20,
            }
        )
        child = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 1.0,
                "sequence": 30,
            }
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "section_end", "sequence": 40}
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet_end", "sequence": 50}
        )
        order.sab_calculation_line_ids._normalize_section_membership()

        self.assertEqual(section.parent_cabinet_id, cabinet)
        self.assertFalse(section.lv_position)
        self.assertFalse(section.is_ntg)
        self.assertFalse(child.lv_position)
        self.assertFalse(child.is_ntg)
        self.assertFalse(
            self.env["sab.project.lv.mapping"].search(
                [("project_id", "=", project.id)]
            )
        )
        order.action_sab_release_offer()
        self.assertEqual(order.sab_offer_release_state, "released")
        self.assertFalse(
            self.env["sab.project.lv.mapping"].search(
                [("project_id", "=", project.id)]
            )
        )

    def test_lv_offer_requires_position_before_release(self):
        project = self.env["project.project"].create(
            {"name": "Projekt LV Pflicht", "partner_id": self.partner.id}
        )
        order = self._order("lv", project=project)
        line = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 1.0,
            }
        )
        self.assertFalse(line.lv_position)
        with self.assertRaisesRegex(ValidationError, "LV-Nummer"):
            order.action_sab_release_offer()
        line.write({"lv_position": "02.03.04"})
        order.action_sab_release_offer()
        self.assertEqual(order.sab_offer_release_state, "released")

    def test_schematic_reuses_lv_and_new_position_becomes_ntg(self):
        self._prepare_priced_lv()
        order = self._order("schematic")
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "QV1",
                "sequence": 10,
            }
        )
        known = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 1.0,
                "sequence": 20,
            }
        )
        new = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_new.id,
                "quantity": 1.0,
                "sequence": 30,
            }
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet_end", "sequence": 40}
        )
        order.sab_calculation_line_ids._normalize_section_membership()

        self.assertEqual(known.lv_position, "01.01.03")
        self.assertFalse(known.is_ntg)
        self.assertTrue(new.lv_position.startswith("NTG "))
        self.assertTrue(new.is_ntg)
        self.assertEqual(known.parent_cabinet_id, cabinet)
        self.assertEqual(new.parent_cabinet_id, cabinet)
        self.assertFalse(known.parent_section_id)
        self.assertFalse(new.parent_section_id)
        self.assertAlmostEqual(
            cabinet.cabinet_total,
            known.recommended_net_price + new.recommended_net_price,
        )

    def test_component_children_share_one_lv_position_and_receive_no_own_ntg(self):
        self._prepare_priced_lv()
        order = self._order("schematic")
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "UV1",
                "sequence": 10,
            }
        )
        section = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "section",
                "description": "Bauteil 1",
                "lv_position": "01.01.02",
                "sequence": 20,
            }
        )
        known_child = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 1.0,
                "sequence": 30,
            }
        )
        new_child = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_new.id,
                "quantity": 2.0,
                "sequence": 40,
            }
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "section_end", "sequence": 50}
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet_end", "sequence": 60}
        )
        order.sab_calculation_line_ids._normalize_section_membership()

        self.assertEqual(section.parent_cabinet_id, cabinet)
        for child in known_child | new_child:
            self.assertEqual(child.parent_section_id, section)
            self.assertEqual(child.parent_cabinet_id, cabinet)
            self.assertEqual(child.lv_position, "01.01.02")
            self.assertFalse(child.is_ntg)
            self.assertTrue(child.lv_position_locked)

        self.assertFalse(
            self.env["sab.project.lv.mapping"].search(
                [
                    ("project_id", "=", self.project.id),
                    ("calculation_item_id", "=", self.item_new.id),
                ]
            )
        )

    def test_new_schematic_component_receives_one_ntg_for_whole_component(self):
        self._prepare_priced_lv()
        order = self._order("schematic")
        self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "UV2",
                "sequence": 10,
            }
        )
        section = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "section",
                "description": "Neues Bauteil",
                "sequence": 20,
            }
        )
        child = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_new.id,
                "quantity": 1.0,
                "sequence": 30,
            }
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "section_end", "sequence": 40}
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet_end", "sequence": 50}
        )
        order.sab_calculation_line_ids._normalize_section_membership()

        self.assertTrue(section.lv_position.startswith("NTG "))
        self.assertTrue(section.is_ntg)
        self.assertEqual(child.lv_position, section.lv_position)
        self.assertTrue(child.is_ntg)
        self.assertFalse(
            self.env["sab.project.lv.mapping"].search(
                [
                    ("project_id", "=", self.project.id),
                    ("calculation_item_id", "=", self.item_new.id),
                ]
            )
        )

    def test_bom_only_from_schematic_and_excludes_auxiliary_material(self):
        lv_order = self._prepare_priced_lv()
        lv_order.write({"state": "sale"})
        with self.assertRaises(ValidationError):
            lv_order.action_generate_sab_bom()

        order = self._order("schematic")
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "UV1",
                "sequence": 10,
            }
        )
        item_line = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item_known.id,
                "quantity": 3.0,
                "sequence": 20,
            }
        )
        self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet_end", "sequence": 30}
        )
        order.sab_calculation_line_ids._normalize_section_membership()
        self.assertEqual(item_line.parent_cabinet_id, cabinet)
        self.assertEqual(len(item_line.component_snapshot_ids), 1)
        self.assertEqual(item_line.component_snapshot_ids.product_id, self.normal_product)

        order.action_sab_release_offer()
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
        self.assertEqual(
            cabinet_bom.line_ids.odoo_product_id,
            self.normal_product.odoo_product_id,
        )
        self.assertAlmostEqual(cabinet_bom.line_ids.quantity, 6.0)
        self.assertAlmostEqual(total_bom.line_ids.quantity, 6.0)
