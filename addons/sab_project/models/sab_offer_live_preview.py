"""Populate scalar quote snapshots in the editor, without database writes.

The existing price computes and create/write pipeline remain authoritative.
Quantity/factor edits reuse the quote's frozen unit inputs, not live masters.
"""
from odoo import api, models


SNAPSHOT_NUMERIC_FIELDS = (
    "unit_material_purchase", "unit_auxiliary_purchase",
    "unit_mechanical_minutes", "unit_wiring_minutes", "unit_testing_minutes",
    "unit_total_minutes", "unit_space_units",
)


class SabOfferLineLivePreview(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _sab_preview_is_editable(self):
        self.ensure_one()
        order = self.order_id
        return not order or (
            order.state in (False, "draft", "sent")
            and order.sab_offer_release_state != "released"
        )

    def _sab_preview_source_snapshot(self):
        """Assign only form-cache values; never create BOM/order/LV records."""
        self.ensure_one()
        if not self._sab_preview_is_editable():
            return
        if self.line_type not in (False, "item"):
            # Cabinet products are references, not priced item rows.
            self.update(dict.fromkeys(SNAPSHOT_NUMERIC_FIELDS, 0.0))
            self.source_write_date = False
            return

        origin = self._origin
        if not (self.calculation_item_id or self.odoo_product_id):
            values = dict.fromkeys(SNAPSHOT_NUMERIC_FIELDS, 0.0)
            values.update(source_write_date=False, description=False)
        elif (
            origin
            and origin.line_type == "item"
            and self.calculation_item_id == origin.calculation_item_id
            and self.odoo_product_id == origin.odoo_product_id
        ):
            # Re-selecting the original article must not reprice an old snapshot
            # from subsequently changed master data.
            values = {name: origin[name] for name in SNAPSHOT_NUMERIC_FIELDS}
            values.update(
                source_write_date=origin.source_write_date,
                description=origin.description,
            )
        elif self.calculation_item_id:
            values = self._snapshot_values(self.calculation_item_id)
        else:
            values = self._product_values(self.odoo_product_id)
        self.update(values)
        # Normal dependency recomputation provides the amounts; no second
        # calculator or hardcoded hourly rate is introduced here.

    @api.onchange("calculation_item_id")
    def _onchange_sab_preview_calculation_item(self):
        for line in self:
            if not line._sab_preview_is_editable():
                continue
            if line.line_type not in (False, "item"):
                line._sab_preview_source_snapshot()
                continue
            if line.calculation_item_id:
                line.odoo_product_id = False
            line._sab_preview_source_snapshot()

    @api.onchange("odoo_product_id")
    def _onchange_sab_preview_product(self):
        for line in self:
            if not line._sab_preview_is_editable():
                continue
            if line.line_type not in (False, "item"):
                line._sab_preview_source_snapshot()
                continue
            if line.odoo_product_id:
                line.calculation_item_id = False
            line._sab_preview_source_snapshot()

    @api.onchange("line_type")
    def _onchange_sab_preview_line_type(self):
        for line in self:
            if line.line_type not in (False, "item"):
                line._sab_preview_source_snapshot()
