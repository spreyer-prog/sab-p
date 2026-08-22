from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DOCUMENT_FIELD_MAP = {
    "conformity": "print_conformity",
    "production_test": "print_production_test",
    "final_inspection": "print_final_inspection",
    "run_card": "print_run_card",
    "missing_parts": "print_missing_parts",
    "shipping_sheet": "print_shipping_sheet",
    "add_pack": "print_add_pack",
    "nameplate": "print_nameplate",
    "info_sheet": "print_info_sheet",
    "folder_label": "print_folder_label",
}


class SabProductionPrintWizard(models.TransientModel):
    _name = "sab.production.print.wizard"
    _description = "SAB-P Fertigungsdruck Auswahl"

    production_order_id = fields.Many2one(
        "sab.production.order",
        string="Fertigungsauftrag",
        required=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        related="production_order_id.project_id",
        string="Projekt",
        readonly=True,
    )
    order_id = fields.Many2one(
        related="production_order_id.order_id",
        string="Auftrag",
        readonly=True,
    )
    line_ids = fields.One2many(
        "sab.production.print.wizard.line",
        "wizard_id",
        string="Verteiler / physische Schränke",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        production_id = self.env.context.get("default_production_order_id") or self.env.context.get("active_id")
        if not production_id:
            return values
        production = self.env["sab.production.order"].browse(production_id).exists()
        if not production:
            return values
        production.action_prepare_production_documents()
        rows = []
        grouped = {}
        for document in production.document_ids.sorted(
            key=lambda d: (d.cabinet_bom_id.id, d.cabinet_instance_no, d.document_type, d.id)
        ):
            key = (document.cabinet_bom_id.id, document.cabinet_instance_no)
            grouped.setdefault(key, document)
        for (_cabinet_id, _instance_no), document in grouped.items():
            rows.append(
                (0, 0, {
                    "cabinet_bom_id": document.cabinet_bom_id.id,
                    "cabinet_instance_no": document.cabinet_instance_no,
                    "cabinet_instance_label": document.cabinet_instance_label,
                })
            )
        values.update({"production_order_id": production.id, "line_ids": rows})
        return values

    def action_select_all(self):
        self.ensure_one()
        if not self.line_ids:
            self.production_order_id.action_prepare_production_documents()
            raise ValidationError(
                _("Für diesen Fertigungsauftrag wurden keine druckbaren Schränke gefunden.")
            )
        self.line_ids.write(
            {field_name: True for field_name in DOCUMENT_FIELD_MAP.values()}
        )
        return self._reopen()

    def action_clear_all(self):
        self.ensure_one()
        self.line_ids.write(
            {field_name: False for field_name in DOCUMENT_FIELD_MAP.values()}
        )
        return self._reopen()

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Fertigungsdruck"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {
                **dict(self.env.context),
                "default_production_order_id": self.production_order_id.id,
                "active_id": self.production_order_id.id,
                "active_model": "sab.production.order",
            },
        }

    def _selected_documents(self):
        self.ensure_one()
        selected = self.env["sab.production.document"]
        for line in self.line_ids:
            for document_type, field_name in DOCUMENT_FIELD_MAP.items():
                if not getattr(line, field_name):
                    continue
                document = self.production_order_id.document_ids.filtered(
                    lambda d, cabinet=line.cabinet_bom_id, no=line.cabinet_instance_no, dtype=document_type:
                    d.cabinet_bom_id == cabinet
                    and d.cabinet_instance_no == no
                    and d.document_type == dtype
                )[:1]
                selected |= document
        return selected

    def action_print_selected(self):
        self.ensure_one()
        selected = self._selected_documents()
        if not selected:
            raise ValidationError(_("Bitte mindestens ein Blatt zum Drucken auswählen."))
        return selected._sab_production_report_action()


class SabProductionPrintWizardLine(models.TransientModel):
    _name = "sab.production.print.wizard.line"
    _description = "SAB-P Fertigungsdruck Auswahlzeile"
    _order = "cabinet_bom_id, cabinet_instance_no, id"

    wizard_id = fields.Many2one(
        "sab.production.print.wizard",
        required=True,
        ondelete="cascade",
    )
    cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler",
        required=True,
        readonly=True,
    )
    cabinet_instance_no = fields.Integer(string="Schrank-Nr.", required=True, readonly=True)
    cabinet_instance_label = fields.Char(string="Physischer Schrank", readonly=True)

    print_conformity = fields.Boolean(string="Konformität")
    print_production_test = fields.Boolean(string="Prüfprotokoll Fertigung")
    print_final_inspection = fields.Boolean(string="Endprüfung")
    print_run_card = fields.Boolean(string="Laufkarte")
    print_missing_parts = fields.Boolean(string="Bestellvorlage")
    print_shipping_sheet = fields.Boolean(string="Versand")
    print_add_pack = fields.Boolean(string="Beipack")
    print_nameplate = fields.Boolean(string="Typenschild")
    print_info_sheet = fields.Boolean(string="Infoschild / Prüfetikett")
    print_folder_label = fields.Boolean(string="Ordneretikett")
