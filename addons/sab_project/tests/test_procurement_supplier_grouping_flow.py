from odoo.tests.common import TransactionCase


class TestProcurementSupplierGroupingFlow(TransactionCase):

    def test_total_bom_release_also_releases_all_cabinet_boms(self):
        partner = self.env["res.partner"].create({"name": "Kunde Freigabefluss"})
        project = self.env["project.project"].create(
            {"name": "Projekt Freigabefluss", "partner_id": partner.id}
        )
        order = self.env["sale.order"].create(
            {"partner_id": partner.id, "sab_project_id": project.id}
        )
        cabinet_line_a = self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet", "description": "UV1"}
        )
        cabinet_line_b = self.env["sab.offer.calculation.line"].create(
            {"order_id": order.id, "line_type": "cabinet", "description": "UV2"}
        )
        total = self.env["sab.project.bom"].create(
            {
                "name": "STL Gesamt",
                "order_id": order.id,
                "project_id": project.id,
                "bom_scope": "total",
            }
        )
        cabinet_a = self.env["sab.project.bom"].create(
            {
                "name": "STL UV1",
                "order_id": order.id,
                "project_id": project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cabinet_line_a.id,
            }
        )
        cabinet_b = self.env["sab.project.bom"].create(
            {
                "name": "STL UV2",
                "order_id": order.id,
                "project_id": project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cabinet_line_b.id,
            }
        )

        # action_release requires material. One minimal common Odoo product line
        # is sufficient for the release semantics under test.
        product = self.env["product.product"].create({"name": "Testmaterial"})
        for bom in total | cabinet_a | cabinet_b:
            self.env["sab.project.bom.line"].create(
                {
                    "bom_id": bom.id,
                    "odoo_product_id": product.id,
                    "quantity": 1.0,
                    "unit": "pcs",
                }
            )

        total.action_release()
        self.assertEqual(total.state, "released")
        self.assertEqual(cabinet_a.state, "released")
        self.assertEqual(cabinet_b.state, "released")

    def test_mixed_supplier_selection_merges_to_one_proposal_per_supplier(self):
        supplier_a = self.env["res.partner"].create(
            {"name": "Lieferant A", "supplier_rank": 1}
        )
        supplier_b = self.env["res.partner"].create(
            {"name": "Lieferant B", "supplier_rank": 1}
        )
        orders = self.env["purchase.order"]
        for partner in (supplier_a, supplier_a, supplier_b, supplier_b):
            orders |= self.env["purchase.order"].create(
                {"partner_id": partner.id, "sab_is_suite_order": True}
            )

        action = orders.action_sab_merge_selected_orders()
        targets = self.env["purchase.order"].search(
            [("id", "in", action["domain"][0][2])]
        )
        self.assertEqual(len(targets), 2)
        self.assertEqual(set(targets.mapped("partner_id").ids), {supplier_a.id, supplier_b.id})
        cancelled = orders.filtered(lambda order: order.state == "cancel")
        self.assertEqual(len(cancelled), 2)
