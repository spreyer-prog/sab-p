from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabProductionDocumentMasterLayouts(TransactionCase):
    """Protect the production-sheet master overrides used for the legacy forms.

    These tests cannot replace a visual PDF comparison, but they ensure that the
    exact-layout QWeb layers stay installed and keep the fixed millimetre geometry
    for every legacy sheet for which an original reference is available.
    """

    def _view_arch(self, xmlid):
        view = self.env.ref(xmlid)
        return etree.fromstring(view.arch_db.encode())

    def test_master_v2_contains_run_card_and_both_inspection_pages(self):
        arch = self._view_arch("sab_project.report_sab_production_document_master_v2")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("run_card", xml)
        self.assertIn("production_test", xml)
        self.assertIn("final_inspection", xml)
        self.assertIn("mm", xml)
        self.assertIn("Mechanische Fertigung", xml)
        self.assertIn("Prüfprotokoll der Fertigung", xml)
        self.assertIn("Prüfprotokoll Endkontrolle", xml)

    def test_master_v5_keeps_legacy_table_sheets_horizontal_on_one_page(self):
        arch = self._view_arch(
            "sab_project.report_sab_production_document_master_v5_orientation"
        )
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("sab-run-card-landscape", xml)
        self.assertIn("sab-test-landscape", xml)
        self.assertIn("sab-final-landscape", xml)
        self.assertIn("width: 277mm", xml)
        self.assertIn("height: 190mm", xml)
        self.assertIn("rotate(90deg)", xml)
        self.assertIn("page-break-inside: avoid", xml)

    def test_master_v6_native_formats_do_not_double_rotate_special_reports(self):
        arch = self._view_arch(
            "sab_project.report_sab_production_document_master_v6_native_formats"
        )
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("sab-master-native-landscape", xml)
        self.assertIn("sab-info-native-page", xml)
        self.assertIn("sab-info-native-card", xml)
        self.assertIn("sab_native_sheet_format", xml)
        self.assertIn("transform: none", xml)
        self.assertIn("width: 265mm", xml)
        self.assertIn("height: 176mm", xml)
        self.assertIn("width: 277mm", xml)
        self.assertIn("height: 190mm", xml)

    def test_master_v7_native_typography_prevents_text_overlap(self):
        arch = self._view_arch(
            "sab_project.report_sab_production_document_master_v7_native_typography"
        )
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("sab-master-native-landscape", xml)
        self.assertIn("line-height: 1.14", xml)
        self.assertIn("vertical-align: middle", xml)
        self.assertIn("white-space: normal", xml)
        self.assertIn("overflow-wrap: break-word", xml)
        self.assertIn("height: 5.15mm", xml)
        self.assertIn("height: 7.4mm", xml)
        self.assertIn("height: 31mm", xml)

    def test_conformity_master_contains_complete_six_page_legacy_set(self):
        arch = self._view_arch(
            "sab_project.report_sab_production_document_conformity"
        )
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("doc.document_type == 'conformity'", xml)
        self.assertEqual(xml.count('class="sab-conf-page"'), 6)
        self.assertIn("Deckblatt &amp; Übersicht der Protokolle", xml)
        self.assertIn("Prüfprotokoll", xml)
        self.assertIn("Erklärung des Herstellers", xml)
        self.assertIn("Bestätigung der DGUV V3", xml)
        self.assertIn("EG-Konformitätserklärung", xml)
        self.assertIn("2014/30/EU", xml)
        self.assertIn("2014/35/EU", xml)
        self.assertIn("EN 61000-6-4", xml)
        self.assertIn("EN 60204-1", xml)
        self.assertIn("-6-", xml)

    def test_master_labels_contains_nameplate_and_info_sheet(self):
        arch = self._view_arch("sab_project.report_sab_production_document_master_labels")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("nameplate", xml)
        self.assertIn("info_sheet", xml)
        self.assertIn("Bemessungs-", xml)
        self.assertIn("DIN VDE 0100-600", xml)
        self.assertIn("Überspannungschutz", xml)
        self.assertIn("rotate(-90deg)", xml)
        self.assertIn("Arial Narrow", xml)
        self.assertIn("doc.inspector_name", xml)
        self.assertIn("doc.inspection_date", xml)
        self.assertIn("doc.next_maintenance_date", xml)
        self.assertGreaterEqual(xml.count("dd.MM.yyyy"), 2)
        self.assertIn("mm", xml)

    def test_master_v3_contains_missing_parts_shipping_and_add_pack(self):
        arch = self._view_arch("sab_project.report_sab_production_document_master_v3")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("missing_parts", xml)
        self.assertIn("shipping_sheet", xml)
        self.assertIn("add_pack", xml)
        self.assertIn("Bestellung Fehlteile", xml)
        self.assertIn("Beipackzettel", xml)
        self.assertIn("Arial Narrow", xml)
        self.assertIn("letter-spacing", xml)
        self.assertIn("mm", xml)

    def test_folder_label_master_uses_project_number_and_fixed_mm_geometry(self):
        arch = self._view_arch("sab_project.report_sab_production_document_folder_label")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("folder_label", xml)
        self.assertIn("sab_project_reference", xml)
        self.assertIn("Liefertermin", xml)
        self.assertIn("dd.MM.yyyy", xml)
        self.assertIn("Arial Narrow", xml)
        self.assertIn("✌", xml)
        self.assertGreaterEqual(xml.count("✌"), 3)
        self.assertIn("mm", xml)
