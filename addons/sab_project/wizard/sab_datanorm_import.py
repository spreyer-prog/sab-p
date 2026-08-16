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
    supplier_id = fields.Many2one(
        "sab.supplier",
        string="Lieferant / Datenquelle",
        required=True,
        help="Bezugsquelle, unter der die DATANORM-Artikel geführt werden.",
    )
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
        candidates = [
            info for info in archive.infolist()
            if not info.is_dir()
            and info.filename.lower().endswith((".001", ".dat", ".txt"))
        ]
        if not candidates:
            raise UserError("Das ZIP enthält keine unterstützte DATANORM-Datei.")
        candidates.sort(key=lambda info: (
            "kurztextinkltyp" not in info.filename.lower(),
            info.filename.lower(),
        ))
        selected = candidates[0]
        if selected.file_size > cls.MAX_UNCOMPRESSED_BYTES:
            raise UserError("Die entpackte DATANORM-Datei ist größer als 150 MB und wird aus Sicherheitsgründen nicht verarbeitet.")
        return selected

    def _read_payload(self):
        self.ensure_one()
        raw = base64.b64decode(self.file_data or b"")
        if not raw:
            raise UserError("Es wurde keine Datei hochgeladen.")
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                member = self._select_zip_member(archive)
                payload = archive.read(member)
                return self._decode_bytes(payload), member.filename
        if len(raw) > self.MAX_UNCOMPRESSED_BYTES:
            raise UserError("Die DATANORM-Datei ist größer als 150 MB und wird aus Sicherheitsgründen nicht verarbeitet.")
        return self._decode_bytes(raw), self.file_name or "DATANORM-Datei"

    @staticmethod
    def _parse_price(value):
        if not value:
            return 0.0
        try:
            return int(value) / 100.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _unit_from_datanorm(value):
        return {
            "PCE": "pcs",
            "MTR": "m",
            "KGM": "kg",
        }.get((value or "").strip().upper(), "other")

    @staticmethod
    def _space_units_from_text(*values):
        text = " ".join(value or "" for value in values)
        match = re.search(r"(?<!\d)(\d+(?:[,.]\d+)?)\s*PLE\b", text, re.IGNORECASE)
        if not match:
            return False
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return False

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
            field = record._fields[field_name]
            current = record[field_name]
            if field.type == "many2one":
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
                source_date = False

        record_counts = self._record_counts(lines)
        Manufacturer = self.env["sab.manufacturer"]
        Product = self.env["sab.product"]
        SupplierProduct = self.env["sab.supplier.product"]

        manufacturer = Manufacturer.search([("name", "=ilike", manufacturer_name)], limit=1)
        if not manufacturer:
            manufacturer = Manufacturer.create({"name": manufacturer_name})

        product_map = {
            record.manufacturer_article_number: record
            for record in Product.search([
                ("manufacturer_id", "=", manufacturer.id),
                ("manufacturer_article_number", "!=", False),
            ])
        }
        supplier_map = {
            record.supplier_article_number: record
            for record in SupplierProduct.search([
                ("supplier_id", "=", self.supplier_id.id),
                ("supplier_article_number", "!=", False),
            ])
        }

        created_products = updated_products = unchanged_products = 0
        created_supplier = updated_supplier = unchanged_supplier = 0
        skipped = errors = 0

        for raw_line in lines[1:]:
            if not raw_line.startswith("A;"):
                continue
            try:
                parts = raw_line.split(";")
                if len(parts) < 21:
                    skipped += 1
                    continue

                article_number = parts[2].strip()
                short_text = " ".join(value.strip() for value in parts[3:5] if value.strip()).strip()
                unit = parts[5].strip()
                datanorm_price = self._parse_price(parts[8].strip())
                datanorm_price_code = parts[9].strip()
                type_name = parts[12].strip()
                manufacturer_article = parts[16].strip() or article_number
                ean = parts[18].strip()

                if not manufacturer_article or not article_number:
                    skipped += 1
                    continue

                product = product_map.get(manufacturer_article)
                vals_product = {
                    "manufacturer_id": manufacturer.id,
                    "manufacturer_article_number": manufacturer_article,
                    "datanorm_number": article_number,
                    "name": short_text or type_name or manufacturer_article,
                }

                if product:
                    if self._needs_write(product, vals_product):
                        product.write(vals_product)
                        updated_products += 1
                    else:
                        unchanged_products += 1
                elif self.create_missing_products:
                    # Nur wenn die DATANORM selbst eine PLE-Angabe enthält.
                    space_units = self._space_units_from_text(short_text, type_name)
                    if space_units is not False:
                        vals_product["space_units"] = space_units
                    product = Product.create(vals_product)
                    product_map[manufacturer_article] = product
                    created_products += 1
                else:
                    skipped += 1
                    continue

                supplier_product = supplier_map.get(article_number)
                vals_supplier = {
                    "supplier_id": self.supplier_id.id,
                    "product_id": product.id,
                    "supplier_article_number": article_number,
                    "datanorm_number": article_number,
                    "datanorm_price": datanorm_price,
                    "list_price": datanorm_price,
                    "datanorm_price_code": datanorm_price_code,
                    "unit": self._unit_from_datanorm(unit),
                    "valid_from": source_date,
                    "datanorm_type_name": type_name,
                    "ean": ean,
                }

                # Preisregel: vorhandenen echten EK nicht überschreiben.
                # Fehlt ein EK, wird der Listenpreis aus DATANORM als Fallback genutzt.
                if not supplier_product or not supplier_product.purchase_price:
                    vals_supplier["purchase_price"] = datanorm_price
                elif self.supplier_id.datanorm_price_as_purchase_price:
                    vals_supplier["purchase_price"] = datanorm_price

                if supplier_product:
                    if self._needs_write(supplier_product, vals_supplier):
                        supplier_product.write(vals_supplier)
                        updated_supplier += 1
                    else:
                        unchanged_supplier += 1
                else:
                    supplier_product = SupplierProduct.create(vals_supplier)
                    supplier_map[article_number] = supplier_product
                    created_supplier += 1

            except Exception:
                errors += 1

        price_mode = "vorhandenen EK behalten; ohne EK Listenpreis als Fallback"
        self.result_text = (
            f"DATANORM 5: {manufacturer_name}\n"
            f"Quelle: {source_file_name}\n"
            f"Datenstand: {source_date or '-'}\n"
            f"EK-Regel: {price_mode}\n"
            f"A-Artikelsätze erkannt: {record_counts.get('A', 0)}\n"
            f"Z-Preis-/Zuschlagssätze erkannt: {record_counts.get('Z', 0)} (noch nicht preiswirksam importiert)\n\n"
            f"Produkte neu: {created_products}\n"
            f"Produkte aktualisiert: {updated_products}\n"
            f"Produkte unverändert: {unchanged_products}\n"
            f"Lieferantenartikel neu: {created_supplier}\n"
            f"Lieferantenartikel aktualisiert: {updated_supplier}\n"
            f"Lieferantenartikel unverändert: {unchanged_supplier}\n"
            f"Übersprungen: {skipped}\n"
            f"Fehler: {errors}"
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
