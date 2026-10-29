from odoo import models
from odoo.exceptions import AccessError


class SabProjectBomOdooCommissioningSecurityFix(models.Model):
    _inherit = "sab.project.bom"

    def _sab_check_standard_commissioning_user(self):
        self.ensure_one()
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            return True
        raise AccessError(
            "Der tatsächliche Odoo-Lagerabgang darf nur durch einen im "
            "Mitarbeiterprofil freigeschalteten Lager- oder Einkaufsmitarbeiter "
            "gebucht werden."
        )
