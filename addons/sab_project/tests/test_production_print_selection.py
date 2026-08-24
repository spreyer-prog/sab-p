import base64

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

    def test_list_print_keeps_every_document_in_its_own_report_action(self):
        self.production.action_prepare_production_documents()
        documents = self.production.document_ids.filtered(
            lambda document: document.document_type in ("run_card", "nameplate")
            and document.cabinet_instance_no == 1
        )

        action = documents.action_print_documents_separately()

        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "sab_production_multi_print")
        self.assertEqual(
            action["params"]["menu_id"],
            self.env.ref("sab_project.sab_production_document_menu").id,
        )
        jobs = action["params"]["jobs"]
        self.assertEqual(len(jobs), 2)
        self.assertTrue(
            all(len(job["action"]["context"]["active_ids"]) == 1 for job in jobs)
        )
        self.assertEqual(
            {job["action"]["context"]["active_id"] for job in jobs},
            set(documents.ids),
        )
        self.assertEqual(
            {job["action"]["report_name"] for job in jobs},
            {
                "sab_project.report_sab_run_card_studio",
                "sab_project.report_sab_nameplate_studio",
            },
        )

    def test_generic_combined_report_is_not_bound_to_the_print_menu(self):
        report = self.env.ref("sab_project.action_report_sab_production_documents")
        self.assertFalse(report.binding_model_id)

    def test_document_list_exposes_only_the_separate_print_button(self):
        source = self.env.ref(
            "sab_project.view_sab_production_document_list"
        ).arch_db
        self.assertIn("action_print_documents_separately", source)
        self.assertIn("Ausgewählte Blätter einzeln drucken / speichern", source)

    def test_document_navigation_returns_to_the_sab_p_suite(self):
        action = self.production.action_view_production_documents()

        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "sab_open_suite_action")
        self.assertEqual(action["target"], "main")
        self.assertEqual(
            action["params"]["menu_id"],
            self.env.ref("sab_project.sab_production_document_menu").id,
        )
        document_action = action["params"]["action"]
        self.assertEqual(document_action["res_model"], "sab.production.document")
        self.assertEqual(document_action["target"], "main")
        self.assertEqual(
            document_action["domain"],
            [("production_order_id", "=", self.production.id)],
        )

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
            "nameplate": ("landscape", 265.0, 176.0),
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
            "sab_project.report_sab_run_card_studio",
        )
        self.assertEqual(action["name"], "Laufkarte")
        self.assertNotIn("Fertigungsblätter", action["name"])
        self.assertNotIn("/", action["name"])

        report = self.env.ref("sab_project.action_report_sab_production_documents")
        self.assertEqual(report.print_report_name, "object._sab_pdf_filename()")

    def test_each_single_pdf_filename_is_exactly_its_document_type(self):
        self.production.action_prepare_production_documents()
        expected = {
            "conformity": "Konformitätserklärung",
            "production_test": "Prüfprotokoll Fertigung",
            "final_inspection": "Prüfprotokoll Endkontrolle",
            "run_card": "Laufkarte",
            "missing_parts": "Bestellung Fehlteile",
            "shipping_sheet": "Versandblatt",
            "add_pack": "Beipackzettel",
            "nameplate": "Typenschild",
            "info_sheet": "Infoschild",
            "folder_label": "Ordneretikett",
        }
        for document_type, filename in expected.items():
            document = self.production.document_ids.filtered(
                lambda item: item.document_type == document_type
            )[0]
            self.assertEqual(document._sab_pdf_filename(), filename)

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
        self.assertEqual(
            runtime_report.report_name,
            "sab_project.report_sab_run_card_studio",
        )
        self.assertEqual(
            runtime_report.print_report_name,
            "object._sab_pdf_filename()",
        )
        paper = runtime_report.paperformat_id
        self.assertTrue(paper)
        self.assertEqual(paper.format, "custom")
        self.assertEqual(paper.orientation, "Landscape")
        self.assertEqual(paper.page_width, 205.0)
        self.assertEqual(paper.page_height, 281.0)
        self.assertEqual(paper.margin_top, 3.0)
        self.assertEqual(paper.margin_bottom, 4.0)
        self.assertEqual(paper.margin_left, 5.0)
        self.assertEqual(paper.margin_right, 6.0)

    def test_each_document_type_routes_to_its_studio_report(self):
        self.production.action_prepare_production_documents()
        expected = {
            "conformity": "sab_project.report_sab_conformity_studio",
            "run_card": "sab_project.report_sab_run_card_studio",
            "production_test": "sab_project.report_sab_production_test_studio",
            "final_inspection": "sab_project.report_sab_final_inspection_studio",
            "missing_parts": "sab_project.report_sab_missing_parts_studio",
            "shipping_sheet": "sab_project.report_sab_shipping_sheet_studio",
            "add_pack": "sab_project.report_sab_add_pack_studio",
            "nameplate": "sab_project.report_sab_nameplate_studio",
            "info_sheet": "sab_project.report_sab_info_sheet_studio",
            "folder_label": "sab_project.report_sab_folder_label_studio",
        }
        documents = self.production.document_ids
        self.assertTrue(set(expected).issubset(set(documents.mapped("document_type"))))
        for document_type, report_name in expected.items():
            document = documents.filtered(
                lambda item, kind=document_type: item.document_type == kind
            )[:1]
            action = document.action_print_document()
            self.assertEqual(action["report_name"], report_name)

    def test_pdf_logo_is_embedded_and_does_not_require_an_http_request(self):
        self.production.action_prepare_production_documents()
        document = self.production.document_ids[:1]
        source = document._sab_report_logo_src()
        self.assertTrue(source.startswith("data:image/jpeg;base64,"))
        image_data = base64.b64decode(source.split(",", 1)[1])
        self.assertTrue(image_data.startswith(b"\xff\xd8"))
        self.assertTrue(image_data.endswith(b"\xff\xd9"))

    def test_studio_templates_keep_german_source_text_untranslated(self):
        page_views = (
            "sab_project.report_sab_conformity_studio_page",
            "sab_project.report_sab_run_card_studio_page",
            "sab_project.report_sab_production_test_studio_page",
            "sab_project.report_sab_final_inspection_studio_page",
            "sab_project.report_sab_missing_parts_studio_page",
            "sab_project.report_sab_shipping_sheet_studio_page",
            "sab_project.report_sab_add_pack_studio_page",
            "sab_project.report_sab_nameplate_studio_page",
            "sab_project.report_sab_info_sheet_studio_page",
            "sab_project.report_sab_folder_label_studio_page",
        )
        for xmlid in page_views:
            source = self.env.ref(xmlid).with_context(lang=None).arch_db
            self.assertIn(
                't-translation="off"',
                source,
                "%s lässt feste deutsche Texte erneut übersetzen" % xmlid,
            )

        reset = self.env.ref("sab_project.report_sab_studio_pdf_reset").arch_db
        self.assertIn("main.container", reset)
        self.assertIn("max-width: none", reset)
        self.assertIn("print-color-adjust: exact", reset)

        utf8_head = self.env.ref("sab_project.report_sab_utf8_head").arch_db
        self.assertIn("Content-Type", utf8_head)
        self.assertIn("charset=utf-8", utf8_head)

        report_views = (
            "sab_project.report_sab_conformity_studio",
            "sab_project.report_sab_run_card_studio",
            "sab_project.report_sab_production_test_studio",
            "sab_project.report_sab_final_inspection_studio",
            "sab_project.report_sab_missing_parts_studio",
            "sab_project.report_sab_shipping_sheet_studio",
            "sab_project.report_sab_add_pack_studio",
            "sab_project.report_sab_nameplate_studio",
            "sab_project.report_sab_info_sheet_studio",
            "sab_project.report_sab_folder_label_studio",
        )
        for xmlid in report_views:
            source = self.env.ref(xmlid).with_context(lang=None).arch_db
            self.assertIn("report_sab_studio_pdf_reset", source)

    def test_exact_layout_reports_use_calibrated_render_dpi(self):
        corrected = (
            "paperformat_sab_run_card_studio",
            "paperformat_sab_production_test_studio",
            "paperformat_sab_final_inspection_studio",
            "paperformat_sab_missing_parts_studio",
            "paperformat_sab_shipping_sheet_studio",
            "paperformat_sab_add_pack_studio",
            "paperformat_sab_nameplate_studio",
            "paperformat_sab_info_sheet_studio",
        )
        for xmlid in corrected:
            self.assertEqual(self.env.ref("sab_project.%s" % xmlid).dpi, 77)
        for xmlid in (
            "paperformat_sab_conformity_studio",
            "paperformat_sab_folder_label_studio",
        ):
            self.assertEqual(self.env.ref("sab_project.%s" % xmlid).dpi, 90)

    def test_inspection_and_missing_parts_grids_have_stable_css_hooks(self):
        expectations = {
            "sab_project.report_sab_production_test_studio_page": "sab-production-test-grid",
            "sab_project.report_sab_final_inspection_studio_page": "sab-final-inspection-grid",
            "sab_project.report_sab_missing_parts_studio_page": "sab-missing-parts-grid",
        }
        for xmlid, css_class in expectations.items():
            source = self.env.ref(xmlid).with_context(lang=None).arch_db
            self.assertIn(css_class, source)
