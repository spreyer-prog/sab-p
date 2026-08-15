from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabProductionWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Fertigung"})
        cls.project = cls.env["project.project"].create({
            "name": "Projekt Fertigung",
            "partner_id": cls.partner.id,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "sab_project_id": cls.project.id,
        })
        cls.bom = cls.env["sab.project.bom"].create({
            "name": "STL Fertigungstest",
            "order_id": cls.order.id,
            "project_id": cls.project.id,
        })

    def test_production_requires_released_bom(self):
        with self.assertRaises(ValidationError):
            self.env["sab.production.order"].create({
                "name": "FA gesperrt",
                "bom_id": self.bom.id,
            })

    def test_employee_can_claim_unassigned_step(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({
            "name": "FA Mitarbeiter",
            "bom_id": self.bom.id,
        })
        step = production.step_ids.sorted("sequence")[:1]
        self.assertFalse(step.responsible_user_id)
        step.action_claim()
        self.assertEqual(step.responsible_user_id, self.env.user)
        self.assertEqual(step.project_id, self.project)
        self.assertEqual(step.production_state, "planned")

    def test_production_start_and_finish_timestamps(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({
            "name": "FA Test",
            "bom_id": self.bom.id,
        })

        self.assertEqual(production.state, "planned")
        self.assertFalse(production.started_at)
        self.assertEqual(len(production.step_ids), 8)

        first_step = production.step_ids.sorted("sequence")[:1]
        first_step.action_start()
        self.assertEqual(production.state, "in_progress")
        self.assertTrue(production.started_at)
        self.assertEqual(first_step.state, "in_progress")
        self.assertTrue(first_step.started_at)

        first_step.action_done()
        self.assertEqual(first_step.state, "done")
        self.assertTrue(first_step.finished_at)
        self.assertGreater(production.progress_percent, 0.0)
        self.assertLess(production.progress_percent, 100.0)

        for step in production.step_ids.filtered(lambda step: step.state != "done"):
            step.action_skip()

        production.action_mark_done()
        self.assertEqual(production.state, "done")
        self.assertTrue(production.finished_at)
        self.assertAlmostEqual(production.progress_percent, 100.0)

        with self.assertRaises(ValidationError):
            production.step_ids[:1].write({"note": "nachträglich"})
