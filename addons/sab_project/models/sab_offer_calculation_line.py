from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLine(models.Model):
    _name = "sab.offer.calculation.line"
    _description = "SAB-P Angebotskalkulationszeile"
    _order = "sequence, id"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    line_type = fields.Selection([
        ("item", "Kalkulationsartikel / Produkt"),
        ("cabinet", "Schaltschrank"),
        ("cabinet_end", "Schaltschrank Ende"),
        ("section", "Bauteil"),
        ("section_end", "Bauteil Ende"),
        ("info", "Infofeld"),
    ], required=True, default="item", index=True)
    sequence = fields.Integer(default=10, index=True)
    parent_cabinet_id = fields.Many2one(
        "sab.offer.calculation.line", string="Schaltschrank", ondelete="set null", index=True,
        domain="[('order_id','=',order_id),('line_type','=','cabinet')]",
    )
    cabinet_child_line_ids = fields.One2many("sab.offer.calculation.line", "parent_cabinet_id")
    cabinet_total = fields.Monetary(string="Schaltschrank-Summe", currency_field="currency_id", compute="_compute_cabinet_total", store=True)
    parent_section_id = fields.Many2one(
        "sab.offer.calculation.line", string="Bauteil", ondelete="set null", index=True,
        domain="[('order_id','=',order_id),('line_type','=','section')]",
    )
    child_line_ids = fields.One2many("sab.offer.calculation.line", "parent_section_id")
    section_total = fields.Monetary(string="Gruppenpreis", currency_field="currency_id", compute="_compute_section_total", store=True)
    hierarchy_marker = fields.Char(compute="_compute_hierarchy_marker")
    group_id = fields.Many2one("sab.offer.calculation.group", string="Bauteil (Altbestand)", ondelete="set null")
    calculation_item_id = fields.Many2one("sab.calculation.item", string="Kalkulationsartikel", ondelete="restrict", index=True)
    odoo_product_id = fields.Many2one("product.product", string="Produkt", ondelete="restrict", index=True)
    quantity = fields.Float(default=1.0, required=True, digits=(16, 3))
    description = fields.Text(string="Angebotstext")
    lv_position = fields.Char(string="LV-Pos.", index=True)
    schematic_reference = fields.Char(string="Schaltplan", index=True)
    is_ntg = fields.Boolean(string="NTG")
    source_write_date = fields.Datetime(readonly=True, copy=True)
    component_snapshot_ids = fields.One2many("sab.offer.calculation.component", "offer_calculation_line_id", copy=True, readonly=True)
    unit_material_purchase = fields.Monetary(currency_field="currency_id", readonly=True, copy=True)
    unit_auxiliary_purchase = fields.Monetary(currency_field="currency_id", readonly=True, copy=True)
    unit_mechanical_minutes = fields.Float(readonly=True, copy=True)
    unit_wiring_minutes = fields.Float(readonly=True, copy=True)
    unit_testing_minutes = fields.Float(readonly=True, copy=True)
    unit_total_minutes = fields.Float(readonly=True, copy=True)
    unit_space_units = fields.Float(readonly=True, copy=True)
    material_purchase_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    auxiliary_purchase_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    mechanical_time_minutes = fields.Float(compute="_compute_totals", store=True)
    wiring_time_minutes = fields.Float(compute="_compute_totals", store=True)
    testing_time_minutes = fields.Float(compute="_compute_totals", store=True)
    total_time_minutes = fields.Float(compute="_compute_totals", store=True)
    total_hours = fields.Float(compute="_compute_totals", store=True)
    space_units = fields.Float(compute="_compute_totals", store=True)
    recommended_net_price = fields.Monetary(string="Verkaufspreis netto", currency_field="currency_id", compute="_compute_price", store=True)
    unit_recommended_net_price = fields.Monetary(string="VK je Einheit", currency_field="currency_id", compute="_compute_price", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", readonly=True, store=True)
    note = fields.Char(string="Bemerkung")

    @api.depends("parent_section_id", "parent_cabinet_id", "line_type")
    def _compute_hierarchy_marker(self):
        for record in self:
            if record.line_type == "section" and record.parent_cabinet_id:
                record.hierarchy_marker = "↳"
            elif record.line_type == "item" and record.parent_section_id:
                record.hierarchy_marker = "↳↳" if record.parent_cabinet_id else "↳"
            elif record.line_type == "item" and record.parent_cabinet_id:
                record.hierarchy_marker = "↳"
            else:
                record.hierarchy_marker = ""

    @api.depends("child_line_ids.recommended_net_price", "child_line_ids.line_type")
    def _compute_section_total(self):
        for record in self:
            record.section_total = sum(record.child_line_ids.filtered(lambda line: line.line_type == "item").mapped("recommended_net_price")) if record.line_type == "section" else 0.0

    @api.depends("cabinet_child_line_ids.recommended_net_price", "cabinet_child_line_ids.line_type")
    def _compute_cabinet_total(self):
        for record in self:
            record.cabinet_total = sum(record.cabinet_child_line_ids.filtered(lambda line: line.line_type == "item").mapped("recommended_net_price")) if record.line_type == "cabinet" else 0.0

    def _normalize_section_membership(self):
        for order in self.mapped("order_id"):
            current_cabinet = False
            current_section = False
            for line in order.sab_calculation_line_ids.sorted(key=lambda item: (item.sequence, item.id)):
                desired_cabinet = False
                desired_section = False
                if line.line_type == "cabinet":
                    current_cabinet = line
                    current_section = False
                elif line.line_type == "cabinet_end":
                    current_cabinet = False
                    current_section = False
                elif line.line_type == "section":
                    current_section = line
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                elif line.line_type == "section_end":
                    current_section = False
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                elif line.line_type == "item":
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                    desired_section = current_section.id if current_section else False
                elif line.line_type == "info":
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                values = {}
                if (line.parent_cabinet_id.id or False) != desired_cabinet:
                    values["parent_cabinet_id"] = desired_cabinet
                if (line.parent_section_id.id or False) != desired_section:
                    values["parent_section_id"] = desired_section
                if values:
                    line.with_context(skip_section_normalize=True).write(values)
        return True

    @staticmethod
    def _snapshot_values(item):
        return {
            "description": item.quotation_text or item.name,
            "source_write_date": item.write_date,
            "unit_material_purchase": item.purchase_total or 0.0,
            "unit_auxiliary_purchase": item.auxiliary_purchase_total or 0.0,
            "unit_mechanical_minutes": item.mechanical_time_minutes or 0.0,
            "unit_wiring_minutes": item.wiring_time_minutes or 0.0,
            "unit_testing_minutes": item.testing_time_minutes or 0.0,
            "unit_total_minutes": item.total_time_minutes or 0.0,
            "unit_space_units": item.space_units or 0.0,
        }

    @staticmethod
    def _product_values(product):
        return {
            "description": product.display_name,
            "source_write_date": product.write_date,
            "unit_material_purchase": getattr(product, "sab_calculated_purchase_price", 0.0) or product.standard_price or 0.0,
            "unit_auxiliary_purchase": 0.0,
            "unit_mechanical_minutes": getattr(product, "sab_mechanical_time_minutes", 0.0) or 0.0,
            "unit_wiring_minutes": getattr(product, "sab_wiring_time_minutes", 0.0) or 0.0,
            "unit_testing_minutes": getattr(product, "sab_testing_time_minutes", 0.0) or 0.0,
            "unit_total_minutes": (getattr(product, "sab_mechanical_time_minutes", 0.0) or 0.0) + (getattr(product, "sab_wiring_time_minutes", 0.0) or 0.0) + (getattr(product, "sab_testing_time_minutes", 0.0) or 0.0),
            "unit_space_units": getattr(product, "sab_space_units", 0.0) or 0.0,
        }

    @staticmethod
    def _component_commands(item):
        commands = []
        for line in item.product_line_ids:
            if not (line.odoo_product_id or line.product_id):
                continue
            if line.position_type in ("information", "heading", "subtotal", "alternative"):
                continue
            commands.append((0, 0, {
                "sequence": line.sequence,
                "product_id": line.product_id.id or False,
                "odoo_product_id": line.odoo_product_id.id or (line.product_id.odoo_product_id.id if line.product_id else False),
                "position_type": line.position_type,
                "quantity_per_unit": line.quantity or 0.0,
                "unit": line.unit,
                "fixed_quantity": line.fixed_quantity,
                "optional": line.optional,
                "source_calculation_line_id": line.id,
                "supplier_product_id": line.selected_supplier_product_id.id or False,
                "unit_purchase_price": line.unit_purchase_price or 0.0,
                "note": line.note,
            }))
        return commands

    @api.depends("line_type", "quantity", "unit_material_purchase", "unit_auxiliary_purchase", "unit_mechanical_minutes", "unit_wiring_minutes", "unit_testing_minutes", "unit_total_minutes", "unit_space_units")
    def _compute_totals(self):
        for record in self:
            if record.line_type != "item":
                record.material_purchase_total = record.auxiliary_purchase_total = record.mechanical_time_minutes = record.wiring_time_minutes = record.testing_time_minutes = record.total_time_minutes = record.total_hours = record.space_units = 0.0
            else:
                quantity = record.quantity or 0.0
                record.material_purchase_total = record.unit_material_purchase * quantity
                record.auxiliary_purchase_total = record.unit_auxiliary_purchase * quantity
                record.mechanical_time_minutes = record.unit_mechanical_minutes * quantity
                record.wiring_time_minutes = record.unit_wiring_minutes * quantity
                record.testing_time_minutes = record.unit_testing_minutes * quantity
                record.total_time_minutes = record.unit_total_minutes * quantity
                record.total_hours = record.total_time_minutes / 60.0
                record.space_units = record.unit_space_units * quantity

    @api.depends("line_type", "material_purchase_total", "auxiliary_purchase_total", "total_hours", "quantity", "order_id.sab_material_factor", "order_id.sab_aux_material_factor", "order_id.sab_hourly_rate", "order_id.sab_time_factor", "order_id.sab_difficulty_factor", "order_id.sab_packaging_factor", "order_id.sab_skonto_factor", "order_id.sab_margin_factor", "order_id.sab_rebate_factor")
    def _compute_price(self):
        for record in self:
            if record.line_type != "item":
                record.recommended_net_price = record.unit_recommended_net_price = 0.0
                continue
            order = record.order_id
            material = record.material_purchase_total * (order.sab_material_factor or 0.0) + record.auxiliary_purchase_total * (order.sab_material_factor or 0.0) * (order.sab_aux_material_factor or 0.0)
            labor = record.total_hours * (order.sab_hourly_rate or 0.0) * (order.sab_time_factor or 0.0) * (order.sab_difficulty_factor or 0.0)
            factor = (order.sab_packaging_factor or 0.0) * (order.sab_skonto_factor or 0.0) * (order.sab_margin_factor or 0.0) * (order.sab_rebate_factor or 0.0)
            record.recommended_net_price = (material + labor) * factor
            record.unit_recommended_net_price = record.recommended_net_price / record.quantity if record.quantity else 0.0

    def _prepare_source_values(self, vals):
        if vals.get("calculation_item_id"):
            item = self.env["sab.calculation.item"].browse(vals["calculation_item_id"]).exists()
            vals.update({"line_type": "item", "odoo_product_id": False})
            if item:
                for key, value in self._snapshot_values(item).items():
                    vals.setdefault(key, value)
                vals.setdefault("component_snapshot_ids", self._component_commands(item))
        elif vals.get("odoo_product_id"):
            product = self.env["product.product"].browse(vals["odoo_product_id"]).exists()
            vals.update({"line_type": "item", "calculation_item_id": False})
            if product:
                for key, value in self._product_values(product).items():
                    vals.setdefault(key, value)
        elif vals.get("line_type") in ("cabinet", "cabinet_end", "section", "section_end", "info"):
            vals.update({
                "calculation_item_id": False,
                "odoo_product_id": False,
                "parent_section_id": False,
                "parent_cabinet_id": False,
                "quantity": 1.0,
                "component_snapshot_ids": [(5, 0, 0)],
            })
        return vals

    @api.constrains("line_type", "calculation_item_id", "odoo_product_id", "description", "quantity")
    def _check_content(self):
        for record in self:
            if record.quantity < 0:
                raise ValidationError("Die Menge darf nicht negativ sein.")
            if record.line_type == "item" and not (record.calculation_item_id or record.odoo_product_id):
                raise ValidationError("Bitte einen Kalkulationsartikel oder ein Produkt auswählen.")
            if record.line_type in ("cabinet", "section", "info") and not (record.description or "").strip():
                raise ValidationError("Schaltschrank, Bauteil bzw. Infofeld benötigt einen Text.")

    def _sync_customer_order_lines(self):
        SaleLine = self.env["sale.order.line"].sudo()
        Product = self.env["product.product"].sudo()
        Tax = self.env["account.tax"].sudo()
        for order in self.mapped("order_id"):
            if order.state not in ("draft", "sent"):
                continue
            SaleLine.search([("order_id", "=", order.id), ("sab_generated_from_calculation", "=", True)]).unlink()
            generic = Product.search([("default_code", "=", "SAB-CALC")], limit=1)
            if not generic:
                generic = Product.create({"name": "SAB-P Kalkulationsposition", "default_code": "SAB-CALC", "type": "service", "sale_ok": True, "purchase_ok": False})
            tax = Tax.search([("type_tax_use", "=", "sale"), ("amount", "=", order.sab_vat_rate or 19.0), ("company