from odoo import fields, models


class ProductProductSabOdoo19UomCompat(models.Model):
    _inherit = "product.product"

    # Odoo 19 has one product unit. Older SAB-P purchase bridge code still
    # reads product.uom_po_id, so expose a non-stored compatibility alias.
    uom_po_id = fields.Many2one(
        "uom.uom",
        string="Purchase Unit",
        related="uom_id",
        readonly=True,
    )
