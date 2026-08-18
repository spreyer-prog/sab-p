from odoo import api, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineLv(models.Model):
    _inherit = "sab.offer.calculation.line"

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
            map_vals = {"project_id": order.sab_project_id.id, "position_code": code, "is_ntg": True, "ntg_number": number, "first_order_id": order.id}
            if calc_id:
                map_vals["calculation_item_id"] = calc_id
            else:
                map_vals["odoo_product_id"] = product_id
            Mapping.create(map_vals)
            vals["lv_position"] = code
            vals["is_ntg"] = True
        return vals

    def sab_lock_lv_positions(self):
        Mapping = self.env["sab.project.lv.mapping"]
        for line in self.filtered(lambda l: l.line_type == "item" and not l.parent_section_id and l.order_id.sab_calculation_source == "lv"):
            if not line.order_id.sab_project_id or not (line.lv_position or "").strip():
                continue
            mapping = line._sab_lv_mapping(line.order_id, line.calculation_item_id.id, line.odoo_product_id.id)
            if mapping:
                if mapping.position_code != line.lv_position or mapping.is_ntg != line.is_ntg:
                    raise ValidationError(f"Die Position {mapping.position_code} ist für diesen Artikel im Projekt festgeschrieben.")
                continue
            vals = {"project_id": line.order_id.sab_project_id.id, "position_code": line.lv_position.strip(), "is_ntg": line.is_ntg or line.lv_position.upper().startswith("NTG"), "first_order_id": line.order_id.id}
            if vals["is_ntg"]:
                try:
                    vals["ntg_number"] = int(vals["position_code"].split()[-1])
                except (ValueError, IndexError):
                    vals["ntg_number"] = Mapping.next_ntg_number(line.order_id.sab_project_id)
                    vals["position_code"] = f"NTG {vals['ntg_number']}"
                    super(SabOfferCalculationLineLv, line).write({"lv_position": vals["position_code"], "is_ntg": True})
            if line.calculation_item_id:
                vals["calculation_item_id"] = line.calculation_item_id.id
            elif line.odoo_product_id:
                vals["odoo_product_id"] = line.odoo_product_id.id
            else:
                continue
            Mapping.create(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            order = self.env["sale.order"].browse(values.get("order_id")).exists() if values.get("order_id") else self.env["sale.order"]
            values = self._sab_apply_project_position(values, order)
            prepared.append(values)
        return super().create(prepared)

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
                    raise ValidationError(f"Die LV-/NTG-Position {mapping.position_code} ist projektbezogen festgeschrieben und darf nicht geändert werden.")
            values = self._sab_apply_project_position(dict(vals), record.order_id)
            return super().write(values)
        return super().write(vals)
