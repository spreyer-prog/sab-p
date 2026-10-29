import math
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabProjectBomProcurement(models.Model):
    _inherit = "sab.project.bom"

    purchase_release_state = fields.Selection(
        [
            ("not_released", "Nicht freigegeben"),
            ("released", "Bestellfreigabe erteilt"),
        ],
        string="Bestellfreigabe",
        required=True,
        default="not_released",
        copy=False,
        index=True,
        tracking=True,
    )
    purchase_released_at = fields.Datetime(
        string="Bestellfreigabe am",
        readonly=True,
        copy=False,
    )
    purchase_released_by_id = fields.Many2one(
        "res.users",
        string="Bestellfreigabe durch",
        readonly=True,
        copy=False,
    )

    def _sab_check_project_manager(self):
        if self.env.is_superuser() or self.env.user.has_group("project.group_project_manager"):
            return True
        raise AccessError("Die Bestellfreigabe darf nur durch einen Projektleiter erteilt werden.")

    def action_release_for_purchase(self):
        """Release one total BOM for stock reservation and purchasing.

        Procurement deliberately starts from the total BOM only. Cabinet BOMs
        remain the technical breakdown and must never duplicate material demand.
        """
        self.ensure_one()
        self._sab_check_project_manager()
        if self.state != "released":
            raise ValidationError(
                "Die Stückliste muss zuerst technisch freigegeben werden."
            )
        if getattr(self, "bom_scope", "total") != "total":
            raise ValidationError(
                "Die Bestellfreigabe wird ausschließlich aus der Gesamtstückliste erteilt. "
                "Die Verteilerstücklisten dienen nur der technischen Zuordnung."
            )
        if not self.line_ids:
            raise ValidationError("Eine leere Stückliste kann nicht zur Bestellung freigegeben werden.")

        # Remove obsolete, still untouched cabinet requirements so the total BOM
        # is the single source of truth. Ordered or received history is preserved.
        obsolete = self.env["sab.purchase.requirement"].search([
            ("project_id", "=", self.project_id.id),
            ("bom_id", "!=", self.id),
            ("bom_id.bom_scope", "=", "cabinet"),
            ("state", "=", "open"),
            ("purchase_order_line_id", "=", False),
        ])
        if obsolete:
            obsolete._release_project_reservation()
            obsolete.unlink()

        self.action_generate_purchase_requirements()
        requirements = self.purchase_requirement_ids.filtered(lambda req: not req.optional)
        requirements._reserve_available_stock()
        self.write({
            "purchase_release_state": "released",
            "purchase_released_at": fields.Datetime.now(),
            "purchase_released_by_id": self.env.user.id,
        })

        purchasing_group = self.env.ref(
            "sab_project.group_sab_purchasing", raise_if_not_found=False
        )
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if purchasing_group and activity_type:
            model_id = self.env["ir.model"]._get_id(self._name)
            for user in purchasing_group.user_ids.filtered("active"):
                existing = self.env["mail.activity"].search_count([
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", self.id),
                    ("user_id", "=", user.id),
                    ("summary", "=", "Neue interne Bestellfreigabe"),
                ])
                if not existing:
                    self.env["mail.activity"].create({
                        "activity_type_id": activity_type.id,
                        "res_model_id": model_id,
                        "res_id": self.id,
                        "user_id": user.id,
                        "summary": "Neue interne Bestellfreigabe",
                        "note": (
                            f"Projekt {self.project_id.display_name}: Die Gesamtstückliste "
                            "wurde zur Lagerprüfung und Bestellung freigegeben."
                        ),
                    })

        return {
            "type": "ir.actions.act_window",
            "name": _("Einkaufsbedarf – %s") % self.project_id.display_name,
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [("bom_id", "=", self.id)],
            "context": {"search_default_group_project": 1},
            "target": "current",
        }


