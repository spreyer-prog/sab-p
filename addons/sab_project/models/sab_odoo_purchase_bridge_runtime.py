from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command


class SabSupplierOdooPurchaseBridge(models.Model):
    _inherit = "sab.supplier"

    def _sab_ensure_partner(self):
        Partner = self.env["res.partner"].sudo()
        for supplier in self:
            partner = supplier.partner_id.sudo()
            if not partner:
                partner = Partner.create(
                    {
                        "name": supplier.name,
                        "supplier_rank": 1,
                        "website": supplier.website or False,
                        "ref": supplier.supplier_number or False,
                    }
                )
                supplier.with_context(
                    skip_sab_supplier_partner_sync=True
                ).write({"partner_id": partner.id})
            else:
                values = {}
                if partner.supplier_rank < 1:
                    values["supplier_rank"] = 1
                if supplier.name and partner.name != supplier.name:
                    values["name"] = supplier.name
                if supplier.website and partner.website != supplier.website:
                    values["website"] = supplier.website
                if supplier.supplier_number and partner.ref != supplier.supplier_number:
                    values["ref"] = supplier.supplier_number
                if values:
                    partner.write(values)
        return self.mapped("partner_id")

    @api.model_create_multi
    def create(self, vals_list):
        suppliers = super().create(vals_list)
        if not self.env.context.get("skip_sab_supplier_partner_sync"):
            suppliers._sab_ensure_partner()
        return suppliers

    def write(self, vals):
        result = super().write(vals)
        if (
            not self.env.context.get("skip_sab_supplier_partner_sync")
            and set(vals) & {"name", "supplier_number", "website", "partner_id"}
        ):
            self._sab_ensure_partner()
        return result


class SabSupplierProductOdooPurchaseBridge(models.Model):
    _inherit = "sab.supplier.product"

    odoo_supplierinfo_id = fields.Many2one(
        "product.supplierinfo",
        string="Odoo-Lieferantenpreisliste",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )

    def _sab_supplierinfo_values(self):
        self.ensure_one()
        product = self.odoo_product_id or self.product_id.odoo_product_id
        if not product or not self.supplier_id:
            return False
        partner = self.supplier_id._sab_ensure_partner()
        if not partner:
            return False
        purchase_base = (
            self.purchase_price
            or self.list_price
            or self.datanorm_price
            or product.standard_price
            or 0.0
        )
        return {
            "partner_id": partner.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_id": product.id,
            "product_code": self.supplier_article_number or False,
            "product_name": self.datanorm_type_name or False,
            "product_uom_id": (product.uom_po_id or product.uom_id).id,
            "min_qty": max(self.minimum_order_quantity or 0.0, 0.0),
            "price": purchase_base,
            "discount": min(max(self.discount_percent or 0.0, 0.0), 100.0),
            "delay": max(self.delivery_time_days or 0, 0),
            "date_start": self.valid_from or False,
            "date_end": self.valid_until or False,
            "sequence": 1 if self.preferred else 10,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
        }

    def _sab_sync_supplierinfo(self):
        SupplierInfo = self.env["product.supplierinfo"].sudo()
        for supplier_product in self.filtered("active"):
            values = supplier_product._sab_supplierinfo_values()
            if not values:
                continue
            target = supplier_product.odoo_supplierinfo_id.sudo()
            if not target:
                target = SupplierInfo.search(
                    [
                        ("partner_id", "=", values["partner_id"]),
                        ("product_id", "=", values["product_id"]),
                        ("product_code", "=", values["product_code"]),
                        ("company_id", "=", values["company_id"]),
                    ],
                    limit=1,
                )
            if target:
                target.write(values)
            else:
                target = SupplierInfo.create(values)
            if supplier_product.odoo_supplierinfo_id != target:
                supplier_product.with_context(
                    skip_sab_supplierinfo_sync=True
                ).write({"odoo_supplierinfo_id": target.id})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        supplier_products = super().create(vals_list)
        if not self.env.context.get("skip_sab_supplierinfo_sync"):
            supplier_products._sab_sync_supplierinfo()
        return supplier_products

    def write(self, vals):
        result = super().write(vals)
        watched = {
            "active",
            "supplier_id",
            "odoo_product_id",
            "product_id",
            "supplier_article_number",
            "datanorm_type_name",
            "list_price",
            "datanorm_price",
            "purchase_price",
            "discount_percent",
            "minimum_order_quantity",
            "delivery_time_days",
            "valid_from",
            "valid_until",
            "preferred",
        }
        if (
            not self.env.context.get("skip_sab_supplierinfo_sync")
            and set(vals) & watched
        ):
            self._sab_sync_supplierinfo()
        return result


