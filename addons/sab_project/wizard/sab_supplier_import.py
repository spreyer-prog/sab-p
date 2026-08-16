import base64
import csv
import io

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabSupplierImport(models.TransientModel):
    _name = "sab.supplier.import"
    _description = "SAB-P Lieferantenstamm Import"

    file_data = fields.Binary(string="Lieferanten-CSV", required=True)
    file_name = fields.Char(string="Dateiname")
    update_existing = fields.Boolean(string="Vorhandene Lieferanten aktualisieren", default=True)
    create_contacts = fields.Boolean(string="Ansprechpartner anlegen", default=True)
    import_bank_data = fields.Boolean(string="Bankdaten importieren", default=True)
    result_text = fields.Text(string="Importergebnis", readonly=True)

    def _decode(self):
        raw = base64.b64decode(self.file_data or b"")
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValidationError(_("Die CSV-Datei konnte nicht als UTF-8/Windows-1252 gelesen werden."))

    def _value(self, row, *names):
        for name in names:
            value = (row.get(name) or "").strip()
            if value:
                return value
        return ""

    def _country(self, value):
        code = (value or "").strip().upper()
        if not code:
            return False
        return self.env["res.country"].search([("code", "=", code)], limit=1)

    def _supplier_number(self, row):
        return self._value(row, "Lieferantennummer", "Kreditorennummer", "Kreditorenkonto", "Lieferanten-Nr.", "Nummer")

    def _supplier_name(self, row):
        return self._value(row, "Name/Firma", "Lieferant", "Firma", "Name")

    def _find_supplier(self, row):
        Supplier = self.env["sab.supplier"].sudo().with_context(active_test=False)
        number = self._supplier_number(row)
        name = self._supplier_name(row)
        if number:
            supplier = Supplier.search([("supplier_number", "=", number)], limit=1)
            if supplier:
                return supplier
        if name:
            matches = Supplier.search([("name", "=", name)], limit=2)
            if len(matches) == 1:
                return matches
        return Supplier

    def _partner_values(self, row):
        country = self._country(self._value(row, "Land", "Land - Standard Rechnungsadresse", "Länderkennzeichen"))
        vals = {"name": self._supplier_name(row), "company_type": "company"}
        mapping = {
            "street": ("Straße, Hnr.", "Straße, Hnr. - Standard Rechnungsadresse", "Straße"),
            "street2": ("Adresszusatz", "Adresszusatz - Standard Rechnungsadresse"),
            "zip": ("PLZ", "PLZ - Standard Rechnungsadresse"),
            "city": ("Ort", "Ort - Standard Rechnungsadresse"),
            "phone": ("Telefon", "Ansprechpartner Telefon"),
            "email": ("E-Mail", "Ansprechpartner E-Mail", "Rechnungs E-Mail"),
            "website": ("Internet", "Website", "Ansprechpartner Internet"),
            "vat": ("USt-IdNr.", "USt-ID", "Umsatzsteuer-ID"),
        }
        for field, aliases in mapping.items():
            value = self._value(row, *aliases)
            if value:
                vals[field] = value
        if country:
            vals["country_id"] = country.id
        return vals

    def _upsert_contact(self, partner, row):
        name = self._value(row, "Ansprechpartner", "Kontaktperson")
        if not name:
            return False
        Partner = self.env["res.partner"].sudo()
        child = Partner.search([("parent_id", "=", partner.id), ("type", "=", "contact"), ("name", "=", name)], limit=1)
        vals = {"parent_id": partner.id, "type": "contact", "name": name}
        email = self._value(row, "Ansprechpartner E-Mail", "E-Mail Ansprechpartner")
        phone = self._value(row, "Ansprechpartner Telefon", "Telefon Ansprechpartner")
        if email:
            vals["email"] = email
        if phone:
            vals["phone"] = phone
        if child:
            child.write(vals)
        else:
            child = Partner.create(vals)
        return child

    def _upsert_bank(self, partner, row):
        account = self._value(row, "IBAN", "Bankkonto-Nummer", "Kontonummer").replace(" ", "")
        if not account:
            return False
        bic = self._value(row, "SWIFT-Code", "BIC", "SWIFT")
        bank_name = self._value(row, "Bankbezeichnung", "Bank", "Bankname")
        Bank = self.env["res.bank"].sudo()
        bank = False
        if bic:
            bank = Bank.search([("bic", "=", bic)], limit=1)
        if not bank and bank_name:
            bank = Bank.search([("name", "=", bank_name)], limit=1)
        if not bank and (bic or bank_name):
            vals = {"name": bank_name or bic}
            if bic:
                vals["bic"] = bic
            bank = Bank.create(vals)
        Account = self.env["res.partner.bank"].sudo()
        record = Account.search([("partner_id", "=", partner.id), ("acc_number", "=", account)], limit=1)
        vals = {"partner_id": partner.id, "acc_number": account}
        if bank:
            vals["bank_id"] = bank.id
        if record:
            record.write(vals)
        else:
            record = Account.create(vals)
        return record

    def action_import(self):
        self.ensure_one()
        reader = csv.DictReader(io.StringIO(self._decode()), delimiter=";")
        if not reader.fieldnames:
            raise ValidationError(_("Die Lieferanten-CSV enthält keine Kopfzeile."))
        created = updated = skipped = contacts = banks = 0
        for row in reader:
            name = self._supplier_name(row)
            if not name:
                skipped += 1
                continue
            supplier = self._find_supplier(row)
            number = self._supplier_number(row)
            website = self._value(row, "Internet", "Website", "Ansprechpartner Internet")
            datanorm = self._value(row, "DATANORM-Kennung", "Datanorm", "DATANORM")
            if supplier:
                if not self.update_existing:
                    skipped += 1
                    continue
            partner = supplier.partner_id if supplier and supplier.partner_id else False
            partner_vals = self._partner_values(row)
            if partner:
                partner.write(partner_vals)
            else:
                partner = self.env["res.partner"].sudo().create(partner_vals)
            supplier_vals = {"name": name, "partner_id": partner.id}
            if number:
                supplier_vals["supplier_number"] = number
            if website:
                supplier_vals["website"] = website
            if datanorm:
                supplier_vals["datanorm_identifier"] = datanorm
            if supplier:
                supplier.write(supplier_vals)
                updated += 1
            else:
                supplier = self.env["sab.supplier"].sudo().create(supplier_vals)
                created += 1
            if self.create_contacts and self._upsert_contact(partner, row):
                contacts += 1
            if self.import_bank_data and self._upsert_bank(partner, row):
                banks += 1

        self.result_text = _("Import abgeschlossen: %(created)s Lieferanten neu, %(updated)s aktualisiert, %(contacts)s Ansprechpartner, %(banks)s Bankverbindungen, %(skipped)s übersprungen.") % {
            "created": created, "updated": updated, "contacts": contacts, "banks": banks, "skipped": skipped,
        }
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
