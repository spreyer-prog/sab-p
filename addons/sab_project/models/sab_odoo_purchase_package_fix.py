from odoo import api, models
from odoo.exceptions import ValidationError


class SabProjectBomTotalReleasePackageFix(models.Model):
    _inherit = "sab.project.bom"

    @api.constrains(
        "bom_scope",
        "source_cabinet_bom_ids",
        "order_id",
        "project_id",
    )
    def _check_procurement_package_sources(self):
        """The released total BOM is the authoritative procurement release.

        Cabinet BOMs remain the technical allocation. They only have to be
        released separately when the user explicitly selected the individual
        review option in the procurement wizard.
        """
        for package in self.filtered(
            lambda record: getattr(record, "bom_scope", "total") == "procurement"
        ):
            if not package.source_cabinet_bom_ids:
                raise ValidationError(
                    "Ein Beschaffungspaket benötigt mindestens einen ausgewählten Schaltschrank."
                )
            invalid = package.source_cabinet_bom_ids.filtered(
                lambda cabinet: cabinet.bom_scope != "cabinet"
                or cabinet.order_id != package.order_id
                or cabinet.project_id != package.project_id
            )
            if invalid:
                raise ValidationError(
                    "Ein Beschaffungspaket darf ausschließlich Schaltschrank-"
                    "Stücklisten desselben Auftrags und Projekts enthalten."
                )
