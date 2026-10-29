from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command


class SabPurchaseRequirementOdooBridge(models.Model):
    _inherit = "sab.purchase.requirement"

    odoo_purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Odoo-Bestellposition",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    odoo_purchase_order_id = fields.Many2one(
        related="odoo_purchase_line_id.order_id",
        string="Odoo-Bestellung",
        store=True,
        readonly=True,
    )
    odoo_purchase_state = fields.Selection(
        related="odoo_purchase_order_id.state",
        string="Odoo-Bestellstatus",
        store=True,
        readonly=True,
    )
    odoo_receipt_status = fields.Selection(
        related="odoo_purchase_order_id.receipt_status",
        string="Odoo-Wareneingangsstatus",
        store=True,
        readonly=True,
    )
    odoo_invoice_status = fields.Selection(
        related="odoo_purchase_order_id.invoice_status",
        string="Odoo-Rechnungsstatus",
        store=True,
        readonly=True,
    )
    odoo_quantity_received = fields.Float(
        related="odoo_purchase_line_id.qty_received",
        string="Über Odoo geliefert",
        digits="Product Unit",
        store=True,
        readonly=True,
    )
    odoo_quantity_invoiced = fields.Float(
        related="odoo_purchase_line_id.qty_invoiced",
        string="Über Odoo berechnet",
        digits="Product Unit",
        store=True,
        readonly=True,
    )
    expected_delivery_date = fields.Date(
        string="Voraussichtlicher Liefertermin",
        compute="_compute_expected_delivery_date_bridge",
        store=True,
        readonly=True,
    )

    @api.depends(
        "purchase_order_line_id.expected_delivery_date",
        "odoo_purchase_line_id.date_planned",
        "odoo_purchase_line_id.order_id.state",
    )
    def _compute_expected_delivery_date_bridge(self):
        for requirement in self:
            standard_line = requirement.odoo_purchase_line_id
            if standard_line and standard_line.order_id.state != "cancel":
                requirement.expected_delivery_date = fields.Date.to_date(
                    standard_line.date_planned
                )
            else:
                requirement.expected_delivery_date = (
                    requirement.purchase_order_line_id.expected_delivery_date
                    if requirement.purchase_order_line_id
                    else False
                )

    @api.depends(
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

    def _sab_check_standard_purchase_user(self):
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            return True
        raise AccessError(
            "Echte Odoo-Bestellungen dürfen nur durch einen im "
            "Mitarbeiterprofil freigeschalteten Einkaufsmitarbeiter erzeugt werden."
        )

    def _sab_standard_purchase_requirements(self):
        requirements = self.exists().filtered(
            lambda requirement: requirement.state == "open"
            and not requirement.optional
            and requirement.quantity_to_order > 0
            and (
                not requirement.odoo_purchase_line_id
                or requirement.odoo_purchase_order_id.state == "cancel"
            )
        )
        if not requirements:
            raise ValidationError(
                "In der Auswahl befindet sich keine offene Position mit einer "
                "Bestellmenge größer 0, für die noch keine aktive Odoo-Bestellung existiert."
            )

        not_released = requirements.filtered(
            lambda requirement: requirement.bom_id.purchase_release_state
            != "released"
        )
        if not_released:
            raise ValidationError(
                "Die Materialanforderung muss vor der Bestellerzeugung durch "
                "einen hinterlegten Bestellfreigeber freigegeben werden."
            )

        legacy_ordered = requirements.filtered(
            lambda requirement: requirement.purchase_order_line_id
            and requirement.purchase_order_id.state != "cancel"
        )
        if legacy_ordered:
            raise ValidationError(
                "Mindestens eine ausgewählte Position ist bereits in einer bisherigen "
                "SAB-P-Bestellung enthalten. Eine doppelte Bestellung wird verhindert."
            )

        without_product = requirements.filtered(
            lambda requirement: not requirement.odoo_product_id
        )
        if without_product:
            raise ValidationError(
                "Für folgende Positionen fehlt ein Odoo-Produkt: %s"
                % ", ".join(without_product.mapped("name"))
            )

        without_supplier = requirements.filtered(
            lambda requirement: not requirement.supplier_product_id.supplier_id
            or not requirement.supplier_product_id.supplier_id.partner_id
        )
        if without_supplier:
            raise ValidationError(
                "Für folgende Positionen fehlt ein Lieferant mit verknüpftem "
                "Odoo-Kontakt: %s"
                % ", ".join(without_supplier.mapped("name"))
            )
        return requirements

    def action_create_standard_purchase_orders(self):
        self._sab_check_standard_purchase_user()
        requirements = self._sab_standard_purchase_requirements()

        grouped = defaultdict(lambda: self.env["sab.purchase.requirement"])
        for requirement in requirements:
            grouped[requirement.supplier_product_id.supplier_id.id] |= requirement

        created_orders = self.env["purchase.order"]
        now = fields.Datetime.now()
        for supplier_id, supplier_requirements in grouped.items():
            supplier = self.env["sab.supplier"].browse(supplier_id)
            partner = supplier.partner_id
            project_refs = sorted(
                set(
                    supplier_requirements.mapped("project_id.sab_project_reference")
                    or supplier_requirements.mapped("project_id.display_name")
                )
            )
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
                if supplier_product.supplier_article_number:
                    description += (
                        "\nLieferanten-Art.-Nr.: "
                        + supplier_product.supplier_article_number
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
                            "price_unit": requirement.unit_purchase_price,
                            "date_planned": planned,
                            "sab_purchase_requirement_id": requirement.id,
                        }
                    )
                )

            order = self.env["purchase.order"].create(
                {
                    "partner_id": partner.id,
                    "origin": ", ".join(project_refs),
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


class PurchaseOrderSabBridge(models.Model):
    _inherit = "purchase.order"

    sab_is_suite_order = fields.Boolean(
        string="SAB-P Bestellung",
        default=False,
        copy=False,
        index=True,
    )
    sab_supplier_id = fields.Many2one(
        "sab.supplier",
        string="SAB-P Lieferant",
        copy=False,
        ondelete="restrict",
        index=True,
    )
    sab_project_ids = fields.Many2many(
        "project.project",
        relation="sab_odoo_purchase_order_project_rel",
        column1="purchase_order_id",
        column2="project_id",
        string="SAB-P Projekte",
        copy=False,
    )
    sab_procurement_bom_ids = fields.Many2many(
        "sab.project.bom",
        relation="sab_odoo_purchase_order_bom_rel",
        column1="purchase_order_id",
        column2="bom_id",
        string="Materialanforderungen",
        copy=False,
    )
    sab_source_cabinet_bom_ids = fields.Many2many(
        "sab.project.bom",
        string="Verteiler / Schaltschränke",
        compute="_compute_sab_purchase_context",
    )
    sab_requirement_count = fields.Integer(
        string="Materialpositionen",
        compute="_compute_sab_purchase_context",
    )

    @api.depends(
        "order_line.sab_purchase_requirement_id",
        "order_line.sab_source_cabinet_bom_id",
    )
    def _compute_sab_purchase_context(self):
        for order in self:
            lines = order.order_line.filtered("sab_purchase_requirement_id")
            order.sab_requirement_count = len(lines)
            order.sab_source_cabinet_bom_ids = lines.mapped(
                "sab_source_cabinet_bom_id"
            )

    def action_sab_view_material_requirements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Materialpositionen – %s") % self.name,
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [
                ("odoo_purchase_order_id", "=", self.id),
            ],
            "target": "current",
        }

    def button_cancel(self):
        lines = self.order_line.filtered("sab_purchase_requirement_id")
        result = super().button_cancel()
        for line in lines:
            requirement = line.sab_purchase_requirement_id
            if (
                requirement.odoo_purchase_line_id == line
                and line.qty_received <= 1e-9
                and not line.invoice_lines
            ):
                requirement.with_context(
                    sab_standard_purchase_link=True
                ).write({"odoo_purchase_line_id": False})
        return result


class PurchaseOrderLineSabBridge(models.Model):
    _inherit = "purchase.order.line"

    sab_purchase_requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="SAB-P Materialposition",
        copy=False,
        ondelete="restrict",
        index=True,
    )
    sab_project_id = fields.Many2one(
        related="sab_purchase_requirement_id.project_id",
        string="SAB-P Projekt",
        store=True,
        readonly=True,
    )
    sab_procurement_bom_id = fields.Many2one(
        related="sab_purchase_requirement_id.bom_id",
        string="Materialanforderung",
        store=True,
        readonly=True,
    )
    sab_source_cabinet_bom_id = fields.Many2one(
        related="sab_purchase_requirement_id.source_cabinet_bom_id",
        string="Verteiler / Schaltschrank",
        store=True,
        readonly=True,
    )
    sab_supplier_product_id = fields.Many2one(
        related="sab_purchase_requirement_id.supplier_product_id",
        string="SAB-P Lieferantenartikel",
        store=True,
        readonly=True,
    )
    sab_supplier_article_number = fields.Char(
        related="sab_supplier_product_id.supplier_article_number",
        string="Lieferanten-Art.-Nr.",
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        requirement_ids = [
            values.get("sab_purchase_requirement_id")
            for values in vals_list
            if values.get("sab_purchase_requirement_id")
        ]
        existing = self.env["sab.purchase.requirement"].browse(
            requirement_ids
        ).filtered(
            lambda requirement: requirement.odoo_purchase_line_id
            and requirement.odoo_purchase_order_id.state != "cancel"
        )
        if existing:
            raise ValidationError(
                "Mindestens eine Materialposition ist bereits mit einer aktiven "
                "Odoo-Bestellposition verknüpft."
            )

        lines = super().create(vals_list)
        for line in lines.filtered("sab_purchase_requirement_id"):
            line.sab_purchase_requirement_id.with_context(
                sab_standard_purchase_link=True
            ).write({"odoo_purchase_line_id": line.id})
        return lines

    def unlink(self):
        links = [
            (line.sab_purchase_requirement_id, line)
            for line in self
            if line.sab_purchase_requirement_id
        ]
        result = super().unlink()
        for requirement, line in links:
            if requirement.exists() and requirement.odoo_purchase_line_id.id == line.id:
                requirement.with_context(
                    sab_standard_purchase_link=True
                ).write({"odoo_purchase_line_id": False})
        return result


class StockMoveSabPurchaseBridge(models.Model):
    _inherit = "stock.move"

    sab_purchase_requirement_id = fields.Many2one(
        related="purchase_line_id.sab_purchase_requirement_id",
        string="SAB-P Materialposition",
        store=True,
        readonly=True,
    )
    sab_project_id = fields.Many2one(
        related="purchase_line_id.sab_project_id",
        string="SAB-P Projekt",
        store=True,
        readonly=True,
    )
    sab_procurement_bom_id = fields.Many2one(
        related="purchase_line_id.sab_procurement_bom_id",
        string="Materialanforderung",
        store=True,
        readonly=True,
    )
    sab_source_cabinet_bom_id = fields.Many2one(
        related="purchase_line_id.sab_source_cabinet_bom_id",
        string="Verteiler / Schaltschrank",
        store=True,
        readonly=True,
    )


class StockPickingSabPurchaseBridge(models.Model):
    _inherit = "stock.picking"

    sab_is_suite_receipt = fields.Boolean(
        string="SAB-P Wareneingang",
        compute="_compute_sab_purchase_context",
        store=True,
        index=True,
    )
    sab_project_ids = fields.Many2many(
        "project.project",
        relation="sab_stock_picking_project_rel",
        column1="picking_id",
        column2="project_id",
        string="SAB-P Projekte",
        compute="_compute_sab_purchase_context",
        store=True,
    )
    sab_source_cabinet_bom_ids = fields.Many2many(
        "sab.project.bom",
        relation="sab_stock_picking_cabinet_rel",
        column1="picking_id",
        column2="bom_id",
        string="Verteiler / Schaltschränke",
        compute="_compute_sab_purchase_context",
        store=True,
    )
    sab_supplier_delivery_note_number = fields.Char(
        string="Lieferanten-Lieferscheinnummer",
        copy=False,
        index=True,
    )
    sab_supplier_delivery_note_date = fields.Date(
        string="Lieferanten-Lieferscheindatum",
        copy=False,
    )
    sab_supplier_delivery_note_file = fields.Binary(
        string="Lieferanten-Lieferschein",
        attachment=True,
        copy=False,
    )
    sab_supplier_delivery_note_filename = fields.Char(
        string="Dateiname Lieferschein",
        copy=False,
    )

    @api.depends(
        "move_ids.sab_purchase_requirement_id",
        "move_ids.sab_project_id",
        "move_ids.sab_source_cabinet_bom_id",
        "move_ids.purchase_line_id.order_id.sab_is_suite_order",
    )
    def _compute_sab_purchase_context(self):
        for picking in self:
            suite_moves = picking.move_ids.filtered(
                lambda move: move.purchase_line_id.order_id.sab_is_suite_order
            )
            picking.sab_is_suite_receipt = bool(suite_moves)
            picking.sab_project_ids = suite_moves.mapped("sab_project_id")
            picking.sab_source_cabinet_bom_ids = suite_moves.mapped(
                "sab_source_cabinet_bom_id"
            )


class AccountMoveLineSabPurchaseBridge(models.Model):
    _inherit = "account.move.line"

    sab_purchase_requirement_id = fields.Many2one(
        related="purchase_line_id.sab_purchase_requirement_id",
        string="SAB-P Materialposition",
        store=True,
        readonly=True,
    )
    sab_project_id = fields.Many2one(
        related="purchase_line_id.sab_project_id",
        string="SAB-P Projekt",
        store=True,
        readonly=True,
    )
    sab_source_cabinet_bom_id = fields.Many2one(
        related="purchase_line_id.sab_source_cabinet_bom_id",
        string="Verteiler / Schaltschrank",
        store=True,
        readonly=True,
    )


class AccountMoveSabPurchaseBridge(models.Model):
    _inherit = "account.move"

    sab_is_suite_vendor_bill = fields.Boolean(
        string="SAB-P Eingangsrechnung",
        compute="_compute_sab_purchase_context",
        store=True,
        index=True,
    )
    sab_purchase_order_ids = fields.Many2many(
        "purchase.order",
        relation="sab_account_move_purchase_order_rel",
        column1="account_move_id",
        column2="purchase_order_id",
        string="SAB-P Bestellungen",
        compute="_compute_sab_purchase_context",
        store=True,
    )
    sab_project_ids = fields.Many2many(
        "project.project",
        relation="sab_account_move_project_rel",
        column1="account_move_id",
        column2="project_id",
        string="SAB-P Projekte",
        compute="_compute_sab_purchase_context",
        store=True,
    )

    @api.depends(
        "invoice_line_ids.purchase_line_id.order_id.sab_is_suite_order",
        "invoice_line_ids.purchase_line_id.sab_project_id",
    )
    def _compute_sab_purchase_context(self):
        for move in self:
            purchase_lines = move.invoice_line_ids.mapped("purchase_line_id").filtered(
                lambda line: line.order_id.sab_is_suite_order
            )
            move.sab_purchase_order_ids = purchase_lines.mapped("order_id")
            move.sab_project_ids = purchase_lines.mapped("sab_project_id")
            move.sab_is_suite_vendor_bill = bool(purchase_lines)
