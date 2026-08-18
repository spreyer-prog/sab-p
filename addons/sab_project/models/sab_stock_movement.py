from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabStockMovement(models.Model):
    _name = "sab.stock.movement"
    _description = "SAB-P Lagerbewegung"
    _order = "movement_date desc, id desc"

    name = fields.Char(string="Beleg", required=True, readonly=True, copy=False)
    product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Produkt (Altbestand)",
        required=False,
        ondelete="restrict",
        index=True,
    )
    odoo_product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        required=False,
        ondelete="restrict",
        index=True,
    )
    product_name = fields.Char(
        string="Produkt",
        compute="_compute_product_name",
    )
    movement_type = fields.Selection(
        selection=[
            ("receipt", "Zugang"),
            ("issue", "Entnahme"),
            ("reserve", "Reservierung"),
            ("release", "Reservierung freigeben"),
        ],
        string="Bewegungsart",
        required=True,
        index=True,
    )
    quantity = fields.Float(string="Menge", required=True, digits=(16, 3))
    unit = fields.Selection(
        selection=[
            ("pcs", "Stück"),
            ("m", "Meter"),
            ("kg", "kg"),
            ("min", "Minute"),
            ("h", "Stunde"),
            ("flat", "Pauschal"),
        ],
        string="Einheit",
        required=True,
        default="pcs",
    )
    unit_cost = fields.Float(
        string="Bewertungs-EK",
        digits=(16, 4),
        readonly=True,
        copy=False,
    )
    total_value = fields.Float(
        string="Bewegungswert",
        digits=(16, 4),
        compute="_compute_total_value",
        store=True,
    )
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projekt / Kommission",
        ondelete="set null",
        index=True,
    )
    purchase_requirement_id = fields.Many2one(
        comodel_name="sab.purchase.requirement",
        string="Einkaufsbedarf",
        ondelete="set null",
        index=True,
    )
    purchase_order_line_id = fields.Many2one(
        "sab.purchase.order.line",
        string="Bestellposition",
        ondelete="set null",
        index=True,
    )
    movement_date = fields.Datetime(
        string="Buchungszeitpunkt",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Gebucht von",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    note = fields.Char(string="Bemerkung")

    def init(self):
        """Backfill the normal Odoo product on all legacy stock movements."""
        self.env.cr.execute(
            """
            UPDATE sab_stock_movement movement
               SET odoo_product_id = product.odoo_product_id
              FROM sab_product product
             WHERE movement.product_id = product.id
               AND movement.odoo_product_id IS NULL
               AND product.odoo_product_id IS NOT NULL
            """
        )

    @api.depends("product_id", "odoo_product_id")
    def _compute_product_name(self):
        for record in self:
            record.product_name = (
                record.odoo_product_id.display_name
                if record.odoo_product_id
                else record.product_id.display_name
                if record.product_id
                else ""
            )

    @api.depends("quantity", "unit_cost")
    def _compute_total_value(self):
        for record in self:
            record.total_value = (record.quantity or 0.0) * (record.unit_cost or 0.0)

    @api.constrains("product_id", "odoo_product_id")
    def _check_product_reference(self):
        for record in self:
            if not (record.product_id or record.odoo_product_id):
                raise ValidationError(
                    _("Eine Lagerbewegung benötigt ein gültiges Produkt.")
                )

    @api.constrains("quantity", "unit_cost")
    def _check_values(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(
                    _("Lagerbewegungen benötigen eine Menge größer 0.")
                )
            if record.unit_cost < 0:
                raise ValidationError(_("Der Bewertungs-EK darf nicht negativ sein."))

    @api.model
    def _stock_domain(self, legacy_product=False, odoo_product=False):
        if odoo_product:
            return [("odoo_product_id", "=", odoo_product.id)]
        return [("product_id", "=", legacy_product.id)]

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        Movement = self.env["sab.stock.movement"]
        LegacyProduct = self.env["sab.product"]
        OdooProduct = self.env["product.product"]

        for incoming in vals_list:
            vals = dict(incoming)
            legacy = LegacyProduct.browse(vals.get("product_id")).exists()
            odoo_product = OdooProduct.browse(vals.get("odoo_product_id")).exists()

            if not odoo_product and legacy and legacy.odoo_product_id:
                odoo_product = legacy.odoo_product_id
                vals["odoo_product_id"] = odoo_product.id
            if not legacy and odoo_product:
                legacy = LegacyProduct.search(
                    [("odoo_product_id", "=", odoo_product.id)], limit=1
                )
                if legacy:
                    vals["product_id"] = legacy.id
            if not (legacy or odoo_product):
                raise ValidationError(
                    _("Für die Lagerbewegung ist ein gültiges Produkt erforderlich.")
                )

            qty = float(vals.get("quantity") or 0.0)
            movement_type = vals.get("movement_type")
            existing = Movement.search(
                self._stock_domain(legacy, odoo_product)
            )
            receipts = existing.filtered(lambda m: m.movement_type == "receipt")
            issues = existing.filtered(lambda m: m.movement_type == "issue")
            on_hand = sum(receipts.mapped("quantity")) - sum(issues.mapped("quantity"))
            reserved = (
                sum(existing.filtered(lambda m: m.movement_type == "reserve").mapped("quantity"))
                - sum(existing.filtered(lambda m: m.movement_type == "release").mapped("quantity"))
            )
            available = on_hand - reserved

            if movement_type == "issue" and qty > available + 1e-9:
                raise ValidationError(
                    _(
                        "Die Entnahme überschreitet den frei verfügbaren Lagerbestand. "
                        "Reservierte Mengen müssen zuerst freigegeben werden."
                    )
                )
            if movement_type == "reserve" and qty > available + 1e-9:
                raise ValidationError(
                    _("Die Reservierung überschreitet den verfügbaren Lagerbestand.")
                )
            if movement_type == "release" and qty > reserved + 1e-9:
                raise ValidationError(
                    _(
                        "Es kann nicht mehr Reservierung freigegeben werden als vorhanden ist."
                    )
                )

            if movement_type == "issue" and "unit_cost" not in vals:
                inventory_value = (
                    sum(receipts.mapped("total_value"))
                    - sum(issues.mapped("total_value"))
                )
                vals["unit_cost"] = inventory_value / on_hand if on_hand else 0.0
            elif movement_type in ("reserve", "release"):
                vals["unit_cost"] = 0.0

            vals.setdefault(
                "name",
                self.env["ir.sequence"].next_by_code("sab.stock.movement")
                or _("Lagerbewegung"),
            )
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        protected = {
            "product_id",
            "odoo_product_id",
            "movement_type",
            "quantity",
            "unit",
            "unit_cost",
            "movement_date",
            "purchase_requirement_id",
            "purchase_order_line_id",
        }
        if protected.intersection(vals):
            raise ValidationError(
                _("Gebuchte Lagerbewegungen dürfen nicht nachträglich verändert werden.")
            )
        return super().write(vals)

    def unlink(self):
        raise ValidationError(
            _("Gebuchte Lagerbewegungen dürfen nicht gelöscht werden. Erfassen Sie eine Gegenbuchung.")
        )
