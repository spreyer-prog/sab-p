import base64
from datetime import datetime

from odoo import fields, models
from odoo.exceptions import UserError


class SabDatanormImport(models.TransientModel):
    _name = "sab.datanorm.import"
    _description = "SAB-P DATANORM-Import"

    file_data = fields.Binary(string="DATANORM-Datei", required=True)
    file_name = fields.Char(string="Dateiname")
    supplier_id = fields.Many2one(
        "sab.supplier",
        string="Lieferant / Datenquelle",
        required=True,
        help="Bezugsquelle, unter der die DATANORM-Artikel geführt werden.",
    )
    create_missing_products = fields.Boolean(
        string="Fehlende Produkte anlegen",
        default=True,
    )
    result_text = fields.Text(string="Importprotokoll", readonly=True)

    def _decode(self):
        self.ensure_one()
        raw = base64.b64decode(self.file_data or b"")
        for encoding in ("cp1252", "latin1", "utf-8"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise UserError("Die DATANORM-Datei konnte nicht gelesen werden.")

    @staticmethod
    def _parse_price(value):
        if not value:
            return 0.0
        try:
            # ABB DATANORM 5 liefert den Preis als Ganzzahl in Cent.
            return int(value) / 100.0
        except ValueError:
            return 0.0

    def action_import(self):
        self.ensure_one()
        text = self._decode()
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

        Manufacturer = self.env["sab.manufacturer"]
        Product = self.env["sab.product"]
        SupplierProduct = self.env["sab.supplier.product"]

        manufacturer = Manufacturer.search([("name", "=ilike", manufacturer_name)], limit=1)
        if not manufacturer:
            manufacturer = Manufacturer.create({"name": manufacturer_name})

        created_products = updated_products = 0
        created_supplier = updated_supplier = skipped = errors = 0

        for raw_line in lines[1:]:
            if not raw_line.startswith("A;"):
                continue
            try:
                parts = raw_line.split(";")
                if len(parts) < 21:
                    skipped += 1
                    continue

                article_number = parts[2].strip()
                short_text = " ".join(x.strip() for x in parts[3:5] if x.strip()).strip()
                unit = parts[5].strip()
                price = self._parse_price(parts[8].strip())
                type_name = parts[12].strip()
                manufacturer_article = (parts[16].strip() or article_number)
                ean = parts[18].strip()

                if not manufacturer_article:
                    skipped += 1
                    continue

                product = Product.search([
                    ("manufacturer_id", "=", manufacturer.id),
                    ("manufacturer_article_number", "=", manufacturer_article),
                ], limit=1)

                vals_product = {
                    "manufacturer_id": manufacturer.id,
                    "manufacturer_article_number": manufacturer_article,
                    "datanorm_number": article_number,
                    "name": short_text or type_name or manufacturer_article,
                }
                if product:
                    # Technische Zeiten/Platzeinheiten bleiben unangetastet.
                    product.write(vals_product)
                    updated_products += 1
                elif self.create_missing_products:
                    product = Product.create(vals_product)
                    created_products += 1
                else:
                    skipped += 1
                    continue

                supplier_product = SupplierProduct.search([
                    ("supplier_id", "=", self.supplier_id.id),
                    ("supplier_article_number", "=", article_number),
                ], limit=1)

                vals_supplier = {
                    "supplier_id": self.supplier_id.id,
                    "product_id": product.id,
                    "supplier_article_number": article_number,
                    "datanorm_number": article_number,
                    "purchase_price": price,
                    "unit": {"PCE": "pcs", "MTR": "m", "KGM": "kg"}.get(unit, "other"),
                    "valid_from": source_date,
                    "datanorm_type_name": type_name,
                    "ean": ean,
                }
                if supplier_product:
                    supplier_product.write(vals_supplier)
                    updated_supplier += 1
                else:
                    SupplierProduct.create(vals_supplier)
                    created_supplier += 1
            except Exception:
                errors += 1

        self.result_text = (
            f"DATANORM 5: {manufacturer_name}\n"
            f"Produkte neu: {created_products}\n"
            f"Produkte aktualisiert: {updated_products}\n"
            f"Lieferantenartikel neu: {created_supplier}\n"
            f"Lieferantenartikel aktualisiert: {updated_supplier}\n"
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
