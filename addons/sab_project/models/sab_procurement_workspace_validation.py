from odoo import api, models, _
from odoo.exceptions import ValidationError


class SabPurchaseRequirementWorkspaceValidation(models.Model):
    _inherit = "sab.purchase.requirement"

    @api.constrains("quantity_to_order")
    def _check_quantity_to_order(self):
        for requirement in self:
            if requirement.quantity_to_order < 0:
                raise ValidationError(
                    _("Die ausgewählte Bestellmenge darf nicht negativ sein.")
                )
