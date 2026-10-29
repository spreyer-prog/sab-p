from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare


class PurchaseOrderLineSabSupplierConfirmation(models.Model):
    _inherit = "purchase.order.line"

    sab_ordered_quantity_snapshot = fields.Float(
        string="Freigegebene Bestellmenge",
        digits="Product Unit",
        readonly=True,
        copy=False,
    )
    sab_ordered_price_snapshot = fields.Float(
        string="Freigegebener EK je Einheit",
        digits="Product Price",
        readonly=True,
        copy=False,
    )
    sab_ordered_delivery_date_snapshot = fields.Date(
        string="Ursprünglicher Liefertermin",
        readonly=True,
        copy=False,
    )
    sab_supplier_confirmed_quantity = fields.Float(
        string="AB-Menge",
        digits="Product Unit",
        copy=False,
    )
    sab_supplier_confirmed_price = fields.Float(
        string="AB-EK je Einheit",
        digits="Product Price",
        copy=False,
    )
    sab_supplier_confirmed_delivery_date = fields.Date(
        string="AB-Liefertermin",
        copy=False,
    )
    sab_supplier_quantity_deviation = fields.Boolean(
        string="AB-Mengenabweichung",
        compute="_compute_sab_supplier_confirmation_deviation",
    )
    sab_supplier_price_deviation = fields.Boolean(
        string="AB-Preisabweichung",
        compute="_compute_sab_supplier_confirmation_deviation",
    )
    sab_supplier_delivery_deviation = fields.Boolean(
        string="AB-Terminabweichung",
        compute="_compute_sab_supplier_confirmation_deviation",
    )

    @api.depends(
        "sab_ordered_quantity_snapshot",
        "sab_ordered_price_snapshot",
        "sab_ordered_delivery_date_snapshot",
        "sab_supplier_confirmed_quantity",
        "sab_supplier_confirmed_price",
        "sab_supplier_confirmed_delivery_date",
        "product_uom_id",
        "order_id.currency_id",
    )
    def _compute_sab_supplier_confirmation_deviation(self):
        for line in self:
            quantity_reference = (
                line.sab_ordered_quantity_snapshot
                if line.sab_ordered_quantity_snapshot
                else line.product_qty
            )
            price_reference = (
                line.sab_ordered_price_snapshot
                if line.sab_ordered_price_snapshot
                else line.price_unit
            )
            date_reference = (
                line.sab_ordered_delivery_date_snapshot
                or (fields.Date.to_date(line.date_planned) if line.date_planned else False)
            )
            line.sab_supplier_quantity_deviation = bool(
                line.sab_supplier_confirmed_quantity
                and float_compare(
                    line.sab_supplier_confirmed_quantity,
                    quantity_reference or 0.0,
                    precision_rounding=line.product_uom_id.rounding,
                )
            )
            currency = line.order_id.currency_id or line.company_id.currency_id
            line.sab_supplier_price_deviation = bool(
                line.sab_supplier_confirmed_price
                and float_compare(
                    line.sab_supplier_confirmed_price,
                    price_reference or 0.0,
                    precision_rounding=currency.rounding,
                )
            )
            line.sab_supplier_delivery_deviation = bool(
                line.sab_supplier_confirmed_delivery_date
                and date_reference
                and line.sab_supplier_confirmed_delivery_date != date_reference
            )


