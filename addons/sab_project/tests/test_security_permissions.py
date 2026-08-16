import base64

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSabSecurityPermissions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.normal_user = cls.env["res.users"].create({
            "name": "SAB Mitarbeiter ohne Freigabe",
            "login": "sab.no.release@test.local",
        })
        cls.release_user = cls.env["res.users"].create({
            "name": "SAB Kundenfreigeber",
            "login": "sab.release@test.local",
        })
        cls.env.ref("base.group_user").write({
            "user_ids": [(4, cls.normal_user.id), (4, cls.release_user.id)],
        })
        cls.env.ref("sab_project.group_sab_customer_release").write({
            "user_ids": [(4, cls.release_user.id)],
        })

        cls.partner = cls.env["res.partner"].create({"name": "Sicherheitskunde"})
        cls.project = cls.env["project.project"].create({
            "name": "Sicherheitsprojekt",
            "partner_id": cls.partner.id,
        })
        cls.status = cls.env["sab.customer.project.status"].create({
            "project_id": cls.project.id,
        })
        cls.document = cls.env["sab.project.document"].create({
            "name": "Freigabetest",
            "project_id": cls.project.id,
            "document_type": "test_report",
            "file_name": "test.pdf",
            "file_data": base64.b64encode(b"test"),
        })
        cls.document.action_release()

    def test_normal_internal_user_cannot_publish_customer_content(self):
        with self.assertRaises(AccessError):
            self.status.with_user(self.normal_user).action_release()
        with self.assertRaises(AccessError):
            self.document.with_user(self.normal_user).action_release_to_customer()

    def test_release_user_can_publish_customer_content(self):
        self.status.with_user(self.release_user).action_release()
        self.assertTrue(self.status.released)

        self.document.with_user(self.release_user).action_release_to_customer()
        self.assertTrue(self.document.customer_visible)
