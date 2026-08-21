from odoo import models


class SabPurchaseRequirementAdminAccess(models.Model):
    _inherit = "sab.purchase.requirement"

    def _sab_check_standard_purchase_user(self):
        if self.env.user.has_group("base.group_system"):
            return True
        return super()._sab_check_standard_purchase_user()
