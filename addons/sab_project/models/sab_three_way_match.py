import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare


class AccountMoveSabThreeWayMatch(models.Model):
    _inherit = "account.move"

    sab_three_way_match_state = fields.Selection(
        [
            ("not_applicable", "Nicht relevant"),
            ("matched", "Bestellung / Wareneingang / Rechnung stimmen überein"),
            ("mismatch", "Abweichung vorhanden"),
        ],
        string="Drei-Wege-Abgleich",
        compute="_compute_sab_three_way_match",
    )
    sab_three_way_quantity_mismatch = fields.Boolean(
        string="Mengenabweichung",
        compute="_compute_sab_three_way_match",
    )
    sab_three_way_price_mismatch = fields.Boolean(
        string="Preisabweichung",
        compute="_compute_sab_three_way_match",
    )
    sab_three_way_tax_mismatch = fields.Boolean(
        string="Steuerabweichung",
        compute="_compute_sab_three_way_match",
    )
    sab_three_way_message = fields.Text(
        string="Prüfergebnis",
        compute="_compute_sab_three_way_match",
    )
    sab_three_way_override_approved = fields.Boolean(
        string="Abweichung freigegeben",
        readonly=True,
        copy=False,
        tracking=True,
    )
    sab_three_way_override_by_id = fields.Many2one(
        "res.users",
        string="Abweichung freigegeben durch",
        readonly=True,
        copy=False,
    )
    sab_three_way_override_at = fields.Datetime(
        string="Abweichung freigegeben am",
        readonly=True,
        copy=False,
    )
    sab_three_way_approved_fingerprint = fields.Char(
        string="Technischer Prüfstand",
        readonly=True,
        copy=False,
    )

    def _sab_three_way_purchase_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda line: line.purchase_line_id
            and line.purchase_line_id.order_id.sab_is_suite_order
        )

    def _sab_invoice_quantity_in_purchase_uom(self, invoice_line, purchase_line):
        invoice_uom = invoice_line.product_uom_id or purchase_line.product_uom_id
        return invoice_uom._compute_quantity(
            invoice_line.quantity,
            purchase_line.product_uom_id,
        )

    def _sab_invoice_net_unit_price_in_purchase_currency(
        self,
        invoice_line,
        purchase_line,
    ):
        invoice_net = (invoice_line.price_unit or 0.0) * (
            1.0 - (invoice_line.discount or 0.0) / 100.0
        )
        invoice_currency = self.currency_id or self.company_currency_id
        purchase_currency = (
            purchase_line.order_id.currency_id
            or purchase_line.order_id.company_id.currency_id
        )
        if invoice_currency == purchase_currency:
            return invoice_net
        conversion_date = (
            self.invoice_date
            or self.date
            or fields.Date.context_today(self)
        )
        return invoice_currency._convert(
            invoice_net,
            purchase_currency,
            self.company_id,
            conversion_date,
        )

    def _sab_three_way_details(self):
        self.ensure_one()
        details = []
        for invoice_line in self._sab_three_way_purchase_lines():
            purchase_line = invoice_line.purchase_line_id
            invoiced_qty = self._sab_invoice_quantity_in_purchase_uom(
                invoice_line,
                purchase_line,
            )
            received_qty = purchase_line.qty_received or 0.0
            ordered_qty = purchase_line.product_qty or 0.0
            uom_rounding = purchase_line.product_uom_id.rounding
            quantity_mismatch = (
                float_compare(
                    invoiced_qty,
                    received_qty,
                    precision_rounding=uom_rounding,
                ) > 0
                or float_compare(
                    invoiced_qty,
                    ordered_qty,
                    precision_rounding=uom_rounding,
                ) > 0
            )

            purchase_net = (purchase_line.price_unit or 0.0) * (
                1.0 - (purchase_line.discount or 0.0) / 100.0
            )
            invoice_net = self._sab_invoice_net_unit_price_in_purchase_currency(
                invoice_line,
                purchase_line,
            )
            currency = (
                purchase_line.order_id.currency_id
                or purchase_line.order_id.company_id.currency_id
            )
            price_mismatch = bool(
                float_compare(
                    invoice_net,
                    purchase_net,
                    precision_rounding=currency.rounding,
                )
            )
            tax_mismatch = set(invoice_line.tax_ids.ids) != set(
                purchase_line.tax_ids.ids
            )

            details.append(
                {
                    "invoice_line": invoice_line,
                    "purchase_line": purchase_line,
                    "invoiced_qty": invoiced_qty,
                    "received_qty": received_qty,
                    "ordered_qty": ordered_qty,
                    "invoice_net": invoice_net,
                    "purchase_net": purchase_net,
                    "quantity_mismatch": quantity_mismatch,
                    "price_mismatch": price_mismatch,
                    "tax_mismatch": tax_mismatch,
                }
            )
        return details

    def _sab_three_way_current_fingerprint(self):
        self.ensure_one()
        parts = []
        for detail in self._sab_three_way_details():
            invoice_line = detail["invoice_line"]
            purchase_line = detail["purchase_line"]
            parts.append(
                "|".join(
                    [
                        str(invoice_line.id),
                        str(purchase_line.id),
                        f"{detail['invoiced_qty']:.9f}",
                        f"{detail['received_qty']:.9f}",
                        f"{detail['ordered_qty']:.9f}",
                        f"{detail['invoice_net']:.9f}",
                        f"{detail['purchase_net']:.9f}",
                        ",".join(map(str, sorted(invoice_line.tax_ids.ids))),
                        ",".join(map(str, sorted(purchase_line.tax_ids.ids))),
                    ]
                )
            )
        payload = "\n".join(parts).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @api.depends(
        "move_type",
        "invoice_line_ids.quantity",
        "invoice_line_ids.price_unit",
        "invoice_line_ids.discount",
        "invoice_line_ids.tax_ids",
        "invoice_line_ids.purchase_line_id.product_qty",
        "invoice_line_ids.purchase_line_id.qty_received",
        "invoice_line_ids.purchase_line_id.price_unit",
        "invoice_line_ids.purchase_line_id.discount",
        "invoice_line_ids.purchase_line_id.tax_ids",
        "invoice_line_ids.purchase_line_id.order_id.sab_is_suite_order",
    )
    def _compute_sab_three_way_match(self):
        for move in self:
            move.sab_three_way_quantity_mismatch = False
            move.sab_three_way_price_mismatch = False
            move.sab_three_way_tax_mismatch = False
            move.sab_three_way_message = False

            if move.move_type not in ("in_invoice", "in_refund"):
                move.sab_three_way_match_state = "not_applicable"
                continue

            details = move._sab_three_way_details()
            if not details:
                move.sab_three_way_match_state = "not_applicable"
                continue

            messages = []
            for detail in details:
                line = detail["invoice_line"]
                purchase_line = detail["purchase_line"]
                label = purchase_line.product_id.display_name or purchase_line.name
                if detail["quantity_mismatch"]:
                    move.sab_three_way_quantity_mismatch = True
                    messages.append(
                        _(
                            "%s: Rechnung %.3f, Wareneingang %.3f, bestellt %.3f."
                        )
                        % (
                            label,
                            detail["invoiced_qty"],
                            detail["received_qty"],
                            detail["ordered_qty"],
                        )
                    )
                if detail["price_mismatch"]:
                    move.sab_three_way_price_mismatch = True
                    messages.append(
                        _("%s: Rechnungs-EK %.4f, Bestell-EK %.4f.")
                        % (
                            label,
                            detail["invoice_net"],
                            detail["purchase_net"],
                        )
                    )
                if detail["tax_mismatch"]:
                    move.sab_three_way_tax_mismatch = True
                    messages.append(
                        _("%s: Steuer der Rechnung weicht von der Bestellung ab.")
                        % label
                    )

            mismatch = bool(
                move.sab_three_way_quantity_mismatch
                or move.sab_three_way_price_mismatch
                or move.sab_three_way_tax_mismatch
            )
            move.sab_three_way_match_state = (
                "mismatch" if mismatch else "matched"
            )
            move.sab_three_way_message = "\n".join(messages) if messages else _(
                "Bestellmenge, Wareneingang, Netto-Einheitspreis und Steuer stimmen überein."
            )

    def action_sab_approve_three_way_deviation(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchase_approver")
            or self.env.user.has_group("account.group_account_manager")
        ):
            raise AccessError(
                "Abweichungen zwischen Bestellung, Wareneingang und Rechnung dürfen "
                "nur durch Bestellfreigabe oder Buchhaltungsleitung freigegeben werden."
            )
        for move in self:
            if move.sab_three_way_match_state != "mismatch":
                raise ValidationError(
                    "Für diese Eingangsrechnung liegt keine freizugebende Abweichung vor."
                )
            move.write(
                {
                    "sab_three_way_override_approved": True,
                    "sab_three_way_override_by_id": self.env.user.id,
                    "sab_three_way_override_at": fields.Datetime.now(),
                    "sab_three_way_approved_fingerprint": move._sab_three_way_current_fingerprint(),
                }
            )
            move.message_post(
                body=_(
                    "Drei-Wege-Abweichung freigegeben durch %s.\n%s"
                )
                % (self.env.user.display_name, move.sab_three_way_message or ""),
            )
        return True

    def action_post(self):
        for move in self:
            if (
                move.sab_is_suite_vendor_bill
                and move.move_type in ("in_invoice", "in_refund")
                and move.sab_three_way_match_state == "mismatch"
            ):
                fingerprint_ok = bool(
                    move.sab_three_way_override_approved
                    and move.sab_three_way_approved_fingerprint
                    == move._sab_three_way_current_fingerprint()
                )
                if not fingerprint_ok:
                    raise ValidationError(
                        "Die SAB-P Eingangsrechnung weicht von Bestellung bzw. "
                        "Wareneingang ab. Bitte die Abweichung prüfen und ausdrücklich "
                        "freigeben, bevor die Rechnung gebucht wird.\n\n%s"
                        % (move.sab_three_way_message or "")
                    )
        return super().action_post()
