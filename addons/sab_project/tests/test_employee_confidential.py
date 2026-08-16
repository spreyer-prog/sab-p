from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabEmployeeConfidential(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["sab.employee.profile"].create({
            "name": "Test Mitarbeiter",
            "login": "test.employee.confidential",
        })
        internal_group = cls.env.ref("base.group_user")
        confidential_group = cls.env.ref("sab_project.group_sab_confidential_hr")
        cls.regular_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Normaler Benutzer",
            "login": "sab_confidential_regular",
            "email": "regular@example.invalid",
            "group_ids": [Command.link(internal_group.id)],
        })
        cls.confidential_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Geschäftsführung Test",
            "login": "sab_confidential_management",
            "email": "management@example.invalid",
            "group_ids": [Command.link(internal_group.id), Command.link(confidential_group.id)],
        })

    def test_regular_user_cannot_create_or_read_confidential_notes(self):
        Note = self.env["sab.employee.confidential.note"]
        with self.assertRaises(AccessError):
            Note.with_user(self.regular_user).create({
                "employee_id": self.employee.id,
                "note_type": "positive",
                "title": "Gute Leistung",
                "facts": "Projekt termingerecht abgeschlossen.",
            })

        note = Note.with_user(self.confidential_user).create({
            "employee_id": self.employee.id,
            "note_type": "salary_review",
            "title": "Gehaltsgespräch",
            "facts": "Für das nächste Gehaltsgespräch berücksichtigen.",
            "salary_review_relevant": True,
        })
        self.assertTrue(note.salary_review_relevant)
        with self.assertRaises(AccessError):
            Note.with_user(self.regular_user).browse(note.id).check_access("read")

    def test_confidential_user_can_open_employee_personnel_record(self):
        employee = self.employee.with_user(self.confidential_user)
        action = employee.action_open_confidential_notes()
        self.assertEqual(action["res_model"], "sab.employee.confidential.note")
        self.assertEqual(action["domain"], [("employee_id", "=", self.employee.id)])