class SabPurchaseRequirementProcurement(models.Model):
    _inherit = "sab.purchase.requirement"

    stock_movement_ids = fields.One2many(
        "sab.stock.movement",
        "purchase_requirement_id",
        string="Lagerbuchungen",
        readonly=True,
    )
    purchase_order_line_id = fields.Many2one(
        "sab.purchase.order.line",
        string="Bestellposition",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    purchase_order_id = fields.Many2one(
        related="purchase_order_line_id.order_id",
        string="Bestellung",
        store=True,
        readonly=True,
    )
    purchase_order_state = fields.Selection(
        related="purchase_order_id.state",
        string="Bestellstatus",
        store=True,
        readonly=True,
    )
    warehouse_on_hand = fields.Float(
        string="Lagerbestand",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    warehouse_reserved = fields.Float(
        string="Gesamt reserviert",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    warehouse_available = fields.Float(
        string="Frei verfügbar",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    project_reserved_quantity = fields.Float(
        string="Für Projekt reserviert",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    shortage_quantity = fields.Float(
        string="Fehlbestand",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    suggested_order_quantity = fields.Float(
        string="Bestellvorschlag",
        digits=(16, 3),
        compute="_compute_procurement_quantities",
    )
    stock_status = fields.Selection(
        [
            ("in_stock", "Vollständig im Lager"),
            ("partial", "Teilbestand – Rest bestellen"),
            ("missing", "Nicht im Lager"),
            ("ordered", "Bestellt"),
            ("partial_received", "Teilgeliefert"),
            ("received", "Vollständig geliefert"),
            ("cancel", "Storniert"),
        ],
        string="Materialstatus",
        compute="_compute_procurement_quantities",
    )
    manufacturer_name = fields.Char(
        string="Hersteller",
        compute="_compute_manufacturer_name",
    )

    def _stock_identity(self):
        self.ensure_one()
        legacy = self.product_id
        odoo_product = self.odoo_product_id or (legacy.odoo_product_id if legacy else False)
        return legacy, odoo_product

    def _product_stock_totals(self):
        self.ensure_one()
        legacy, odoo_product = self._stock_identity()
        Movement = self.env["sab.stock.movement"]
        if odoo_product:
            movements = Movement.search([("odoo_product_id", "=", odoo_product.id)])
        elif legacy:
            movements = Movement.search([("product_id", "=", legacy.id)])
        else:
            return 0.0, 0.0, 0.0
        receipts = sum(movements.filtered(lambda m: m.movement_type == "receipt").mapped("quantity"))
        issues = sum(movements.filtered(lambda m: m.movement_type == "issue").mapped("quantity"))
        reserves = sum(movements.filtered(lambda m: m.movement_type == "reserve").mapped("quantity"))
        releases = sum(movements.filtered(lambda m: m.movement_type == "release").mapped("quantity"))
        on_hand = receipts - issues
        reserved = reserves - releases
        return on_hand, reserved, on_hand - reserved

    @api.depends(
        "quantity",
        "state",
        "supplier_product_id.packaging_quantity",
        "supplier_product_id.minimum_order_quantity",
        "stock_movement_ids.movement_type",
        "stock_movement_ids.quantity",
        "purchase_order_line_id.quantity_ordered",
        "purchase_order_line_id.quantity_received",
        "purchase_order_id.state",
    )
    def _compute_procurement_quantities(self):
        for requirement in self:
            on_hand, reserved_total, available = requirement._product_stock_totals()
            own_movements = requirement.stock_movement_ids
            own_reserved = (
                sum(own_movements.filtered(lambda m: m.movement_type == "reserve").mapped("quantity"))
                - sum(own_movements.filtered(lambda m: m.movement_type == "release").mapped("quantity"))
            )
            shortage = max((requirement.quantity or 0.0) - own_reserved, 0.0)
            supplier_product = requirement.supplier_product_id
            packaging = max(supplier_product.packaging_quantity or 1.0, 0.000001) if supplier_product else 1.0
            minimum = max(supplier_product.minimum_order_quantity or 0.0, 0.0) if supplier_product else 0.0
            order_base = max(shortage, minimum) if shortage else 0.0
            suggested = math.ceil(order_base / packaging - 1e-9) * packaging if order_base else 0.0

            requirement.warehouse_on_hand = on_hand
            requirement.warehouse_reserved = reserved_total
            requirement.warehouse_available = available
            requirement.project_reserved_quantity = own_reserved
            requirement.shortage_quantity = shortage
            requirement.suggested_order_quantity = suggested

            order_line = requirement.purchase_order_line_id
            if requirement.state == "cancel":
                status = "cancel"
            elif order_line and order_line.quantity_remaining <= 0:
                status = "received"
            elif order_line and order_line.quantity_received > 0:
                status = "partial_received"
            elif order_line and requirement.purchase_order_id.state in (
                "to_approve", "approved", "sent", "partial", "done"
            ):
                status = "ordered"
            elif shortage <= 0:
                status = "in_stock"
            elif own_reserved > 0:
                status = "partial"
            else:
                status = "missing"
            requirement.stock_status = status

    @api.depends(
        "product_id.manufacturer_supplier_id",
        "product_id.manufacturer_id",
        "odoo_product_id.sab_manufacturer_supplier_id",
        "odoo_product_id.sab_manufacturer_id",
    )
    def _compute_manufacturer_name(self):
        for requirement in self:
            legacy, product = requirement._stock_identity()
            supplier_manufacturer = (
                product.sab_manufacturer_supplier_id
                if product
                else legacy.manufacturer_supplier_id
                if legacy
                else False
            )
            datanorm_manufacturer = (
                product.sab_manufacturer_id
                if product
                else legacy.manufacturer_id
                if legacy
                else False
            )
            requirement.manufacturer_name = (
                supplier_manufacturer.name
                if supplier_manufacturer
                else datanorm_manufacturer.name
                if datanorm_manufacturer
                else ""
            )

    def _movement_product_values(self):
        self.ensure_one()
        legacy, product = self._stock_identity()
        if not (legacy or product):
            raise ValidationError(
                f"Für {self.name} ist kein lagerfähiges Produkt hinterlegt."
            )
        return {
            "product_id": legacy.id if legacy else False,
            "odoo_product_id": product.id if product else False,
        }

    def _reserve_available_stock(self):
        Movement = self.env["sab.stock.movement"]
        for requirement in self.filtered(lambda req: req.state == "open" and not req.optional):
            requirement.invalidate_recordset()
            needed = max(
                (requirement.quantity or 0.0)
                - (requirement.project_reserved_quantity or 0.0),
                0.0,
            )
            available = max(requirement.warehouse_available or 0.0, 0.0)
            reserve_qty = min(needed, available)
            if reserve_qty <= 0:
                continue
            values = requirement._movement_product_values()
            values.update({
                "movement_type": "reserve",
                "quantity": reserve_qty,
                "unit": requirement.unit,
                "project_id": requirement.project_id.id,
                "purchase_requirement_id": requirement.id,
                "note": f"Projektreservierung aus {requirement.bom_id.name}",
            })
            Movement.create(values)
        return True

    def _release_project_reservation(self):
        Movement = self.env["sab.stock.movement"]
        for requirement in self:
            requirement.invalidate_recordset()
            quantity = max(requirement.project_reserved_quantity or 0.0, 0.0)
            if quantity <= 0:
                continue
            values = requirement._movement_product_values()
            values.update({
                "movement_type": "release",
                "quantity": quantity,
                "unit": requirement.unit,
                "project_id": requirement.project_id.id,
                "purchase_requirement_id": requirement.id,
                "note": f"Projektreservierung aufgehoben: {requirement.name}",
            })
            Movement.create(values)
        return True

    def action_create_purchase_orders(self):
        requirements = self.exists().filtered(
            lambda req: req.state == "open"
            and not req.optional
            and req.shortage_quantity > 0
            and not req.purchase_order_line_id
        )
        if not requirements:
            raise ValidationError(
                "In der Auswahl befindet sich kein offener Fehlbestand ohne Bestellung."
            )
        not_released = requirements.filtered(
            lambda req: req.bom_id.purchase_release_state != "released"
        )
        if not_released:
            raise ValidationError(
                "Bestellungen dürfen erst nach der Bestellfreigabe des Projektleiters erzeugt werden."
            )
        without_supplier = requirements.filtered(lambda req: not req.supplier_product_id.supplier_id)
        if without_supplier:
            names = ", ".join(without_supplier.mapped("product_id.name") or without_supplier.mapped("name"))
            raise ValidationError(
                f"Für folgende Positionen fehlt ein Lieferantenartikel: {names}."
            )

        grouped = defaultdict(lambda: self.env["sab.purchase.requirement"])
        for requirement in requirements:
            grouped[requirement.supplier_id.id] |= requirement

        created_orders = self.env["sab.purchase.order"]
        for supplier_id, supplier_requirements in grouped.items():
            order = self.env["sab.purchase.order"].create({
                "supplier_id": supplier_id,
                "line_ids": [
                    (0, 0, {
                        "requirement_id": requirement.id,
                        "quantity_ordered": requirement.suggested_order_quantity,
                        "unit_purchase_price": requirement.unit_purchase_price,
                    })
                    for requirement in supplier_requirements.sorted(
                        key=lambda req: (
                            req.project_id.sab_project_reference or "",
                            req.sequence,
                            req.id,
                        )
                    )
                ],
            })
            created_orders |= order

        return {
            "type": "ir.actions.act_window",
            "name": _("Bestellvorschläge"),
            "res_model": "sab.purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created_orders.ids)],
            "target": "current",
        }


class SabPurchaseOrder(models.Model):
    _name = "sab.purchase.order"
    _description = "SAB-P Lieferantenbestellung"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Bestellung",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("sab.purchase.order")
        or _("Neue Bestellung"),
        index=True,
    )
    supplier_id = fields.Many2one(
        "sab.supplier",
        string="Lieferant",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related="supplier_id.partner_id",
        string="Lieferantenkontakt",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Entwurf"),
            ("to_approve", "Zur Freigabe"),
            ("approved", "Freigegeben"),
            ("sent", "Bestellt – offen"),
            ("partial", "Teilgeliefert"),
            ("done", "Vollständig geliefert"),
            ("cancel", "Storniert"),
        ],
        string="Status",
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        "sab.purchase.order.line",
        "order_id",
        string="Bestellpositionen",
        copy=True,
    )
    project_ids = fields.Many2many(
        "project.project",
        string="Projekte",
        compute="_compute_totals",
        store=True,
    )
    amount_total = fields.Float(
        string="Bestellwert netto",
        digits=(16, 2),
        compute="_compute_totals",
        store=True,
    )
    receipt_progress = fields.Float(
        string="Wareneingang (%)",
        compute="_compute_totals",
        store=True,
    )
    approved_at = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    sent_at = fields.Datetime(string="Bestellt am", readonly=True, copy=False)
    sent_by_id = fields.Many2one("res.users", string="Bestellt durch", readonly=True, copy=False)
    note = fields.Text(string="Hinweise")

    @api.depends(
        "line_ids.project_id",
        "line_ids.purchase_total",
        "line_ids.quantity_ordered",
        "line_ids.quantity_received",
    )
    def _compute_totals(self):
        for order in self:
            order.project_ids = order.line_ids.mapped("project_id")
            order.amount_total = sum(order.line_ids.mapped("purchase_total"))
            ordered = sum(order.line_ids.mapped("quantity_ordered"))
            received = sum(order.line_ids.mapped("quantity_received"))
            order.receipt_progress = min(received / ordered * 100.0, 100.0) if ordered else 0.0

    @api.constrains("supplier_id", "line_ids")
    def _check_supplier_lines(self):
        for order in self:
            wrong = order.line_ids.filtered(
                lambda line: line.requirement_id.supplier_id != order.supplier_id
            )
            if wrong:
                raise ValidationError(
                    "Alle Positionen einer Bestellung müssen zum gleichen Lieferanten gehören."
                )

    def _check_purchasing_user(self):
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
            or self.env.user.has_group("project.group_project_manager")
        ):
            return True
        raise AccessError("Diese Funktion ist dem Einkauf oder einem Projektleiter vorbehalten.")

    def _check_project_manager(self):
        if self.env.is_superuser() or self.env.user.has_group("project.group_project_manager"):
            return True
        raise AccessError("Die Bestellung muss durch einen Projektleiter freigegeben werden.")

    def _check_receiving_user(self):
        if (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_warehouse")
            or self.env.user.has_group("sab_project.group_sab_purchasing")
            or self.env.user.has_group("project.group_project_manager")
        ):
            return True
        raise AccessError("Wareneingänge dürfen nur durch Lager, Einkauf oder Projektleitung gebucht werden.")

    def action_submit_for_approval(self):
        self._check_purchasing_user()
        for order in self:
            if order.state != "draft":
                raise ValidationError("Nur ein Entwurf kann zur Freigabe vorgelegt werden.")
            if not order.line_ids:
                raise ValidationError("Eine leere Bestellung kann nicht freigegeben werden.")
            order.state = "to_approve"
        return True

    def action_approve(self):
        self._check_project_manager()
        for order in self:
            if order.state not in ("draft", "to_approve"):
                raise ValidationError("Diese Bestellung kann nicht mehr freigegeben werden.")
            order.write({
                "state": "approved",
                "approved_at": fields.Datetime.now(),
                "approved_by_id": self.env.user.id,
            })
        return True

    def action_print_order(self):
        self.ensure_one()
        return self.env.ref("sab_project.action_report_sab_purchase_order").report_action(self)

    def action_send_order_email(self):
        self._check_purchasing_user()
        for order in self:
            if order.state != "approved":
                raise ValidationError(
                    "Die Bestellung muss vor dem Versand durch einen Projektleiter freigegeben werden."
                )
            if not order.partner_id or not order.partner_id.email:
                raise ValidationError(
                    f"Beim Lieferanten {order.supplier_id.name} ist keine E-Mail-Adresse hinterlegt."
                )
            template = self.env.ref(
                "sab_project.mail_template_sab_purchase_order",
                raise_if_not_found=False,
            )
            if not template:
                raise ValidationError("Die E-Mail-Vorlage für Bestellungen fehlt.")
            template.send_mail(order.id, force_send=True)
            order.write({
                "state": "sent",
                "sent_at": fields.Datetime.now(),
                "sent_by_id": self.env.user.id,
            })
            order.line_ids.mapped("requirement_id").action_mark_ordered()
        return True

    def action_post_receipts(self):
        self._check_receiving_user()
        for order in self:
            if order.state not in ("sent", "partial"):
                raise ValidationError(
                    "Wareneingang kann nur für bestellte, noch offene Bestellungen gebucht werden."
                )
            lines = order.line_ids.filtered(lambda line: line.quantity_to_receive > 0)
            if not lines:
                raise ValidationError(
                    "Bitte in mindestens einer Bestellposition die jetzt gelieferte Menge eintragen."
                )
            lines._post_receipt()
            order.invalidate_recordset(["receipt_progress"])
            order.state = (
                "done"
                if all(line.quantity_remaining <= 0 for line in order.line_ids)
                else "partial"
            )
        return True

    def action_cancel(self):
        self._check_purchasing_user()
        for order in self:
            if any(line.quantity_received > 0 for line in order.line_ids):
                raise ValidationError(
                    "Eine Bestellung mit bereits gebuchtem Wareneingang darf nicht storniert werden."
                )
            order.line_ids.mapped("requirement_id")._release_project_reservation()
            order.line_ids.mapped("requirement_id").write({"state": "cancel"})
            order.state = "cancel"
        return True


class SabPurchaseOrderLine(models.Model):
    _name = "sab.purchase.order.line"
    _description = "SAB-P Lieferantenbestellposition"
    _order = "project_id, sequence, id"

    order_id = fields.Many2one(
        "sab.purchase.order",
        string="Bestellung",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10, index=True)
    requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="Einkaufsbedarf",
        required=True,
        ondelete="restrict",
        index=True,
    )
    project_id = fields.Many2one(
        related="requirement_id.project_id",
        string="Projekt",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related="requirement_id.product_id",
        string="Produkt (Altbestand)",
        store=True,
        readonly=True,
    )
    odoo_product_id = fields.Many2one(
        related="requirement_id.odoo_product_id",
        string="Produkt",
        store=True,
        readonly=True,
    )
    supplier_product_id = fields.Many2one(
        related="requirement_id.supplier_product_id",
        string="Lieferantenartikel",
        store=True,
        readonly=True,
    )
    supplier_article_number = fields.Char(
        related="supplier_product_id.supplier_article_number",
        string="Artikelnummer",
        store=True,
        readonly=True,
    )
    manufacturer_name = fields.Char(
        related="requirement_id.manufacturer_name",
        string="Hersteller",
        readonly=True,
    )
    quantity_ordered = fields.Float(
        string="Bestellmenge",
        required=True,
        digits=(16, 3),
    )
    quantity_received = fields.Float(
        string="Geliefert",
        readonly=True,
        copy=False,
        digits=(16, 3),
    )
    quantity_to_receive = fields.Float(
        string="Jetzt geliefert",
        digits=(16, 3),
        copy=False,
    )
    quantity_remaining = fields.Float(
        string="Noch offen",
        compute="_compute_amounts",
        store=True,
        digits=(16, 3),
    )
    unit = fields.Selection(
        related="requirement_id.unit",
        string="Einheit",
        store=True,
        readonly=True,
    )
    unit_purchase_price = fields.Float(
        string="EK je Einheit",
        digits=(16, 4),
        required=True,
    )
    purchase_total = fields.Float(
        string="Gesamt",
        digits=(16, 4),
        compute="_compute_amounts",
        store=True,
    )

    _requirement_unique = models.Constraint(
        "UNIQUE(requirement_id)",
        "Ein Einkaufsbedarf darf nur in einer Bestellung enthalten sein.",
    )

    @api.depends("quantity_ordered", "quantity_received", "unit_purchase_price")
    def _compute_amounts(self):
        for line in self:
            line.quantity_remaining = max(
                (line.quantity_ordered or 0.0) - (line.quantity_received or 0.0),
                0.0,
            )
            line.purchase_total = (
                line.quantity_ordered or 0.0
            ) * (line.unit_purchase_price or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.quantity_ordered <= 0:
                raise ValidationError("Die Bestellmenge muss größer als 0 sein.")
            line.requirement_id.purchase_order_line_id = line.id
        return lines

    def write(self, vals):
        protected = {"requirement_id", "quantity_ordered", "unit_purchase_price"}
        if protected & set(vals) and any(
            line.order_id.state not in ("draft", "to_approve") for line in self
        ):
            raise ValidationError(
                "Freigegebene oder versendete Bestellpositionen dürfen nicht mehr verändert werden."
            )
        return super().write(vals)

    def _post_receipt(self):
        Movement = self.env["sab.stock.movement"]
        for line in self:
            quantity = line.quantity_to_receive or 0.0
            if quantity <= 0:
                continue
            if quantity > line.quantity_remaining + 1e-9:
                raise ValidationError(
                    f"Bei {line.supplier_article_number or line.requirement_id.name} wurden mehr Teile "
                    "als noch offen eingegeben."
                )
            product_values = line.requirement_id._movement_product_values()
            common = {
                **product_values,
                "quantity": quantity,
                "unit": line.unit,
                "project_id": line.project_id.id,
                "purchase_requirement_id": line.requirement_id.id,
                "purchase_order_line_id": line.id,
            }
            Movement.create({
                **common,
                "movement_type": "receipt",
                "unit_cost": line.unit_purchase_price,
                "note": f"Wareneingang {line.order_id.name}",
            })
            # Incoming material is immediately commissioned/reserved for the
            # project that caused the order. It remains visible in stock, but is
            # no longer freely available to other projects.
            Movement.create({
                **common,
                "movement_type": "reserve",
                "note": f"Kommissionierung {line.project_id.display_name} aus {line.order_id.name}",
            })
            line.write({
                "quantity_received": line.quantity_received + quantity,
                "quantity_to_receive": 0.0,
            })
            if line.quantity_remaining <= 0:
                line.requirement_id.state = "received"
        return True
