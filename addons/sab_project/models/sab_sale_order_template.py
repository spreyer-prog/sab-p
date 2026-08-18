from odoo import api, fields, models


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    def _sab_param(self, key, default):
        raw = self.env["ir.config_parameter"].sudo().get_param(key, str(default))
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    # Kalkulationswerte aus der bisherigen SAB-P Excel-Vorlage.
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

    # Weitere in der Excel-Kalkulation vorhandene Referenzwerte. Sie werden in der
    # Vorlage gespeichert, auch wenn einzelne Sonderformeln erst schrittweise in
    # den Rechenkern übernommen werden.
    sab_additional_order_factor = fields.Float(string="Nachtragsaufschlag", default=1.10)
    sab_hw_metal_factor = fields.Float(string="HW-Faktor / Metallzuschlag", default=1.0)
    sab_trade_factor_1 = fields.Float(string="Handelsware 1", default=1.25)
    sab_trade_factor_2 = fields.Float(string="Handelsware 2", default=1.25)
    sab_trade_factor_3 = fields.Float(string="Handelsware 3", default=1.25)
    sab_trade_factor_4 = fields.Float(string="Handelsware 4", default=1.25)
    sab_trade_factor_5 = fields.Float(string="Handelsware 5", default=1.25)
    sab_trade_factor_6 = fields.Float(string="Handelsware 6", default=1.25)
    sab_terminal_deduction = fields.Float(string="Abzugswert Klemme", default=0.0)
    sab_wage_unit = fields.Float(string="Lohneinheit", default=1.6666666667)
    sab_planning_hours = fields.Float(string="Planstunden", default=80.0)
    sab_assembly_correction = fields.Float(string="Korrektur Montage", default=0.0)

    # Angebotsbedingungen aus der bisherigen Angebotsvorlage.
    sab_object_discount_percent = fields.Float(string="Objektnachlass (%)", default=0.0, digits=(5, 2))
    sab_transport_cost = fields.Monetary(string="Transportkosten", currency_field="currency_id", default=0.0)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    sab_delivery_time_text = fields.Char(string="Lieferzeit", default="5-8 Wochen")
    sab_payment_text = fields.Char(string="Zahlung", default="nach Vereinbarung")
    sab_service_description = fields.Html(string="Leistungsbeschreibung")
    sab_documentation_text = fields.Html(string="Dokumentation")
    sab_reservations_text = fields.Html(string="Vorbehalte")
    sab_additional_terms_text = fields.Html(string="Zusätzliche Bedingungen")
    sab_transport_text = fields.Html(string="Transport / Verpackung")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sab_additional_order_factor = fields.Float(string="Nachtragsaufschlag", default=1.10, copy=True)
    sab_hw_metal_factor = fields.Float(string="HW-Faktor / Metallzuschlag", default=1.0, copy=True)
    sab_trade_factor_1 = fields.Float(string="Handelsware 1", default=1.25, copy=True)
    sab_trade_factor_2 = fields.Float(string="Handelsware 2", default=1.25, copy=True)
    sab_trade_factor_3 = fields.Float(string="Handelsware 3", default=1.25, copy=True)
    sab_trade_factor_4 = fields.Float(string="Handelsware 4", default=1.25, copy=True)
    sab_trade_factor_5 = fields.Float(string="Handelsware 5", default=1.25, copy=True)
    sab_trade_factor_6 = fields.Float(string="Handelsware 6", default=1.25, copy=True)
    sab_terminal_deduction = fields.Float(string="Abzugswert Klemme", default=0.0, copy=True)
    sab_wage_unit = fields.Float(string="Lohneinheit", default=1.6666666667, copy=True)
    sab_planning_hours = fields.Float(string="Planstunden", default=80.0, copy=True)
    sab_assembly_correction = fields.Float(string="Korrektur Montage", default=0.0, copy=True)

    sab_object_discount_percent = fields.Float(string="Objektnachlass (%)", default=0.0, digits=(5, 2), copy=True)
    sab_transport_cost = fields.Monetary(string="Transportkosten", currency_field="currency_id", default=0.0, copy=True)
    sab_delivery_time_text = fields.Char(string="Lieferzeit", copy=True)
    sab_payment_text = fields.Char(string="Zahlung", copy=True)
    sab_service_description = fields.Html(string="Leistungsbeschreibung", copy=True)
    sab_documentation_text = fields.Html(string="Dokumentation", copy=True)
    sab_reservations_text = fields.Html(string="Vorbehalte", copy=True)
    sab_additional_terms_text = fields.Html(string="Zusätzliche Bedingungen", copy=True)
    sab_transport_text = fields.Html(string="Transport / Verpackung", copy=True)

    @api.onchange("sale_order_template_id")
    def _onchange_sale_order_template_id(self):
        result = super()._onchange_sale_order_template_id()
        for order in self:
            template = order.sale_order_template_id
            if not template:
                continue
            fields_to_copy = (
                "sab_material_factor", "sab_aux_material_factor", "sab_hourly_rate",
                "sab_time_factor", "sab_difficulty_factor", "sab_planning_surcharge_factor",
                "sab_packaging_factor", "sab_skonto_factor", "sab_margin_factor",
                "sab_rebate_factor", "sab_vat_rate", "sab_additional_order_factor",
                "sab_hw_metal_factor", "sab_trade_factor_1", "sab_trade_factor_2",
                "sab_trade_factor_3", "sab_trade_factor_4", "sab_trade_factor_5",
                "sab_trade_factor_6", "sab_terminal_deduction", "sab_wage_unit",
                "sab_planning_hours", "sab_assembly_correction", "sab_object_discount_percent",
                "sab_transport_cost", "sab_delivery_time_text", "sab_payment_text",
                "sab_service_description", "sab_documentation_text", "sab_reservations_text",
                "sab_additional_terms_text", "sab_transport_text",
            )
            for field_name in fields_to_copy:
                order[field_name] = template[field_name]
        return result
