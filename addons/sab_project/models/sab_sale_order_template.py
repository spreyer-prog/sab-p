from odoo import api, fields, models


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    def _sab_param(self, key, default):
        raw = self.env["ir.config_parameter"].sudo().get_param(key, str(default))
        try: return float(raw)
        except (TypeError, ValueError): return float(default)

    sab_material_factor = fields.Float(string="Materialfaktor", default=lambda self: self._sab_param("sab_project.material_factor", 1.0))
    sab_aux_material_factor = fields.Float(string="Hilfsmaterialfaktor", default=lambda self: self._sab_param("sab_project.aux_material_factor", 1.15))
    sab_hourly_rate = fields.Float(string="Kalkulatorischer Stundenlohn", default=lambda self: self._sab_param("sab_project.hourly_rate", 80.0))
    sab_time_factor = fields.Float(string="Zeitfaktor", default=lambda self: self._sab_param("sab_project.time_factor", 1.25))
    sab_difficulty_factor = fields.Float(string="Schwierigkeitsfaktor", default=lambda self: self._sab_param("sab_project.difficulty_factor", 1.0))
    sab_planning_surcharge_factor = fields.Float(string="Planungszuschlag", default=lambda self: self._sab_param("sab_project.planning_surcharge_factor", 1.15))
    sab_packaging_factor = fields.Float(string="Verpackung / Transport Faktor", default=lambda self: self._sab_param("sab_project.packaging_factor", 1.03))
    sab_skonto_factor = fields.Float(string="Skontofaktor", default=lambda self: self._sab_param("sab_project.skonto_factor", 1.03))
    sab_margin_factor = fields.Float(string="Margenfaktor", default=lambda self: self._sab_param("sab_project.margin_factor", 1.35))
    sab_rebate_factor = fields.Float(string="Rabattfaktor", default=lambda self: self._sab_param("sab_project.rebate_factor", 1.125))
    sab_vat_rate = fields.Float(string="Umsatzsteuer (%)", default=19.0, digits=(5, 2))
    sab_additional_order_factor = fields.Float(string="Nachtragsaufschlag", default=1.10)
    sab_hw_metal_factor = fields.Float(string="HW-Faktor / Metallzuschlag", default=1.0)
    sab_trade_factor_1 = fields.Float(string="Handelsware 1", default=1.25); sab_trade_factor_2 = fields.Float(string="Handelsware 2", default=1.25); sab_trade_factor_3 = fields.Float(string="Handelsware 3", default=1.25); sab_trade_factor_4 = fields.Float(string="Handelsware 4", default=1.25); sab_trade_factor_5 = fields.Float(string="Handelsware 5", default=1.25); sab_trade_factor_6 = fields.Float(string="Handelsware 6", default=1.25)
    sab_terminal_deduction = fields.Float(string="Abzugswert Klemme", default=0.0); sab_wage_unit = fields.Float(string="Lohneinheit", default=1.6666666667); sab_planning_hours = fields.Float(string="Planstunden", default=80.0); sab_assembly_correction = fields.Float(string="Korrektur Montage", default=0.0)
    sab_object_discount_percent = fields.Float(string="Objektnachlass (%)", default=0.0, digits=(5, 2)); sab_transport_cost = fields.Monetary(string="Transportkosten", currency_field="currency_id", default=0.0); currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    sab_delivery_time_text = fields.Char(string="Lieferzeit", default="5-8 Wochen"); sab_payment_text = fields.Char(string="Zahlung", default="nach Vereinbarung"); sab_service_description = fields.Html(string="Leistungsbeschreibung"); sab_documentation_text = fields.Html(string="Dokumentation"); sab_reservations_text = fields.Html(string="Vorbehalte"); sab_additional_terms_text = fields.Html(string="Zusätzliche Bedingungen"); sab_transport_text = fields.Html(string="Transport / Verpackung")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sab_calculation_source = fields.Selection([("lv", "LV-Angebot"), ("schematic", "Schaltplan-Angebot")], string="Kalkulationsgrundlage", default="lv", copy=True)
    sab_margin_factor = fields.Float(default=lambda self: self._sab_float_param("sab_project.margin_factor", 1.35))
    sab_additional_order_factor = fields.Float(string="Nachtragsaufschlag", default=1.10, copy=True); sab_hw_metal_factor = fields.Float(string="HW-Faktor / Metallzuschlag", default=1.0, copy=True)
    sab_trade_factor_1 = fields.Float(string="Handelsware 1", default=1.25, copy=True); sab_trade_factor_2 = fields.Float(string="Handelsware 2", default=1.25, copy=True); sab_trade_factor_3 = fields.Float(string="Handelsware 3", default=1.25, copy=True); sab_trade_factor_4 = fields.Float(string="Handelsware 4", default=1.25, copy=True); sab_trade_factor_5 = fields.Float(string="Handelsware 5", default=1.25, copy=True); sab_trade_factor_6 = fields.Float(string="Handelsware 6", default=1.25, copy=True)
    sab_terminal_deduction = fields.Float(string="Abzugswert Klemme", default=0.0, copy=True); sab_wage_unit = fields.Float(string="Lohneinheit", default=1.6666666667, copy=True); sab_planning_hours = fields.Float(string="Planstunden", default=80.0, copy=True); sab_assembly_correction = fields.Float(string="Korrektur Montage", default=0.0, copy=True)
    sab_object_discount_percent = fields.Float(string="Objektnachlass (%)", default=0.0, digits=(5, 2), copy=True); sab_transport_cost = fields.Monetary(string="Transportkosten", currency_field="currency_id", default=0.0, copy=True)
    sab_delivery_time_text = fields.Char(string="Lieferzeit", copy=True); sab_payment_text = fields.Char(string="Zahlung", copy=True); sab_service_description = fields.Html(string="Leistungsbeschreibung", copy=True); sab_documentation_text = fields.Html(string="Dokumentation", copy=True); sab_reservations_text = fields.Html(string="Vorbehalte", copy=True); sab_additional_terms_text = fields.Html(string="Zusätzliche Bedingungen", copy=True); sab_transport_text = fields.Html(string="Transport / Verpackung", copy=True)
    sab_auxiliary_purchase_total = fields.Monetary(string="Hilfsmaterial-EK", currency_field="currency_id", compute="_compute_sab_calculation_totals", store=True)

    @api.depends("sab_calculation_line_ids.material_purchase_total", "sab_calculation_line_ids.auxiliary_purchase_total", "sab_calculation_line_ids.mechanical_time_minutes", "sab_calculation_line_ids.wiring_time_minutes", "sab_calculation_line_ids.testing_time_minutes", "sab_calculation_line_ids.total_time_minutes", "sab_calculation_line_ids.space_units", "sab_material_factor", "sab_aux_material_factor", "sab_hourly_rate", "sab_time_factor", "sab_difficulty_factor", "sab_packaging_factor", "sab_skonto_factor", "sab_margin_factor", "sab_rebate_factor")
    def _compute_sab_calculation_totals(self):
        for order in self:
            lines = order.sab_calculation_line_ids.filtered(lambda line: line.line_type == "item")
            normal_material = sum(lines.mapped("material_purchase_total")); auxiliary_material = sum(lines.mapped("auxiliary_purchase_total")); total_minutes = sum(lines.mapped("total_time_minutes"))
            order.sab_material_purchase_total = normal_material; order.sab_auxiliary_purchase_total = auxiliary_material
            order.sab_mechanical_hours = sum(lines.mapped("mechanical_time_minutes")) / 60.0; order.sab_wiring_hours = sum(lines.mapped("wiring_time_minutes")) / 60.0; order.sab_testing_hours = sum(lines.mapped("testing_time_minutes")) / 60.0; order.sab_calculated_hours = total_minutes / 60.0; order.sab_space_units = sum(lines.mapped("space_units"))
            normal_cost = normal_material * (order.sab_material_factor or 0.0); auxiliary_cost = auxiliary_material * (order.sab_material_factor or 0.0) * (order.sab_aux_material_factor or 0.0)
            order.sab_material_cost = normal_cost + auxiliary_cost; order.sab_labor_cost = order.sab_calculated_hours * (order.sab_hourly_rate or 0.0) * (order.sab_time_factor or 0.0) * (order.sab_difficulty_factor or 0.0); order.sab_direct_cost = order.sab_material_cost + order.sab_labor_cost
            order.sab_commercial_factor = (order.sab_packaging_factor or 0.0) * (order.sab_skonto_factor or 0.0) * (order.sab_margin_factor or 0.0) * (order.sab_rebate_factor or 0.0); order.sab_recommended_net_price = order.sab_direct_cost * order.sab_commercial_factor

    @api.onchange("sale_order_template_id")
    def _onchange_sale_order_template_id(self):
        result = super()._onchange_sale_order_template_id()
        for order in self:
            template = order.sale_order_template_id
            if not template: continue
            fields_to_copy = ("sab_material_factor", "sab_aux_material_factor", "sab_hourly_rate", "sab_time_factor", "sab_difficulty_factor", "sab_planning_surcharge_factor", "sab_packaging_factor", "sab_skonto_factor", "sab_margin_factor", "sab_rebate_factor", "sab_vat_rate", "sab_additional_order_factor", "sab_hw_metal_factor", "sab_trade_factor_1", "sab_trade_factor_2", "sab_trade_factor_3", "sab_trade_factor_4", "sab_trade_factor_5", "sab_trade_factor_6", "sab_terminal_deduction", "sab_wage_unit", "sab_planning_hours", "sab_assembly_correction", "sab_object_discount_percent", "sab_transport_cost", "sab_delivery_time_text", "sab_payment_text", "sab_service_description", "sab_documentation_text", "sab_reservations_text", "sab_additional_terms_text", "sab_transport_text")
            for field_name in fields_to_copy: order[field_name] = template[field_name]
        return result


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sab_generated_from_calculation = fields.Boolean(string="Aus SAB-P Kalkulation", default=False, copy=False, index=True)
    sab_calculation_source_line_id = fields.Many2one("sab.offer.calculation.line", string="SAB-P Kalkulationszeile", copy=False, ondelete="set null", index=True)
