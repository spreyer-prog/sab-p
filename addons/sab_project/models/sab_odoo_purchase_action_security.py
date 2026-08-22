from odoo import models
from odoo.exceptions import AccessError


class PurchaseOrderSabActionSecurity(models.Model):
    _inherit = "purchase.order"

    def _sab_check_purchase_action_user(self):
        protected_orders = self.filtered("sab_is_suite_order")
        if protected_orders and not (
            self.env.is_superuser()
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Diese Aktion einer SAB-P-Bestellung darf nur durch einen im "
                "Mitarbeiterprofil freigeschalteten Einkaufsmitarbeiter "
                "ausgeführt werden."
            )
        return True

    def action_rfq_send(self):
        self._sab_check_purchase_action_user()
        return super().action_rfq_send()

    def print_quotation(self):
        self._sab_check_purchase_action_user()
        return super().print_quotation()

    def action_acknowledge(self):
        self._sab_check_purchase_action_user()
        return super().action_acknowledge()

    def action_create_invoice(self):
        self._sab_check_purchase_action_user()
        return super().action_create_invoice()
