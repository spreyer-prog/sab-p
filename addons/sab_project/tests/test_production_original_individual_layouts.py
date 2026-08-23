from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabProductionOriginalIndividualLayouts(TransactionCase):
    """Each uploaded legacy sheet must own its geometry and paper orientation."""

    def _xml(self, xmlid):
        view = self.env.ref(xmlid)
        return etree.tostring(etree.fromstring(view.arch_db.encode()), encoding="unicode")

    def test_run_card_is_its_own_a4_portrait_original(self):
        inherited_xml = self._xml(
            "sab_project.report_sab_production_document_run_card_original"
        )
        page_xml = self._xml("sab_project.report_sab_run_card_studio_page")
        self.assertIn("doc.document_type == 'run_card'", inherited_xml)
        self.assertIn("report_sab_run_card_studio_page", inherited_xml)
        studio = self.env.ref("sab_project.action_report_sab_run_card_studio")
        self.assertEqual(studio.report_name, "sab_project.report_sab_run_card_studio")
        self.assertEqual(studio.paperformat_id.orientation, "Portrait")
        self.assertEqual((studio.paperformat_id.page_width, studio.paperformat_id.page_height), (210.0, 297.0))
        self.assertIn("width:210mm", page_xml)
        self.assertIn("height:297mm", page_xml)
        self.assertIn("left:24.8mm", page_xml)
        self.assertIn("width:164.7mm", page_xml)
        self.assertNotIn("rotate(90deg)", page_xml)

    def test_production_test_is_its_own_a4_portrait_original(self):
        xml = self._xml("sab_project.report_sab_production_document_production_test_original")
        self.assertIn("doc.document_type == 'production_test'", xml)
        self.assertIn("Prüfprotokoll der Fertigung", xml)
        self.assertIn("left:20.1mm", xml)
        self.assertIn("width:174.7mm", xml)
        self.assertIn("Überprüfung der Schutzleiterbahnen", xml)
        self.assertNotIn("rotate(90deg)", xml)

    def test_final_inspection_is_its_own_a4_portrait_original(self):
        xml = self._xml("sab_project.report_sab_production_document_final_inspection_original")
        self.assertIn("doc.document_type == 'final_inspection'", xml)
        self.assertIn("Prüfprotokoll Endkontrolle", xml)
        self.assertIn("left:20.1mm", xml)
        self.assertIn("width:174.7mm", xml)
        self.assertIn("Beipack vollständig zusammengestellt", xml)
        self.assertNotIn("rotate(90deg)", xml)

    def test_each_remaining_sheet_has_a_separate_original_view(self):
        expectations = {
            "sab_project.report_sab_production_document_shipping_original": ("shipping_sheet", "width:297mm"),
            "sab_project.report_sab_production_document_missing_parts_original": ("missing_parts", "Bestellung Fehlteile"),
            "sab_project.report_sab_production_document_add_pack_original": ("add_pack", "Beipackzettel"),
            "sab_project.report_sab_production_document_nameplate_original": ("nameplate", "width:176mm"),
            "sab_project.report_sab_production_document_info_sheet_original": ("info_sheet", "width:265mm"),
            "sab_project.report_sab_production_document_folder_label_original": ("folder_label", "width:61mm"),
            "sab_project.report_sab_production_document_conformity": ("conformity", "2014/35/EU"),
        }
        for xmlid, (document_type, marker) in expectations.items():
            xml = self._xml(xmlid)
            self.assertIn(document_type, xml, xmlid)
            self.assertIn(marker, xml, xmlid)

    def test_every_sheet_has_an_independent_studio_report(self):
        expected = {
            "conformity": ("Portrait", 210.0, 297.0),
            "run_card": ("Portrait", 210.0, 297.0),
            "production_test": ("Portrait", 210.0, 297.0),
            "final_inspection": ("Portrait", 210.0, 297.0),
            "missing_parts": ("Landscape", 297.0, 210.0),
            "shipping_sheet": ("Landscape", 297.0, 210.0),
            "add_pack": ("Landscape", 297.0, 210.0),
            "nameplate": ("Portrait", 176.0, 265.0),
            "info_sheet": ("Landscape", 265.0, 176.0),
            "folder_label": ("Portrait", 61.0, 192.0),
        }
        for document_type, geometry in expected.items():
            action = self.env.ref(
                "sab_project.action_report_sab_%s_studio" % document_type
            )
            self.assertEqual(
                action.report_name,
                "sab_project.report_sab_%s_studio" % document_type,
            )
            self.assertEqual(action.model, "sab.production.document")
            self.assertEqual(
                (
                    action.paperformat_id.orientation,
                    action.paperformat_id.page_width,
                    action.paperformat_id.page_height,
                ),
                geometry,
            )

    def test_company_standard_profiles_follow_uploaded_original_page_formats(self):
        Profile = self.env["sab.production.print.profile"].sudo()
        Profile._sab_apply_original_standard_profiles()

        for document_type in ("conformity", "run_card", "production_test", "final_inspection"):
            profile = Profile.search(
                [("user_id", "=", False), ("document_type", "=", document_type)],
                limit=1,
            )
            self.assertTrue(profile)
            self.assertEqual(profile.orientation, "portrait")
            self.assertEqual(profile.width_mm, 210.0)
            self.assertEqual(profile.height_mm, 297.0)

        for document_type in ("missing_parts", "shipping_sheet", "add_pack"):
            profile = Profile.search(
                [("user_id", "=", False), ("document_type", "=", document_type)],
                limit=1,
            )
            self.assertTrue(profile)
            self.assertEqual(profile.orientation, "landscape")
            self.assertEqual(profile.width_mm, 297.0)
            self.assertEqual(profile.height_mm, 210.0)

        nameplate = Profile.search(
            [("user_id", "=", False), ("document_type", "=", "nameplate")],
            limit=1,
        )
        info_sheet = Profile.search(
            [("user_id", "=", False), ("document_type", "=", "info_sheet")],
            limit=1,
        )
        folder_label = Profile.search(
            [("user_id", "=", False), ("document_type", "=", "folder_label")],
            limit=1,
        )
        self.assertEqual((nameplate.width_mm, nameplate.height_mm), (176.0, 265.0))
        self.assertEqual((info_sheet.width_mm, info_sheet.height_mm), (265.0, 176.0))
        self.assertEqual((folder_label.width_mm, folder_label.height_mm), (61.0, 192.0))
