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

    # ---------------------------------------------------------
    # Kalkulationskonstanten
    # ---------------------------------------------------------
    # Die Defaults bilden die im bereitgestellten Altkalkulationsbeispiel
    # sichtbaren Grundwerte ab. Sie bleiben vollständig konfigurierbar.

    sab_material_factor = fields.Float(
        string="Materialfaktor",
        default=1.0,
        config_parameter="sab_project.material_factor",
    )
    sab_aux_material_factor = fields.Float(
        string="Hilfsmaterialfaktor",
        default=1.15,
        config_parameter="sab_project.aux_material_factor",
    )
    sab_hourly_rate = fields.Float(
        string="Kalkulatorischer Stundenlohn",
        default=80.0,
        config_parameter="sab_project.hourly_rate",
    )
    sab_time_factor = fields.Float(
        string="Zeitfaktor",
        default=1.25,
        config_parameter="sab_project.time_factor",
    )
    sab_difficulty_factor = fields.Float(
        string="Schwierigkeitsfaktor",
        default=1.0,
        config_parameter="sab_project.difficulty_factor",
    )
    sab_planning_surcharge_factor = fields.Float(
        string="Planungszuschlag",
        default=1.15,
        config_parameter="sab_project.planning_surcharge_factor",
    )
    sab_packaging_factor = fields.Float(
        string="Verpackung / Transport Faktor",
        default=1.03,
        config_parameter="sab_project.packaging_factor",
    )
    sab_skonto_factor = fields.Float(
        string="Skontofaktor",
        default=1.03,
        config_parameter="sab_project.skonto_factor",
    )
    sab_margin_factor = fields.Float(
        string="Margenfaktor",
        default=1.25,
        config_parameter="sab_project.margin_factor",
    )
    sab_rebate_factor = fields.Float(
        string="Rabattfaktor",
        default=1.125,
        config_parameter="sab_project.rebate_factor",
    )
    sab_calculation_change_code = fields.Char(
        string="Freigabecode Kalkulationsänderung",
        default="1111",
        config_parameter="sab_project.calculation_change_code",
        help=(
            "Einfacher bewusster Freigabecode für protokollierte Änderungen. "
            "Dies ist kein Sicherheitskennwort, sondern eine Bedienbarriere gegen versehentliche Änderungen."
        ),
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
                raise ValidationError(
                    _("Das Projekt-Trennzeichen darf höchstens 3 Zeichen lang sein.")
                )
            if len(settings.sab_offer_separator or "") > 3:
                raise ValidationError(
                    _("Das Angebots-Trennzeichen darf höchstens 3 Zeichen lang sein.")
                )
            if not 1 <= settings.sab_project_digits <= 8:
                raise ValidationError(
                    _("Die Projektnummer muss zwischen 1 und 8 Stellen haben.")
                )
            if not 1 <= settings.sab_offer_digits <= 5:
                raise ValidationError(
                    _("Die Angebotsnummer muss zwischen 1 und 5 Stellen haben.")
                )
            if settings.sab_project_start_number < 0:
                raise ValidationError(_("Die Startnummer darf nicht negativ sein."))
            max_project_number = (10 ** settings.sab_project_digits) - 1
            if settings.sab_project_start_number > max_project_number:
                raise ValidationError(
                    _("Die Startnummer passt nicht in die gewählte Stellenzahl.")
                )

    @api.constrains(
        "sab_material_factor",
        "sab_aux_material_factor",
        "sab_hourly_rate",
        "sab_time_factor",
        "sab_difficulty_factor",
        "sab_planning_surcharge_factor",
        "sab_packaging_factor",
        "sab_skonto_factor",
        "sab_margin_factor",
        "sab_rebate_factor",
    )
    def _check_sab_calculation_settings(self):
        for settings in self:
            values = {
                "Materialfaktor": settings.sab_material_factor,
                "Hilfsmaterialfaktor": settings.sab_aux_material_factor,
                "Stundenlohn": settings.sab_hourly_rate,
                "Zeitfaktor": settings.sab_time_factor,
                "Schwierigkeitsfaktor": settings.sab_difficulty_factor,
                "Planungszuschlag": settings.sab_planning_surcharge_factor,
                "Verpackung / Transport": settings.sab_packaging_factor,
                "Skonto": settings.sab_skonto_factor,
                "Marge": settings.sab_margin_factor,
                "Rabatt": settings.sab_rebate_factor,
            }
            for label, value in values.items():
                if value < 0:
                    raise ValidationError(_("%s darf nicht negativ sein.", label))
