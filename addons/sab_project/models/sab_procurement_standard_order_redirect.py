from odoo import fields, models, _


class SabPurchaseRequirementStandardOrderSelection(models.Model):
    _inherit = "sab.purchase.requirement"

    def action_create_standard_purchase_orders_from_selection(self):
        """Create native Odoo purchase orders only for explicitly selected rows.

        Unselected open requirements remain untouched. If at least one selected
        product has more than one currently valid supplier article, purchasing
        must explicitly choose the supplier before the proposals are generated.
        """
        requirements = self._sab_standard_purchase_requirements()
        SupplierProduct = self.env["sab.supplier.product"]
        today = fields.Date.today()
        needs_choice = False

        for requirement in requirements:
            candidates = SupplierProduct.search(
                [
                    ("active", "=", True),
                    ("odoo_product_id", "=", requirement.odoo_product_id.id),
                    ("supplier_id.partner_id", "!=", False),
                ]
            ).filtered(
                lambda candidate: (
                    not candidate.valid_from or candidate.valid_from <= today
                )
                and (
                    not candidate.valid_until or candidate.valid_until >= today
                )
            )
            if len(candidates) > 1:
                needs_choice = True
                break
            if len(candidates) == 1 and requirement.supplier_product_id != candidates:
                supplier_product = candidates[0]
                requirement.write(
                    {
                        "supplier_product_id": supplier_product.id,
                        "unit_purchase_price": supplier_product.net_purchase_price,
                    }
                )

        if needs_choice:
            return {
                "type": "ir.actions.act_window",
                "name": _("Lieferant auswählen"),
                "res_model": "sab.supplier.choice.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "active_ids": requirements.ids,
                    "sab_requirement_ids": requirements.ids,
                },
            }
        return requirements.action_create_standard_purchase_orders()
