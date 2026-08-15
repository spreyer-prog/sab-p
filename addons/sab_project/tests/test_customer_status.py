from odoo.tests.common import TransactionCase


class TestSabCustomerStatus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Portalkunde"})
        cls.project = cls.env["project.project"].create({
            "name": "Portalprojekt",
            "partner_id": cls.partner.id,
        })

    def test_customer_status_requires_explicit_release_after_change(self):
        status = self.env["sab.customer.project.status"].create({
            "project_id": self.project.id,
            "milestone": "order_received",
            "note_customer": "Auftrag ist eingegangen.",
            "note_internal": "Interner Text darf nicht zum Kunden.",
        })
        self.assertFalse(status.released)
        self.assertEqual(status.progress_percent, 0)

        status.action_release()
        self.assertTrue(status.released)
        self.assertTrue(status.released_at)

        status.write({"milestone": "planning"})
        self.assertFalse(status.released)
        self.assertGreater(status.progress_percent, 0)

        status.action_release()
        self.assertTrue(status.released)
