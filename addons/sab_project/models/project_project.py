from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    sab_status = fields.Selection(
        selection=[
            ("offer_open", "Angebot offen"),
            ("customer_awarded", "Kunde hat Auftrag – Vergabe an uns offen"),
            ("won", "Auftrag erhalten"),
            ("lost", "Auftrag verloren"),
        ],
        string="Projektstatus",
        default="offer_open",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    sab_request_date = fields.Date(
        string="Anfragedatum",
        default=fields.Date.context_today,
        required=True,
        copy=False,
    )
    sab_contact_id = fields.Many2one(
        comodel_name="res.partner",
        string="Ansprechpartner",
        domain="[('parent_id', '=', partner_id)]",
    )
    sab_engineering_office_id = fields.Many2one(
        comodel_name="res.partner",
        string="Ingenieurbüro",
    )
    sab_delivery_date = fields.Date(string="Liefertermin")
    sab_calendar_week = fields.Integer(
        string="KW",
        compute="_compute_sab_calendar_week",
        store=True,
    )

    sab_created_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Angelegt von",
        related="create_uid",
        readonly=True,
        store=True,
    )

    sab_offer_amount = fields.Monetary(
        string="Gesamtangebotssumme",
        currency_field="sab_currency_id",
        compute="_compute_sab_offer_totals",
        store=True,
        help="Summe aller nicht stornierten Angebote und Unterangebote des Projekts.",
    )
    sab_calculated_hours = fields.Float(
        string="Kalkulierte Zeit",
        compute="_compute_sab_offer_totals",
        store=True,
        help="Summe der kalkulierten Stunden aller nicht stornierten Angebote.",
    )
    sab_required_hours = fields.Float(
        string="Benötigte Zeit",
        help="Wird später aus Zeitbuchungen bzw. der Nachkalkulation ermittelt.",
    )
    sab_currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        string="Währung",
        readonly=True,
    )

    sab_inquiry_type_id = fields.Many2one(
        comodel_name="sab.inquiry.type",
        string="Art der Anfrage",
        required=True,
        default=lambda self: self.env.ref(
            "sab_project.sab_inquiry_type_electrician",
            raise_if_not_found=False,
        ),
        ondelete="restrict",
        index=True,
    )
    sab_technology_id = fields.Many2one(
        comodel_name="sab.technology",
        string="Technik",
        required=True,
        default=lambda self: self.env.ref(
            "sab_project.sab_technology_energy_distribution",
            raise_if_not_found=False,
        ),
        ondelete="restrict",
        index=True,
    )
    sab_service_type_id = fields.Many2one(
        comodel_name="sab.service.type",
        string="Leistungsart",
        required=True,
        default=lambda self: self.env.ref(
            "sab_project.sab_service_type_new_installation",
            raise_if_not_found=False,
        ),
        ondelete="restrict",
        index=True,
    )

    sab_customer_phone = fields.Char(
        string="Telefon",
        related="partner_id.phone",
        readonly=True,
    )
    sab_customer_email = fields.Char(
        string="E-Mail",
        related="partner_id.email",
        readonly=True,
    )

    sab_commission = fields.Char(
        string="Kommission",
        help="Interne oder kundenseitige Kommissionsbezeichnung.",
    )
    sab_offer_identifier = fields.Char(
        string="Angebotskennzeichen",
        help="Freies Kennzeichen des Vorgangs bzw. Angebots.",
    )
    sab_customer_order_reference = fields.Char(
        string="Bestell-Nr. / Bestellkennzeichen",
    )
    sab_customer_short_code = fields.Char(
        string="Kundenkürzel",
        help="Optionales Kürzel für Kunde oder Projekt.",
    )
    sab_follow_up_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Wiedervorlage an",
    )
    sab_follow_up_date = fields.Date(
        string="Datum Wiedervorlage",
    )
    sab_notes = fields.Html(string="Notiz")
    sab_project_description = fields.Html(string="Projektbeschreibung")
    sab_site_address = fields.Char(string="Baustelle / Lieferort")
    sab_internal_reference = fields.Char(string="Interne Referenz")

    sab_sale_order_ids = fields.One2many(
        comodel_name="sale.order",
        inverse_name="sab_project_id",
        string="Angebote",
    )
    sab_sale_order_count = fields.Integer(
        string="Anzahl Angebote",
        compute="_compute_sab_sale_order_count",
    )

    @api.depends("sab_delivery_date")
    def _compute_sab_calendar_week(self):
        for project in self:
            project.sab_calendar_week = (
                project.sab_delivery_date.isocalendar().week
                if project.sab_delivery_date
                else 0
            )

    @api.depends("sab_sale_order_ids")
    def _compute_sab_sale_order_count(self):
        for project in self:
            project.sab_sale_order_count = len(project.sab_sale_order_ids)

    @api.depends(
        "sab_sale_order_ids.state",
        "sab_sale_order_ids.amount_total",
        "sab_sale_order_ids.sab_calculated_hours",
    )
    def _compute_sab_offer_totals(self):
        for project in self:
            valid_orders = project.sab_sale_order_ids.filtered(
                lambda order: order.state != "cancel"
            )
            project.sab_offer_amount = sum(valid_orders.mapped("amount_total"))
            project.sab_calculated_hours = sum(
                valid_orders.mapped("sab_calculated_hours")
            )

    sab_project_reference = fields.Char(
        string="Projektnummer",
        readonly=True,
        copy=False,
        index=True,
        help="Automatisch vergebene, unveränderliche SAB-P Projektnummer.",
    )
    sab_next_offer_number = fields.Integer(
        string="Nächste Angebotsnummer",
        default=1,
        copy=False,
        readonly=True,
        groups="base.group_system",
    )

    _sab_project_reference_unique = models.Constraint(
        "UNIQUE(sab_project_reference)",
        "Die Projektnummer ist bereits vergeben.",
    )

    @api.model
    def _sab_get_numbering_settings(self):
        params = self.env["ir.config_parameter"].sudo()
        return {
            "prefix": params.get_param("sab_project.project_prefix", "A"),
            "year_digits": int(params.get_param("sab_project.year_digits", "2")),
            "project_separator": params.get_param("sab_project.project_separator", "."),
            "project_digits": int(params.get_param("sab_project.project_digits", "4")),
            "project_start_number": int(
                params.get_param("sab_project.project_start_number", "1")
            ),
            "offer_separator": params.get_param("sab_project.offer_separator", "-"),
            "offer_digits": int(params.get_param("sab_project.offer_digits", "2")),
        }

    @api.model
    def _sab_allocate_project_reference(self):
        today = fields.Date.context_today(self)
        year = today.year if today else date.today().year
        settings = self._sab_get_numbering_settings()
        start_number = settings["project_start_number"]

        self.env.cr.execute(
            """
            INSERT INTO sab_project_year_counter
                (year, next_number, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, NOW(), %s, NOW())
            ON CONFLICT (year)
            DO UPDATE SET
                next_number = sab_project_year_counter.next_number + 1,
                write_uid = EXCLUDED.write_uid,
                write_date = NOW()
            RETURNING next_number - 1
            """,
            [year, start_number + 1, self.env.uid, self.env.uid],
        )
        running_number = self.env.cr.fetchone()[0]

        year_part = str(year) if settings["year_digits"] == 4 else f"{year % 100:02d}"
        running_part = f"{running_number:0{settings['project_digits']}d}"
        return (
            f"{settings['prefix']}{year_part}"
            f"{settings['project_separator']}{running_part}"
        )

    def _sab_ensure_project_reference(self):
        """Assign a SAB-P number to legacy/existing projects on first SAB-P use."""
        for project in self:
            if not project.sab_project_reference:
                project.write({
                    "sab_project_reference": project._sab_allocate_project_reference(),
                    "sab_next_offer_number": project.sab_next_offer_number or 1,
                })
        return True

    def action_assign_sab_project_reference(self):
        self.ensure_one()
        self._sab_ensure_project_reference()
        return True

    def _sab_allocate_offer_reference(self):
        self.ensure_one()
        self._sab_ensure_project_reference()

        self.env.cr.execute(
            """
            UPDATE project_project
               SET sab_next_offer_number = sab_next_offer_number + 1,
                   write_uid = %s,
                   write_date = NOW()
             WHERE id = %s
         RETURNING sab_next_offer_number - 1
            """,
            [self.env.uid, self.id],
        )
        row = self.env.cr.fetchone()
        if not row:
            raise UserError(_("Das Projekt konnte nicht gefunden werden."))

        offer_number = row[0]
        self.invalidate_recordset(["sab_next_offer_number"])
        settings = self._sab_get_numbering_settings()
        offer_part = f"{offer_number:0{settings['offer_digits']}d}"
        return (
            f"{self.sab_project_reference}"
            f"{settings['offer_separator']}{offer_part}"
        )

    def action_create_sab_quotation(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Bitte zuerst einen Kunden im Projekt hinterlegen."))
        self._sab_ensure_project_reference()
        return {
            "type": "ir.actions.act_window",
            "name": _("Neues SAB-P Angebot"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_sab_project_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_user_id": self.user_id.id or self.env.user.id,
                "default_client_order_ref": self.sab_customer_order_reference or False,
                "default_note": False,
            },
        }

    def action_view_sab_quotations(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Angebote %s") % (self.sab_project_reference or self.name),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("sab_project_id", "=", self.id)],
            "context": {
                "default_sab_project_id": self.id,
                "default_partner_id": self.partner_id.id or False,
                "default_user_id": self.user_id.id or self.env.user.id,
            },
        }
        if self.sab_sale_order_count == 1:
            action.update({
                "view_mode": "form",
                "res_id": self.sab_sale_order_ids.id,
            })
        return action

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            vals["sab_project_reference"] = self._sab_allocate_project_reference()
            vals["sab_next_offer_number"] = 1
            vals.setdefault("user_id", self.env.user.id)
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)

    def write(self, vals):
        if "sab_project_reference" in vals:
            for project in self:
                new_reference = vals.get("sab_project_reference")
                if (
                    project.sab_project_reference
                    and new_reference != project.sab_project_reference
                ):
                    raise UserError(
                        _("Eine vergebene Projektnummer darf nicht geändert werden.")
                    )
        return super().write(vals)

    def copy_data(self, default=None):
        default = dict(default or {})
        default.pop("sab_project_reference", None)
        default["sab_next_offer_number"] = 1
        return super().copy_data(default)

    def _compute_display_name(self):
        super()._compute_display_name()
        for project in self:
            if project.sab_project_reference:
                project.display_name = f"{project.sab_project_reference} – {project.name}"
