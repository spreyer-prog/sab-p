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
