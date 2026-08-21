from odoo import models, _
from odoo.exceptions import AccessError, ValidationError


class SabProjectBomProcurementHandover(models.Model):
    _inherit = "sab.project.bom"

    def action_open_procurement_package_from_bom(self):
        self.ensure_one()
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("project.group_project_manager")
            or self.env.user.has_group("base.group_system")
        ):
            raise AccessError(
                _("Nur Projektleitung oder Administration darf eine Stückliste an den Einkauf übergeben.")
            )
        if self.bom_scope != "total":
            raise ValidationError(
                _("Die Übergabe an den Einkauf wird aus der Gesamtstückliste gestartet.")
            )
        if self.state != "released":
            raise ValidationError(
                _("Bitte die Gesamtstückliste zuerst technisch freigeben.")
            )
        if not self.order_id or self.order_id.state not in ("sale", "done"):
            raise ValidationError(
                _("Die Stückliste kann erst nach Auftragserteilung an den Einkauf übergeben werden.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Stückliste an Einkauf übergeben"),
            "res_model": "sab.procurement.package.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.order_id.id,
                "active_model": "sale.order",
                "active_id": self.order_id.id,
            },
        }
