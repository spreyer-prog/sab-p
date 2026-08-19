from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabDeliveryOverdue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for xmlid in (
            "sab_project.group_sab_purchasing",
            "sab_project.group_sab_purchase_approver",
        ):
            cls.env.ref(xmlid).write(
                {"user_ids": [Command.link(cls.env.user.id)]}
            )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Kunde Liefertermin"}
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Liefertermin",
                "partner_id": cls.partner.id,
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "sab_project_id": cls.project.id,
            }
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "Produkt Liefertermin",
                "manufacturer_article_number": "LIEF-100",
                "price_mode": "fixed",
                "fixed_purchase_price": 15.0,
            }
        )
        supplier_partner = cls.env["res.partner"].create(
            {
                "name": "Lieferant Liefertermin",
                "email": "liefertermin@example.invalid",
            }
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {
                "name": "Lieferant Liefertermin",
                "partner_id": supplier_partner.id,
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-LIEF-100",
                "purchase_price": 15.0,
                "packaging_quantity": 1.0,
                "minimum_order_quantity": 1.0,
                "preferred": True,
            }
        )
        cls.bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL Liefertermin / GESAMT",
                "order_id": cls.sale_order.id,
                "project_id": cls.project.id,
                "bom_scope": "total",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "product_id": cls.product.id,
                            "odoo_product_id": cls.product.odoo_product_id.id,
                            "quantity": 2.0,
                            "unit": "pcs",
                            "supplier_product_id": cls.supplier_product.id,
                            "unit_purchase_price": 15.0,
                        },
                    )
                ],
            }
        )
        cls.bom.action_release()
        cls.requirement = cls.env["sab.purchase.requirement"].create(
            {"bom_line_id": cls.bom.line_ids.id}
        )
        cls.purchase_order = cls.env["sab.purchase.order"].create(
            {
                "supplier_id": cls.supplier.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "requirement_id": cls.requirement.id,
                            "quantity_ordered": 2.0,
                            "unit_purchase_price": 15.0,
                        },
                    )
                ],
            }
        )
        cls.purchase_order.action_submit_for_approval()
        cls.purchase_order.action_approve()
        cls.purchase_order.action_send_order_email()
        cls.line = cls.purchase_order.line_ids
        cls.line.expected_delivery_date = fields.Date.today() - timedelta(days=3)

    def test_overdue_position_is_listed_and_cron_creates_activity(self):
        self.assertTrue(self.line.delivery_is_overdue)
        self.assertEqual(self.line.delivery_status, "overdue")
        self.assertEqual(self.line.delivery_overdue_days, 3)
        self.assertTrue(self.purchase_order.has_overdue_delivery)
        self.assertEqual(self.purchase_order.overdue_line_count, 1)

        action = self.env.ref("sab_project.action_sab_overdue_delivery_lines")
        self.assertEqual(action.res_model, "sab.purchase.order.line")
        search_result = self.env["sab.purchase.order.line"].search(
            [("delivery_is_overdue", "=", True)]
        )
        self.assertIn(self.line, search_result)

        self.env["sab.purchase.order"]._cron_check_overdue_deliveries()
        activity = self.env["mail.activity"].search(
            [
                ("res_model", "=", "sab.purchase.order"),
                ("res_id", "=", self.purchase_order.id),
                ("summary", "=", "Liefertermin überschritten"),
            ]
        )
        self.assertTrue(activity)

    def test_one_click_reminder_is_grouped_per_order_and_logged(self):
        self.line.action_send_overdue_delivery_reminder()
        self.assertEqual(self.line.delivery_reminder_count, 1)
        self.assertTrue(self.line.delivery_reminder_sent_at)
        self.assertEqual(
            self.line.delivery_reminder_sent_by_id,
            self.env.user,
        )
        self.assertTrue(self.purchase_order.delivery_reminder_sent_at)
        reminder_message = self.purchase_order.message_ids.filtered(
            lambda message: "Liefertermin-Nachfrage" in (message.body or "")
        )
        self.assertTrue(reminder_message)

    def test_overdue_views_contain_grouped_send_controls(self):
        list_view = self.env.ref(
            "sab_project.view_sab_overdue_delivery_line_list"
        )
        list_arch = etree.fromstring(list_view.arch_db.encode("utf-8"))
        self.assertTrue(
            list_arch.xpath(
                "//button[@name='action_send_overdue_delivery_reminder']"
            )
        )
        self.assertTrue(list_arch.xpath("//field[@name='delivery_overdue_days']"))

        order_view = self.env.ref(
            "sab_project.view_sab_purchase_order_form_overdue_delivery"
        )
        order_arch = etree.fromstring(order_view.arch_db.encode("utf-8"))
        self.assertTrue(
            order_arch.xpath(
                "//button[@name='action_send_overdue_delivery_reminder']"
            )
        )
        self.assertTrue(
            order_arch.xpath(
                "//button[@name='action_view_overdue_delivery_lines']"
            )
        )
