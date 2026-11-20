from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabTimeEntry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Zeit"})
        cls.project = cls.env["project.project"].create({"name": "Projekt Zeit", "partner_id": cls.partner.id})

    def test_only_confirmed_time_counts_for_actual_hours(self):
        entry = self.env["sab.time.entry"].create({
            "name": "Montage vor Ort",
            "project_id": self.project.id,
            "activity_type": "service",
            "hours": 3.5,
            "hourly_cost": 80.0,
        })
        self.assertEqual(entry.state, "draft")
        self.assertAlmostEqual(self.project.sab_required_hours, 0.0)
        self.assertAlmostEqual(entry.cost_total, 280.0)

        entry.action_confirm()
        self.assertEqual(entry.state, "confirmed")
        self.assertAlmostEqual(self.project.sab_required_hours, 3.5)

        with self.assertRaises(ValidationError):
            entry.write({"hours": 4.0})
        with self.assertRaises(ValidationError):
            entry.unlink()

    def test_default_hourly_cost_uses_calculation_setting(self):
        self.env["ir.config_parameter"].sudo().set_param("sab_project.hourly_rate", "95.0")
        entry = self.env["sab.time.entry"].create({
            "name": "Prüfung",
            "project_id": self.project.id,
            "activity_type": "testing",
            "hours": 2.0,
        })
        self.assertAlmostEqual(entry.hourly_cost, 95.0)
        self.assertAlmostEqual(entry.cost_total, 190.0)
