import base64
import csv
import io

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabCustomerImport(models.TransientModel):
    _name = "sab.customer.import"
    _description = "SAB-P Kundenstamm Import"

    file_data = fields.Binary(string="Kunden-CSV", required=True)
    file_name = fields.Char(string="Dateiname")
    update_existing = fields.Boolean(string="Vorhandene Kunden aktualisieren", default=True)
    create_contacts = fields.Boolean(string="Ansprechpartner anlegen", default=True)
    create_delivery_addresses = fields.Boolean(string="Lieferadressen anlegen", default=True)
    create_invoice_addresses = fields.Boolean(string="Weitere Rechnungsadressen anlegen", default=True)
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

    def _country(self, value):
        code = (value or "").strip().upper()
        if not code:
            return False
        return self.env["res.country"].search([("code", "=", code)], limit=1)

    def _external_reference(self, row):
        return (row.get("Kundennummer") or row.get("Debitorenkonto") or "").strip()

    def _find_partner(self, row):
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        reference = self._external_reference(row)
        vat = (row.get("USt-IdNr.") or "").strip()
        name = (row.get("Name/Firma") or "").strip()
        if reference:
            partner = Partner.search([("ref", "=", reference), ("parent_id", "=", False)], limit=1)
            if partner:
                return partner
        if vat:
            partner = Partner.search([("vat", "=", vat), ("parent_id", "=", False)], limit=1)
            if partner:
                return partner
        if name:
            street = (row.get("Straße, Hnr. - Standard Rechnungsadresse") or "").strip()
            zip_code = (row.get("PLZ - Standard Rechnungsadresse") or "").strip()
            city = (row.get("Ort - Standard Rechnungsadresse") or "").strip()
            domain = [("name", "=", name), ("parent_id", "=", False)]
            if street:
                domain.append(("street", "=", street))
            if zip_code:
                domain.append(("zip", "=", zip_code))
            if city:
                domain.append(("city", "=", city))
            matches = Partner.search(domain, limit=2)
            if len(matches) == 1:
                return matches
        return Partner

    def _put(self, values, key, value):
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, False, ""):
            values[key] = value

    def _main_values(self, row):
        values = {"name": (row.get("Name/Firma") or "").strip(), "company_type": "company", "customer_rank": 1}
        self._put(values, "ref", self._external_reference(row))
        self._put(values, "vat", row.get("USt-IdNr."))
        self._put(values, "street", row.get("Straße, Hnr. - Standard Rechnungsadresse"))
        self._put(values, "street2", row.get("Adresszusatz - Standard Rechnungsadresse"))
        self._put(values, "zip", row.get("PLZ - Standard Rechnungsadresse"))
        self._put(values, "city", row.get("Ort - Standard Rechnungsadresse"))
        country = self._country(row.get("Land - Standard Rechnungsadresse"))
        if country:
            values["country_id"] = country.id
        self._put(values, "phone", row.get("Ansprechpartner Telefon"))
        self._put(values, "email", row.get("Ansprechpartner E-Mail") or row.get("Rechnungs E-Mail"))
        self._put(values, "website", row.get("Ansprechpartner Internet"))
        notes = []
        for label, key in [
            ("Debitorenkonto", "Debitorenkonto"), ("Steuernummer", "Steuernummer"),
            ("Rechnungsformat", "Rechnungsformat"), ("Peppol-ID", "Peppol-ID"),
            ("Leitweg-ID", "Leitweg-ID"), ("TRAFFIQX-ID", "TRAFFIQX-ID"),
            ("Lieferbedingung", "Lieferbedingung"), ("Zahlungsbedingung (Altbestand)", "Zahlungsbedingung"),
            ("Sonstige Kundenreferenz", "Sonstige Kundenreferenz"),
        ]:
            value = (row.get(key) or "").strip()
            if value:
                notes.append(f"{label}: {value}")
        if notes:
            values["comment"] = "\n".join(notes)
        return values

    def _upsert_child(self, parent, child_type, name, street, zip_code, city, country_code, street2=False, email=False, phone=False):
        if not any([name, street, zip_code, city, email, phone]):
            return False
        Partner = self.env["res.partner"].sudo()
        country = self._country(country_code)
        domain = [("parent_id", "=", parent.id), ("type", "=", child_type)]
        if name:
            domain.append(("name", "=", name))
        child = Partner.search(domain, limit=1)
        vals = {"parent_id": parent.id, "type": child_type, "name": name or parent.name}
        self._put(vals, "street", street)
        self._put(vals, "street2", street2)
        self._put(vals, "zip", zip_code)
        self._put(vals, "city", city)
        self._put(vals, "email", email)
        self._put(vals, "phone", phone)
        if country:
            vals["country_id"] = country.id
        if child:
            child.write(vals)
        else:
            child = Partner.create(vals)
        return child

    def _upsert_bank(self, partner, row):
        account = (row.get("IBAN") or row.get("Bankkonto-Nummer") or "").strip().replace(" ", "")
        if not account:
            return False
        BankAccount = self.env["res.partner.bank"].sudo()
        bank_account = BankAccount.search([("partner_id", "=", partner.id), ("acc_number", "=", account)], limit=1)
        bank_name = (row.get("Bankbezeichnung") or "").strip()
        bic = (row.get("SWIFT-Code") or "").strip()
        bank = False
        if bic or bank_name:
            Bank = self.env["res.bank"].sudo()
            if bic:
                bank = Bank.search([("bic", "=", bic)], limit=1)
            if not bank and bank_name:
                bank = Bank.search([("name", "=", bank_name)], limit=1)
            if not bank:
                bank_vals = {"name": bank_name or bic}
                if bic:
                    bank_vals["bic"] = bic
                bank = Bank.create(bank_vals)
        vals = {"partner_id": partner.id, "acc_number": account}
        if bank:
            vals["bank_id"] = bank.id
        if bank_account:
            bank_account.write(vals)
        else:
            bank_account = BankAccount.create(vals)
        return bank_account

    def action_import(self):
        self.ensure_one()
        text = self._decode()
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        if not reader.fieldnames or "Name/Firma" not in reader.fieldnames:
            raise ValidationError(_("Die Datei entspricht nicht dem erwarteten SAB-P Kundenexport. Spalte 'Name/Firma' fehlt."))
        created = updated = skipped = contacts = addresses = banks = 0
        for row in reader:
            name = (row.get("Name/Firma") or "").strip()
            if not name:
                skipped += 1
                continue
            partner = self._find_partner(row)
            vals = self._main_values(row)
            if partner:
                if not self.update_existing:
                    skipped += 1
                    continue
                partner.write(vals)
                updated += 1
            else:
                partner = self.env["res.partner"].sudo().create(vals)
                created += 1

            contact_name = (row.get("Ansprechpartner") or "").strip()
            if self.create_contacts and contact_name:
                child = self._upsert_child(partner, "contact", contact_name, False, False, False, False, email=(row.get("Ansprechpartner E-Mail") or "").strip(), phone=(row.get("Ansprechpartner Telefon") or "").strip())
                contacts += 1 if child else 0

            if self.create_invoice_addresses:
                child = self._upsert_child(partner, "invoice", (row.get("Bezeichnung Adresse - Weitere Rechnungsadresse") or "").strip(), (row.get("Straße, Hnr. - Weitere Rechnungsadresse") or "").strip(), (row.get("PLZ - Weitere Rechnungsadresse") or "").strip(), (row.get("Ort - Weitere Rechnungsadresse") or "").strip(), (row.get("Land - Weitere Rechnungsadresse") or "").strip(), (row.get("Adresszusatz - Weitere Rechnungsadresse") or "").strip())
                addresses += 1 if child else 0

            if self.create_delivery_addresses:
                child = self._upsert_child(partner, "delivery", (row.get("Name - Standard Lieferadresse") or row.get("Bezeichnung Adresse - Standard Lieferadresse") or "").strip(), (row.get("Straße, Hnr. - Standard Lieferadresse") or "").strip(), (row.get("PLZ - Standard Lieferadresse") or "").strip(), (row.get("Ort - Standard Lieferadresse") or "").strip(), (row.get("Land - Standard Lieferadresse") or "").strip(), (row.get("Adresszusatz - Standard Lieferadresse") or "").strip())
                addresses += 1 if child else 0

            if self.import_bank_data and self._upsert_bank(partner, row):
                banks += 1

        self.result_text = _("Import abgeschlossen: %(created)s Kunden neu, %(updated)s aktualisiert, %(contacts)s Ansprechpartner, %(addresses)s Zusatzadressen, %(banks)s Bankverbindungen, %(skipped)s übersprungen.") % {"created": created, "updated": updated, "contacts": contacts, "addresses": addresses, "banks": banks, "skipped": skipped}
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
