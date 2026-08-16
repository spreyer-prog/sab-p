import base64

from odoo.tests.common import TransactionCase


class TestSabPortalVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("sab_project.group_sab_customer_release").write({
            "user_ids": [(4, cls.env.user.id)],
        })
        cls.partner_a = cls.env["res.partner"].create({"name": "Portal Kunde A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Portal Kunde B"})
        cls.project_a = cls.env["project.project"].create({"name": "Portal Projekt A", "partner_id": cls.partner_a.id})
        cls.project_b = cls.env["project.project"].create({"name": "Portal Projekt B", "partner_id": cls.partner_b.id})

    def _released_status(self, project):
        status = self.env["sab.customer.project.status"].create({"project_id": project.id})
        status.action_release()
        return status

    def _released_document(self, project):
        document = self.env["sab.project.document"].create({
            "name": "Kundenunterlage",
            "project_id": project.id,
            "document_type": "drawing",
            "file_name": "plan.pdf",
            "file_data": base64.b64encode(b"portal-test"),
        })
        document.action_release()
        document.action_release_to_customer()
        return document

    def _released_photo(self, project):
        order = self.env["sale.order"].create({"partner_id": project.partner_id.id, "sab_project_id": project.id})
        bom = self.env["sab.project.bom"].create({"name": f"STL {project.name}", "order_id": order.id, "project_id": project.id})
        bom.state = "released"
        production = self.env["sab.production.order"].create({"name": f"FA {project.name}", "bom_id": bom.id})
        step = production.step_ids.sorted("sequence")[:1]
        feedback = self.env["sab.employee.feedback"].create({
            "name": "Kundenfoto",
            "production_step_id": step.id,
            "feedback_type": "photo",
            "description": "Freigegebener Fertigungsstand",
            "photo_filename": "fertigung.jpg",
            "photo": base64.b64encode(b"fake-image"),
        })
        feedback.action_mark_processed()
        feedback.action_release_to_customer()
        return feedback

    def test_status_is_visible_only_to_same_customer(self):
        status_a = self._released_status(self.project_a)
        self.assertTrue(status_a.is_portal_visible_to(self.partner_a))
        self.assertFalse(status_a.is_portal_visible_to(self.partner_b))
        status_a.action_withdraw()
        self.assertFalse(status_a.is_portal_visible_to(self.partner_a))

    def test_document_is_visible_only_to_same_customer(self):
        document_a = self._released_document(self.project_a)
        self.assertTrue(document_a.is_portal_visible_to(self.partner_a))
        self.assertFalse(document_a.is_portal_visible_to(self.partner_b))
        document_a.action_withdraw_customer_release()
        self.assertFalse(document_a.is_portal_visible_to(self.partner_a))

    def test_photo_is_visible_only_to_same_customer(self):
        photo_a = self._released_photo(self.project_a)
        self.assertTrue(photo_a.is_portal_visible_to(self.partner_a))
        self.assertFalse(photo_a.is_portal_visible_to(self.partner_b))
        photo_a.action_withdraw_customer_release()
        self.assertFalse(photo_a.is_portal_visible_to(self.partner_a))
