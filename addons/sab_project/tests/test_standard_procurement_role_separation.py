from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabStandardProcurementRoleSeparation(TransactionCase):
    def test_purchase_approver_does_not_inherit_sab_purchasing(self):
        profile = self.env["sab.employee.profile"].create(
            {
                "name": "Reiner Bestellfreigeber",
                "login": "reiner-freigeber@example.invalid",
                "email": "reiner-freigeber@example.invalid",
                "mobile_access": False,
                "purchasing_access": False,
                "purchase_approval_access": True,
                "warehouse_access": False,
            }
        )
        profile.action_create_or_update_user()
        user = profile.user_id

        self.assertTrue(
            user.has_group("sab_project.group_sab_purchase_approver")
        )
        self.assertTrue(user.has_group("purchase.group_purchase_manager"))
        self.assertFalse(user.has_group("sab_project.group_sab_purchasing"))
        self.assertFalse(user.has_group("sab_project.group_sab_warehouse"))

    def test_project_manager_without_stock_role_cannot_post_commissioning(self):
        manager = self.env["res.users"].create(
            {
                "name": "Projektleiter ohne Lagerrolle",
                "login": "projektleiter-ohne-lager@example.invalid",
                "email": "projektleiter-ohne-lager@example.invalid",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(
                        self.env.ref("project.group_project_manager").id
                    ),
                ],
            }
        )
        customer = self.env["res.partner"].create(
            {"name": "Kunde Rollenprüfung"}
        )
        project = self.env["project.project"].create(
            {"name": "Projekt Rollenprüfung", "partner_id": customer.id}
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "sab_project_id": project.id,
            }
        )
        bom = self.env["sab.project.bom"].create(
            {
                "name": "Materialanforderung Rollenprüfung",
                "order_id": order.id,
                "project_id": project.id,
            }
        )

        with self.assertRaises(AccessError):
            bom.with_user(manager)._sab_check_standard_commissioning_user()
