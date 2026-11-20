from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestSabAdminProcurementWithoutEmployeeRoles(TransactionCase):
    """Real admin test path while employee procurement roles are not configured yet."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin_user = cls.env["res.users"].create(
            {
                "name": "SAB-P Testadministrator ohne Einkaufsrolle",
                "login": "sab-admin-ohne-einkaufsrolle@example.invalid",
            }
        )
        cls.env.ref("base.group_system").write(
            {"user_ids": [Command.link(cls.admin_user.id)]}
        )
        # Make the test explicit: this user must not obtain any procurement role.
        for xmlid in (
            "sab_project.group_sab_purchasing",
            "sab_project.group_sab_purchase_approver",
            "sab_project.group_sab_warehouse",
        ):
            cls.env.ref(xmlid).write(
                {"user_ids": [Command.unlink(cls.admin_user.id)]}
            )

        cls.customer = cls.env["res.partner"].create(
            {"name": "Admin-Praxistest Kunde"}
        )
        cls.project = cls.env["project.project"].create(
            {"name": "Admin-Praxistest Projekt", "partner_id": cls.customer.id}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "sab_project_id": cls.project.id,
                "sab_calculation_source": "schematic",
            }
        )
        cls.supplier_partner = cls.env["res.partner"].create(
            {"name": "Admin-Praxistest Lieferant"}
        )
        cls.supplier = cls.env["sab.supplier"].create(
            {
                "name": "Admin-Praxistest Lieferant",
                "supplier_number": "ADMIN-E2E",
                "partner_id": cls.supplier_partner.id,
            }
        )
        cls.material = cls.env["sab.product"].create(
            {
                "name": "Admin-Praxistest Material",
                "manufacturer_article_number": "ADMIN-E2E-MAT",
            }
        )
        cls.supplier_product = cls.env["sab.supplier.product"].create(
            {
                "supplier_id": cls.supplier.id,
                "product_id": cls.material.id,
                "supplier_article_number": "ADMIN-E2E-SUP",
                "purchase_price": 12.34,
                "preferred": True,
            }
        )
        cls.cabinet_line = cls.env["sab.offer.calculation.line"].create(
            {
                "order_id": cls.order.id,
                "line_type": "cabinet",
                "description": "UV ADMIN E2E",
                "quantity": 1.0,
                "sequence": 10,
            }
        )
        common_line = {
            "sequence": 10,
            "product_id": cls.material.id,
            "odoo_product_id": cls.material.odoo_product_id.id,
            "quantity": 1.0,
            "unit": "pcs",
            "supplier_product_id": cls.supplier_product.id,
            "unit_purchase_price": 12.34,
        }
        cls.cabinet_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL ADMIN E2E / UV 1",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "cabinet",
                "cabinet_line_id": cls.cabinet_line.id,
                "line_ids": [Command.create(common_line)],
            }
        )
        cls.total_bom = cls.env["sab.project.bom"].create(
            {
                "name": "STL ADMIN E2E / GESAMT",
                "order_id": cls.order.id,
                "project_id": cls.project.id,
                "bom_scope": "total",
                "line_ids": [Command.create(common_line)],
            }
        )
        cls.cabinet_bom.action_release()
        cls.total_bom.action_release()
        cls.order.write({"state": "sale"})

        # Package creation is setup data. The actual operator path below starts
        # with an already existing package, matching the user's current database.
        handover = cls.total_bom.action_open_procurement_package_from_bom()
        Wizard = cls.env["sab.procurement.package.wizard"].with_context(
            **handover["context"]
        )
        values = Wizard.default_get(["order_id", "cabinet_bom_ids"])
        wizard = Wizard.create(values)
        package_action = wizard.action_create_procurement_package()
        cls.package = cls.env["sab.project.bom"].browse(package_action["res_id"])

    def test_admin_without_employee_roles_can_reach_real_purchase_proposal(self):
        admin_package = self.package.with_user(self.admin_user)

        # 1) Existing technically released package can be released to purchasing
        # without a configured employee approver during the temporary test phase.
        workspace_action = admin_package.action_release_for_purchase()
        self.assertEqual(workspace_action["res_model"], "sab.purchase.requirement")
        self.assertEqual(admin_package.purchase_release_state, "released")

        requirements = admin_package.purchase_requirement_ids.filtered(
            lambda requirement: requirement.state == "open"
            and not requirement.optional
        )
        self.assertEqual(len(requirements), 1)
        requirement = requirements.with_user(self.admin_user)

        # 2) The same admin must really be able to edit the requirement. This is
        # the ACL failure that previously only appeared in the browser.
        requirement.write({"note": "Admin-Praxistest bearbeitet"})
        self.assertEqual(requirement.note, "Admin-Praxistest bearbeitet")

        # 3) And the exact row-button path must create a real Odoo draft RFQ.
        requirement._sab_prepare_order_quantities(force=True)
        self.assertGreater(requirement.quantity_to_order, 0)
        purchase_action = requirement.action_create_standard_purchase_orders_from_selection()
        self.assertEqual(purchase_action["res_model"], "purchase.order")
        purchase_orders = self.env["purchase.order"].browse(
            purchase_action["domain"][0][2]
        )
        self.assertEqual(len(purchase_orders), 1)
        self.assertEqual(purchase_orders.state, "draft")
        self.assertEqual(
            purchase_orders.order_line.filtered(lambda line: not line.display_type)
            .sab_purchase_requirement_id,
            requirement,
        )
