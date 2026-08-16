import re

from odoo import models


class SabDatanormImportEnrichment(models.TransientModel):
    _inherit = "sab.datanorm.import"

    SPACE_PATTERNS = (
        re.compile(r"(?<!\d)(\d+(?:[\.,]\d+)?)\s*(?:platzeinheit(?:en)?|ple)\b", re.IGNORECASE),
        re.compile(r"(?<!\d)(\d+(?:[\.,]\d+)?)\s*te\b", re.IGNORECASE),
    )

    @classmethod
    def _space_units_from_text(cls, *values):
        """Liest PLE/TE nur dann, wenn sie in den DATANORM-Texten enthalten sind."""
        text = " ".join(value or "" for value in values)
        for pattern in cls.SPACE_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    return float(match.group(1).replace(",", "."))
                except ValueError:
                    return 0.0
        return 0.0

    def action_import(self):
        self.ensure_one()
        action = super().action_import()
        text, _source_file_name = self._read_payload()
        lines = text.splitlines()
        if not lines:
            return action

        header = lines[0].split(";")
        manufacturer_name = (header[8] or "Unbekannter Hersteller").strip() if len(header) > 8 else "Unbekannter Hersteller"
        manufacturer = self.env["sab.manufacturer"].search([("name", "=ilike", manufacturer_name)], limit=1)
        if not manufacturer:
            return action

        Product = self.env["sab.product"].sudo()
        SupplierProduct = self.env["sab.supplier.product"].sudo()
        product_map = {
            product.manufacturer_article_number: product
            for product in Product.search([
                ("manufacturer_id", "=", manufacturer.id),
                ("manufacturer_article_number", "!=", False),
            ])
        }
        supplier_map = {
            item.supplier_article_number: item
            for item in SupplierProduct.search([
                ("supplier_id", "=", self.supplier_id.id),
                ("supplier_article_number", "!=", False),
            ])
        }

        enriched_prices = enriched_spaces = 0
        for raw_line in lines[1:]:
            if not raw_line.startswith("A;"):
                continue
            parts = raw_line.split(";")
            if len(parts) < 19:
                continue
            article_number = parts[2].strip()
            manufacturer_article = parts[16].strip() or article_number
            datanorm_price = self._parse_price(parts[8].strip())
            supplier_product = supplier_map.get(article_number)
            if supplier_product:
                vals = {"list_price": datanorm_price}
                # Vorhandenen echten EK nicht überschreiben. Nur ohne EK dient
                # der Listenpreis als kalkulatorischer Fallback.
                if not supplier_product.purchase_price:
                    vals["purchase_price"] = datanorm_price
                supplier_product.write(vals)
                enriched_prices += 1

            product = product_map.get(manufacturer_article)
            if product:
                combined_text = " ".join(value.strip() for value in parts[3:5] + parts[12:18] if value.strip())
                space_units = self._space_units_from_text(combined_text)
                if space_units:
                    product.write({"space_units": space_units})
                    enriched_spaces += 1

        suffix = f"\nListenpreise gespeichert: {enriched_prices}\nPlatzeinheiten aus DATANORM erkannt: {enriched_spaces}"
        self.result_text = (self.result_text or "") + suffix
        return action
