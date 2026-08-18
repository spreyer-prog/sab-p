from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    sab_manufacturer_supplier_id = fields.Many2one("sab.supplier", string="Hersteller", ondelete="restrict", index=True)
    sab_manufacturer_id = fields.Many2one("sab.manufacturer", string="Hersteller (Altbestand)", ondelete="restrict", index=True)
    sab_manufacturer_article_number = fields.Char(string="Herstellerartikelnummer", index=True)
    sab_datanorm_number = fields.Char(string="DATANORM-Nummer", index=True)
    sab_price_mode = fields.Selection([
        ("supplier", "Lieferantenartikel"),
        ("fixed", "Fixpreis"),
    ], string="SAB-P Preisermittlung", default="supplier", required=True)
    sab_fixed_purchase_price = fields.Float(string="SAB-P Fixpreis EK", digits=(16, 4), default=0.0)
    sab_supplier_product_ids = fields.One2many("sab.supplier.product", "odoo_product_id", string="SAB-P Lieferantenartikel")
    sab_calculated_purchase_price = fields.Float(string="SAB-P kalkulatorischer EK", digits=(16, 4), compute="_compute_sab_calculated_purchase_price", store=True)
    sab_space_units = fields.Float(string="Platzeinheiten", default=0.0)
    sab_mechanical_time_minutes = fields.Float(string="Mechanikzeit in Minuten", default=0.0)
    sab_wiring_time_minutes = fields.Float(string="Verdrahtungszeit in Minuten", default=0.0)
    sab_testing_time_minutes = fields.Float(string="Prüfzeit in Minuten", default=0.0)

    @api.depends(
        "sab_price_mode",
        "sab_fixed_purchase_price",
        "sab_supplier_product_ids.active",
        "sab_supplier_product_ids.preferred",
        "sab_supplier_product_ids.net_purchase_price",
    )
    def _compute_sab_calculated_purchase_price(self):
        for product in self:
            if product.sab_price_mode == "fixed":
                product.sab_calculated_purchase_price = product.sab_fixed_purchase_price or 0.0
                continue
            candidates = product.sab_supplier_product_ids.filtered("active")
            preferred = candidates.filtered("preferred")
            pool = preferred or candidates
            product.sab_calculated_purchase_price = min(pool.mapped("net_purchase_price")) if pool else 0.0
