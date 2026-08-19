from odoo import api, models, _
from odoo.exceptions import ValidationError


class SaleOrderOfferReleaseServerSecurity(models.Model):
    _inherit = "sale.order"

    def _sab_offer_reuse_assert_editable(self):
        result = super()._sab_offer_reuse_assert_editable()
        for order in self:
            if order.sab_offer_release_state == "released":
                raise ValidationError(
                    _(
                        "Das Angebot ist zum Verschicken freigegeben und "
                        "festgeschrieben. Positionen können nur über eine neue "
                        "Revision ergänzt werden."
                    )
                )
        return result


class SaleOrderLineOfferReleaseSecurity(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("sab_offer_release_write"):
            order_ids = {
                vals.get("order_id")
                for vals in vals_list
                if vals.get("order_id")
            }
            released = self.env["sale.order"].browse(order_ids).filtered(
                lambda order: order.sab_project_id
                and order.sab_offer_release_state == "released"
            )
            if released:
                raise ValidationError(
                    _(
                        "Zu einem zum Verschicken freigegebenen Angebot dürfen "
                        "keine Auftragspositionen mehr ergänzt werden. Bitte eine "
                        "neue Revision anlegen."
                    )
                )
        return super().create(vals_list)

    def write(self, vals):
        commercial_fields = {
            "product_id",
            "product_template_id",
            "name",
            "display_type",
            "sequence",
            "product_uom_qty",
            "product_uom",
            "price_unit",
            "discount",
            "tax_ids",
        }
        if (
            not self.env.context.get("sab_offer_release_write")
            and commercial_fields.intersection(vals)
            and any(
                line.order_id.sab_project_id
                and line.order_id.sab_offer_release_state == "released"
                for line in self
            )
        ):
            raise ValidationError(
                _(
                    "Die kaufmännischen Positionen eines zum Verschicken "
                    "freigegebenen Angebots sind festgeschrieben. Bitte eine neue "
                    "Revision anlegen."
                )
            )
        return super().write(vals)

    def unlink(self):
        if (
            not self.env.context.get("sab_offer_release_write")
            and any(
                line.order_id.sab_project_id
                and line.order_id.sab_offer_release_state == "released"
                for line in self
            )
        ):
            raise ValidationError(
                _(
                    "Auftragspositionen eines zum Verschicken freigegebenen "
                    "Angebots dürfen nicht gelöscht werden. Bitte eine neue "
                    "Revision anlegen."
                )
            )
        return super().unlink()
