from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabStandardPurchaseSelectionAndSupplierChoice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("sab_project.group_sab_purchasing").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchase_approver").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )

        cls.customer = cls.env["res.partner"].create({"name": "Kunde Einkauf Auswahl"})
        cls.project = cls.env["project.project"].create(
            {"name": "Projekt Einkauf Auswahl", "partner_id": cls.customer.id}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
            }
        )

        cls.supplier_a = cls.env["sab.supplier"].create(
            {"name": "Lieferant Auswahl A", "supplier_number": "SEL-A"}
        )
        cls.supplier_b = cls.env["sab.supplier"].create(
            {"name": "Lieferant Auswahl B", "supplier_number": "SEL-B"}
        )

        cls.product_a = cls.env["sab.product"].create(
            {"name": "Produkt Auswahl A", "manufacturer_article_number": "SEL-PA"}
        )
        cls.product_b = cls.env["sab.product"].create(
            {"name": "Produkt Auswahl B", "manufacturer_article_number": "SEL-PB"}
        )

        cls.supplier_a_product_a = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier_a.id,
                "product_id": cls.product_a.id,
                "supplier_article_number": "A-PA",
                "purchase_price": 10.0,
                "delivery_time_days": 3,
                "preferred": True,
            }
        )
        cls.supplier_a_product_b = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier_a.id,
                "product_id": cls.product_b.id,
                "supplier_article_number": "A-PB",
                "purchase_price": 20.0,
                "delivery_time_days": 4,
                "preferred": True,
            }
        )
        cls.supplier_b_product_a = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier_b.id,
                "product_id": cls.product_a.id,
                "supplier_article_number": "B-PA",
                "purchase_price": 9.0,
                "delivery_time_days": 6,
                "preferred": False,
            }
        )

    def _create_released_requirements(self):
        bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Auswahl / GESAMT",
                "order_id": self.order.id,
                "project_id": self.project.id,
                "bom_scope": "total",
                "line_ids": [
                    Command.create(
                        {
                            "sequence": 10,
                            "product_id": self.product_a.id,
                            "odoo_product_id": self.product_a.odoo_product_id.id,
                            "quantity": 2.0,
                            "unit": "pcs",
                            "supplier_product_id": self.supplier_a_product_a.id,
                            "unit_purchase_price": 10.0,
                        }
                    ),
                    Command.create(
                        {
                            "sequence": 20,
                            "product_id": self.product_b.id,
                            "odoo_product_id": self.product_b.odoo_product_id.id,
                            "quantity": 3.0,
                            "unit": "pcs",
                            "supplier_product_id": self.supplier_a_product_b.id,
                            "unit_purchase_price": 20.0,
                        }
                    ),
                ],
            }
        )
        bom.action_release()
        bom.write({"purchase_release_state": "released"})
        requirements = self.env["sab.purchase.requirement"]
        for line in bom.line_ids:
            requirements |= self.env["sab.purchase.requirement"].create(
                {"bom_line_id": line.id}
            )
        requirements._sab_prepare_order_quantities(force=True)
        return requirements.sorted("sequence")

    def test_only_explicitly_selected_requirement_is_ordered(self):
        requirements = self._create_released_requirements()
        first, second = requirements[0], requirements[1]

        # Product A deliberately has two suppliers; select the unambiguous product B
        # to prove that an individual row can be ordered without touching the other.
        action = second.action_create_standard_purchase_orders_from_selection()
        self.assertEqual(action["res_model"], "purchase.order")
        order = self.env["purchase.order"].browse(action["domain"][0][2])
        self.assertEqual(len(order), 1)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.sab_purchase_requirement_id, second)
        self.assertFalse(first.odoo_purchase_line_id)
        self.assertTrue(second.odoo_purchase_line_id)
        self.assertEqual(first.state, "open")

    def test_multiple_suppliers_require_explicit_choice(self):
        requirement = self._create_released_requirements()[0]
        action = requirement.action_create_standard_purchase_orders_from_selection()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sab.supplier.choice.wizard")

        Wizard = self.env["sab.supplier.choice.wizard"].with_context(
            **action["context"]
        )
        values = Wizard.default_get(["line_ids"])
        wizard = Wizard.create(values)
        self.assertEqual(len(wizard.line_ids), 1)
        wizard.line_ids.supplier_product_id = self.supplier_b_product_a

        purchase_action = wizard.action_continue()
        order = self.env["purchase.order"].browse(purchase_action["domain"][0][2])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.partner_id, self.supplier_b.partner_id)
        self.assertEqual(order.order_line.price_unit, 9.0)
        self.assertEqual(requirement.supplier_product_id, self.supplier_b_product_a)

    def test_draft_purchase_proposal_accepts_manual_product_and_text_lines(self):
        requirement = self._create_released_requirements()[1]
        action = requirement.action_create_standard_purchase_orders_from_selection()
        order = self.env["purchase.order"].browse(action["domain"][0][2])
        self.assertEqual(order.state, "draft")

        section = self.env["purchase.order.line"].create(
            {
                "order_id": order.id,
                "display_type": "line_section",
                "name": "Manuelle Zusatzpositionen",
            }
        )
        note = self.env["purchase.order.line"].create(
            {
                "order_id": order.id,
                "display_type": "line_note",
                "name": "Freie Bestelltextzeile",
            }
        )
        manual = self.env["purchase.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product_a.odoo_product_id.id,
                "name": "Manuell ergänzter Lagerartikel",
                "product_qty": 1.0,
                "product_uom_id": self.product_a.odoo_product_id.uom_po_id.id,
                "price_unit": 12.5,
                "date_planned": fields.Datetime.now(),
            }
        )

        self.assertIn(section, order.order_line)
        self.assertIn(note, order.order_line)
        self.assertIn(manual, order.order_line)
        self.assertFalse(manual.sab_purchase_requirement_id)
        self.assertEqual(manual.price_unit, 12.5)
