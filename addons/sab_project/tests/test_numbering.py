from odoo.tests.common import TransactionCase


class TestSabNumbering(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Testkunde"})

    def test_project_and_offer_numbering(self):
        project_1 = self.env["project.project"].create({"name": "Projekt Eins"})
        project_2 = self.env["project.project"].create({"name": "Projekt Zwei"})

        self.assertRegex(project_1.sab_project_reference, r"^A\d{2}\.\d{4}$")
        self.assertNotEqual(
            project_1.sab_project_reference,
            project_2.sab_project_reference,
        )

        offer_1 = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": project_1.id,
        })
        offer_2 = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sab_project_id": project_1.id,
        })

        self.assertEqual(
            offer_1.name,
            f"{project_1.sab_project_reference}-01",
        )
        self.assertEqual(
            offer_2.name,
            f"{project_1.sab_project_reference}-02",
        )
