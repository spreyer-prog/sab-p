from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabStockMovementOdooBridge(models.Model):
    _inherit = "sab.stock.movement"

    odoo_stock_move_id = fields.Many2one(
        "stock.move",
        string="Odoo-Lagerbewegung",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    odoo_bridge_event = fields.Selection(
        [
            ("receipt", "Odoo-Wareneingang gespiegelt"),
            ("return_release", "Reservierung für Rücksendung freigegeben"),
            ("return_issue", "Lieferantenrücksendung gespiegelt"),
            ("commission_release", "Reservierung zur Kommissionierung freigegeben"),
            ("commission_issue", "Kommissionierung gespiegelt"),
        ],
        string="Odoo-Brückenereignis",
        readonly=True,
        copy=False,
        index=True,
    )

    _odoo_bridge_event_unique = models.Constraint(
        "UNIQUE(odoo_stock_move_id, odoo_bridge_event, purchase_requirement_id)",
        "Diese Odoo-Lagerbewegung wurde für den Einkaufsbedarf bereits übernommen.",
    )

    def write(self, vals):
        if {"odoo_stock_move_id", "odoo_bridge_event"}.intersection(vals):
            raise ValidationError(
                "Die technische Verbindung zu einer Odoo-Lagerbewegung darf "
                "nach der Buchung nicht verändert werden."
            )
        return super().write(vals)


class StockMoveSabAssignmentBridge(models.Model):
    _inherit = "stock.move"

    # Diese Felder waren im ersten Brückenschritt reine Related-Felder. Als
    # normale, gespeicherte Felder können sie auch auf internen
    # Kommissionierbewegungen ohne purchase_line_id geführt werden.
    sab_purchase_requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="SAB-P Materialposition",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_project_id = fields.Many2one(
        "project.project",
        string="SAB-P Projekt",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_procurement_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Materialanforderung",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_source_cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler / Schaltschrank",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )

    def init(self):
        """Backfill SAB-P assignments on existing Odoo purchase stock moves."""
        self.env.cr.execute(
            """
            UPDATE stock_move move
               SET sab_purchase_requirement_id = line.sab_purchase_requirement_id,
                   sab_project_id = requirement.project_id,
                   sab_procurement_bom_id = requirement.bom_id,
                   sab_source_cabinet_bom_id = requirement.source_cabinet_bom_id
              FROM purchase_order_line line
              JOIN sab_purchase_requirement requirement
                ON requirement.id = line.sab_purchase_requirement_id
             WHERE move.purchase_line_id = line.id
               AND line.sab_purchase_requirement_id IS NOT NULL
               AND (
                    move.sab_purchase_requirement_id IS NULL
                    OR move.sab_project_id IS NULL
                    OR move.sab_procurement_bom_id IS NULL
               )
            """
        )


class PurchaseOrderLineSabStockAssignment(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_stock_move_vals(
        self,
        picking,
        price_unit,
        product_uom_qty,
        product_uom,
    ):
        values = super()._prepare_stock_move_vals(
            picking,
            price_unit,
            product_uom_qty,
            product_uom,
        )
        requirement = self.sab_purchase_requirement_id
        if requirement:
            values.update(
                {
                    "sab_purchase_requirement_id": requirement.id,
                    "sab_project_id": requirement.project_id.id or False,
                    "sab_procurement_bom_id": requirement.bom_id.id or False,
                    "sab_source_cabinet_bom_id": (
                        requirement.source_cabinet_bom_id.id or False
                    ),
                }
            )
        return values


class StockPickingSabCommissioningBridge(models.Model):
    _inherit = "stock.picking"

    sab_is_suite_commissioning = fields.Boolean(
        string="SAB-P Kommissionierung",
        default=False,
        copy=False,
        index=True,
    )
    sab_procurement_bom_id = fields.Many2one(
        "sab.project.bom",
        string="SAB-P Materialanforderung",
        copy=False,
        ondelete="set null",
        index=True,
    )
    sab_picking_user_id = fields.Many2one(
        "res.users",
        string="Kommissioniert durch",
        copy=False,
        ondelete="set null",
        index=True,
    )

    def _sab_move_quantity_in_requirement_uom(self, move, requirement):
        purchase_line = requirement.odoo_purchase_line_id
        target_uom = (
            purchase_line.product_uom_id
            if purchase_line
            else move.product_id.uom_id
        )
        return move.product_uom._compute_quantity(
            move.quantity,
            target_uom,
            rounding_method="HALF-UP",
        )

    def _sab_create_bridge_movement(
        self,
        *,
        move,
        requirement=False,
        event,
        movement_type,
        quantity,
        unit_cost=None,
        note,
    ):
        Movement = self.env["sab.stock.movement"].sudo()
        domain = [
            ("odoo_stock_move_id", "=", move.id),
            ("odoo_bridge_event", "=", event),
        ]
        if requirement:
            domain.append(("purchase_requirement_id", "=", requirement.id))
        if Movement.search_count(domain):
            return Movement.search(domain, limit=1)

        values = {
            "product_id": (
                requirement.product_id.id
                if requirement and requirement.product_id
                else False
            ),
            "odoo_product_id": move.product_id.id,
            "movement_type": movement_type,
            "quantity": quantity,
            "unit": requirement.unit if requirement else "pcs",
            "project_id": (
                requirement.project_id.id
                if requirement and requirement.project_id
                else move.sab_project_id.id or False
            ),
            "purchase_requirement_id": requirement.id if requirement else False,
            "odoo_stock_move_id": move.id,
            "odoo_bridge_event": event,
            "note": note,
        }
        if unit_cost is not None:
            values["unit_cost"] = unit_cost
        return Movement.create(values)

    def _sab_bridge_done_purchase_move(self, move):
        requirement = move.sab_purchase_requirement_id
        if not requirement or move.quantity <= 0:
            return
        quantity = self._sab_move_quantity_in_requirement_uom(
            move,
            requirement,
        )
        if quantity <= 0:
            return

        is_supplier_return = (
            move.location_dest_id.usage == "supplier"
            or move._is_purchase_return()
        )
        if is_supplier_return:
            requirement.invalidate_recordset(
                ["project_reserved_quantity", "commissioned_quantity"]
            )
            release_quantity = min(
                quantity,
                max(requirement.project_reserved_quantity or 0.0, 0.0),
            )
            if release_quantity > 0:
                self._sab_create_bridge_movement(
                    move=move,
                    requirement=requirement,
                    event="return_release",
                    movement_type="release",
                    quantity=release_quantity,
                    note=(
                        "Projektreservierung wegen Lieferantenrücksendung "
                        f"freigegeben: {move.reference or move.picking_id.name}"
                    ),
                )
            # Die Rücksendung reduziert den Gesamtbestand, darf aber nicht als
            # Fertigungs-Kommissionierung dieser Materialposition zählen.
            self._sab_create_bridge_movement(
                move=move,
                requirement=False,
                event="return_issue",
                movement_type="issue",
                quantity=quantity,
                note=(
                    "Lieferantenrücksendung aus Odoo: "
                    f"{move.reference or move.picking_id.name}"
                ),
            )
            requirement.invalidate_recordset()
            return

        if move.location_dest_id.usage in ("internal", "transit"):
            purchase_line = requirement.odoo_purchase_line_id
            net_unit_cost = (
                (purchase_line.price_unit or 0.0)
                * (1.0 - (purchase_line.discount or 0.0) / 100.0)
                if purchase_line
                else 0.0
            )
            self._sab_create_bridge_movement(
                move=move,
                requirement=requirement,
                event="receipt",
                movement_type="receipt",
                quantity=quantity,
                unit_cost=net_unit_cost,
                note=(
                    "Odoo-Wareneingang: "
                    f"{move.reference or move.picking_id.name}"
                ),
            )
            requirement.invalidate_recordset()
            requirement._reserve_available_stock()

    def _sab_bridge_done_commission_move(self, move):
        requirement = move.sab_purchase_requirement_id
        if not requirement or move.quantity <= 0:
            return
        quantity = self._sab_move_quantity_in_requirement_uom(
            move,
            requirement,
        )
        if quantity <= 0:
            return

        requirement.invalidate_recordset(
            ["project_reserved_quantity", "commissioned_quantity"]
        )
        release_quantity = min(
            quantity,
            max(requirement.project_reserved_quantity or 0.0, 0.0),
        )
        if release_quantity + 1e-9 < quantity:
            raise ValidationError(
                "Die Odoo-Kommissionierung überschreitet die für das Projekt "
                "reservierte Materialmenge."
            )

        self._sab_create_bridge_movement(
            move=move,
            requirement=requirement,
            event="commission_release",
            movement_type="release",
            quantity=quantity,
            note=(
                "Reservierung zur Odoo-Kommissionierung freigegeben: "
                f"{move.reference or move.picking_id.name}"
            ),
        )
        self._sab_create_bridge_movement(
            move=move,
            requirement=requirement,
            event="commission_issue",
            movement_type="issue",
            quantity=quantity,
            note=(
                "Odoo-Kommissionierung für "
                f"{requirement.source_cabinet_bom_id.name or requirement.project_id.display_name}"
            ),
        )

    def _action_done(self):
        result = super()._action_done()
        for picking in self:
            done_moves = picking.move_ids.filtered(
                lambda move: move.state == "done"
                and move.sab_purchase_requirement_id
            )
            if picking.sab_is_suite_commissioning:
                for move in done_moves:
                    picking._sab_bridge_done_commission_move(move)
            elif picking.sab_is_suite_receipt:
                for move in done_moves:
                    picking._sab_bridge_done_purchase_move(move)

        requirements = self.move_ids.mapped("sab_purchase_requirement_id")
        if requirements:
            requirements.invalidate_recordset()
            for requirement in requirements:
                purchase_line = requirement.odoo_purchase_line_id
                if purchase_line and purchase_line.order_id.state != "cancel":
                    requirement.state = (
                        "received"
                        if purchase_line.qty_received
                        >= (purchase_line.product_qty or 0.0) - 1e-9
                        else "ordered"
                    )
        return result


class SabPurchaseRequirementOdooStockFinal(models.Model):
    _inherit = "sab.purchase.requirement"

    @api.depends(
        "quantity",
        "state",
        "stock_movement_ids.movement_type",
        "stock_movement_ids.quantity",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_line_id.quantity_remaining",
        "purchase_order_line_id.order_id.state",
        "purchase_order_id.state",
        "odoo_purchase_line_id.order_id.state",
        "odoo_purchase_line_id.product_qty",
        "odoo_purchase_line_id.qty_received",
        "odoo_purchase_line_id.qty_invoiced",
    )
    def _compute_procurement_quantities(self):
        # Der endgültige Stand basiert auch im Übergang ausschließlich auf
        # tatsächlich gespiegelten Lagerbuchungen. Ein Wareneingang darf nicht
        # nur rechnerisch als Reservierung erscheinen, weil die anschließende
        # Kommissionierung sonst keine passende Freigabebuchung hätte.
        super()._compute_procurement_quantities()
        for requirement in self:
            on_hand, reserved_total, available = (
                requirement._product_stock_totals()
            )
            movements = requirement.stock_movement_ids
            own_reserved = max(
                sum(
                    movements.filtered(
                        lambda movement: movement.movement_type == "reserve"
                    ).mapped("quantity")
                )
                - sum(
                    movements.filtered(
                        lambda movement: movement.movement_type == "release"
                    ).mapped("quantity")
                ),
                0.0,
            )
            commissioned = max(
                sum(
                    movements.filtered(
                        lambda movement: movement.movement_type == "issue"
                    ).mapped("quantity")
                ),
                0.0,
            )
            required = max(requirement.quantity or 0.0, 0.0)
            shortage = max(required - own_reserved - commissioned, 0.0)

            requirement.warehouse_on_hand = on_hand
            requirement.warehouse_reserved = reserved_total
            requirement.warehouse_available = available
            requirement.project_reserved_quantity = own_reserved
            requirement.commissioned_quantity = commissioned
            requirement.shortage_quantity = shortage
            requirement.suggested_order_quantity = shortage

            standard_line = requirement.odoo_purchase_line_id
            standard_state = (
                standard_line.order_id.state if standard_line else False
            )
            if requirement.state == "cancel" or standard_state == "cancel":
                status = "cancel"
            elif commissioned >= required - 1e-9 and required > 0:
                status = "commissioned"
            elif standard_line and standard_line.qty_received >= (
                standard_line.product_qty or 0.0
            ) - 1e-9:
                status = "received"
            elif standard_line and standard_line.qty_received > 1e-9:
                status = "partial_received"
            elif standard_line and standard_state in ("draft", "sent"):
                status = "proposal"
            elif standard_line and standard_state == "to approve":
                status = "approval"
            elif standard_line and standard_state == "purchase":
                status = "ordered"
            elif shortage <= 1e-9:
                status = "in_stock"
            elif commissioned > 1e-9:
                status = "partial_commissioned"
            elif own_reserved > 1e-9:
                status = "partial"
            else:
                status = "missing"
            requirement.stock_status = status


class SabProjectBomOdooCommissioning(models.Model):
    _inherit = "sab.project.bom"

    odoo_commissioning_picking_ids = fields.One2many(
        "stock.picking",
        "sab_procurement_bom_id",
        string="Odoo-Kommissionierungen",
        readonly=True,
    )
    odoo_commissioning_picking_count = fields.Integer(
        string="Odoo-Kommissionierungen",
        compute="_compute_odoo_commissioning_picking_count",
    )

    @api.depends("odoo_commissioning_picking_ids.state")
    def _compute_odoo_commissioning_picking_count(self):
        for package in self:
            package.odoo_commissioning_picking_count = len(
                package.odoo_commissioning_picking_ids.filtered(
                    lambda picking: picking.state != "cancel"
                )
            )

    def _sab_check_standard_commissioning_user(self):
        self.ensure_one()
        allowed = (
            self.env.is_superuser()
            or self.env.user == self.picking_user_id
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
            or self.env.user.has_group("project.group_project_manager")
        )
        if not allowed:
            raise AccessError(
                "Die Kommissionierung darf nur durch den zugewiesenen Mitarbeiter, "
                "Lager, Einkauf oder Projektleitung gebucht werden."
            )
        return True

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

        destination = self.env.ref("stock.stock_location_production")
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
                    # Die vorherige SAB-P-Reservierung ist fachlich bereits
                    # erfolgt. Für nicht als storable markierte Altprodukte kann
                    # Odoo keine Quant-Reservierung anzeigen; die bestätigte
                    # Kommissioniermenge wird deshalb explizit gesetzt.
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

    def action_view_odoo_commissioning_pickings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Odoo-Kommissionierungen – %s")
            % (self.procurement_reference or self.name),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [
                ("sab_procurement_bom_id", "=", self.id),
                ("sab_is_suite_commissioning", "=", True),
            ],
            "context": {"create": False},
            "target": "current",
        }
