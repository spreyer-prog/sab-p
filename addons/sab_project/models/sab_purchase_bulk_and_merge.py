from collections import defaultdict

from odoo import models, _
from odoo.exceptions import ValidationError
from odoo.fields import Command


class PurchaseOrderSabBulkAndMerge(models.Model):
    _inherit = "purchase.order"

    def _sab_merge_by_supplier(self):
        orders = self.exists()
        if not orders:
            raise ValidationError(_("Bitte mindestens einen Bestellvorschlag auswählen."))
        if any(not order.sab_is_suite_order for order in orders):
            raise ValidationError(_("Es dürfen nur SAB-P-Bestellvorschläge verarbeitet werden."))
        invalid = orders.filtered(lambda order: order.state not in ("draft", "sent"))
        if invalid:
            raise ValidationError(
                _("Nur offene Bestellvorschläge bzw. Angebotsanfragen dürfen verarbeitet werden.")
            )

        grouped = defaultdict(lambda: self.env["purchase.order"])
        for order in orders:
            grouped[order.partner_id.id] |= order

        targets = self.env["purchase.order"]
        for _partner_id, supplier_orders in grouped.items():
            supplier_orders = supplier_orders.sorted(key=lambda order: order.id)
            target = supplier_orders[0]
            sources = supplier_orders - target

            if target.state == "sent" and sources:
                target.button_cancel()
                target.button_draft()

            project_ids = set(target.sab_project_ids.ids)
            procurement_ids = set(target.sab_procurement_bom_ids.ids)
            origins = {
                part.strip()
                for part in (target.origin or "").split(",")
                if part.strip()
            }

            for source in sources:
                if source.partner_id != target.partner_id:
                    raise ValidationError(
                        _("Bestellvorschläge verschiedener Lieferanten dürfen niemals in denselben Beleg gelangen.")
                    )
                if source.state == "sent":
                    source.button_cancel()
                source.order_line.write({"order_id": target.id})
                project_ids.update(source.sab_project_ids.ids)
                procurement_ids.update(source.sab_procurement_bom_ids.ids)
                origins.update(
                    part.strip()
                    for part in (source.origin or "").split(",")
                    if part.strip()
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
            if hasattr(target, "_sab_refresh_suite_links_from_lines"):
                target._sab_refresh_suite_links_from_lines()
            targets |= target
        return targets

    def action_sab_merge_selected_orders(self):
        targets = self._sab_merge_by_supplier()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellvorschläge nach Lieferant"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", targets.ids)],
            "context": {"create": False},
            "target": "current",
        }

    def action_sab_direct_order(self):
        targets = self._sab_merge_by_supplier()
        for order in targets:
            if order.state in ("draft", "sent"):
                order.button_confirm()
            if order.state == "to approve" and (
                self.env.is_superuser()
                or self.env.user.has_group("base.group_system")
                or self.env.user.has_group("sab_project.group_sab_purchase_approver")
            ):
                order.button_approve()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellungen"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", targets.ids)],
            "context": {"create": False},
            "target": "current",
        }

    def action_sab_prepare_supplier_inquiries(self):
        targets = self._sab_merge_by_supplier()
        return {
            "type": "ir.actions.act_window",
            "name": _("Anfragen nach Lieferant"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", targets.ids)],
            "context": {"create": False, "sab_supplier_inquiry_mode": True},
            "target": "current",
        }

    def action_sab_send_supplier_inquiry(self):
        self.ensure_one()
        if not self.sab_is_suite_order or self.state not in ("draft", "sent"):
            raise ValidationError(
                _("Eine Angebotsanfrage kann nur aus einem offenen SAB-P-Bestellvorschlag gesendet werden.")
            )
        return self.action_rfq_send()
