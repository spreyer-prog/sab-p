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

    def _find_partner(self, row):
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        customer_no = (row.get("Kundennummer") or "").strip()
        vat = (row.get("USt-IdNr.") or "").strip()
        name = (row.get("Name/Firma") or "").strip()
        if customer_no:
            partner = Partner.search([("ref", "=", customer_no), ("parent_id", "=", False)], limit=1)
            if partner:
                return partner
        if vat:
            partner = Partner.search([("vat", "=", vat), ("parent_id", "=", False)], limit=1)
            if partner:
                return partner
        return Partner.search([("name", "=", name), ("parent_id", "=", False)], limit=1) if name else Partner

    def _main_values(self, row):
        country = self._country(row.get("Land - Standard Rechnungsadresse"))
        values = {
            "name": (row.get("Name/Firma") or "").strip(),
            "company_type": "company",
            "customer_rank": 1,
            "ref": (row.get("Kundennummer") or "").strip() or False,
            "vat": (row.get("USt-IdNr.") or "").strip() or False,
            "street": (row.get("Straße, Hnr. - Standard Rechnungsadresse") or "").strip() or False,
            "street2": (row.get("Adresszusatz - Standard Rechnungsadresse") or "").strip() or False,
            "zip": (row.get("PLZ - Standard Rechnungsadresse") or "").strip() or False,
            "city": (row.get("Ort - Standard Rechnungsadresse") or "").strip() or False,
            "country_id": country.id if country else False,
            "phone": (row.get("Ansprechpartner Telefon") or "").strip() or False,
            "email": (row.get("Ansprechpartner E-Mail") or row.get("Rechnungs E-Mail") or "").strip() or False,
            "website": (row.get("Ansprechpartner Internet") or "").strip() or False,
        }
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
        values["comment"] = "\n".join(notes) or False
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
        vals = {"parent_id": parent.id, "type": child_type, "name": name or parent.name, "street": street or False, "street2": street2 or False, "zip": zip_code or False, "city": city or False, "country_id": country.id if country else False, "email": email or False, "phone": phone or False}
        if child:
            child.write(vals)
        else:
            child = Partner.create(vals)
        return child

    def action_import(self):
        self.ensure_one()
        text = self._decode()
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        if not reader.fieldnames or "Name/Firma" not in reader.fieldnames:
            raise ValidationError(_("Die Datei entspricht nicht dem erwarteten SAB-P Kundenexport. Spalte 'Name/Firma' fehlt."))
        created = updated = skipped = contacts = addresses = 0
        for line_no, row in enumerate(reader, start=2):
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
                self._upsert_child(partner, "contact", contact_name, False, False, False, False, email=(row.get("Ansprechpartner E-Mail") or "").strip(), phone=(row.get("Ansprechpartner Telefon") or "").strip())
                contacts += 1

            if self.create_invoice_addresses:
                child = self._upsert_child(partner, "invoice", (row.get("Bezeichnung Adresse - Weitere Rechnungsadresse") or "").strip(), (row.get("Straße, Hnr. - Weitere Rechnungsadresse") or "").strip(), (row.get("PLZ - Weitere Rechnungsadresse") or "").strip(), (row.get("Ort - Weitere Rechnungsadresse") or "").strip(), (row.get("Land - Weitere Rechnungsadresse") or "").strip(), (row.get("Adresszusatz - Weitere Rechnungsadresse") or "").strip())
                addresses += 1 if child else 0

            if self.create_delivery_addresses:
                child = self._upsert_child(partner, "delivery", (row.get("Name - Standard Lieferadresse") or row.get("Bezeichnung Adresse - Standard Lieferadresse") or "").strip(), (row.get("Straße, Hnr. - Standard Lieferadresse") or "").strip(), (row.get("PLZ - Standard Lieferadresse") or "").strip(), (row.get("Ort - Standard Lieferadresse") or "").strip(), (row.get("Land - Standard Lieferadresse") or "").strip(), (row.get("Adresszusatz - Standard Lieferadresse") or "").strip())
                addresses += 1 if child else 0

        self.result_text = _("Import abgeschlossen: %(created)s Kunden neu, %(updated)s aktualisiert, %(contacts)s Ansprechpartner, %(addresses)s Zusatzadressen, %(skipped)s übersprungen.") % {"created": created, "updated": updated, "contacts": contacts, "addresses": addresses, "skipped": skipped}
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
