from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLine(models.Model):
    _name = "sab.offer.calculation.line"
    _description = "SAB-P Angebotskalkulationszeile"
    _order = "sequence, id"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    line_type = fields.Selection([("item", "Kalkulationsartikel / Produkt"), ("cabinet", "Schaltschrank"), ("cabinet_end", "Schaltschrank Ende"), ("section", "Bauteil"), ("section_end", "Bauteil Ende"), ("info", "Infofeld")], required=True, default="item", index=True)
    sequence = fields.Integer(default=10, index=True)
    parent_cabinet_id = fields.Many2one("sab.offer.calculation.line", string="Schaltschrank", ondelete="set null", index=True, domain="[('order_id','=',order_id),('line_type','=','cabinet')]")
    cabinet_child_line_ids = fields.One2many("sab.offer.calculation.line", "parent_cabinet_id")
    cabinet_total = fields.Monetary(string="Schaltschrank-Summe", currency_field="currency_id", compute="_compute_cabinet_total", store=True)
    parent_section_id = fields.Many2one("sab.offer.calculation.line", string="Bauteil", ondelete="set null", index=True, domain="[('order_id','=',order_id),('line_type','=','section')]")
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
            else:
                record.hierarchy_marker = ""

    @api.depends("child_line_ids.recommended_net_price", "child_line_ids.line_type", "quantity")
    def _compute_section_total(self):
        for r in self:
            if r.line_type == "section":
                unit_total = sum(
                    r.child_line_ids.filtered(lambda x: x.line_type == "item").mapped("recommended_net_price")
                )
                r.section_total = unit_total * (r.quantity or 0.0)
            else:
                r.section_total = 0.0

    @api.depends("cabinet_child_line_ids.recommended_net_price", "cabinet_child_line_ids.line_type")
    def _compute_cabinet_total(self):
        for r in self: r.cabinet_total = sum(r.cabinet_child_line_ids.filtered(lambda x: x.line_type == "item").mapped("recommended_net_price")) if r.line_type == "cabinet" else 0.0

    @staticmethod
    def _snapshot_values(item):
        return {"description": item.quotation_text or item.name, "source_write_date": item.write_date, "unit_material_purchase": item.purchase_total or 0.0, "unit_auxiliary_purchase": item.auxiliary_purchase_total or 0.0, "unit_mechanical_minutes": item.mechanical_time_minutes or 0.0, "unit_wiring_minutes": item.wiring_time_minutes or 0.0, "unit_testing_minutes": item.testing_time_minutes or 0.0, "unit_total_minutes": item.total_time_minutes or 0.0, "unit_space_units": item.space_units or 0.0}

    @staticmethod
    def _product_values(product):
        m=getattr(product,"sab_mechanical_time_minutes",0.0) or 0.0; w=getattr(product,"sab_wiring_time_minutes",0.0) or 0.0; t=getattr(product,"sab_testing_time_minutes",0.0) or 0.0
        return {"description":product.display_name,"source_write_date":product.write_date,"unit_material_purchase":getattr(product,"sab_calculated_purchase_price",0.0) or product.standard_price or 0.0,"unit_auxiliary_purchase":0.0,"unit_mechanical_minutes":m,"unit_wiring_minutes":w,"unit_testing_minutes":t,"unit_total_minutes":m+w+t,"unit_space_units":getattr(product,"sab_space_units",0.0) or 0.0}

    @staticmethod
    def _component_commands(item):
        result=[]
        for line in item.product_line_ids:
            if not (line.odoo_product_id or line.product_id) or line.position_type in ("information","heading","subtotal","alternative"): continue
            result.append((0,0,{"sequence":line.sequence,"product_id":line.product_id.id or False,"odoo_product_id":line.odoo_product_id.id or (line.product_id.odoo_product_id.id if line.product_id else False),"position_type":line.position_type,"quantity_per_unit":line.quantity or 0.0,"unit":line.unit,"fixed_quantity":line.fixed_quantity,"optional":line.optional,"source_calculation_line_id":line.id,"supplier_product_id":line.selected_supplier_product_id.id or False,"unit_purchase_price":line.unit_purchase_price or 0.0,"note":line.note}))
        return result

    @api.depends(
        "line_type",
        "quantity",
        "unit_material_purchase",
        "unit_auxiliary_purchase",
        "unit_mechanical_minutes",
        "unit_wiring_minutes",
        "unit_testing_minutes",
        "unit_total_minutes",
        "unit_space_units",
        "cabinet_child_line_ids.line_type",
        "cabinet_child_line_ids.space_units",
    )
    def _compute_totals(self):
        for r in self:
            if r.line_type == "item":
                q=r.quantity or 0.0; r.material_purchase_total=r.unit_material_purchase*q; r.auxiliary_purchase_total=r.unit_auxiliary_purchase*q; r.mechanical_time_minutes=r.unit_mechanical_minutes*q; r.wiring_time_minutes=r.unit_wiring_minutes*q; r.testing_time_minutes=r.unit_testing_minutes*q; r.total_time_minutes=r.unit_total_minutes*q; r.total_hours=r.total_time_minutes/60.0; r.space_units=r.unit_space_units*q
            else:
                r.material_purchase_total=r.auxiliary_purchase_total=r.mechanical_time_minutes=r.wiring_time_minutes=r.testing_time_minutes=r.total_time_minutes=r.total_hours=0.0
                r.space_units = (
                    sum(
                        r.cabinet_child_line_ids.filtered(
                            lambda line: line.line_type == "item"
                        ).mapped("space_units")
                    )
                    if r.line_type == "cabinet"
                    else 0.0
                )

    @api.depends("line_type","material_purchase_total","auxiliary_purchase_total","total_hours","quantity","order_id.sab_material_factor","order_id.sab_aux_material_factor","order_id.sab_hourly_rate","order_id.sab_time_factor","order_id.sab_difficulty_factor","order_id.sab_packaging_factor","order_id.sab_skonto_factor","order_id.sab_margin_factor","order_id.sab_rebate_factor")
    def _compute_price(self):
        for r in self:
            if r.line_type != "item": r.recommended_net_price=r.unit_recommended_net_price=0.0; continue
            o=r.order_id; material=r.material_purchase_total*(o.sab_material_factor or 0.0)+r.auxiliary_purchase_total*(o.sab_material_factor or 0.0)*(o.sab_aux_material_factor or 0.0); labor=r.total_hours*(o.sab_hourly_rate or 0.0)*(o.sab_time_factor or 0.0)*(o.sab_difficulty_factor or 0.0); factor=(o.sab_packaging_factor or 0.0)*(o.sab_skonto_factor or 0.0)*(o.sab_margin_factor or 0.0)*(o.sab_rebate_factor or 0.0); r.recommended_net_price=(material+labor)*factor; r.unit_recommended_net_price=r.recommended_net_price/r.quantity if r.quantity else 0.0

    @api.constrains("line_type","calculation_item_id","odoo_product_id","description","quantity")
    def _check_content(self):
        for r in self:
            if r.quantity < 0: raise ValidationError("Die Menge darf nicht negativ sein.")
            if r.line_type == "item" and not (r.calculation_item_id or r.odoo_product_id): raise ValidationError("Bitte einen Kalkulationsartikel oder ein Produkt auswählen.")
            if r.line_type in ("cabinet","section","info") and not (r.description or "").strip(): raise ValidationError("Schaltschrank, Bauteil bzw. Infofeld benötigt einen Text.")
