from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabProjectBomProcurementReleaseWithoutEmployeeGate(models.Model):
    _inherit = "sab.project.bom"

    def action_release_for_purchase(self):
        """Temporärer Freigabepfad ohne Mitarbeiter-/Bestellfreigeber-Zwang.

        Die Rollenprüfung wird später wieder aktiviert, sobald die Mitarbeiterprofile
        vollständig eingerichtet sind. Fachliche Prüfungen des Beschaffungspakets
        bleiben unverändert bestehen.
        """
        self.ensure_one()
        if getattr(self, "bom_scope", "total") != "procurement":
            return super().action_release_for_purchase()

        if self.state != "released":
            raise ValidationError(
                _("Das Beschaffungspaket muss technisch freigegeben sein.")
            )
        if not self.line_ids:
            raise ValidationError(
                _("Ein leeres Beschaffungspaket kann nicht freigegeben werden.")
            )

        # Bereits vorhandene Einkaufsnutzer erhalten weiterhin eine Aktivität.
        # Sind noch keine Mitarbeiterrollen eingerichtet, blockiert das die
        # Beschaffungsfreigabe vorübergehend nicht mehr.
        purchasing_group = self.env.ref(
            "sab_project.group_sab_purchasing",
            raise_if_not_found=False,
        )
        purchasing_users = (
            purchasing_group.user_ids.filtered("active")
            if purchasing_group
            else self.env["res.users"]
        )

        obsolete = self.env["sab.purchase.requirement"].sudo().search(
            [
                ("order_id", "=", self.order_id.id),
                ("bom_id", "!=", self.id),
                ("bom_id.bom_scope", "in", ("total", "cabinet")),
                ("state", "=", "open"),
                ("purchase_order_line_id", "=", False),
            ]
        )
        if obsolete:
            obsolete._release_project_reservation()
            obsolete.unlink()

        self.with_context(
            sab_procurement_release=True
        ).action_generate_purchase_requirements()
        requirements = self.purchase_requirement_ids.filtered(
            lambda requirement: not requirement.optional
            and requirement.state == "open"
        )
        requirements._reserve_available_stock()
        requirements._sab_prepare_order_quantities()

        self.write(
            {
                "purchase_release_state": "released",
                "purchase_released_at": fields.Datetime.now(),
                "purchase_released_by_id": self.env.user.id,
            }
        )

        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )
        if activity_type and purchasing_users:
            model_id = self.env["ir.model"]._get_id(self._name)
            for user in purchasing_users:
                existing = self.env["mail.activity"].search_count(
                    [
                        ("res_model_id", "=", model_id),
                        ("res_id", "=", self.id),
                        ("user_id", "=", user.id),
                        ("summary", "=", "Beschaffungspaket bearbeiten"),
                    ]
                )
                if not existing:
                    self.env["mail.activity"].create(
                        {
                            "activity_type_id": activity_type.id,
                            "res_model_id": model_id,
                            "res_id": self.id,
                            "user_id": user.id,
                            "summary": "Beschaffungspaket bearbeiten",
                            "note": (
                                f"{self.procurement_reference or self.name} wurde "
                                "zur Beschaffung freigegeben. Bitte Fehlbestände "
                                "prüfen und Bestellvorschläge erzeugen."
                            ),
                        }
                    )

        return self.action_open_procurement_workspace()
