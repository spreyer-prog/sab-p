from odoo import models


class SabProjectBomProcurementOrderQuantityReleaseFix(models.Model):
    _inherit = "sab.project.bom"

    def action_release_for_purchase(self):
        result = super().action_release_for_purchase()
        for bom in self:
            if getattr(bom, "purchase_release_state", False) != "released":
                continue
            requirements = bom.purchase_requirement_ids.filtered(
                lambda requirement: requirement.state == "open"
                and not requirement.optional
                and not requirement.purchase_order_line_id
            )
            if requirements:
                requirements._sab_prepare_order_quantities()
        return result
