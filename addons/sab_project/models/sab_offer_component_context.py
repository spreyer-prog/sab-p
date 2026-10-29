from odoo import models


class SabOfferCalculationLineComponentContext(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _sab_parent_section_from_values(self, vals):
        """Return the currently open Bauteil for a newly entered item."""
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

    def _sab_apply_project_position(self, vals, order):
        """Attach a new row to its Bauteil before any LV/NTG mapping is created."""
        values = super()._sab_apply_project_position(vals, order)
        if values.get("line_type", "item") != "item":
            return values

        section = self._sab_parent_section_from_values(values)
        if not section:
            return values

        values["parent_section_id"] = section.id
        values["lv_position"] = section.lv_position or False
        values["is_ntg"] = bool(
            section.lv_position
            and (
                section.is_ntg
                or section.lv_position.upper().startswith("NTG")
            )
        )
        if section.parent_cabinet_id:
            values["parent_cabinet_id"] = section.parent_cabinet_id.id
        return values
