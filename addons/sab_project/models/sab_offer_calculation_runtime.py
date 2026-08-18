from odoo import api, models
from odoo.exceptions import ValidationError


class SabOfferCalculationRuntime(models.Model):
    _inherit = "sab.offer.calculation.line"

    def _normalize_section_membership(self):
        for order in self.mapped("order_id"):
            cabinet = section = False
            for line in order.sab_calculation_line_ids.sorted(key=lambda x: (x.sequence, x.id)):
                dc = ds = False
                if line.line_type == "cabinet": cabinet, section = line, False
                elif line.line_type == "cabinet_end": cabinet = section = False
                elif line.line_type == "section": section, dc = line, cabinet.id if cabinet else False
                elif line.line_type == "section_end": section, dc = False, cabinet.id if cabinet else False
                elif line.line_type == "item": dc, ds = (cabinet.id if cabinet else False), (section.id if section else False)
                elif line.line_type == "info": dc = cabinet.id if cabinet else False
                vals = {}
                if (line.parent_cabinet_id.id or False) != dc: vals["parent_cabinet_id"] = dc
                if (line.parent_section_id.id or False) != ds: vals["parent_section_id"] = ds
                if vals: line.with_context(skip_section_normalize=True).write(vals)
        return True

    def _prepare_source_values(self, vals):
        if vals.get("calculation_item_id"):
            item=self.env["sab.calculation.item"].browse(vals["calculation_item_id"]).exists(); vals.update({"line_type":"item","odoo_product_id":False})
            if item:
                for k,v in self._snapshot_values(item).items(): vals.setdefault(k,v)
                vals.setdefault("component_snapshot_ids", self._component_commands(item))
        elif vals.get("odoo_product_id"):
            product=self.env["product.product"].browse(vals["odoo_product_id"]).exists(); vals.update({"line_type":"item","calculation_item_id":False})
            if product:
                for k,v in self._product_values(product).items(): vals.setdefault(k,v)
        elif vals.get("line_type") in ("cabinet","cabinet_end","section","section_end","info"):
            vals.update({"calculation_item_id":False,"odoo_product_id":False,"parent_section_id":False,"parent_cabinet_id":False,"quantity":1.0,"component_snapshot_ids":[(5,0,0)]})
        return vals

    def _sync_customer_order_lines(self):
        SaleLine=self.env["sale.order.line"].sudo(); Product=self.env["product.product"].sudo(); Tax=self.env["account.tax"].sudo()
        for order in self.mapped("order_id"):
            if order.state not in ("draft","sent"): continue
            SaleLine.search([("order_id","=",order.id),("sab_generated_from_calculation","=",True)]).unlink()
            generic=Product.search([("default_code","=","SAB-CALC")],limit=1)
            if not generic: generic=Product.create({"name":"SAB-P Kalkulationsposition","default_code":"SAB-CALC","type":"service","sale_ok":True,"purchase_ok":False})
            tax=Tax.search([("type_tax_use","=","sale"),("amount","=",order.sab_vat_rate or 19.0),("company_id","=",order.company_id.id)],limit=1)
            for line in order.sab_calculation_line_ids.sorted(key=lambda x:(x.sequence,x.id)):
                vals=False
                if line.line_type=="cabinet": vals={"display_type":"line_section","name":line.description or "Schaltschrank","sequence":line.sequence}
                elif line.line_type=="section": vals={"product_id":generic.id,"name":line.description or "Bauteil","product_uom_qty":1.0,"price_unit":line.section_total,"sequence":line.sequence}
                elif line.line_type=="item" and not line.parent_section_id:
                    p=line.odoo_product_id or generic; vals={"product_id":p.id,"name":line.description or p.display_name,"product_uom_qty":line.quantity,"price_unit":line.unit_recommended_net_price,"sequence":line.sequence}
                elif line.line_type=="info": vals={"display_type":"line_note","name":line.description or "","sequence":line.sequence}
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
        result=super().unlink(); remaining=orders.mapped("sab_calculation_line_ids")
        if remaining: remaining._normalize_section_membership(); remaining._sync_customer_order_lines()
        else: self.env["sale.order.line"].sudo().search([("order_id","in",orders.ids),("sab_generated_from_calculation","=",True)]).unlink()
        return result
