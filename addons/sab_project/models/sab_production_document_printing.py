import base64
import re
from functools import lru_cache

from odoo import fields, models, _
from odoo.tools import file_open


EXTRA_PRODUCTION_DOCUMENT_TYPES = [
    ("shipping_sheet", "Blatt Versand"),
    ("folder_label", "Ordneretikett"),
]

# Diese früher separat geführten Drucktypen entfallen vollständig.
# Das ehemalige Prüfetikett ist fachlich identisch mit dem Infoschild.
OBSOLETE_PRODUCTION_DOCUMENT_TYPES = {
    "conversion_sheet",
    "commissioning",
    "inspection_label",
}


@lru_cache(maxsize=1)
def _sab_logo_data_uri():
    """Embed the logo so wkhtmltopdf never has to fetch a protected URL."""
    with file_open("sab_project/static/src/img/sab_p_logo.jpg", "rb") as logo_file:
        encoded = base64.b64encode(logo_file.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class SabProductionDocumentPrinting(models.Model):
    _inherit = "sab.production.document"

    document_type = fields.Selection(
        selection_add=EXTRA_PRODUCTION_DOCUMENT_TYPES,
        ondelete={key: "cascade" for key, _label in EXTRA_PRODUCTION_DOCUMENT_TYPES},
    )

    def _sab_report_logo_src(self):
        return _sab_logo_data_uri()

    def _sab_safe_pdf_part(self, value):
        value = (value or "").strip()
        value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
        value = re.sub(r"\s+", " ", value).strip(" .-_\t\r\n")
        return value

    def _sab_pdf_filename(self):
        documents = self.exists()
        if not documents:
            return "Fertigungsdokument"

        first = documents[0]
        project = self._sab_safe_pdf_part(
            first.project_id.sab_project_reference
            or first.project_reference
            or first.project_id.name
        )

        if self.env.context.get("sab_multi_production_print") or len(documents) > 1:
            cabinets = documents.mapped("cabinet_instance_label")
            parts = [project]
            if len(set(filter(None, cabinets))) == 1:
                parts.append(self._sab_safe_pdf_part(cabinets[0]))
            parts.append("Fertigungsordner")
            return "_".join(filter(None, parts)) or "Fertigungsordner"

        document_labels = {
            "conformity": "Konformitätserklärung",
            "production_test": "Prüfprotokoll Fertigung",
            "final_inspection": "Prüfprotokoll Endkontrolle",
            "run_card": "Laufkarte",
            "missing_parts": "Bestellung Fehlteile",
            "shipping_sheet": "Versandblatt",
            "add_pack": "Beipackzettel",
            "nameplate": "Typenschild",
            "info_sheet": "Infoschild",
            "folder_label": "Ordneretikett",
        }
        document_label = document_labels.get(
            first.document_type,
            first.name or "Fertigungsdokument",
        )
        # Der sichtbare Dateiname muss die Dokumentart sein. Projekt- und
        # Verteilerbezeichnungen gehören in den Dokumentinhalt und dürfen den
        # Dateityp für Lager und Fertigung nicht verdecken.
        return self._sab_safe_pdf_part(document_label) or "Fertigungsdokument"

    def _sab_production_report_action(self):
        """Return the native QWeb PDF report action for these exact documents.

        Building the action from the ir.actions.report record keeps single-document
        and multi-document printing deterministic and prevents a window action from
        being returned by surrounding wizard/view context.
        """
        documents = self.exists()
        if not documents:
            return False
        report = self.env.ref("sab_project.action_report_sab_production_documents")
        multi_print = len(documents) > 1
        report_context = {
            **dict(self.env.context),
            # Die Vorlagen selbst sind der freigegebene deutsche Originaltext.
            # Alte de_DE-QWeb-Uebersetzungen in bestehenden Datenbanken koennen
            # UTF-8-Text doppelt dekodiert enthalten (z. B. "PrÃ¼fung").
            # en_US waehlt hier bewusst den unveraenderten XML-Quelltext.
            "lang": "en_US",
            "active_model": self._name,
            "active_id": documents[0].id,
            "active_ids": documents.ids,
            "sab_multi_production_print": multi_print,
        }
        filename = documents.with_context(report_context)._sab_pdf_filename()
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

    def action_print_document(self):
        self.ensure_one()
        return self._sab_production_report_action()


class SabProductionOrderPrinting(models.Model):
    _inherit = "sab.production.order"

    def action_prepare_production_documents(self):
        result = super().action_prepare_production_documents()
        Document = self.env["sab.production.document"]
        for production in self:
            obsolete_documents = production.document_ids.filtered(
                lambda document: document.document_type in OBSOLETE_PRODUCTION_DOCUMENT_TYPES
            )
            if obsolete_documents:
                obsolete_documents.unlink()

            base_documents = production.document_ids.filtered(
                lambda document: document.document_type not in dict(EXTRA_PRODUCTION_DOCUMENT_TYPES)
            )
            instances = {}
            for document in base_documents:
                key = (document.cabinet_bom_id.id, document.cabinet_instance_no)
                instances.setdefault(key, document)
            existing = {
                (
                    document.cabinet_bom_id.id,
                    document.cabinet_instance_no,
                    document.document_type,
                )
                for document in production.document_ids
            }
            for (_cabinet_id, _instance_no), reference in instances.items():
                snapshot = production._sab_cabinet_product_snapshot_values(
                    reference.cabinet_bom_id
                )
                for document_type, _label in EXTRA_PRODUCTION_DOCUMENT_TYPES:
                    key = (
                        reference.cabinet_bom_id.id,
                        reference.cabinet_instance_no,
                        document_type,
                    )
                    if key in existing:
                        continue
                    Document.create(
                        {
                            "production_order_id": production.id,
                            "cabinet_bom_id": reference.cabinet_bom_id.id,
                            "cabinet_instance_no": reference.cabinet_instance_no,
                            "cabinet_instance_count": reference.cabinet_instance_count,
                            "document_type": document_type,
                            **snapshot,
                        }
                    )
                    existing.add(key)
        return result

    def action_open_production_print_wizard(self):
        self.ensure_one()
        self.action_prepare_production_documents()
        return {
            "type": "ir.actions.act_window",
            "name": _("Fertigungsdruck"),
            "res_model": "sab.production.print.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_production_order_id": self.id,
                "active_id": self.id,
                "active_model": self._name,
            },
        }
