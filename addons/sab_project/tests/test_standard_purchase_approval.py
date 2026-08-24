from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestSabStandardPurchaseApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.purchasing_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Einkauf Standardbestellung",
                "login": "einkauf-standard@example.invalid",
                "email": "einkauf-standard@example.invalid",
                "mobile_access": False,
                "purchasing_access": True,
                "purchase_approval_access": False,
                "warehouse_access": False,
            }
        )
        cls.purchasing_profile.action_create_or_update_user()
        cls.purchasing_user = cls.purchasing_profile.user_id

        cls.approver_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Freigabe Standardbestellung",
                "login": "freigabe-standard@example.invalid",
                "email": "freigabe-standard@example.invalid",
                "mobile_access": False,
                "purchasing_access": False,
                "purchase_approval_access": True,
                "warehouse_access": False,
            }
        )
        cls.approver_profile.action_create_or_update_user()
        cls.approver_user = cls.approver_profile.user_id

        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Lieferant Standardfreigabe",
                "supplier_rank": 1,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Prüfservice Standardfreigabe",
                "type": "service",
                "purchase_ok": True,
                "sale_ok": False,
            }
        )

    def _create_sab_purchase_order(self):
        return self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "sab_is_suite_order": True,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.display_name,
                            "product_qty": 1.0,
                            "product_uom_id": self.product.uom_id.id,
                            "price_unit": 100.0,
                            "date_planned": fields.Datetime.now(),
                        },
                    )
                ],
            }
        )

    def test_purchase_requires_separate_sab_approval(self):
        order = self._create_sab_purchase_order()

        order.with_user(self.purchasing_user).button_confirm()
        self.assertEqual(order.state, "to approve")

        with self.assertRaises(AccessError):
            order.with_user(self.purchasing_user).button_approve()

        order.with_user(self.approver_user).button_approve()
        self.assertEqual(order.state, "purchase")

        with self.assertRaises(AccessError):
            order.with_user(self.approver_user).button_cancel()

        order.with_user(self.purchasing_user).button_cancel()
        self.assertEqual(order.state, "cancel")

        with self.assertRaises(ValidationError):
            order.with_user(self.purchasing_user).button_draft()
