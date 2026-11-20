from odoo import models


class ProjectProjectProcurementActionDomainFix(models.Model):
    _inherit = "project.project"

    def action_view_sab_material_requirements(self):
        """Keep the project constraint visible in the material action domain.

        The selected procurement package is still narrowed to its exact
        requirement IDs. Adding the project condition makes the action explicit,
        keeps it safe when reused by other views and preserves the established
        project-level contract tested by the existing procurement workflow.
        """
        self.ensure_one()
        action = super().action_view_sab_material_requirements()
        if action.get("res_model") != "sab.purchase.requirement":
            return action

        requirements = self._sab_current_procurement_requirements()
        if requirements:
            action["domain"] = [
                ("project_id", "=", self.id),
                ("id", "in", requirements.ids),
            ]
        return action
