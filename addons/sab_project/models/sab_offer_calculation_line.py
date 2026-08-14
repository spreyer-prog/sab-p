from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLine(models.Model):
    _name = "sab.offer.calculation.line"
    _description = "SAB-P Angebotskalkulationszeile"
    _order = "sequence, id"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Angebot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    calculation_item_id = fields.Many2one(
        comodel_name="sab.calculation.item",
        string="Kalkulationsartikel",
        required=True,
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(
        string="Menge",
        default=1.0,
        required=True,
        digits=(16, 3),
    )
    description = fields.Text(
        string="Angebotstext",
        compute="_compute_values",
        store=True,
        readonly=False,
    )

    material_purchase_total = fields.Monetary(
        string="Material-EK",
        currency_field="currency_id",
        compute="_compute_values",
        store=True,
    )
    mechanical_time_minutes = fields.Float(
        string="Mechanik min",
        compute="_compute_values",
        store=True,
    )
    wiring_time_minutes = fields.Float(
        string="Verdrahtung min",
        compute="_compute_values",
        store=True,
    )
    testing_time_minutes = fields.Float(
        string="Prüfung min",
        compute="_compute_values",
        store=True,
    )
    total_time_minutes = fields.Float(
        string="Gesamtzeit min",
        compute="_compute_values",
        store=True,
    )
    total_hours = fields.Float(
        string="Gesamtstunden",
        compute="_compute_values",
        store=True,
    )
    space_units = fields.Float(
        string="Platzeinheiten",
        compute="_compute_values",
        store=True,
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id",
        string="Währung",
        readonly=True,
        store=True,
    )
    note = fields.Char(string="Bemerkung")

    @api.depends(
        "calculation_item_id",
        "calculation_item_id.quotation_text",
        "calculation_item_id.purchase_total",
        "calculation_item_id.mechanical_time_minutes",
        "calculation_item_id.wiring_time_minutes",
        "calculation_item_id.testing_time_minutes",
        "calculation_item_id.total_time_minutes",
        "calculation_item_id.space_units",
        "quantity",
    )
    def _compute_values(self):
        for record in self:
            item = record.calculation_item_id
            qty = record.quantity or 0.0
            if not item:
                record.description = False
                record.material_purchase_total = 0.0
                record.mechanical_time_minutes = 0.0
                record.wiring_time_minutes = 0.0
                record.testing_time_minutes = 0.0
                record.total_time_minutes = 0.0
                record.total_hours = 0.0
                record.space_units = 0.0
                continue

            # Beschreibung darf im Angebot anschließend bewusst angepasst werden.
            if not record.description:
                record.description = item.quotation_text

            record.material_purchase_total = (item.purchase_total or 0.0) * qty
            record.mechanical_time_minutes = (item.mechanical_time_minutes or 0.0) * qty
            record.wiring_time_minutes = (item.wiring_time_minutes or 0.0) * qty
            record.testing_time_minutes = (item.testing_time_minutes or 0.0) * qty
            record.total_time_minutes = (item.total_time_minutes or 0.0) * qty
            record.total_hours = record.total_time_minutes / 60.0
            record.space_units = (item.space_units or 0.0) * qty

    @api.constrains("quantity")
    def _check_quantity(self):
        for record in self:
            if record.quantity < 0:
                raise ValidationError("Die Menge einer Kalkulationsposition darf nicht negativ sein.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get("order_id")
            if order_id:
                order = self.env["sale.order"].browse(order_id)
                if order.state not in ("draft", "sent"):
                    raise ValidationError(
                        "Kalkulationspositionen dürfen nach Auftragsbestätigung nicht neu angelegt werden."
                    )
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            if record.order_id.state not in ("draft", "sent"):
                raise ValidationError(
                    "Kalkulationspositionen eines bestätigten Angebots sind gesperrt."
                )
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.order_id.state not in ("draft", "sent"):
                raise ValidationError(
                    "Kalkulationspositionen eines bestätigten Angebots sind gesperrt."
                )
        return super().unlink()
