from odoo import api, fields, models


class SabProjectControlling(models.Model):
    _name = "sab.project.controlling"
    _description = "SAB-P Projektnachkalkulation"
    _rec_name = "project_id"

    project_id = fields.Many2one(comodel_name="project.project", string="Projekt", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="project_id.company_id.currency_id", string="Währung", readonly=True)
    calculated_hours = fields.Float(string="Kalkulierte Stunden", compute="_compute_values")
    actual_hours = fields.Float(string="Ist-Stunden", compute="_compute_values")
    hours_variance = fields.Float(string="Abweichung Stunden", compute="_compute_values")
    hours_variance_percent = fields.Float(string="Abweichung Stunden (%)", compute="_compute_values")
    actual_labor_cost = fields.Monetary(string="Ist-Lohnkosten", currency_field="currency_id", compute="_compute_values")
    material_issue_cost = fields.Monetary(
        string="Materialentnahmen",
        currency_field="currency_id",
        compute="_compute_values",
        help="Historischer Bewegungswert der projektbezogenen Lagerentnahmen.",
    )
    offer_amount = fields.Monetary(string="Angebotssumme", currency_field="currency_id", compute="_compute_values")
    actual_direct_cost = fields.Monetary(string="Ist-Direktkosten", currency_field="currency_id", compute="_compute_values")
    contribution_margin = fields.Monetary(string="Deckungsbeitrag vor Gemeinkosten", currency_field="currency_id", compute="_compute_values")
    contribution_margin_percent = fields.Float(string="Deckungsbeitrag (%)", compute="_compute_values")
    result_status = fields.Selection(
        selection=[("positive", "Positiv"), ("warning", "Kritisch"), ("negative", "Negativ")],
        string="Ergebnisstatus",
        compute="_compute_values",
    )

    _project_unique = models.Constraint("UNIQUE(project_id)", "Für dieses Projekt existiert bereits eine Nachkalkulation.")

    @api.depends("project_id")
    def _compute_values(self):
        TimeEntry = self.env["sab.time.entry"]
        Movement = self.env["sab.stock.movement"]
        for record in self:
            project = record.project_id
            if not project:
                record.calculated_hours = 0.0
                record.actual_hours = 0.0
                record.hours_variance = 0.0
                record.hours_variance_percent = 0.0
                record.actual_labor_cost = 0.0
                record.material_issue_cost = 0.0
                record.offer_amount = 0.0
                record.actual_direct_cost = 0.0
                record.contribution_margin = 0.0
                record.contribution_margin_percent = 0.0
                record.result_status = "warning"
                continue

            entries = TimeEntry.search([("project_id", "=", project.id), ("state", "=", "confirmed")])
            calculated_hours = project.sab_calculated_hours or 0.0
            actual_hours = sum(entries.mapped("hours"))
            labor_cost = sum(entries.mapped("cost_total"))
            issues = Movement.search([("project_id", "=", project.id), ("movement_type", "=", "issue")])
            issue_cost = sum(issues.mapped("total_value"))
            offer_amount = project.sab_offer_amount or 0.0
            direct_cost = labor_cost + issue_cost
            contribution = offer_amount - direct_cost
            contribution_percent = (contribution / offer_amount * 100.0) if offer_amount else 0.0

            record.calculated_hours = calculated_hours
            record.actual_hours = actual_hours
            record.hours_variance = actual_hours - calculated_hours
            record.hours_variance_percent = (((actual_hours - calculated_hours) / calculated_hours) * 100.0 if calculated_hours else 0.0)
            record.actual_labor_cost = labor_cost
            record.material_issue_cost = issue_cost
            record.offer_amount = offer_amount
            record.actual_direct_cost = direct_cost
            record.contribution_margin = contribution
            record.contribution_margin_percent = contribution_percent
            record.result_status = "negative" if contribution < 0 else ("warning" if contribution_percent < 10.0 else "positive")
