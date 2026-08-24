from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabProjectBom(models.Model):
    _name = "sab.project.bom"
    _description = "SAB-P Projektstückliste"
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Stückliste", required=True, readonly=True, copy=False)
    order_id = fields.Many2one(comodel_name="sale.order", string="Auftrag / Angebot", required=True, ondelete="restrict", index=True)
    project_id = fields.Many2one(comodel_name="project.project", string="Projekt", required=True, ondelete="restrict", index=True)
    state = fields.Selection(selection=[("draft", "Entwurf"), ("released", "Freigegeben")], string="Status", required=True, default="draft", index=True)
    generated_at = fields.Datetime(string="Erzeugt am", required=True, readonly=True, default=fields.Datetime.now)
    generated_by_id = fields.Many2one(comodel_name="res.users", string="Erzeugt von", required=True, readonly=True, default=lambda self: self.env.user)
    line_ids = fields.One2many(comodel_name="sab.project.bom.line", inverse_name="bom_id", string="Stücklistenpositionen", copy=True)
    production_order_ids = fields.One2many(comodel_name="sab.production.order", inverse_name="bom_id", string="Fertigungsaufträge", copy=False)
    production_order_count = fields.Integer(string="Anzahl Fertigungsaufträge", compute="_compute_production_order_count")
    purchase_requirement_ids = fields.One2many(comodel_name="sab.purchase.requirement", inverse_name="bom_id", string="Einkaufsbedarf", copy=False)
    purchase_requirement_count = fields.Integer(string="Anzahl Einkaufsbedarfe", compute="_compute_purchase_requirement_count")
    note = fields.Text(string="Hinweise")

    _order_unique = models.Constraint("UNIQUE(order_id)", "Für diesen Auftrag existiert bereits eine SAB-P Stückliste.")

    @api.depends("production_order_ids")
    def _compute_production_order_count(self):
        for record in self:
            record.production_order_count = len(record.production_order_ids)

    @api.depends("purchase_requirement_ids")
    def _compute_purchase_requirement_count(self):
        for record in self:
            record.purchase_requirement_count = len(record.purchase_requirement_ids)

    def action_release(self):
        for record in self:
            if not record.line_ids:
                raise ValidationError("Eine leere Stückliste kann nicht freigegeben werden.")
            record.state = "released"
        return True

    def action_create_production_order(self):
        self.ensure_one()
        if self.state != "released":
            raise ValidationError(_("Ein Fertigungsauftrag kann erst aus einer freigegebenen Stückliste erzeugt werden."))
        production = self.production_order_ids[:1]
        if not production:
            production = self.env["sab.production.order"].create({"name": f"FA {self.order_id.sab_offer_reference or self.order_id.name}", "bom_id": self.id})
        return {"type": "ir.actions.act_window", "name": _("SAB-P Fertigungsauftrag"), "res_model": "sab.production.order", "res_id": production.id, "view_mode": "form", "target": "current"}

    def action_generate_purchase_requirements(self):
        self.ensure_one()
        if self.state != "released":
            raise ValidationError(_("Einkaufsbedarf kann erst aus einer freigegebenen Stückliste erzeugt werden."))
        Requirement = self.env["sab.purchase.requirement"]
        existing_line_ids = set(self.purchase_requirement_ids.mapped("bom_line_id").ids)
        for line in self.line_ids.filtered(lambda item: not item.optional):
            if line.id in existing_line_ids:
                continue
            Requirement.create({"bom_line_id": line.id})
        return {"type": "ir.actions.act_window", "name": _("SAB-P Einkaufsbedarf"), "res_model": "sab.purchase.requirement", "view_mode": "list,form", "domain": [("bom_id", "=", self.id)], "target": "current"}

    def _sab_released_bom_allowed_fields(self):
        """Fields that may still change after technical BOM release.

        Technical material data remains immutable. Later workflow extensions may
        add operational metadata by extending this method.
        """
        return {
            "state",
            "purchase_release_state",
            "purchase_released_at",
            "purchase_released_by_id",
        }

    def write(self, vals):
        if any(record.state == "released" for record in self):
            allowed = self._sab_released_bom_allowed_fields()
            if set(vals) - allowed:
                raise ValidationError("Eine freigegebene Stückliste ist technisch gesperrt.")
            if "state" in vals and vals.get("state") != "released":
                raise ValidationError("Eine freigegebene Stückliste darf nicht zurückgesetzt werden.")
        return super().write(vals)

    def unlink(self):
        if any(record.state == "released" for record in self):
            raise ValidationError("Eine freigegebene Stückliste darf nicht gelöscht werden.")
        return super().unlink()


class SabProjectBomLine(models.Model):
    _name = "sab.project.bom.line"
    _description = "SAB-P Projektstücklistenposition"
    _order = "sequence, id"

    bom_id = fields.Many2one(comodel_name="sab.project.bom", string="Stückliste", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    product_id = fields.Many2one(comodel_name="sab.product", string="Produkt", required=True, ondelete="restrict", index=True)
    quantity = fields.Float(string="Menge", required=True, digits=(16, 3), default=1.0)
    unit = fields.Selection(selection=[("pcs", "Stück"), ("m", "Meter"), ("kg", "kg"), ("min", "Minute"), ("h", "Stunde"), ("flat", "Pauschal")], string="Einheit", required=True, default="pcs")
    optional = fields.Boolean(string="Optional", default=False)
    supplier_product_id = fields.Many2one(comodel_name="sab.supplier.product", string="Lieferantenartikel", ondelete="set null")
    unit_purchase_price = fields.Float(string="EK je Einheit", digits=(16, 4), readonly=True)
    purchase_total = fields.Float(string="EK gesamt", digits=(16, 4), compute="_compute_purchase_total", store=True)
    note = fields.Char(string="Bemerkung")

    @api.depends("quantity", "unit_purchase_price")
    def _compute_purchase_total(self):
        for record in self:
            record.purchase_total = (record.quantity or 0.0) * (record.unit_purchase_price or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        allow_procurement_extra = (
            self.env.context.get("sab_procurement_extra_line")
            and (
                self.env.is_superuser()
                or self.env.user.has_group("sab_project.group_sab_purchasing")
                or self.env.user.has_group("project.group_project_manager")
            )
        )
        for vals in vals_list:
            bom_id = vals.get("bom_id")
            if bom_id:
                bom = self.env["sab.project.bom"].browse(bom_id)
                allowed_released_extra = (
                    allow_procurement_extra
                    and getattr(bom, "bom_scope", "total") == "procurement"
                )
                if bom.state == "released" and not allowed_released_extra:
                    raise ValidationError("Zu einer freigegebenen Stückliste dürfen keine Positionen ergänzt werden.")
        return super().create(vals_list)

    def write(self, vals):
        if any(record.bom_id.state == "released" for record in self):
            raise ValidationError("Positionen einer freigegebenen Stückliste sind gesperrt.")
        return super().write(vals)

    def unlink(self):
        if any(record.bom_id.state == "released" for record in self):
            raise ValidationError("Positionen einer freigegebenen Stückliste dürfen nicht gelöscht werden.")
        return super().unlink()
