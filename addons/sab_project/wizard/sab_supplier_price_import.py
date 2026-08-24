import base64
import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabSupplierPriceImport(models.TransientModel):
    _name = "sab.supplier.price.import"
    _description = "SAB-P Lieferanten Preis-/Rabattlistenimport"

    supplier_id = fields.Many2one("sab.supplier", string="Lieferant", required=True)
    file_data = fields.Binary(string="Preis-/Rabattliste", required=True)
    file_name = fields.Char(string="Dateiname")
    result_text = fields.Text(string="Importergebnis", readonly=True)

    ARTICLE_ALIASES = (
        "artikelnummer", "artikel-nr", "artikelnr", "lieferantenartikelnummer",
        "bestellnummer", "bestell-nr", "materialnummer", "material-nr",
        "herstellerartikelnummer", "datanorm-nummer", "datanormnummer",
    )
    LIST_PRICE_ALIASES = (
        "listenpreis", "bruttopreis", "brutto-ek", "brutto ek", "lp", "preis",
    )
    DISCOUNT_ALIASES = (
        "rabatt", "rabatt %", "rabatt (%)", "rabattprozent", "rabatt in %", "discount",
    )
    NET_PRICE_ALIASES = (
        "nettopreis", "netto-ek", "netto ek", "einkaufspreis", "ek", "ek-preis",
    )
    SPACE_UNIT_ALIASES = (
        "platzeinheiten", "platzeinheit", "platz einheiten", "platz-einheiten", "pe",
    )

    @staticmethod
    def _normalize_header(value):
        value = str(value or "").strip().lower()
        value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        value = re.sub(r"\s+", " ", value)
        return value

    @classmethod
    def _find_header(cls, headers, aliases):
        normalized = {cls._normalize_header(h): h for h in headers if h is not None}
        for alias in aliases:
            key = cls._normalize_header(alias)
            if key in normalized:
                return normalized[key]
        return False

    @staticmethod
    def _number(value):
        if value in (None, ""):
            return None
        text = str(value).strip().replace("€", "").replace("%", "").replace(" ", "")
        if not text:
            return None
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _decode_csv(raw):
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValidationError(_("Die Datei konnte nicht gelesen werden."))
        first = next((line for line in text.splitlines() if line.strip()), "")
        delimiter = ";" if first.count(";") >= first.count(",") else ","
        return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))

    @staticmethod
    def _xlsx_rows(raw):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if "xl/workbook.xml" not in archive.namelist():
                raise ValidationError(_("Die XLSX-Datei ist nicht vollständig."))
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in root.findall("a:si", ns):
                    shared.append("".join(t.text or "" for t in si.iterfind(".//a:t", ns)))
            sheet_name = next((n for n in archive.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")), None)
            if not sheet_name:
                raise ValidationError(_("Die XLSX-Datei enthält kein Tabellenblatt."))
            root = ET.fromstring(archive.read(sheet_name))
            ns_uri = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
            rows = []
            for row in root.iter("{%s}row" % ns_uri):
                values = {}
                for cell in row.findall("{%s}c" % ns_uri):
                    ref = cell.attrib.get("r", "")
                    col = re.sub(r"\d", "", ref)
                    cell_type = cell.attrib.get("t")
                    v = cell.find("{%s}v" % ns_uri)
                    inline = cell.find("{%s}is" % ns_uri)
                    value = ""
                    if cell_type == "s" and v is not None:
                        try:
                            value = shared[int(v.text)]
                        except (ValueError, IndexError, TypeError):
                            value = ""
                    elif cell_type == "inlineStr" and inline is not None:
                        value = "".join(t.text or "" for t in inline.iter("{%s}t" % ns_uri))
                    elif v is not None:
                        value = v.text or ""
                    values[col] = value
                rows.append(values)
            if not rows:
                return []
            headers_by_col = rows[0]
            result = []
            for raw_row in rows[1:]:
                result.append({headers_by_col.get(col, col): value for col, value in raw_row.items()})
            return result

    def _read_rows(self):
        raw = base64.b64decode(self.file_data or b"")
        if not raw:
            raise ValidationError(_("Es wurde keine Datei hochgeladen."))
        name = (self.file_name or "").lower()
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                candidates = [n for n in archive.namelist() if not n.endswith("/") and n.lower().endswith((".xlsx", ".csv"))]
                if not candidates:
                    raise ValidationError(_("Das ZIP enthält keine unterstützte XLSX- oder CSV-Datei."))
                candidates.sort(key=lambda n: ("rabatt" not in n.lower() and "preis" not in n.lower(), n.lower()))
                selected = candidates[0]
                payload = archive.read(selected)
                return (self._xlsx_rows(payload) if selected.lower().endswith(".xlsx") else self._decode_csv(payload)), selected
        if name.endswith(".xlsx") or raw[:2] == b"PK":
            return self._xlsx_rows(raw), self.file_name or "Excel-Datei"
        return self._decode_csv(raw), self.file_name or "CSV-Datei"

    def action_import(self):
        self.ensure_one()
        rows, source_name = self._read_rows()
        if not rows:
            raise ValidationError(_("Die Datei enthält keine Datenzeilen."))
        headers = list(rows[0].keys())
        article_col = self._find_header(headers, self.ARTICLE_ALIASES)
        if not article_col:
            raise ValidationError(_("Keine Artikelnummern-Spalte erkannt. Unterstützt werden z. B. Artikelnummer, Bestellnummer oder Herstellerartikelnummer."))
        list_col = self._find_header(headers, self.LIST_PRICE_ALIASES)
        discount_col = self._find_header(headers, self.DISCOUNT_ALIASES)
        net_col = self._find_header(headers, self.NET_PRICE_ALIASES)
        space_col = self._find_header(headers, self.SPACE_UNIT_ALIASES)
        if not any((list_col, discount_col, net_col, space_col)):
            raise ValidationError(_("Es wurde weder Listenpreis, Rabatt, Netto-EK noch Platzeinheiten erkannt."))

        SupplierProduct = self.env["sab.supplier.product"].sudo()
        products = SupplierProduct.search([("supplier_id", "=", self.supplier_id.id)])
        by_number = {}
        for record in products:
            for number in (record.supplier_article_number, record.datanorm_number, record.product_id.manufacturer_article_number):
                if number:
                    by_number[str(number).strip().upper()] = record

        updated = missing = skipped = 0
        for row in rows:
            number = str(row.get(article_col) or "").strip()
            if not number:
                skipped += 1
                continue
            record = by_number.get(number.upper())
            if not record:
                missing += 1
                continue
            vals = {}
            list_price = self._number(row.get(list_col)) if list_col else None
            discount = self._number(row.get(discount_col)) if discount_col else None
            net_price = self._number(row.get(net_col)) if net_col else None
            space_units = self._number(row.get(space_col)) if space_col else None
            if list_price is not None:
                vals["list_price"] = list_price
                vals["purchase_price"] = list_price
            if discount is not None:
                vals["discount_percent"] = discount
            if net_price is not None:
                vals["purchase_price"] = net_price
                vals["discount_percent"] = 0.0
            if space_units is not None:
                record.product_id.sudo().write({"space_units": space_units})
            if vals:
                record.write(vals)
                updated += 1
            else:
                skipped += 1

        self.result_text = _("Import abgeschlossen (%(source)s): %(updated)s Lieferantenartikel aktualisiert, %(missing)s Artikel nicht gefunden, %(skipped)s Zeilen übersprungen.") % {
            "source": source_name, "updated": updated, "missing": missing, "skipped": skipped,
        }
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
