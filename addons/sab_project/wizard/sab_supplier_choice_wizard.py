from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabSupplierChoiceWizard(models.TransientModel):
    _name = "sab.supplier.choice.wizard"
    _description = "SAB-P Lieferantenauswahl vor Bestellvorschlag"

    line_ids = fields.One2many(
        "sab.supplier.choice.wizard.line",
        "wizard_id",
        string="Lieferantenauswahl",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        requirement_ids = self.env.context.get("active_ids") or self.env.context.get(
            "sab_requirement_ids"
        ) or []
        requirements = self.env["sab.purchase.requirement"].browse(requirement_ids).exists()
        rows = []
        SupplierProduct = self.env["sab.supplier.product"]
        today = fields.Date.today()
        for requirement in requirements:
            product = requirement.odoo_product_id
            domain = [
                ("active", "=", True),
                ("odoo_product_id", "=", product.id),
                ("supplier_id.partner_id", "!=", False),
            ]
            candidates = SupplierProduct.search(domain)
            candidates = candidates.filtered(
                lambda candidate: (
                    not candidate.valid_from or candidate.valid_from <= today
                )
                and (
                    not candidate.valid_until or candidate.valid_until >= today
                )
            )
            selected = requirement.supplier_product_id
            if selected not in candidates:
                preferred = candidates.filtered("preferred")[:1]
                selected = preferred or candidates[:1]
            rows.append(
                (
                    0,
                    0,
                    {
                        "requirement_id": requirement.id,
                        "odoo_product_id": product.id,
                        "supplier_product_id": selected.id if selected else False,
                    },
                )
            )
        values["line_ids"] = rows
        return values

    def action_continue(self):
        self.ensure_one()
        requirements = self.env["sab.purchase.requirement"]
        for line in self.line_ids:
            if not line.supplier_product_id:
                raise ValidationError(
                    _("Bitte für jede markierte Position einen Lieferanten auswählen.")
                )
            supplier_product = line.supplier_product_id
            line.requirement_id.write(
                {
                    "supplier_product_id": supplier_product.id,
                    "unit_purchase_price": supplier_product.net_purchase_price,
                }
            )
            requirements |= line.requirement_id
        return requirements.action_create_standard_purchase_orders()


class SabSupplierChoiceWizardLine(models.TransientModel):
    _name = "sab.supplier.choice.wizard.line"
    _description = "SAB-P Lieferantenauswahl Position"

    wizard_id = fields.Many2one(
        "sab.supplier.choice.wizard",
        required=True,
        ondelete="cascade",
    )
    requirement_id = fields.Many2one(
        "sab.purchase.requirement",
        string="Bedarfsposition",
        required=True,
        readonly=True,
    )
    odoo_product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        required=True,
        readonly=True,
    )
    supplier_product_id = fields.Many2one(
        "sab.supplier.product",
        string="Lieferant / Lieferantenartikel",
        domain="[('active','=',True),('odoo_product_id','=',odoo_product_id),('supplier_id.partner_id','!=',False)]",
        required=True,
    )
    supplier_id = fields.Many2one(
        related="supplier_product_id.supplier_id",
        string="Lieferant",
        readonly=True,
    )
    supplier_article_number = fields.Char(
        related="supplier_product_id.supplier_article_number",
        string="Lieferanten-Art.-Nr.",
        readonly=True,
    )
    net_purchase_price = fields.Float(
        related="supplier_product_id.net_purchase_price",
        string="Netto-EK",
        readonly=True,
    )
    delivery_time_days = fields.Integer(
        related="supplier_product_id.delivery_time_days",
        string="Lieferzeit Tage",
        readonly=True,
    )
    preferred = fields.Boolean(
        related="supplier_product_id.preferred",
        string="Bevorzugt",
        readonly=True,
    )
