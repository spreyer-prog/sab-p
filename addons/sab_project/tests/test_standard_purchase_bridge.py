from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.fields import Command


class TestSabStandardPurchaseBridge(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("sab_project.group_sab_purchasing").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchase_approver").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_warehouse").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )

        cls.customer = cls.env["res.partner"].create(
            {"name": "Kunde Standardbeschaffung"}
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {
                "name": "Lieferant Standardbeschaffung",
                "supplier_number": "L-STD-001",
            }
        )
        cls.supplier.partner_id.write(
            {
                "email": "standardbeschaffung@example.invalid",
                "property_account_payable_id": cls.company_data[
                    "default_account_payable"
                ].id,
                "property_account_receivable_id": cls.company_data[
                    "default_account_receivable"
                ].id,
            }
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Standardbeschaffung",
                "partner_id": cls.customer.id,
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
            }
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "Leistungsschalter Standardbeschaffung",
                "manufacturer_article_number": "STD-100",
            }
        )
        cls.product.odoo_product_id.product_tmpl_id.write(
            {
                "purchase_method": "receive",
                "property_account_expense_id": cls.company_data[
                    "default_account_expense"
                ].id,
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-STD-100",
                "purchase_price": 25.0,
                "packaging_quantity": 1.0,
                "minimum_order_quantity": 1.0,
                "delivery_time_days": 7,
                "preferred": True,
            }
        )

    def _create_released_package(self, cabinet_released=False):
        cabinet_heading = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": self.sale_order.id,
                "line_type": "cabinet",
                "description": "UV-STD-01",
                "sequence": 10,
            }
        )
        line_values = {
            "sequence": 10,
            "product_id": self.product.id,
            "odoo_product_id": self.product.odoo_product_id.id,
            "quantity": 6.0,
            "unit": "pcs",
            "supplier_product_id": self.supplier_product.id,
            "unit_purchase_price": 25.0,
        }
        cabinet_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Standardbeschaffung / UV-STD-01",
                "order_id": self.sale_order.id,
                "project_id": self.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cabinet_heading.id,
                "line_ids": [(0, 0, line_values)],
            }
        )
        if cabinet_released:
            cabinet_bom.action_release()

        total_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Standardbeschaffung / GESAMT",
                "order_id": self.sale_order.id,
                "project_id": self.project.id,
                "bom_scope": "total",
                "line_ids": [(0, 0, line_values)],
            }
        )
        total_bom.action_release()
        self.sale_order.write({"state": "sale"})

        wizard = self.env["sab.procurement.package.wizard"].create(
            {
                "order_id": self.sale_order.id,
                "cabinet_bom_ids": [Command.set([cabinet_bom.id])],
                "require_individual_cabinet_release": False,
            }
        )
        package_action = wizard.action_create_procurement_package()
        package = self.env["sab.project.bom"].browse(package_action["res_id"])
        package.action_release_for_purchase()
        requirement = package.purchase_requirement_ids
        self.assertEqual(len(requirement), 1)
        requirement._sab_prepare_order_quantities(force=True)
        return cabinet_bom, total_bom, package, requirement

    def _create_standard_purchase_order(self):
        cabinet_bom, total_bom, package, requirement = (
            self._create_released_package(cabinet_released=False)
        )
        action = requirement.action_create_standard_purchase_orders()
        order_ids = action["domain"][0][2]
        purchase_order = self.env["purchase.order"].browse(order_ids)
        self.assertEqual(len(purchase_order), 1)
        return cabinet_bom, total_bom, package, requirement, purchase_order

    def test_total_bom_release_is_enough_for_procurement_handover(self):
        cabinet_bom, total_bom, package, requirement = (
            self._create_released_package(cabinet_released=False)
        )
        self.assertEqual(total_bom.state, "released")
        self.assertEqual(cabinet_bom.state, "draft")
        self.assertEqual(package.state, "released")
        self.assertEqual(requirement.source_cabinet_bom_id, cabinet_bom)
        self.assertEqual(
            requirement.source_cabinet_line_id.bom_id,
            cabinet_bom,
        )

    def test_requirement_creates_real_odoo_purchase_order(self):
        _cabinet, _total, package, requirement, purchase_order = (
            self._create_standard_purchase_order()
        )
        self.assertTrue(self.supplier.partner_id)
        self.assertGreaterEqual(self.supplier.partner_id.supplier_rank, 1)
        self.assertTrue(self.supplier_product.odoo_supplierinfo_id)
        self.assertTrue(purchase_order.sab_is_suite_order)
        self.assertEqual(purchase_order.sab_supplier_id, self.supplier)
        self.assertIn(self.project, purchase_order.sab_project_ids)
        self.assertIn(package, purchase_order.sab_procurement_bom_ids)
        self.assertEqual(len(purchase_order.order_line), 1)
        self.assertEqual(
            purchase_order.order_line.sab_purchase_requirement_id,
            requirement,
        )
        self.assertEqual(
            purchase_order.order_line.sab_source_cabinet_bom_id,
            requirement.source_cabinet_bom_id,
        )
        self.assertEqual(requirement.odoo_purchase_order_id, purchase_order)
        self.assertEqual(purchase_order.order_line.product_qty, 6.0)
        self.assertEqual(purchase_order.order_line.price_unit, 25.0)

        with self.assertRaises(ValidationError):
            requirement.action_create_standard_purchase_orders()

    def test_standard_purchase_receipt_and_vendor_bill_flow(self):
        _cabinet, _total, _package, requirement, purchase_order = (
            self._create_standard_purchase_order()
        )
        purchase_order.button_confirm()
        if purchase_order.state == "to approve":
            purchase_order.button_approve()
        self.assertEqual(purchase_order.state, "purchase")
        self.assertEqual(requirement.state, "ordered")

        receipt = purchase_order.picking_ids.filtered(
            lambda picking: picking.picking_type_id.code == "incoming"
            and picking.state != "cancel"
        )
        self.assertEqual(len(receipt), 1)
        self.assertTrue(receipt.sab_is_suite_receipt)
        self.assertIn(self.project, receipt.sab_project_ids)
        self.assertIn(
            requirement.source_cabinet_bom_id,
            receipt.sab_source_cabinet_bom_ids,
        )
        self.assertEqual(
            receipt.move_ids.sab_purchase_requirement_id,
            requirement,
        )

        receipt.write(
            {
                "sab_supplier_delivery_note_number": "LS-STD-0001",
                "sab_supplier_delivery_note_date": fields.Date.today(),
            }
        )
        receipt.move_ids.quantity = purchase_order.order_line.product_qty
        receipt.button_validate()
        self.assertEqual(receipt.state, "done")

        purchase_order.order_line.invalidate_recordset()
        requirement.invalidate_recordset()
        self.assertEqual(purchase_order.order_line.qty_received, 6.0)
        self.assertEqual(requirement.odoo_quantity_received, 6.0)
        self.assertEqual(requirement.state, "received")
        self.assertEqual(requirement.stock_status, "received")
        self.assertEqual(requirement.shortage_quantity, 0.0)

        purchase_order.invalidate_recordset()
        self.assertEqual(purchase_order.invoice_status, "to invoice")
        purchase_order.action_create_invoice()
        bill = purchase_order.invoice_ids
        self.assertEqual(len(bill), 1)
        bill.ref = "RE-STD-0001"
        bill.action_post()

        self.assertEqual(bill.state, "posted")
        self.assertTrue(bill.sab_is_suite_vendor_bill)
        self.assertIn(purchase_order, bill.sab_purchase_order_ids)
        self.assertIn(self.project, bill.sab_project_ids)
        linked_lines = bill.invoice_line_ids.filtered("purchase_line_id")
        self.assertEqual(
            linked_lines.sab_purchase_requirement_id,
            requirement,
        )
        self.assertEqual(
            linked_lines.sab_source_cabinet_bom_id,
            requirement.source_cabinet_bom_id,
        )
