from odoo import fields, models
from odoo.exceptions import AccessError, ValidationError


class PurchaseOrderSabMandatoryApproval(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        sab_orders = self.filtered(
            lambda order: order.sab_is_suite_order
            and order.state in ("draft", "sent")
        )
        regular_orders = self - sab_orders

        for order in sab_orders:
            error_message = order._confirmation_error_message()
            if error_message:
                raise ValidationError(error_message)
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            order.write({"state": "to approve"})
            order.message_post(
                body=(
                    "Die SAB-P-Bestellung wurde zur verbindlichen "
                    "Bestellfreigabe vorgelegt."
                )
            )

        result = True
        if regular_orders:
            result = super(
                PurchaseOrderSabMandatoryApproval,
                regular_orders,
            ).button_confirm()
        return result

    def button_approve(self, force=False):
        protected_orders = self.filtered("sab_is_suite_order")
        if protected_orders and not (
            self.env.is_superuser()
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "sab_project.group_sab_purchase_approver"
            )
        ):
            raise AccessError(
                "SAB-P-Bestellungen dürfen nur durch einen im Mitarbeiterprofil "
                "hinterlegten Bestellfreigeber oder einen Systemadministrator "
                "bestätigt werden."
            )
        result = super().button_approve(force=force)
        for order in protected_orders.filtered(
            lambda record: record.state == "purchase"
        ):
            order.message_post(
                body=(
                    "Bestellung freigegeben durch "
                    f"{self.env.user.display_name} am "
                    f"{fields.Datetime.to_string(fields.Datetime.now())}."
                )
            )
        return result

    def button_cancel(self):
        protected_orders = self.filtered("sab_is_suite_order")
        if protected_orders and not (
            self.env.is_superuser()
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "SAB-P-Bestellungen dürfen nur durch den Einkauf oder einen "
                "Systemadministrator storniert werden."
            )
        return super().button_cancel()

    def button_draft(self):
        if self.filtered("sab_is_suite_order"):
            raise ValidationError(
                "Eine stornierte SAB-P-Bestellung darf nicht wieder in den "
                "Entwurf gesetzt werden. Erzeugen Sie aus dem erneut offenen "
                "Materialbedarf einen neuen Bestellvorschlag."
            )
        return super().button_draft()
