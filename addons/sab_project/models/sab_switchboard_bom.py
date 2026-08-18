from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabProjectBomSwitchboard(models.Model):
    _inherit = "sab.project.bom"

    bom_scope = fields.Selection(
        [("total", "Gesamtstückliste"), ("cabinet", "Verteiler / Schaltschrank")],
        string="Stücklistenart",
        required=True,
        default="total",
        index=True,
    )
    cabinet_line_id = fields.Many2one(
        "sab.offer.calculation.line",
        string="Schaltschrank",
        ondelete="restrict",
        index=True,
        domain="[('order_id', '=', order_id), ('line_type', '=', 'cabinet')]",
    )
    scope_key = fields.Char(string="Interner Stücklistenschlüssel", required=True, default="total", copy=False, index=True)

    _order_unique = models.Constraint(
        "UNIQUE(order_id, scope_key)",
        "Für diesen Auftrag existiert diese SAB-P Stückliste bereits.",
    )

    @api.constrains("bom_scope", "cabinet_line_id")
    def _check_bom_scope(self):
        for bom in self:
            if bom.bom_scope == "cabinet" and not bom.cabinet_line_id:
                raise ValidationError("Eine Verteilerstückliste benötigt einen zugeordneten Schaltschrank.")
            if bom.bom_scope == "total" and bom.cabinet_line_id:
                raise ValidationError("Die Gesamtstückliste darf keinem einzelnen Schaltschrank zugeordnet sein.")

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            scope = vals.get("bom_scope", "total")
            cabinet_id = vals.get("cabinet_line_id")
            vals["scope_key"] = f"cabinet:{cabinet_id}" if scope == "cabinet" and cabinet_id else "total"
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        values = dict(vals)
        if "bom_scope" in values or "cabinet_line_id" in values:
            for bom in self:
                scope = values.get("bom_scope", bom.bom_scope)
                cabinet = values.get("cabinet_line_id", bom.cabinet_line_id.id)
                values["scope_key"] = f"cabinet:{cabinet}" if scope == "cabinet" and cabinet else "total"
        return super().write(values)


class SabProjectBomLineOdooLink(models.Model):
    _inherit = "sab.project.bom.line"

    odoo_product_id = fields.Many2one(
        "product.product",
        string="Odoo-Produkt",
        ondelete="restrict",
        index=True,
    )


class SabOfferCalculationComponentOdooLink(models.Model):
    _inherit = "sab.offer.calculation.component"

    odoo_product_id = fields.Many2one(
        "product.product",
        string="Odoo-Produkt beim Snapshot",
        readonly=True,
        ondelete="restrict",
        index=True,
    )

    def init(self):
        self.env.cr.execute(
            """
            UPDATE sab_offer_calculation_component c
               SET odoo_product_id = p.odoo_product_id
              FROM sab_product p
             WHERE c.product_id = p.id
               AND c.odoo_product_id IS NULL
               AND p.odoo_product_id IS NOT NULL
            """
        )


class SabPurchaseRequirementOdooLink(models.Model):
    _inherit = "sab.purchase.requirement"

    odoo_product_id = fields.Many2one(
        related="bom_line_id.odoo_product_id",
        string="Odoo-Produkt",
        store=True,
        readonly=True,
    )


