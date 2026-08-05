from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sab_project_id = fields.Many2one(
        comodel_name="project.project",
        string="SAB-P Projekt",
        copy=True,
        index=True,
        ondelete="restrict",
        help="Projekt, zu dem dieses Angebot gehört.",
    )
    sab_offer_reference = fields.Char(
        string="SAB-P Angebotsnummer",
        readonly=True,
        copy=False,
        index=True,
        help="Automatisch vergebene, unveränderliche Angebotsnummer.",
    )

    _sab_offer_reference_unique = models.Constraint(
        "UNIQUE(sab_offer_reference)",
        "Die Angebotsnummer ist bereits vergeben.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            project_id = vals.get("sab_project_id")
            if project_id:
                project = self.env["project.project"].browse(project_id).exists()
                if not project:
                    raise ValidationError(_("Das ausgewählte Projekt existiert nicht."))
                offer_reference = project._sab_allocate_offer_reference()
                vals["sab_offer_reference"] = offer_reference
                vals["name"] = offer_reference
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)

    def write(self, vals):
        if "sab_project_id" in vals:
            for order in self:
                new_project_id = vals.get("sab_project_id")
                if (
                    order.sab_project_id
                    and new_project_id
                    and new_project_id != order.sab_project_id.id
                ):
                    raise ValidationError(
                        _("Das Projekt eines bereits nummerierten Angebots darf nicht geändert werden.")
                    )
        if "sab_offer_reference" in vals:
            for order in self:
                if (
                    order.sab_offer_reference
                    and vals.get("sab_offer_reference") != order.sab_offer_reference
                ):
                    raise ValidationError(
                        _("Eine vergebene Angebotsnummer darf nicht geändert werden.")
                    )
        if "name" in vals:
            for order in self:
                if (
                    order.sab_offer_reference
                    and vals.get("name") != order.name
                ):
                    raise ValidationError(
                        _("Eine vergebene Angebotsnummer darf nicht geändert werden.")
                    )
        return super().write(vals)

    def copy_data(self, default=None):
        result = super().copy_data(default)
        for values in result:
            values.pop("sab_offer_reference", None)
            if values.get("sab_project_id"):
                values["name"] = "/"
        return result
