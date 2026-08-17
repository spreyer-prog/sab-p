from odoo import api, fields, models


class SabCalculationItemLine(models.Model):
    _name = "sab.calculation.item.line"
    _description = "SAB-P Kalkulationszeile"
    _order = "sequence, id"

    calculation_item_id = fields.Many2one("sab.calculation.item", string="Kalkulationsartikel", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    position_type = fields.Selection([
        ("normal", "Normal"), ("alternative", "Alternative"), ("information", "Information"),
        ("heading", "Überschrift"), ("subtotal", "Zwischensumme")], string="Positionstyp", required=True, default="normal", index=True)
    product_id = fields.Many2one("sab.product", string="Standardprodukt", ondelete="restrict", index=True)
    alternative_product_ids = fields.Many2many("sab.product", relation="sab_calculation_line_alternative_product_rel", column1="calculation_line_id", column2="product_id", string="Alternativprodukte")
    quantity = fields.Float(string="Menge", required=True, default=1.0, digits=(16, 2))
    unit = fields.Selection([("pcs", "Stück"), ("m", "Meter"), ("kg", "kg"), ("min", "Minute"), ("h", "Stunde"), ("flat", "Pauschal")], string="Einheit", required=True, default="pcs")
    fixed_quantity = fields.Boolean(string="Festmenge", default=False)
    optional = fields.Boolean(string="Optional", default=False)
    note = fields.Char(string="Bemerkung")

    selected_supplier_product_id = fields.Many2one("sab.supplier.product", string="Verwendeter Lieferantenartikel", compute="_compute_purchase_values")
    unit_purchase_price = fields.Float(string="EK je Einheit", digits=(16, 2), compute="_compute_purchase_values")
    purchase_total = fields.Float(string="EK gesamt", digits=(16, 2), compute="_compute_purchase_values")

    @api.depends(
        "product_id", "quantity", "product_id.price_mode", "product_id.fixed_purchase_price",
        "product_id.component_ids.total_price", "product_id.supplier_product_ids.active",
        "product_id.supplier_product_ids.preferred", "product_id.supplier_product_ids.net_purchase_price")
    def _compute_purchase_values(self):
        for line in self:
            selected = False
            price = 0.0
            product = line.product_id
            if product:
                price = product.calculated_purchase_price or 0.0
                if product.price_mode == "supplier":
                    candidates = product.supplier_product_ids.filtered("active")
                    preferred = candidates.filtered("preferred")
                    pool = preferred or candidates
                    if pool:
                        selected = min(pool, key=lambda item: (item.net_purchase_price, item.id))
            line.selected_supplier_product_id = selected
            line.unit_purchase_price = price
            line.purchase_total = price * (line.quantity or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            calculation_item_id = vals.get("calculation_item_id")
            if calculation_item_id and not vals.get("sequence"):
                last_line = self.search([("calculation_item_id", "=", calculation_item_id)], order="sequence desc, id desc", limit=1)
                vals["sequence"] = last_line.sequence + 10 if last_line else 10
        return super().create(vals_list)
