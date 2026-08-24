from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabPurchaseOrderLineDeliveryOverdue(models.Model):
    _inherit = "sab.purchase.order.line"

    supplier_id = fields.Many2one(
        related="order_id.supplier_id",
        string="Lieferant",
        store=True,
        readonly=True,
    )
    delivery_status = fields.Selection(
        [
            ("no_date", "Kein Liefertermin"),
            ("scheduled", "Liefertermin offen"),
            ("overdue", "Liefertermin überschritten"),
            ("received", "Vollständig geliefert"),
            ("cancel", "Storniert"),
        ],
        string="Lieferstatus",
        compute="_compute_delivery_overdue",
    )
    delivery_is_overdue = fields.Boolean(
        string="Liefertermin überschritten",
        compute="_compute_delivery_overdue",
        search="_search_delivery_is_overdue",
    )
    delivery_overdue_days = fields.Integer(
        string="Überfällig seit (Tagen)",
        compute="_compute_delivery_overdue",
    )
    delivery_reminder_count = fields.Integer(
        string="Liefertermin-Nachfragen",
        default=0,
        readonly=True,
        copy=False,
    )
    delivery_reminder_sent_at = fields.Datetime(
        string="Letzte Nachfrage am",
        readonly=True,
        copy=False,
    )
    delivery_reminder_sent_by_id = fields.Many2one(
        "res.users",
        string="Letzte Nachfrage durch",
        readonly=True,
        copy=False,
    )

    @api.depends(
        "expected_delivery_date",
        "quantity_remaining",
        "order_id.state",
    )
    def _compute_delivery_overdue(self):
        today = fields.Date.context_today(self)
        for line in self:
            if line.order_id.state == "cancel":
                status = "cancel"
                overdue = False
                days = 0
            elif line.quantity_remaining <= 1e-9:
                status = "received"
                overdue = False
                days = 0
            elif not line.expected_delivery_date:
                status = "no_date"
                overdue = False
                days = 0
            elif (
                line.order_id.state in ("sent", "partial")
                and line.expected_delivery_date < today
            ):
                status = "overdue"
                overdue = True
                days = (today - line.expected_delivery_date).days
            else:
                status = "scheduled"
                overdue = False
                days = 0
            line.delivery_status = status
            line.delivery_is_overdue = overdue
            line.delivery_overdue_days = days

    @api.model
    def _search_delivery_is_overdue(self, operator, value):
        overdue_domain = [
            ("order_id.state", "in", ("sent", "partial")),
            ("expected_delivery_date", "<", fields.Date.context_today(self)),
            ("quantity_remaining", ">", 0),
        ]
        wants_overdue = bool(value)
        if operator in ("!=", "not in"):
            wants_overdue = not wants_overdue
        if wants_overdue:
            return overdue_domain
        return ["!"] + overdue_domain

    def action_send_overdue_delivery_reminder(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Liefertermin-Nachfragen dürfen nur durch den Einkauf versendet werden."
            )
        overdue_lines = self.filtered("delivery_is_overdue")
        if not overdue_lines:
            raise ValidationError(
                "In der Auswahl befindet sich keine Position mit überschrittenem Liefertermin."
            )
        grouped = defaultdict(lambda: self.env["sab.purchase.order.line"])
        for line in overdue_lines:
            grouped[line.order_id.id] |= line
        for order_id, lines in grouped.items():
            self.env["sab.purchase.order"].browse(order_id)._sab_send_overdue_delivery_reminder(
                lines
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Liefertermin-Nachfrage versendet"),
                "message": _(
                    "Die überfälligen Positionen wurden je Bestellung zusammengefasst "
                    "und an den jeweiligen Lieferanten gesendet."
                ),
                "type": "success",
                "sticky": False,
            },
        }


