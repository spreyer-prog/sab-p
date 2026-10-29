from odoo import api, fields, models


class SabPurchaseRequirementMinimumStockProjectionFix(models.Model):
    _inherit = "sab.purchase.requirement"

    quantity_to_order = fields.Float(
        string="Jetzt zu bestellen",
        digits=(16, 3),
        default=0.0,
        copy=False,
        help=(
            "Standardmäßig wird genau der tatsächliche Fehlbestand vorgeschlagen. "
            "Lieferanten-Mindestbestellmengen und Verpackungseinheiten erhöhen die "
            "Menge nicht automatisch, sondern werden lediglich als Hinweis angezeigt. "
            "Nur bei ausdrücklicher Auswahl wird zusätzlich der Produkt-Mindestbestand "
            "wieder aufgefüllt. Mit 0 bleibt die Position in dieser Bestellung außen vor."
        ),
    )

    @api.depends(
        "warehouse_available",
        "shortage_quantity",
        "odoo_product_id",
        "product_id",
        "purchase_order_line_id.quantity_remaining",
        "purchase_order_id.state",
    )
    def _compute_minimum_stock_replenishment(self):
        """Keep current free stock and add only surplus incoming quantities.

        The current free stock is already calculated after all reservations. It
        must not be reduced a second time by open project shortages. Incoming
        purchase quantities are counted toward the minimum stock only to the
        extent that they exceed all still-open shortages for the product.
        """
        Requirement = self.env["sab.purchase.requirement"].sudo()
        OrderLine = self.env["sab.purchase.order.line"].sudo()

        for requirement in self:
            legacy, product, minimum = (
                requirement._minimum_stock_product_values()
            )
            current_free = max(
                requirement.warehouse_available or 0.0,
                0.0,
            )
            projected_free = current_free

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
                total_open_shortage = sum(
                    Requirement.search(requirement_domain).mapped(
                        "shortage_quantity"
                    )
                )
                incoming_quantity = sum(
                    OrderLine.search(order_line_domain).mapped(
                        "quantity_remaining"
                    )
                )
                incoming_surplus = max(
                    incoming_quantity - total_open_shortage,
                    0.0,
                )
                projected_free = current_free + incoming_surplus

            replenishment = (
                max(minimum - projected_free, 0.0)
                if minimum > 0
                else 0.0
            )
            requirement.minimum_stock_quantity = minimum
            requirement.projected_free_stock = projected_free
            requirement.minimum_stock_replenishment_quantity = replenishment
            requirement.minimum_stock_below = replenishment > 1e-9