class SaleOrderSwitchboardBom(models.Model):
    _inherit = "sale.order"

    def _sab_bom_values_for_lines(self, calculation_lines):
        aggregated = defaultdict(lambda: {
            "product_id": False,
            "odoo_product_id": False,
            "quantity": 0.0,
            "unit": "pcs",
            "optional": False,
            "supplier_product_id": False,
            "unit_purchase_price": 0.0,
            "note": False,
        })
        for calc_line in calculation_lines.filtered(lambda line: line.line_type == "item"):
            for component in calc_line.component_snapshot_ids:
                source = component.source_calculation_line_id
                if source and source.position_type == "auxiliary_material":
                    continue
                qty = component.quantity_per_unit or 0.0
                if not component.fixed_quantity:
                    qty *= calc_line.quantity or 0.0
                odoo_product = component.odoo_product_id or component.product_id.odoo_product_id
                key = (
                    component.product_id.id or 0,
                    odoo_product.id or 0,
                    component.unit,
                    component.optional,
                    component.supplier_product_id.id or 0,
                    component.unit_purchase_price or 0.0,
                )
                row = aggregated[key]
                row.update({
                    "product_id": component.product_id.id or False,
                    "odoo_product_id": odoo_product.id or False,
                    "unit": component.unit,
                    "optional": component.optional,
                    "supplier_product_id": component.supplier_product_id.id or False,
                    "unit_purchase_price": component.unit_purchase_price or 0.0,
                    "note": component.note,
                })
                row["quantity"] += qty
        commands = []
        for sequence, values in enumerate(aggregated.values(), start=1):
            values = dict(values)
            values["sequence"] = sequence * 10
            commands.append((0, 0, values))
        return commands

    def _sab_prepare_or_update_bom(self, scope, cabinet=False, line_commands=None):
        self.ensure_one()
        Bom = self.env["sab.project.bom"]
        domain = [("order_id", "=", self.id), ("bom_scope", "=", scope)]
        if scope == "cabinet":
            domain.append(("cabinet_line_id", "=", cabinet.id))
        bom = Bom.search(domain, limit=1)
        name = (
            f"STL {self.sab_offer_reference or self.name} / {cabinet.description}"
            if scope == "cabinet"
            else f"STL {self.sab_offer_reference or self.name} / GESAMT"
        )
        if bom and bom.state == "released":
            return bom
        values = {
            "name": name,
            "project_id": self.sab_project_id.id,
            "order_id": self.id,
            "bom_scope": scope,
            "cabinet_line_id": cabinet.id if cabinet else False,
            "generated_at": fields.Datetime.now(),
            "generated_by_id": self.env.user.id,
            "line_ids": [(5, 0, 0)] + (line_commands or []),
        }
        if bom:
            bom.write(values)
        else:
            bom = Bom.create(values)
        return bom

    def action_generate_sab_bom(self):
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise ValidationError(_("Die SAB-P Stückliste kann erst aus einem bestätigten Auftrag erzeugt werden."))
        if not self.sab_project_id:
            raise ValidationError(_("Dem Auftrag ist kein SAB-P Projekt zugeordnet."))
        if self.sab_calculation_source != "schematic":
            raise ValidationError(
                _("Aus einem reinen LV-Angebot darf keine Stückliste erzeugt werden. "
                  "Stücklisten werden ausschließlich aus einem bestätigten Schaltplan-Angebot mit abgegrenzten Schaltschränken erzeugt.")
            )
        if not self.sab_calculation_line_ids:
            raise ValidationError(_("Der Auftrag enthält keine SAB-P Kalkulationspositionen."))

        self._sab_validate_schematic_lv_basis()
        self.sab_calculation_line_ids._normalize_section_membership()
        self._sab_validate_switchboard_structure()

        cabinets = self.sab_calculation_line_ids.filtered(lambda line: line.line_type == "cabinet")
        if not cabinets:
            raise ValidationError(
                _("Für die Stücklistenerzeugung muss mindestens ein Schaltschrank, z. B. UV1 oder QV1, angelegt und beendet sein.")
            )

        generated = self.env["sab.project.bom"]
        all_item_lines = self.env["sab.offer.calculation.line"]
        for cabinet in cabinets.sorted(key=lambda line: (line.sequence, line.id)):
            cabinet_items = self.sab_calculation_line_ids.filtered(
                lambda line: line.line_type == "item" and line.parent_cabinet_id == cabinet
            )
            if not cabinet_items:
                raise ValidationError(_(f"Schaltschrank {cabinet.description} enthält keine Stücklistenpositionen."))
            commands = self._sab_bom_values_for_lines(cabinet_items)
            if not commands:
                raise ValidationError(
                    _(
                        f"Für Schaltschrank {cabinet.description} konnten keine normalen Materialpositionen erzeugt werden. "
                        "Hilfsmaterial wird absichtlich nicht in die Stückliste übernommen."
                    )
                )
            generated |= self._sab_prepare_or_update_bom("cabinet", cabinet, commands)
            all_item_lines |= cabinet_items

        total_commands = self._sab_bom_values_for_lines(all_item_lines)
        generated |= self._sab_prepare_or_update_bom("total", False, total_commands)

        stale = self.sab_bom_ids.filtered(
            lambda bom: bom.state == "draft"
            and bom.bom_scope == "cabinet"
            and bom.cabinet_line_id not in cabinets
        )
        if stale:
            stale.unlink()

        return {
            "type": "ir.actions.act_window",
            "name": _("SAB-P Stücklisten"),
            "res_model": "sab.project.bom",
            "view_mode": "list,form",
            "domain": [("id", "in", generated.ids)],
            "target": "current",
        }
