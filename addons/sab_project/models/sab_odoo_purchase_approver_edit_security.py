from odoo import api, models
from odoo.exceptions import AccessError


class PurchaseOrderSabApproverEditSecurity(models.Model):
    _inherit = "purchase.order"

    def _sab_is_pure_purchase_approver(self):
        return (
            not self.env.is_superuser()
            and self.env.user.has_group(
                "sab_project.group_sab_purchase_approver"
            )
            and not self.env.user.has_group(
                "sab_project.group_sab_purchasing"
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self._sab_is_pure_purchase_approver() and any(
            values.get("sab_is_suite_order") for values in vals_list
        ):
            raise AccessError(
                "Ein reiner Bestellfreigeber darf keine SAB-P-Bestellung "
                "anlegen."
            )
        return super().create(vals_list)

    def write(self, vals):
        if (
            self.filtered("sab_is_suite_order")
            and self._sab_is_pure_purchase_approver()
            and not self.env.context.get("sab_purchase_approval_transition")
        ):
            raise AccessError(
                "Ein reiner Bestellfreigeber darf SAB-P-Bestellungen nicht "
                "inhaltlich verändern. Er darf sie ausschließlich freigeben "
                "oder ablehnen."
            )
        return super().write(vals)

    def button_approve(self, force=False):
        return super(
            PurchaseOrderSabApproverEditSecurity,
            self.with_context(sab_purchase_approval_transition=True),
        ).button_approve(force=force)


class PurchaseOrderLineSabApproverEditSecurity(models.Model):
    _inherit = "purchase.order.line"

    def _sab_is_pure_purchase_approver(self):
        return (
            not self.env.is_superuser()
            and self.env.user.has_group(
                "sab_project.group_sab_purchase_approver"
            )
            and not self.env.user.has_group(
                "sab_project.group_sab_purchasing"
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self._sab_is_pure_purchase_approver():
            order_ids = [
                values.get("order_id")
                for values in vals_list
                if values.get("order_id")
            ]
            protected_orders = self.env["purchase.order"].browse(
                order_ids
            ).filtered("sab_is_suite_order")
            if protected_orders:
                raise AccessError(
                    "Ein reiner Bestellfreigeber darf keine Position zu einer "
                    "SAB-P-Bestellung ergänzen."
                )
        return super().create(vals_list)

    def write(self, vals):
        if (
            self.mapped("order_id").filtered("sab_is_suite_order")
            and self._sab_is_pure_purchase_approver()
        ):
            raise AccessError(
                "Ein reiner Bestellfreigeber darf Positionen einer "
                "SAB-P-Bestellung nicht verändern."
            )
        return super().write(vals)

    def unlink(self):
        if (
            self.mapped("order_id").filtered("sab_is_suite_order")
            and self._sab_is_pure_purchase_approver()
        ):
            raise AccessError(
                "Ein reiner Bestellfreigeber darf Positionen einer "
                "SAB-P-Bestellung nicht löschen."
            )
        return super().unlink()
