from odoo.tests import Form

from .test_standard_purchase_bridge import TestSabStandardPurchaseBridge


class TestSabStandardPurchaseSupplierReturn(TestSabStandardPurchaseBridge):
    # Reuse the proven integrated setup/helpers without executing the six
    # purchase-bridge scenarios a second time in this dedicated regression class.
    test_total_bom_release_is_enough_for_procurement_handover = None
    test_requirement_creates_real_odoo_purchase_order = None
    test_supplier_confirmation_deviation_requires_approval = None
    test_standard_purchase_partial_receipt_creates_backorder = None
    test_three_way_mismatch_requires_current_explicit_approval = None
    test_standard_purchase_receipt_and_vendor_bill_flow = None

    def test_standard_purchase_supplier_return_reopens_requirement(self):
        _cabinet, _total, _package, requirement, purchase_order = (
            self._confirm_standard_purchase_order()
        )
        receipt = self._receive_full_purchase_order(
            purchase_order,
            "LS-RETURN-0001",
        )

        purchase_order.order_line.invalidate_recordset()
        requirement.invalidate_recordset()
        self.assertEqual(purchase_order.order_line.qty_received, 6.0)
        self.assertEqual(requirement.state, "received")
        self.assertEqual(requirement.stock_status, "received")
        self.assertEqual(requirement.project_reserved_quantity, 6.0)
        self.assertEqual(requirement.shortage_quantity, 0.0)

        return_form = Form(
            self.env["stock.return.picking"].with_context(
                active_ids=receipt.ids,
                active_id=receipt.id,
                active_model="stock.picking",
            )
        )
        return_wizard = return_form.save()
        self.assertEqual(len(return_wizard.product_return_moves), 1)
        return_wizard.product_return_moves.write(
            {
                "quantity": 2.0,
                "to_refund": True,
            }
        )
        action = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(action["res_id"])
        self.assertEqual(len(return_picking.move_ids), 1)

        return_move = return_picking.move_ids
        self.assertEqual(return_move.sab_purchase_requirement_id, requirement)
        self.assertEqual(return_move.sab_project_id, requirement.project_id)
        self.assertEqual(return_move.sab_procurement_bom_id, requirement.bom_id)
        self.assertEqual(
            return_move.sab_source_cabinet_bom_id,
            requirement.source_cabinet_bom_id,
        )

        return_picking.move_line_ids.write({"quantity": 2.0})
        return_picking.move_ids.picked = True
        return_picking.button_validate()

        purchase_order.order_line.invalidate_recordset()
        requirement.invalidate_recordset()
        self.assertEqual(return_picking.state, "done")
        self.assertEqual(purchase_order.order_line.qty_received, 4.0)
        self.assertEqual(requirement.odoo_quantity_received, 4.0)
        self.assertEqual(requirement.state, "ordered")
        self.assertEqual(requirement.stock_status, "partial_received")
        self.assertEqual(requirement.project_reserved_quantity, 4.0)
        self.assertEqual(requirement.shortage_quantity, 2.0)

        return_release = requirement.stock_movement_ids.filtered(
            lambda movement: movement.odoo_bridge_event == "return_release"
            and movement.odoo_stock_move_id == return_move
        )
        self.assertEqual(len(return_release), 1)
        self.assertEqual(return_release.quantity, 2.0)
