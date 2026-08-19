from odoo import models
from odoo.exceptions import AccessError, ValidationError


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
        if vals.get("purchase_release_state") == "released":
            for bom in self:
                if bom.state != "released":
                    raise ValidationError(
                        "Die Stückliste muss vor der Bestellfreigabe technisch freigegeben sein."
                    )
                if getattr(bom, "bom_scope", "total") != "total":
                    raise ValidationError(
                        "Nur die Gesamtstückliste darf zur Beschaffung freigegeben werden."
                    )
        return super().write(vals)


class SabPurchaseOrderTransitionSecurity(models.Model):
    _inherit = "sab.purchase.order"

    def _validate_direct_state_transition(self, target_state):
        if not target_state:
            return
        for order in self:
            if target_state == order.state:
                continue
            if target_state == "draft":
                raise ValidationError(
                    "Eine Lieferantenbestellung darf nicht in den Entwurf zurückgesetzt werden."
                )
            if target_state == "to_approve":
                if order.state != "draft" or not order.line_ids:
                    raise ValidationError(
                        "Nur ein nicht leerer Bestellentwurf kann zur Freigabe vorgelegt werden."
                    )
            elif target_state == "approved":
                if order.state not in ("draft", "to_approve"):
                    raise ValidationError(
                        "Nur ein Entwurf oder eine vorgelegte Bestellung kann freigegeben werden."
                    )
            elif target_state == "sent":
                if order.state != "approved":
                    raise ValidationError(
                        "Nur eine freigegebene Bestellung darf an den Lieferanten versendet werden."
                    )
            elif target_state in ("partial", "done"):
                if order.state not in ("sent", "partial"):
                    raise ValidationError(
                        "Wareneingänge sind nur bei versendeten Bestellungen zulässig."
                    )
                remaining = order.line_ids.filtered(
                    lambda line: line.quantity_remaining > 1e-9
                )
                received = order.line_ids.filtered(
                    lambda line: line.quantity_received > 0
                )
                if target_state == "done" and remaining:
                    raise ValidationError(
                        "Eine Bestellung mit offenen Mengen darf nicht abgeschlossen werden."
                    )
                if target_state == "partial" and (not received or not remaining):
                    raise ValidationError(
                        "Der Status 'Teilgeliefert' benötigt gelieferte und noch offene Mengen."
                    )
            elif target_state == "cancel":
                if order.state in ("done", "cancel"):
                    raise ValidationError(
                        "Eine abgeschlossene oder bereits stornierte Bestellung kann nicht storniert werden."
                    )
                if any(line.quantity_received > 0 for line in order.line_ids):
                    raise ValidationError(
                        "Eine Bestellung mit gebuchtem Wareneingang darf nicht storniert werden."
                    )

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
        self._validate_direct_state_transition(target_state)
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
        if "quantity_received" in vals:
            for line in self:
                incoming = vals.get("quantity_received") or 0.0
                if incoming < line.quantity_received - 1e-9:
                    raise ValidationError(
                        "Bereits gebuchte Liefermengen dürfen nicht reduziert werden."
                    )
                if incoming > line.quantity_ordered + 1e-9:
                    raise ValidationError(
                        "Die gelieferte Menge darf die Bestellmenge nicht überschreiten."
                    )
        return super().write(vals)
