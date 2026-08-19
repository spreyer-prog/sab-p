from lxml import etree

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabOfferReleaseAndProcurementWorkspace(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("project.group_project_manager").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchasing").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )
        cls.env.ref("sab_project.group_sab_purchase_approver").write(
            {"user_ids": [Command.link(cls.env.user.id)]}
        )

        cls.partner = cls.env["res.partner"].create(
            {"name": "Kunde Angebotsfreigabe"}
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Projekt Angebotsfreigabe",
                "partner_id": cls.partner.id,
            }
        )
        cls.product = cls.env["sab.product"].create(
            {
                "name": "Produkt Beschaffungsarbeitsplatz",
                "manufacturer_article_number": "WORK-100",
                "price_mode": "fixed",
                "fixed_purchase_price": 10.0,
            }
        )
        cls.item = cls.env["sab.calculation.item"].create(
            {
                "name": "Kalkulationsartikel Angebotsfreigabe",
                "quotation_text": "Kalkulationsartikel Angebotsfreigabe",
                "product_line_ids": [
                    (
                        0,
                        0,
                        {
                            "position_type": "normal",
                            "product_id": cls.product.id,
                            "quantity": 1.0,
                        },
                    )
                ],
            }
        )
        cls.supplier_partner = cls.env["res.partner"].create(
            {
                "name": "Lieferant Beschaffungsarbeitsplatz",
                "email": "workspace@example.invalid",
            }
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {
                "name": "Lieferant Beschaffungsarbeitsplatz",
                "partner_id": cls.supplier_partner.id,
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.product.id,
                "supplier_article_number": "SUP-WORK-100",
                "purchase_price": 10.0,
                "packaging_quantity": 1.0,
                "minimum_order_quantity": 1.0,
                "preferred": True,
            }
        )

    def test_explicit_offer_release_locks_lv_and_precedes_order_received(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": self.project.id,
                "sab_calculation_source": "lv",
            }
        )
        line = self.env["sab.offer.calculation.line"].create(
            {
                "order_id": order.id,
                "calculation_item_id": self.item.id,
                "quantity": 1.0,
                "lv_position": "01.02.03",
            }
        )
        mapping_domain = [
            ("project_id", "=", self.project.id),
            ("calculation_item_id", "=", self.item.id),
        ]
        self.assertFalse(self.env["sab.project.lv.mapping"].search(mapping_domain))

        with self.assertRaises(ValidationError):
            order.action_confirm()
        with self.assertRaises(ValidationError):
            order._sab_check_offer_output_release()

        order.action_sab_release_offer()
        self.assertEqual(order.sab_offer_release_state, "released")
        self.assertEqual(order.sab_offer_released_by_id, self.env.user)
        self.assertTrue(order.sab_offer_released_at)
        self.assertTrue(order._sab_check_offer_output_release())
        self.assertEqual(
            self.env["sab.project.lv.mapping"].search(mapping_domain).position_code,
            "01.02.03",
        )
        self.assertFalse(order.sab_offer_reuse_payload()["editable"])

        with self.assertRaises(ValidationError):
            line.write({"quantity": 2.0})
        with self.assertRaises(ValidationError):
            order.sab_offer_add_reuse_entry(
                "lv",
                self.env["sab.project.lv.mapping"].search(mapping_domain).id,
            )
        with self.assertRaises(ValidationError):
            order.order_line.write({"price_unit": 999.0})

        revision_action = order.action_create_sab_revision()
        revision = self.env["sale.order"].browse(revision_action["res_id"])
        self.assertEqual(revision.sab_offer_release_state, "draft")
        self.assertFalse(revision.sab_offer_released_at)

    def test_released_total_bom_is_pushed_to_purchasing_dashboard(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sab_project_id": self.project.id,
                "sab_calculation_source": "schematic",
            }
        )
        self.env["sab.stock.movement"].create(
            {
                "product_id": self.product.id,
                "odoo_product_id": self.product.odoo_product_id.id,
                "movement_type": "receipt",
                "quantity": 2.0,
                "unit": "pcs",
                "unit_cost": 10.0,
                "note": "Anfangsbestand Dashboard-Test",
            }
        )
        bom = self.env["sab.project.bom"].create(
            {
                "name": "STL Dashboard / GESAMT",
                "order_id": order.id,
                "project_id": self.project.id,
                "bom_scope": "total",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "product_id": self.product.id,
                            "odoo_product_id": self.product.odoo_product_id.id,
                            "quantity": 5.0,
                            "unit": "pcs",
                            "supplier_product_id": self.supplier_product.id,
                            "unit_purchase_price": 10.0,
                        },
                    )
                ],
            }
        )

        bom.action_release()
        requirement = bom.purchase_requirement_ids
        self.assertEqual(len(requirement), 1)
        self.assertAlmostEqual(requirement.warehouse_on_hand, 2.0)
        self.assertAlmostEqual(requirement.project_reserved_quantity, 2.0)
        self.assertAlmostEqual(requirement.shortage_quantity, 3.0)
        self.assertAlmostEqual(requirement.suggested_order_quantity, 3.0)
        self.assertAlmostEqual(requirement.quantity_to_order, 3.0)
        self.assertAlmostEqual(requirement.warehouse_stock_value, 20.0)
        self.assertEqual(bom.purchase_release_state, "not_released")

        workspace_action = bom.action_open_procurement_workspace()
        self.assertEqual(workspace_action["res_model"], "sab.purchase.requirement")
        self.assertIn(("bom_id", "=", bom.id), workspace_action["domain"])

        with self.assertRaises(ValidationError):
            requirement.write({"quantity_to_order": -1.0})

        bom.action_release_for_purchase()
        requirement.write({"quantity_to_order": 2.0})
        purchase_action = requirement.action_create_purchase_orders()
        purchase_order = self.env["sab.purchase.order"].browse(
            purchase_action["domain"][0][2][0]
        )
        self.assertEqual(purchase_order.state, "draft")
        self.assertEqual(purchase_order.supplier_id, self.supplier)
        self.assertAlmostEqual(
            purchase_order.line_ids.quantity_ordered,
            2.0,
        )

    def test_dashboard_and_offer_release_controls_are_present(self):
        dashboard = self.env.ref(
            "sab_project.view_sab_procurement_dashboard_kanban"
        )
        dashboard_arch = etree.fromstring(dashboard.arch_db.encode("utf-8"))
        self.assertTrue(
            dashboard_arch.xpath(
                "//button[@name='action_open_procurement_workspace']"
            )
        )
        self.assertTrue(
            dashboard_arch.xpath(
                "//button[@name='action_release_for_purchase']"
            )
        )

        requirement_view = self.env.ref(
            "sab_project.view_sab_purchase_requirement_list_workspace"
        )
        requirement_arch = etree.fromstring(
            requirement_view.arch_db.encode("utf-8")
        )
        self.assertTrue(
            requirement_arch.xpath("//field[@name='quantity_to_order']")
        )
        self.assertTrue(
            requirement_arch.xpath("//field[@name='warehouse_stock_value']")
        )

        sale_view = self.env.ref("sab_project.sab_sale_order_form_inherit")
        sale_arch = etree.fromstring(sale_view.arch_db.encode("utf-8"))
        self.assertTrue(
            sale_arch.xpath(
                "//button[@name='action_sab_release_offer'][@string='Angebot zum Verschicken freigeben']"
            )
        )
        confirm_label = sale_arch.xpath(
            "//xpath[@expr=\"//button[@name='action_confirm']\"]"
            "/attribute[@name='string']"
        )
        self.assertEqual(len(confirm_label), 1)
        self.assertEqual((confirm_label[0].text or "").strip(), "Auftrag erhalten")

        send_control = self.env.ref(
            "sab_project.sab_sale_order_form_offer_release_controls"
        )
        send_arch = etree.fromstring(send_control.arch_db.encode("utf-8"))
        invisible = send_arch.xpath(
            "//xpath[@expr=\"//button[@name='action_quotation_send']\"]"
            "/attribute[@name='invisible']"
        )
        self.assertEqual(len(invisible), 1)
        self.assertIn("sab_project_id and", invisible[0].text or "")
