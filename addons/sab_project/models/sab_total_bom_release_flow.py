from odoo import models


class SabProjectBomTotalReleaseFlow(models.Model):
    _inherit = "sab.project.bom"

    def action_release(self):
        result = super().action_release()
        totals = self.filtered(
            lambda bom: getattr(bom, "bom_scope", "total") == "total"
        )
        for total in totals:
            cabinet_boms = self.search(
                [
                    ("order_id", "=", total.order_id.id),
                    ("bom_scope", "=", "cabinet"),
                    ("state", "=", "draft"),
                ]
            )
            if cabinet_boms:
                # Same technical decision as the total BOM. The project manager
                # must not have to repeat the identical release per cabinet.
                super(SabProjectBomTotalReleaseFlow, cabinet_boms).action_release()
        return result
