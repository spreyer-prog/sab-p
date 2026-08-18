from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    sab_product_type = fields.Selection(related="product_tmpl_id.sab_product_type", readonly=False, store=True)
    sab_manufacturer_supplier_id = fields.Many2one(related="product_tmpl_id.sab_manufacturer_supplier_id", readonly=False, store=True)
    sab_manufacturer_id = fields.Many2one(related="product_tmpl_id.sab_manufacturer_id", readonly=False, store=True)
    sab_manufacturer_article_number = fields.Char(related="product_tmpl_id.sab_manufacturer_article_number", readonly=False, store=True)
    sab_datanorm_number = fields.Char(related="product_tmpl_id.sab_datanorm_number", readonly=False, store=True)
    sab_price_mode = fields.Selection(related="product_tmpl_id.sab_price_mode", readonly=False, store=True)
    sab_fixed_purchase_price = fields.Float(related="product_tmpl_id.sab_fixed_purchase_price", readonly=False, store=True)
    sab_space_units = fields.Float(related="product_tmpl_id.sab_space_units", readonly=False, store=True)
    sab_mechanical_time_minutes = fields.Float(related="product_tmpl_id.sab_mechanical_time_minutes", readonly=False, store=True)
    sab_wiring_time_minutes = fields.Float(related="product_tmpl_id.sab_wiring_time_minutes", readonly=False, store=True)
    sab_testing_time_minutes = fields.Float(related="product_tmpl_id.sab_testing_time_minutes", readonly=False, store=True)
    sab_notes = fields.Text(related="product_tmpl_id.sab_notes", readonly=False)

    sab_supplier_product_ids = fields.One2many("sab.supplier.product", "odoo_product_id", string="Lieferantenartikel")
    sab_component_ids = fields.One2many("sab.product.component", "odoo_product_id", string="Baugruppenpositionen", copy=True)
    sab_calculated_purchase_price = fields.Float(
        string="Kalkulatorischer EK", digits=(16, 4), compute="_compute_sab_calculated_purchase_price", store=True
    )

    @api.depends(
        "sab_price_mode",
        "sab_fixed_purchase_price",
        "sab_component_ids.total_price",
        "sab_supplier_product_ids.active",
        "sab_supplier_product_ids.preferred",
        "sab_supplier_product_ids.net_purchase_price",
    )
    def _compute_sab_calculated_purchase_price(self):
        for product in self:
            if product.sab_price_mode == "fixed":
                product.sab_calculated_purchase_price = product.sab_fixed_purchase_price or 0.0
            elif product.sab_price_mode == "assembly":
                product.sab_calculated_purchase_price = sum(product.sab_component_ids.mapped("total_price"))
            else:
                candidates = product.sab_supplier_product_ids.filtered("active")
                preferred = candidates.filtered("preferred")
                pool = preferred or candidates
                product.sab_calculated_purchase_price = min(pool.mapped("net_purchase_price")) if pool else 0.0
