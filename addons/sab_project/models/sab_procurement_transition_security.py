from odoo import models
from odoo.exceptions import AccessError


class SabProjectBomProcurementWriteSecurity(models.Model):
    _inherit = "sab.project.bom"

    def write(self, vals):
        approval_fields = {
            "purchase_release_state",
            "purchase_released_at",
            "purchase_released_by_id",
        }
        if approval_fields.intersection(vals) and not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchase_approver")
        ):
            raise AccessError(
                "Bestellfreigaben dürfen nur durch einen im Mitarbeiterprofil "
                "festgelegten Bestellfreigeber geändert werden."
            )
        return super().write(vals)


class SabPurchaseOrderTransitionSecurity(models.Model):
    _inherit = "sab.purchase.order"

    def write(self, vals):
        target_state = vals.get("state")
        if target_state == "approved" or {
            "approved_at",
            "approved_by_id",
        }.intersection(vals):
            self._check_project_manager()
        elif target_state in ("draft", "to_approve", "sent", "cancel"):
            self._check_purchasing_user()
        elif target_state in ("partial", "done"):
            self._check_receiving_user()
        return super().write(vals)


class SabPurchaseOrderLineTransitionSecurity(models.Model):
    _inherit = "sab.purchase.order.line"

    def write(self, vals):
        if "expected_delivery_date" in vals and not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Voraussichtliche Liefertermine dürfen nur durch einen im "
                "Mitarbeiterprofil freigeschalteten Einkaufsmitarbeiter gepflegt werden."
            )
        if {"quantity_to_receive", "quantity_received"}.intersection(vals) and not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Liefermengen dürfen nur durch Lager oder Einkauf gepflegt werden."
            )
        return super().write(vals)
