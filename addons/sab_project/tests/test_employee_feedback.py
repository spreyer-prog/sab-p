import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabEmployeeFeedback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Mitarbeiter-App"})
        cls.project = cls.env["project.project"].create({"name": "Projekt Mitarbeiter-App", "partner_id": cls.partner.id})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id, "sab_project_id": cls.project.id})
        cls.bom = cls.env["sab.project.bom"].create({"name": "STL Mitarbeiter-App", "order_id": cls.order.id, "project_id": cls.project.id})
        cls.bom.state = "released"
        cls.production = cls.env["sab.production.order"].create({"name": "FA Mitarbeiter-App", "bom_id": cls.bom.id})
        cls.step = cls.production.step_ids.sorted("sequence")[:1]
        cls.product = cls.env["sab.product"].create({"name": "Fehlendes Material"})

    def _photo_feedback(self):
        return self.env["sab.employee.feedback"].create({
            "name": "Aufbau dokumentiert",
            "production_step_id": self.step.id,
            "feedback_type": "photo",
            "description": "Stand nach mechanischem Aufbau",
            "photo_filename": "aufbau.jpg",
            "photo": base64.b64encode(b"fake-image"),
        })

    def test_photo_feedback_requires_photo(self):
        with self.assertRaises(ValidationError):
            self.env["sab.employee.feedback"].create({
                "name": "Foto fehlt",
                "production_step_id": self.step.id,
                "feedback_type": "photo",
                "description": "Dokumentation",
            })

        feedback = self._photo_feedback()
        self.assertEqual(feedback.project_id, self.project)
        self.assertEqual(feedback.state, "open")
        self.assertFalse(feedback.customer_visible)

        with self.assertRaises(ValidationError):
            feedback.action_release_to_customer()

        feedback.action_mark_processed()
        feedback.action_release_to_customer()
        self.assertTrue(feedback.customer_visible)
        self.assertTrue(feedback.customer_released_at)

        feedback.write({"customer_caption": "Aktueller Fertigungsstand"})
        self.assertFalse(feedback.customer_visible)
        feedback.action_release_to_customer()
        self.assertTrue(feedback.customer_visible)

        feedback.action_withdraw_customer_release()
        self.assertFalse(feedback.customer_visible)

    def test_material_request_requires_product_and_quantity(self):
        with self.assertRaises(ValidationError):
            self.env["sab.employee.feedback"].create({
                "name": "Material fehlt",
                "production_step_id": self.step.id,
                "feedback_type": "material",
                "description": "Material nachfordern",
            })

        feedback = self.env["sab.employee.feedback"].create({
            "name": "Material fehlt",
            "production_step_id": self.step.id,
            "feedback_type": "material",
            "description": "Bitte Material bereitstellen",
            "material_product_id": self.product.id,
            "material_quantity": 2.0,
            "material_unit": "pcs",
        })
        self.assertEqual(feedback.material_product_id, self.product)
        self.assertAlmostEqual(feedback.material_quantity, 2.0)
        feedback.action_mark_processed()
        self.assertEqual(feedback.state, "processed")
        self.assertTrue(feedback.processed_at)
        with self.assertRaises(ValidationError):
            feedback.action_release_to_customer()
