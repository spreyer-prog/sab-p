from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabProjectLvMapping(models.Model):
    _name = "sab.project.lv.mapping"
    _description = "SAB-P Projekt LV-/NTG-Zuordnung"
    _order = "project_id, is_ntg, ntg_number, position_code, id"

    project_id = fields.Many2one(
        "project.project",
        string="Projekt",
        required=True,
        ondelete="cascade",
        index=True,
    )
    calculation_item_id = fields.Many2one(
        "sab.calculation.item",
        string="Kalkulationsartikel",
        ondelete="restrict",
        index=True,
    )
    odoo_product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        ondelete="restrict",
        index=True,
    )
    position_code = fields.Char(
        string="LV-/NTG-Position",
        required=True,
        index=True,
    )
    is_ntg = fields.Boolean(string="NTG", default=False, index=True)
    ntg_number = fields.Integer(string="NTG-Nummer", default=0, index=True)
    first_order_id = fields.Many2one(
        "sale.order",
        string="Erstmals verwendet in",
        ondelete="set null",
        readonly=True,
    )

    @api.constrains("calculation_item_id", "odoo_product_id")
    def _check_source(self):
        for record in self:
            if bool(record.calculation_item_id) == bool(record.odoo_product_id):
                raise ValidationError(
                    "Eine LV-Zuordnung muss genau einem Kalkulationsartikel oder "
                    "einem Produkt zugeordnet sein."
                )

    @api.constrains(
        "project_id",
        "calculation_item_id",
        "odoo_product_id",
        "position_code",
    )
    def _check_unique_mapping(self):
        for record in self:
            domain = [
                ("project_id", "=", record.project_id.id),
                ("id", "!=", record.id),
            ]
            if record.calculation_item_id:
                domain.append(
                    ("calculation_item_id", "=", record.calculation_item_id.id)
                )
            else:
                domain.append(("odoo_product_id", "=", record.odoo_product_id.id))
            if self.search_count(domain):
                raise ValidationError(
                    "Für diesen Artikel existiert im Projekt bereits eine feste "
                    "LV-/NTG-Zuordnung."
                )

    def write(self, vals):
        immutable = {
            "project_id",
            "calculation_item_id",
            "odoo_product_id",
            "position_code",
            "is_ntg",
            "ntg_number",
        }
        if immutable & set(vals):
            for record in self:
                for field_name in immutable & set(vals):
                    incoming = vals[field_name]
                    current = record[field_name]
                    if record._fields[field_name].type == "many2one":
                        current = current.id or False
                    if incoming != current:
                        raise ValidationError(
                            "Eine einmal festgelegte projektbezogene LV-/NTG-Zuordnung "
                            "darf nicht geändert werden."
                        )
        return super().write(vals)

    @api.model
    def next_ntg_number(self, project):
        last_mapping = self.search(
            [("project_id", "=", project.id), ("is_ntg", "=", True)],
            order="ntg_number desc",
            limit=1,
        )
        highest = last_mapping.ntg_number or 0

        # Provisional NTG numbers in still editable quotations are taken into
        # account as well. They are not project mappings until the quotation is
        # explicitly released, but they must nevertheless remain unique.
        lines = self.env["sab.offer.calculation.line"].search(
            [
                ("order_id.sab_project_id", "=", project.id),
                ("order_id.state", "!=", "cancel"),
                ("line_type", "in", ("section", "item")),
                ("is_ntg", "=", True),
                ("lv_position", "!=", False),
            ]
        )
        for line in lines:
            code = (line.lv_position or "").strip().upper()
            if not code.startswith("NTG"):
                continue
            try:
                highest = max(highest, int(code.split()[-1]))
            except (ValueError, IndexError):
                continue
        return highest + 1
