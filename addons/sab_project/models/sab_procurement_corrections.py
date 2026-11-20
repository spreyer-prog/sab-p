from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SabPurchaseRequirementProcurementCorrections(models.Model):
    _inherit = "sab.purchase.requirement"

    @api.depends(
        "product_id.manufacturer_supplier_id",
        "product_id.manufacturer_id",
        "odoo_product_id.sab_manufacturer_supplier_id",
        "odoo_product_id.sab_manufacturer_id",
    )
    def _compute_manufacturer_name(self):
        """Show the real DATANORM manufacturer, not the import supplier."""
        for requirement in self:
            legacy, product = requirement._stock_identity()
            datanorm_manufacturer = (
                product.sab_manufacturer_id
                if product
                else legacy.manufacturer_id
                if legacy
                else False
            )
            supplier_source = (
                product.sab_manufacturer_supplier_id
                if product
                else legacy.manufacturer_supplier_id
                if legacy
                else False
            )
            requirement.manufacturer_name = (
                datanorm_manufacturer.name
                if datanorm_manufacturer
                else supplier_source.name
                if supplier_source
                else ""
            )


class SabPurchaseOrderProcurementCorrections(models.Model):
    _inherit = "sab.purchase.order"

    @api.depends(
        "line_ids.project_id",
        "line_ids.purchase_total",
        "line_ids.quantity_ordered",
        "line_ids.quantity_received",
        "line_ids.unit_purchase_price",
    )
    def _compute_totals(self):
        """Calculate receipt progress without adding incompatible units."""
        for order in self:
            order.project_ids = order.line_ids.mapped("project_id")
            order.amount_total = sum(order.line_ids.mapped("purchase_total"))

            total_value = 0.0
            received_value = 0.0
            line_ratios = []
            for line in order.line_ids.filtered(lambda item: item.quantity_ordered > 0):
                ordered = max(line.quantity_ordered or 0.0, 0.0)
                received = min(max(line.quantity_received or 0.0, 0.0), ordered)
                unit_price = max(line.unit_purchase_price or 0.0, 0.0)
                total_value += ordered * unit_price
                received_value += received * unit_price
                line_ratios.append(received / ordered if ordered else 1.0)

            if total_value > 0:
                progress = received_value / total_value * 100.0
            elif line_ratios:
                progress = sum(line_ratios) / len(line_ratios) * 100.0
            else:
                progress = 0.0
            order.receipt_progress = min(max(progress, 0.0), 100.0)

    def action_send_order_email(self):
        """Send the approved order with the generated PDF attached."""
        self._check_purchasing_user()
        template = self.env.ref(
            "sab_project.mail_template_sab_purchase_order",
            raise_if_not_found=False,
        )
        report_action = self.env.ref(
            "sab_project.action_report_sab_purchase_order",
            raise_if_not_found=False,
        )
        if not template:
            raise ValidationError("Die E-Mail-Vorlage für Bestellungen fehlt.")
        if not report_action:
            raise ValidationError("Das PDF-Layout für Bestellungen fehlt.")

        for order in self:
            if order.state != "approved":
                raise ValidationError(
                    "Die Bestellung muss vor dem Versand durch einen Projektleiter freigegeben werden."
                )
            if not order.partner_id or not order.partner_id.email:
                raise ValidationError(
                    f"Beim Lieferanten {order.supplier_id.name} ist keine E-Mail-Adresse hinterlegt."
                )

            pdf_content, _pdf_format = self.env["ir.actions.report"]._render_qweb_pdf(
                report_action.report_name,
                res_ids=[order.id],
            )
            attachment = self.env["ir.attachment"].create({
                "name": f"Bestellung_{order.name}.pdf",
                "raw": pdf_content,
                "mimetype": "application/pdf",
                "res_model": order._name,
                "res_id": order.id,
            })
            template.send_mail(
                order.id,
                force_send=True,
                email_values={"attachment_ids": [(4, attachment.id)]},
            )
            order.write({
                "state": "sent",
                "sent_at": fields.Datetime.now(),
                "sent_by_id": self.env.user.id,
            })
            order.line_ids.mapped("requirement_id").action_mark_ordered()
        return True


class SabPurchaseOrderLineProcurementCorrections(models.Model):
    _inherit = "sab.purchase.order.line"

    def _post_receipt(self):
        """Book incoming goods and reserve only the quantity still needed by the project.

        Supplier packaging or minimum-order quantities can make the ordered amount
        larger than the project shortage. The excess must stay freely available in
        the warehouse instead of being commissioned to the project that triggered
        the order.
        """
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

            requirement = line.requirement_id
            requirement.invalidate_recordset()
            project_needed = max(
                (requirement.quantity or 0.0)
                - (requirement.project_reserved_quantity or 0.0),
                0.0,
            )
            reserve_quantity = min(quantity, project_needed)

            product_values = requirement._movement_product_values()
            common = {
                **product_values,
                "quantity": quantity,
                "unit": line.unit,
                "project_id": line.project_id.id,
                "purchase_requirement_id": requirement.id,
                "purchase_order_line_id": line.id,
            }
            Movement.create({
                **common,
                "movement_type": "receipt",
                "unit_cost": line.unit_purchase_price,
                "note": f"Wareneingang {line.order_id.name}",
            })

            if reserve_quantity > 0:
                Movement.create({
                    **common,
                    "quantity": reserve_quantity,
                    "movement_type": "reserve",
                    "note": f"Kommissionierung {line.project_id.display_name} aus {line.order_id.name}",
                })

            line.write({
                "quantity_received": line.quantity_received + quantity,
                "quantity_to_receive": 0.0,
            })
            if line.quantity_remaining <= 0:
                requirement.state = "received"
        return True
