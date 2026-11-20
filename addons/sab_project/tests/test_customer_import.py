import base64

from lxml import etree

from odoo.tests.common import TransactionCase


HEADERS = [
    "Name/Firma", "Ort - Standard Rechnungsadresse", "Debitorenkonto", "Kundennummer", "USt-IdNr.",
    "Bankkonto-Nummer", "Bankleitzahl", "Bankbezeichnung", "Länderkennz. Bank", "IBAN", "SWIFT-Code",
    "Anrede", "Adresszusatz - Standard Rechnungsadresse", "Straße, Hnr. - Standard Rechnungsadresse",
    "PLZ - Standard Rechnungsadresse", "Steuernummer", "Ansprechpartner", "Ansprechpartner Telefon",
    "Ansprechpartner E-Mail", "Ansprechpartner Sonstige 1", "Ansprechpartner Internet",
    "Land - Standard Rechnungsadresse", "Land-USt-IdNr.", "Bezeichnung Adresse - Standard Rechnungsadresse",
    "Straße, Hnr. - Weitere Rechnungsadresse", "PLZ - Weitere Rechnungsadresse", "Ort - Weitere Rechnungsadresse",
    "Land - Weitere Rechnungsadresse", "Adresszusatz - Weitere Rechnungsadresse", "Bezeichnung Adresse - Weitere Rechnungsadresse",
    "Name - Standard Lieferadresse", "Straße, Hnr. - Standard Lieferadresse", "PLZ - Standard Lieferadresse",
    "Ort - Standard Lieferadresse", "Land - Standard Lieferadresse", "Adresszusatz - Standard Lieferadresse",
    "Bezeichnung Adresse - Standard Lieferadresse", "Belegsprache", "Rechnungsformat", "Rechnungs E-Mail",
    "Peppol-ID", "Ansprechpartner E-Mail E-Rechnung", "Sonstige Kundenreferenz", "Leitweg-ID", "TRAFFIQX-ID",
    "Lieferbedingung", "Zahlungsbedingung", "Hinweis für Umsatzsteuer", "Einleitungstext", "Rechnungsrabatt in %",
    "Steuerpflicht", "Notiz Telefon", "Notiz E-Mail", "Notiz Internet", "Ansprechpartner Sonstige 2",
    "Notiz Sonstige 1", "Notiz Sonstige 2",
]


def csv_file(rows):
    lines = [";".join(HEADERS)]
    for row in rows:
        lines.append(";".join(str(row.get(header, "")) for header in HEADERS))
    return base64.b64encode(("\n".join(lines) + "\n").encode("utf-8"))


class TestSabCustomerImport(TransactionCase):

    def _import(self, rows, **values):
        wizard = self.env["sab.customer.import"].create({
            "file_data": csv_file(rows),
            "file_name": "kunden.csv",
            **values,
        })
        wizard.action_import()
        return wizard

    def test_import_creates_customer_contact_addresses_and_bank(self):
        row = {
            "Name/Firma": "Import Kunde GmbH",
            "Debitorenkonto": "10501",
            "Kundennummer": "101234",
            "USt-IdNr.": "DE123456789",
            "Straße, Hnr. - Standard Rechnungsadresse": "Hauptstraße 1",
            "PLZ - Standard Rechnungsadresse": "42929",
            "Ort - Standard Rechnungsadresse": "Wermelskirchen",
            "Land - Standard Rechnungsadresse": "DE",
            "Ansprechpartner": "Max Mustermann",
            "Ansprechpartner Telefon": "+49 2196 123",
            "Ansprechpartner E-Mail": "max@example.invalid",
            "Straße, Hnr. - Weitere Rechnungsadresse": "Rechnung 2",
            "PLZ - Weitere Rechnungsadresse": "42929",
            "Ort - Weitere Rechnungsadresse": "Wermelskirchen",
            "Land - Weitere Rechnungsadresse": "DE",
            "Bezeichnung Adresse - Weitere Rechnungsadresse": "Buchhaltung",
            "Name - Standard Lieferadresse": "Werk 1",
            "Straße, Hnr. - Standard Lieferadresse": "Industriestraße 5",
            "PLZ - Standard Lieferadresse": "42929",
            "Ort - Standard Lieferadresse": "Wermelskirchen",
            "Land - Standard Lieferadresse": "DE",
            "IBAN": "DE02120300000000202051",
            "SWIFT-Code": "BYLADEM1001",
            "Bankbezeichnung": "Testbank",
            "Rechnungsformat": "E-Rechnung",
            "Leitweg-ID": "992-12345",
        }
        wizard = self._import([row])
        partner = self.env["res.partner"].search([("ref", "=", "101234"), ("parent_id", "=", False)])
        self.assertEqual(len(partner), 1)
        self.assertEqual(partner.name, "Import Kunde GmbH")
        self.assertEqual(partner.city, "Wermelskirchen")
        self.assertEqual(partner.country_id.code, "DE")
        self.assertIn("Rechnungsformat: E-Rechnung", partner.comment)
        self.assertIn("Leitweg-ID: 992-12345", partner.comment)
        self.assertEqual(len(partner.child_ids.filtered(lambda child: child.type == "contact" and child.name == "Max Mustermann")), 1)
        self.assertEqual(len(partner.child_ids.filtered(lambda child: child.type == "invoice")), 1)
        self.assertEqual(len(partner.child_ids.filtered(lambda child: child.type == "delivery")), 1)
        self.assertEqual(len(partner.bank_ids), 1)
        self.assertEqual(partner.bank_ids.acc_number.replace(" ", ""), "DE02120300000000202051")
        self.assertIn("1 Kunden neu", wizard.result_text)

    def test_repeat_import_updates_without_duplicates_and_keeps_nonempty_odoo_data(self):
        first = {"Name/Firma": "Wiederhol Kunde GmbH", "Kundennummer": "101235", "Ort - Standard Rechnungsadresse": "Köln", "Land - Standard Rechnungsadresse": "DE"}
        self._import([first])
        partner = self.env["res.partner"].search([("ref", "=", "101235"), ("parent_id", "=", False)])
        partner.write({"phone": "+49 221 999", "website": "https://intern.example.invalid"})
        second = {"Name/Firma": "Wiederhol Kunde GmbH", "Kundennummer": "101235", "Ort - Standard Rechnungsadresse": "Leverkusen", "Land - Standard Rechnungsadresse": "DE"}
        wizard = self._import([second])
        partners = self.env["res.partner"].search([("ref", "=", "101235"), ("parent_id", "=", False)])
        self.assertEqual(len(partners), 1)
        self.assertEqual(partners.city, "Leverkusen")
        self.assertEqual(partners.phone, "+49 221 999")
        self.assertEqual(partners.website, "https://intern.example.invalid")
        self.assertIn("1 aktualisiert", wizard.result_text)

    def test_same_company_name_with_different_debtor_accounts_stays_separate(self):
        self._import([
            {"Name/Firma": "ABH Stromschienen GmbH", "Debitorenkonto": "10740"},
            {"Name/Firma": "ABH Stromschienen GmbH", "Debitorenkonto": "10027"},
        ])
        partners = self.env["res.partner"].search([("name", "=", "ABH Stromschienen GmbH"), ("parent_id", "=", False)])
        self.assertEqual(len(partners), 2)
        self.assertEqual(set(partners.mapped("ref")), {"10740", "10027"})

    def test_customer_list_has_visible_import_button(self):
        view = self.env.ref("sab_project.view_sab_partner_list_customer_import")
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        buttons = arch.xpath("//header/button[@string='Kunden importieren']")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("display"), "always")
        self.assertEqual(buttons[0].get("type"), "action")
