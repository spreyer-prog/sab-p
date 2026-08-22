from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DOCUMENT_TYPES = [
    ("conformity", "Konformitätserklärung"),
    ("production_test", "Prüfprotokoll Fertigung"),
    ("final_inspection", "Prüfprotokoll Endkontrolle"),
    ("run_card", "Laufkarte"),
    ("missing_parts", "Bestellung Fehlteile"),
    ("shipping_sheet", "Blatt Versand"),
    ("add_pack", "Beipackzettel"),
    ("nameplate", "Typenschild"),
    ("info_sheet", "Infoschild"),
    ("folder_label", "Ordneretikett"),
]


class SabProductionPrintProfile(models.Model):
    _name = "sab.production.print.profile"
    _description = "SAB-P Druckprofil Fertigungsblatt"
    _order = "user_id, document_type, id"

    user_id = fields.Many2one(
        "res.users",
        string="Benutzer",
        ondelete="cascade",
        index=True,
        help="Leer = Firmenstandard. Mit Benutzer = persönlicher Override.",
    )
    document_type = fields.Selection(DOCUMENT_TYPES, string="Blatt", required=True, index=True)
    paper_kind = fields.Selection(
        [
            ("a4", "DIN A4"),
            ("custom", "Sonderformat / Etikett"),
        ],
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
    width_mm = fields.Float(string="Breite (mm)", digits=(16, 1), default=210.0)
    height_mm = fields.Float(string="Höhe (mm)", digits=(16, 1), default=297.0)
    margin_top_mm = fields.Float(string="Rand oben (mm)", digits=(16, 1), default=5.0)
    margin_bottom_mm = fields.Float(string="Rand unten (mm)", digits=(16, 1), default=5.0)
    margin_left_mm = fields.Float(string="Rand links (mm)", digits=(16, 1), default=5.0)
    margin_right_mm = fields.Float(string="Rand rechts (mm)", digits=(16, 1), default=5.0)
    printer_name = fields.Char(
        string="Drucker",
        help="Arbeitsplatz-/IoT-Druckername. Wird benutzerspezifisch gespeichert.",
    )
    scale_percent = fields.Float(string="Skalierung (%)", digits=(16, 1), default=100.0)

    _profile_unique = models.Constraint(
        "UNIQUE(user_id, document_type)",
        "Für diesen Benutzer existiert bereits ein Druckprofil für dieses Blatt.",
    )

    @api.constrains("width_mm", "height_mm", "scale_percent")
    def _check_geometry(self):
        for profile in self:
            if profile.width_mm <= 0 or profile.height_mm <= 0:
                raise ValidationError(_("Breite und Höhe des Druckformats müssen größer 0 sein."))
            if profile.scale_percent <= 0 or profile.scale_percent > 200:
                raise ValidationError(_("Die Druckskalierung muss zwischen 0 und 200 Prozent liegen."))

    @api.model
    def effective_profile(self, document_type, user=None):
        user = user or self.env.user
        personal = self.search(
            [("user_id", "=", user.id), ("document_type", "=", document_type)],
            limit=1,
        )
        if personal:
            return personal
        return self.search(
            [("user_id", "=", False), ("document_type", "=", document_type)],
            limit=1,
        )
