from odoo import api, fields, models


class SabProduct(models.Model):
    _name = "sab.product"
    _description = "SAB-P Produkt"
    _order = "manufacturer_supplier_id, manufacturer_article_number, name"
    _rec_name = "name"

    active = fields.Boolean(string="Aktiv", default=True)
    odoo_product_id = fields.Many2one("product.product", string="Odoo-Produkt", copy=False, ondelete="set null", index=True)
    product_type = fields.Selection([
        ("material", "Material"), ("mechanical", "Mechanik"), ("wiring", "Verdrahtung"),
        ("testing", "Prüfung"), ("labeling", "Beschriftung"), ("documentation", "Dokumentation"),
        ("transport", "Transport"), ("packaging", "Verpackung"), ("other", "Sonstiges")],
        string="Produkttyp", required=True, default="material", index=True)
    name = fields.Char(string="Bezeichnung", required=True, index=True)
    manufacturer_supplier_id = fields.Many2one("sab.supplier", string="Hersteller", ondelete="restrict", index=True)
    manufacturer_id = fields.Many2one("sab.manufacturer", string="Hersteller (Altbestand)", ondelete="restrict", index=True)
    manufacturer_article_number = fields.Char(string="Herstellerartikelnummer", index=True)
    datanorm_number = fields.Char(string="DATANORM-Nummer", index=True)
    price_mode = fields.Selection([("supplier", "Lieferantenartikel"), ("fixed", "Fixpreis"), ("assembly", "Baugruppe")], string="Preisermittlung", required=True, default="supplier")
    fixed_purchase_price = fields.Float(string="Fixpreis EK", digits=(16, 2), default=0.0)
    component_ids = fields.One2many("sab.product.component", "product_id", string="Baugruppenpositionen", copy=True)
    calculated_purchase_price = fields.Float(string="Kalkulatorischer EK", digits=(16, 2), compute="_compute_calculated_purchase_price")
    supplier_product_ids = fields.One2many("sab.supplier.product", "product_id", string="Lieferantenartikel")
    stock_movement_ids = fields.One2many("sab.stock.movement", "product_id", string="Lagerbewegungen")
    stock_on_hand = fields.Float(string="Lagerbestand", digits=(16, 3), compute="_compute_stock_balances")
    stock_reserved = fields.Float(string="Reserviert", digits=(16, 3), compute="_compute_stock_balances")
    stock_available = fields.Float(string="Verfügbar", digits=(16, 3), compute="_compute_stock_balances")
    space_units = fields.Float(string="Platzeinheiten", default=0.0)
    mechanical_time_minutes = fields.Float(string="Mechanikzeit in Minuten", default=0.0)
    wiring_time_minutes = fields.Float(string="Verdrahtungszeit in Minuten", default=0.0)
    testing_time_minutes = fields.Float(string="Prüfzeit in Minuten", default=0.0)
    notes = fields.Text(string="Interne Hinweise")

    def init(self):
        """Altwerte nur migrieren, wenn die jeweiligen Tabellen bereits existieren."""
        cr = self.env.cr
        cr.execute("SELECT to_regclass('public.sab_product')")
        if not cr.fetchone()[0]:
            return
        cr.execute("SELECT to_regclass('public.product_product'), to_regclass('public.product_template')")
        pp_table, pt_table = cr.fetchone()
        if pp_table and pt_table:
            cr.execute("""
                UPDATE product_template pt
                   SET sab_product_type = COALESCE(sp.product_type, 'material'),
                       sab_manufacturer_supplier_id = sp.manufacturer_supplier_id,
                       sab_manufacturer_id = sp.manufacturer_id,
                       sab_manufacturer_article_number = sp.manufacturer_article_number,
                       sab_datanorm_number = sp.datanorm_number,
                       sab_price_mode = COALESCE(sp.price_mode, 'supplier'),
                       sab_fixed_purchase_price = COALESCE(sp.fixed_purchase_price, 0),
                       sab_space_units = COALESCE(sp.space_units, 0),
                       sab_mechanical_time_minutes = COALESCE(sp.mechanical_time_minutes, 0),
                       sab_wiring_time_minutes = COALESCE(sp.wiring_time_minutes, 0),
                       sab_testing_time_minutes = COALESCE(sp.testing_time_minutes, 0),
                       sab_notes = sp.notes
                  FROM sab_product sp
                  JOIN product_product pp ON pp.id = sp.odoo_product_id
                 WHERE pt.id = pp.product_tmpl_id
            """)
        cr.execute("SELECT to_regclass('public.sab_supplier_product')")
        if cr.fetchone()[0]:
            cr.execute("""
                UPDATE sab_supplier_product ssp
                   SET odoo_product_id = sp.odoo_product_id
                  FROM sab_product sp
                 WHERE ssp.product_id = sp.id
                   AND ssp.odoo_product_id IS NULL
                   AND sp.odoo_product_id IS NOT NULL
            """)
        cr.execute("SELECT to_regclass('public.sab_product_component')")
        if cr.fetchone()[0]:
            cr.execute("""
                UPDATE sab_product_component c
                   SET odoo_product_id = sp.odoo_product_id
                  FROM sab_product sp
                 WHERE c.product_id = sp.id
                   AND c.odoo_product_id IS NULL
                   AND sp.odoo_product_id IS NOT NULL
            """)

    @api.depends("price_mode", "fixed_purchase_price", "component_ids.total_price", "supplier_product_ids.active", "supplier_product_ids.preferred", "supplier_product_ids.net_purchase_price")
    def _compute_calculated_purchase_price(self):
        for product in self:
            if product.price_mode == "fixed": product.calculated_purchase_price = product.fixed_purchase_price or 0.0
            elif product.price_mode == "assembly": product.calculated_purchase_price = sum(product.component_ids.mapped("total_price"))
            else:
                candidates = product.supplier_product_ids.filtered("active"); preferred = candidates.filtered("preferred"); pool = preferred or candidates
                product.calculated_purchase_price = min(pool.mapped("net_purchase_price")) if pool else 0.0

    def _odoo_product_values(self):
        self.ensure_one()
        return {
            "name": self.name, "default_code": self.manufacturer_article_number or self.datanorm_number or False,
            "active": self.active, "sale_ok": True, "purchase_ok": True, "standard_price": self.calculated_purchase_price or 0.0, "type": "consu",
            "sab_product_type": self.product_type, "sab_manufacturer_supplier_id": self.manufacturer_supplier_id.id or False,
            "sab_manufacturer_id": self.manufacturer_id.id or False, "sab_manufacturer_article_number": self.manufacturer_article_number or False,
            "sab_datanorm_number": self.datanorm_number or False, "sab_price_mode": self.price_mode,
            "sab_fixed_purchase_price": self.fixed_purchase_price or 0.0, "sab_space_units": self.space_units or 0.0,
            "sab_mechanical_time_minutes": self.mechanical_time_minutes or 0.0, "sab_wiring_time_minutes": self.wiring_time_minutes or 0.0,
            "sab_testing_time_minutes": self.testing_time_minutes or 0.0, "sab_notes": self.notes or False,
        }

    def _sync_to_odoo_product(self):
        Product = self.env["product.product"].sudo()
        for record in self:
            vals = record._odoo_product_values(); target = record.odoo_product_id.sudo()
            if not target:
                code = vals.get("default_code"); target = Product.search([("default_code", "=", code)], limit=1) if code else Product.browse()
            if target: target.write(vals)
            else: target = Product.create(vals)
            if record.odoo_product_id != target: record.with_context(skip_odoo_product_sync=True).write({"odoo_product_id": target.id})
            record.supplier_product_ids.filtered(lambda r: not r.odoo_product_id).write({"odoo_product_id": target.id})
            record.component_ids.filtered(lambda r: not r.odoo_product_id).write({"odoo_product_id": target.id})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("skip_odoo_product_sync"): records._sync_to_odoo_product()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched = {"name", "manufacturer_supplier_id", "manufacturer_id", "manufacturer_article_number", "datanorm_number", "active", "product_type", "price_mode", "fixed_purchase_price", "space_units", "mechanical_time_minutes", "wiring_time_minutes", "testing_time_minutes", "notes"}
        if not self.env.context.get("skip_odoo_product_sync") and set(vals) & watched: self._sync_to_odoo_product()
        return result

    @api.depends("stock_movement_ids.movement_type", "stock_movement_ids.quantity")
    def _compute_stock_balances(self):
        for product in self:
            movements = product.stock_movement_ids
            receipts = sum(movements.filtered(lambda m: m.movement_type == "receipt").mapped("quantity")); issues = sum(movements.filtered(lambda m: m.movement_type == "issue").mapped("quantity"))
            reservations = sum(movements.filtered(lambda m: m.movement_type == "reserve").mapped("quantity")); releases = sum(movements.filtered(lambda m: m.movement_type == "release").mapped("quantity"))
            product.stock_on_hand = receipts - issues; product.stock_reserved = reservations - releases; product.stock_available = product.stock_on_hand - product.stock_reserved
