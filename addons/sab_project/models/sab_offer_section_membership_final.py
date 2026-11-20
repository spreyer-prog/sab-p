from odoo import models


class SabOfferSectionMembershipFinal(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _normalize_section_membership(self):
        for order in self.mapped("order_id"):
            cabinet = False
            section = False
            lines = order.sab_calculation_line_ids.sorted(
                key=lambda line: (line.sequence, line.id)
            )
            for line in lines:
                parent_cabinet_id = False
                parent_section_id = False

                if line.line_type == "cabinet":
                    cabinet = line
                    section = False
                elif line.line_type == "cabinet_end":
                    cabinet = False
                    section = False
                elif line.line_type == "section":
                    section = line
                    parent_cabinet_id = cabinet.id if cabinet else False
                elif line.line_type == "section_end":
                    parent_cabinet_id = cabinet.id if cabinet else False
                    section = False
                elif line.line_type == "item":
                    parent_cabinet_id = cabinet.id if cabinet else False
                    parent_section_id = section.id if section else False
                elif line.line_type == "info":
                    parent_cabinet_id = cabinet.id if cabinet else False

                values = {}
                if (line.parent_cabinet_id.id or False) != parent_cabinet_id:
                    values["parent_cabinet_id"] = parent_cabinet_id
                if (line.parent_section_id.id or False) != parent_section_id:
                    values["parent_section_id"] = parent_section_id
                if values:
                    # Die Hierarchie-Normalisierung ist eine rein technische
                    # Zuordnung. Sie darf auch beim Stücklistenaufbau eines
                    # bestätigten Auftrags laufen, ohne die festgeschriebenen
                    # Kalkulationswerte wieder editierbar zu machen.
                    line.with_context(
                        skip_section_normalize=True,
                        skip_sale_line_sync=True,
                        sab_offer_release_write=True,
                    ).write(values)

            lines._sab_sync_section_positions()
        return True
