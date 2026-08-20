from odoo import models


class SabOfferSectionParentPreservation(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _prepare_source_values(self, vals):
        incoming = dict(vals)
        result = super()._prepare_source_values(vals)

        if len(self) == 1 and self.id and self.line_type == "section":
            # Bei normalen Änderungen an einer bestehenden Bauteil-/Section-Zeile
            # darf die durch die Struktur bestimmte Schrankzuordnung nicht
            # gelöscht werden. Nur ein echter Strukturwechsel darf sie neu setzen.
            if "line_type" not in incoming and "order_id" not in incoming:
                result.pop("parent_cabinet_id", None)
                result.pop("parent_section_id", None)

        return result
