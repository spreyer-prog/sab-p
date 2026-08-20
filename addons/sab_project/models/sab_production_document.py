from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


PRODUCTION_DOCUMENT_TYPES = [
    ("conformity", "Konformitätserklärung"),
    ("production_test", "Prüfprotokoll Fertigung"),
    ("final_inspection", "Prüfprotokoll Endkontrolle"),
    ("run_card", "Laufkarte"),
    ("missing_parts", "Bestellung Fehlteile"),
    ("nameplate", "Typenschild"),
    ("info_sheet", "Infoschild / Prüfhinweis"),
    ("add_pack", "Beipackzettel"),
]


class SabProductionDocument(models.Model):
    _name = "sab.production.document"
    _description = "SAB-P Fertigungsdokument"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "project_id, cabinet_bom_id, cabinet_instance_no, document_type, id"

    name = fields.Char(string="Dokument", compute="_compute_name", store=True)
    production_order_id = fields.Many2one(
        "sab.production.order",
        string="Fertigungsauftrag",
        required=True,
        ondelete="cascade",
        index=True,
    )
    order_id = fields.Many2one(
        related="production_order_id.order_id",
        string="Auftrag",
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        related="production_order_id.project_id",
        string="Projekt",
        store=True,
        readonly=True,
    )
    cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler",
        required=True,
        ondelete="restrict",
        domain="[('order_id', '=', order_id), ('bom_scope', '=', 'cabinet')]",
        index=True,
    )
    cabinet_line_id = fields.Many2one(
        related="cabinet_bom_id.cabinet_line_id",
        string="Schaltschrankposition",
        store=True,
        readonly=True,
    )
    cabinet_product_id = fields.Many2one(
        "product.product",
        string="Schrankprodukt (Snapshot)",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
        help="Produkt, aus dessen Schrank-/Typenschild-Stammdaten dieses Dokument vorbereitet wurde.",
    )
    cabinet_instance_no = fields.Integer(
        string="Schrank-Nr.",
        required=True,
        default=1,
        readonly=True,
        index=True,
        help="Laufende Nummer des physischen Schranks innerhalb derselben Schrankposition.",
    )
    cabinet_instance_count = fields.Integer(
        string="Schrankanzahl",
        required=True,
        default=1,
        readonly=True,
    )
    cabinet_instance_label = fields.Char(
        string="Physischer Schrank",
        compute="_compute_cabinet_instance_label",
        store=True,
    )
    document_type = fields.Selection(
        PRODUCTION_DOCUMENT_TYPES,
        string="Dokumentart",
        required=True,
        index=True,
    )
    state = fields.Selection(
        [("draft", "Vorbereitet"), ("completed", "Ausgefüllt"), ("printed", "Gedruckt")],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )

    project_reference = fields.Char(string="Auftragsnummer", compute="_compute_prefill", store=True)
    project_name = fields.Char(string="Projekt", compute="_compute_prefill", store=True)
    customer_name = fields.Char(string="Kunde", compute="_compute_prefill", store=True)
    customer_street = fields.Char(string="Straße", compute="_compute_prefill", store=True)
    customer_zip = fields.Char(string="PLZ", compute="_compute_prefill", store=True)
    customer_city = fields.Char(string="Ort", compute="_compute_prefill", store=True)
    responsible_name = fields.Char(string="Bearbeiter", compute="_compute_prefill", store=True)
    delivery_date = fields.Date(string="Liefertermin", compute="_compute_prefill", store=True)
    cabinet_name = fields.Char(string="Verteilung", compute="_compute_prefill", store=True)

    cabinet_width_mm = fields.Float(string="Schrankbreite (mm)", digits=(16, 1))
    type_designation = fields.Char(string="Typenbezeichnung")
    cabinet_type = fields.Char(string="Schranktyp")
    construction_year = fields.Integer(string="Baujahr", default=lambda self: fields.Date.today().year)
    standard_family = fields.Char(string="DIN EN", default="61439")
    standard_part = fields.Char(string="Teil", default="3")
    rated_voltage = fields.Float(string="Bemessungsspannung (V)", default=400.0)
    rated_current = fields.Float(string="Bemessungsstrom (A)", default=100.0)
    frequency = fields.Float(string="Frequenz (Hz)", default=50.0)
    busbar_current = fields.Float(string="Sammelschiene (A)")
    protection_class = fields.Char(string="Schutzklasse", default="2")
    ip_rating = fields.Char(string="IP-Schutzart")

    test_voltage = fields.Float(string="Prüfspannung Vtest (V)")
    insulation_resistance = fields.Float(string="Ergebnis Riso (MOhm)")
    protective_conductor_resistance = fields.Float(string="Ergebnis Rpe (Ohm)")
    inspector_name = fields.Char(string="Prüfer / Kennung")
    inspection_date = fields.Date(string="Prüfdatum")
    next_maintenance_date = fields.Date(string="Nächster vorgeschlagener Wartungstermin")
    note = fields.Text(string="Bemerkung")

    _document_per_cabinet = models.Constraint(
        "UNIQUE(production_order_id, cabinet_bom_id, cabinet_instance_no, document_type)",
        "Diese Dokumentart existiert für diesen physischen Schrank bereits.",
    )

    @api.depends("cabinet_name", "cabinet_instance_no", "cabinet_instance_count")
    def _compute_cabinet_instance_label(self):
        for record in self:
            base = record.cabinet_name or record.cabinet_bom_id.name or _("Schrank")
            if (record.cabinet_instance_count or 1) > 1:
                record.cabinet_instance_label = "%s – %s/%s" % (
                    base,
                    record.cabinet_instance_no,
                    record.cabinet_instance_count,
                )
            else:
                record.cabinet_instance_label = base

    @api.depends(
        "document_type",
        "project_reference",
        "cabinet_name",
        "cabinet_instance_no",
        "cabinet_instance_count",
    )
    def _compute_name(self):
        labels = dict(PRODUCTION_DOCUMENT_TYPES)
        for record in self:
            parts = [labels.get(record.document_type, _("Fertigungsdokument"))]
            if record.project_reference:
                parts.append(record.project_reference)
            if record.cabinet_name:
                cabinet_label = record.cabinet_name
                if (record.cabinet_instance_count or 1) > 1:
                    cabinet_label = "%s %s/%s" % (
                        cabinet_label,
                        record.cabinet_instance_no,
                        record.cabinet_instance_count,
                    )
                parts.append(cabinet_label)
            record.name = " – ".join(parts)

    @api.depends(
        "production_order_id.order_id",
        "production_order_id.project_id",
        "production_order_id.responsible_user_id",
        "production_order_id.delivery_date",
        "cabinet_bom_id.cabinet_line_id.description",
    )
    def _compute_prefill(self):
        for record in self:
            order = record.order_id
            project = record.project_id
            customer = order.partner_id if order else False
            reference = (
                (order.sab_offer_reference if order else False)
                or (project.sab_project_reference if project else False)
                or (order.name if order else False)
            )
            record.project_reference = reference or False
            record.project_name = project.name if project else False
            record.customer_name = customer.name if customer else False
            record.customer_street = customer.street if customer else False
            record.customer_zip = customer.zip if customer else False
            record.customer_city = customer.city if customer else False
            record.responsible_name = (
                record.production_order_id.responsible_user_id.name
                if record.production_order_id.responsible_user_id
                else False
            )
            record.delivery_date = record.production_order_id.delivery_date
            record.cabinet_name = (
                record.cabinet_bom_id.cabinet_line_id.description
                if record.cabinet_bom_id.cabinet_line_id
                else record.cabinet_bom_id.name
            )

    @api.constrains("cabinet_bom_id", "production_order_id")
    def _check_same_order(self):
        for record in self:
            if record.cabinet_bom_id.order_id != record.production_order_id.order_id:
                raise ValidationError(
                    _("Der ausgewählte Verteiler gehört nicht zum Fertigungsauftrag.")
                )

    @api.constrains("cabinet_instance_no", "cabinet_instance_count")
    def _check_cabinet_instance(self):
        for record in self:
            if record.cabinet_instance_count < 1:
                raise ValidationError(_("Die Schrankanzahl muss mindestens 1 sein."))
            if not 1 <= record.cabinet_instance_no <= record.cabinet_instance_count:
                raise ValidationError(
                    _("Die laufende Schranknummer muss zwischen 1 und der Schrankanzahl liegen.")
                )

    def action_mark_completed(self):
        self.write({"state": "completed"})
        return True

    def action_mark_printed(self):
        self.write({"state": "printed"})
        return True


