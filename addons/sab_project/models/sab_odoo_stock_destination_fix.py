from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SabProjectBomOdoo19ProductionLocation(models.Model):
    _inherit = "sab.project.bom"

    def action_complete_picking(self):
        self.ensure_one()
        if self.bom_scope != "procurement":
            return super().action_complete_picking()
        self._sab_check_standard_commissioning_user()
        if not self.picking_user_id:
            raise ValidationError(
                "Die Kommissionierung muss vor der Buchung einem Mitarbeiter "
                "zugewiesen werden."
            )

        requirements = self.purchase_requirement_ids.filtered(
            lambda requirement: requirement.state != "cancel"
            and not requirement.optional
        )
        requirements.invalidate_recordset()
        quantities = {}
        for requirement in requirements:
            open_quantity = max(
                (requirement.quantity or 0.0)
                - (requirement.commissioned_quantity or 0.0),
                0.0,
            )
            quantity = min(
                max(requirement.project_reserved_quantity or 0.0, 0.0),
                open_quantity,
            )
            if quantity > 1e-9:
                if not requirement.odoo_product_id:
                    raise ValidationError(
                        f"Für {requirement.name} fehlt das Odoo-Produkt."
                    )
                quantities[requirement] = quantity

        if not quantities:
            raise ValidationError(
                "Für dieses Beschaffungspaket ist aktuell keine reservierte "
                "Lagerware zu kommissionieren."
            )

        grouped = defaultdict(dict)
        Warehouse = self.env["stock.warehouse"].sudo()
        for requirement, quantity in quantities.items():
            warehouse = requirement.odoo_purchase_order_id.picking_type_id.warehouse_id
            if not warehouse:
                warehouse = Warehouse.search(
                    [("company_id", "=", self.env.company.id)],
                    limit=1,
                )
            if not warehouse:
                raise ValidationError(
                    "Für die Firma ist kein Odoo-Lager eingerichtet."
                )
            grouped[warehouse][requirement] = quantity

        destination = self.env["stock.location"].sudo().search(
            [
                ("usage", "=", "production"),
                ("company_id", "in", [False, self.env.company.id]),
            ],
            order="company_id desc, id",
            limit=1,
        )
        if not destination:
            self.env.company.sudo()._create_production_location()
            destination = self.env["stock.location"].sudo().search(
                [
                    ("usage", "=", "production"),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
        if not destination:
            raise ValidationError(
                "Für die Firma ist kein Odoo-Produktionslagerort eingerichtet."
            )

        created_pickings = self.env["stock.picking"]
        for warehouse, warehouse_quantities in grouped.items():
            picking_type = self.env["stock.picking.type"].search(
                [
                    ("code", "=", "internal"),
                    ("warehouse_id", "=", warehouse.id),
                ],
                limit=1,
            )
            if not picking_type:
                raise ValidationError(
                    f"Für das Lager {warehouse.display_name} fehlt eine interne "
                    "Vorgangsart zur Kommissionierung."
                )

            picking = self.env["stock.picking"].create(
                {
                    "picking_type_id": picking_type.id,
                    "location_id": warehouse.lot_stock_id.id,
                    "location_dest_id": destination.id,
                    "origin": self.procurement_reference or self.name,
                    "sab_is_suite_commissioning": True,
                    "sab_procurement_bom_id": self.id,
                    "sab_picking_user_id": self.picking_user_id.id,
                }
            )
            created_pickings |= picking

            moves = self.env["stock.move"]
            for requirement, quantity in warehouse_quantities.items():
                product = requirement.odoo_product_id
                purchase_line = requirement.odoo_purchase_line_id
                source_uom = (
                    purchase_line.product_uom_id
                    if purchase_line
                    else product.uom_id
                )
                move_quantity = source_uom._compute_quantity(
                    quantity,
                    product.uom_id,
                    rounding_method="HALF-UP",
                )
                move = self.env["stock.move"].create(
                    {
                        "name": (
                            requirement.source_cabinet_bom_id.name
                            or requirement.name
                        ),
                        "product_id": product.id,
                        "product_uom_qty": move_quantity,
                        "product_uom": product.uom_id.id,
                        "location_id": warehouse.lot_stock_id.id,
                        "location_dest_id": destination.id,
                        "picking_id": picking.id,
                        "company_id": self.env.company.id,
                        "sab_purchase_requirement_id": requirement.id,
                        "sab_project_id": requirement.project_id.id or False,
                        "sab_procurement_bom_id": self.id,
                        "sab_source_cabinet_bom_id": (
                            requirement.source_cabinet_bom_id.id or False
                        ),
                    }
                )
                moves |= move

            moves._action_confirm()._action_assign()
            for move in moves:
                if move.product_uom.compare(
                    move.quantity,
                    move.product_uom_qty,
                ) < 0:
                    move.quantity = move.product_uom_qty
                move.picked = True
            result = picking.with_context(skip_backorder=True).button_validate()
            if result is not True and isinstance(result, dict):
                raise ValidationError(
                    "Die Odoo-Kommissionierung konnte nicht ohne zusätzlichen "
                    "Dialog abgeschlossen werden. Bitte den Vorgang im geöffneten "
                    "Warenausgang prüfen."
                )

        requirements.invalidate_recordset()
        all_done = all(
            (requirement.commissioned_quantity or 0.0)
            >= (requirement.quantity or 0.0) - 1e-9
            for requirement in requirements
        )
        self.write(
            {
                "picking_state": "done" if all_done else "partial",
                "picking_completed_at": fields.Datetime.now(),
                "picking_completed_by_id": self.env.user.id,
            }
        )
        model_id = self.env["ir.model"]._get_id(self._name)
        activities = self.env["mail.activity"].search(
            [
                ("res_model_id", "=", model_id),
                ("res_id", "=", self.id),
                ("summary", "=", "Material kommissionieren"),
            ]
        )
        if activities:
            activities.sudo().unlink()

        return {
            "type": "ir.actions.act_window",
            "name": _("Odoo-Kommissionierungen – %s")
            % (self.procurement_reference or self.name),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", created_pickings.ids)],
            "context": {"create": False},
            "target": "current",
        }
