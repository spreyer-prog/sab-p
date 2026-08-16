from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabProjectDocument(models.Model):
    _name = "sab.project.document"
    _description = "SAB-P Projektdokument"
    _order = "project_id, document_type, name, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Dokument", required=True, tracking=True)
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projekt",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    document_type = fields.Selection(
        selection=[
            ("customer_order", "Kundenbestellung"),
            ("drawing", "Zeichnung / Plan"),
            ("parts_list", "Stückliste"),
            ("test_report", "Prüfprotokoll"),
            ("declaration", "Errichter-/Konformitätserklärung"),
            ("delivery_note", "Lieferschein"),
            ("photo", "Foto"),
            ("correspondence", "Korrespondenz"),
            ("other", "Sonstiges"),
        ],
        string="Dokumentart",
        required=True,
        default="other",
        index=True,
        tracking=True,
    )
    version = fields.Integer(string="Version", required=True, default=1, readonly=True)
    revision_of_id = fields.Many2one(
        comodel_name="sab.project.document",
        string="Revision von",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    revision_ids = fields.One2many(
        comodel_name="sab.project.document",
        inverse_name="revision_of_id",
        string="Revisionen",
        readonly=True,
    )
    state = fields.Selection(
        selection=[("draft", "Entwurf"), ("released", "Freigegeben"), ("obsolete", "Überholt")],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    file_data = fields.Binary(string="Datei", attachment=True, required=True)
    file_name = fields.Char(string="Dateiname", required=True)
    note = fields.Text(string="Interne Hinweise")
    released_at = fields.Datetime(string="Freigegeben am", readonly=True)
    released_by_id = fields.Many2one(comodel_name="res.users", string="Freigegeben von", readonly=True)

    customer_visible = fields.Boolean(
        string="Für Kundenportal freigegeben",
        default=False,
        copy=False,
        tracking=True,
    )
    customer_title = fields.Char(
        string="Bezeichnung im Kundenportal",
        help="Optional. Wenn leer, wird die Dokumentbezeichnung verwendet.",
    )
    customer_note = fields.Text(string="Hinweis für Kunden")
    customer_released_at = fields.Datetime(string="Kundenfreigabe am", readonly=True)
    customer_released_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Kundenfreigabe von",
        readonly=True,
    )

    def action_release(self):
        for record in self:
            if record.state != "draft":
                continue
            if not record.file_data:
                raise ValidationError(_("Ein Dokument ohne Datei kann nicht freigegeben werden."))
            record.write({
                "state": "released",
                "released_at": fields.Datetime.now(),
                "released_by_id": self.env.user.id,
            })
        return True

    def action_release_to_customer(self):
        for record in self:
            if record.state != "released":
                raise ValidationError(_("Nur intern freigegebene Dokumente dürfen für Kunden freigegeben werden."))
            if not record.project_id.partner_id:
                raise ValidationError(_("Dem Projekt muss vor der Kundenfreigabe ein Kunde zugeordnet sein."))
            record.write({
                "customer_visible": True,
                "customer_released_at": fields.Datetime.now(),
                "customer_released_by_id": self.env.user.id,
            })
        return True

    def action_withdraw_customer_release(self):
        self.write({"customer_visible": False})
        return True

    def action_create_revision(self):
        self.ensure_one()
        if self.state != "released":
            raise ValidationError(_("Eine Revision kann nur von einem freigegebenen Dokument erzeugt werden."))
        revision = self.copy({
            "revision_of_id": self.id,
            "version": self.version + 1,
            "state": "draft",
            "released_at": False,
            "released_by_id": False,
            "customer_visible": False,
            "customer_released_at": False,
            "customer_released_by_id": False,
        })
        self.write({"state": "obsolete", "customer_visible": False})
        return {
            "type": "ir.actions.act_window",
            "name": _("Dokumentrevision"),
            "res_model": "sab.project.document",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }

    def write(self, vals):
        protected = {"project_id", "document_type", "version", "file_data", "file_name"}
        if any(record.state in ("released", "obsolete") for record in self) and protected.intersection(vals):
            raise ValidationError(_("Freigegebene oder überholte Dokumentstände dürfen nicht verändert werden. Erstellen Sie eine Revision."))
        if vals.get("customer_visible") and any(record.state != "released" for record in self):
            raise ValidationError(_("Nur intern freigegebene Dokumente dürfen im Kundenportal sichtbar sein."))
        return super().write(vals)

    def unlink(self):
        if any(record.state != "draft" for record in self):
            raise ValidationError(_("Freigegebene oder überholte Dokumentstände dürfen nicht gelöscht werden."))
        return super().unlink()
