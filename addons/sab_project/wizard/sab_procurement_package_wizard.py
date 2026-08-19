from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command


class SabProcurementPackageWizard(models.TransientModel):
    _name = "sab.procurement.package.wizard"
    _description = "SAB-P Schaltschränke zur Beschaffung zusammenstellen"

    order_id = fields.Many2one(
        "sale.order",
        string="Auftrag",
        required=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        related="order_id.sab_project_id",
        string="Projekt",
        readonly=True,
    )
    cabinet_bom_ids = fields.Many2many(
        "sab.project.bom",
        relation="sab_procurement_package_wizard_cabinet_rel",
        column1="wizard_id",
        column2="cabinet_bom_id",
        string="Schaltschränke für diese Materialanforderung",
        required=True,
        domain="[('order_id','=',order_id),('bom_scope','=','cabinet'),('state','=','released')]",
    )
    note = fields.Text(
        string="Hinweis an Einkauf / Lager",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        order = self.env["sale.order"].browse(
            self.env.context.get("default_order_id")
            or self.env.context.get("active_id")
        ).exists()
        if order:
            values["order_id"] = order.id
            if "cabinet_bom_ids" in fields_list:
                cabinets = order.sab_bom_ids.filtered(
                    lambda bom: bom.bom_scope == "cabinet"
                    and bom.state == "released"
                )
                values["cabinet_bom_ids"] = [Command.set(cabinets.ids)]
        return values

    def action_create_procurement_package(self):
        self.ensure_one()
        if not (
            self.env.is_superuser()
            or self.env.user.has_group("project.group_project_manager")
        ):
            raise AccessError(
                "Nur die Projektleitung darf technisch freigegebene Schaltschränke "
                "zu einer Materialanforderung zusammenstellen."
            )
        order = self.order_id
        if order.state not in ("sale", "done"):
            raise ValidationError(
                "Die Materialanforderung kann erst nach 'Auftrag erhalten' erzeugt werden."
            )
        if order.sab_calculation_source != "schematic":
            raise ValidationError(
                "Eine Materialanforderung benötigt einen Schaltplan-Auftrag mit einzelnen Schaltschränken."
            )
        cabinets = self.cabinet_bom_ids.sorted(
            key=lambda bom: (
                bom.cabinet_line_id.sequence if bom.cabinet_line_id else 0,
                bom.id,
            )
        )
        if not cabinets:
            raise ValidationError(
                "Bitte mindestens einen Schaltschrank auswählen."
            )
        invalid = cabinets.filtered(
            lambda bom: bom.order_id != order
            or bom.project_id != order.sab_project_id
            or bom.bom_scope != "cabinet"
            or bom.state != "released"
        )
        if invalid:
            raise ValidationError(
                "Es dürfen nur technisch freigegebene Schaltschrank-Stücklisten "
                "dieses Auftrags ausgewählt werden."
            )

        existing_packages = self.env["sab.project.bom"].search(
            [
                ("bom_scope", "=", "procurement"),
                ("order_id", "=", order.id),
                ("source_cabinet_bom_ids", "in", cabinets.ids),
            ]
        )
        if existing_packages:
            duplicated = existing_packages.mapped("source_cabinet_bom_ids") & cabinets
            names = ", ".join(duplicated.mapped("name"))
            raise ValidationError(
                "Folgende Schaltschränke sind bereits in einer Materialanforderung "
                f"enthalten: {names}. Eine doppelte Bestellung wird dadurch verhindert."
            )

        line_commands = []
        sequence = 10
        for cabinet in cabinets:
            for source_line in cabinet.line_ids.sorted(
                key=lambda line: (line.sequence, line.id)
            ):
                line_commands.append(
                    Command.create(
                        {
                            "sequence": sequence,
                            "product_id": source_line.product_id.id or False,
                            "odoo_product_id": source_line.odoo_product_id.id
                            or False,
                            "quantity": source_line.quantity,
                            "unit": source_line.unit,
                            "optional": source_line.optional,
                            "supplier_product_id": source_line.supplier_product_id.id
                            or False,
                            "unit_purchase_price": source_line.unit_purchase_price
                            or 0.0,
                            "note": source_line.note,
                            "source_cabinet_bom_id": cabinet.id,
                            "source_cabinet_line_id": source_line.id,
                        }
                    )
                )
                sequence += 10

        if not line_commands:
            raise ValidationError(
                "Die ausgewählten Schaltschränke enthalten keine Materialpositionen."
            )

        reference = self.env["ir.sequence"].next_by_code(
            "sab.procurement.request"
        )
        if not reference:
            raise ValidationError(
                "Die Nummer für die Materialanforderung konnte nicht erzeugt werden."
            )
        cabinet_labels = ", ".join(
            cabinets.mapped("cabinet_line_id.description")
            or cabinets.mapped("name")
        )
        package = self.env["sab.project.bom"].create(
            {
                "name": f"{reference} / {cabinet_labels}",
                "procurement_reference": reference,
                "order_id": order.id,
                "project_id": order.sab_project_id.id,
                "bom_scope": "procurement",
                "source_cabinet_bom_ids": [Command.set(cabinets.ids)],
                "line_ids": line_commands,
                "note": self.note,
            }
        )
        package.action_release()
        return {
            "type": "ir.actions.act_window",
            "name": _("Materialanforderung %s") % reference,
            "res_model": "sab.project.bom",
            "res_id": package.id,
            "view_mode": "form",
            "target": "current",
        }
