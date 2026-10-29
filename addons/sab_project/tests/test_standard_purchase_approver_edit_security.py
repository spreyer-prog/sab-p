from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSabStandardPurchaseApproverEditSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.purchasing_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Einkauf Änderungssperre",
                "login": "einkauf-aenderungssperre@example.invalid",
                "email": "einkauf-aenderungssperre@example.invalid",
                "mobile_access": False,
                "purchasing_access": True,
            }
        )
        cls.purchasing_profile.action_create_or_update_user()
        cls.purchasing_user = cls.purchasing_profile.user_id

        cls.approver_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Freigabe Änderungssperre",
                "login": "freigabe-aenderungssperre@example.invalid",
                "email": "freigabe-aenderungssperre@example.invalid",
                "mobile_access": False,
                "purchase_approval_access": True,
            }
        )
        cls.approver_profile.action_create_or_update_user()
        cls.approver_user = cls.approver_profile.user_id

        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Lieferant Änderungssperre",
                "supplier_rank": 1,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Prüfposition Änderungssperre",
                "type": "service",
                "purchase_ok": True,
                "sale_ok": False,
            }
        )

    def test_pure_approver_cannot_change_order_but_can_approve(self):
        order = self.env["purchase.order"].create(
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
        order.with_user(self.purchasing_user).button_confirm()
        self.assertEqual(order.state, "to approve")

        with self.assertRaises(AccessError):
            order.with_user(self.approver_user).write(
                {"partner_ref": "UNZULÄSSIGE ÄNDERUNG"}
            )
        with self.assertRaises(AccessError):
            order.order_line.with_user(self.approver_user).write(
                {"product_qty": 2.0}
            )

        order.with_user(self.approver_user).button_approve()
        self.assertEqual(order.state, "purchase")
