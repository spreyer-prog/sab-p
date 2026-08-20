from odoo.fields import Command
from odoo.tests.common import TransactionCase

from odoo.addons.sab_project.models.sab_production_document import (
    PRODUCTION_DOCUMENT_TYPES,
)


class TestSabProductionDocumentCabinetQuantity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {"name": "Kunde Schrankdokumente"}
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Schrankdokumente",
                "partner_id": cls.customer.id,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
            }
        )
        cls.material = cls.env["sab.product"].create(
            {
                "name": "Material für Schrankdokumente",
                "manufacturer_article_number": "DOC-MAT-001",
            }
        )
        cls.cabinet_template = cls.env["product.template"].create(
            {
                "name": "Schrankgehäuse 800 mm",
                "sale_ok": True,
                "purchase_ok": True,
                "sab_is_cabinet_product": True,
                "sab_cabinet_width_mm": 800.0,
                "sab_nameplate_type_designation": "SAB-P UV 800",
                "sab_nameplate_cabinet_type": "TG(G)",
                "sab_nameplate_standard_family": "61439",
                "sab_nameplate_standard_part": "3",
                "sab_nameplate_rated_voltage": 400.0,
                "sab_nameplate_rated_current": 250.0,
                "sab_nameplate_frequency": 50.0,
                "sab_nameplate_busbar_current": 400.0,
                "sab_nameplate_protection_class": "2",
                "sab_nameplate_ip_rating": "IP54",
                "sab_nameplate_notes": "Snapshot aus Schrankprodukt",
            }
        )
        cls.cabinet_product = cls.cabinet_template.product_variant_id
        cls.cabinet_heading = cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.order.id,
                "line_type": "cabinet",
                "description": "UV Hauptverteilung",
                "sequence": 10,
                "quantity": 3.0,
                "odoo_product_id": cls.cabinet_product.id,
            }
        )
        line_values = {
            "sequence": 10,
            "product_id": cls.material.id,
            "odoo_product_id": cls.material.odoo_product_id.id,
            "quantity": 1.0,
            "unit": "pcs",
        }
        cls.cabinet_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL Schrankdokumente / UV Hauptverteilung",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cls.cabinet_heading.id,
                "line_ids": [Command.create(line_values)],
            }
        )
        cls.total_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL Schrankdokumente / GESAMT",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "total",
                "line_ids": [Command.create(line_values)],
            }
        )
        cls.total_bom.action_release()
        cls.production = cls.env["sab.production.order"].create(
            {
                "name": "FA Schrankdokumente",
                "bom_id": cls.total_bom.id,
            }
        )

    def test_quantity_three_creates_three_complete_document_sets(self):
        self.production.action_prepare_production_documents()
        documents = self.production.document_ids
        per_cabinet_types = len(PRODUCTION_DOCUMENT_TYPES)

        self.assertEqual(len(documents), 3 * per_cabinet_types)
        self.assertEqual(set(documents.mapped("cabinet_instance_no")), {1, 2, 3})
        self.assertEqual(set(documents.mapped("cabinet_instance_count")), {3})

        for instance_no in (1, 2, 3):
            instance_docs = documents.filtered(
                lambda document: document.cabinet_instance_no == instance_no
            )
            self.assertEqual(len(instance_docs), per_cabinet_types)
            self.assertEqual(
                set(instance_docs.mapped("document_type")),
                set(dict(PRODUCTION_DOCUMENT_TYPES)),
            )
            self.assertIn(f"{instance_no}/3", instance_docs[0].cabinet_instance_label)

    def test_nameplate_values_are_snapshotted_from_cabinet_product(self):
        self.production.action_prepare_production_documents()
        nameplates = self.production.document_ids.filtered(
            lambda document: document.document_type == "nameplate"
        )
        self.assertEqual(len(nameplates), 3)
        for nameplate in nameplates:
            self.assertEqual(nameplate.cabinet_product_id, self.cabinet_product)
            self.assertEqual(nameplate.cabinet_width_mm, 800.0)
            self.assertEqual(nameplate.type_designation, "SAB-P UV 800")
            self.assertEqual(nameplate.cabinet_type, "TG(G)")
            self.assertEqual(nameplate.rated_voltage, 400.0)
            self.assertEqual(nameplate.rated_current, 250.0)
            self.assertEqual(nameplate.busbar_current, 400.0)
            self.assertEqual(nameplate.ip_rating, "IP54")

        self.cabinet_template.write(
            {
                "sab_nameplate_type_designation": "SPÄTER GEÄNDERT",
                "sab_nameplate_rated_current": 630.0,
            }
        )
        nameplates.invalidate_recordset()
        for nameplate in nameplates:
            self.assertEqual(nameplate.type_designation, "SAB-P UV 800")
            self.assertEqual(nameplate.rated_current, 250.0)
