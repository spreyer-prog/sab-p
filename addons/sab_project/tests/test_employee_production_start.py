from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSabEmployeeProductionStart(TransactionCase):

    def test_employee_starts_parent_order_without_production_order_write_acl(self):
        partner = self.env["res.partner"].create({"name": "Kunde Mitarbeiterstart"})
        project = self.env["project.project"].create({"name": "Projekt Mitarbeiterstart", "partner_id": partner.id})
        order = self.env["sale.order"].create({"partner_id": partner.id, "sab_project_id": project.id})
        bom = self.env["sab.project.bom"].create({
            "name": "STL Mitarbeiterstart",
            "order_id": order.id,
            "project_id": project.id,
            "state": "released",
        })
        production = self.env["sab.production.order"].create({"name": "FA Mitarbeiterstart", "bom_id": bom.id})
        step = production.step_ids.sorted("sequence")[:1]
        employee = self.env["sab.employee.profile"].create({
            "name": "Mitarbeiter Start",
            "login": "employee.production.start@test.local",
            "email": "employee.production.start@example.invalid",
            "mobile_access": True,
            "work_area_ids": [(6, 0, [step.work_area_id.id])],
        })
        employee.action_create_or_update_user()
        user = employee.user_id

        with self.assertRaises(AccessError):
            self.env["sab.production.order"].with_user(user).check_access("write")
        step.with_user(user).action_start()

        production.invalidate_recordset(["state", "started_at"])
        step.invalidate_recordset(["state", "responsible_employee_id", "responsible_user_id"])
        self.assertEqual(step.state, "in_progress")
        self.assertEqual(step.responsible_employee_id, employee)
        self.assertEqual(step.responsible_user_id, user)
        self.assertEqual(production.state, "in_progress")
        self.assertTrue(production.started_at)
