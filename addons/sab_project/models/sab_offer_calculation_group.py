from odoo import api, fields, models


class SabOfferCalculationGroup(models.Model):
    _name = "sab.offer.calculation.group"
    _description = "SAB-P Angebotsbauteil"
    _order = "sequence, id"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Angebot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    name = fields.Char(string="Bauteil", required=True)
    description = fields.Text(string="Angebotstext")
    line_ids = fields.One2many(
        comodel_name="sab.offer.calculation.line",
        inverse_name="group_id",
        string="Positionen",
    )
    group_net_price = fields.Monetary(
        string="Gruppenpreis",
        currency_field="currency_id",
        compute="_compute_group_net_price",
        store=True,
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id",
        string="Währung",
        readonly=True,
        store=True,
    )
    note = fields.Char(string="Bemerkung")

    @api.depends("line_ids.recommended_net_price")
    def _compute_group_net_price(self):
        for record in self:
            record.group_net_price = sum(record.line_ids.mapped("recommended_net_price"))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sab_calculation_group_ids = fields.One2many(
        comodel_name="sab.offer.calculation.group",
        inverse_name="order_id",
        string="Bauteile / Gruppenpreise",
        copy=True,
    )
    sab_vat_rate = fields.Float(
        string="Umsatzsteuer (%)",
        default=19.0,
        copy=True,
        digits=(5, 2),
        help="Umsatzsteuersatz für den SAB-P Angebotsdruck. Standard: 19 %.",
    )
    sab_offer_net_total = fields.Monetary(
        string="SAB-P Netto-Angebotssumme",
        currency_field="currency_id",
        compute="_compute_sab_offer_totals",
        store=True,
    )
    sab_offer_vat_total = fields.Monetary(
        string="Umsatzsteuer",
        currency_field="currency_id",
        compute="_compute_sab_offer_totals",
        store=True,
    )
    sab_offer_gross_total = fields.Monetary(
        string="Brutto-Angebotssumme",
        currency_field="currency_id",
        compute="_compute_sab_offer_totals",
        store=True,
    )

    @api.depends(
        "sab_calculation_group_ids.group_net_price",
        "sab_calculation_line_ids.recommended_net_price",
        "sab_calculation_line_ids.group_id",
        "sab_vat_rate",
    )
    def _compute_sab_offer_totals(self):
        for order in self:
            grouped_total = sum(order.sab_calculation_group_ids.mapped("group_net_price"))
            ungrouped_total = sum(
                order.sab_calculation_line_ids
                .filtered(lambda line: not line.group_id)
                .mapped("recommended_net_price")
            )
            net_total = grouped_total + ungrouped_total
            vat_total = net_total * (order.sab_vat_rate or 0.0) / 100.0
            order.sab_offer_net_total = net_total
            order.sab_offer_vat_total = vat_total
            order.sab_offer_gross_total = net_total + vat_total
