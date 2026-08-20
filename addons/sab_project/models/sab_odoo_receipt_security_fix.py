from odoo import models
from odoo.exceptions import AccessError


class StockPickingSabReceiptSecurityFix(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        protected_pickings = self.filtered(
            lambda picking: picking.sab_is_suite_receipt
            and picking.state not in ("done", "cancel")
        )
        if protected_pickings and not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "SAB-P-Wareneingänge und Lieferantenrücksendungen dürfen nur "
                "durch einen im Mitarbeiterprofil freigeschalteten Lager- oder "
                "Einkaufsmitarbeiter gebucht werden."
            )
        return super().button_validate()
