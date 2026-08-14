from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabPurchaseRequirement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Einkauf"})
        cls.project = cls.env["project.project"].create({"name": "Projekt Einkauf", "partner_id": cls.partner.id})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id, "sab_project_id": cls.project.id})
        cls.manufacturer = cls.env["sab.manufacturer"].create({"name": "Hersteller Einkauf"})
        cls.supplier = cls.env["sab.supplier"].create({"name": "Lieferant Einkauf"})
        cls.product = cls.env["sab.product"].create({"name": "Einkaufsprodukt", "manufacturer_id": cls.manufacturer.id, "manufacturer_article_number": "EK-100"})
        cls.supplier_product = cls.env["sab.supplier.product"].create({"supplier_id": cls.supplier.id, "product_id": cls.product.id, "supplier_article_number": "SUP-EK-100", "purchase_price": 12.5, "preferred": True})

    def _bom(self):
        return self.env["sab.project.bom"].create({
            "name": "STL Einkaufstest",
            "order_id": self.order.id,
            "project_id": self.project.id,
            "line_ids": [
                (0, 0, {"sequence": 10, "product_id": self.product.id, "quantity": 4.0, "unit": "pcs", "supplier_product_id": self.supplier_product.id, "unit_purchase_price": 12.5}),
                (0, 0, {"sequence": 20, "product_id": self.product.id, "quantity": 1.0, "unit": "pcs", "optional": True, "supplier_product_id": self.supplier_product.id, "unit_purchase_price": 12.5}),
            ],
        })

    def test_requirement_requires_released_bom(self):
        bom = self._bom()
        with self.assertRaises(ValidationError):
            self.env["sab.purchase.requirement"].create({"bom_line_id": bom.line_ids[:1].id})

    def test_generate_requirement_is_idempotent_and_skips_optional(self):
        bom = self._bom()
        bom.action_release()
        bom.action_generate_purchase_requirements()
        self.assertEqual(len(bom.purchase_requirement_ids), 1)
        requirement = bom.purchase_requirement_ids
        self.assertEqual(requirement.product_id, self.product)
        self.assertEqual(requirement.supplier_id, self.supplier)
        self.assertAlmostEqual(requirement.quantity, 4.0)
        self.assertAlmostEqual(requirement.unit_purchase_price, 12.5)
        self.assertAlmostEqual(requirement.purchase_total, 50.0)

        bom.action_generate_purchase_requirements()
        self.assertEqual(len(bom.purchase_requirement_ids), 1)

        requirement.action_mark_ordered()
        self.assertEqual(requirement.state, "ordered")
        requirement.action_mark_received()
        self.assertEqual(requirement.state, "received")
