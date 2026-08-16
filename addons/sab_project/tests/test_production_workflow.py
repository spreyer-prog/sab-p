from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabProductionWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Fertigung"})
        cls.project = cls.env["project.project"].create({"name": "Projekt Fertigung", "partner_id": cls.partner.id})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id, "sab_project_id": cls.project.id})
        cls.bom = cls.env["sab.project.bom"].create({"name": "STL Fertigungstest", "order_id": cls.order.id, "project_id": cls.project.id})

    def test_production_requires_released_bom(self):
        with self.assertRaises(ValidationError):
            self.env["sab.production.order"].create({"name": "FA gesperrt", "bom_id": self.bom.id})

    def test_default_steps_receive_work_areas(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({"name": "FA Bereiche", "bom_id": self.bom.id})
        steps = production.step_ids.sorted("sequence")
        self.assertEqual(steps[0].work_area_id, self.env.ref("sab_project.sab_work_area_mechanical_fabrication"))
        self.assertEqual(steps[1].work_area_id, self.env.ref("sab_project.sab_work_area_mechanical_assembly"))
        self.assertEqual(steps[5].work_area_id, self.env.ref("sab_project.sab_work_area_electrical"))
        self.assertEqual(steps[6].work_area_id, self.env.ref("sab_project.sab_work_area_testing"))

    def test_wrong_work_area_employee_assignment_is_rejected(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({"name": "FA Qualifikation", "bom_id": self.bom.id})
        step = production.step_ids.sorted("sequence")[1]
        user = self.env["res.users"].with_context(no_reset_password=True).create({"name": "Nur Elektrik", "login": "only.electrical@test.local"})
        employee = self.env["sab.employee.profile"].create({
            "name": "Nur Elektrik",
            "login": "only.electrical@test.local",
            "user_id": user.id,
            "work_area_ids": [(6, 0, [self.env.ref("sab_project.sab_work_area_electrical").id])],
        })
        with self.assertRaises(ValidationError):
            step.write({"responsible_employee_id": employee.id})

    def test_employee_can_only_claim_matching_work_area(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({"name": "FA Mitarbeiterbereich", "bom_id": self.bom.id})
        mechanical_step = production.step_ids.sorted("sequence")[0]
        electrical_step = production.step_ids.sorted("sequence")[5]
        mechanical_area = self.env.ref("sab_project.sab_work_area_mechanical_fabrication")

        employee = self.env["sab.employee.profile"].create({
            "name": "Mechanik Mitarbeiter",
            "login": "mechanic.workarea@test.local",
            "email": "mechanic.workarea@example.invalid",
            "work_area_ids": [(6, 0, [mechanical_area.id])],
            "mobile_access": True,
        })
        employee.action_create_or_update_user()

        mechanical_step.with_user(employee.user_id).action_claim()
        mechanical_step.invalidate_recordset(["responsible_employee_id", "responsible_user_id"])
        self.assertEqual(mechanical_step.responsible_employee_id, employee)
        self.assertEqual(mechanical_step.responsible_user_id, employee.user_id)

        with self.assertRaises(ValidationError):
            electrical_step.with_user(employee.user_id).action_claim()

    def test_employee_can_claim_unassigned_step(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({"name": "FA Mitarbeiter", "bom_id": self.bom.id})
        step = production.step_ids.sorted("sequence")[:1]
        self.assertFalse(step.responsible_user_id)
        step.action_claim()
        self.assertEqual(step.responsible_user_id, self.env.user)
        self.assertEqual(step.project_id, self.project)
        self.assertEqual(step.production_state, "planned")

    def test_step_pause_and_resume(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({"name": "FA Pause", "bom_id": self.bom.id})
        step = production.step_ids.sorted("sequence")[:1]
        step.action_start()
        started_at = step.started_at
        self.assertEqual(step.state, "in_progress")
        step.action_pause()
        self.assertEqual(step.state, "paused")
        self.assertTrue(step.paused_at)
        step.action_start()
        self.assertEqual(step.state, "in_progress")
        self.assertFalse(step.paused_at)
        self.assertEqual(step.started_at, started_at)

    def test_production_start_and_finish_timestamps(self):
        self.bom.state = "released"
        production = self.env["sab.production.order"].create({"name": "FA Test", "bom_id": self.bom.id})
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
