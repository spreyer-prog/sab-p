from odoo import Command, api, fields, models, _


class SabReceiptAssignmentList(models.Model):
    _name = "sab.receipt.assignment.list"
    _description = "Kommissionierungs- und Projektzuordnungsliste"
    _order = "generated_at desc, id desc"

    name = fields.Char(string="Bezeichnung", required=True, readonly=True)
    picking_id = fields.Many2one(
        "stock.picking",
        string="Wareneingang",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        related="picking_id.partner_id",
        string="Lieferant",
        store=True,
        readonly=True,
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="Bestellungen",
        readonly=True,
    )
    generated_at = fields.Datetime(
        string="Erzeugt am",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    line_ids = fields.One2many(
        "sab.receipt.assignment.list.line",
        "assignment_list_id",
        string="Gelieferte Produkte",
        readonly=True,
    )
    printer_name = fields.Char(
        string="Zieldrucker",
        compute="_compute_printer_name",
    )

    _picking_unique = models.Constraint(
        "UNIQUE(picking_id)",
        "Für diesen Wareneingang existiert bereits eine Projektzuordnungsliste.",
    )

    def _compute_printer_name(self):
        parameters = self.env["ir.config_parameter"].sudo()
        configured = parameters.get_param("sab_project.receipt_assignment_printer")
        fallback = parameters.get_param(
            "sab_project.default_pdf_printer",
            "PDF-Drucker",
        )
        for assignment in self:
            assignment.printer_name = configured or fallback

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            "sab_project.action_report_sab_receipt_assignment_list"
        ).with_context(sab_printer_name=self.printer_name).report_action(self)


class SabReceiptAssignmentListLine(models.Model):
    _name = "sab.receipt.assignment.list.line"
    _description = "Position Projektzuordnungsliste"
    _order = "project_id, source_cabinet_bom_id, product_id, id"

    assignment_list_id = fields.Many2one(
        "sab.receipt.assignment.list",
        required=True,
        ondelete="cascade",
        index=True,
    )
    stock_move_id = fields.Many2one(
        "stock.move",
        string="Lagerbewegung",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    purchase_requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="Materialposition",
        readonly=True,
        ondelete="set null",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Bestellung",
        readonly=True,
        ondelete="set null",
    )
    project_id = fields.Many2one(
        "project.project",
        string="Projekt",
        readonly=True,
        ondelete="set null",
    )
    procurement_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Materialanforderung",
        readonly=True,
        ondelete="set null",
    )
    source_cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler / Schaltschrank",
        readonly=True,
        ondelete="set null",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    supplier_article_number = fields.Char(
        string="Lieferanten-Art.-Nr.",
        readonly=True,
    )
    quantity_received = fields.Float(
        string="Geliefert",
        digits="Product Unit of Measure",
        readonly=True,
    )
    quantity_project = fields.Float(
        string="Projektmenge",
        digits="Product Unit of Measure",
        readonly=True,
    )
    quantity_free_stock = fields.Float(
        string="Freier Lagerbestand",
        digits="Product Unit of Measure",
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Einheit",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Lagerziel",
        readonly=True,
        ondelete="set null",
    )


