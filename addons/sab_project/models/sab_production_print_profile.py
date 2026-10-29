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
    _order = "user_id, sequence, document_type, id"

    active = fields.Boolean(string="Aktiv", default=True)
    sequence = fields.Integer(
        string="Druckreihenfolge",
        default=10,
        help="Legt die Reihenfolge beim Gesamtdruck fest.",
    )

    user_id = fields.Many2one(
        "res.users",
        string="Benutzer",
        ondelete="cascade",
        index=True,
        help="Leer = Firmenstandard. Mit Benutzer = persönlicher Override.",
    )
    document_type = fields.Selection(DOCUMENT_TYPES, string="Blatt", required=True, index=True)
    paper_kind = fields.Selection(
        [("a4", "DIN A4"), ("custom", "Sonderformat / Etikett")],
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
        help=(
            "Arbeitsplatz-/IoT-Druckername. Bleibt das Feld leer, wird der "
            "in den Einstellungen hinterlegte PDF-Standarddrucker verwendet."
        ),
    )
    scale_percent = fields.Float(string="Skalierung (%)", digits=(16, 1), default=100.0)
    copies = fields.Integer(string="Exemplare", default=1)

    _profile_unique = models.Constraint(
        "UNIQUE(user_id, document_type)",
        "Für diesen Benutzer existiert bereits ein Druckprofil für dieses Blatt.",
    )

    @api.constrains("width_mm", "height_mm", "scale_percent", "copies")
    def _check_geometry(self):
        for profile in self:
            if profile.width_mm <= 0 or profile.height_mm <= 0:
                raise ValidationError(_("Breite und Höhe des Druckformats müssen größer 0 sein."))
            if profile.scale_percent <= 0 or profile.scale_percent > 200:
                raise ValidationError(_("Die Druckskalierung muss zwischen 0 und 200 Prozent liegen."))
            if profile.copies < 1 or profile.copies > 20:
                raise ValidationError(_("Die Anzahl der Exemplare muss zwischen 1 und 20 liegen."))

    @api.model
    def _sab_original_profile_values(self):
        """Return the approved physical format for every uploaded original."""
        return {
            "conformity": dict(paper_kind="a4", orientation="portrait", width_mm=210.0, height_mm=297.0, sequence=10),
            "run_card": dict(paper_kind="a4", orientation="portrait", width_mm=210.0, height_mm=297.0, sequence=20),
            "production_test": dict(paper_kind="a4", orientation="portrait", width_mm=210.0, height_mm=297.0, sequence=30),
            "final_inspection": dict(paper_kind="a4", orientation="portrait", width_mm=210.0, height_mm=297.0, sequence=40),
            "missing_parts": dict(paper_kind="a4", orientation="landscape", width_mm=297.0, height_mm=210.0, sequence=50),
            "shipping_sheet": dict(paper_kind="a4", orientation="landscape", width_mm=297.0, height_mm=210.0, sequence=60),
            "add_pack": dict(paper_kind="a4", orientation="landscape", width_mm=297.0, height_mm=210.0, sequence=70),
            "nameplate": dict(paper_kind="custom", orientation="landscape", width_mm=265.0, height_mm=176.0, sequence=80),
            "info_sheet": dict(paper_kind="custom", orientation="landscape", width_mm=265.0, height_mm=176.0, sequence=90),
            "folder_label": dict(paper_kind="custom", orientation="portrait", width_mm=61.0, height_mm=192.0, sequence=100),
        }

    @api.model
    def _sab_apply_original_standard_profiles(self):
        """Synchronise company defaults with the actual uploaded legacy PDFs.

        Every document owns its page geometry. Personal profiles stay untouched.
        """
        defaults = self._sab_original_profile_values()
        for document_type, values in defaults.items():
            values = {
                **values,
                "margin_top_mm": 0.0,
                "margin_bottom_mm": 0.0,
                "margin_left_mm": 0.0,
                "margin_right_mm": 0.0,
                "scale_percent": 100.0,
                "copies": 1,
                "active": True,
            }
            profile = self.sudo().search(
                [("user_id", "=", False), ("document_type", "=", document_type)],
                limit=1,
            )
            if profile:
                profile.write(values)
            else:
                self.sudo().create({"document_type": document_type, **values})
        return True

    def action_reset_to_sab_original(self):
        defaults = self._sab_original_profile_values()
        for profile in self:
            values = defaults.get(profile.document_type)
            if not values:
                continue
            profile.write(
                {
                    **values,
                    "margin_top_mm": 0.0,
                    "margin_bottom_mm": 0.0,
                    "margin_left_mm": 0.0,
                    "margin_right_mm": 0.0,
                    "scale_percent": 100.0,
                    "copies": 1,
                    "active": True,
                }
            )
        return True

    def action_test_preview(self):
        self.ensure_one()
        document = self.env["sab.production.document"].search(
            [("document_type", "=", self.document_type)],
            order="id desc",
            limit=1,
        )
        if not document:
            raise ValidationError(
                _("Für diese Vorlage ist noch kein Fertigungsdokument für eine Vorschau vorhanden.")
            )
        return document.with_context(sab_print_profile_id=self.id)._sab_production_report_action()

    @api.model
    def effective_profile(self, document_type, user=None):
        user = user or self.env.user
        personal = self.search(
            [("user_id", "=", user.id), ("document_type", "=", document_type)],
            limit=1,
        )
        if personal and personal.active:
            return personal
        return self.search(
            [
                ("user_id", "=", False),
                ("document_type", "=", document_type),
                ("active", "=", True),
            ],
            limit=1,
        )

    def resolved_printer_name(self):
        self.ensure_one()
        return self.printer_name or self.env["ir.config_parameter"].sudo().get_param(
            "sab_project.default_pdf_printer",
            "PDF-Drucker",
        )

    def _ensure_runtime_report_action(self):
        """Return a private report action using exactly this profile's geometry."""
        self.ensure_one()
        report_name = {
            "conformity": "sab_project.report_sab_conformity_studio",
            "run_card": "sab_project.report_sab_run_card_studio",
            "production_test": "sab_project.report_sab_production_test_studio",
            "final_inspection": "sab_project.report_sab_final_inspection_studio",
            "missing_parts": "sab_project.report_sab_missing_parts_studio",
            "shipping_sheet": "sab_project.report_sab_shipping_sheet_studio",
            "add_pack": "sab_project.report_sab_add_pack_studio",
            "nameplate": "sab_project.report_sab_nameplate_studio",
            "info_sheet": "sab_project.report_sab_info_sheet_studio",
            "folder_label": "sab_project.report_sab_folder_label_studio",
        }.get(self.document_type, "sab_project.report_sab_production_document")
        profile_key = "SAB-P Druckprofil %s" % self.id
        Paperformat = self.env["report.paperformat"].sudo()
        paperformat = Paperformat.search([("name", "=", profile_key)], limit=1)
        # wkhtmltopdf rotates custom dimensions once more for Landscape.  Store
        # the short edge as page_width and the long edge as page_height, then
        # let the orientation perform exactly one rotation.  Otherwise a
        # configured 297 x 210 mm landscape sheet is emitted as A4 portrait.
        short_edge = min(self.width_mm, self.height_mm)
        long_edge = max(self.width_mm, self.height_mm)
        render_dpi = 90 if self.document_type in {"folder_label", "conformity"} else 77
        paper_values = {
            "name": profile_key,
            "format": "custom",
            "page_width": short_edge,
            "page_height": long_edge,
            "orientation": "Landscape" if self.orientation == "landscape" else "Portrait",
            "margin_top": self.margin_top_mm,
            "margin_bottom": self.margin_bottom_mm,
            "margin_left": self.margin_left_mm,
            "margin_right": self.margin_right_mm,
            # Odoo/wkhtmltopdf renders the full-page production canvases at
            # about 85.3 % when using 90 DPI. 77 DPI compensates that factor.
            # Folder label and conformity use flowing layouts calibrated at
            # the regular 90 DPI and must not receive that correction.
            "dpi": render_dpi,
        }
        if paperformat:
            paperformat.write(paper_values)
        else:
            paperformat = Paperformat.create(paper_values)

        action_name = "%s Report" % profile_key
        Report = self.env["ir.actions.report"].sudo()
        report = Report.search(
            [
                ("name", "=", action_name),
                ("model", "=", "sab.production.document"),
            ],
            limit=1,
        )
        report_values = {
            "name": action_name,
            "model": "sab.production.document",
            "report_type": "qweb-pdf",
            "report_name": report_name,
            "report_file": report_name,
            "paperformat_id": paperformat.id,
            "print_report_name": "object._sab_pdf_filename()",
        }
        if report:
            report.write(report_values)
        else:
            report = Report.create(report_values)
        return report
