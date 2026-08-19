from datetime import date, timedelta

from lxml import etree

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabProcurementApprovalAndDelivery(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("project.group_project_manager").write({
            "user_ids": [Command.link(cls.env.user.id)],
        })

        cls.partner = cls.env["res.partner"].create({
            "name": "Kunde Beschaffungsübersicht",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Projekt Beschaffungsübersicht",
            "partner_id": cls.partner.id,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "sab_project_id": cls.project.id,
        })
        cls.manufacturer = cls.env["sab.manufacturer"].create({
            "name": "Hersteller Beschaffungsübersicht",
        })
        cls.supplier_partner = cls.env["res.partner"].create({
            "name": "Lieferant Beschaffungsübersicht",
            "email": "lieferant@example.invalid",
        })
        cls.supplier = cls.env["sab.supplier"].create({
            "name": "Lieferant Beschaffungsübersicht",
            "partner_id": cls.supplier_partner.id,
        })
        cls.product = cls.env["sab.product"].create({
            "name": "Leistungsschalter Beschaffungsübersicht",
            "manufacturer_id": cls.manufacturer.id,
            "manufacturer_article_number": "BES-100",
        })
        cls.supplier_product = cls.env["sab.supplier.product"].create({
            "supplier_id": cls.supplier.id,
            "product_id": cls.product.id,
            "supplier_article_number": "SUP-BES-100",
            "purchase_price": 25.0,
            "packaging_quantity": 1.0,
            "minimum_order_quantity": 1.0,
            "preferred": True,
        })

        cls.approver_profile = cls.env["sab.employee.profile"].create({
            "name": "Bestellfreigeber",
            "login": "bestellfreigabe@example.invalid",
            "email": "bestellfreigabe@example.invalid",
            "mobile_access": False,
            "purchase_approval_access": True,
        })
        cls.approver_profile.action_create_or_update_user()
        cls.approver_user = cls.approver_profile.user_id

        cls.purchasing_profile = cls.env["sab.employee.profile"].create({
            "name": "Einkaufsmitarbeiter",
            "login": "einkauf@example.invalid",
            "email": "einkauf@example.invalid",
            "mobile_access": False,
            "purchasing_access": True,
        })
        cls.purchasing_profile.action_create_or_update_user()
        cls.purchasing_user = cls.purchasing_profile.user_id

        cls.regular_user = cls.env["res.users"].create({
            "name": "Benutzer ohne Bestellfreigabe",
            "login": "ohne-freigabe@example.invalid",
            "email": "ohne-freigabe@example.invalid",
            "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
        })

    def _create_boms(self):
        cabinet_line = self.env["sab.offer.calculation.line"].create({
            "order_id": self.order.id,
            "line_type": "cabinet",
            "description": "UV1",
            "sequence": 10,
        })
        total_bom = self.env["sab.project.bom"].create({
            "name": "STL Beschaffungsübersicht / GESAMT",
            "order_id": self.order.id,
            "project_id": self.project.id,
            "bom_scope": "total",
            "line_ids": [(0, 0, {
                "sequence": 10,
                "product_id": self.product.id,
                "odoo_product_id": self.product.odoo_product_id.id,
                "quantity": 4.0,
                "unit": "pcs",
                "supplier_product_id": self.supplier_product.id,
                "unit_purchase_price": 25.0,
            })],
        })
        cabinet_bom = self.env["sab.project.bom"].create({
            "name": "STL Beschaffungsübersicht / UV1",
            "order_id": self.order.id,
            "project_id": self.project.id,
            "bom_scope": "cabinet",
            "cabinet_line_id": cabinet_line.id,
            "line_ids": [(0, 0, {
                "sequence": 10,
                "product_id": self.product.id,
                "odoo_product_id": self.product.odoo_product_id.id,
                "quantity": 2.0,
                "unit": "pcs",
                "supplier_product_id": self.supplier_product.id,
                "unit_purchase_price": 25.0,
            })],
        })
        total_bom.action_release()
        cabinet_bom.action_release()
        return total_bom, cabinet_bom

    def test_employee_profile_assigns_procurement_roles(self):
        self.assertIn(
            self.env.ref("sab_project.group_sab_purchase_approver"),
            self.approver_user.group_ids,
        )
        self.assertIn(
            self.env.ref("sab_project.group_sab_purchasing"),
            self.purchasing_user.group_ids,
        )
        self.assertNotIn(
            self.env.ref("project.group_project_manager"),
            self.approver_user.group_ids,
        )

    def test_only_profile_approver_releases_and_approves_order(self):
        total_bom, _cabinet_bom = self._create_boms()
        with self.assertRaises(AccessError):
            total_bom.with_user(self.regular_user).action_release_for_purchase()

        total_bom.with_user(self.approver_user).action_release_for_purchase()
        self.assertEqual(total_bom.purchase_release_state, "released")
        self.assertEqual(total_bom.purchase_released_by_id, self.approver_user)

        requirement = total_bom.purchase_requirement_ids
        purchase_action = requirement.with_user(
            self.purchasing_user
        ).action_create_purchase_orders()
        purchase_order = self.env["sab.purchase.order"].browse(
            purchase_action["domain"][0][2][0]
        )
        purchase_order.with_user(self.purchasing_user).action_submit_for_approval()

        with self.assertRaises(AccessError):
            purchase_order.with_user(self.regular_user).action_approve()

        purchase_order.with_user(self.approver_user).action_approve()
        self.assertEqual(purchase_order.state, "approved")
        self.assertEqual(purchase_order.approved_by_id, self.approver_user)

    def test_delivery_date_and_value_weighted_project_progress(self):
        total_bom, cabinet_bom = self._create_boms()
        self.env["sab.stock.movement"].create({
            "product_id": self.product.id,
            "odoo_product_id": self.product.odoo_product_id.id,
            "movement_type": "receipt",
            "quantity": 2.0,
            "unit": "pcs",
            "unit_cost": 25.0,
            "note": "Anfangsbestand",
        })

        total_bom.with_user(self.approver_user).action_release_for_purchase()
        requirement = total_bom.purchase_requirement_ids
        self.assertAlmostEqual(requirement.project_reserved_quantity, 2.0)
        self.project.invalidate_recordset()
        self.assertAlmostEqual(self.project.sab_material_required_value, 100.0)
        self.assertAlmostEqual(self.project.sab_material_available_value, 50.0)
        self.assertAlmostEqual(self.project.sab_material_available_percent, 50.0)
        self.assertAlmostEqual(self.project.sab_material_missing_percent, 50.0)
        self.assertAlmostEqual(self.project.sab_material_procured_percent, 50.0)

        action = requirement.with_user(
            self.purchasing_user
        ).action_create_purchase_orders()
        purchase_order = self.env["sab.purchase.order"].browse(
            action["domain"][0][2][0]
        )
        purchase_order.with_user(self.purchasing_user).action_submit_for_approval()
        self.project.invalidate_recordset()
        self.assertAlmostEqual(self.project.sab_material_procured_percent, 100.0)

        delivery_date = date.today() + timedelta(days=14)
        purchase_order.line_ids.with_user(self.purchasing_user).write({
            "expected_delivery_date": delivery_date,
        })
        requirement.invalidate_recordset()
        cabinet_bom.line_ids.invalidate_recordset()
        cabinet_bom.invalidate_recordset()

        self.assertEqual(requirement.expected_delivery_date, delivery_date)
        self.assertEqual(
            cabinet_bom.line_ids.purchase_requirement_id,
            requirement,
        )
        self.assertEqual(
            cabinet_bom.line_ids.expected_delivery_date,
            delivery_date,
        )
        self.assertEqual(
            cabinet_bom.sab_expected_delivery_date,
            delivery_date,
        )

    def test_project_form_contains_total_material_orders_and_cabinets(self):
        view = self.env.ref(
            "sab_project.sab_project_project_form_procurement_detail"
        )
        arch = etree.fromstring(view.arch_db.encode("utf-8"))
        self.assertTrue(arch.xpath("//page[@name='sab_material_procurement']"))
        self.assertTrue(arch.xpath("//page[@name='sab_total_material']"))
        self.assertTrue(arch.xpath("//page[@name='sab_project_purchase_orders']"))
        self.assertTrue(arch.xpath("//page[@name='sab_project_switchboards']"))

        order_view = self.env.ref(
            "sab_project.view_sab_purchase_order_form_delivery_and_approval"
        )
        order_arch = etree.fromstring(order_view.arch_db.encode("utf-8"))
        approve_button = order_arch.xpath(
            "//button[@name='action_approve']/attribute[@name='groups']"
        )
        self.assertEqual(len(approve_button), 1)
        self.assertEqual(
            (approve_button[0].text or "").strip(),
            "sab_project.group_sab_purchase_approver",
        )
