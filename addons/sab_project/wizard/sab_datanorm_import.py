import base64
import io
import re
import zipfile
from collections import Counter
from datetime import datetime

from odoo import fields, models
from odoo.exceptions import UserError


class SabDatanormImport(models.TransientModel):
    _name = "sab.datanorm.import"
    _description = "SAB-P DATANORM-Import"

    file_data = fields.Binary(string="DATANORM-Datei / ZIP", required=True)
    file_name = fields.Char(string="Dateiname")
    source_file_name = fields.Char(string="Verarbeitete DATANORM-Datei", readonly=True)
    supplier_id = fields.Many2one("sab.supplier", string="Lieferant / Datenquelle", required=True)
    create_missing_products = fields.Boolean(string="Fehlende Produkte anlegen", default=True)
    result_text = fields.Text(string="Importprotokoll", readonly=True)
    MAX_UNCOMPRESSED_BYTES = 150 * 1024 * 1024

    @staticmethod
    def _decode_bytes(raw):
        for encoding in ("cp1252", "latin1", "utf-8"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise UserError("Die DATANORM-Datei konnte nicht gelesen werden.")

    @classmethod
    def _select_zip_member(cls, archive):
        candidates = [i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith((".001", ".dat", ".txt"))]
        if not candidates:
            raise UserError("Das ZIP enthält keine unterstützte DATANORM-Datei.")
        candidates.sort(key=lambda i: ("kurztextinkltyp" not in i.filename.lower(), i.filename.lower()))
        selected = candidates[0]
        if selected.file_size > cls.MAX_UNCOMPRESSED_BYTES:
            raise UserError("Die entpackte DATANORM-Datei ist größer als 150 MB.")
        return selected

    def _read_payload(self):
        self.ensure_one()
        raw = base64.b64decode(self.file_data or b"")
        if not raw:
            raise UserError("Es wurde keine Datei hochgeladen.")
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                member = self._select_zip_member(archive)
                return self._decode_bytes(archive.read(member)), member.filename
        if len(raw) > self.MAX_UNCOMPRESSED_BYTES:
            raise UserError("Die DATANORM-Datei ist größer als 150 MB.")
        return self._decode_bytes(raw), self.file_name or "DATANORM-Datei"

    @staticmethod
    def _parse_price(value):
        try:
            return int(value) / 100.0 if value else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _unit_from_datanorm(value):
        return {"PCE": "pcs", "MTR": "m", "KGM": "kg"}.get((value or "").strip().upper(), "other")

    @staticmethod
    def _space_units_from_text(*values):
        text = " ".join(value or "" for value in values)
        match = re.search(r"(?<!\d)(\d+(?:[,.]\d+)?)\s*PLE\b", text, re.IGNORECASE)
        return float(match.group(1).replace(",", ".")) if match else False

    @staticmethod
    def _record_counts(lines):
        counter = Counter()
        for line in lines:
            if line:
                counter[line[0]] += 1
        return counter

    @staticmethod
    def _needs_write(record, vals):
        for field_name, value in vals.items():
            current = record[field_name]
            if record._fields[field_name].type == "many2one":
                current = current.id or False
            if current != value:
                return True
        return False

    def action_import(self):
        self.ensure_one()
        text, source_file_name = self._read_payload()
        self.source_file_name = source_file_name
        lines = text.splitlines()
        if not lines:
            raise UserError("Die DATANORM-Datei ist leer.")
        header = lines[0].split(";")
        if len(header) < 10 or header[0] != "V" or header[1] != "050":
            raise UserError("Es wird derzeit DATANORM 5 (Kennung 050) erwartet.")

        manufacturer_name = (header[8] or "Unbekannter Hersteller").strip()
        source_date = False
        if len(header) > 3 and header[3]:
            try:
                source_date = datetime.strptime(header[3], "%Y%m%d").date()
            except ValueError:
                pass

        counts = self._record_counts(lines)
        Manufacturer = self.env["sab.manufacturer"]
        Product = self.env["sab.product"]
        SupplierProduct = self.env["sab.supplier.product"]
        manufacturer = Manufacturer.search([("name", "=ilike", manufacturer_name)], limit=1) or Manufacturer.create({"name": manufacturer_name})
        product_map = {r.manufacturer_article_number: r for r in Product.search([("manufacturer_id", "=", manufacturer.id), ("manufacturer_article_number", "!=", False)])}
        supplier_map = {r.supplier_article_number: r for r in SupplierProduct.search([("supplier_id", "=", self.supplier_id.id), ("supplier_article_number", "!=", False)])}

        created_products = updated_products = unchanged_products = 0
        created_supplier = updated_supplier = unchanged_supplier = skipped = errors = 0
        error_samples = []

        for raw_line in lines[1:]:
            if not raw_line.startswith("A;"):
                continue
            parts = raw_line.split(";")
            if len(parts) < 19:
                skipped += 1
                continue
            article_number = parts[2].strip()
            try:
                short_text = " ".join(v.strip() for v in parts[3:5] if v.strip()).strip()
                unit = parts[5].strip()
                datanorm_price = self._parse_price(parts[8].strip())
                price_code = parts[9].strip()
                type_name = parts[12].strip()
                manufacturer_article = parts[16].strip() or article_number
                ean = parts[18].strip()
                if not article_number or not manufacturer_article:
                    skipped += 1
                    continue

                product = product_map.get(manufacturer_article)
                product_vals = {"manufacturer_id": manufacturer.id, "manufacturer_article_number": manufacturer_article, "datanorm_number": article_number, "name": short_text or type_name or manufacturer_article}
                if product:
                    if self._needs_write(product, product_vals):
                        product.write(product_vals); updated_products += 1
                    else:
                        unchanged_products += 1
                elif self.create_missing_products:
                    ple = self._space_units_from_text(short_text, type_name)
                    if ple is not False:
                        product_vals["space_units"] = ple
                    product = Product.create(product_vals)
                    product_map[manufacturer_article] = product
                    created_products += 1
                else:
                    skipped += 1
                    continue

                supplier_product = supplier_map.get(article_number)
                supplier_vals = {"supplier_id": self.supplier_id.id, "product_id": product.id, "supplier_article_number": article_number, "datanorm_number": article_number, "datanorm_price": datanorm_price, "list_price": datanorm_price, "datanorm_price_code": price_code, "unit": self._unit_from_datanorm(unit), "valid_from": source_date, "datanorm_type_name": type_name, "ean": ean}
                if not supplier_product or not supplier_product.purchase_price:
                    supplier_vals["purchase_price"] = datanorm_price
                elif self.supplier_id.datanorm_price_as_purchase_price:
                    supplier_vals["purchase_price"] = datanorm_price

                if supplier_product:
                    if self._needs_write(supplier_product, supplier_vals):
                        supplier_product.write(supplier_vals); updated_supplier += 1
                    else:
                        unchanged_supplier += 1
                else:
                    supplier_product = SupplierProduct.create(supplier_vals)
                    supplier_map[article_number] = supplier_product
                    created_supplier += 1
            except (UserError, ValueError, TypeError, IndexError) as exc:
                errors += 1
                if len(error_samples) < 5:
                    error_samples.append(f"{article_number}: {type(exc).__name__}: {exc}")

        error_detail = "\n".join(error_samples) if error_samples else "-"
        self.result_text = (
            f"DATANORM 5: {manufacturer_name}\nQuelle: {source_file_name}\nDatenstand: {source_date or '-'}\n"
            "EK-Regel: vorhandenen EK behalten; ohne EK Listenpreis als Fallback verwenden\n"
            f"A-Artikelsätze erkannt: {counts.get('A', 0)}\nZ-Preis-/Zuschlagssätze erkannt: {counts.get('Z', 0)} (noch nicht preiswirksam importiert)\n\n"
            f"Produkte neu: {created_products}\nProdukte aktualisiert: {updated_products}\nProdukte unverändert: {unchanged_products}\n"
            f"Lieferantenartikel neu: {created_supplier}\nLieferantenartikel aktualisiert: {updated_supplier}\nLieferantenartikel unverändert: {unchanged_supplier}\nÜbersprungen: {skipped}\nFehler: {errors}\n"
            f"Erste Fehlerdetails:\n{error_detail}"
        )
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
