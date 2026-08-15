import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSabProjectDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Kunde Dokumente"})
        cls.project = cls.env["project.project"].create({"name": "Projekt Dokumente", "partner_id": cls.partner.id})

    def test_release_and_revision_preserve_history(self):
        document = self.env["sab.project.document"].create({
            "name": "Prüfprotokoll NSHV",
            "project_id": self.project.id,
            "document_type": "test_report",
            "file_name": "pruefprotokoll-v1.pdf",
            "file_data": base64.b64encode(b"version-1"),
        })
        document.action_release()
        self.assertEqual(document.state, "released")
        self.assertTrue(document.released_at)
        self.assertEqual(document.released_by_id, self.env.user)

        with self.assertRaises(ValidationError):
            document.write({"file_name": "manipuliert.pdf"})

        action = document.action_create_revision()
        revision = self.env["sab.project.document"].browse(action["res_id"])
        self.assertEqual(document.state, "obsolete")
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.revision_of_id, document)
        self.assertEqual(revision.project_id, document.project_id)
        self.assertEqual(revision.document_type, document.document_type)
        self.assertEqual(revision.file_name, document.file_name)

        revision.write({
            "file_name": "pruefprotokoll-v2.pdf",
            "file_data": base64.b64encode(b"version-2"),
        })
        revision.action_release()
        self.assertEqual(revision.state, "released")

        with self.assertRaises(ValidationError):
            document.unlink()