class SabProductionOrderDocuments(models.Model):
    _inherit = "sab.production.order"

    document_ids = fields.One2many(
        "sab.production.document",
        "production_order_id",
        string="Protokolle & Fertigungsdokumente",
        copy=False,
    )
    document_count = fields.Integer(
        string="Dokumente",
        compute="_compute_document_count",
    )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    def _sab_physical_cabinet_count(self, cabinet_bom):
        quantity = (
            cabinet_bom.cabinet_line_id.quantity
            if cabinet_bom.cabinet_line_id
            else 1.0
        ) or 1.0
        rounded = round(quantity)
        if quantity <= 0 or abs(quantity - rounded) > 1e-9:
            raise ValidationError(
                _(
                    "Die Schrankmenge von '%s' muss für Fertigungsdokumente eine positive ganze Zahl sein."
                )
                % (cabinet_bom.name,)
            )
        return int(rounded)

    def _sab_cabinet_product_snapshot_values(self, cabinet_bom):
        cabinet_line = cabinet_bom.cabinet_line_id
        product = cabinet_line.odoo_product_id if cabinet_line else False
        if not product:
            return {}
        template = product.product_tmpl_id
        if not template.sab_is_cabinet_product:
            raise ValidationError(
                _(
                    "Das an '%s' ausgewählte Produkt '%s' ist nicht als Schrank / Gehäuse gekennzeichnet."
                )
                % (cabinet_bom.name, product.display_name)
            )
        return {
            "cabinet_product_id": product.id,
            "cabinet_width_mm": template.sab_cabinet_width_mm or 0.0,
            "type_designation": template.sab_nameplate_type_designation or False,
            "cabinet_type": template.sab_nameplate_cabinet_type or False,
            "standard_family": template.sab_nameplate_standard_family or "61439",
            "standard_part": template.sab_nameplate_standard_part or "3",
            "rated_voltage": template.sab_nameplate_rated_voltage or 0.0,
            "rated_current": template.sab_nameplate_rated_current or 0.0,
            "frequency": template.sab_nameplate_frequency or 0.0,
            "busbar_current": template.sab_nameplate_busbar_current or 0.0,
            "protection_class": template.sab_nameplate_protection_class or False,
            "ip_rating": template.sab_nameplate_ip_rating or False,
            "note": template.sab_nameplate_notes or False,
        }

    def action_prepare_production_documents(self):
        Document = self.env["sab.production.document"]
        for production in self:
            cabinet_boms = self.env["sab.project.bom"].search(
                [
                    ("order_id", "=", production.order_id.id),
                    ("bom_scope", "=", "cabinet"),
                ],
                order="id",
            )
            if not cabinet_boms:
                raise ValidationError(
                    _("Für den Auftrag sind keine Verteilerstücklisten vorhanden.")
                )
            existing = {
                (
                    document.cabinet_bom_id.id,
                    document.cabinet_instance_no,
                    document.document_type,
                )
                for document in production.document_ids
            }
            for cabinet_bom in cabinet_boms:
                cabinet_count = production._sab_physical_cabinet_count(cabinet_bom)
                snapshot_values = production._sab_cabinet_product_snapshot_values(cabinet_bom)
                for cabinet_instance_no in range(1, cabinet_count + 1):
                    for document_type, _label in PRODUCTION_DOCUMENT_TYPES:
                        key = (
                            cabinet_bom.id,
                            cabinet_instance_no,
                            document_type,
                        )
                        if key in existing:
                            continue
                        Document.create(
                            {
                                "production_order_id": production.id,
                                "cabinet_bom_id": cabinet_bom.id,
                                "cabinet_instance_no": cabinet_instance_no,
                                "cabinet_instance_count": cabinet_count,
                                "document_type": document_type,
                                **snapshot_values,
                            }
                        )
                        existing.add(key)
        return self.action_view_production_documents()

    def action_view_production_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Protokolle & Fertigungsdokumente"),
            "res_model": "sab.production.document",
            "view_mode": "list,form",
            "domain": [("production_order_id", "=", self.id)],
            "context": {"default_production_order_id": self.id},
            "target": "current",
        }
