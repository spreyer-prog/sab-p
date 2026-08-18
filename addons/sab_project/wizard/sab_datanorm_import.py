import base64
import io
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

    import_state = fields.Selection([
        ("ready", "Bereit"),
        ("running", "Import läuft"),
        ("done", "Abgeschlossen"),
        ("error", "Fehler"),
    ], string="Status", default="ready", readonly=True)
    progress_percent = fields.Float(string="Fortschritt (%)", readonly=True)
    processed_records = fields.Integer(string="Verarbeitet", readonly=True)
    total_records = fields.Integer(string="Gesamt", readonly=True)
    current_status = fields.Char(string="Aktueller Status", readonly=True)
    last_error = fields.Text(string="Letzter Fehler", readonly=True)

    # Temporärer Arbeitsstand. Durch die Verarbeitung in einzelnen RPC-Aufrufen kann
    # der Browser zwischen den Paketen den echten Fortschritt anzeigen.
    import_payload = fields.Text(string="Import-Arbeitsdaten", readonly=True)
    import_manufacturer_name = fields.Char(readonly=True)
    import_source_date = fields.Date(readonly=True)
    import_z_count = fields.Integer(readonly=True)

    created_products = fields.Integer(readonly=True)
    updated_products = fields.Integer(readonly=True)
    unchanged_products = fields.Integer(readonly=True)
    created_supplier = fields.Integer(readonly=True)
    updated_supplier = fields.Integer(readonly=True)
    unchanged_supplier = fields.Integer(readonly=True)
    synced_odoo = fields.Integer(readonly=True)
    skipped_records = fields.Integer(readonly=True)
    error_records = fields.Integer(readonly=True)

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
        candidates = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith((".001", ".dat", ".txt"))]
        if not candidates:
            raise UserError("Das ZIP enthält keine unterstützte DATANORM-Datei.")
        candidates.sort(key=lambda info: ("kurztextinkltyp" not in info.filename.lower(), info.filename.lower()))
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
                return self._decode_bytes(archive.read(member)), member.filename
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
        return {"PCE": "pcs", "MTR": "m", "KGM": "kg"}.get((value or "").strip().upper(), "other")

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
        """Vorbereiten und anschließend in kleinen Paketen im Browser verarbeiten."""
        self.ensure_one()
        text, source_file_name = self._read_payload()
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
        article_lines = [line for line in lines[1:] if line.startswith("A;")]
        if not article_lines:
            raise UserError("Die DATANORM-Datei enthält keine Artikelsätze (A-Sätze).")

        self.write({
            "source_file_name": source_file_name,
            "import_manufacturer_name": manufacturer_name,
            "import_source_date": source_date,
            "import_z_count": record_counts.get("Z", 0),
            "import_payload": "\n".join(article_lines),
            "import_state": "running",
            "progress_percent": 0.0,
            "processed_records": 0,
            "total_records": len(article_lines),
            "current_status": f"Vorbereitet – {len(article_lines)} Artikel erkannt",
            "last_error": False,
            "result_text": False,
            "created_products": 0,
            "updated_products": 0,
            "unchanged_products": 0,
            "created_supplier": 0,
            "updated_supplier": 0,
            "unchanged_supplier": 0,
            "synced_odoo": 0,
            "skipped_records": 0,
            "error_records": 0,
        })
        return {
            "type": "ir.actions.client",
            "tag": "sab_datanorm_progress",
            "params": {"wizard_id": self.id},
        }

    def action_process_chunk(self, batch_size=250):
        self.ensure_one()
        if self.import_state in ("done", "error"):
            return self._progress_response()
        if not self.import_payload:
            self.write({"import_state": "error", "last_error": "Temporäre Importdaten fehlen."})
            return self._progress_response()

        article_lines = self.import_payload.splitlines()
        start = self.processed_records
        end = min(start + max(25, min(int(batch_size or 250), 1000)), len(article_lines))
        chunk = article_lines[start:end]

        Manufacturer = self.env["sab.manufacturer"]
        Product = self.env["sab.product"]
        SupplierProduct = self.env["sab.supplier.product"]
        manufacturer = Manufacturer.search([("name", "=ilike", self.import_manufacturer_name)], limit=1)
        if not manufacturer:
            manufacturer = Manufacturer.create({"name": self.import_manufacturer_name})

        # Nur die im aktuellen Paket benötigten Stammsätze laden.
        parsed = []
        manufacturer_articles = []
        article_numbers = []
        for raw_line in chunk:
            parts = raw_line.split(";")
            if len(parts) >= 21:
                article_number = parts[2].strip()
                manufacturer_article = parts[16].strip() or article_number
                if article_number and manufacturer_article:
                    parsed.append((raw_line, parts, article_number, manufacturer_article))
                    manufacturer_articles.append(manufacturer_article)
                    article_numbers.append(article_number)

        product_map = {
            r.manufacturer_article_number: r
            for r in Product.search([
                ("manufacturer_id", "=", manufacturer.id),
                ("manufacturer_article_number", "in", list(set(manufacturer_articles))),
            ])
        }
        supplier_map = {
            r.supplier_article_number: r
            for r in SupplierProduct.search([
                ("supplier_id", "=", self.supplier_id.id),
                ("supplier_article_number", "in", list(set(article_numbers))),
            ])
        }

        counters = {
            "created_products": self.created_products,
            "updated_products": self.updated_products,
            "unchanged_products": self.unchanged_products,
            "created_supplier": self.created_supplier,
            "updated_supplier": self.updated_supplier,
            "unchanged_supplier": self.unchanged_supplier,
            "synced_odoo": self.synced_odoo,
            "skipped_records": self.skipped_records + (len(chunk) - len(parsed)),
            "error_records": self.error_records,
        }
        last_error = False

        for raw_line, parts, article_number, manufacturer_article in parsed:
            try:
                short_text = " ".join(value.strip() for value in parts[3:5] if value.strip()).strip()
                unit = parts[5].strip()
                datanorm_price = self._parse_price(parts[8].strip())
                datanorm_price_code = parts[9].strip()
                type_name = parts[12].strip()
                ean = parts[18].strip()

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
                        counters["updated_products"] += 1
                    else:
                        counters["unchanged_products"] += 1
                elif self.create_missing_products:
                    product = Product.create(vals_product)
                    product_map[manufacturer_article] = product
                    counters["created_products"] += 1
                else:
                    counters["skipped_records"] += 1
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
                    "valid_from": self.import_source_date,
                    "datanorm_type_name": type_name,
                    "ean": ean,
                }
                if not supplier_product or not supplier_product.purchase_price:
                    vals_supplier["purchase_price"] = datanorm_price
                elif self.supplier_id.datanorm_price_as_purchase_price:
                    vals_supplier["purchase_price"] = datanorm_price

                if supplier_product:
                    if self._needs_write(supplier_product, vals_supplier):
                        supplier_product.write(vals_supplier)
                        counters["updated_supplier"] += 1
                    else:
                        counters["unchanged_supplier"] += 1
                else:
                    supplier_product = SupplierProduct.create(vals_supplier)
                    supplier_map[article_number] = supplier_product
                    counters["created_supplier"] += 1

                product._sync_to_odoo_product()
                counters["synced_odoo"] += 1
            except Exception as exc:
                counters["error_records"] += 1
                last_error = f"Artikel {article_number or '?'}: {exc}"

        processed = end
        total = len(article_lines)
        progress = 100.0 if not total else min(100.0, processed * 100.0 / total)
        done = processed >= total
        values = dict(counters)
        values.update({
            "processed_records": processed,
            "total_records": total,
            "progress_percent": progress,
            "current_status": f"{processed:,} von {total:,} Artikeln verarbeitet".replace(",", "."),
            "last_error": last_error or self.last_error,
            "import_state": "done" if done else "running",
        })
        self.write(values)
        if done:
            self._finish_import()
        return self._progress_response()

    def _finish_import(self):
        self.ensure_one()
        self.result_text = (
            f"DATANORM 5: {self.import_manufacturer_name}\n"
            f"Quelle: {self.source_file_name}\n"
            f"Datenstand: {self.import_source_date or '-'}\n"
            f"EK-Regel: vorhandenen EK behalten; ohne EK Listenpreis als Fallback\n"
            f"A-Artikelsätze erkannt: {self.total_records}\n"
            f"Z-Preis-/Zuschlagssätze erkannt: {self.import_z_count} (noch nicht preiswirksam importiert)\n\n"
            f"Produkte neu: {self.created_products}\n"
            f"Produkte aktualisiert: {self.updated_products}\n"
            f"Produkte unverändert: {self.unchanged_products}\n"
            f"Lieferantenartikel neu: {self.created_supplier}\n"
            f"Lieferantenartikel aktualisiert: {self.updated_supplier}\n"
            f"Lieferantenartikel unverändert: {self.unchanged_supplier}\n"
            f"Mit Odoo-Produktstamm synchronisiert: {self.synced_odoo}\n"
            f"Übersprungen: {self.skipped_records}\n"
            f"Fehler: {self.error_records}"
        )

    def _progress_response(self):
        self.ensure_one()
        return {
            "done": self.import_state == "done",
            "failed": self.import_state == "error",
            "state": self.import_state,
            "progress": round(self.progress_percent or 0.0, 1),
            "processed": self.processed_records,
            "total": self.total_records,
            "status": self.current_status or "",
            "errors": self.error_records,
            "last_error": self.last_error or "",
        }
