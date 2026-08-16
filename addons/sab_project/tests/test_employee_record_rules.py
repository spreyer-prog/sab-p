from odoo.tests.common import TransactionCase


class TestSabEmployeeRecordRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_a = cls.env["res.users"].create({"name": "Mitarbeiter A", "login": "employee.a@test.local"})
        cls.employee_b = cls.env["res.users"].create({"name": "Mitarbeiter B", "login": "employee.b@test.local"})
        cls.env.ref("base.group_user").write({"user_ids": [(4, cls.employee_a.id), (4, cls.employee_b.id)]})
        cls.env.ref("sab_project.group_sab_employee").write({"user_ids": [(4, cls.employee_a.id), (4, cls.employee_b.id)]})

        cls.partner = cls.env["res.partner"].create({"name": "Record-Rule-Kunde"})
        cls.project = cls.env["project.project"].create({"name": "Record-Rule-Projekt", "partner_id": cls.partner.id})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id, "sab_project_id": cls.project.id})
        cls.bom = cls.env["sab.project.bom"].create({"name": "STL Record Rule", "order_id": cls.order.id, "project_id": cls.project.id})
        cls.bom.state = "released"
        cls.production = cls.env["sab.production.order"].create({"name": "FA Record Rule", "bom_id": cls.bom.id})
        steps = cls.production.step_ids.sorted("sequence")
        cls.step_a = steps[0]
        cls.step_b = steps[1]
        cls.step_free = steps[2]
        cls.step_a.responsible_user_id = cls.employee_a
        cls.step_b.responsible_user_id = cls.employee_b

        cls.time_a = cls.env["sab.time.entry"].create({"project_id": cls.project.id, "production_step_id": cls.step_a.id, "user_id": cls.employee_a.id, "name": "Zeit A", "hours": 1.0})
        cls.time_b = cls.env["sab.time.entry"].create({"project_id": cls.project.id, "production_step_id": cls.step_b.id, "user_id": cls.employee_b.id, "name": "Zeit B", "hours": 1.0})

        cls.feedback_a = cls.env["sab.employee.feedback"].create({"name": "Feedback A", "production_step_id": cls.step_a.id, "user_id": cls.employee_a.id, "feedback_type": "note", "description": "A"})
        cls.feedback_b = cls.env["sab.employee.feedback"].create({"name": "Feedback B", "production_step_id": cls.step_b.id, "user_id": cls.employee_b.id, "feedback_type": "note", "description": "B"})

    def test_employee_sees_only_own_or_free_steps(self):
        visible = self.env["sab.production.step"].with_user(self.employee_a).search([("production_order_id", "=", self.production.id)])
        self.assertIn(self.step_a, visible)
        self.assertIn(self.step_free, visible)
        self.assertNotIn(self.step_b, visible)

    def test_employee_sees_only_own_times(self):
        visible = self.env["sab.time.entry"].with_user(self.employee_a).search([("project_id", "=", self.project.id)])
        self.assertIn(self.time_a, visible)
        self.assertNotIn(self.time_b, visible)

    def test_employee_sees_only_own_feedback(self):
        visible = self.env["sab.employee.feedback"].with_user(self.employee_a).search([("project_id", "=", self.project.id)])
        self.assertIn(self.feedback_a, visible)
        self.assertNotIn(self.feedback_b, visible)
