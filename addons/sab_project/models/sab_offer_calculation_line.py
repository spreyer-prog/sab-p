from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLine(models.Model):
    _name = "sab.offer.calculation.line"
    _description = "SAB-P Angebotskalkulationszeile"
    _order = "sequence, id"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    line_type = fields.Selection([("item", "Kalkulationsartikel / Produkt"), ("section", "Bauteil"), ("section_end", "Bauteil Ende"), ("info", "Infofeld")], required=True, default="item", index=True)
    sequence = fields.Integer(default=10, index=True)
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
    unit_mechanical_minutes = fields.Float(readonly=True, copy=True); unit_wiring_minutes = fields.Float(readonly=True, copy=True); unit_testing_minutes = fields.Float(readonly=True, copy=True); unit_total_minutes = fields.Float(readonly=True, copy=True); unit_space_units = fields.Float(readonly=True, copy=True)
    material_purchase_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True); auxiliary_purchase_total = fields.Monetary(currency_field="currency_id", compute="_compute_totals", store=True)
    mechanical_time_minutes = fields.Float(compute="_compute_totals", store=True); wiring_time_minutes = fields.Float(compute="_compute_totals", store=True); testing_time_minutes = fields.Float(compute="_compute_totals", store=True); total_time_minutes = fields.Float(compute="_compute_totals", store=True); total_hours = fields.Float(compute="_compute_totals", store=True); space_units = fields.Float(compute="_compute_totals", store=True)
    recommended_net_price = fields.Monetary(string="Verkaufspreis netto", currency_field="currency_id", compute="_compute_price", store=True); unit_recommended_net_price = fields.Monetary(string="VK je Einheit", currency_field="currency_id", compute="_compute_price", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", readonly=True, store=True)
    note = fields.Char(string="Bemerkung")

    @api.depends("parent_section_id", "line_type")
    def _compute_hierarchy_marker(self):
        for r in self: r.hierarchy_marker = "↳" if r.line_type == "item" and r.parent_section_id else ""

    @api.depends("child_line_ids.recommended_net_price", "child_line_ids.line_type")
    def _compute_section_total(self):
        for r in self: r.section_total = sum(r.child_line_ids.filtered(lambda x: x.line_type == "item").mapped("recommended_net_price")) if r.line_type == "section" else 0.0

    def _normalize_section_membership(self):
        for order in self.mapped("order_id"):
            current = False
            for line in order.sab_calculation_line_ids.sorted(key=lambda x: (x.sequence, x.id)):
                if line.line_type == "section": current, desired = line, False
                elif line.line_type == "section_end": current, desired = False, False
                elif line.line_type == "item": desired = current.id if current else False
                else: desired = False
                if (line.parent_section_id.id or False) != desired:
                    line.with_context(skip_section_normalize=True).write({"parent_section_id": desired})
        return True

    @staticmethod
    def _snapshot_values(item):
        return {"description": item.quotation_text or item.name, "source_write_date": item.write_date, "unit_material_purchase": item.purchase_total or 0.0, "unit_auxiliary_purchase": item.auxiliary_purchase_total or 0.0, "unit_mechanical_minutes": item.mechanical_time_minutes or 0.0, "unit_wiring_minutes": item.wiring_time_minutes or 0.0, "unit_testing_minutes": item.testing_time_minutes or 0.0, "unit_total_minutes": item.total_time_minutes or 0.0, "unit_space_units": item.space_units or 0.0}

    @staticmethod
    def _product_values(product):
        return {"description": product.display_name, "source_write_date": product.write_date, "unit_material_purchase": getattr(product, "sab_calculated_purchase_price", 0.0) or product.standard_price or 0.0, "unit_auxiliary_purchase": 0.0, "unit_mechanical_minutes": getattr(product, "sab_mechanical_time_minutes", 0.0) or 0.0, "unit_wiring_minutes": getattr(product, "sab_wiring_time_minutes", 0.0) or 0.0, "unit_testing_minutes": getattr(product, "sab_testing_time_minutes", 0.0) or 0.0, "unit_total_minutes": (getattr(product, "sab_mechanical_time_minutes", 0.0) or 0.0) + (getattr(product, "sab_wiring_time_minutes", 0.0) or 0.0) + (getattr(product, "sab_testing_time_minutes", 0.0) or 0.0), "unit_space_units": getattr(product, "sab_space_units", 0.0) or 0.0}

    @staticmethod
    def _component_commands(item):
        return [(0, 0, {"sequence": l.sequence, "product_id": l.product_id.id, "quantity_per_unit": l.quantity or 0.0, "unit": l.unit, "fixed_quantity": l.fixed_quantity, "optional": l.optional, "source_calculation_line_id": l.id, "supplier_product_id": l.selected_supplier_product_id.id or False, "unit_purchase_price": l.unit_purchase_price or 0.0, "note": l.note}) for l in item.product_line_ids if l.product_id and l.position_type not in ("information", "heading", "subtotal", "alternative")]

    @api.depends("line_type", "quantity", "unit_material_purchase", "unit_auxiliary_purchase", "unit_mechanical_minutes", "unit_wiring_minutes", "unit_testing_minutes", "unit_total_minutes", "unit_space_units")
    def _compute_totals(self):
        for r in self:
            if r.line_type != "item":
                r.material_purchase_total = r.auxiliary_purchase_total = r.mechanical_time_minutes = r.wiring_time_minutes = r.testing_time_minutes = r.total_time_minutes = r.total_hours = r.space_units = 0.0
            else:
                q = r.quantity or 0.0; r.material_purchase_total = r.unit_material_purchase*q; r.auxiliary_purchase_total = r.unit_auxiliary_purchase*q; r.mechanical_time_minutes = r.unit_mechanical_minutes*q; r.wiring_time_minutes = r.unit_wiring_minutes*q; r.testing_time_minutes = r.unit_testing_minutes*q; r.total_time_minutes = r.unit_total_minutes*q; r.total_hours = r.total_time_minutes/60.0; r.space_units = r.unit_space_units*q

    @api.depends("line_type", "material_purchase_total", "auxiliary_purchase_total", "total_hours", "quantity", "order_id.sab_material_factor", "order_id.sab_aux_material_factor", "order_id.sab_hourly_rate", "order_id.sab_time_factor", "order_id.sab_difficulty_factor", "order_id.sab_packaging_factor", "order_id.sab_skonto_factor", "order_id.sab_margin_factor", "order_id.sab_rebate_factor")
    def _compute_price(self):
        for r in self:
            if r.line_type != "item": r.recommended_net_price = r.unit_recommended_net_price = 0.0; continue
            o = r.order_id; material = r.material_purchase_total*(o.sab_material_factor or 0.0) + r.auxiliary_purchase_total*(o.sab_material_factor or 0.0)*(o.sab_aux_material_factor or 0.0); labor = r.total_hours*(o.sab_hourly_rate or 0.0)*(o.sab_time_factor or 0.0)*(o.sab_difficulty_factor or 0.0); factor = (o.sab_packaging_factor or 0.0)*(o.sab_skonto_factor or 0.0)*(o.sab_margin_factor or 0.0)*(o.sab_rebate_factor or 0.0); r.recommended_net_price = (material+labor)*factor; r.unit_recommended_net_price = r.recommended_net_price/r.quantity if r.quantity else 0.0

    def _prepare_source_values(self, vals):
        if vals.get("calculation_item_id"):
            item = self.env["sab.calculation.item"].browse(vals["calculation_item_id"]).exists(); vals.update({"line_type": "item", "odoo_product_id": False})
            if item:
                for k,v in self._snapshot_values(item).items(): vals.setdefault(k,v)
                vals.setdefault("component_snapshot_ids", self._component_commands(item))
        elif vals.get("odoo_product_id"):
            product = self.env["product.product"].browse(vals["odoo_product_id"]).exists(); vals.update({"line_type": "item", "calculation_item_id": False})
            if product:
                for k,v in self._product_values(product).items(): vals.setdefault(k,v)
        elif vals.get("line_type") in ("section", "section_end", "info"):
            vals.update({"calculation_item_id": False, "odoo_product_id": False, "parent_section_id": False, "quantity": 1.0, "component_snapshot_ids": [(5,0,0)]})
        return vals

    @api.constrains("line_type", "calculation_item_id", "odoo_product_id", "description", "quantity")
    def _check_content(self):
        for r in self:
            if r.quantity < 0: raise ValidationError("Die Menge darf nicht negativ sein.")
            if r.line_type == "item" and not (r.calculation_item_id or r.odoo_product_id): raise ValidationError("Bitte einen Kalkulationsartikel oder ein Produkt auswählen.")
            if r.line_type in ("section", "info") and not (r.description or "").strip(): raise ValidationError("Bauteil bzw. Infofeld benötigt einen Text.")

    def _sync_customer_order_lines(self):
        SaleLine = self.env["sale.order.line"].sudo(); Product = self.env["product.product"].sudo(); Tax = self.env["account.tax"].sudo()
        for order in self.mapped("order_id"):
            if order.state not in ("draft", "sent"): continue
            SaleLine.search([("order_id","=",order.id),("sab_generated_from_calculation","=",True)]).unlink()
            generic = Product.search([("default_code","=","SAB-CALC")], limit=1)
            if not generic: generic = Product.create({"name":"SAB-P Kalkulationsposition", "default_code":"SAB-CALC", "type":"service", "sale_ok":True, "purchase_ok":False})
            tax = Tax.search([("type_tax_use","=","sale"),("amount","=",order.sab_vat_rate or 19.0),("company_id","=",order.company_id.id)], limit=1)
            for line in order.sab_calculation_line_ids.sorted(key=lambda x:(x.sequence,x.id)):
                vals = False
                if line.line_type == "section": vals = {"product_id":generic.id,"name":line.description or "Bauteil","product_uom_qty":1.0,"price_unit":line.section_total,"sequence":line.sequence}
                elif line.line_type == "item" and not line.parent_section_id:
                    p = line.odoo_product_id or generic; vals = {"product_id":p.id,"name":line.description or p.display_name,"product_uom_qty":line.quantity,"price_unit":line.unit_recommended_net_price,"sequence":line.sequence}
                elif line.line_type == "info": vals = {"display_type":"line_note","name":line.description or "","sequence":line.sequence}
                if vals:
                    vals.update({"order_id":order.id,"sab_generated_from_calculation":True,"sab_calculation_source_line_id":line.id})
                    if tax and not vals.get("display_type"): vals["tax_ids"]=[(6,0,tax.ids)]
                    SaleLine.create(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        prepared=[]
        for incoming in vals_list:
            vals=dict(incoming); oid=vals.get("order_id")
            if oid and self.env["sale.order"].browse(oid).state not in ("draft","sent"): raise ValidationError("Kalkulationspositionen dürfen nach Auftragsbestätigung nicht neu angelegt werden.")
            prepared.append(self._prepare_source_values(vals))
        records=super().create(prepared)
        if not self.env.context.get("skip_section_normalize"): records._normalize_section_membership()
        if not self.env.context.get("skip_sale_line_sync"): records._sync_customer_order_lines()
        return records

    def write(self, vals):
        for r in self:
            if r.order_id.state not in ("draft","sent"): raise ValidationError("Kalkulationspositionen eines bestätigten Angebots sind gesperrt.")
        result=super().write(self._prepare_source_values(dict(vals)))
        if not self.env.context.get("skip_section_normalize") and set(vals)&{"sequence","line_type","order_id"}: self._normalize_section_membership()
        if not self.env.context.get("skip_sale_line_sync"): self._sync_customer_order_lines()
        return result

    def action_refresh_from_calculation_item(self):
        for r in self.filtered(lambda x:x.line_type=="item" and x.calculation_item_id):
            if r.order_id.state not in ("draft","sent"): raise ValidationError("Ein bestätigtes Angebot darf nicht neu berechnet werden.")
            vals=self._snapshot_values(r.calculation_item_id); vals["component_snapshot_ids"]=[(5,0,0)]+self._component_commands(r.calculation_item_id); r.write(vals)
        return True

    def unlink(self):
        orders=self.mapped("order_id")
        for r in self:
            if r.order_id.state not in ("draft","sent"): raise ValidationError("Kalkulationspositionen eines bestätigten Angebots sind gesperrt.")
        result=super().unlink()
        remaining=orders.mapped("sab_calculation_line_ids")
        if remaining: remaining._normalize_section_membership(); remaining._sync_customer_order_lines()
        else: self.env["sale.order.line"].sudo().search([("order_id","in",orders.ids),("sab_generated_from_calculation","=",True)]).unlink()
        return