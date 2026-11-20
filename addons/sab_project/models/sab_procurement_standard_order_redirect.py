from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabPurchaseRequirementStandardOrderSelection(models.Model):
    _inherit = "sab.purchase.requirement"

    def action_create_standard_purchase_orders_from_selection(self):
        """Create native Odoo purchase orders only for explicitly selected rows.

        Unselected open requirements remain untouched. Supplier resolution is
        deliberately performed before the normal standard-purchase validation so
        a missing or ambiguous supplier can be resolved interactively first.
        """
        self._sab_check_standard_purchase_user()
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
                _(
                    "In der Auswahl befindet sich keine offene Position mit einer "
                    "Bestellmenge größer 0, für die noch keine aktive Odoo-Bestellung existiert."
                )
            )

        not_released = requirements.filtered(
            lambda requirement: requirement.bom_id.purchase_release_state != "released"
        )
        if not_released:
            raise ValidationError(
                _(
                    "Die Materialanforderung muss vor der Bestellerzeugung durch "
                    "einen hinterlegten Bestellfreigeber freigegeben werden."
                )
            )

        without_product = requirements.filtered(
            lambda requirement: not requirement.odoo_product_id
        )
        if without_product:
            raise ValidationError(
                _("Für folgende Positionen fehlt ein Odoo-Produkt: %s")
                % ", ".join(without_product.mapped("name"))
            )

        legacy_ordered = requirements.filtered(
            lambda requirement: requirement.purchase_order_line_id
            and requirement.purchase_order_id.state != "cancel"
        )
        if legacy_ordered:
            raise ValidationError(
                _(
                    "Mindestens eine ausgewählte Position ist bereits in einer bisherigen "
                    "SAB-P-Bestellung enthalten. Eine doppelte Bestellung wird verhindert."
                )
            )

        SupplierProduct = self.env["sab.supplier.product"]
        today = fields.Date.today()
        needs_choice = False
        no_supplier = self.env["sab.purchase.requirement"]

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
            if not candidates:
                no_supplier |= requirement
                continue
            if len(candidates) > 1:
                needs_choice = True
                continue
            supplier_product = candidates[0]
            if requirement.supplier_product_id != supplier_product:
                requirement.write(
                    {
                        "supplier_product_id": supplier_product.id,
                        "unit_purchase_price": supplier_product.net_purchase_price,
                    }
                )

        if no_supplier:
            raise ValidationError(
                _("Für folgende Positionen ist kein gültiger Lieferant hinterlegt: %s")
                % ", ".join(no_supplier.mapped("odoo_product_id.display_name"))
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
