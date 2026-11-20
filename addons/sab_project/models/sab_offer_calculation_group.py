from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationGroup(models.Model):
    _name = "sab.offer.calculation.group"
    _description = "SAB-P Angebotsbauteil (Altbestand)"
    _order = "sequence, id"

    order_id = fields.Many2one("sale.order", string="Angebot", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    name = fields.Char(string="Bauteil", required=True)
    description = fields.Text(string="Angebotstext")
    line_ids = fields.One2many("sab.offer.calculation.line", "group_id", string="Positionen")
    group_net_price = fields.Monetary(string="Gruppenpreis", currency_field="currency_id", compute="_compute_group_net_price", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", readonly=True, store=True)
    note = fields.Char(string="Bemerkung")

    @api.depends("line_ids.recommended_net_price")
    def _compute_group_net_price(self):
        for record in self:
            record.group_net_price = sum(record.line_ids.mapped("recommended_net_price"))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sab_calculation_group_ids = fields.One2many("sab.offer.calculation.group", "order_id", string="Bauteile / Gruppenpreise (Altbestand)", copy=True)
    sab_vat_rate = fields.Float(string="Umsatzsteuer (%)", default=19.0, copy=True, digits=(5, 2))
    sab_offer_subtotal = fields.Monetary(string="SAB-P Nettobetrag vor Objektnachlass", currency_field="currency_id", compute="_compute_sab_offer_totals", store=True)
    sab_object_discount_amount = fields.Monetary(string="Objektnachlass", currency_field="currency_id", compute="_compute_sab_offer_totals", store=True)
    sab_offer_net_after_discount = fields.Monetary(string="Nettobetrag nach Objektnachlass", currency_field="currency_id", compute="_compute_sab_offer_totals", store=True)
    sab_offer_net_total = fields.Monetary(string="SAB-P Netto-Angebotssumme", currency_field="currency_id", compute="_compute_sab_offer_totals", store=True)
    sab_offer_vat_total = fields.Monetary(string="Umsatzsteuer", currency_field="currency_id", compute="_compute_sab_offer_totals", store=True)
    sab_offer_gross_total = fields.Monetary(string="Brutto-Angebotssumme", currency_field="currency_id", compute="_compute_sab_offer_totals", store=True)

    @api.depends(
        "sab_calculation_line_ids.recommended_net_price",
        "sab_calculation_line_ids.line_type",
        "sab_object_discount_percent",
        "sab_transport_cost",
        "sab_vat_rate",
    )
    def _compute_sab_offer_totals(self):
        for order in self:
            # Jede echte Position wird genau einmal summiert. Bauteil-/Abschnittszeilen
            # zeigen lediglich die Summe ihrer untergeordneten Positionen und werden nicht doppelt addiert.
            subtotal = sum(order.sab_calculation_line_ids.filtered(lambda line: line.line_type == "item").mapped("recommended_net_price"))
            discount_amount = subtotal * (order.sab_object_discount_percent or 0.0) / 100.0
            after_discount = subtotal - discount_amount
            net_total = after_discount + (order.sab_transport_cost or 0.0)
            vat_total = net_total * (order.sab_vat_rate or 0.0) / 100.0
            order.sab_offer_subtotal = subtotal
            order.sab_object_discount_amount = discount_amount
            order.sab_offer_net_after_discount = after_discount
            order.sab_offer_net_total = net_total
            order.sab_offer_vat_total = vat_total
            order.sab_offer_gross_total = net_total + vat_total


class SaleOrderCalculationWorkspaces(models.Model):
    _inherit = "sale.order"

    # This is a filtered view of the SAME records, not an additional cost table.
    # The canonical sab_calculation_line_ids remains the sole source for prices,
    # snapshots, customer lines, reports, LV validation and release protection.
    sab_material_calculation_line_ids = fields.One2many(
        comodel_name="sab.offer.calculation.line",
        inverse_name="order_id",
        string="Materialkalkulation",
        domain=[
            ("line_type", "=", "item"),
            ("calculation_item_id", "=", False),
            ("odoo_product_id", "!=", False),
        ],
        copy=False,
        help="Direkte Produktpositionen desselben Angebots; keine doppelte Summierung.",
    )

    def action_sab_create_suboffer(self):
        """Create an empty project quotation with the source commercial snapshot.

        Unlike action_create_sab_revision, no calculation/customer/group lines
        are copied. No source record or central customer parameter is written.
        Copying the header preserves the stored customer-specific factors rather
        than silently taking today's global default values.
        """
        self.ensure_one()
        if not self.sab_project_id:
            raise ValidationError("Ein Unterangebot benötigt ein SAB-P Projekt.")
        new_order = self.copy({
            "state": "draft",
            "order_line": [],
            "sab_calculation_line_ids": [],
            "sab_material_calculation_line_ids": [],
            "sab_calculation_group_ids": [],
            "sab_revision_of_id": False,
            "sab_revision_reason": False,
            "sab_offer_release_state": "draft",
            "sab_offer_released_at": False,
            "sab_offer_released_by_id": False,
            "origin": self.sab_offer_reference or self.name,
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Neues Unterangebot",
            "res_model": "sale.order",
            "res_id": new_order.id,
            "view_mode": "form",
            "target": "current",
        }
