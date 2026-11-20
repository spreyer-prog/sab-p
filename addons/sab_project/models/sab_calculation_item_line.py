from odoo import api, fields, models


class SabCalculationItemLine(models.Model):
    _name = "sab.calculation.item.line"
    _description = "SAB-P Kalkulationszeile"
    _order = "sequence, id"

    calculation_item_id = fields.Many2one("sab.calculation.item", string="Kalkulationsartikel", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    position_type = fields.Selection([
        ("normal", "Normal"), ("auxiliary_material", "Hilfsmaterial"), ("alternative", "Alternative"),
        ("information", "Information"), ("heading", "Überschrift"), ("subtotal", "Zwischensumme"),
    ], string="Positionstyp", required=True, default="normal", index=True)

    odoo_product_id = fields.Many2one("product.product", string="Produkt", ondelete="restrict", index=True)
    alternative_odoo_product_ids = fields.Many2many(
        "product.product", relation="sab_calculation_line_alternative_odoo_product_rel",
        column1="calculation_line_id", column2="product_id", string="Alternativprodukte")
    product_id = fields.Many2one("sab.product", string="Standardprodukt (Altbestand)", ondelete="restrict", index=True)
    alternative_product_ids = fields.Many2many("sab.product", relation="sab_calculation_line_alternative_product_rel", column1="calculation_line_id", column2="product_id", string="Alternativprodukte (Altbestand)")

    quantity = fields.Float(string="Menge", required=True, default=1.0, digits=(16, 2))
    unit = fields.Selection([("pcs", "Stück"), ("m", "Meter"), ("kg", "kg"), ("min", "Minute"), ("h", "Stunde"), ("flat", "Pauschal")], string="Einheit", required=True, default="pcs")
    fixed_quantity = fields.Boolean(string="Festmenge", default=False)
    optional = fields.Boolean(string="Optional", default=False)
    note = fields.Char(string="Bemerkung")
    selected_supplier_product_id = fields.Many2one("sab.supplier.product", string="Verwendeter Lieferantenartikel", compute="_compute_purchase_values")
    unit_purchase_price = fields.Float(string="EK je Einheit", digits=(16, 2), compute="_compute_purchase_values")
    purchase_total = fields.Float(string="EK gesamt", digits=(16, 2), compute="_compute_purchase_values")

    def init(self):
        self.env.cr.execute("""
            UPDATE sab_calculation_item_line l
               SET odoo_product_id = p.odoo_product_id
              FROM sab_product p
             WHERE l.product_id = p.id
               AND l.odoo_product_id IS NULL
               AND p.odoo_product_id IS NOT NULL
        """)

    @api.depends(
        "odoo_product_id", "odoo_product_id.sab_price_mode", "odoo_product_id.sab_fixed_purchase_price",
        "odoo_product_id.sab_supplier_product_ids.active", "odoo_product_id.sab_supplier_product_ids.preferred",
        "odoo_product_id.sab_supplier_product_ids.net_purchase_price",
        "product_id", "product_id.price_mode", "product_id.fixed_purchase_price",
        "product_id.component_ids.total_price", "product_id.supplier_product_ids.active",
        "product_id.supplier_product_ids.preferred", "product_id.supplier_product_ids.net_purchase_price", "quantity")
    def _compute_purchase_values(self):
        for line in self:
            selected = False
            price = 0.0
            if line.odoo_product_id:
                product = line.odoo_product_id
                price = product.sab_calculated_purchase_price or product.standard_price or 0.0
                if product.sab_price_mode == "supplier":
                    candidates = product.sab_supplier_product_ids.filtered("active")
                    preferred = candidates.filtered("preferred")
                    pool = preferred or candidates
                    if pool:
                        selected = min(pool, key=lambda item: (item.net_purchase_price, item.id))
            elif line.product_id:
                product = line.product_id
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
            if not vals.get("odoo_product_id") and vals.get("product_id"):
                legacy = self.env["sab.product"].browse(vals["product_id"])
                if legacy.odoo_product_id:
                    vals["odoo_product_id"] = legacy.odoo_product_id.id
            calculation_item_id = vals.get("calculation_item_id")
            if calculation_item_id and not vals.get("sequence"):
                last_line = self.search([("calculation_item_id", "=", calculation_item_id)], order="sequence desc, id desc", limit=1)
                vals["sequence"] = last_line.sequence + 10 if last_line else 10
        return super().create(vals_list)
