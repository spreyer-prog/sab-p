from odoo import fields, models, _


EXTRA_PRODUCTION_DOCUMENT_TYPES = [
    ("shipping_sheet", "Blatt Versand"),
    ("conversion_sheet", "Blatt Umbau"),
    ("inspection_label", "Prüfetikett"),
    ("commissioning", "Kommissionierung"),
    ("folder_label", "Ordneretikett"),
]


class SabProductionDocumentPrinting(models.Model):
    _inherit = "sab.production.document"

    document_type = fields.Selection(
        selection_add=EXTRA_PRODUCTION_DOCUMENT_TYPES,
        ondelete={key: "cascade" for key, _label in EXTRA_PRODUCTION_DOCUMENT_TYPES},
    )

    def action_print_document(self):
        self.ensure_one()
        return self.env.ref(
            "sab_project.action_report_sab_production_documents"
        ).report_action(self)


class SabProductionOrderPrinting(models.Model):
    _inherit = "sab.production.order"

    def action_prepare_production_documents(self):
        result = super().action_prepare_production_documents()
        Document = self.env["sab.production.document"]
        for production in self:
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
