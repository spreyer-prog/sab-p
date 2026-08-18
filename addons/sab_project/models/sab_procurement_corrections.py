from odoo import api, models


class SabPurchaseRequirementProcurementCorrections(models.Model):
    _inherit = "sab.purchase.requirement"

    @api.depends(
        "product_id.manufacturer_supplier_id",
        "product_id.manufacturer_id",
        "odoo_product_id.sab_manufacturer_supplier_id",
        "odoo_product_id.sab_manufacturer_id",
    )
    def _compute_manufacturer_name(self):
        """Show the real DATANORM manufacturer, not the import supplier."""
        for requirement in self:
            legacy, product = requirement._stock_identity()
            datanorm_manufacturer = (
                product.sab_manufacturer_id
                if product
                else legacy.manufacturer_id
                if legacy
                else False
            )
            supplier_source = (
                product.sab_manufacturer_supplier_id
                if product
                else legacy.manufacturer_supplier_id
                if legacy
                else False
            )
            requirement.manufacturer_name = (
                datanorm_manufacturer.name
                if datanorm_manufacturer
                else supplier_source.name
                if supplier_source
                else ""
            )


class SabPurchaseOrderProcurementCorrections(models.Model):
    _inherit = "sab.purchase.order"

    @api.depends(
        "line_ids.project_id",
        "line_ids.purchase_total",
        "line_ids.quantity_ordered",
        "line_ids.quantity_received",
        "line_ids.unit_purchase_price",
    )
    def _compute_totals(self):
        """Calculate receipt progress without adding incompatible units."""
        for order in self:
            order.project_ids = order.line_ids.mapped("project_id")
            order.amount_total = sum(order.line_ids.mapped("purchase_total"))

            total_value = 0.0
            received_value = 0.0
            line_ratios = []
            for line in order.line_ids.filtered(lambda item: item.quantity_ordered > 0):
                ordered = max(line.quantity_ordered or 0.0, 0.0)
                received = min(max(line.quantity_received or 0.0, 0.0), ordered)
                unit_price = max(line.unit_purchase_price or 0.0, 0.0)
                total_value += ordered * unit_price
                received_value += received * unit_price
                line_ratios.append(received / ordered if ordered else 1.0)

            if total_value > 0:
                progress = received_value / total_value * 100.0
            elif line_ratios:
                progress = sum(line_ratios) / len(line_ratios) * 100.0
            else:
                progress = 0.0
            order.receipt_progress = min(max(progress, 0.0), 100.0)
