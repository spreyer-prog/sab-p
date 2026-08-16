import base64
import io
import zipfile

from odoo.tests.common import TransactionCase


HEADER = "V;050;A;20260801;EUR;;;;ABB AG;Geschaeftsbereich;Elektrifizierung;;;;;"
ARTICLE = (
    "A;N;1SFA170190R8000;Schutzabdeckung Gummi schwarz, fuer flac;"
    "he Tasten, Modular Metall Reihe;PCE;1;1;714;V2;;;080CPN;;;;"
    "1SFA170190R8000;080CPN;7320500520642;;5;;;;;;;;;"
)
ARTICLE_WITH_TYPE = (
    "A;N;1SFA170190R8000;080CPN Schutzabdeckung Gummi schwarz, fu;"
    "er flache Tasten, Modular Metall Reihe;PCE;1;1;714;V2;;;080CPN;;;;"
    "1SFA170190R8000;080CPN;7320500520642;;5;;;;;;;;;"
)
ARTICLE_WITH_SPACE_UNITS = (
    "A;N;2CDS251001R0164;Leitungsschutzschalter 1-polig 16A 1 PLE;"
    "S201-B16;PCE;1;1;1250;V2;;;S201-B16;;;;"
    "2CDS251001R0164;S201-B16;4016779467604;;5;;;;;;;;;"
)
Z_RECORD = "Z;N;1SFA170190R8000;11;2;CU;3;+;1;1;2;15100;20000;10;"
END = "E;"


class TestSabDatanormImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["sab.supplier"].create({
            "name": "ABB DATANORM Test",
        })

    def _wizard(self, payload, filename="DATANORM.001"):
        return self.env["sab.datanorm.import"].create({
            "file_data": base64.b64encode(payload),
            "file_name": filename,
            "supplier_id": self.supplier.id,
            "create_missing_products": True,
        })

    def test_zip_prefers_abb_shorttext_with_type(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "DataNorm5_2026-08_Direkt-Gesamt.001",
                "\n".join([HEADER, ARTICLE, END]),
            )
            archive.writestr(
                "DataNorm5_2026-08_Direkt_KurztextinklTyp-Gesamt.001",
                "\n".join([HEADER, ARTICLE_WITH_TYPE, END]),
            )

        wizard = self._wizard(buffer.getvalue(), "ABB.zip")
        text, source_name = wizard._read_payload()

        self.assertIn("KurztextinklTyp", source_name)
        self.assertIn("080CPN Schutzabdeckung", text)

    def test_import_preserves_sab_technical_values_and_raw_price(self):
        manufacturer = self.env["sab.manufacturer"].create({"name": "ABB AG"})
        product = self.env["sab.product"].create({
            "name": "Alttext",
            "manufacturer_id": manufacturer.id,
            "manufacturer_article_number": "1SFA170190R8000",
            "space_units": 1.25,
            "mechanical_time_minutes": 4.0,
            "wiring_time_minutes": 5.0,
            "testing_time_minutes": 6.0,
        })

        payload = "\n".join([HEADER, ARTICLE, Z_RECORD, END]).encode("cp1252")
        wizard = self._wizard(payload)
        wizard.action_import()

        product.invalidate_recordset()
        self.assertEqual(product.datanorm_number, "1SFA170190R8000")
        self.assertAlmostEqual(product.space_units, 1.25)
        self.assertAlmostEqual(product.mechanical_time_minutes, 4.0)
        self.assertAlmostEqual(product.wiring_time_minutes, 5.0)
        self.assertAlmostEqual(product.testing_time_minutes, 6.0)

        supplier_product = self.env["sab.supplier.product"].search([
            ("supplier_id", "=", self.supplier.id),
            ("supplier_article_number", "=", "1SFA170190R8000"),
        ])
        self.assertEqual(len(supplier_product), 1)
        self.assertAlmostEqual(supplier_product.datanorm_price, 7.14)
        self.assertAlmostEqual(supplier_product.list_price, 7.14)
        self.assertEqual(supplier_product.datanorm_price_code, "V2")
        self.assertAlmostEqual(supplier_product.purchase_price, 0.0)
        self.assertEqual(supplier_product.datanorm_type_name, "080CPN")
        self.assertEqual(supplier_product.ean, "7320500520642")
        self.assertIn("Z-Preis-/Zuschlagssätze erkannt: 1", wizard.result_text)

        self.supplier.datanorm_price_as_purchase_price = True
        wizard = self._wizard(payload)
        wizard.action_import()
        supplier_product.invalidate_recordset()
        self.assertAlmostEqual(supplier_product.purchase_price, 7.14)

    def test_imports_space_units_from_article_text_for_new_products(self):
        payload = "\n".join([HEADER, ARTICLE_WITH_SPACE_UNITS, END]).encode("cp1252")
        wizard = self._wizard(payload)
        wizard.action_import()
        product = self.env["sab.product"].search([
            ("manufacturer_article_number", "=", "2CDS251001R0164")
        ], limit=1)
        self.assertTrue(product)
        self.assertAlmostEqual(product.space_units, 1.0)
        supplier_product = self.env["sab.supplier.product"].search([
            ("supplier_id", "=", self.supplier.id),
            ("supplier_article_number", "=", "2CDS251001R0164"),
        ], limit=1)
        self.assertAlmostEqual(supplier_product.list_price, 12.50)

    def test_record_count_and_units(self):
        counts = self.env["sab.datanorm.import"]._record_counts([
            HEADER,
            ARTICLE,
            Z_RECORD,
            Z_RECORD,
            END,
        ])
        self.assertEqual(counts["A"], 1)
        self.assertEqual(counts["Z"], 2)
        self.assertEqual(
            self.env["sab.datanorm.import"]._unit_from_datanorm("PCE"),
            "pcs",
        )
        self.assertAlmostEqual(
            self.env["sab.datanorm.import"]._parse_price("714"),
            7.14,
        )
