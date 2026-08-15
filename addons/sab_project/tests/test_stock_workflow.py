from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabStockWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["sab.product"].create({"name": "Lagerprodukt"})

    def test_receipt_reserve_release_issue_balances(self):
        Movement = self.env["sab.stock.movement"]
        Movement.create({
            "product_id": self.product.id,
            "movement_type": "receipt",
            "quantity": 10.0,
            "unit": "pcs",
        })
        self.assertAlmostEqual(self.product.stock_on_hand, 10.0)
        self.assertAlmostEqual(self.product.stock_available, 10.0)

        Movement.create({
            "product_id": self.product.id,
            "movement_type": "reserve",
            "quantity": 4.0,
            "unit": "pcs",
        })
        self.assertAlmostEqual(self.product.stock_reserved, 4.0)
        self.assertAlmostEqual(self.product.stock_available, 6.0)

        with self.assertRaises(ValidationError):
            Movement.create({
                "product_id": self.product.id,
                "movement_type": "reserve",
                "quantity": 7.0,
                "unit": "pcs",
            })

        Movement.create({
            "product_id": self.product.id,
            "movement_type": "release",
            "quantity": 1.0,
            "unit": "pcs",
        })
        self.assertAlmostEqual(self.product.stock_reserved, 3.0)
        self.assertAlmostEqual(self.product.stock_available, 7.0)

        Movement.create({
            "product_id": self.product.id,
            "movement_type": "issue",
            "quantity": 2.0,
            "unit": "pcs",
        })
        self.assertAlmostEqual(self.product.stock_on_hand, 8.0)
        self.assertAlmostEqual(self.product.stock_available, 5.0)

    def test_purchase_receipt_posts_stock_once(self):
        partner = self.env["res.partner"].create({"name": "Kunde Lager"})
        project = self.env["project.project"].create({"name": "Projekt Lager", "partner_id": partner.id})
        order = self.env["sale.order"].create({"partner_id": partner.id, "sab_project_id": project.id})
        bom = self.env["sab.project.bom"].create({
            "name": "STL Lager",
            "order_id": order.id,
            "project_id": project.id,
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 3.0,
                "unit": "pcs",
            })],
        })
        bom.action_release()
        bom.action_generate_purchase_requirements()
        requirement = bom.purchase_requirement_ids
        requirement.action_mark_received()

        self.assertEqual(requirement.state, "received")
        self.assertTrue(requirement.stock_movement_id)
        self.assertAlmostEqual(self.product.stock_on_hand, 3.0)

        movement_id = requirement.stock_movement_id.id
        requirement.action_mark_received()
        self.assertEqual(requirement.stock_movement_id.id, movement_id)
        self.assertAlmostEqual(self.product.stock_on_hand, 3.0)
