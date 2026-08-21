from lxml import etree

from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabOperationalProcurementAndPrintPath(TransactionCase):
    """Protect the exact operator path used in the SAB-P UI.

    This test intentionally creates its own master data. It must not depend on
    customer, supplier or material imports performed manually in a test database.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("sab_project.group_sab_purchasing").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchase_approver").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )

        cls.customer = cls.env["res.partner"].create(
            {"name": "E2E Bedienweg Kunde"}
        )
        cls.project = cls.env["project.project"].create(
            {"name": "E2E Bedienweg Projekt", "partner_id": cls.customer.id}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
                "state": "sale",
            }
        )

        cls.supplier = cls.env["sab.supplier"].create(
            {"name": "E2E Bedienweg Lieferant", "supplier_number": "E2E-OP"}
        )
        cls.material = cls.env["sab.product"].create(
            {
                "name": "E2E Bedienweg Material",
                "manufacturer_article_number": "E2E-OP-MAT",
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.material.id,
                "supplier_article_number": "E2E-OP-SUP",
                "purchase_price": 42.0,
                "preferred": True,
            }
        )

        cls.cabinet_line = cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.order.id,
                "line_type": "cabinet",
                "description": "UV E2E BEDIENWEG",
                "quantity": 1.0,
                "sequence": 10,
            }
        )
        common_line = {
            "sequence": 10,
            "product_id": cls.material.id,
            "odoo_product_id": cls.material.odoo_product_id.id,
            "quantity": 1.0,
            "unit": "pcs",
            "supplier_product_id": cls.supplier_product.id,
            "unit_purchase_price": 42.0,
        }
        cls.cabinet_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL E2E / UV E2E BEDIENWEG",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cls.cabinet_line.id,
                "line_ids": [Command.create(common_line)],
            }
        )
        cls.total_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL E2E / GESAMT",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "total",
                "line_ids": [Command.create(common_line)],
            }
        )
        cls.cabinet_bom.action_release()
        cls.total_bom.action_release()

    def test_01_all_operator_buttons_are_declared_on_the_real_views(self):
        handover_view = self.env.ref(
            "sab_project.view_sab_project_bom_form_explicit_procurement_handover"
        )
        handover_arch = etree.fromstring(handover_view.arch_db.encode())
        handover_button = handover_arch.xpath(
            ".//button[@name='action_open_procurement_package_from_bom']"
        )
        self.assertTrue(handover_button)
        self.assertEqual(
            handover_button[0].get("string"), "Stückliste an Einkauf übergeben"
        )
        self.assertIn("base.group_system", handover_button[0].get("groups", ""))

        release_button = handover_arch.xpath(
            ".//button[@name='action_release_for_purchase']"
        )
        self.assertTrue(release_button)
        self.assertEqual(
            release_button[0].xpath("./attribute[@name='string']")[0].text,
            "An Einkauf freigeben",
        )

        requirement_view = self.env.ref(
            "sab_project.view_sab_purchase_requirement_list"
        )
        requirement_arch = etree.fromstring(requirement_view.arch_db.encode())
        selection_button = requirement_arch.xpath(
            ".//header/button[@name='action_create_standard_purchase_orders_from_selection']"
        )
        self.assertTrue(selection_button)
        self.assertEqual(
            selection_button[0].get("string"),
            "Bestellvorschlag aus markierten Positionen",
        )
        self.assertIn("base.group_system", selection_button[0].get("groups", ""))

        row_button = requirement_arch.xpath(
            ".//list/button[@name='action_create_standard_purchase_orders_from_selection']"
        )
        self.assertTrue(row_button)
        self.assertEqual(row_button[0].get("string"), "Bestellen")
        self.assertIn("base.group_system", row_button[0].get("groups", ""))

    def test_02_full_handover_to_real_purchase_order_without_manual_imports(self):
        handover = self.total_bom.action_open_procurement_package_from_bom()
        self.assertEqual(handover["res_model"], "sab.procurement.package.wizard")
        self.assertEqual(handover["target"], "new")

        Wizard = self.env["sab.procurement.package.wizard"].with_context(
            **handover["context"]
        )
        values = Wizard.default_get(["order_id", "cabinet_bom_ids"])
        wizard = Wizard.create(values)
        self.assertEqual(wizard.order_id, self.order)
        self.assertIn(self.cabinet_bom, wizard.cabinet_bom_ids)

        package_action = wizard.action_create_procurement_package()
        package = self.env["sab.project.bom"].browse(package_action["res_id"])
        self.assertEqual(package.bom_scope, "procurement")
        self.assertEqual(package.state, "released")
        self.assertIn(self.cabinet_bom, package.source_cabinet_bom_ids)
        self.assertEqual(package.purchase_release_state, "not_released")

        workspace_action = package.action_release_for_purchase()
        self.assertEqual(package.purchase_release_state, "released")
        self.assertEqual(workspace_action["res_model"], "sab.purchase.requirement")

        requirements = package.purchase_requirement_ids.filtered(
            lambda requirement: requirement.state == "open"
            and not requirement.optional
        )
        self.assertEqual(len(requirements), 1)
        requirement = requirements[0]
        requirement._sab_prepare_order_quantities(force=True)
        self.assertGreater(requirement.quantity_to_order, 0)

        purchase_action = requirement.action_create_standard_purchase_orders_from_selection()
        self.assertEqual(purchase_action["res_model"], "purchase.order")
        purchase_orders = self.env["purchase.order"].browse(
            purchase_action["domain"][0][2]
        )
        self.assertEqual(len(purchase_orders), 1)
        self.assertEqual(purchase_orders.state, "draft")
        self.assertEqual(len(purchase_orders.order_line.filtered(lambda line: not line.display_type)), 1)
        self.assertEqual(
            purchase_orders.order_line.filtered(lambda line: not line.display_type).sab_purchase_requirement_id,
            requirement,
        )

    def test_03_production_document_selection_and_direct_print_are_reachable(self):
        production_action = self.cabinet_bom.action_create_production_order()
        production = self.env["sab.production.order"].browse(
            production_action["res_id"]
        )
        production.action_prepare_production_documents()
        self.assertTrue(production.document_ids)

        print_action = production.action_open_production_print_wizard()
        self.assertEqual(print_action["res_model"], "sab.production.print.wizard")
        self.assertEqual(print_action["target"], "new")

        Wizard = self.env["sab.production.print.wizard"].with_context(
            **print_action.get("context", {}),
            active_id=production.id,
            default_production_order_id=production.id,
        )
        values = Wizard.default_get(["production_order_id", "line_ids"])
        wizard = Wizard.create(values)
        self.assertEqual(len(wizard.line_ids), 1)
        wizard.line_ids.write(
            {
                "print_run_card": True,
                "print_production_test": True,
                "print_final_inspection": True,
                "print_nameplate": True,
            }
        )
        report_action = wizard.action_print_selected()
        self.assertEqual(report_action["type"], "ir.actions.report")
        self.assertEqual(
            report_action["report_name"],
            "sab_project.report_sab_production_document",
        )

        run_card = production.document_ids.filtered(
            lambda document: document.document_type == "run_card"
        )[:1]
        self.assertTrue(run_card)
        direct_action = run_card.action_print_document()
        self.assertEqual(direct_action["type"], "ir.actions.report")
