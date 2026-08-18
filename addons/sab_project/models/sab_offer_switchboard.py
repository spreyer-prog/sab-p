from odoo import api, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineSwitchboard(models.Model):
    _inherit = "sab.offer.calculation.line"

    @staticmethod
    def _component_commands(item):
        """Snapshot normal BOM material only; auxiliary material remains calculation-only."""
        result = []
        for line in item.product_line_ids:
            if line.position_type in ("auxiliary_material", "information", "heading", "subtotal", "alternative"):
                continue
            odoo_product = line.odoo_product_id or (line.product_id.odoo_product_id if line.product_id else False)
            if not (odoo_product or line.product_id):
                continue
            result.append((0, 0, {
                "sequence": line.sequence,
                "product_id": line.product_id.id or False,
                "odoo_product_id": odoo_product.id or False,
                "position_type": line.position_type,
                "quantity_per_unit": line.quantity or 0.0,
                "unit": line.unit,
                "fixed_quantity": line.fixed_quantity,
                "optional": line.optional,
                "source_calculation_line_id": line.id,
                "supplier_product_id": line.selected_supplier_product_id.id or False,
                "unit_purchase_price": line.unit_purchase_price or 0.0,
                "note": line.note,
            }))
        return result

    @api.constrains("line_type", "description")
    def _check_switchboard_content(self):
        for line in self:
            if line.line_type == "cabinet" and not (line.description or "").strip():
                raise ValidationError("Ein Schaltschrank benötigt eine Bezeichnung, z. B. QV1 oder UV1.")


class SaleOrderSwitchboardRules(models.Model):
    _inherit = "sale.order"

    def _sab_validate_switchboard_structure(self):
        for order in self:
            if order.sab_calculation_source != "schematic":
                continue
            current_cabinet = False
            for line in order.sab_calculation_line_ids.sorted(key=lambda item: (item.sequence, item.id)):
                if line.line_type == "cabinet":
                    if current_cabinet:
                        raise ValidationError(f"Schaltschrank {current_cabinet.description} wurde nicht beendet, bevor ein neuer Schaltschrank begonnen wurde.")
                    current_cabinet = line
                elif line.line_type == "cabinet_end":
                    if not current_cabinet:
                        raise ValidationError("'Schaltschrank beenden' wurde ohne offenen Schaltschrank verwendet.")
                    current_cabinet = False
                elif line.line_type == "section" and not current_cabinet:
                    raise ValidationError(f"Das Bauteil '{line.description or 'ohne Bezeichnung'}' liegt außerhalb eines Schaltschrankes.")
                elif line.line_type == "item" and not current_cabinet:
                    raise ValidationError("Bei einem Schaltplan-Angebot muss jede Kalkulationsposition einem Schaltschrank zugeordnet sein.")
            if current_cabinet:
                raise ValidationError(f"Schaltschrank {current_cabinet.description} ist noch offen. Bitte 'Schaltschrank beenden' setzen.")
        return True
