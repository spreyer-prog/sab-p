from odoo import fields, models


class SabPurchaseRequirementReleaseCompat(models.Model):
    _inherit = "sab.purchase.requirement"

    def _sab_standard_purchase_requirements(self):
        """Backfill procurement release state for existing technically released packages.

        Older test/procurement packages created before the temporary employee-role
        bypass can still have purchase_release_state != 'released'. For a technically
        released procurement package, treat the missing procurement release flag as
        migrated state so existing packages can continue into the standard Odoo
        purchase proposal without being recreated.
        """
        packages = self.mapped("bom_id").filtered(
            lambda bom: getattr(bom, "bom_scope", "total") == "procurement"
            and bom.state == "released"
            and bom.purchase_release_state != "released"
        )
        if packages:
            packages.sudo().with_context(sab_procurement_release=True).write(
                {
                    "purchase_release_state": "released",
                    "purchase_released_at": fields.Datetime.now(),
                    "purchase_released_by_id": self.env.user.id,
                }
            )
        return super()._sab_standard_purchase_requirements()
