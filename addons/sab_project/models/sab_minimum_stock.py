from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ProductTemplateSabMinimumStock(models.Model):
    _inherit = "product.template"

    sab_minimum_stock_quantity = fields.Float(
        string="Mindestbestand",
        digits=(16, 3),
        default=0.0,
        help=(
            "Gewünschter frei verfügbarer Lagerbestand nach Berücksichtigung "
            "aller Projektreservierungen und bereits offenen Bestellungen. "
            "Der Wert 0 deaktiviert die Mindestbestandsprüfung."
        ),
    )

    @api.constrains("sab_minimum_stock_quantity")
    def _check_sab_minimum_stock_quantity(self):
        for template in self:
            if template.sab_minimum_stock_quantity < 0:
                raise ValidationError(
                    _("Der Mindestbestand darf nicht negativ sein.")
                )


class SabProductMinimumStock(models.Model):
    _inherit = "sab.product"

    minimum_stock_quantity = fields.Float(
        string="Mindestbestand",
        digits=(16, 3),
        default=0.0,
        help="Altbestandsfeld; wird in den normalen Odoo-Produktstamm synchronisiert.",
    )

    @api.constrains("minimum_stock_quantity")
    def _check_minimum_stock_quantity(self):
        for product in self:
            if product.minimum_stock_quantity < 0:
                raise ValidationError(
                    _("Der Mindestbestand darf nicht negativ sein.")
                )

    def _odoo_product_values(self):
        values = super()._odoo_product_values()
        self.ensure_one()
        values["sab_minimum_stock_quantity"] = (
            self.minimum_stock_quantity or 0.0
        )
        return values

    def write(self, vals):
        result = super().write(vals)
        if (
            "minimum_stock_quantity" in vals
            and not self.env.context.get("skip_odoo_product_sync")
        ):
            self._sync_to_odoo_product()
        return result


