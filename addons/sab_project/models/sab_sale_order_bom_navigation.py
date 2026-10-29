from odoo import models, _
from odoo.exceptions import ValidationError


class SaleOrderSabBomNavigation(models.Model):
    _inherit = "sale.order"

    def action_view_sab_boms(self):
        self.ensure_one()
        boms = self.sab_bom_ids
        if not boms:
            raise ValidationError(
                _("Für diesen Auftrag wurden noch keine SAB-P Stücklisten erzeugt.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("SAB-P Stücklisten – %s") % (self.sab_offer_reference or self.name),
            "res_model": "sab.project.bom",
            "view_mode": "list,form",
            "domain": [("id", "in", boms.ids)],
            "context": {"create": False},
            "target": "current",
        }
