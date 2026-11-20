from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabEndToEnd(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("sab_project.group_sab_customer_release").write(
            {"user_ids": [(4, cls.env.user.id)]}
        )
        cls.partner = cls.env["res.partner"].create({"name": "E2E Kunde"})
        cls.manufacturer = cls.env["sab.manufacturer"].create(
            {"name": "E2E Hersteller"}
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {"name": "E2E Lieferant"}
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "E2E Leistungsschalter",
                "manufacturer_id": cls.manufacturer.id,
                "manufacturer_article_number": "E2E-100",
                "mechanical_time_minutes": 10.0,
                "wiring_time_minutes": 20.0,
                "testing_time_minutes": 5.0,
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-E2E-100",
                "purchase_price": 25.0,
                "preferred": True,
            }
        )
        cls.calculation_item = cls.env["sab.calculation.item"].create(
            {
                "name": "E2E Kalkulationsartikel",
                "quotation_text": "E2E Schaltschrankposition",
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
        cls.production_employee = cls.env["sab.employee.profile"].create(
            {
                "name": "E2E Fertigungsmitarbeiter",
                "login": "e2e.production@test.local",
                "email": "e2e.production@example.invalid",
                "mobile_access": True,
                "work_area_ids": [
                    Command.set(cls.env["sab.work.area"].search([]).ids)
                ],
            }
        )
        cls.production_employee.action_create_or_update_user()

    def test_complete_project_flow(self):
        project = self.env["project.project"].create(
            {"name": "E2E NSHV", "partner_id": self.partner.id}
        )
        self.assertRegex(project.sab_project_reference, r"^A\d{2}\.\d{4}$")

        lv_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": project.id,
                "sab_calculation_source": "lv",
            }
        )
        lv_line = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": lv_order.id,
                "calculation_item_id": self.calculation_item.id,
                "quantity": 3.0,
                "lv_position": "01.01.03",
            }
        )
        lv_order.action_sab_release_offer()
        lv_order.state = "sent"
        self.assertEqual(lv_line.lv_position, "01.01.03")
        self.assertEqual(
            lv_order.sab_offer_reference,
            f"{project.sab_project_reference}-01",
        )

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": project.id,
                "sab_calculation_source": "schematic",
            }
        )
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "line_type": "cabinet",
                "description": "NSHV1",
                "sequence": 10,
            }
        )
        schematic_line = self.env["sab.offer.calculation.line"].create(
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

        self.assertEqual(
            order.sab_offer_reference,
            f"{project.sab_project_reference}-02",
        )
        self.assertGreater(order.sab_calculated_hours, 0.0)
        self.assertEqual(schematic_line.lv_position, "01.01.03")
        self.assertEqual(schematic_line.parent_cabinet_id, cabinet)

        order.action_sab_release_offer()
        order.state = "sale"
        bom_action = order.action_generate_sab_bom()
        self.assertEqual(bom_action["res_model"], "sab.project.bom")
        self.assertEqual(len(order.sab_bom_ids), 2)
        bom = order.sab_bom_ids.filtered(
            lambda record: record.bom_scope == "cabinet"
        )
        total_bom = order.sab_bom_ids.filtered(
            lambda record: record.bom_scope == "total"
        )
        self.assertEqual(bom.cabinet_line_id, cabinet)
        self.assertAlmostEqual(bom.line_ids.quantity, 6.0)
        self.assertAlmostEqual(total_bom.line_ids.quantity, 6.0)
        bom.action_release()
        total_bom.action_release()

        total_bom.action_generate_purchase_requirements()
        requirement = total_bom.purchase_requirement_ids
        self.assertEqual(len(requirement), 1)
        self.assertFalse(bom.purchase_requirement_ids)
        requirement.action_mark_ordered()
        requirement.action_mark_received()
        self.assertEqual(requirement.state, "received")
        self.assertTrue(requirement.stock_movement_id)
        self.assertAlmostEqual(self.product.stock_on_hand, 6.0)

        production_action = bom.action_create_production_order()
        production = self.env["sab.production.order"].browse(
            production_action["res_id"]
        )
        self.assertTrue(production.step_ids)
        self.assertTrue(all(production.step_ids.mapped("work_area_id")))
        for step in production.step_ids.sorted("sequence"):
            employee_step = step.with_user(self.production_employee.user_id)
            employee_step.action_start()
            employee_step.action_done()
            step.invalidate_recordset(
                ["responsible_employee_id", "responsible_user_id"]
            )
            self.assertEqual(
                step.responsible_employee_id,
                self.production_employee,
            )
            self.assertEqual(
                step.responsible_user_id,
                self.production_employee.user_id,
            )
        production.action_mark_done()
        self.assertEqual(production.state, "done")
        self.assertAlmostEqual(production.progress_percent, 100.0)

        first_step = production.step_ids.sorted("sequence")[:1]
        time_entry = self.env["sab.time.entry"].create(
            {
                "production_step_id": first_step.id,
                "project_id": project.id,
                "name": "E2E Ist-Zeit",
                "hours": 1.5,
                "hourly_cost": 80.0,
            }
        )
        time_entry.action_confirm()
        self.assertAlmostEqual(project.sab_required_hours, 1.5)

        status_action = project.action_open_sab_customer_status()
        status = self.env["sab.customer.project.status"].browse(
            status_action["res_id"]
        )
        status.invalidate_recordset(["suggested_milestone"])
        self.assertEqual(status.suggested_milestone, "ready")
        status.action_apply_suggestion()
        self.assertFalse(status.released)
        status.action_release()
        self.assertTrue(status.released)

        controlling = self.env["sab.project.controlling"].create(
            {"project_id": project.id}
        )
        self.assertAlmostEqual(controlling.actual_hours, 1.5)
        self.assertAlmostEqual(controlling.actual_labor_cost, 120.0)
