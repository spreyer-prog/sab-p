from odoo import api, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineSchematicLv(models.Model):
    _inherit = "sab.offer.calculation.line"

    @api.depends(
        "order_id.sab_project_id",
        "order_id.sab_calculation_source",
        "calculation_item_id",
        "odoo_product_id",
        "lv_position",
    )
    def _compute_lv_position_locked(self):
        for line in self:
            mapping = self.env["sab.project.lv.mapping"]
            if (
                line.line_type == "item"
                and line.order_id.sab_calculation_source in ("lv", "schematic")
                and line.order_id.sab_project_id
            ):
                mapping = line._sab_lv_mapping(
                    line.order_id,
                    line.calculation_item_id.id,
                    line.odoo_product_id.id,
                )
            line.lv_position_locked = bool(mapping)

    def _sab_apply_project_position(self, vals, order):
        if not order or not order.sab_project_id:
            return vals
        if vals.get("line_type", "item") != "item":
            return vals

        calc_id = vals.get("calculation_item_id")
        product_id = vals.get("odoo_product_id")
        if not (calc_id or product_id):
            return vals

        mapping = self._sab_lv_mapping(order, calc_id, product_id)
        if mapping:
            vals["lv_position"] = mapping.position_code
            vals["is_ntg"] = mapping.is_ntg
            return vals

        if order.sab_calculation_source == "schematic":
            if not self._sab_has_prior_lv_offer(order):
                raise ValidationError(
                    "Ein Schaltplan-Angebot setzt ein zuvor bepreistes LV-Angebot im selben Projekt voraus. "
                    "Bitte zuerst mindestens ein LV-Angebot senden oder bestätigen."
                )
            Mapping = self.env["sab.project.lv.mapping"]
            number = Mapping.next_ntg_number(order.sab_project_id)
            code = f"NTG {number}"
            map_vals = {
                "project_id": order.sab_project_id.id,
                "position_code": code,
                "is_ntg": True,
                "ntg_number": number,
                "first_order_id": order.id,
            }
            if calc_id:
                map_vals["calculation_item_id"] = calc_id
            else:
                map_vals["odoo_product_id"] = product_id
            Mapping.create(map_vals)
            vals["lv_position"] = code
            vals["is_ntg"] = True
            return vals

        if order.sab_calculation_source == "lv" and self._sab_has_prior_lv_offer(order):
            Mapping = self.env["sab.project.lv.mapping"]
            number = Mapping.next_ntg_number(order.sab_project_id)
            code = f"NTG {number}"
            map_vals = {
                "project_id": order.sab_project_id.id,
                "position_code": code,
                "is_ntg": True,
                "ntg_number": number,
                "first_order_id": order.id,
            }
            if calc_id:
                map_vals["calculation_item_id"] = calc_id
            else:
                map_vals["odoo_product_id"] = product_id
            Mapping.create(map_vals)
            vals["lv_position"] = code
            vals["is_ntg"] = True
        return vals


class SaleOrderSchematicLvRules(models.Model):
    _inherit = "sale.order"

    def _sab_validate_schematic_lv_basis(self):
        for order in self:
            if order.sab_calculation_source != "schematic":
                continue
            prior = self.env["sale.order"].search_count(
                [
                    ("sab_project_id", "=", order.sab_project_id.id),
                    ("id", "!=", order.id),
                    ("sab_calculation_source", "=", "lv"),
                    ("state", "in", ("sent", "sale", "done")),
                ]
            )
            if not prior:
                raise ValidationError(
                    "Ein Schaltplan-Angebot darf erst erstellt bzw. weitergeführt werden, "
                    "wenn im Projekt bereits ein bepreistes LV-Angebot gesendet oder bestätigt wurde."
                )
        return True
