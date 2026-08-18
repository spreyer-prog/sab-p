from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLine(models.Model):
    _name = "sab.offer.calculation.line"
    _description = "SAB-P Angebotskalkulationszeile"
    _order = "sequence, id"

    order_id = fields.Many2one("sale.order", string="Angebot", required=True, ondelete="cascade", index=True)
    line_type = fields.Selection([
        ("item", "Kalkulationsartikel / Produkt"),
        ("section", "Bauteil"),
        ("section_end", "Bauteil Ende"),
        ("info", "Infofeld"),
    ], string="Zeilentyp", required=True, default="item", index=True)
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    parent_section_id = fields.Many2one(
        "sab.offer.calculation.line", string="Bauteil", ondelete="set null", index=True,
        domain="[('order_id', '=', order_id), ('line_type', '=', 'section')]",
    )
    child_line_ids = fields.One2many("sab.offer.calculation.line", "parent_section_id", string="Enthaltene Positionen")
    section_total = fields.Monetary(string="Gruppenpreis", currency_field="currency_id", compute="_compute_section_total", store=True)
    hierarchy_marker = fields.Char(string="", compute="_compute_hierarchy_marker")

    group_id = fields.Many2one("sab.offer.calculation.group", string="Bauteil (Altbestand)", ondelete="set null", index=True)
    calculation_item_id = fields.Many2one("sab.calculation.item", string="Kalkulationsartikel", ondelete="restrict", index=True)
    odoo_product_id = fields.Many2one("product.product", string="Produkt", ondelete="restrict", index=True)
    quantity = fields.Float(string="Menge", default=1.0, required=True, digits=(16, 3))
    description = fields.Text(string="Angebotstext")
    lv_position = fields.Char(string="LV-Pos.", index=True, help="Originale Positionsnummer aus dem Leistungsverzeichnis.")
    schematic_reference = fields.Char(string="Schaltplan", index=True, help="Referenz/Position aus dem Schaltplan.")
    is_ntg = fields.Boolean(string="NTG", help="Nachtragsposition, die nicht aus dem ursprünglichen LV stammt.")
    source_write_date = fields.Datetime(string="Kalkulationsstand übernommen am", readonly=True, copy=True)
    component_snapshot_ids = fields.One2many("sab.offer.calculation.component", inverse_name="offer_calculation_line_id", string="Komponenten-Snapshot", copy=True, readonly=True)

    unit_material_purchase = fields.Monetary(string="Material-EK normal je Einheit", currency_field="currency_id", readonly=True, copy=True)
    unit_auxiliary_purchase = fields.Monetary(string="Hilfsmaterial-EK je Einheit", currency_field="currency_id", readonly=True, copy=True)
    unit_mechanical_minutes = fields.Float(string="Mechanik min je Einheit", readonly=True, copy=True)
    unit_wiring_minutes = fields.Float(string="Verdrahtung min je Einheit", readonly=True, copy=True)
    unit_testing_minutes = fields.Float(string="Prüfung min je Einheit", readonly=True, copy=True)
    unit_total_minutes = fields.Float(string="Gesamtzeit min je Einheit", readonly=True, copy=True)
    unit_space_units = fields.Float(string="Platzeinheiten je Einheit", readonly=True, copy=True)
    material_purchase_total = fields.Monetary(string="Material-EK normal", currency_field="currency_id", compute="_compute_totals", store=True)
    auxiliary_purchase_total = fields.Monetary(string="Hilfsmaterial-EK", currency_field="currency_id", compute="_compute_totals", store=True)
    mechanical_time_minutes = fields.Float(string="Mechanik min", compute="_compute_totals", store=True)
    wiring_time_minutes = fields.Float(string="Verdrahtung min", compute="_compute_totals", store=True)
    testing_time_minutes = fields.Float(string="Prüfung min", compute="_compute_totals", store=True)
    total_time_minutes = fields.Float(string="Gesamtzeit min", compute="_compute_totals", store=True)
    total_hours = fields.Float(string="Gesamtstunden", compute="_compute_totals", store=True)
    space_units = fields.Float(string="Platzeinheiten", compute="_compute_totals", store=True)
    recommended_net_price = fields.Monetary(string="Verkaufspreis netto", currency_field="currency_id", compute="_compute_recommended_net_price", store=True)
    unit_recommended_net_price = fields.Monetary(string="VK je Einheit", currency_field="currency_id", compute="_compute_recommended_net_price", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", string="Währung", readonly=True, store=True)
    note = fields.Char(string="Bemerkung")

    @api.depends("parent_section_id", "line_type")
    def _compute_hierarchy_marker(self):
        for record in self:
            record.hierarchy_marker = "↳" if record.line_type == "item" and record.parent_section_id else ""

    @api.depends("child_line_ids.recommended_net_price", "child_line_ids.line_type")
    def _compute_section_total(self):
        for record in self:
            record.section_total = sum(record.child_line_ids.filtered(lambda line: line.line_type == "item").mapped("recommended_net_price")) if record.line_type == "section" else 0.0

    def _normalize_section_membership(self):
        orders = self.mapped("order_id")
        for order in orders:
            current_section = False
            for line in order.sab_calculation_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
                if line.line_type == "section":
                    current_section = line
                    desired = False
                elif line.line_type == "section_end":
                    current_section = False
                    desired = False
                elif line.line_type == "item":
                    desired = current_section.id if current_section else False
                else:
                    desired = False
                if (line.parent_section_id.id or False) != desired:
                    line.with_context(skip_section_normalize=True).write({"parent_section_id": desired})
        return True

    @staticmethod
    def _snapshot_values(item):
        return {"description": item.quotation_text or item.name, "source_write_date": item.write_date, "unit_material_purchase": item.purchase_total or 0.0, "unit_auxiliary_purchase": item.auxiliary_purchase_total or 0.0, "unit_mechanical_minutes": item.mechanical_time_minutes or 0.0, "unit_wiring_minutes": item.wiring_time_minutes or 0.0, "unit_testing_minutes": item.testing_time_minutes or 0.0, "unit_total_minutes": item.total_time_minutes or 0.0, "unit_space_units": item.space_units or 0.0}

    @staticmethod
    def _product_snapshot_values(sab_product, odoo_product):
        if sab_product:
            return {"description": sab_product.name, "source_write_date": sab_product.write_date, "unit_material_purchase": sab_product.calculated_purchase_price or 0.0, "unit_auxiliary_purchase": 0.0, "unit_mechanical_minutes": sab_product.mechanical_time_minutes or 0.0, "unit_wiring_minutes": sab_product.wiring_time_minutes or 0.0, "unit_testing_minutes": sab_product.testing_time_minutes or 0.0, "unit_total_minutes": (sab_product.mechanical_time_minutes or 0.0) + (sab_product.wiring_time_minutes or 0.0) + (sab_product.testing_time_minutes or 0.0), "unit_space_units": sab_product.space_units or 0.0}
        return {"description": odoo_product.display_name, "source_write_date": odoo_product.write_date, "unit_material_purchase": odoo_product.standard_price or 0.0, "unit_auxiliary_purchase": 0.0, "unit_mechanical_minutes": getattr(odoo_product, "sab_mechanical_time_minutes", 0.0) or 0.0, "unit_wiring_minutes": getattr(odoo_product, "sab_wiring_time_minutes", 0.0) or 0.0, "unit_testing_minutes": getattr(odoo_product, "sab_testing_time_minutes", 0.0) or 0.0, "unit_total_minutes": (getattr(odoo_product, "sab_mechanical_time_minutes", 0.0) or 0.0) + (getattr(odoo_product, "sab_wiring_time_minutes", 0.0) or 0.0) + (getattr(odoo_product, "sab_testing_time_minutes", 0.0) or 0.0), "unit_space_units": getattr(odoo_product, "sab_space_units", 0.0) or 0.0}

    @staticmethod
    def _component_commands(item):
        commands = []
        for source_line in item.product_line_ids:
            if not source_line.product_id or source_line.position_type in ("information", "heading", "subtotal", "alternative"):
                continue
            commands.append((0, 0, {"sequence": source_line.sequence, "product_id": source_line.product_id.id, "quantity_per_unit": source_line.quantity or 0.0, "unit": source_line.unit, "fixed_quantity": source_line.fixed_quantity, "optional": source_line.optional, "source_calculation_line_id": source_line.id, "supplier_product_id": source_line.selected_supplier_product_id.id or False, "unit_purchase_price": source_line.unit_purchase_price or 0.0, "note": source_line.note}))
        return commands

    @staticmethod
    def _direct_product_component(sab_product):
        if not sab_product:
            return []
        supplier = sab_product.supplier_product_ids.filtered("preferred")[:1] or sab_product.supplier_product_ids.filtered("active")[:1]
        return [(0, 0, {"sequence": 10, "product_id": sab_product.id, "quantity_per_unit": 1.0, "unit": "pcs", "fixed_quantity": False, "optional": False, "supplier_product_id": supplier.id or False, "unit_purchase_price": sab_product.calculated_purchase_price or 0.0})]

    @api.depends("line_type", "quantity", "unit_material_purchase", "unit_auxiliary_purchase", "unit_mechanical_minutes", "unit_wiring_minutes", "unit_testing_minutes", "unit_total_minutes", "unit_space_units")
    def _compute_totals(self):
        for record in self:
            if record.line_type != "item":
                record.material_purchase_total = record.auxiliary_purchase_total = 0.0
                record.mechanical_time_minutes = record.wiring_time_minutes = record.testing_time_minutes = 0.0
                record.total_time_minutes = record.total_hours = record.space_units = 0.0
                continue
            qty = record.quantity or 0.0
            record.material_purchase_total = record.unit_material_purchase * qty
            record.auxiliary_purchase_total = record.unit_auxiliary_purchase * qty
            record.mechanical_time_minutes = record.unit_mechanical_minutes * qty
            record.wiring_time_minutes = record.unit_wiring_minutes * qty
            record.testing_time_minutes = record.unit_testing_minutes * qty
            record.total_time_minutes = record.unit_total_minutes * qty
            record.total_hours = record.total_time_minutes / 60.0
            record.space_units = record.unit_space_units * qty

    @api.depends("line_type", "material_purchase_total", "auxiliary_purchase_total", "total_hours", "order_id.sab_material_factor", "order_id.sab_aux_material_factor", "order_id.sab_hourly_rate", "order_id.sab_time_factor", "order_id.sab_difficulty_factor", "order_id.sab_packaging_factor", "order_id.sab_skonto_factor", "order_id.sab_margin_factor", "order_id.sab_rebate_factor", "quantity")
    def _compute_recommended_net_price(self):
        for record in self:
            if record.line_type != "item":
                record.recommended_net_price = record.unit_recommended_net_price = 0.0
                continue
            order = record.order_id
            normal_material_cost = record.material_purchase_total * (order.sab_material_factor or 0.0)
            auxiliary_material_cost = record.auxiliary_purchase_total * (order.sab_material_factor or 0.0) * (order.sab_aux_material_factor or 0.0)
            labor_cost = record.total_hours * (order.sab_hourly_rate or 0.0) * (order.sab_time_factor or 0.0) * (order.sab_difficulty_factor or 0.0)
            commercial_factor = (order.sab_packaging_factor or 0.0) * (order.sab_skonto_factor or 0.0) * (order.sab_margin_factor or 0.0) * (order.sab_rebate_factor or 0.0)
            total = (normal_material_cost + auxiliary_material_cost + labor_cost) * commercial_factor
            record.recommended_net_price = total
            record.unit_recommended_net_price = total / record.quantity if record.quantity else 0.0

    @api.onchange("calculation_item_id")
    def _onchange_calculation_item_id(self):
        for record in self:
            if record.calculation_item_id:
                record.line_type = "item"; record.odoo_product_id = False
                for field_name, value in self._snapshot_values(record.calculation_item_id).items(): record[field_name] = value

    @api.onchange("odoo_product_id")
    def _onchange_odoo_product_id(self):
        for record in self:
            if record.odoo_product_id:
                record.line_type = "item"; record.calculation_item_id = False
                sab_product = self.env["sab.product"].search([("odoo_product_id", "=", record.odoo_product_id.id)], limit=1)
                for field_name, value in self._product_snapshot_values(sab_product, record.odoo_product_id).items(): record[field_name] = value

    @api.constrains("line_type", "calculation_item_id", "odoo_product_id", "description", "quantity")
    def _check_line_content(self):
        for record in self:
            if record.quantity < 0: raise ValidationError("Die Menge einer Kalkulationsposition darf nicht negativ sein.")
            if record.line_type == "item" and not (record.calculation_item_id or record.odoo_product_id): raise ValidationError("Bitte einen Kalkulationsartikel oder ein Produkt auswählen.")
            if record.line_type in ("section", "info") and not (record.description or "").strip(): raise ValidationError("Bauteil