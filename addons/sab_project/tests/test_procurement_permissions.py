from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabProcurementPermissions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.regular_user = cls.env["res.users"].create({
            "name": "Interner Benutzer ohne Beschaffungsrolle",
            "login": "procurement.no.role@example.invalid",
            "email": "procurement.no.role@example.invalid",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
        })
        cls.manager_user = cls.env["res.users"].create({
            "name": "Projektleiter ohne Beschaffungsrolle",
            "login": "project.manager.no.procurement@example.invalid",
            "email": "project.manager.no.procurement@example.invalid",
            "group_ids": [
                Command.link(cls.env.ref("base.group_user").id),
                Command.link(cls.env.ref("project.group_project_manager").id),
            ],
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Kunde Beschaffungsrechte",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Projekt Beschaffungsrechte",
            "partner_id": cls.partner.id,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "sab_project_id": cls.project.id,
        })
        cls.product = cls.env["sab.product"].create({
            "name": "Produkt Beschaffungsrechte",
            "manufacturer_article_number": "SEC-PROC-1",
        })
        cls.bom = cls.env["sab.project.bom"].create({
            "name": "STL Beschaffungsrechte",
            "order_id": cls.order.id,
            "project_id": cls.project.id,
            "bom_scope": "total",
            "line_ids": [(0, 0, {
                "product_id": cls.product.id,
                "odoo_product_id": cls.product.odoo_product_id.id,
                "quantity": 1.0,
                "unit": "pcs",
            })],
        })
        cls.bom.action_release()
        cls.supplier = cls.env["sab.supplier"].create({
            "name": "Lieferant Beschaffungsrechte",
        })
        cls.purchase_order = cls.env["sab.purchase.order"].create({
            "supplier_id": cls.supplier.id,
        })

    def test_regular_internal_user_can_read_but_not_create_procurement_records(self):
        self.assertTrue(
            self.env["sab.purchase.requirement"].with_user(
                self.regular_user
            ).has_access("read")
        )
        self.assertFalse(
            self.env["sab.purchase.requirement"].with_user(
                self.regular_user
            ).has_access("create")
        )
        self.assertFalse(
            self.env["sab.stock.movement"].with_user(
                self.regular_user
            ).has_access("create")
        )

        with self.assertRaises(AccessError):
            self.env["sab.purchase.requirement"].with_user(
                self.regular_user
            ).create({"bom_line_id": self.bom.line_ids.id})

        with self.assertRaises(AccessError):
            self.env["sab.stock.movement"].with_user(
                self.regular_user
            ).create({
                "product_id": self.product.id,
                "odoo_product_id": self.product.odoo_product_id.id,
                "movement_type": "receipt",
                "quantity": 1.0,
                "unit": "pcs",
                "unit_cost": 1.0,
            })

    def test_approval_metadata_cannot_be_written_directly_without_role(self):
        with self.assertRaises(AccessError):
            self.bom.with_user(self.regular_user).write({
                "purchase_release_state": "released",
            })

    def test_project_manager_is_read_only_without_procurement_profile_role(self):
        self.assertTrue(
            self.purchase_order.with_user(self.manager_user).has_access("read")
        )
        self.assertFalse(
            self.purchase_order.with_user(self.manager_user).has_access("write")
        )
        with self.assertRaises(AccessError):
            self.purchase_order.with_user(self.manager_user).write({
                "state": "approved",
            })