class SabPurchaseRequirementMinimumStock(models.Model):
    _inherit = "sab.purchase.requirement"

    minimum_stock_quantity = fields.Float(
        string="Mindestbestand",
        digits=(16, 3),
        compute="_compute_minimum_stock_replenishment",
        compute_sudo=True,
    )
    projected_free_stock = fields.Float(
        string="Voraussichtlich frei nach offenen Bestellungen",
        digits=(16, 3),
        compute="_compute_minimum_stock_replenishment",
        compute_sudo=True,
    )
    minimum_stock_replenishment_quantity = fields.Float(
        string="Zusatzmenge bis Mindestbestand",
        digits=(16, 3),
        compute="_compute_minimum_stock_replenishment",
        compute_sudo=True,
    )
    minimum_stock_below = fields.Boolean(
        string="Mindestbestand unterschritten",
        compute="_compute_minimum_stock_replenishment",
        compute_sudo=True,
    )
    include_minimum_stock_replenishment = fields.Boolean(
        string="Mindestbestand mit auffüllen",
        default=False,
        copy=False,
        help=(
            "Standardmäßig wird ausschließlich der tatsächliche Fehlbestand "
            "bestellt. Mit dieser Auswahl wird zusätzlich genau die Menge "
            "bestellt, die zum Wiederauffüllen des hinterlegten Mindestbestands "
            "erforderlich ist."
        ),
    )
    supplier_quantity_warning = fields.Char(
        string="Lieferantenhinweis zur Bestellmenge",
        compute="_compute_supplier_quantity_warning",
    )

    @api.depends(
        "quantity",
        "state",
        "stock_movement_ids.movement_type",
        "stock_movement_ids.quantity",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_id.state",
    )
    def _compute_procurement_quantities(self):
        """Use the real shortage as the proposal; never round automatically.

        Supplier packaging units and supplier minimum order quantities remain
        visible as warnings. They do not silently increase a project demand.
        """
        super()._compute_procurement_quantities()
        for requirement in self:
            requirement.suggested_order_quantity = max(
                requirement.shortage_quantity or 0.0,
                0.0,
            )

    def _minimum_stock_product_values(self):
        self.ensure_one()
        legacy, product = self._stock_identity()
        minimum = 0.0
        if product:
            minimum = (
                product.product_tmpl_id.sab_minimum_stock_quantity or 0.0
            )
        elif legacy:
            minimum = legacy.minimum_stock_quantity or 0.0
        return legacy, product, max(minimum, 0.0)

    @api.depends(
        "warehouse_available",
        "shortage_quantity",
        "odoo_product_id",
        "product_id",
        "purchase_order_line_id.quantity_remaining",
        "purchase_order_id.state",
    )
    def _compute_minimum_stock_replenishment(self):
        Requirement = self.env["sab.purchase.requirement"].sudo()
        OrderLine = self.env["sab.purchase.order.line"].sudo()

        for requirement in self:
            legacy, product, minimum = (
                requirement._minimum_stock_product_values()
            )
            projected_free = max(
                requirement.warehouse_available or 0.0,
                0.0,
            )

            if product:
                requirement_domain = [
                    ("odoo_product_id", "=", product.id),
                    ("state", "in", ("open", "ordered")),
                ]
                order_line_domain = [
                    ("odoo_product_id", "=", product.id),
                    (
                        "order_id.state",
                        "in",
                        ("draft", "to_approve", "approved", "sent", "partial"),
                    ),
                ]
            elif legacy:
                requirement_domain = [
                    ("product_id", "=", legacy.id),
                    ("state", "in", ("open", "ordered")),
                ]
                order_line_domain = [
                    ("product_id", "=", legacy.id),
                    (
                        "order_id.state",
                        "in",
                        ("draft", "to_approve", "approved", "sent", "partial"),
                    ),
                ]
            else:
                requirement_domain = []
                order_line_domain = []

            if requirement_domain:
                open_requirements = Requirement.search(requirement_domain)
                total_open_shortage = sum(
                    open_requirements.mapped("shortage_quantity")
                )
                open_order_lines = OrderLine.search(order_line_domain)
                incoming_quantity = sum(
                    open_order_lines.mapped("quantity_remaining")
                )
                projected_free = max(
                    projected_free
                    + incoming_quantity
                    - total_open_shortage,
                    0.0,
                )

            replenishment = (
                max(minimum - projected_free, 0.0)
                if minimum > 0
                else 0.0
            )
            requirement.minimum_stock_quantity = minimum
            requirement.projected_free_stock = projected_free
            requirement.minimum_stock_replenishment_quantity = replenishment
            requirement.minimum_stock_below = replenishment > 1e-9

    @api.depends(
        "quantity_to_order",
        "supplier_product_id.packaging_quantity",
        "supplier_product_id.minimum_order_quantity",
    )
    def _compute_supplier_quantity_warning(self):
        for requirement in self:
            quantity = max(requirement.quantity_to_order or 0.0, 0.0)
            supplier_product = requirement.supplier_product_id
            warnings = []
            if quantity > 0 and supplier_product:
                supplier_minimum = max(
                    supplier_product.minimum_order_quantity or 0.0,
                    0.0,
                )
                packaging = max(
                    supplier_product.packaging_quantity or 0.0,
                    0.0,
                )
                if supplier_minimum > 0 and quantity + 1e-9 < supplier_minimum:
                    warnings.append(
                        _("Lieferanten-Mindestbestellmenge: %s")
                        % supplier_minimum
                    )
                if packaging > 0:
                    multiple = quantity / packaging
                    if abs(multiple - round(multiple)) > 1e-9:
                        warnings.append(
                            _("Verpackungseinheit des Lieferanten: %s")
                            % packaging
                        )
            requirement.supplier_quantity_warning = "; ".join(warnings)

    def _sab_policy_order_quantity(self, include_minimum=None):
        self.ensure_one()
        include = (
            self.include_minimum_stock_replenishment
            if include_minimum is None
            else bool(include_minimum)
        )
        quantity = max(self.shortage_quantity or 0.0, 0.0)
        if include:
            quantity += max(
                self.minimum_stock_replenishment_quantity or 0.0,
                0.0,
            )
        return quantity

    def _sab_prepare_order_quantities(self, force=False):
        for requirement in self.filtered(
            lambda record: record.state == "open"
            and not record.optional
            and not record.purchase_order_line_id
        ):
            requirement.invalidate_recordset(
                [
                    "suggested_order_quantity",
                    "shortage_quantity",
                    "project_reserved_quantity",
                ]
            )
            if force or not requirement.quantity_to_order_manual:
                requirement.with_context(
                    sab_prepare_order_quantity=True
                ).write(
                    {
                        "quantity_to_order": (
                            requirement._sab_policy_order_quantity()
                        ),
                        "quantity_to_order_manual": False,
                    }
                )
        return True

    @api.onchange("include_minimum_stock_replenishment")
    def _onchange_include_minimum_stock_replenishment(self):
        for requirement in self:
            requirement.quantity_to_order = (
                requirement._sab_policy_order_quantity()
            )
            requirement.quantity_to_order_manual = False

    def write(self, vals):
        if (
            "include_minimum_stock_replenishment" in vals
            and "quantity_to_order" not in vals
            and not self.env.context.get("sab_prepare_order_quantity")
        ):
            if len(self) > 1:
                for requirement in self:
                    requirement.write(vals)
                return True
            values = dict(vals)
            values["quantity_to_order"] = self._sab_policy_order_quantity(
                values.get("include_minimum_stock_replenishment")
            )
            values["quantity_to_order_manual"] = False
            return super(
                SabPurchaseRequirementMinimumStock,
                self.with_context(sab_prepare_order_quantity=True),
            ).write(values)
        return super().write(vals)

    def action_create_purchase_orders(self):
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
        ):
            raise AccessError(
                "Bestellvorschläge dürfen nur durch einen im Mitarbeiterprofil "
                "freigeschalteten Einkaufsmitarbeiter erzeugt werden."
            )

        requirements = self.exists().filtered(
            lambda requirement: requirement.state == "open"
            and not requirement.optional
            and not requirement.purchase_order_line_id
            and requirement.quantity_to_order > 0
        )
        if not requirements:
            raise ValidationError(
                "In der Auswahl befindet sich keine offene Position mit einer "
                "Bestellmenge größer 0."
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

        without_supplier = requirements.filtered(
            lambda requirement: not requirement.supplier_product_id.supplier_id
        )
        if without_supplier:
            names = ", ".join(
                without_supplier.mapped("odoo_product_id.display_name")
                or without_supplier.mapped("product_id.name")
                or without_supplier.mapped("name")
            )
            raise ValidationError(
                f"Für folgende Positionen fehlt ein Lieferantenartikel: {names}."
            )

        grouped = defaultdict(lambda: self.env["sab.purchase.requirement"])
        for requirement in requirements:
            grouped[requirement.supplier_id.id] |= requirement

        created_orders = self.env["sab.purchase.order"]
        for supplier_id, supplier_requirements in grouped.items():
            order = self.env["sab.purchase.order"].create(
                {
                    "supplier_id": supplier_id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "requirement_id": requirement.id,
                                "quantity_ordered": requirement.quantity_to_order,
                                "unit_purchase_price": requirement.unit_purchase_price,
                            },
                        )
                        for requirement in supplier_requirements.sorted(
                            key=lambda record: (
                                record.project_id.sab_project_reference or "",
                                record.source_cabinet_bom_id.name
                                if record.source_cabinet_bom_id
                                else "",
                                record.sequence,
                                record.id,
                            )
                        )
                    ],
                }
            )
            created_orders |= order

        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellvorschläge"),
            "res_model": "sab.purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created_orders.ids)],
            "target": "current",
        }
