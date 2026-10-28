"""Exercise unsaved form rows, not just the ORM create/write path."""
from lxml import etree
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from ..models.sab_offer_live_preview import SNAPSHOT_NUMERIC_FIELDS


class TestSabOfferLivePreview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({"name": "Live preview test customer"})
        cls.project = cls.env["project.project"].create({
            "name": "Live preview test project", "partner_id": cls.customer.id,
        })
        cls.item = cls.env["sab.calculation.item"].create({
            "name": "Live preview 30 minutes", "quotation_text": "Assembly test",
            "legacy_time_minutes": 30, "mechanical_factor": 100,
            "wiring_factor": 0, "testing_factor": 0,
        })
        cls.other_item = cls.env["sab.calculation.item"].create({
            "name": "Live preview 60 minutes", "quotation_text": "Other assembly test",
            "legacy_time_minutes": 60, "mechanical_factor": 100,
            "wiring_factor": 0, "testing_factor": 0,
        })
        cls.product = cls.env["sab.product"].create({
            "name": "Live preview material", "price_mode": "fixed",
            "fixed_purchase_price": 10.0,
        }).odoo_product_id
        cls.factors = {
            "sab_hourly_rate": 80.0, "sab_material_factor": 1.0,
            "sab_aux_material_factor": 1.15, "sab_time_factor": 1.25,
            "sab_difficulty_factor": 1.0, "sab_packaging_factor": 1.03,
            "sab_skonto_factor": 1.03, "sab_margin_factor": 1.35,
            "sab_rebate_factor": 1.125, "sab_transport_cost": 0.0,
            "sab_object_discount_percent": 0.0,
        }

    def _form(self):
        defaults = dict(
            self.factors, partner_id=self.customer.id, sab_project_id=self.project.id,
            sab_calculation_source="lv", sale_order_template_id=False,
        )
        return Form(self.env["sale.order"].with_context(
            **{"default_" + key: value for key, value in defaults.items()}
        ), view="sale.view_order_form")

    def _counts(self):
        # A preview must not create orders, lines, components or LV mappings.
        return tuple(self.env[model].search_count([]) for model in (
            "sale.order", "sale.order.line", "sab.offer.calculation.line",
            "sab.offer.calculation.component", "sab.project.lv.mapping",
        ))

    def _saved_order(self):
        return self.env["sale.order"].create(dict(self.factors, **{
            "partner_id": self.customer.id, "sab_project_id": self.project.id,
            "sab_calculation_source": "lv",
            "sab_calculation_line_ids": [(0, 0, {
                "calculation_item_id": self.item.id, "quantity": 1,
                "lv_position": "1.1.1",
            })],
        }))

    def test_new_order_shows_price_and_total_before_first_save(self):
        before = self._counts()
        form = self._form()
        with form.sab_calculation_line_ids.new() as row:
            row.calculation_item_id = self.item
            row.lv_position = "1.1.1"
            row.quantity = 3
            self.assertAlmostEqual(row.unit_total_minutes, 30)
            self.assertAlmostEqual(row.unit_recommended_net_price, 80.56)
            self.assertAlmostEqual(row.recommended_net_price, 241.68)
        self.assertAlmostEqual(form.sab_offer_subtotal, 241.68)
        self.assertEqual(self._counts(), before)
        order = form.save()
        self.assertAlmostEqual(order.sab_calculation_line_ids.unit_recommended_net_price, 80.56)
        self.assertAlmostEqual(order.sab_offer_subtotal, 241.68)
        self.assertEqual(order.sab_offer_release_state, "draft")

    def test_quantity_changes_do_not_lose_unsaved_snapshot(self):
        form = self._form()
        with form.sab_calculation_line_ids.new() as row:
            row.calculation_item_id = self.item
            row.lv_position = "1.1.1"
            for quantity in (1, 3, 4, 0, 2):
                row.quantity = quantity
                self.assertAlmostEqual(row.unit_total_minutes, 30)
                self.assertAlmostEqual(row.unit_recommended_net_price, 80.56)
                self.assertAlmostEqual(row.recommended_net_price, round(80.56 * quantity, 2))

    def test_material_workspace_previews_product_before_save(self):
        before = self._counts()
        form = self._form()
        with form.sab_material_calculation_line_ids.new() as row:
            row.odoo_product_id = self.product
            row.quantity = 2
            self.assertAlmostEqual(row.unit_material_purchase, 10)
            self.assertAlmostEqual(row.unit_recommended_net_price, 16.11)
            self.assertAlmostEqual(row.recommended_net_price, 32.22)
        self.assertEqual(self._counts(), before)

    def test_edit_saved_order_quantity_uses_frozen_minutes_not_changed_master(self):
        order = self._saved_order()
        self.item.legacy_time_minutes = 60
        form = Form(order, view="sale.view_order_form")
        with form.sab_calculation_line_ids.edit(0) as row:
            row.quantity = 3
            self.assertAlmostEqual(row.unit_total_minutes, 30)
            self.assertAlmostEqual(row.recommended_net_price, 241.68)
        self.assertAlmostEqual(order.sab_calculation_line_ids.quantity, 1)
        form.save()
        self.assertAlmostEqual(order.sab_calculation_line_ids.unit_total_minutes, 30)
        self.assertAlmostEqual(order.sab_offer_subtotal, 241.68)

    def test_switching_article_refreshes_preview_and_clearing_removes_stale_price(self):
        form = self._form()
        with form.sab_calculation_line_ids.new() as row:
            row.calculation_item_id = self.item
            self.assertAlmostEqual(row.unit_recommended_net_price, 80.56)
            row.calculation_item_id = self.other_item
            self.assertAlmostEqual(row.unit_total_minutes, 60)
            self.assertAlmostEqual(row.unit_recommended_net_price, 161.12)
            row.calculation_item_id = self.env["sab.calculation.item"]
            self.assertAlmostEqual(row.unit_total_minutes, 0)
            self.assertAlmostEqual(row.unit_recommended_net_price, 0)
            # Leave a valid row in the form; the clearing itself was checked above.
            row.calculation_item_id = self.item
            row.lv_position = "1.1.1"

    def test_reselecting_original_article_restores_original_snapshot(self):
        order = self._saved_order()
        self.item.legacy_time_minutes = 90
        form = Form(order, view="sale.view_order_form")
        with form.sab_calculation_line_ids.edit(0) as row:
            row.calculation_item_id = self.other_item
            self.assertAlmostEqual(row.unit_total_minutes, 60)
            row.calculation_item_id = self.item
            self.assertAlmostEqual(row.unit_total_minutes, 30)
            self.assertAlmostEqual(row.unit_recommended_net_price, 80.56)
        self.assertAlmostEqual(order.sab_calculation_line_ids.unit_total_minutes, 30)

    def test_saving_first_quote_exposes_position_without_release(self):
        form = self._form()
        with form.sab_calculation_line_ids.new() as row:
            row.calculation_item_id = self.item
            row.lv_position = "1.1.1"
        order = form.save()
        payload = order.sab_offer_reuse_payload()
        found = [entry for entry in payload["lv_positions"] if entry["position"] == "1.1.1"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["position_status"], "Entwurf")
        self.assertEqual(order.sab_offer_release_state, "draft")
        self.assertFalse(self.env["sab.project.lv.mapping"].search([
            ("project_id", "=", self.project.id),
        ]))

    def test_released_offer_preview_does_not_change_snapshot(self):
        order = self._saved_order()
        order.action_sab_release_offer()
        original = order.sab_calculation_line_ids
        virtual = self.env["sab.offer.calculation.line"].new({
            "order_id": order.id, "line_type": "item",
            "calculation_item_id": self.other_item.id, "unit_total_minutes": 30,
        }, origin=original)
        virtual._onchange_sab_preview_calculation_item()
        self.assertAlmostEqual(virtual.unit_total_minutes, 30)
        self.assertAlmostEqual(original.unit_total_minutes, 30)

    def test_cabinet_product_does_not_receive_item_costs(self):
        virtual = self.env["sab.offer.calculation.line"].new({
            "line_type": "cabinet", "description": "Test cabinet",
            "odoo_product_id": self.product.id, "unit_material_purchase": 99,
        })
        virtual._onchange_sab_preview_product()
        self.assertEqual(virtual.odoo_product_id, self.product)
        self.assertAlmostEqual(virtual.unit_material_purchase, 0)
        self.assertEqual(virtual.description, "Test cabinet")

    def test_both_workspaces_keep_scalar_snapshot_fields(self):
        result = self.env["sale.order"].get_view(
            view_id=self.env.ref("sale.view_order_form").id, view_type="form",
        )
        arch = etree.fromstring(result["arch"].encode())
        for name in ("sab_calculation_line_ids", "sab_material_calculation_line_ids"):
            list_view = arch.xpath("//field[@name='%s']/list" % name)[0]
            for field in SNAPSHOT_NUMERIC_FIELDS:
                nodes = list_view.xpath("./field[@name='%s']" % field)
                self.assertEqual(len(nodes), 1)
                self.assertEqual(nodes[0].get("column_invisible"), "1")
                self.assertNotEqual(nodes[0].get("force_save"), "1")
