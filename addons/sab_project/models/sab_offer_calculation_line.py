from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLine(models.Model):
    _name = "sab.offer.calculation.line"
    _description = "SAB-P Angebotskalkulationszeile"
    _order = "sequence, id"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Angebot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    group_id = fields.Many2one(
        comodel_name="sab.offer.calculation.group",
        string="Bauteil",
        ondelete="set null",
        index=True,
        domain="[('order_id', '=', order_id)]",
        help="Mehrere Kalkulationspositionen können zu einem Bauteil zusammengefasst werden. Im Angebot wird dann nur der Gruppenpreis des Bauteils gezeigt.",
    )
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    calculation_item_id = fields.Many2one(
        comodel_name="sab.calculation.item",
        string="Kalkulationsartikel",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(string="Menge", default=1.0, required=True, digits=(16, 3))
    description = fields.Text(string="Angebotstext")
    source_write_date = fields.Datetime(string="Kalkulationsstand übernommen am", readonly=True, copy=True)
    component_snapshot_ids = fields.One2many(
        comodel_name="sab.offer.calculation.component",
        inverse_name="offer_calculation_line_id",
        string="Komponenten-Snapshot",
        copy=True,
        readonly=True,
    )

    unit_material_purchase = fields.Monetary(string="Material-EK je Einheit", currency_field="currency_id", readonly=True, copy=True)
    unit_mechanical_minutes = fields.Float(string="Mechanik min je Einheit", readonly=True, copy=True)
    unit_wiring_minutes = fields.Float(string="Verdrahtung min je Einheit", readonly=True, copy=True)
    unit_testing_minutes = fields.Float(string="Prüfung min je Einheit", readonly=True, copy=True)
    unit_total_minutes = fields.Float(string="Gesamtzeit min je Einheit", readonly=True, copy=True)
    unit_space_units = fields.Float(string="Platzeinheiten je Einheit", readonly=True, copy=True)

    material_purchase_total = fields.Monetary(string="Material-EK", currency_field="currency_id", compute="_compute_totals", store=True)
    mechanical_time_minutes = fields.Float(string="Mechanik min", compute="_compute_totals", store=True)
    wiring_time_minutes = fields.Float(string="Verdrahtung min", compute="_compute_totals", store=True)
    testing_time_minutes = fields.Float(string="Prüfung min", compute="_compute_totals", store=True)
    total_time_minutes = fields.Float(string="Gesamtzeit min", compute="_compute_totals", store=True)
    total_hours = fields.Float(string="Gesamtstunden", compute="_compute_totals", store=True)
    space_units = fields.Float(string="Platzeinheiten", compute="_compute_totals", store=True)
    recommended_net_price = fields.Monetary(
        string="Verkaufspreis netto",
        currency_field="currency_id",
        compute="_compute_recommended_net_price",
        store=True,
        help="Kalkulatorischer Netto-Verkaufspreis dieser SAB-P Position einschließlich der im Angebot gespeicherten Faktoren.",
    )
    unit_recommended_net_price = fields.Monetary(
        string="VK je Einheit",
        currency_field="currency_id",
        compute="_compute_recommended_net_price",
        store=True,
    )
    currency_id = fields.Many2one(related="order_id.currency_id", string="Währung", readonly=True, store=True)
    note = fields.Char(string="Bemerkung")

    @staticmethod
    def _snapshot_values(item):
        return {
            "description": item.quotation_text or item.name,
            "source_write_date": item.write_date,
            "unit_material_purchase": item.purchase_total or 0.0,
            "unit_mechanical_minutes": item.mechanical_time_minutes or 0.0,
            "unit_wiring_minutes": item.wiring_time_minutes or 0.0,
            "unit_testing_minutes": item.testing_time_minutes or 0.0,
            "unit_total_minutes": item.total_time_minutes or 0.0,
            "unit_space_units": item.space_units or 0.0,
        }

    @staticmethod
    def _component_commands(item):
        commands = []
        for source_line in item.product_line_ids:
            if not source_line.product_id:
                continue
            if source_line.position_type in ("information", "heading", "subtotal"):
                continue
            commands.append((0, 0, {
                "sequence": source_line.sequence,
                "product_id": source_line.product_id.id,
                "quantity_per_unit": source_line.quantity or 0.0,
                "unit": source_line.unit,
                "fixed_quantity": source_line.fixed_quantity,
                "optional": source_line.optional,
                "source_calculation_line_id": source_line.id,
                "supplier_product_id": source_line.selected_supplier_product_id.id or False,
                "unit_purchase_price": source_line.unit_purchase_price or 0.0,
                "note": source_line.note,
            }))
        return commands

    @api.depends("quantity", "unit_material_purchase", "unit_mechanical_minutes", "unit_wiring_minutes", "unit_testing_minutes", "unit_total_minutes", "unit_space_units")
    def _compute_totals(self):
        for record in self:
            qty = record.quantity or 0.0
            record.material_purchase_total = record.unit_material_purchase * qty
            record.mechanical_time_minutes = record.unit_mechanical_minutes * qty
            record.wiring_time_minutes = record.unit_wiring_minutes * qty
            record.testing_time_minutes = record.unit_testing_minutes * qty
            record.total_time_minutes = record.unit_total_minutes * qty
            record.total_hours = record.total_time_minutes / 60.0
            record.space_units = record.unit_space_units * qty

    @api.depends(
        "material_purchase_total", "total_hours",
        "order_id.sab_material_factor", "order_id.sab_aux_material_factor",
        "order_id.sab_hourly_rate", "order_id.sab_time_factor", "order_id.sab_difficulty_factor",
        "order_id.sab_packaging_factor", "order_id.sab_skonto_factor",
        "order_id.sab_margin_factor", "order_id.sab_rebate_factor",
        "quantity",
    )
    def _compute_recommended_net_price(self):
        for record in self:
            order = record.order_id
            material_cost = record.material_purchase_total * (order.sab_material_factor or 0.0) * (order.sab_aux_material_factor or 0.0)
            labor_cost = record.total_hours * (order.sab_hourly_rate or 0.0) * (order.sab_time_factor or 0.0) * (order.sab_difficulty_factor or 0.0)
            commercial_factor = (order.sab_packaging_factor or 0.0) * (order.sab_skonto_factor or 0.0) * (order.sab_margin_factor or 0.0) * (order.sab_rebate_factor or 0.0)
            total = (material_cost + labor_cost) * commercial_factor
            record.recommended_net_price = total
            record.unit_recommended_net_price = total / record.quantity if record.quantity else 0.0

    @api.onchange("calculation_item_id")
    def _onchange_calculation_item_id(self):
        for record in self:
            if record.calculation_item_id:
                for field_name, value in self._snapshot_values(record.calculation_item_id).items():
                    record[field_name] = value

    @api.constrains("quantity")
    def _check_quantity(self):
        for record in self:
            if record.quantity < 0:
                raise ValidationError("Die Menge einer Kalkulationsposition darf nicht negativ sein.")

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            order_id = vals.get("order_id")
            if order_id:
                order = self.env["sale.order"].browse(order_id)
                if order.state not in ("draft", "sent"):
                    raise ValidationError("Kalkulationspositionen dürfen nach Auftragsbestätigung nicht neu angelegt werden.")
            item_id = vals.get("calculation_item_id")
            if item_id:
                item = self.env["sab.calculation.item"].browse(item_id).exists()
                if item:
                    snapshot = self._snapshot_values(item)
                    for field_name, value in snapshot.items():
                        vals.setdefault(field_name, value)
                    vals.setdefault("component_snapshot_ids", self._component_commands(item))
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        for record in self:
            if record.order_id.state not in ("draft", "sent"):
                raise ValidationError("Kalkulationspositionen eines bestätigten Angebots sind gesperrt.")
        vals = dict(vals)
        if vals.get("calculation_item_id"):
            item = self.env["sab.calculation.item"].browse(vals["calculation_item_id"]).exists()
            if item:
                snapshot = self._snapshot_values(item)
                if "description" in vals:
                    snapshot.pop("description", None)
                snapshot.update(vals)
                snapshot["component_snapshot_ids"] = [(5, 0, 0)] + self._component_commands(item)
                vals = snapshot
        return super().write(vals)

    def action_refresh_from_calculation_item(self):
        for record in self:
            if record.order_id.state not in ("draft", "sent"):
                raise ValidationError("Ein bestätigtes Angebot darf nicht aus aktuellen Stammdaten neu berechnet werden.")
            if record.calculation_item_id:
                values = self._snapshot_values(record.calculation_item_id)
                values["component_snapshot_ids"] = [(5, 0, 0)] + self._component_commands(record.calculation_item_id)
                record.write(values)
        return True

    def unlink(self):
        for record in self:
            if record.order_id.state not in ("draft", "sent"):
                raise ValidationError("Kalkulationspositionen eines bestätigten Angebots sind gesperrt.")
        return super().unlink()
