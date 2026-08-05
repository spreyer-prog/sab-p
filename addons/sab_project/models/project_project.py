from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

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
    def _sab_allocate_project_reference(self):
        today = fields.Date.context_today(self)
        year = today.year if today else date.today().year

        # Atomare Vergabe über PostgreSQL. Auch bei parallelem Speichern
        # können zwei Benutzer niemals dieselbe laufende Nummer erhalten.
        self.env.cr.execute(
            '''
            INSERT INTO sab_project_year_counter (year, next_number, create_uid, create_date, write_uid, write_date)
            VALUES (%s, 2, %s, NOW(), %s, NOW())
            ON CONFLICT (year)
            DO UPDATE SET
                next_number = sab_project_year_counter.next_number + 1,
                write_uid = EXCLUDED.write_uid,
                write_date = NOW()
            RETURNING next_number - 1
            ''',
            [year, self.env.uid, self.env.uid],
        )
        running_number = self.env.cr.fetchone()[0]
        return f"A{year % 100:02d}.{running_number:04d}"

    def _sab_allocate_offer_reference(self):
        self.ensure_one()
        if not self.sab_project_reference:
            raise UserError(_("Für das Projekt wurde noch keine Projektnummer vergeben."))

        # Die Zeile des Projektes wird atomar aktualisiert und gesperrt.
        self.env.cr.execute(
            '''
            UPDATE project_project
               SET sab_next_offer_number = sab_next_offer_number + 1,
                   write_uid = %s,
                   write_date = NOW()
             WHERE id = %s
         RETURNING sab_next_offer_number - 1
            ''',
            [self.env.uid, self.id],
        )
        row = self.env.cr.fetchone()
        if not row:
            raise UserError(_("Das Projekt konnte nicht gefunden werden."))

        offer_number = row[0]
        self.invalidate_recordset(["sab_next_offer_number"])
        return f"{self.sab_project_reference}-{offer_number:02d}"

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            # Extern übergebene Projektnummern werden bewusst ignoriert.
            vals["sab_project_reference"] = self._sab_allocate_project_reference()
            vals["sab_next_offer_number"] = 1
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)

    def write(self, vals):
        if "sab_project_reference" in vals:
            for project in self:
                new_reference = vals.get("sab_project_reference")
                if project.sab_project_reference and new_reference != project.sab_project_reference:
                    raise UserError(_("Eine vergebene Projektnummer darf nicht geändert werden."))
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
