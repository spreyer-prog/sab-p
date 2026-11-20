from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DOCUMENT_FIELD_MAP = {
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
    def _sab_print_rows_for_production(self, production):
        grouped = {}
        documents = production.document_ids.filtered(
            lambda document: bool(document.cabinet_bom_id)
            and (document.cabinet_instance_no or 0) > 0
        )
        for document in documents.sorted(
            key=lambda d: (
                d.cabinet_bom_id.id,
                d.cabinet_instance_no,
                d.document_type,
                d.id,
            )
        ):
            key = (document.cabinet_bom_id.id, document.cabinet_instance_no)
            grouped.setdefault(key, document)
        return [
            {
                "cabinet_bom_id": document.cabinet_bom_id.id,
                "cabinet_instance_no": document.cabinet_instance_no,
                "cabinet_instance_label": document.cabinet_instance_label,
            }
            for document in grouped.values()
        ]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        production_id = (
            self.env.context.get("default_production_order_id")
            or self.env.context.get("active_id")
        )
        if not production_id:
            return values
        production = self.env["sab.production.order"].browse(production_id).exists()
        if not production:
            return values
        production.action_prepare_production_documents()
        rows = self._sab_print_rows_for_production(production)
        values.update(
            {
                "production_order_id": production.id,
                "line_ids": [(0, 0, row) for row in rows],
            }
        )
        return values

    def _sab_refresh_print_rows(self):
        self.ensure_one()
        production = self.production_order_id
        production.action_prepare_production_documents()
        rows = self._sab_print_rows_for_production(production)
        existing_keys = {
            (line.cabinet_bom_id.id, line.cabinet_instance_no)
            for line in self.line_ids
            if line.cabinet_bom_id and line.cabinet_instance_no > 0
        }
        Line = self.env["sab.production.print.wizard.line"]
        for row in rows:
            key = (row["cabinet_bom_id"], row["cabinet_instance_no"])
            if key in existing_keys:
                continue
            Line.create({"wizard_id": self.id, **row})
            existing_keys.add(key)
        self.invalidate_recordset(["line_ids"])
        return self.line_ids.filtered(
            lambda line: bool(line.cabinet_bom_id)
            and (line.cabinet_instance_no or 0) > 0
        )

    def action_select_all(self):
        self.ensure_one()
        valid_lines = self._sab_refresh_print_rows()
        if not valid_lines:
            raise ValidationError(
                _(
                    "Für diesen Fertigungsauftrag konnten auch nach erneuter Dokumenterzeugung keine druckbaren Schränke gefunden werden. Bitte prüfen, ob zum Auftrag Verteilerstücklisten vorhanden sind."
                )
            )
        valid_lines.write(
            {field_name: True for field_name in DOCUMENT_FIELD_MAP.values()}
        )
        return self._reopen()

    def action_clear_all(self):
        self.ensure_one()
        valid_lines = self.line_ids.filtered(
            lambda line: bool(line.cabinet_bom_id)
            and (line.cabinet_instance_no or 0) > 0
        )
        valid_lines.write(
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
        valid_lines = self.line_ids.filtered(
            lambda line: bool(line.cabinet_bom_id)
            and (line.cabinet_instance_no or 0) > 0
        )
        for line in valid_lines:
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

        jobs = selected._sab_individual_print_jobs()

        return {
            "type": "ir.actions.client",
            "tag": "sab_production_multi_print",
            "name": _("Fertigungsdruck"),
            "target": "main",
            "params": {
                "jobs": jobs,
                "menu_id": self.env.ref(
                    "sab_project.sab_production_document_menu"
                ).id,
            },
        }


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
        required=False,
        readonly=True,
    )
    cabinet_instance_no = fields.Integer(
        string="Schrank-Nr.", required=False, readonly=True
    )
    cabinet_instance_label = fields.Char(
        string="Physischer Schrank", readonly=True
    )

    # Aus Kompatibilitaetsgruenden bleibt das alte technische Feld erhalten.
    # Die Konformitaetserklaerung wird jedoch nur noch unter Protokolle gedruckt.
    print_conformity = fields.Boolean(string="Konformität", default=False)
    print_production_test = fields.Boolean(string="Prüfprotokoll Fertigung")
    print_final_inspection = fields.Boolean(string="Endprüfung")
    print_run_card = fields.Boolean(string="Laufkarte")
    print_missing_parts = fields.Boolean(string="Bestellvorlage")
    print_shipping_sheet = fields.Boolean(string="Versand")
    print_add_pack = fields.Boolean(string="Beipack")
    print_nameplate = fields.Boolean(string="Typenschild")
    print_info_sheet = fields.Boolean(string="Infoschild / Prüfetikett")
    print_folder_label = fields.Boolean(string="Ordneretikett")
