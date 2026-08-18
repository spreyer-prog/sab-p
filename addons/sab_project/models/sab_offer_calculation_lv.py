from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineLv(models.Model):
    _inherit = "sab.offer.calculation.line"

    lv_position_locked = fields.Boolean(
        string="LV-Position projektweit festgeschrieben",
        compute="_compute_lv_position_locked",
    )

    def _sab_lv_mapping(self, order=None, calculation_item_id=False, odoo_product_id=False):
        order = order or self.order_id
        if not order or not order.sab_project_id:
            return self.env["sab.project.lv.mapping"]
        domain = [("project_id", "=", order.sab_project_id.id)]
        if calculation_item_id:
            domain.append(("calculation_item_id", "=", calculation_item_id))
        elif odoo_product_id:
            domain.append(("odoo_product_id", "=", odoo_product_id))
        else:
            return self.env["sab.project.lv.mapping"]
        return self.env["sab.project.lv.mapping"].search(domain, limit=1)

    @api.depends(
        "order_id.sab_project_id",
        "order_id.sab_calculation_source",
        "calculation_item_id",
        "odoo_product_id",
        "lv_position",
    )
    def _compute_lv_position_locked(self):
        for line in self:
            mapping = line._sab_lv_mapping(
                line.order_id,
                line.calculation_item_id.id,
                line.odoo_product_id.id,
            ) if line.line_type == "item" and line.order_id.sab_calculation_source == "lv" else self.env["sab.project.lv.mapping"]
            line.lv_position_locked = bool(mapping)

    @staticmethod
    def _sab_has_prior_lv_offer(order):
        return bool(order and order.sab_project_id and order.env["sale.order"].search_count([
            ("sab_project_id", "=", order.sab_project_id.id),
            ("id", "!=", order.id or 0),
            ("sab_calculation_source", "=", "lv"),
            ("state", "in", ("sent", "sale", "done")),
        ]))

    def _sab_apply_project_position(self, vals, order):
        if not order or order.sab_calculation_source != "lv" or not order.sab_project_id:
            return vals
        if vals.get("line_type", "item") != "item":
            return vals
        calc_id = vals.get("calculation_item_id")
        product_id = vals.get("odoo_product_id")
        mapping = self._sab_lv_mapping(order, calc_id, product_id)
        if mapping:
            vals["lv_position"] = mapping.position_code
            vals["is_ntg"] = mapping.is_ntg
            return vals
        if self._sab_has_prior_lv_offer(order) and (calc_id or product_id):
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

    def _sab_create_mapping_from_line(self):
        """Persist the first entered LV position immediately for the whole project.

        This deliberately happens already in a draft quotation. Once an article has
        received an LV/NTG position in a project, every later project quotation must
        reuse exactly that position.
        """
        Mapping = self.env["sab.project.lv.mapping"]
        for line in self:
            if (
                line.line_type != "item"
                or line.order_id.sab_calculation_source != "lv"
                or not line.order_id.sab_project_id
                or not (line.lv_position or "").strip()
                or not (line.calculation_item_id or line.odoo_product_id)
            ):
                continue
            mapping = line._sab_lv_mapping(
                line.order_id,
                line.calculation_item_id.id,
                line.odoo_product_id.id,
            )
            if mapping:
                if mapping.position_code != line.lv_position or mapping.is_ntg != line.is_ntg:
                    raise ValidationError(
                        f"Die LV-/NTG-Position {mapping.position_code} ist für diesen Artikel "
                        "im Projekt festgeschrieben und darf nicht geändert werden."
                    )
                continue
            position_code = line.lv_position.strip()
            is_ntg = bool(line.is_ntg or position_code.upper().startswith("NTG"))
            values = {
                "project_id": line.order_id.sab_project_id.id,
                "position_code": position_code,
                "is_ntg": is_ntg,
                "first_order_id": line.order_id.id,
            }
            if is_ntg:
                try:
                    values["ntg_number"] = int(position_code.split()[-1])
                except (ValueError, IndexError):
                    values["ntg_number"] = Mapping.next_ntg_number(line.order_id.sab_project_id)
                    values["position_code"] = f"NTG {values['ntg_number']}"
                    super(SabOfferCalculationLineLv, line).write({
                        "lv_position": values["position_code"],
                        "is_ntg": True,
                    })
            if line.calculation_item_id:
                values["calculation_item_id"] = line.calculation_item_id.id
            else:
                values["odoo_product_id"] = line.odoo_product_id.id
            Mapping.create(values)
        return True

    def sab_lock_lv_positions(self):
        # Kept as validation gate when sending/confirming, but mappings are now
        # already created immediately when the first LV position is entered.
        self._sab_create_mapping_from_line()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            order = self.env["sale.order"].browse(values.get("order_id")).exists() if values.get("order_id") else self.env["sale.order"]
            values = self._sab_apply_project_position(values, order)
            prepared.append(values)
        records = super().create(prepared)
        records._sab_create_mapping_from_line()
        return records

    def write(self, vals):
        if len(self) == 1:
            record = self
            calc_id = vals.get("calculation_item_id", record.calculation_item_id.id)
            product_id = vals.get("odoo_product_id", record.odoo_product_id.id)
            mapping = record._sab_lv_mapping(record.order_id, calc_id, product_id)
            if mapping and ("lv_position" in vals or "is_ntg" in vals):
                pos = vals.get("lv_position", record.lv_position)
                is_ntg = vals.get("is_ntg", record.is_ntg)
                if pos != mapping.position_code or is_ntg != mapping.is_ntg:
                    raise ValidationError(
                        f"Die LV-/NTG-Position {mapping.position_code} ist projektbezogen "
                        "festgeschrieben und darf nicht geändert werden."
                    )
            values = self._sab_apply_project_position(dict(vals), record.order_id)
            result = super().write(values)
            record._sab_create_mapping_from_line()
            return result
        result = super().write(vals)
        self._sab_create_mapping_from_line()
        return result
