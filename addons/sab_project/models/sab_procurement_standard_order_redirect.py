from odoo import models


class SabPurchaseRequirementStandardOrderSelection(models.Model):
    _inherit = "sab.purchase.requirement"

    def action_create_standard_purchase_orders_from_selection(self):
        """Create native Odoo purchase orders only for explicitly selected rows.

        The legacy action_create_purchase_orders contract remains untouched for
        existing SAB-P workflows and regression tests.  The purchasing workspace
        uses this dedicated action so unselected open requirements remain in the
        workspace for a later order run.
        """
        return self.action_create_standard_purchase_orders()
