from odoo import models
from odoo.exceptions import ValidationError


class SabPurchaseRequirementOdooUomValidation(models.Model):
    _inherit = "sab.purchase.requirement"

    def _sab_expected_odoo_uom(self):
        self.ensure_one()
        xmlid = {
            "pcs": "uom.product_uom_unit",
            "m": "uom.product_uom_meter",
            "kg": "uom.product_uom_kgm",
            "min": "uom.product_uom_minute",
            "h": "uom.product_uom_hour",
            "flat": "uom.product_uom_unit",
        }.get(self.unit or "pcs", "uom.product_uom_unit")
        return self.env.ref(xmlid)

    def _sab_standard_purchase_requirements(self):
        requirements = super()._sab_standard_purchase_requirements()
        errors = []
        for requirement in requirements:
            expected_uom = requirement._sab_expected_odoo_uom()
            supplier_product = requirement.supplier_product_id
            supplier_uom = supplier_product._sab_odoo_uom()

            supplier_product._sab_sync_product_uom()
            product = requirement.odoo_product_id
            product.invalidate_recordset(["uom_id", "uom_po_id"])
            product_uom = product.uom_po_id or product.uom_id

            if supplier_uom != expected_uom:
                errors.append(
                    "%s: Stückliste %s, Lieferantenartikel %s"
                    % (
                        requirement.name,
                        expected_uom.display_name,
                        supplier_uom.display_name,
                    )
                )
            elif product_uom != expected_uom:
                errors.append(
                    "%s: Stückliste %s, Odoo-Produkt %s"
                    % (
                        requirement.name,
                        expected_uom.display_name,
                        product_uom.display_name,
                    )
                )

        if errors:
            raise ValidationError(
                "Die Bestellung wurde nicht erzeugt, weil Mengeneinheiten "
                "widersprüchlich sind:\n- " + "\n- ".join(errors)
            )
        return requirements
