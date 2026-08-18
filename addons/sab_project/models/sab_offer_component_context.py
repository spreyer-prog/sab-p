from odoo import models


class SabOfferCalculationLineComponentContext(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _sab_parent_section_from_values(self, vals):
        """Return the currently open Bauteil for a newly entered item.

        Odoo creates an editable-list row before the later normalization pass.
        Detecting the open Bauteil here prevents a child product from receiving
        a temporary own NTG number in the first place.
        """
        section = super()._sab_parent_section_from_values(vals)
        if section:
            return section

        order = self.env["sale.order"]
        order_id = vals.get("order_id")
        if order_id:
            order = self.env["sale.order"].browse(order_id).exists()
        elif len(self) == 1:
            order = self.order_id
        if not order:
            return self.env["sab.offer.calculation.line"]

        open_section = self.env["sab.offer.calculation.line"]
        for line in order.sab_calculation_line_ids.sorted(
            key=lambda item: (item.sequence, item.id)
        ):
            if line.line_type == "section":
                open_section = line
            elif line.line_type in ("section_end", "cabinet", "cabinet_end"):
                open_section = self.env["sab.offer.calculation.line"]
        return open_section
