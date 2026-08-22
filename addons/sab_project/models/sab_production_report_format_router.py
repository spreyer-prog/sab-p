from odoo import models


class SabProductionDocumentFormatRouter(models.Model):
    _inherit = "sab.production.document"

    def _sab_production_report_action(self):
        documents = self.exists()
        if len(documents) != 1:
            return super()._sab_production_report_action()

        document = documents[0]
        report_xmlid = {
            "run_card": "sab_project.action_report_sab_production_landscape",
            "production_test": "sab_project.action_report_sab_production_landscape",
            "final_inspection": "sab_project.action_report_sab_production_landscape",
            "info_sheet": "sab_project.action_report_sab_info_sheet_native",
            "folder_label": "sab_project.action_report_sab_folder_label_native",
        }.get(document.document_type)
        if not report_xmlid:
            return super()._sab_production_report_action()

        report = self.env.ref(report_xmlid)
        report_context = {
            **dict(self.env.context),
            "active_model": self._name,
            "active_id": document.id,
            "active_ids": [document.id],
            "sab_multi_production_print": False,
            "sab_native_sheet_format": True,
        }
        filename = document.with_context(report_context)._sab_pdf_filename()
        action = report.read()[0]
        action.update(
            {
                "type": "ir.actions.report",
                "name": filename,
                "report_type": report.report_type,
                "report_name": report.report_name,
                "report_file": report.report_file,
                "context": report_context,
            }
        )
        return action