class StockPickingSabReceiptAssignment(models.Model):
    _inherit = "stock.picking"

    sab_receipt_assignment_list_ids = fields.One2many(
        "sab.receipt.assignment.list",
        "picking_id",
        string="Projektzuordnungslisten",
        readonly=True,
        copy=False,
    )
    sab_receipt_assignment_list_count = fields.Integer(
        string="Anzahl Projektzuordnungslisten",
        compute="_compute_sab_receipt_assignment_list_count",
    )

    @api.depends("sab_receipt_assignment_list_ids")
    def _compute_sab_receipt_assignment_list_count(self):
        for picking in self:
            picking.sab_receipt_assignment_list_count = len(
                picking.sab_receipt_assignment_list_ids
            )

    def _sab_receipt_assignment_quantity(self, move):
        requirement = move.sab_purchase_requirement_id
        if requirement:
            return self._sab_move_quantity_in_requirement_uom(move, requirement)
        return move.quantity

    def _sab_create_receipt_assignment_list(self):
        Assignment = self.env["sab.receipt.assignment.list"].sudo()
        AssignmentLine = self.env["sab.receipt.assignment.list.line"].sudo()
        for picking in self.filtered(
            lambda record: record.sab_is_suite_receipt and record.state == "done"
        ):
            existing = Assignment.search([("picking_id", "=", picking.id)], limit=1)
            if existing:
                continue

            done_moves = picking.move_ids.filtered(
                lambda move: move.state == "done"
                and move.quantity > 0
                and move.location_dest_id.usage in ("internal", "transit")
            )
            if not done_moves:
                continue

            line_commands = []
            purchase_orders = self.env["purchase.order"]
            for move in done_moves:
                requirement = move.sab_purchase_requirement_id
                purchase_line = move.purchase_line_id
                purchase_order = purchase_line.order_id if purchase_line else False
                if purchase_order:
                    purchase_orders |= purchase_order
                received_quantity = picking._sab_receipt_assignment_quantity(move)

                project_quantity = 0.0
                if requirement:
                    previously_assigned = sum(
                        AssignmentLine.search(
                            [
                                ("purchase_requirement_id", "=", requirement.id),
                                ("assignment_list_id.picking_id", "!=", picking.id),
                            ]
                        ).mapped("quantity_project")
                    )
                    remaining_project_quantity = max(
                        (requirement.quantity or 0.0) - previously_assigned,
                        0.0,
                    )
                    project_quantity = min(
                        received_quantity,
                        remaining_project_quantity,
                    )

                free_quantity = max(received_quantity - project_quantity, 0.0)
                line_commands.append(
                    Command.create(
                        {
                            "stock_move_id": move.id,
                            "purchase_requirement_id": requirement.id if requirement else False,
                            "purchase_order_id": purchase_order.id if purchase_order else False,
                            "project_id": (
                                requirement.project_id.id
                                if requirement
                                else move.sab_project_id.id or False
                            ),
                            "procurement_bom_id": (
                                requirement.bom_id.id
                                if requirement
                                else move.sab_procurement_bom_id.id or False
                            ),
                            "source_cabinet_bom_id": (
                                requirement.source_cabinet_bom_id.id
                                if requirement
                                else move.sab_source_cabinet_bom_id.id or False
                            ),
                            "product_id": move.product_id.id,
                            "supplier_article_number": (
                                purchase_line.sab_supplier_article_number
                                if purchase_line
                                else False
                            ),
                            "quantity_received": received_quantity,
                            "quantity_project": project_quantity,
                            "quantity_free_stock": free_quantity,
                            "uom_id": (
                                purchase_line.product_uom_id.id
                                if purchase_line
                                else move.product_uom.id
                            ),
                            "destination_location_id": move.location_dest_id.id,
                        }
                    )
                )

            assignment = Assignment.create(
                {
                    "name": _("Projektzuordnung %s") % picking.name,
                    "picking_id": picking.id,
                    "purchase_order_ids": [Command.set(purchase_orders.ids)],
                    "line_ids": line_commands,
                }
            )
            picking.message_post(
                body=_(
                    "Die Kommissionierungs- und Projektzuordnungsliste %s wurde aus den tatsächlich gebuchten Wareneingangsmengen erzeugt."
                )
                % assignment.name,
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _action_done(self):
        result = super()._action_done()
        self._sab_create_receipt_assignment_list()
        return result

    def button_validate(self):
        result = super().button_validate()
        if not isinstance(result, dict):
            assignments = self.filtered(
                lambda picking: picking.state == "done"
                and picking.sab_receipt_assignment_list_ids
            ).mapped("sab_receipt_assignment_list_ids")
            if len(assignments) == 1:
                return assignments.action_print()
        return result

    def action_open_receipt_assignment_lists(self):
        self.ensure_one()
        if len(self.sab_receipt_assignment_list_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Projektzuordnungsliste"),
                "res_model": "sab.receipt.assignment.list",
                "res_id": self.sab_receipt_assignment_list_ids.id,
                "view_mode": "form",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Projektzuordnungslisten"),
            "res_model": "sab.receipt.assignment.list",
            "view_mode": "list,form",
            "domain": [("picking_id", "=", self.id)],
        }
