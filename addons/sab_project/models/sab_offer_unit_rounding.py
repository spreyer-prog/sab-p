"""Unit-first selling-price rounding for new quotation families only.

Existing orders keep the old algorithm on upgrade. Their copies and new
suboffers keep the same version, even when other projects use the new rule.
This changes neither customer factors nor the stored hourly cost rate.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderUnitRounding(models.Model):
    _inherit = "sale.order"

    sab_price_rounding_version = fields.Selection(
        [("legacy", "Bestand: bisherige Rundung"),
         ("unit_v1", "Einzelpreis runden, dann Menge")],
        string="Preisrundung", default="legacy", required=True,
        copy=True, readonly=True,
        help="Bestehende Angebote behalten ihre Rechenregel. Neue Projekte "
             "runden zuerst den Einzelpreis. Unterangebote übernehmen dieselbe Regel.",
    )

    @api.model
    def _sab_rounding_for_project(self, project_id):
        if not project_id:
            return "legacy"
        previous = self.sudo().with_context(active_test=False).search(
            [("sab_project_id", "=", project_id)], order="id", limit=1,
        )
        return (previous.sab_price_rounding_version or "legacy") if previous else "unit_v1"

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "sab_price_rounding_version" in fields_list:
            project_id = values.get("sab_project_id") or self.env.context.get("default_sab_project_id")
            if project_id:
                values["sab_price_rounding_version"] = self._sab_rounding_for_project(project_id)
        return values

    @api.onchange("sab_project_id")
    def _onchange_sab_rounding_project(self):
        for order in self:
            if not order._origin.id:
                order.sab_price_rounding_version = self._sab_rounding_for_project(order.sab_project_id.id)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [dict(values) for values in vals_list]
        project_ids = sorted({
            values.get("sab_project_id", self.env.context.get("default_sab_project_id"))
            for values in prepared
        } - {False, None})
        # Prevent two simultaneous first offers of one project choosing different rules.
        if project_ids:
            self.env.cr.execute(
                "SELECT id FROM project_project WHERE id IN %s ORDER BY id FOR UPDATE",
                [tuple(project_ids)],
            )
        policies = {}
        for project_id in project_ids:
            previous = self.sudo().with_context(active_test=False).search(
                [("sab_project_id", "=", project_id)], order="id", limit=1,
            )
            if previous:
                policies[project_id] = previous.sab_price_rounding_version or "legacy"
        for values in prepared:
            project_id = values.get("sab_project_id", self.env.context.get("default_sab_project_id"))
            requested = values.get("sab_price_rounding_version")
            if project_id in policies:
                policy = policies[project_id]
                if requested and requested != policy:
                    raise ValidationError(
                        "Haupt- und Unterangebote eines Projekts müssen dieselbe Preisrundung verwenden."
                    )
            else:
                policy = requested or ("unit_v1" if project_id else "legacy")
                if project_id:
                    policies[project_id] = policy
            values["sab_price_rounding_version"] = policy
        return super().create(prepared)

    def write(self, vals):
        if "sab_price_rounding_version" in vals:
            for order in self:
                if vals["sab_price_rounding_version"] != order.sab_price_rounding_version:
                    raise ValidationError(
                        "Die Preisrundung bestehender Angebote darf nicht nachträglich geändert werden."
                    )
        result = super().write(vals)
        # Normal Odoo order lines must show the same unit prices as the SAB-P lines.
        price_fields = {
            "sab_material_factor", "sab_aux_material_factor", "sab_hourly_rate",
            "sab_time_factor", "sab_difficulty_factor", "sab_packaging_factor",
            "sab_skonto_factor", "sab_margin_factor", "sab_rebate_factor",
        }
        if price_fields.intersection(vals):
            orders = self.filtered(lambda order: order.sab_price_rounding_version == "unit_v1"
                                   and order.state == "draft"
                                   and order.sab_offer_release_state != "released")
            orders.mapped("sab_calculation_line_ids")._sync_customer_order_lines()
        return result

    @api.depends("sab_price_rounding_version",
                 "sab_calculation_line_ids.recommended_net_price",
                 "sab_calculation_line_ids.line_type")
    def _compute_sab_calculation_totals(self):
        super()._compute_sab_calculation_totals()
        for order in self:
            if order.sab_price_rounding_version == "unit_v1":
                # Do not recalculate a competing quote total from unrounded costs.
                order.sab_recommended_net_price = sum(
                    order.sab_calculation_line_ids.filtered(
                        lambda line: line.line_type == "item"
                    ).mapped("recommended_net_price")
                )


class SabOfferLineUnitRounding(models.Model):
    _inherit = "sab.offer.calculation.line"

    @api.depends("order_id.sab_price_rounding_version", "unit_material_purchase",
                 "unit_auxiliary_purchase", "unit_total_minutes", "currency_id",
                 "currency_id.rounding")
    def _compute_price(self):
        legacy = self.filtered(lambda line: line.order_id.sab_price_rounding_version != "unit_v1")
        if legacy:
            # Keep historical calculation, including its rounding, unchanged.
            super(SabOfferLineUnitRounding, legacy)._compute_price()
        for line in self - legacy:
            if line.line_type != "item":
                line.unit_recommended_net_price = 0.0
                line.recommended_net_price = 0.0
                continue
            order = line.order_id
            currency = line.currency_id or order.company_id.currency_id
            material = (line.unit_material_purchase * order.sab_material_factor
                        + line.unit_auxiliary_purchase * order.sab_material_factor
                        * order.sab_aux_material_factor)
            labor = (line.unit_total_minutes / 60.0 * order.sab_hourly_rate
                     * order.sab_time_factor * order.sab_difficulty_factor)
            factor = (order.sab_packaging_factor * order.sab_skonto_factor
                      * order.sab_margin_factor * order.sab_rebate_factor)
            unit_price = currency.round((material + labor) * factor)
            line.unit_recommended_net_price = unit_price
            line.recommended_net_price = currency.round(unit_price * line.quantity)
