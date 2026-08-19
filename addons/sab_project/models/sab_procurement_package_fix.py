from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabProjectBomProcurementPackageFix(models.Model):
    _inherit = "sab.project.bom"

    def action_open_procurement_workspace(self):
        self.ensure_one()
        if self.state != "released":
            raise ValidationError(
                "Der Einkaufsbereich steht erst nach technischer Freigabe des Beschaffungspakets zur Verfügung."
            )
        if getattr(self, "bom_scope", "total") != "procurement":
            return super().action_open_procurement_workspace()
        self._sab_push_to_procurement_workspace()
        if (
            self.env.user.has_group("sab_project.group_sab_purchasing")
            and not self.procurement_acknowledged
        ):
            self.write(
                {
                    "procurement_acknowledged": True,
                    "procurement_acknowledged_at": fields.Datetime.now(),
                    "procurement_acknowledged_by_id": self.env.user.id,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Einkaufsbearbeitung – %s")
            % (self.procurement_reference or self.project_id.display_name),
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [
                ("bom_id", "=", self.id),
                ("state", "!=", "cancel"),
            ],
            "context": {
                "search_default_group_project": 0,
                "search_default_open": 1,
            },
            "target": "current",
        }

    def action_complete_picking(self):
        result = super().action_complete_picking()
        for package in self.filtered(
            lambda bom: getattr(bom, "bom_scope", "total") == "procurement"
        ):
            package.purchase_requirement_ids.invalidate_recordset()
            still_missing = package.purchase_requirement_ids.filtered(
                lambda requirement: requirement.state != "cancel"
                and requirement.shortage_quantity > 1e-9
            )
            package.write(
                {
                    "picking_state": "partial" if still_missing else "done",
                }
            )
        return result
