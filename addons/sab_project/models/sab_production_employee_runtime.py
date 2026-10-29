from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabProductionStepEmployeeRuntime(models.Model):
    _inherit = "sab.production.step"

    def _start_parent_order_from_employee_step(self):
        """Start the parent order through this controlled workflow only.

        SAB-P employees intentionally have read-only ACLs on production orders.
        Starting a permitted production step must nevertheless move its parent
        order from planned to in-progress.  The sudo is limited to that exact
        system transition so employees do not receive general write access to
        production orders.
        """
        for record in self:
            order = record.production_order_id
            if order.state != "planned":
                continue
            if order.bom_id.state != "released":
                raise ValidationError(_("Die Fertigung kann nur mit einer freigegebenen Stückliste gestartet werden."))
            order.sudo().write({
                "state": "in_progress",
                "started_at": order.started_at or fields.Datetime.now(),
            })

    def action_start(self):
        self._ensure_editable()
        self._ensure_user_can_work()
        self._claim_for_current_employee()
        for record in self:
            if record.state not in ("pending", "paused"):
                raise ValidationError(_("Nur offene oder pausierte Arbeitsschritte können gestartet werden."))
            record.write({
                "state": "in_progress",
                "started_at": record.started_at or fields.Datetime.now(),
                "paused_at": False,
            })
            record._start_parent_order_from_employee_step()
        return True

    def action_done(self):
        self._ensure_editable()
        self._ensure_user_can_work()
        self._claim_for_current_employee()
        for record in self:
            if record.state not in ("pending", "in_progress", "paused"):
                raise ValidationError(_("Nur offene, laufende oder pausierte Arbeitsschritte können fertiggemeldet werden."))
            record.write({
                "state": "done",
                "started_at": record.started_at or fields.Datetime.now(),
                "paused_at": False,
                "finished_at": fields.Datetime.now(),
            })
            record._start_parent_order_from_employee_step()
        return True
