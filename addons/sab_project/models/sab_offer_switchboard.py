from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabOfferCalculationLineSwitchboard(models.Model):
    _inherit = "sab.offer.calculation.line"

    line_type = fields.Selection(
        selection_add=[
            ("cabinet", "Schaltschrank"),
            ("cabinet_end", "Schaltschrank Ende"),
        ],
        ondelete={"cabinet": "cascade", "cabinet_end": "cascade"},
    )
    parent_cabinet_id = fields.Many2one(
        "sab.offer.calculation.line",
        string="Schaltschrank",
        ondelete="set null",
        index=True,
        domain="[('order_id', '=', order_id), ('line_type', '=', 'cabinet')]",
    )
    cabinet_line_ids = fields.One2many(
        "sab.offer.calculation.line",
        "parent_cabinet_id",
        string="Schaltschrankpositionen",
    )
    cabinet_total = fields.Monetary(
        string="Schaltschrank gesamt",
        currency_field="currency_id",
        compute="_compute_cabinet_total",
        store=True,
    )

    @api.depends("cabinet_line_ids.recommended_net_price", "cabinet_line_ids.line_type")
    def _compute_cabinet_total(self):
        for line in self:
            if line.line_type == "cabinet":
                line.cabinet_total = sum(
                    line.cabinet_line_ids.filtered(lambda item: item.line_type == "item").mapped(
                        "recommended_net_price"
                    )
                )
            else:
                line.cabinet_total = 0.0

    @api.depends("parent_section_id", "parent_cabinet_id", "line_type")
    def _compute_hierarchy_marker(self):
        for line in self:
            if line.line_type == "item" and line.parent_section_id:
                line.hierarchy_marker = "↳ ↳"
            elif line.line_type in ("item", "section") and line.parent_cabinet_id:
                line.hierarchy_marker = "↳"
            else:
                line.hierarchy_marker = ""

    def _normalize_section_membership(self):
        for order in self.mapped("order_id"):
            current_cabinet = False
            current_section = False
            lines = order.sab_calculation_line_ids.sorted(key=lambda item: (item.sequence, item.id))
            for line in lines:
                desired_section = False
                desired_cabinet = False

                if line.line_type == "cabinet":
                    current_cabinet = line
                    current_section = False
                elif line.line_type == "cabinet_end":
                    current_section = False
                    current_cabinet = False
                elif line.line_type == "section":
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                    current_section = line
                elif line.line_type == "section_end":
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                    current_section = False
                elif line.line_type == "item":
                    desired_cabinet = current_cabinet.id if current_cabinet else False
                    desired_section = current_section.id if current_section else False
                elif line.line_type == "info":
                    desired_cabinet = current_cabinet.id if current_cabinet else False

                changes = {}
                if (line.parent_section_id.id or False) != desired_section:
                    changes["parent_section_id"] = desired_section
                if (line.parent_cabinet_id.id or False) != desired_cabinet:
                    changes["parent_cabinet_id"] = desired_cabinet
                if changes:
                    line.with_context(
                        skip_section_normalize=True,
                        skip_sale_line_sync=True,
                    ).write(changes)
        return True

    @staticmethod
    def _component_commands(item):
        """Only real BOM material is snapshotted; auxiliary material is calculation-only."""
        return [
            (
                0,
                0,
                {
                    "sequence": line.sequence,
                    "product_id": line.product_id.id,
                    "odoo_product_id": line.odoo_product_id.id
                    or (line.product_id.odoo_product_id.id if line.product_id else False),
                    "quantity_per_unit": line.quantity or 0.0,
                    "unit": line.unit,
                    "fixed_quantity": line.fixed_quantity,
                    "optional": line.optional,
                    "source_calculation_line_id": line.id,
                    "supplier_product_id": line.selected_supplier_product_id.id or False,
                    "unit_purchase_price": line.unit_purchase_price or 0.0,
                    "note": line.note,
                },
            )
            for line in item.product_line_ids
            if line.product_id
            and line.position_type
            not in ("auxiliary_material", "information", "heading", "subtotal", "alternative")
        ]

    def _prepare_source_values(self, vals):
        values = super()._prepare_source_values(vals)
        if values.get("line_type") in ("cabinet", "cabinet_end"):
            values.update(
                {
                    "calculation_item_id": False,
                    "odoo_product_id": False,
                    "parent_section_id": False,
                    "parent_cabinet_id": False,
                    "quantity": 1.0,
                    "component_snapshot_ids": [(5, 0, 0)],
                }
            )
        return values

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
            current_section = False
            for line in order.sab_calculation_line_ids.sorted(key=lambda item: (item.sequence, item.id)):
                if line.line_type == "cabinet":
                    if current_cabinet:
                        raise ValidationError(
                            f"Schaltschrank {current_cabinet.description} wurde nicht beendet, bevor ein neuer Schaltschrank begonnen wurde."
                        )
                    current_cabinet = line
                    current_section = False
                elif line.line_type == "cabinet_end":
                    if not current_cabinet:
                        raise ValidationError("'Schaltschrank beenden' wurde ohne offenen Schaltschrank verwendet.")
                    current_cabinet = False
                    current_section = False
                elif line.line_type == "section":
                    if not current_cabinet:
                        raise ValidationError(
                            f"Das Bauteil '{line.description or 'ohne Bezeichnung'}' liegt außerhalb eines Schaltschrankes."
                        )
                    current_section = line
                elif line.line_type == "section_end":
                    current_section = False
                elif line.line_type == "item" and not current_cabinet:
                    raise ValidationError(
                        "Bei einem Schaltplan-Angebot muss jede Kalkulationsposition einem Schaltschrank zugeordnet sein."
                    )
            if current_cabinet:
                raise ValidationError(
                    f"Schaltschrank {current_cabinet.description} ist noch offen. Bitte 'Schaltschrank beenden' setzen."
                )
        return True
