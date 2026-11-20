from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabOfferPrintTemplate(models.Model):
    _name = "sab.offer.print.template"
    _description = "SAB-P Angebotsdruck Vorlage"
    _order = "company_id, id"

    name = fields.Char(string="Vorlage", required=True, default="SAB-P Angebot")
    active = fields.Boolean(string="Aktiv", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Unternehmen",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    printer_name = fields.Char(
        string="Drucker",
        help="Leer = Standard-PDF-Drucker aus den SAB-P-Einstellungen.",
    )
    paper_format = fields.Selection(
        [("a4", "DIN A4")],
        string="Papierformat",
        required=True,
        default="a4",
    )
    orientation = fields.Selection(
        [("portrait", "Hochformat"), ("landscape", "Querformat")],
        string="Ausrichtung",
        required=True,
        default="portrait",
    )
    margin_top_mm = fields.Float(string="Rand oben (mm)", default=10.0)
    margin_bottom_mm = fields.Float(string="Rand unten (mm)", default=12.0)
    margin_left_mm = fields.Float(string="Rand links (mm)", default=12.0)
    margin_right_mm = fields.Float(string="Rand rechts (mm)", default=12.0)
    binding_days = fields.Integer(string="Bindefrist in Tagen", default=30)
    footer_manager_name = fields.Char(
        string="Geschäftsführer im Fußbereich",
        default="Sascha Preyer",
    )
    intro_html = fields.Html(
        string="Einleitung",
        default=(
            "<p>Sehr geehrte Damen und Herren,</p>"
            "<p>wir bedanken uns für Ihre Anfrage und erlauben uns, Ihnen "
            "nachstehendes freibleibendes Angebot zuzusenden.</p>"
        ),
    )
    scope_html = fields.Html(string="Leistungsbeschreibung")
    delivery_html = fields.Html(string="Lieferbedingungen")
    payment_html = fields.Html(string="Zahlungsbedingungen")
    reservations_html = fields.Html(string="Vorbehalte")
    conditions_html = fields.Html(string="Weitere Bedingungen")
    closing_html = fields.Html(
        string="Schlusstext",
        default=(
            "<p>Wir würden uns freuen, Ihren Auftrag zu erhalten und sichern "
            "Ihnen bereits jetzt eine technisch einwandfreie und termingerechte "
            "Lieferung zu.</p><p>Mit freundlichen Grüßen<br/>SAB-P GmbH<br/>"
            "Schaltanlagenbau Preyer</p>"
        ),
    )
    terms_html = fields.Html(
        string="Allgemeine Verkaufsbedingungen / AGB",
        help="Der vollständige Text beginnt im Angebotsdruck auf einer neuen Seite.",
    )

    _company_unique = models.Constraint(
        "UNIQUE(company_id)",
        "Für dieses Unternehmen existiert bereits eine Angebotsdruck-Vorlage.",
    )

    @api.constrains(
        "margin_top_mm",
        "margin_bottom_mm",
        "margin_left_mm",
        "margin_right_mm",
        "binding_days",
    )
    def _check_print_values(self):
        for template in self:
            margins = (
                template.margin_top_mm,
                template.margin_bottom_mm,
                template.margin_left_mm,
                template.margin_right_mm,
            )
            if any(value < 0 or value > 40 for value in margins):
                raise ValidationError(_("Die Seitenränder müssen zwischen 0 und 40 mm liegen."))
            if template.binding_days < 0 or template.binding_days > 365:
                raise ValidationError(_("Die Bindefrist muss zwischen 0 und 365 Tagen liegen."))

    @api.model
    def effective_template(self, company=None):
        company = company or self.env.company
        return self.search(
            [("company_id", "=", company.id), ("active", "=", True)],
            limit=1,
        )

    def resolved_printer_name(self):
        self.ensure_one()
        return self.printer_name or self.env["ir.config_parameter"].sudo().get_param(
            "sab_project.default_pdf_printer",
            "PDF-Drucker",
        )

    def _ensure_runtime_report_action(self):
        self.ensure_one()
        key = "SAB-P Angebotsdruck %s" % self.company_id.id
        Paperformat = self.env["report.paperformat"].sudo()
        paperformat = Paperformat.search([("name", "=", key)], limit=1)
        values = {
            "name": key,
            "format": "A4",
            "orientation": (
                "Landscape" if self.orientation == "landscape" else "Portrait"
            ),
            "margin_top": self.margin_top_mm,
            "margin_bottom": self.margin_bottom_mm,
            "margin_left": self.margin_left_mm,
            "margin_right": self.margin_right_mm,
            "dpi": 90,
        }
        if paperformat:
            paperformat.write(values)
        else:
            paperformat = Paperformat.create(values)

        Report = self.env["ir.actions.report"].sudo()
        report = Report.search(
            [
                ("name", "=", key),
                ("model", "=", "sale.order"),
                ("report_name", "=", "sab_project.report_sab_offer_exact"),
            ],
            limit=1,
        )
        report_values = {
            "name": key,
            "model": "sale.order",
            "report_type": "qweb-pdf",
            "report_name": "sab_project.report_sab_offer_exact",
            "report_file": "sab_project.report_sab_offer_exact",
            "paperformat_id": paperformat.id,
        }
        if report:
            report.write(report_values)
        else:
            report = Report.create(report_values)
        return report

    def action_preview(self):
        self.ensure_one()
        order = self.env["sale.order"].search(
            [("company_id", "=", self.company_id.id)],
            order="id desc",
            limit=1,
        )
        if not order:
            raise ValidationError(_("Für die Vorschau ist noch kein Angebot vorhanden."))
        return order.action_print_sab_offer()

    def action_reset_layout(self):
        self.write(
            {
                "paper_format": "a4",
                "orientation": "portrait",
                "margin_top_mm": 10.0,
                "margin_bottom_mm": 12.0,
                "margin_left_mm": 12.0,
                "margin_right_mm": 12.0,
                    "binding_days": 30,
            }
        )
        return True


class SaleOrderSabOfferPrinting(models.Model):
    _inherit = "sale.order"

    def _sab_offer_binding_date(self, template):
        self.ensure_one()
        base_date = fields.Date.to_date(self.date_order) or fields.Date.context_today(self)
        return fields.Date.add(base_date, days=template.binding_days or 0)

    def action_print_sab_offer(self):
        self.ensure_one()
        template = self.env["sab.offer.print.template"].effective_template(
            self.company_id
        )
        if not template:
            template = self.env["sab.offer.print.template"].create(
                {
                    "name": _("SAB-P Angebot"),
                    "company_id": self.company_id.id,
                }
            )
        report = template._ensure_runtime_report_action()
        context = {
            **dict(self.env.context),
            "sab_offer_print_template_id": template.id,
            "sab_printer_name": template.resolved_printer_name(),
        }
        return report.with_context(context).report_action(self)
