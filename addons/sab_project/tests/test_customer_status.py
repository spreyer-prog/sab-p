from odoo.tests.common import TransactionCase


class TestSabCustomerStatus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("sab_project.group_sab_customer_release").write({
            "user_ids": [(4, cls.env.user.id)],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Portalkunde"})
        cls.project = cls.env["project.project"].create({"name": "Portalprojekt", "partner_id": cls.partner.id})

    def test_customer_status_requires_explicit_release_after_change(self):
        action = self.project.action_open_sab_customer_status()
        status = self.env["sab.customer.project.status"].browse(action["res_id"])
        self.assertEqual(status.project_id, self.project)
        self.assertEqual(self.project.sab_customer_status_count, 1)
        self.assertFalse(status.released)
        self.assertEqual(status.progress_percent, 0)
        self.assertEqual(status.suggested_milestone, "order_received")

        status.write({"note_customer": "Auftrag ist eingegangen.", "note_internal": "Interner Text darf nicht zum Kunden."})
        status.action_release()
        self.assertTrue(status.released)
        self.assertTrue(status.released_at)

        status.write({"milestone": "planning"})
        self.assertFalse(status.released)
        self.assertGreater(status.progress_percent, 0)
        status.action_release()
        self.assertTrue(status.released)

        second_action = self.project.action_open_sab_customer_status()
        self.assertEqual(second_action["res_id"], status.id)
        self.assertEqual(self.project.sab_customer_status_count, 1)

    def test_internal_suggestion_never_auto_publishes(self):
        status = self.env["sab.customer.project.status"].create({"project_id": self.project.id})
        order = self.env["sale.order"].create({"partner_id": self.partner.id, "sab_project_id": self.project.id})
        order.state = "sale"
        status.invalidate_recordset(["suggested_milestone"])
        self.assertEqual(status.suggested_milestone, "planning")
        self.assertFalse(status.released)

        status.action_apply_suggestion()
        self.assertEqual(status.milestone, "planning")
        self.assertFalse(status.released)
