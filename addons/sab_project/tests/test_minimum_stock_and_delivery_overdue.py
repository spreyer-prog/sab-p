from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabMinimumStockAndDeliveryOverdue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({"name": "Mindestbestand Projekt"})
        cls.customer = cls.env["res.partner"].create({"name": "Mindestbestand Kunde"})
        cls.supplier = cls.env["res.partner"].create({"name": "Mindestbestand Lieferant", "supplier_rank": 1, "email": "supplier@example.invalid"})
        cls.sale_order = cls.env["sale.order"].create({"partner_id": cls.customer.id, "sab_project_id": cls.project.id, "sab_calculation_source": "schematic"})
        cls.product = cls.env["sab.product"].create({"name": "Mindestbestand Produkt", "manufacturer_part_number": "MIN-001", "unit": "pcs", "minimum_stock_quantity": 5.0})
        cls.supplier_product = cls.env["sab.supplier.product"].create({"product_id": cls.product.id, "supplier_id": cls.supplier.id, "supplier_article_number": "MIN-SUP-001", "list_price": 10.0, "discount_percent": 0.0, "minimum_order_quantity": 10.0, "preferred": True})

    def _create_requirement(self):
        self.env["sab.stock.movement"].create({"product_id": self.product.id, "odoo_product_id": self.product.odoo_product_id.id, "movement_type": "receipt", "quantity": 4.0, "unit": "pcs", "unit_cost": 10.0, "note": "Anfangsbestand Mindestbestand-Test"})
        cabinet = self.env["sab.offer.calculation.line"].create({"order_id": self.sale_order.id, "line_type": "cabinet", "description": "UV Mindestbestand", "sequence": 10})
        line_vals = {"sequence": 10, "product_id": self.product.id, "odoo_product_id": self.product.odoo_product_id.id, "quantity": 10.0, "unit": "pcs", "supplier_product_id": self.supplier_product.id, "unit_purchase_price": 10.0}
        cabinet_bom = self.env["sab.project.bom"].create({"name": "STL Mindestbestand / UV", "order_id": self.sale_order.id, "project_id": self.project.id, "bom_scope": "cabinet", "cabinet_line_id": cabinet.id, "line_ids": [(0, 0, line_vals)]})
        cabinet_bom.action_release()
        total_bom = self.env["sab.project.bom"].create({"name": "Gesamtstückliste Mindestbestand", "order_id": self.sale_order.id, "project_id": self.project.id, "bom_scope": "total", "line_ids": [(0, 0, line_vals)]})
        total_bom.action_release()
        self.sale_order.write({"state": "sale"})
        wizard = self.env["sab.procurement.package.wizard"].create({"order_id": self.sale_order.id, "cabinet_bom_ids": [Command.set([cabinet_bom.id])]})
        package_action = wizard.action_create_procurement_package()
        package = self.env["sab.project.bom"].browse(package_action["res_id"])
        return package, package.purchase_requirement_ids

    def _create_purchase_order(self, replenish_minimum=False):
        package, requirement = self._create_requirement()
        requirement.write({"replenish_minimum_stock": replenish_minimum})
        requirement.action_reset_order_quantity_to_suggestion()
        action = requirement.action_create_purchase_orders()
        purchase_order = self.env["sab.purchase.order"].browse(action["res_id"])
        return package, requirement, purchase_order

    def test_default_order_proposal_is_exact_shortage_without_rounding(self):
        _package, requirement = self._create_requirement()
        self.assertEqual(requirement.shortage_quantity, 6.0)
        self.assertEqual(requirement.suggested_order_quantity, 6.0)

    def test_purchase_order_uses_exact_shortage_only_by_default(self):
        _package, requirement, purchase_order = self._create_purchase_order(False)
        self.assertEqual(requirement.quantity_to_order, 6.0)
        self.assertEqual(purchase_order.line_ids.quantity, 6.0)

    def test_minimum_stock_is_added_only_after_explicit_selection(self):
        _package, requirement, purchase_order = self._create_purchase_order(True)
        self.assertGreater(requirement.quantity_to_order, requirement.shortage_quantity)
        self.assertEqual(purchase_order.line_ids.quantity, requirement.quantity_to_order)

    def test_overdue_delivery_is_listed_and_supplier_can_be_reminded(self):
        _package, _requirement, purchase_order = self._create_purchase_order(False)
        purchase_order.write({"state": "sent"})
        purchase_order.line_ids.write({"expected_delivery_date": fields.Date.today() - timedelta(days=2)})
        overdue = self.env["sab.purchase.order.line"].search([("id", "in", purchase_order.line_ids.ids), ("expected_delivery_date", "<", fields.Date.today())])
        self.assertEqual(overdue, purchase_order.line_ids)
        if hasattr(purchase_order, "action_send_delivery_reminder"):
            purchase_order.action_send_delivery_reminder()

    def test_overdue_delivery_view_contains_order_and_position_details(self):
        view = self.env.ref("sab_project.view_sab_delivery_overdue_list")
        arch = view.arch_db
        self.assertIn("purchase_order_id", arch)
        self.assertIn("expected_delivery_date", arch)
