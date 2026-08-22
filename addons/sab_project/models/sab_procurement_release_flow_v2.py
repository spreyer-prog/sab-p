from collections import defaultdict

from odoo import models, _
from odoo.exceptions import ValidationError
from odoo.fields import Command


class SabProjectBomReleaseFlowV2(models.Model):
    _inherit = "sab.project.bom"

    def action_release(self):
        result = super().action_release()
        for bom in self.filtered(lambda record: getattr(record, "bom_scope", "total") == "total"):
            cabinet_boms = self.search([
                ("order_id", "=", bom.order_id.id),
                ("bom_scope", "=", "cabinet"),
                ("state", "=", "draft"),
            ])
            if cabinet_boms:
                super(SabProjectBomReleaseFlowV2, cabinet_boms).action_release()
        return result


class PurchaseOrderSabSupplierProposalFlow(models.Model):
    _inherit = "purchase.order"

    def action_sab_merge_selected_by_supplier(self):
        orders = self.exists().filtered(
            lambda order: order.sab_is_suite_order and order.state in ("draft", "sent")
        )
        if not orders:
            raise ValidationError(_("Bitte mindestens einen offenen SAB-P-Bestellvorschlag auswählen."))

        grouped = defaultdict(lambda: self.env["purchase.order"])
        for order in orders:
            grouped[order.partner_id.id] |= order

        targets = self.env["purchase.order"]
        for _partner_id, supplier_orders in grouped.items():
            supplier_orders = supplier_orders.sorted(key=lambda order: order.id)
            target = supplier_orders[0]
            targets |= target
            for source in supplier_orders[1:]:
                if source.partner_id != target.partner_id:
                    raise ValidationError(_("Bestellvorschläge verschiedener Lieferanten dürfen nicht zusammengeführt werden."))
                source.order_line.write({"order_id": target.id})
                target.write({
                    "sab_project_ids": [Command.link(record.id) for record in source.sab_project_ids],
                    "sab_procurement_bom_ids": [Command.link(record.id) for record in source.sab_procurement_bom_ids],
                })
                source.button_cancel()
            target._sab_refresh_suite_links_from_lines()

        return {
            "type": "ir.actions.act_window",
            "name": _("Zusammengefasste Bestellvorschläge"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", targets.ids)],
            "context": {"create": False},
            "target": "current",
        }

    def action_sab_create_order(self):
        for order in self:
            if not order.sab_is_suite_order:
                raise ValidationError(_("Diese Aktion ist nur für SAB-P-Bestellvorschläge vorgesehen."))
            if order.state not in ("draft", "sent", "to approve"):
                continue
            if order.state in ("draft", "sent"):
                order.button_confirm()
            if order.state == "to approve" and (
                self.env.is_superuser()
                or self.env.user.has_group("base.group_system")
                or self.env.user.has_group("sab_project.group_sab_purchase_approver")
            ):
                order.button_approve()
        return True
