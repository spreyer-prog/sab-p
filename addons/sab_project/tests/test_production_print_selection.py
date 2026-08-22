from odoo.fields import Command
from odoo.tests.common import TransactionCase


PRINT_FIELDS = (
    "print_conformity",
    "print_production_test",
    "print_final_inspection",
    "print_run_card",
    "print_missing_parts",
    "print_shipping_sheet",
    "print_add_pack",
    "print_nameplate",
    "print_info_sheet",
    "print_folder_label",
)


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

    def _wizard(self):
        self.production.action_prepare_production_documents()
        Wizard = self.env["sab.production.print.wizard"].with_context(
            default_production_order_id=self.production.id,
            active_id=self.production.id,
        )
        values = Wizard.default_get(["production_order_id", "line_ids"])
        return Wizard.create(values)

    def test_print_wizard_has_one_row_per_physical_cabinet_and_selected_only(self):
        wizard = self._wizard()

        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(
            set(wizard.line_ids.mapped("cabinet_instance_no")),
            {1, 2},
        )

        first = wizard.line_ids.sorted("cabinet_instance_no")[0]
        first.write({"print_run_card": True, "print_nameplate": True})
        action = wizard.action_print_selected()

        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "sab_production_multi_print")
        self.assertEqual(len(action["params"]["jobs"]), 2)
        self.assertEqual(
            {job["action"]["context"]["active_id"] for job in action["params"]["jobs"]},
            set(wizard._selected_documents().ids),
        )
        self.assertFalse(wizard.line_ids.sorted("cabinet_instance_no")[1].print_run_card)

    def test_select_all_marks_every_sheet_and_renders_complete_folder(self):
        wizard = self._wizard()

        reopen = wizard.action_select_all()
        self.assertEqual(reopen["res_id"], wizard.id)
        for line in wizard.line_ids:
            for field_name in PRINT_FIELDS:
                self.assertTrue(
                    line[field_name],
                    "%s wurde durch 'Alle Blätter markieren' nicht gesetzt" % field_name,
                )

        selected = wizard._selected_documents()
        expected_count = len(wizard.line_ids) * len(PRINT_FIELDS)
        self.assertEqual(len(selected), expected_count)

        action = wizard.action_print_selected()
        self.assertEqual(action["type"], "ir.actions.client")
        jobs = action["params"]["jobs"]
        self.assertEqual(len(jobs), expected_count)
        self.assertEqual(
            {job["action"]["context"]["active_id"] for job in jobs},
            set(selected.ids),
        )
        self.assertTrue(
            all(len(job["action"]["context"]["active_ids"]) == 1 for job in jobs)
        )

        first_job = jobs[0]["action"]
        runtime_report = self.env["ir.actions.report"].browse(first_job["id"])
        html, _report_type = runtime_report.with_context(
            first_job["context"]
        )._render_qweb_html(runtime_report.report_name, first_job["context"]["active_ids"])
        self.assertTrue(html)

    def test_approved_original_formats_are_the_company_defaults(self):
        profiles = self.env["sab.production.print.profile"]
        profiles._sab_apply_original_standard_profiles()
        expected = {
            "conformity": ("portrait", 210.0, 297.0),
            "run_card": ("portrait", 210.0, 297.0),
            "production_test": ("portrait", 210.0, 297.0),
            "final_inspection": ("portrait", 210.0, 297.0),
            "missing_parts": ("landscape", 297.0, 210.0),
            "shipping_sheet": ("landscape", 297.0, 210.0),
            "add_pack": ("landscape", 297.0, 210.0),
            "nameplate": ("portrait", 176.0, 265.0),
            "info_sheet": ("landscape", 265.0, 176.0),
            "folder_label": ("portrait", 61.0, 192.0),
        }
        for document_type, geometry in expected.items():
            profile = profiles.search(
                [("user_id", "=", False), ("document_type", "=", document_type)],
                limit=1,
            )
            self.assertEqual(
                (profile.orientation, profile.width_mm, profile.height_mm),
                geometry,
            )

    def test_single_document_has_direct_print_action_and_specific_filename(self):
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
        self.assertIn("Laufkarte", action["name"])
        self.assertNotIn("Fertigungsblätter", action["name"])
        self.assertNotIn("/", action["name"])

        report = self.env.ref("sab_project.action_report_sab_production_documents")
        self.assertEqual(report.print_report_name, "object._sab_pdf_filename()")

    def test_personal_print_profile_controls_paperformat_and_printer_context(self):
        self.production.action_prepare_production_documents()
        document = self.production.document_ids.filtered(
            lambda item: item.document_type == "run_card"
        )[0]
        profile = self.env["sab.production.print.profile"].create(
            {
                "user_id": self.env.user.id,
                "document_type": "run_card",
                "paper_kind": "custom",
                "orientation": "landscape",
                "width_mm": 281.0,
                "height_mm": 205.0,
                "margin_top_mm": 3.0,
                "margin_bottom_mm": 4.0,
                "margin_left_mm": 5.0,
                "margin_right_mm": 6.0,
                "printer_name": "TEST-QUERDRUCKER",
                "scale_percent": 97.0,
            }
        )

        action = document.action_print_document()
        self.assertEqual(action["context"]["sab_print_profile_id"], profile.id)
        self.assertEqual(action["context"]["sab_printer_name"], "TEST-QUERDRUCKER")
        self.assertEqual(action["context"]["sab_print_scale_percent"], 97.0)
        self.assertEqual(action["context"]["sab_print_width_mm"], 281.0)
        self.assertEqual(action["context"]["sab_print_height_mm"], 205.0)

        runtime_report = self.env["ir.actions.report"].browse(action["id"])
        paper = runtime_report.paperformat_id
        self.assertTrue(paper)
        self.assertEqual(paper.format, "custom")
        self.assertEqual(paper.orientation, "Landscape")
        self.assertEqual(paper.page_width, 281.0)
        self.assertEqual(paper.page_height, 205.0)
        self.assertEqual(paper.margin_top, 3.0)
        self.assertEqual(paper.margin_bottom, 4.0)
        self.assertEqual(paper.margin_left, 5.0)
        self.assertEqual(paper.margin_right, 6.0)
