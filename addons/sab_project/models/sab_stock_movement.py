from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabStockMovement(models.Model):
    _name = "sab.stock.movement"
    _description = "SAB-P Lagerbewegung"
    _order = "movement_date desc, id desc"

    name = fields.Char(string="Beleg", required=True, readonly=True, copy=False)
    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Produkt",
        required=True,
        ondelete="restrict",
        index=True,
    )
    movement_type = fields.Selection(
        selection=[
            ("receipt", "Zugang"),
            ("issue", "Entnahme"),
            ("reserve", "Reservierung"),
            ("release", "Reservierung freigeben"),
        ],
        string="Bewegungsart",
        required=True,
        index=True,
    )
    quantity = fields.Float(string="Menge", required=True, digits=(16, 3))
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
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projekt",
        ondelete="set null",
        index=True,
    )
    purchase_requirement_id = fields.Many2one(
        comodel_name="sab.purchase.requirement",
        string="Einkaufsbedarf",
        ondelete="set null",
        index=True,
    )
    movement_date = fields.Datetime(
        string="Buchungszeitpunkt",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Gebucht von",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    note = fields.Char(string="Bemerkung")

    @api.constrains("quantity")
    def _check_positive_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("Lagerbewegungen benötigen eine Menge größer 0."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        Movement = self.env["sab.stock.movement"]
        for incoming in vals_list:
            vals = dict(incoming)
            product = self.env["sab.product"].browse(vals.get("product_id")).exists()
            if not product:
                raise ValidationError(_("Für die Lagerbewegung ist ein gültiges Produkt erforderlich."))
            qty = float(vals.get("quantity") or 0.0)
            movement_type = vals.get("movement_type")
            if movement_type in ("issue", "reserve", "release") and qty > 0:
                existing = Movement.search([("product_id", "=", product.id)])
                on_hand = sum(existing.filtered(lambda m: m.movement_type == "receipt").mapped("quantity")) - sum(existing.filtered(lambda m: m.movement_type == "issue").mapped("quantity"))
                reserved = sum(existing.filtered(lambda m: m.movement_type == "reserve").mapped("quantity")) - sum(existing.filtered(lambda m: m.movement_type == "release").mapped("quantity"))
                if movement_type == "issue" and qty > on_hand:
                    raise ValidationError(_("Die Entnahme überschreitet den vorhandenen Lagerbestand."))
                if movement_type == "reserve" and qty > (on_hand - reserved):
                    raise ValidationError(_("Die Reservierung überschreitet den verfügbaren Lagerbestand."))
                if movement_type == "release" and qty > reserved:
                    raise ValidationError(_("Es kann nicht mehr Reservierung freigegeben werden als vorhanden ist."))
            vals.setdefault("name", self.env["ir.sequence"].next_by_code("sab.stock.movement") or _("Lagerbewegung"))
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        protected = {"product_id", "movement_type", "quantity", "unit", "movement_date", "purchase_requirement_id"}
        if protected.intersection(vals):
            raise ValidationError(_("Gebuchte Lagerbewegungen dürfen nicht nachträglich verändert werden."))
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_("Gebuchte Lagerbewegungen dürfen nicht gelöscht werden. Erfassen Sie eine Gegenbuchung."))
