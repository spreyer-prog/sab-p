from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabPurchaseRequirement(models.Model):
    _name = "sab.purchase.requirement"
    _description = "SAB-P Einkaufsbedarf"
    _order = "project_id, supplier_id, sequence, id"

    name = fields.Char(string="Bedarf", required=True, readonly=True, copy=False)
    bom_id = fields.Many2one(comodel_name="sab.project.bom", string="Stückliste", required=True, ondelete="cascade", index=True)
    bom_line_id = fields.Many2one(comodel_name="sab.project.bom.line", string="Stücklistenposition", required=True, ondelete="cascade", index=True)
    project_id = fields.Many2one(related="bom_id.project_id", string="Projekt", store=True, readonly=True)
    order_id = fields.Many2one(related="bom_id.order_id", string="Kundenauftrag", store=True, readonly=True)
    sequence = fields.Integer(string="Pos.", related="bom_line_id.sequence", store=True, readonly=True)
    product_id = fields.Many2one(related="bom_line_id.product_id", string="Produkt", store=True, readonly=True)
    quantity = fields.Float(string="Bedarfsmenge", required=True, digits=(16, 3), readonly=True)
    unit = fields.Selection(related="bom_line_id.unit", string="Einheit", store=True, readonly=True)
    optional = fields.Boolean(related="bom_line_id.optional", string="Optional", store=True, readonly=True)
    supplier_product_id = fields.Many2one(comodel_name="sab.supplier.product", string="Lieferantenartikel", readonly=True, ondelete="restrict")
    supplier_id = fields.Many2one(related="supplier_product_id.supplier_id", string="Lieferant", store=True, readonly=True)
    unit_purchase_price = fields.Float(string="EK je Einheit", digits=(16, 4), readonly=True)
    purchase_total = fields.Float(string="EK gesamt", digits=(16, 4), compute="_compute_purchase_total", store=True)
    stock_movement_id = fields.Many2one(comodel_name="sab.stock.movement", string="Lagerzugang", readonly=True, copy=False, ondelete="restrict")
    state = fields.Selection(selection=[("open", "Offen"), ("ordered", "Bestellt"), ("received", "Geliefert"), ("cancel", "Storniert")], string="Status", required=True, default="open", index=True)
    note = fields.Char(string="Bemerkung")

    _bom_line_unique = models.Constraint("UNIQUE(bom_line_id)", "Für diese Stücklistenposition existiert bereits ein Einkaufsbedarf.")

    @api.depends("quantity", "unit_purchase_price")
    def _compute_purchase_total(self):
        for record in self:
            record.purchase_total = (record.quantity or 0.0) * (record.unit_purchase_price or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            bom_line_id = vals.get("bom_line_id")
            if not bom_line_id:
                raise ValidationError(_("Ein Einkaufsbedarf benötigt eine Stücklistenposition."))
            line = self.env["sab.project.bom.line"].browse(bom_line_id).exists()
            if not line:
                raise ValidationError(_("Die Stücklistenposition existiert nicht."))
            if line.bom_id.state != "released":
                raise ValidationError(_("Einkaufsbedarf darf nur aus einer freigegebenen Stückliste erzeugt werden."))
            vals.setdefault("bom_id", line.bom_id.id)
            vals.setdefault("name", f"BED {line.bom_id.name} / {line.sequence}")
            vals.setdefault("quantity", line.quantity)
            vals.setdefault("supplier_product_id", line.supplier_product_id.id or False)
            vals.setdefault("unit_purchase_price", line.unit_purchase_price)
            vals.setdefault("note", line.note)
            prepared.append(vals)
        return super().create(prepared)

    def action_mark_ordered(self):
        for record in self:
            if record.state == "open":
                record.state = "ordered"
        return True

    def action_mark_received(self):
        for record in self:
            if record.state == "received" and record.stock_movement_id:
                continue
            if record.state not in ("open", "ordered", "received"):
                raise ValidationError(_("Nur offener oder bestellter Bedarf kann als geliefert markiert werden."))
            if not record.stock_movement_id:
                movement = self.env["sab.stock.movement"].create({
                    "product_id": record.product_id.id,
                    "movement_type": "receipt",
                    "quantity": record.quantity,
                    "unit": record.unit,
                    "unit_cost": record.unit_purchase_price,
                    "project_id": record.project_id.id or False,
                    "purchase_requirement_id": record.id,
                    "note": record.name,
                })
                record.stock_movement_id = movement.id
            record.state = "received"
        return True
