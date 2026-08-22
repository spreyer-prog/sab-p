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

    def test_master_labels_contains_nameplate_and_info_sheet(self):
        arch = self._view_arch("sab_project.report_sab_production_document_master_labels")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("nameplate", xml)
        self.assertIn("info_sheet", xml)
        self.assertIn("Bemessungs-", xml)
        self.assertIn("DIN VDE 0100-600", xml)
        self.assertIn("Überspannungschutz", xml)
        self.assertIn("rotate(-90deg)", xml)
        self.assertIn("mm", xml)

    def test_master_v3_contains_missing_parts_shipping_and_add_pack(self):
        arch = self._view_arch("sab_project.report_sab_production_document_master_v3")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("missing_parts", xml)
        self.assertIn("shipping_sheet", xml)
        self.assertIn("add_pack", xml)
        self.assertIn("Bestellung Fehlteile", xml)
        self.assertIn("Beipackzettel", xml)
        self.assertIn("mm", xml)

    def test_folder_label_master_uses_project_number_and_fixed_mm_geometry(self):
        arch = self._view_arch("sab_project.report_sab_production_document_folder_label")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn("folder_label", xml)
        self.assertIn("sab_project_reference", xml)
        self.assertIn("Liefertermin", xml)
        self.assertIn("dd.MM.yyyy", xml)
        self.assertIn("mm", xml)
