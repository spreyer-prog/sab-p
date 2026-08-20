from odoo import fields, models


class ProductTemplateSabOdoo19UomCompat(models.Model):
    _inherit = "product.template"

    # Odoo 19 uses one product unit for sales, stock and purchasing. Older
    # SAB-P bridge code still addresses uom_po_id. Keep that code compatible
    # without maintaining a second, diverging purchase unit.
    uom_po_id = fields.Many2one(
        "uom.uom",
        string="Purchase Unit",
        related="uom_id",
        readonly=False,
    )


class ProductProductSabOdoo19UomCompat(models.Model):
    _inherit = "product.product"

    uom_po_id = fields.Many2one(
        "uom.uom",
        string="Purchase Unit",
        related="uom_id",
        readonly=False,
    )
