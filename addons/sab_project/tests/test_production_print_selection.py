from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabProductionPrintSelection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({"name": "Kunde Fertigungsdruck"})
        cls.project = cls.env["project.project"].create(
            {"name": "Projekt Fertigungsdruck", "partner_id": cls.customer.id}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
            }
        )
        cls.material = cls.env["sab.product"].create(
            {
                "name": "Material Fertigungsdruck",
                "manufacturer_article_number": "PRINT-001",
            }
        )
        cls.cabinet = cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.order.id,
                "line_type": "cabinet",
                "description": "UV PRINT",
                "quantity": 2.0,
                "sequence": 10,
            }
        )
        line_values = {
            "sequence": 10,
            "product_id": cls.material.id,
            "odoo_product_id": cls.material.odoo_product_id.id,
            "quantity": 1.0,
            "unit": "pcs",
        }
        cls.cabinet_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL PRINT / UV PRINT",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cls.cabinet.id,
                "line_ids": [Command.create(line_values)],
            }
        )
        cls.total_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL PRINT / GESAMT",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "total",
                "line_ids": [Command.create(line_values)],
            }
        )
        cls.total_bom.action_release()
        cls.production = cls.env["sab.production.order"].create(
            {"name": "FA PRINT", "bom_id": cls.total_bom.id}
        )

    def test_print_wizard_has_one_row_per_physical_cabinet_and_selected_only(self):
        self.production.action_prepare_production_documents()
        Wizard = self.env["sab.production.print.wizard"].with_context(
            default_production_order_id=self.production.id,
            active_id=self.production.id,
        )
        values = Wizard.default_get(["production_order_id", "line_ids"])
        wizard = Wizard.create(values)

        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(
            set(wizard.line_ids.mapped("cabinet_instance_no")),
            {1, 2},
        )

        first = wizard.line_ids.sorted("cabinet_instance_no")[0]
        first.write({"print_run_card": True, "print_nameplate": True})
        action = wizard.action_print_selected()

        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(
            action["report_name"],
            "sab_project.report_sab_production_document",
        )
        self.assertFalse(wizard.line_ids.sorted("cabinet_instance_no")[1].print_run_card)

    def test_single_document_has_direct_print_action(self):
        self.production.action_prepare_production_documents()
        document = self.production.document_ids.filtered(
            lambda item: item.document_type == "run_card"
        )[0]
        action = document.action_print_document()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(
            action["report_name"],
            "sab_project.report_sab_production_document",
        )
