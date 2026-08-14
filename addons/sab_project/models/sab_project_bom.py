from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabProjectBom(models.Model):
    _name = "sab.project.bom"
    _description = "SAB-P Projektstückliste"
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Stückliste", required=True, readonly=True, copy=False)
    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Auftrag / Angebot",
        required=True,
        ondelete="restrict",
        index=True,
    )
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projekt",
        required=True,
        ondelete="restrict",
        index=True,
    )
    state = fields.Selection(
        selection=[("draft", "Entwurf"), ("released", "Freigegeben")],
        string="Status",
        required=True,
        default="draft",
        index=True,
    )
    generated_at = fields.Datetime(
        string="Erzeugt am",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    generated_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Erzeugt von",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    line_ids = fields.One2many(
        comodel_name="sab.project.bom.line",
        inverse_name="bom_id",
        string="Stücklistenpositionen",
        copy=True,
    )
    note = fields.Text(string="Hinweise")

    _order_unique = models.Constraint(
        "UNIQUE(order_id)",
        "Für diesen Auftrag existiert bereits eine SAB-P Stückliste.",
    )

    def action_release(self):
        for record in self:
            if not record.line_ids:
                raise ValidationError("Eine leere Stückliste kann nicht freigegeben werden.")
            record.state = "released"
        return True

    def write(self, vals):
        if any(record.state == "released" for record in self):
            allowed = {"state"}
            if set(vals) - allowed or vals.get("state") != "released":
                raise ValidationError("Eine freigegebene Stückliste ist gesperrt.")
        return super().write(vals)

    def unlink(self):
        if any(record.state == "released" for record in self):
            raise ValidationError("Eine freigegebene Stückliste darf nicht gelöscht werden.")
        return super().unlink()


class SabProjectBomLine(models.Model):
    _name = "sab.project.bom.line"
    _description = "SAB-P Projektstücklistenposition"
    _order = "sequence, id"

    bom_id = fields.Many2one(
        comodel_name="sab.project.bom",
        string="Stückliste",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Produkt",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(string="Menge", required=True, digits=(16, 3), default=1.0)
    unit = fields.Selection(
        selection=[
            ("pcs", "Stück"),
            ("m", "Meter"),
            ("kg", "kg"),
            ("min", "Minute"),
            ("h", "Stunde"),
            ("flat", "Pauschal"),
        ],
        string="Einheit",
        required=True,
        default="pcs",
    )
    optional = fields.Boolean(string="Optional", default=False)
    supplier_product_id = fields.Many2one(
        comodel_name="sab.supplier.product",
        string="Lieferantenartikel",
        ondelete="set null",
    )
    unit_purchase_price = fields.Float(string="EK je Einheit", digits=(16, 4), readonly=True)
    purchase_total = fields.Float(
        string="EK gesamt",
        digits=(16, 4),
        compute="_compute_purchase_total",
        store=True,
    )
    note = fields.Char(string="Bemerkung")

    @api.depends("quantity", "unit_purchase_price")
    def _compute_purchase_total(self):
        for record in self:
            record.purchase_total = (record.quantity or 0.0) * (record.unit_purchase_price or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            bom_id = vals.get("bom_id")
            if bom_id:
                bom = self.env["sab.project.bom"].browse(bom_id)
                if bom.state == "released":
                    raise ValidationError("Zu einer freigegebenen Stückliste dürfen keine Positionen ergänzt werden.")
        return super().create(vals_list)

    def write(self, vals):
        if any(record.bom_id.state == "released" for record in self):
            raise ValidationError("Positionen einer freigegebenen Stückliste sind gesperrt.")
        return super().write(vals)

    def unlink(self):
        if any(record.bom_id.state == "released" for record in self):
            raise ValidationError("Positionen einer freigegebenen Stückliste dürfen nicht gelöscht werden.")
        return super().unlink()