class SabPurchaseRequirementOdooPurchaseRuntime(models.Model):
    _inherit = "sab.purchase.requirement"

    odoo_purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Odoo-Bestellposition",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )

    @api.depends(
        "quantity",
        "state",
        "stock_movement_ids.movement_type",
        "stock_movement_ids.quantity",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_line_id.quantity_remaining",
        "purchase_order_line_id.order_id.state",
        "purchase_order_id.state",
        "odoo_purchase_line_id.order_id.state",
        "odoo_purchase_line_id.product_qty",
        "odoo_purchase_line_id.qty_received",
        "odoo_purchase_line_id.qty_invoiced",
    )
    def _compute_procurement_quantities(self):
        super()._compute_procurement_quantities()
        for requirement in self:
            line = requirement.odoo_purchase_line_id
            if not line or requirement.state == "cancel":
                continue

            required = max(requirement.quantity or 0.0, 0.0)
            commissioned = max(
                getattr(requirement, "commissioned_quantity", 0.0) or 0.0,
                0.0,
            )
            reserved_before_receipt = max(
                requirement.project_reserved_quantity or 0.0,
                0.0,
            )
            allocatable_received = min(
                max(line.qty_received or 0.0, 0.0),
                max(required - commissioned - reserved_before_receipt, 0.0),
            )
            allocated = min(
                reserved_before_receipt + allocatable_received,
                max(required - commissioned, 0.0),
            )
            requirement.project_reserved_quantity = allocated
            requirement.shortage_quantity = max(
                required - commissioned - allocated,
                0.0,
            )
            requirement.suggested_order_quantity = requirement.shortage_quantity

            order = line.order_id
            if order.state == "cancel":
                continue
            if line.qty_received >= (line.product_qty or 0.0) - 1e-9:
                requirement.stock_status = "received"
            elif line.qty_received > 1e-9:
                requirement.stock_status = "partial_received"
            elif order.state in ("draft", "sent"):
                requirement.stock_status = "proposal"
            elif order.state == "to approve":
                requirement.stock_status = "approval"
            elif order.state == "purchase":
                requirement.stock_status = "ordered"

    def action_create_standard_purchase_orders(self):
        self._sab_check_standard_purchase_user()
        requirements = self._sab_standard_purchase_requirements()

        grouped = defaultdict(lambda: self.env["sab.purchase.requirement"])
        for requirement in requirements:
            supplier = requirement.supplier_product_id.supplier_id
            supplier._sab_ensure_partner()
            requirement.supplier_product_id._sab_sync_supplierinfo()
            grouped[supplier.id] |= requirement

        created_orders = self.env["purchase.order"]
        now = fields.Datetime.now()
        for supplier_id, supplier_requirements in grouped.items():
            supplier = self.env["sab.supplier"].browse(supplier_id)
            partner = supplier.partner_id
            project_refs = [
                reference
                for reference in supplier_requirements.mapped(
                    "project_id.sab_project_reference"
                )
                if reference
            ]
            if not project_refs:
                project_refs = [
                    name
                    for name in supplier_requirements.mapped(
                        "project_id.display_name"
                    )
                    if name
                ]
            project_refs = sorted(set(project_refs))
            project_ids = supplier_requirements.mapped("project_id").ids
            procurement_bom_ids = supplier_requirements.mapped("bom_id").ids

            line_commands = []
            for requirement in supplier_requirements.sorted(
                key=lambda record: (
                    record.project_id.sab_project_reference or "",
                    record.source_cabinet_bom_id.name
                    if record.source_cabinet_bom_id
                    else "",
                    record.sequence,
                    record.id,
                )
            ):
                product = requirement.odoo_product_id
                supplier_product = requirement.supplier_product_id
                planned = now + timedelta(
                    days=max(supplier_product.delivery_time_days or 0, 0)
                )
                description = product.with_context(
                    lang=partner.lang or self.env.user.lang
                ).display_name
                references = []
                if requirement.project_id.sab_project_reference:
                    references.append(requirement.project_id.sab_project_reference)
                if requirement.source_cabinet_bom_id:
                    references.append(requirement.source_cabinet_bom_id.name)
                if references:
                    description += "\nZuordnung: " + " / ".join(references)
                if supplier_product.supplier_article_number:
                    description += (
                        "\nLieferanten-Art.-Nr.: "
                        + supplier_product.supplier_article_number
                    )
                unit_price = (
                    requirement.unit_purchase_price
                    or supplier_product.net_purchase_price
                    or product.standard_price
                    or 0.0
                )
                line_commands.append(
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": description,
                            "product_qty": requirement.quantity_to_order,
                            "product_uom_id": (
                                product.uom_po_id or product.uom_id
                            ).id,
                            "price_unit": unit_price,
                            "discount": 0.0,
                            "date_planned": planned,
                            "sab_purchase_requirement_id": requirement.id,
                        }
                    )
                )

            order = self.env["purchase.order"].create(
                {
                    "partner_id": partner.id,
                    "origin": ", ".join(project_refs),
                    "user_id": self.env.user.id,
                    "sab_is_suite_order": True,
                    "sab_supplier_id": supplier.id,
                    "sab_project_ids": [Command.set(project_ids)],
                    "sab_procurement_bom_ids": [
                        Command.set(procurement_bom_ids)
                    ],
                    "order_line": line_commands,
                }
            )
            created_orders |= order

        return {
            "type": "ir.actions.act_window",
            "name": _("SAB-P Bestellvorschläge"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created_orders.ids)],
            "context": {"create": False},
            "target": "current",
        }


