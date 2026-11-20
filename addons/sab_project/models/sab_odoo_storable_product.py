from odoo import models


class SabProductOdooStorable(models.Model):
    _inherit = "sab.product"

    def _odoo_product_values(self):
        values = super()._odoo_product_values()
        if self.product_type == "material":
            values["is_storable"] = True
        return values

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE product_template
               SET is_storable = TRUE
             WHERE type = 'consu'
               AND sab_product_type = 'material'
               AND NOT is_storable
            """
        )
