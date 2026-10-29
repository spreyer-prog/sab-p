from lxml import etree

from odoo.tests.common import TransactionCase


class TestSabOfferStructureSpacing(TransactionCase):

    def _assert_structure_spacers(self, view_xmlid):
        view = self.env.ref(view_xmlid)
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        spacers = arch.xpath(
            "//tr[contains(concat(' ', normalize-space(@class), ' '), ' sab-structure-spacer ')]"
        )
        self.assertGreaterEqual(
            len(spacers),
            4,
            f"{view_xmlid} benötigt vollständige Leerzeilen vor und nach Bauteilen sowie bei Schaltschränken.",
        )
        self.assertTrue(
            arch.xpath(
                "//t[@t-elif=\"line.line_type == 'section'\"]//tr[contains(@class, 'sab-component-spacer-before')]"
            )
        )
        self.assertTrue(
            arch.xpath(
                "//t[@t-elif=\"line.line_type == 'section_end'\"]//tr[contains(@class, 'sab-component-spacer-after')]"
            )
        )
        self.assertTrue(
            arch.xpath(
                "//tr[contains(@class, 'sab-component-spacer')]/td[@colspan='5' and contains(@style, 'height: 16px')]"
            )
        )
        self.assertTrue(
            arch.xpath(
                "//t[@t-if=\"line.line_type == 'cabinet'\"]//tr[contains(@class, 'sab-cabinet-spacer')]"
            )
        )
        self.assertTrue(
            arch.xpath(
                "//t[@t-elif=\"line.line_type == 'cabinet_end'\"]//tr[contains(@class, 'sab-cabinet-spacer')]"
            )
        )

    def test_customer_portal_separates_switchboards_and_components(self):
        self._assert_structure_spacers(
            "sab_project.sab_sale_order_portal_calculation"
        )

    def test_offer_pdf_separates_switchboards_and_components(self):
        self._assert_structure_spacers(
            "sab_project.sab_report_saleorder_document"
        )
