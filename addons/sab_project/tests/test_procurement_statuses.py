from odoo.tests.common import TransactionCase


class TestSabProcurementStatuses(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Kunde Bestellstatus",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Projekt Bestellstatus",
            "partner_id": cls.partner.id,
        })
        cls.sale_order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "sab_project_id": cls.project.id,
        })
        cls.supplier = cls.env["sab.supplier"].create({
            "name": "Lieferant Bestellstatus",
        })
        cls.product = cls.env["sab.product"].create({
            "name": "Produkt Bestellstatus",
            "manufacturer_article_number": "STATUS-1",
        })
        cls.supplier_product = cls.env["sab.supplier.product"].create({
            "supplier_id": cls.supplier.id,
            "product_id": cls.product.id,
            "supplier_article_number": "SUP-STATUS-1",
            "purchase_price": 10.0,
            "preferred": True,
        })
        cls.bom = cls.env["sab.project.bom"].create({
            "name": "STL Bestellstatus",
            "order_id": cls.sale_order.id,
            "project_id": cls.project.id,
            "bom_scope": "total",
            "line_ids": [(0, 0, {
                "product_id": cls.product.id,
                "odoo_product_id": cls.product.odoo_product_id.id,
                "quantity": 2.0,
                "unit": "pcs",
                "supplier_product_id": cls.supplier_product.id,
                "unit_purchase_price": 10.0,
            })],
        })
        cls.bom.action_release()
        cls.bom.action_generate_purchase_requirements()
        cls.requirement = cls.bom.purchase_requirement_ids
        cls.purchase_order = cls.env["sab.purchase.order"].create({
            "supplier_id": cls.supplier.id,
            "line_ids": [(0, 0, {
                "requirement_id": cls.requirement.id,
                "quantity_ordered": 2.0,
                "unit_purchase_price": 10.0,
            })],
        })

    def _status(self):
        self.requirement.invalidate_recordset([
            "stock_status",
            "purchase_order_state",
        ])
        return self.requirement.stock_status

    def test_requirement_status_follows_real_purchase_order_stage(self):
        self.assertEqual(self._status(), "proposal")

        self.purchase_order.write({"state": "to_approve"})
        self.assertEqual(self._status(), "approval")

        self.purchase_order.write({
            "state": "approved",
            "approved_by_id": self.env.user.id,
        })
        self.assertEqual(self._status(), "approved")

        self.purchase_order.write({"state": "sent"})
        self.assertEqual(self._status(), "ordered")