class PurchaseOrderSabPurchaseRuntime(models.Model):
    _inherit = "purchase.order"

    def _sab_sync_standard_requirement_states(self):
        for order in self:
            requirements = order.order_line.mapped("sab_purchase_requirement_id")
            if order.state == "purchase":
                requirements.filtered(lambda record: record.state == "open").write(
                    {"state": "ordered"}
                )
        return True

    def button_confirm(self):
        result = super().button_confirm()
        self._sab_sync_standard_requirement_states()
        return result

    def button_approve(self, force=False):
        result = super().button_approve(force=force)
        self._sab_sync_standard_requirement_states()
        return result


class PurchaseOrderLineSabPurchaseRuntime(models.Model):
    _inherit = "purchase.order.line"

    def unlink(self):
        for line in self.filtered("sab_purchase_requirement_id"):
            requirement = line.sab_purchase_requirement_id
            if requirement.odoo_purchase_line_id == line:
                requirement.with_context(
                    sab_standard_purchase_link=True
                ).write({"odoo_purchase_line_id": False})
        return super().unlink()


class StockPickingSabPurchaseRuntime(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        for picking in self.filtered(
            lambda record: record.sab_is_suite_receipt
            and record.picking_type_id.code == "incoming"
            and record.state not in ("done", "cancel")
        ):
            if not (picking.sab_supplier_delivery_note_number or "").strip():
                raise ValidationError(
                    "Bitte vor der Buchung des SAB-P-Wareneingangs die "
                    "Lieferanten-Lieferscheinnummer eintragen."
                )
            if not picking.sab_supplier_delivery_note_date:
                picking.sab_supplier_delivery_note_date = fields.Date.context_today(
                    picking
                )
        return super().button_validate()

    def _action_done(self):
        result = super()._action_done()
        requirements = self.filtered("sab_is_suite_receipt").move_ids.mapped(
            "sab_purchase_requirement_id"
        )
        for requirement in requirements:
            line = requirement.odoo_purchase_line_id
            if not line or line.order_id.state == "cancel":
                continue
            requirement.state = (
                "received"
                if line.qty_received >= (line.product_qty or 0.0) - 1e-9
                else "ordered"
            )
        return result


class ProjectProjectSabStandardPurchase(models.Model):
    _inherit = "project.project"

    sab_standard_purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="Odoo-Bestellungen",
        compute="_compute_sab_standard_purchase_orders",
    )
    sab_standard_purchase_order_count = fields.Integer(
        string="Odoo-Bestellungen",
        compute="_compute_sab_standard_purchase_orders",
    )

    @api.depends(
        "sab_purchase_requirement_ids.odoo_purchase_order_id",
        "sab_purchase_requirement_ids.odoo_purchase_order_id.state",
    )
    def _compute_sab_standard_purchase_orders(self):
        for project in self:
            orders = project.sab_purchase_requirement_ids.mapped(
                "odoo_purchase_order_id"
            ).filtered(lambda order: order.state != "cancel")
            project.sab_standard_purchase_order_ids = orders
            project.sab_standard_purchase_order_count = len(orders)

    def action_view_sab_standard_purchase_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Odoo-Bestellungen – %s") % self.display_name,
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [
                ("sab_is_suite_order", "=", True),
                ("sab_project_ids", "in", self.id),
            ],
            "context": {"create": False},
            "target": "current",
        }