class PurchaseOrderSabSupplierConfirmation(models.Model):
    _inherit = "purchase.order"

    sab_supplier_confirmation_number = fields.Char(
        string="Lieferanten-Auftragsbestätigung",
        copy=False,
        index=True,
    )
    sab_supplier_confirmation_date = fields.Date(
        string="Auftragsbestätigung vom",
        copy=False,
    )
    sab_supplier_confirmation_file = fields.Binary(
        string="Auftragsbestätigung",
        attachment=True,
        copy=False,
    )
    sab_supplier_confirmation_filename = fields.Char(
        string="Dateiname Auftragsbestätigung",
        copy=False,
    )
    sab_supplier_confirmation_state = fields.Selection(
        [
            ("none", "Nicht erfasst"),
            ("matched", "AB stimmt überein"),
            ("deviation", "AB mit Abweichung"),
            ("accepted", "AB-Abweichung freigegeben"),
        ],
        string="AB-Status",
        default="none",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )
    sab_supplier_confirmation_accepted_by_id = fields.Many2one(
        "res.users",
        string="AB freigegeben durch",
        readonly=True,
        copy=False,
    )
    sab_supplier_confirmation_accepted_at = fields.Datetime(
        string="AB freigegeben am",
        readonly=True,
        copy=False,
    )
    sab_supplier_confirmation_has_deviation = fields.Boolean(
        string="AB-Abweichung vorhanden",
        compute="_compute_sab_supplier_confirmation_summary",
    )

    @api.depends(
        "order_line.sab_supplier_quantity_deviation",
        "order_line.sab_supplier_price_deviation",
        "order_line.sab_supplier_delivery_deviation",
    )
    def _compute_sab_supplier_confirmation_summary(self):
        for order in self:
            lines = order.order_line.filtered(
                lambda line: line.sab_purchase_requirement_id and not line.display_type
            )
            order.sab_supplier_confirmation_has_deviation = any(
                line.sab_supplier_quantity_deviation
                or line.sab_supplier_price_deviation
                or line.sab_supplier_delivery_deviation
                for line in lines
            )

    def _sab_confirmation_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: line.sab_purchase_requirement_id and not line.display_type
        )

    def _sab_check_confirmation_editor(self):
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            return True
        raise AccessError(
            "Lieferanten-Auftragsbestätigungen dürfen nur durch den SAB-P Einkauf erfasst werden."
        )

    def _sab_snapshot_approved_order_values(self):
        for order in self.filtered("sab_is_suite_order"):
            for line in order._sab_confirmation_lines():
                values = {}
                if not line.sab_ordered_quantity_snapshot:
                    values["sab_ordered_quantity_snapshot"] = line.product_qty
                if not line.sab_ordered_price_snapshot:
                    values["sab_ordered_price_snapshot"] = line.price_unit
                if not line.sab_ordered_delivery_date_snapshot:
                    values["sab_ordered_delivery_date_snapshot"] = (
                        fields.Date.to_date(line.date_planned)
                        if line.date_planned
                        else False
                    )
                if values:
                    line.write(values)
        return True

    def button_approve(self, force=False):
        result = super().button_approve(force=force)
        self.filtered(lambda order: order.state == "purchase")._sab_snapshot_approved_order_values()
        return result

    def action_sab_record_supplier_confirmation(self):
        self._sab_check_confirmation_editor()
        for order in self:
            if not order.sab_is_suite_order or order.state != "purchase":
                raise ValidationError(
                    "Eine Lieferanten-Auftragsbestätigung kann erst zu einer freigegebenen SAB-P-Bestellung erfasst werden."
                )
            if not (order.sab_supplier_confirmation_number or "").strip():
                raise ValidationError("Bitte die Nummer der Lieferanten-Auftragsbestätigung eintragen.")
            if not order.sab_supplier_confirmation_date:
                raise ValidationError("Bitte das Datum der Lieferanten-Auftragsbestätigung eintragen.")

            order._sab_snapshot_approved_order_values()
            for line in order._sab_confirmation_lines():
                values = {}
                if not line.sab_supplier_confirmed_quantity:
                    values["sab_supplier_confirmed_quantity"] = line.product_qty
                if not line.sab_supplier_confirmed_price:
                    values["sab_supplier_confirmed_price"] = line.price_unit
                if not line.sab_supplier_confirmed_delivery_date:
                    values["sab_supplier_confirmed_delivery_date"] = (
                        fields.Date.to_date(line.date_planned)
                        if line.date_planned
                        else fields.Date.context_today(order)
                    )
                if values:
                    line.write(values)

            order.invalidate_recordset()
            if order.sab_supplier_confirmation_has_deviation:
                order.write(
                    {
                        "sab_supplier_confirmation_state": "deviation",
                        "sab_supplier_confirmation_accepted_by_id": False,
                        "sab_supplier_confirmation_accepted_at": False,
                    }
                )
                order.message_post(
                    body=_(
                        "Lieferanten-Auftragsbestätigung %s erfasst. Es bestehen Abweichungen zur freigegebenen Bestellung."
                    )
                    % order.sab_supplier_confirmation_number
                )
            else:
                for line in order._sab_confirmation_lines():
                    if line.sab_supplier_confirmed_delivery_date:
                        line.date_planned = fields.Datetime.to_datetime(
                            line.sab_supplier_confirmed_delivery_date
                        )
                order.write({"sab_supplier_confirmation_state": "matched"})
                order.message_post(
                    body=_("Lieferanten-Auftragsbestätigung %s ohne Abweichung erfasst.")
                    % order.sab_supplier_confirmation_number
                )
        return True

    def action_sab_accept_supplier_confirmation(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchase_approver")
        ):
            raise AccessError(
                "Abweichende Lieferanten-Auftragsbestätigungen dürfen nur durch die SAB-P Bestellfreigabe übernommen werden."
            )
        for order in self:
            if order.sab_supplier_confirmation_state != "deviation":
                raise ValidationError("Für diese Bestellung liegt keine freizugebende AB-Abweichung vor.")
            for line in order._sab_confirmation_lines():
                confirmed_qty = line.sab_supplier_confirmed_quantity or line.product_qty
                if float_compare(
                    confirmed_qty,
                    line.qty_received or 0.0,
                    precision_rounding=line.product_uom_id.rounding,
                ) < 0:
                    raise ValidationError(
                        _("Die bestätigte Menge für %s liegt unter der bereits gelieferten Menge.")
                        % line.product_id.display_name
                    )
                values = {
                    "product_qty": confirmed_qty,
                    "price_unit": line.sab_supplier_confirmed_price or line.price_unit,
                }
                if line.sab_supplier_confirmed_delivery_date:
                    values["date_planned"] = fields.Datetime.to_datetime(
                        line.sab_supplier_confirmed_delivery_date
                    )
                line.write(values)
            order.write(
                {
                    "sab_supplier_confirmation_state": "accepted",
                    "sab_supplier_confirmation_accepted_by_id": self.env.user.id,
                    "sab_supplier_confirmation_accepted_at": fields.Datetime.now(),
                }
            )
            order.message_post(
                body=_("Abweichende Auftragsbestätigung %s freigegeben und in die Bestellung übernommen durch %s.")
                % (
                    order.sab_supplier_confirmation_number,
                    self.env.user.display_name,
                )
            )
        return True
