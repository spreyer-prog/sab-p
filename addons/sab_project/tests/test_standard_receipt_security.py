from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSabStandardReceiptSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.purchasing_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Einkauf Wareneingangstest",
                "login": "einkauf-wareneingang@example.invalid",
                "email": "einkauf-wareneingang@example.invalid",
                "mobile_access": False,
                "purchasing_access": True,
            }
        )
        cls.purchasing_profile.action_create_or_update_user()
        cls.purchasing_user = cls.purchasing_profile.user_id

        cls.approver_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Freigabe Wareneingangstest",
                "login": "freigabe-wareneingang@example.invalid",
                "email": "freigabe-wareneingang@example.invalid",
                "mobile_access": False,
                "purchase_approval_access": True,
            }
        )
        cls.approver_profile.action_create_or_update_user()
        cls.approver_user = cls.approver_profile.user_id

        cls.warehouse_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Lager Wareneingangstest",
                "login": "lager-wareneingang@example.invalid",
                "email": "lager-wareneingang@example.invalid",
                "mobile_access": False,
                "warehouse_access": True,
            }
        )
        cls.warehouse_profile.action_create_or_update_user()
        cls.warehouse_user = cls.warehouse_profile.user_id

        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Lieferant Wareneingangstest",
                "supplier_rank": 1,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Material Wareneingangstest",
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": False,
                "purchase_method": "receive",
            }
        )

    def _create_receipt(self):
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
                            "product_qty": 2.0,
                            "product_uom_id": self.product.uom_id.id,
                            "price_unit": 20.0,
                            "date_planned": fields.Datetime.now(),
                        },
                    )
                ],
            }
        )
        order.with_user(self.purchasing_user).button_confirm()
        order.with_user(self.approver_user).button_approve()
        receipt = order.picking_ids.filtered(
            lambda picking: picking.picking_type_id.code == "incoming"
            and picking.state != "cancel"
        )
        self.assertEqual(len(receipt), 1)
        receipt.invalidate_recordset()
        self.assertTrue(receipt.sab_is_suite_receipt)
        return receipt

    def test_only_warehouse_or_purchasing_can_validate_sab_receipt(self):
        receipt = self._create_receipt()
        receipt.write(
            {
                "sab_supplier_delivery_note_number": "LS-RECHTE-0001",
                "sab_supplier_delivery_note_date": fields.Date.today(),
            }
        )
        receipt.move_ids.quantity = receipt.move_ids.product_uom_qty

        with self.assertRaises(AccessError):
            receipt.with_user(self.approver_user).button_validate()

        receipt.with_user(self.warehouse_user).button_validate()
        self.assertEqual(receipt.state, "done")
