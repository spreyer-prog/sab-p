import base64

from lxml import etree

from odoo.tests.common import TransactionCase


def csv_file(rows):
    headers = ["Lieferant", "Lieferantennummer", "Straße", "PLZ", "Ort", "Land", "USt-IdNr.", "Ansprechpartner", "Ansprechpartner Telefon", "Ansprechpartner E-Mail", "IBAN", "SWIFT-Code", "Bankbezeichnung", "Website", "DATANORM-Kennung"]
    lines = [";".join(headers)]
    for row in rows:
        lines.append(";".join(str(row.get(header, "")) for header in headers))
    return base64.b64encode(("\n".join(lines) + "\n").encode("utf-8"))


class TestSabSupplierImport(TransactionCase):

    def _import(self, rows):
        wizard = self.env["sab.supplier.import"].create({"file_data": csv_file(rows), "file_name": "lieferanten.csv"})
        wizard.action_import()
        return wizard

    def test_supplier_import_creates_master_contact_and_bank(self):
        wizard = self._import([{
            "Lieferant": "Test Lieferant GmbH",
            "Lieferantennummer": "L1001",
            "Straße": "Industriestraße 10",
            "PLZ": "42929",
            "Ort": "Wermelskirchen",
            "Land": "DE",
            "USt-IdNr.": "DE987654321",
            "Ansprechpartner": "Erika Einkauf",
            "Ansprechpartner Telefon": "+49 2196 555",
            "Ansprechpartner E-Mail": "einkauf@example.invalid",
            "IBAN": "DE89370400440532013000",
            "SWIFT-Code": "COBADEFFXXX",
            "Bankbezeichnung": "Testbank Lieferant",
            "Website": "https://supplier.example.invalid",
            "DATANORM-Kennung": "TEST-LIEF",
        }])
        supplier = self.env["sab.supplier"].search([("supplier_number", "=", "L1001")])
        self.assertEqual(len(supplier), 1)
        self.assertEqual(supplier.name, "Test Lieferant GmbH")
        self.assertEqual(supplier.website, "https://supplier.example.invalid")
        self.assertEqual(supplier.datanorm_identifier, "TEST-LIEF")
        self.assertTrue(supplier.partner_id)
        self.assertEqual(supplier.partner_id.city, "Wermelskirchen")
        self.assertEqual(len(supplier.partner_id.child_ids.filtered(lambda child: child.name == "Erika Einkauf")), 1)
        self.assertEqual(len(supplier.partner_id.bank_ids), 1)
        self.assertIn("1 Lieferanten neu", wizard.result_text)

    def test_repeat_supplier_import_updates_without_duplicate(self):
        self._import([{"Lieferant": "Wiederhol Lieferant GmbH", "Lieferantennummer": "L1002", "Ort": "Köln"}])
        self._import([{"Lieferant": "Wiederhol Lieferant GmbH", "Lieferantennummer": "L1002", "Ort": "Leverkusen"}])
        suppliers = self.env["sab.supplier"].search([("supplier_number", "=", "L1002")])
        self.assertEqual(len(suppliers), 1)
        self.assertEqual(suppliers.partner_id.city, "Leverkusen")

    def test_supplier_list_has_visible_import_button(self):
        view = self.env.ref("sab_project.view_sab_supplier_tree_import_button")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        buttons = arch.xpath("//header/button[@string='Lieferanten importieren']")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("display"), "always")
