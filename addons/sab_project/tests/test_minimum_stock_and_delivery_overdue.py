from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabMinimumStockAndDeliveryOverdue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("project.group_project_manager").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchasing").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchase_approver").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )

        cls.purchasing_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Einkauf Mindestbestand Test",
                "login": "einkauf-mindestbestand@example.invalid",
                "email": "einkauf-mindestbestand@example.invalid",
                "mobile_access": False,
                "purchasing_access": True,
            }
        )
        cls.purchasing_profile.action_create_or_update_user()

        cls.partner = cls.env["res.partner"].create(
            {"name": "Kunde Mindestbestand"}
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Mindestbestand",
                "partner_id": cls.partner.id,
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
                "state": "sale",
            }
        )
        cls.supplier_partner = cls.env["res.partner"].create(
            {
                "name": "Lieferant Mindestbestand",
                "email": "liefertermin@example.invalid",
            }
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {
                "name": "Lieferant Mindestbestand",
                "partner_id": cls.supplier_partner.id,
            }
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "Produkt Mindestbestand",
                "manufacturer_article_number": "MIN-100",
                "price_mode": "fixed",
                "fixed_purchase_price": 10.0,
                "minimum_stock_quantity": 5.0,
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-MIN-100",
                "purchase_price": 10.0,
                "packaging_quantity": 5.0,
                "minimum_order_quantity": 10.0,
                "preferred": True,
            }
        )

    def _create_requirement(self):
        self.env["sab.stock.movement"].create(
            {
                "product_id": self.product.id,
                "odoo_product_id": self.product.odoo_product_id.id,
                "movement_type": "receipt",
                "quantity": 4.0,
                "unit": "pcs",
                "unit_cost": 10.0,
                "note": "Anfangsbestand Mindestbestand-Test",
            }
        )
        cabinet = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": self.sale_order.id,
                "line_type": "cabinet",
                "description": "UV Mindestbestand",
                "sequence": 10,
            }
        )
        cabinet_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Mindestbestand / UV",
                "order_id": self.sale_order.id,
                "project_id": self.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cabinet.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "product_id": self.product.id,
                            "odoo_product_id": self.product.odoo_product_id.id,
                            "quantity": 10.0,
                            "unit": "pcs",
                            "supplier_product_id": self.supplier_product.id,
                            "unit_purchase_price": 10.0,
                        },
                    )
                ],
            }
        )
        cabinet_bom.action_release()
        wizard = self.env["sab.procurement.package.wizard"].create(
            {
                "order_id": self.sale_order.id,
                "cabinet_bom_ids": [Command.set([cabinet_bom.id])],
            }
        )
        package_action = wizard.action_create_procurement_package()
        package = self.env["sab.project.bom"].browse(
            package_action["res_id"]
        )
        return package, package.purchase_requirement_ids

    def _create_purchase_order(self, replenish_minimum=False):
        package, requirement = self._create_requirement()
        requirement.write(
            {
                "include_minimum_stock_replenishment": replenish_minimum,
            }
        )
        package.action_release_for_purchase()
        action = requirement.action_create_purchase_orders()
        order = self.env["sab.purchase.order"].browse(
            action["domain"][0][2][0]
        )
        return package, requirement, order

    def test_default_order_proposal_is_exact_shortage_without_rounding(self):
        package, requirement = self._create_requirement()

        self.assertAlmostEqual(
            self.product.odoo_product_id.product_tmpl_id.sab_minimum_stock_quantity,
            5.0,
        )
        self.assertAlmostEqual(requirement.warehouse_on_hand, 4.0)
        self.assertAlmostEqual(requirement.project_reserved_quantity, 4.0)
        self.assertAlmostEqual(requirement.shortage_quantity, 6.0)
        self.assertAlmostEqual(requirement.suggested_order_quantity, 6.0)
        self.assertAlmostEqual(requirement.quantity_to_order, 6.0)
        self.assertAlmostEqual(requirement.minimum_stock_quantity, 5.0)
        self.assertAlmostEqual(requirement.projected_free_stock, 0.0)
        self.assertAlmostEqual(
            requirement.minimum_stock_replenishment_quantity,
            5.0,
        )
        self.assertTrue(requirement.minimum_stock_below)
        self.assertFalse(requirement.include_minimum_stock_replenishment)
        self.assertIn(
            "Lieferanten-Mindestbestellmenge",
            requirement.supplier_quantity_warning,
        )
        self.assertIn(
            "Verpackungseinheit",
            requirement.supplier_quantity_warning,
        )

        requirement.write({"include_minimum_stock_replenishment": True})
        self.assertAlmostEqual(requirement.quantity_to_order, 11.0)
        requirement.write({"include_minimum_stock_replenishment": False})
        self.assertAlmostEqual(requirement.quantity_to_order, 6.0)
        self.assertEqual(package.purchase_release_state, "not_released")

    def test_purchase_order_uses_exact_shortage_only_by_default(self):
        _package, requirement, purchase_order = self._create_purchase_order(False)
        self.assertAlmostEqual(requirement.quantity_to_order, 6.0)
        self.assertAlmostEqual(
            purchase_order.line_ids.quantity_ordered,
            6.0,
        )

    def test_minimum_stock_is_added_only_after_explicit_selection(self):
        _package, requirement, purchase_order = self._create_purchase_order(True)
        self.assertAlmostEqual(requirement.quantity_to_order, 11.0)
        self.assertAlmostEqual(
            purchase_order.line_ids.quantity_ordered,
            11.0,
        )

    def test_overdue_delivery_is_listed_and_supplier_can_be_reminded(self):
        _package, _requirement, purchase_order = self._create_purchase_order(False)
        purchase_order.write({"state": "to_approve"})
        purchase_order.write(
            {
                "state": "approved",
                "approved_at": fields.Datetime.now(),
                "approved_by_id": self.env.user.id,
            }
        )
        purchase_order.write(
            {
                "state": "sent",
                "sent_at": fields.Datetime.now(),
                "sent_by_id": self.env.user.id,
            }
        )
        line = purchase_order.line_ids
        line.write(
            {
                "expected_delivery_date": (
                    fields.Date.context_today(self.env.user) - timedelta(days=2)
                ),
            }
        )

        self.assertTrue(line.delivery_is_overdue)
        self.assertEqual(line.delivery_status, "overdue")
        self.assertEqual(line.delivery_overdue_days, 2)
        self.assertTrue(purchase_order.has_overdue_delivery)
        self.assertEqual(purchase_order.overdue_line_count, 1)

        self.env["sab.purchase.order"]._cron_check_overdue_deliveries()
        model_id = self.env["ir.model"]._get_id("sab.purchase.order")
        activity = self.env["mail.activity"].search(
            [
                ("res_model_id", "=", model_id),
                ("res_id", "=", purchase_order.id),
                ("summary", "=", "Liefertermin überschritten"),
            ]
        )
        self.assertTrue(activity)

        result = line.action_send_overdue_delivery_reminder()
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(line.delivery_reminder_count, 1)
        self.assertTrue(line.delivery_reminder_sent_at)
        self.assertTrue(purchase_order.delivery_reminder_sent_at)
        self.assertFalse(
            self.env["mail.activity"].search(
                [
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", purchase_order.id),
                    ("summary", "=", "Liefertermin überschritten"),
                ]
            )
        )

    def test_overdue_delivery_view_contains_order_and_position_details(self):
        view = self.env.ref(
            "sab_project.view_sab_overdue_delivery_line_list"
        )
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//field[@name='order_id']"))
        self.assertTrue(arch.xpath("//field[@name='supplier_id']"))
        self.assertTrue(arch.xpath("//field[@name='source_cabinet_bom_id']"))
        self.assertTrue(arch.xpath("//field[@name='expected_delivery_date']"))
        self.assertTrue(arch.xpath("//field[@name='delivery_overdue_days']"))
        self.assertTrue(
            arch.xpath(
                "//button[@name='action_send_overdue_delivery_reminder']"
            )
        )

        action = self.env.ref("sab_project.action_sab_overdue_delivery_lines")
        self.assertEqual(action.res_model, "sab.purchase.order.line")
        self.assertIn("delivery_is_overdue", action.domain)
