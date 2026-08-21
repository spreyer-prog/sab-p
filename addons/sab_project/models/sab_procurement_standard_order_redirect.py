from odoo import models


class SabPurchaseRequirementStandardOrderRedirect(models.Model):
    _inherit = "sab.purchase.requirement"

    def action_create_purchase_orders(self):
        """Create native Odoo purchase orders from the selected requirements.

        The purchasing workspace keeps its established button/action contract,
        but the actual order document is the native Odoo purchase.order. This
        gives purchasing the normal editable order form with product, section
        and note lines while preserving SAB-P requirement/project assignments.
        """
        return self.action_create_standard_purchase_orders()
