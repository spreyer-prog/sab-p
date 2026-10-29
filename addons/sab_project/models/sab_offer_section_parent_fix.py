from odoo import models


class SabOfferSectionParentPreservation(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _prepare_source_values(self, vals):
        incoming = dict(vals)
        result = super()._prepare_source_values(vals)

        if len(self) == 1 and self.id and self.line_type == "section":
            # Die Struktur-Normalisierung muss parent_cabinet_id ausdrücklich
            # setzen dürfen. Bei normalen Änderungen einer bestehenden Section
            # darf die Zuordnung dagegen nicht durch die allgemeine Struktur-
            # Bereinigung gelöscht werden.
            if self.env.context.get("skip_section_normalize"):
                if "parent_cabinet_id" in incoming:
                    result["parent_cabinet_id"] = incoming["parent_cabinet_id"]
                if "parent_section_id" in incoming:
                    result["parent_section_id"] = incoming["parent_section_id"]
            elif "line_type" not in incoming and "order_id" not in incoming:
                result.pop("parent_cabinet_id", None)
                result.pop("parent_section_id", None)

        return result
