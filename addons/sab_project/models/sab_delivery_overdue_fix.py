from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabPurchaseOrderLineDeliveryOverdueSearchFix(models.Model):
    _inherit = "sab.purchase.order.line"

    @api.model
    def _search_delivery_is_overdue(self, operator, value):
        overdue_ids = self.search(
            [
                ("order_id.state", "in", ("sent", "partial")),
                ("expected_delivery_date", "<", fields.Date.context_today(self)),
                ("quantity_remaining", ">", 0),
            ]
        ).ids
        wants_overdue = bool(value)
        if operator in ("!=", "not in"):
            wants_overdue = not wants_overdue
        return [("id", "in" if wants_overdue else "not in", overdue_ids)]


class SabPurchaseOrderDeliveryOverdueSendFix(models.Model):
    _inherit = "sab.purchase.order"

    def _sab_get_overdue_lines_for_email(self):
        self.ensure_one()
        requested_ids = self.env.context.get("sab_overdue_line_ids") or []
        lines = (
            self.env["sab.purchase.order.line"].browse(requested_ids).exists()
            if requested_ids
            else self.overdue_line_ids
        )
        return lines.filtered(
            lambda line: line.order_id == self and line.delivery_is_overdue
        )

    def _sab_send_overdue_delivery_reminder(self, lines=False):
        self.ensure_one()
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Liefertermin-Nachfragen dürfen nur durch den Einkauf versendet werden."
            )
        overdue_lines = (lines or self.overdue_line_ids).filtered(
            lambda line: line.order_id == self and line.delivery_is_overdue
        )
        if not overdue_lines:
            raise ValidationError(
                f"Bestellung {self.name} enthält keine überfällige Lieferposition."
            )
        if not self.partner_id or not self.partner_id.email:
            raise ValidationError(
                f"Beim Lieferanten {self.supplier_id.name} ist keine E-Mail-Adresse hinterlegt."
            )
        template = self.env.ref(
            "sab_project.mail_template_sab_delivery_overdue",
            raise_if_not_found=False,
        )
        if not template:
            raise ValidationError(
                "Die E-Mail-Vorlage für Liefertermin-Nachfragen fehlt."
            )

        template.with_context(
            sab_overdue_line_ids=overdue_lines.ids
        ).send_mail(
            self.id,
            force_send=True,
            email_values={"email_to": self.partner_id.email},
        )
        now = fields.Datetime.now()
        for line in overdue_lines:
            line.write(
                {
                    "delivery_reminder_count": line.delivery_reminder_count + 1,
                    "delivery_reminder_sent_at": now,
                    "delivery_reminder_sent_by_id": self.env.user.id,
                }
            )
        self.write(
            {
                "delivery_reminder_sent_at": now,
                "delivery_reminder_sent_by_id": self.env.user.id,
            }
        )
        self.message_post(
            body=_(
                "Liefertermin-Nachfrage zu %s über %s überfällige Position(en) "
                "an %s versendet."
            )
            % (self.name, len(overdue_lines), self.partner_id.email)
        )

        model_id = self.env["ir.model"]._get_id(self._name)
        activities = self.env["mail.activity"].sudo().search(
            [
                ("res_model_id", "=", model_id),
                ("res_id", "=", self.id),
                ("summary", "=", "Liefertermin überschritten"),
            ]
        )
        if activities:
            activities.unlink()
        return True
