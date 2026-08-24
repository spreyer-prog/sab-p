from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabCalculationAuditAndBom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Stückliste"})
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Stückliste",
                "partner_id": cls.partner.id,
            }
        )
        cls.manufacturer = cls.env["sab.manufacturer"].create(
            {"name": "Hersteller Stückliste"}
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {"name": "Lieferant Stückliste"}
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "Stücklistenprodukt",
                "manufacturer_id": cls.manufacturer.id,
                "manufacturer_article_number": "BOM-100",
                "mechanical_time_minutes": 1.0,
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-BOM-100",
                "purchase_price": 5.0,
                "preferred": True,
            }
        )
        cls.calculation_item = cls.env["sab.calculation.item"].create(
            {
                "name": "Kalkulationsartikel Stückliste",
                "quotation_text": "Stücklistenartikel",
                "product_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "quantity": 2.0,
                            "unit": "pcs",
                        },
                    )
                ],
            }
        )

    def _order(self):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": self.project.id,
                "sab_calculation_source": "lv",
                "sab_calculation_line_ids": [
                    (
                        0,
                        0,
                        {
                            "calculation_item_id": self.calculation_item.id,
                            "quantity": 3.0,
                        },
                    )
                ],
            }
        )

    def _schematic_order(self):
        lv_order = self._order()
        lv_order.sab_calculation_line_ids.write({"lv_position": "01.01.03"})
        lv_order.action_sab_release_offer()
        lv_order.write({"state": "sent"})

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": self.project.id,
                "sab_calculation_source": "schematic",
            }
        )
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "UV1",
                "sequence": 10,
            }
        )
        item = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.calculation_item.id,
                "quantity": 3.0,
                "sequence": 20,
            }
        )
        self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet_end",
                "sequence": 30,
            }
        )
        order.sab_calculation_line_ids._normalize_section_membership()
        self.assertEqual(item.parent_cabinet_id, cabinet)
        self.assertEqual(item.lv_position, "01.01.03")
        return order, cabinet

    def test_component_snapshot_is_stable(self):
        order = self._order()
        calc_line = order.sab_calculation_line_ids
        self.assertEqual(len(calc_line.component_snapshot_ids), 1)
        self.assertAlmostEqual(
            calc_line.component_snapshot_ids.quantity_per_unit,
            2.0,
        )

        source_line = self.calculation_item.product_line_ids
        source_line.quantity = 9.0
        self.assertAlmostEqual(
            calc_line.component_snapshot_ids.quantity_per_unit,
            2.0,
        )

    def test_confirmed_schematic_order_generates_distributor_and_total_bom_from_snapshot(self):
        order, cabinet = self._schematic_order()
        order.action_sab_release_offer()
        order.state = "sale"
        action = order.action_generate_sab_bom()

        self.assertEqual(action["res_model"], "sab.project.bom")
        self.assertEqual(len(order.sab_bom_ids), 2)
        cabinet_bom = order.sab_bom_ids.filtered(
            lambda bom: bom.bom_scope == "cabinet"
        )
        total_bom = order.sab_bom_ids.filtered(
            lambda bom: bom.bom_scope == "total"
        )

        self.assertEqual(cabinet_bom.order_id, order)
        self.assertEqual(cabinet_bom.project_id, self.project)
        self.assertEqual(cabinet_bom.cabinet_line_id, cabinet)
        self.assertEqual(len(cabinet_bom.line_ids), 1)
        self.assertEqual(len(total_bom.line_ids), 1)
        self.assertEqual(cabinet_bom.line_ids.product_id, self.product)
        self.assertAlmostEqual(cabinet_bom.line_ids.quantity, 6.0)
        self.assertAlmostEqual(total_bom.line_ids.quantity, 6.0)
        self.assertAlmostEqual(cabinet_bom.line_ids.unit_purchase_price, 5.0)
        self.assertAlmostEqual(cabinet_bom.line_ids.purchase_total, 30.0)

        cabinet_bom.action_release()
        with self.assertRaises(ValidationError):
            cabinet_bom.line_ids.write({"quantity": 7.0})

    def test_bom_regeneration_preserves_referenced_cabinet_lines_and_stale_boms(self):
        order, cabinet = self._schematic_order()
        order.action_sab_release_offer()
        order.state = "sale"
        order.action_generate_sab_bom()

        cabinet_bom = order.sab_bom_ids.filtered(
            lambda bom: bom.bom_scope == "cabinet"
            and bom.cabinet_line_id == cabinet
        )
        source_line = cabinet_bom.line_ids
        self.assertTrue(source_line)
        source_line_id = source_line.id

        holder_order = self.env["sale.order"].create(
            {"partner_id": self.partner.id}
        )
        holder_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Referenzhalter",
                "order_id": holder_order.id,
                "project_id": self.project.id,
                "bom_scope": "total",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "unit": "pcs",
                            "source_cabinet_bom_id": cabinet_bom.id,
                            "source_cabinet_line_id": source_line.id,
                        },
                    )
                ],
            }
        )

        # Re-running the button must keep the already referenced source line ID
        # instead of clearing the O2M with (5, 0, 0), which previously caused
        # the PostgreSQL FK error seen in the real UI.
        order.action_generate_sab_bom()
        source_line.invalidate_recordset()
        self.assertTrue(source_line.exists())
        self.assertEqual(source_line.id, source_line_id)
        self.assertEqual(
            holder_bom.line_ids.source_cabinet_line_id.id,
            source_line_id,
        )

        fake_cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": holder_order.id,
                "line_type": "cabinet",
                "description": "ALT-UV",
                "sequence": 10,
            }
        )
        stale_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Altverteiler",
                "order_id": order.id,
                "project_id": self.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": fake_cabinet.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "unit": "pcs",
                        },
                    )
                ],
            }
        )
        stale_holder = self.env["sab.project.bom.line"].create(
            {
                "bom_id": holder_bom.id,
                "product_id": self.product.id,
                "quantity": 1.0,
                "unit": "pcs",
                "source_cabinet_bom_id": stale_bom.id,
                "source_cabinet_line_id": stale_bom.line_ids.id,
            }
        )

        order.action_generate_sab_bom()
        self.assertTrue(stale_bom.exists())
        self.assertTrue(stale_holder.exists())
        self.assertEqual(stale_holder.source_cabinet_bom_id, stale_bom)

    def test_calculation_setting_requires_code_and_creates_log(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("sab_project.calculation_change_code", "1111")
        params.set_param("sab_project.material_factor", "1.0")

        settings = self.env["res.config.settings"].create(
            {
                "sab_material_factor": 1.2,
                "sab_calculation_change_code": "1111",
            }
        )
        with self.assertRaises(ValidationError):
            settings.set_values()

        settings.sab_calculation_change_code_confirm = "1111"
        settings.set_values()
        self.assertAlmostEqual(
            float(params.get_param("sab_project.material_factor")),
            1.2,
        )

        log = self.env["sab.calculation.change.log"].search(
            [("parameter_key", "=", "sab_project.material_factor")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(log)
        self.assertEqual(log.old_value, "1.0")
        self.assertEqual(log.new_value, "1.2")