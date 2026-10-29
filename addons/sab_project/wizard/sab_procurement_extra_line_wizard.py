from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SabProcurementExtraLineWizard(models.TransientModel):
    _name = "sab.procurement.extra.line.wizard"
    _description = "SAB-P Zusatzposition zur Beschaffung"

    procurement_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Beschaffungspaket",
        required=True,
        readonly=True,
        domain="[('bom_scope','=','procurement'),('state','=','released')]",
    )
    purchase_order_id = fields.Many2one(
        "sab.purchase.order",
        string="Bestellentwurf",
        readonly=True,
        domain="[('state','=','draft')]",
    )
    available_cabinet_bom_ids = fields.Many2many(
        related="procurement_bom_id.source_cabinet_bom_ids",
        string="Verfügbare Schaltschränke",
        readonly=True,
    )
    source_cabinet_bom_id = fields.Many2one(
        "sab.project.bom",
        string="Verteiler / Schaltschrank",
        required=True,
        domain="[('id','in',available_cabinet_bom_ids)]",
    )
    odoo_product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        required=True,
        domain="[('active','=',True),('purchase_ok','=',True)]",
    )
    supplier_product_id = fields.Many2one(
        "sab.supplier.product",
        string="Lieferantenartikel",
        required=True,
        domain="[('odoo_product_id','=',odoo_product_id),('active','=',True)]",
    )
    supplier_id = fields.Many2one(
        related="supplier_product_id.supplier_id",
        string="Lieferant",
        readonly=True,
    )
    quantity = fields.Float(
        string="Zusätzliche Bestellmenge",
        required=True,
        digits=(16, 3),
        default=1.0,
    )
    unit = fields.Selection(
        [
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
    note = fields.Char(string="Begründung / Hinweis")

    @api.onchange("odoo_product_id")
    def _onchange_odoo_product_id(self):
        for wizard in self:
            wizard.supplier_product_id = False
            if not wizard.odoo_product_id:
                continue
            candidates = self.env["sab.supplier.product"].search(
                [
                    ("odoo_product_id", "=", wizard.odoo_product_id.id),
                    ("active", "=", True),
                ]
            )
            preferred = candidates.filtered("preferred")
            pool = preferred or candidates
            if pool:
                wizard.supplier_product_id = pool.sorted(
                    key=lambda item: (
                        item.net_purchase_price or 0.0,
                        item.id,
                    )
                )[:1]

    def action_add_extra_line(self):
        self.ensure_one()
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("sab_project.group_sab_purchasing")
            or self.env.user.has_group("project.group_project_manager")
        ):
            raise AccessError(
                "Zusatzpositionen dürfen nur durch Einkauf oder Projektleitung ergänzt werden."
            )
        package = self.procurement_bom_id
        if package.bom_scope != "procurement" or package.state != "released":
            raise ValidationError(
                "Zusatzpositionen benötigen ein freigegebenes Beschaffungspaket."
            )
        if self.source_cabinet_bom_id not in package.source_cabinet_bom_ids:
            raise ValidationError(
                "Die Zusatzposition muss einem im Beschaffungspaket enthaltenen "
                "Verteiler zugeordnet werden."
            )
        if self.quantity <= 0:
            raise ValidationError("Die zusätzliche Bestellmenge muss größer 0 sein.")
        if self.supplier_product_id.odoo_product_id != self.odoo_product_id:
            raise ValidationError(
                "Der Lieferantenartikel gehört nicht zum ausgewählten Produkt."
            )
        order = self.purchase_order_id
        if order:
            if order.state != "draft":
                raise ValidationError(
                    "Zusatzpositionen können nur einem Bestellentwurf hinzugefügt werden."
                )
            if order.supplier_id != self.supplier_product_id.supplier_id:
                raise ValidationError(
                    "Der Lieferant der Zusatzposition stimmt nicht mit dem Bestellentwurf überein."
                )

        legacy_product = self.env["sab.product"].search(
            [("odoo_product_id", "=", self.odoo_product_id.id)],
            limit=1,
        )
        next_sequence = max(package.line_ids.mapped("sequence") or [0]) + 10
        bom_line = self.env["sab.project.bom.line"].with_context(
            sab_procurement_extra_line=True
        ).create(
            {
                "bom_id": package.id,
                "sequence": next_sequence,
                "product_id": legacy_product.id or False,
                "odoo_product_id": self.odoo_product_id.id,
                "quantity": self.quantity,
                "unit": self.unit,
                "optional": False,
                "supplier_product_id": self.supplier_product_id.id,
                "unit_purchase_price": self.supplier_product_id.net_purchase_price
                or 0.0,
                "note": self.note or "Manuell ergänzte Beschaffungsposition",
                "source_cabinet_bom_id": self.source_cabinet_bom_id.id,
            }
        )
        requirement = self.env["sab.purchase.requirement"].create(
            {"bom_line_id": bom_line.id}
        )
        requirement._reserve_available_stock()
        requirement.write(
            {
                "quantity_to_order": self.quantity,
                "quantity_to_order_manual": True,
            }
        )

        if order:
            self.env["sab.purchase.order.line"].create(
                {
                    "order_id": order.id,
                    "requirement_id": requirement.id,
                    "quantity_ordered": self.quantity,
                    "unit_purchase_price": requirement.unit_purchase_price,
                }
            )
            return {
                "type": "ir.actions.act_window",
                "name": _("Bestellentwurf"),
                "res_model": "sab.purchase.order",
                "res_id": order.id,
                "view_mode": "form",
                "target": "current",
            }

        return {
            "type": "ir.actions.act_window",
            "name": _("Einkaufsbearbeitung"),
            "res_model": "sab.purchase.requirement",
            "view_mode": "list,form",
            "domain": [("bom_id", "=", package.id)],
            "target": "current",
        }
