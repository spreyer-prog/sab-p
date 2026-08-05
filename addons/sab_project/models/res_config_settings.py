from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sab_project_prefix = fields.Char(
        string="Präfix",
        default="A",
        config_parameter="sab_project.project_prefix",
        help="Buchstaben oder Zeichen vor der Jahreszahl, z. B. A.",
    )
    sab_year_digits = fields.Selection(
        selection=[
            ("2", "Zweistellig, z. B. 26"),
            ("4", "Vierstellig, z. B. 2026"),
        ],
        string="Jahresformat",
        default="2",
        config_parameter="sab_project.year_digits",
        required=True,
    )
    sab_project_separator = fields.Char(
        string="Trennzeichen Projekt",
        default=".",
        config_parameter="sab_project.project_separator",
        help="Trennzeichen zwischen Jahr und laufender Projektnummer.",
    )
    sab_project_digits = fields.Integer(
        string="Stellen Projektnummer",
        default=4,
        config_parameter="sab_project.project_digits",
        required=True,
    )
    sab_project_start_number = fields.Integer(
        string="Startnummer neues Jahr",
        default=1,
        config_parameter="sab_project.project_start_number",
        required=True,
        help="Wird nur verwendet, wenn für ein Jahr erstmals eine Nummer vergeben wird.",
    )
    sab_offer_separator = fields.Char(
        string="Trennzeichen Angebot",
        default="-",
        config_parameter="sab_project.offer_separator",
    )
    sab_offer_digits = fields.Integer(
        string="Stellen Angebotsnummer",
        default=2,
        config_parameter="sab_project.offer_digits",
        required=True,
    )

    @api.constrains(
        "sab_project_prefix",
        "sab_project_separator",
        "sab_project_digits",
        "sab_project_start_number",
        "sab_offer_separator",
        "sab_offer_digits",
    )
    def _check_sab_numbering_settings(self):
        for settings in self:
            if not settings.sab_project_prefix:
                raise ValidationError(_("Das Präfix darf nicht leer sein."))
            if len(settings.sab_project_prefix) > 5:
                raise ValidationError(_("Das Präfix darf höchstens 5 Zeichen lang sein."))
            if len(settings.sab_project_separator or "") > 3:
                raise ValidationError(_("Das Projekt-Trennzeichen darf höchstens 3 Zeichen lang sein."))
            if len(settings.sab_offer_separator or "") > 3:
                raise ValidationError(_("Das Angebots-Trennzeichen darf höchstens 3 Zeichen lang sein."))
            if not 1 <= settings.sab_project_digits <= 8:
                raise ValidationError(_("Die Projektnummer muss zwischen 1 und 8 Stellen haben."))
            if not 1 <= settings.sab_offer_digits <= 5:
                raise ValidationError(_("Die Angebotsnummer muss zwischen 1 und 5 Stellen haben."))
            if settings.sab_project_start_number < 0:
                raise ValidationError(_("Die Startnummer darf nicht negativ sein."))
            max_project_number = (10 ** settings.sab_project_digits) - 1
            if settings.sab_project_start_number > max_project_number:
                raise ValidationError(
                    _("Die Startnummer passt nicht in die gewählte Stellenzahl.")
                )