class SabPurchaseOrderDeliveryOverdue(models.Model):
    _inherit = "sab.purchase.order"

    overdue_line_ids = fields.Many2many(
        "sab.purchase.order.line",
        string="Überfällige Lieferpositionen",
        compute="_compute_overdue_delivery",
    )
    overdue_line_count = fields.Integer(
        string="Überfällige Positionen",
        compute="_compute_overdue_delivery",
    )
    maximum_delivery_overdue_days = fields.Integer(
        string="Maximal überfällig (Tage)",
        compute="_compute_overdue_delivery",
    )
    has_overdue_delivery = fields.Boolean(
        string="Liefertermin überschritten",
        compute="_compute_overdue_delivery",
        search="_search_has_overdue_delivery",
    )
    delivery_reminder_sent_at = fields.Datetime(
        string="Letzte Liefertermin-Nachfrage am",
        readonly=True,
        copy=False,
    )
    delivery_reminder_sent_by_id = fields.Many2one(
        "res.users",
        string="Letzte Liefertermin-Nachfrage durch",
        readonly=True,
        copy=False,
    )

    @api.depends(
        "line_ids.expected_delivery_date",
        "line_ids.quantity_remaining",
        "line_ids.delivery_reminder_count",
        "state",
    )
    def _compute_overdue_delivery(self):
        for order in self:
            overdue = order.line_ids.filtered("delivery_is_overdue")
            order.overdue_line_ids = overdue
            order.overdue_line_count = len(overdue)
            order.maximum_delivery_overdue_days = max(
                overdue.mapped("delivery_overdue_days") or [0]
            )
            order.has_overdue_delivery = bool(overdue)

    @api.model
    def _search_has_overdue_delivery(self, operator, value):
        line_domain = self.env["sab.purchase.order.line"]._search_delivery_is_overdue(
            "=", True
        )
        order_ids = self.env["sab.purchase.order.line"].search(
            line_domain
        ).mapped("order_id").ids
        wants_overdue = bool(value)
        if operator in ("!=", "not in"):
            wants_overdue = not wants_overdue
        return [("id", "in" if wants_overdue else "not in", order_ids)]

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

        self.with_context(
            sab_overdue_line_ids=overdue_lines.ids
        ).message_post(
            body=_(
                "Liefertermin-Nachfrage zu %s über %s überfällige Position(en) "
                "an %s versendet."
            )
            % (self.name, len(overdue_lines), self.partner_id.email)
        )
        template.with_context(
            sab_overdue_line_ids=overdue_lines.ids
        ).send_mail(
            self.id,
            force_send=True,
            email_values={"email_to": self.partner_id.email},
        )
        now = fields.Datetime.now()
        overdue_lines.write(
            {
                "delivery_reminder_count": fields.first(
                    [line.delivery_reminder_count + 1 for line in overdue_lines]
                )
                if len(set(overdue_lines.mapped("delivery_reminder_count"))) == 1
                else 1,
                "delivery_reminder_sent_at": now,
                "delivery_reminder_sent_by_id": self.env.user.id,
            }
        )
        # Different positions may already have different reminder counters. Keep
        # each line's own history exact instead of flattening it.
        for line in overdue_lines:
            line.with_context(sab_delivery_reminder_write=True).write(
                {
                    "delivery_reminder_count": line.delivery_reminder_count
                    if line.delivery_reminder_sent_at == now
                    else line.delivery_reminder_count + 1,
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

    def action_send_overdue_delivery_reminder(self):
        for order in self:
            order._sab_send_overdue_delivery_reminder()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Liefertermin-Nachfrage versendet"),
                "message": _(
                    "Die überfälligen Positionen wurden je Bestellung "
                    "zusammengefasst an den Lieferanten gesendet."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_overdue_delivery_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Überfällige Lieferpositionen – %s") % self.name,
            "res_model": "sab.purchase.order.line",
            "view_mode": "list,form",
            "domain": [
                ("order_id", "=", self.id),
                ("delivery_is_overdue", "=", True),
            ],
            "target": "current",
        }

    @api.model
    def _cron_check_overdue_deliveries(self):
        overdue_lines = self.env["sab.purchase.order.line"].sudo().search(
            [
                ("delivery_is_overdue", "=", True),
            ]
        )
        overdue_orders = overdue_lines.mapped("order_id")
        purchasing_group = self.env.ref(
            "sab_project.group_sab_purchasing",
            raise_if_not_found=False,
        )
        users = (
            purchasing_group.user_ids.filtered("active")
            if purchasing_group
            else self.env["res.users"]
        )
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if not activity_type:
            return True
        model_id = self.env["ir.model"]._get_id(self._name)
        for order in overdue_orders:
            line_count = len(overdue_lines.filtered(lambda line: line.order_id == order))
            for user in users:
                existing = self.env["mail.activity"].sudo().search_count(
                    [
                        ("res_model_id", "=", model_id),
                        ("res_id", "=", order.id),
                        ("user_id", "=", user.id),
                        ("summary", "=", "Liefertermin überschritten"),
                    ]
                )
                if not existing:
                    self.env["mail.activity"].sudo().create(
                        {
                            "activity_type_id": activity_type.id,
                            "res_model_id": model_id,
                            "res_id": order.id,
                            "user_id": user.id,
                            "summary": "Liefertermin überschritten",
                            "note": (
                                f"Bestellung {order.name}: {line_count} offene "
                                "Position(en) haben den bestätigten Liefertermin überschritten."
                            ),
                        }
                    )

        stale = self.env["mail.activity"].sudo().search(
            [
                ("res_model_id", "=", model_id),
                ("summary", "=", "Liefertermin überschritten"),
                ("res_id", "not in", overdue_orders.ids or [0]),
            ]
        )
        if stale:
            stale.unlink()
        return True
