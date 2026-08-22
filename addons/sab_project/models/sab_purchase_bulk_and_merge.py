from odoo import fields, models, _
from odoo.exceptions import ValidationError
from odoo.fields import Command


class PurchaseOrderSabBulkAndMerge(models.Model):
    _inherit = "purchase.order"

    def action_sab_merge_selected_orders(self):
        orders = self.exists()
        if len(orders) < 2:
            raise ValidationError(_("Bitte mindestens zwei Bestellvorschläge auswählen."))
        if any(not order.sab_is_suite_order for order in orders):
            raise ValidationError(_("Es dürfen nur SAB-P-Bestellvorschläge zusammengeführt werden."))
        partners = orders.mapped("partner_id")
        if len(partners) != 1:
            raise ValidationError(
                _("Bestellvorschläge können nur zusammengeführt werden, wenn der Lieferant identisch ist.")
            )
        invalid = orders.filtered(lambda order: order.state not in ("draft", "sent"))
        if invalid:
            raise ValidationError(
                _("Nur offene Bestellvorschläge bzw. Angebotsanfragen dürfen zusammengeführt werden.")
            )

        target = orders.sorted(key=lambda order: order.id)[0]
        sources = orders - target

        # Eine bereits versendete Anfrage wird durch das Zusammenführen inhaltlich
        # verändert und muss deshalb wieder als neuer Entwurf behandelt werden.
        if target.state == "sent":
            target.button_cancel()
            target.button_draft()

        project_ids = set(target.sab_project_ids.ids)
        procurement_ids = set(target.sab_procurement_bom_ids.ids)
        origins = {part.strip() for part in (target.origin or "").split(",") if part.strip()}

        for source in sources:
            if source.state == "sent":
                source.button_cancel()
            source.order_line.write({"order_id": target.id})
            project_ids.update(source.sab_project_ids.ids)
            procurement_ids.update(source.sab_procurement_bom_ids.ids)
            origins.update(
                part.strip() for part in (source.origin or "").split(",") if part.strip()
            )
            if source.state != "cancel":
                source.button_cancel()

        target.write(
            {
                "sab_project_ids": [Command.set(sorted(project_ids))],
                "sab_procurement_bom_ids": [Command.set(sorted(procurement_ids))],
                "origin": ", ".join(sorted(origins)),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Zusammengeführter Bestellvorschlag"),
            "res_model": "purchase.order",
            "res_id": target.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_sab_direct_order(self):
        self.ensure_one()
        if not self.sab_is_suite_order:
            raise ValidationError(_("Diese Aktion ist nur für SAB-P-Bestellungen vorgesehen."))
        if self.state not in ("draft", "sent"):
            raise ValidationError(_("Nur ein offener Bestellvorschlag kann bestellt werden."))
        self.button_confirm()
        # Systemadministratoren und hinterlegte Bestellfreigeber dürfen den
        # vollständigen Bestellschritt in einem Zug abschließen. Bei normalen
        # Einkaufsmitarbeitern bleibt die vorgesehene Freigabestufe erhalten.
        if self.state == "to approve" and (
            self.env.is_superuser()
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group("sab_project.group_sab_purchase_approver")
        ):
            self.button_approve()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellung"),
            "res_model": "purchase.order",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_sab_send_supplier_inquiry(self):
        self.ensure_one()
        if not self.sab_is_suite_order or self.state not in ("draft", "sent"):
            raise ValidationError(_("Eine Angebotsanfrage kann nur aus einem offenen SAB-P-Bestellvorschlag gesendet werden."))
        return self.action_rfq_send()
