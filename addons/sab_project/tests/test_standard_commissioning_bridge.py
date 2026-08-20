from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabStandardCommissioningBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for xmlid in (
            "project.group_project_manager",
            "sab_project.group_sab_purchasing",
            "sab_project.group_sab_purchase_approver",
            "sab_project.group_sab_warehouse",
        ):
            cls.env.ref(xmlid).write(
                {"user_ids": [Command.link(cls.env.user.id)]}
            )

        # Der produktive Workflow verlangt mindestens einen tatsächlich aktiven
        # Einkaufsmitarbeiter. Deshalb bildet der Test auch das SAB-P-
        # Mitarbeiterprofil ab und verlässt sich nicht nur auf Superuser-Rechte.
        cls.procurement_user = cls.env["res.users"].sudo().with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Test Einkauf Kommissionierung",
                "login": "test-einkauf-kommissionierung@example.invalid",
                "email": "test-einkauf-kommissionierung@example.invalid",
                "active": True,
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )
        cls.procurement_profile = cls.env["sab.employee.profile"].create(
            {
                "name": "Test Einkauf Kommissionierung",
                "login": "test-einkauf-kommissionierung@example.invalid",
                "email": "test-einkauf-kommissionierung@example.invalid",
                "user_id": cls.procurement_user.id,
                "mobile_access": False,
                "purchasing_access": True,
                "purchase_approval_access": True,
                "warehouse_access": True,
            }
        )
        cls.procurement_profile.action_apply_permissions()

        cls.customer = cls.env["res.partner"].create(
            {"name": "Kunde Odoo-Kommissionierung"}
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {
                "name": "Lieferant Odoo-Kommissionierung",
                "supplier_number": "L-KOM-001",
            }
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Odoo-Kommissionierung",
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
                "name": "Material Odoo-Kommissionierung",
                "manufacturer_article_number": "KOM-100",
                "product_type": "material",
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-KOM-100",
                "purchase_price": 15.0,
                "unit": "pcs",
                "packaging_quantity": 1.0,
                "minimum_order_quantity": 1.0,
                "preferred": True,
            }
        )

    def _prepare_received_package(self):
        cabinet_heading = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": self.sale_order.id,
                "line_type": "cabinet",
                "description": "UV-KOM-01",
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
            "unit_purchase_price": 15.0,
        }
        cabinet_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Odoo-Kommissionierung / UV-KOM-01",
                "order_id": self.sale_order.id,
                "project_id": self.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cabinet_heading.id,
                "line_ids": [(0, 0, line_values)],
            }
        )
        total_bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Odoo-Kommissionierung / GESAMT",
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
            }
        )
        package_action = wizard.action_create_procurement_package()
        package = self.env["sab.project.bom"].browse(package_action["res_id"])
        package.action_release_for_purchase()
        requirement = package.purchase_requirement_ids
        requirement._sab_prepare_order_quantities(force=True)

        purchase_action = requirement.action_create_standard_purchase_orders()
        purchase_order = self.env["purchase.order"].browse(
            purchase_action["domain"][0][2]
        )
        purchase_order.button_confirm()
        if purchase_order.state == "to approve":
            purchase_order.button_approve()

        receipt = purchase_order.picking_ids.filtered(
            lambda picking: picking.picking_type_id.code == "incoming"
            and picking.state != "cancel"
        )
        receipt.write(
            {
                "sab_supplier_delivery_note_number": "LS-KOM-0001",
                "sab_supplier_delivery_note_date": fields.Date.today(),
            }
        )
        receipt.move_ids.quantity = purchase_order.order_line.product_qty
        receipt.button_validate()
        requirement.invalidate_recordset()
        return cabinet_bom, package, requirement, purchase_order

    def test_received_material_is_commissioned_through_odoo_stock(self):
        cabinet_bom, package, requirement, purchase_order = (
            self._prepare_received_package()
        )
        self.assertEqual(requirement.project_reserved_quantity, 6.0)
        self.assertEqual(requirement.commissioned_quantity, 0.0)

        package.write({"picking_user_id": self.env.user.id})
        action = package.action_complete_picking()
        commission_pickings = self.env["stock.picking"].search(
            [("id", "in", action["domain"][0][2])]
        )

        self.assertEqual(len(commission_pickings), 1)
        self.assertEqual(commission_pickings.state, "done")
        self.assertTrue(commission_pickings.sab_is_suite_commissioning)
        self.assertEqual(commission_pickings.sab_procurement_bom_id, package)
        self.assertIn(self.project, commission_pickings.sab_project_ids)
        self.assertIn(
            cabinet_bom,
            commission_pickings.sab_source_cabinet_bom_ids,
        )

        requirement.invalidate_recordset()
        package.invalidate_recordset()
        self.assertEqual(requirement.project_reserved_quantity, 0.0)
        self.assertEqual(requirement.commissioned_quantity, 6.0)
        self.assertEqual(requirement.stock_status, "commissioned")
        self.assertEqual(package.picking_state, "done")

        bridge_events = self.env["sab.stock.movement"].search(
            [
                ("purchase_requirement_id", "=", requirement.id),
                ("odoo_bridge_event", "in", ("commission_release", "commission_issue")),
            ]
        )
        self.assertEqual(
            set(bridge_events.mapped("odoo_bridge_event")),
            {"commission_release", "commission_issue"},
        )

        warehouse = purchase_order.picking_type_id.warehouse_id
        stock_quantity = self.product.odoo_product_id.with_context(
            location=warehouse.lot_stock_id.id,
        ).qty_available
        self.assertEqual(stock_quantity, 0.0)
