from odoo import models, _
from odoo.exceptions import ValidationError

from .sab_production_print_wizard import DOCUMENT_FIELD_MAP


class SabProductionPrintWizardRepair(models.TransientModel):
    _inherit = "sab.production.print.wizard"

    def _sab_ensure_print_lines(self):
        self.ensure_one()
        valid = self.line_ids.filtered(
            lambda line: bool(line.cabinet_bom_id)
            and (line.cabinet_instance_no or 0) > 0
        )
        if valid:
            return valid

        self.production_order_id.action_prepare_production_documents()
        documents = self.production_order_id.document_ids.filtered(
            lambda document: bool(document.cabinet_bom_id)
            and (document.cabinet_instance_no or 0) > 0
        )
        grouped = {}
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

        Line = self.env["sab.production.print.wizard.line"]
        for (_cabinet_id, _instance_no), document in grouped.items():
            Line.create(
                {
                    "wizard_id": self.id,
                    "cabinet_bom_id": document.cabinet_bom_id.id,
                    "cabinet_instance_no": document.cabinet_instance_no,
                    "cabinet_instance_label": document.cabinet_instance_label,
                }
            )
        return self.line_ids.filtered(
            lambda line: bool(line.cabinet_bom_id)
            and (line.cabinet_instance_no or 0) > 0
        )

    def action_select_all(self):
        self.ensure_one()
        valid_lines = self._sab_ensure_print_lines()
        if not valid_lines:
            raise ValidationError(
                _(
                    "Für diesen Fertigungsauftrag konnten auch nach erneuter "
                    "Dokumentvorbereitung keine druckbaren Schränke ermittelt werden."
                )
            )
        valid_lines.write(
            {field_name: True for field_name in DOCUMENT_FIELD_MAP.values()}
        )
        return self._reopen()

    def _selected_documents(self):
        self.ensure_one()
        if not self.line_ids:
            self._sab_ensure_print_lines()
        return super()._selected_documents()
