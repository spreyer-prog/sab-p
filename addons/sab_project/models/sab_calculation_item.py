from odoo import api, fields, models


class SabCalculationItem(models.Model):
    _name = "sab.calculation.item"
    _description = "SAB-P Kalkulationsartikel"
    _order = "calculation_number, name"
    _rec_name = "name"

    active = fields.Boolean(string="Aktiv", default=True)
    calculation_number = fields.Char(
        string="Kalkulationsnummer",
        required=True,
        readonly=True,
        copy=False,
        default="Neu",
        index=True,
    )
    name = fields.Char(string="Bezeichnung", required=True, index=True)
    quotation_text = fields.Text(string="Angebotstext", required=True)
    status = fields.Selection(
        selection=[
            ("active", "Aktiv"),
            ("inactive", "Inaktiv"),
            ("phase_out", "Auslauf"),
            ("archived", "Archiviert"),
        ],
        string="Status",
        required=True,
        default="active",
        index=True,
    )

    standard_product_id = fields.Many2one(
        comodel_name="sab.product",
        string="Standardprodukt",
        ondelete="restrict",
    )
    alternative_product_ids = fields.Many2many(
        comodel_name="sab.product",
        relation="sab_calculation_item_alternative_product_rel",
        column1="calculation_item_id",
        column2="product_id",
        string="Alternativprodukte",
    )

    mechanical_factor = fields.Float(string="Mechanikfaktor (%)", default=100.0)
    wiring_factor = fields.Float(string="Verdrahtungsfaktor (%)", default=100.0)
    testing_factor = fields.Float(string="Prüffaktor (%)", default=100.0)
    space_factor = fields.Float(
        string="Platzfaktor",
        default=1.0,
        help="Dezimaler Platzfaktor, z. B. 0,50 / 1,00 / 1,25.",
    )

    product_line_ids = fields.One2many(
        comodel_name="sab.calculation.item.line",
        inverse_name="calculation_item_id",
        string="Kalkulationszeilen",
        copy=True,
    )

    legacy_import_key = fields.Char(
        string="Import-Schlüssel", copy=False, index=True, readonly=True
    )
    legacy_source_sheet = fields.Char(
        string="Import-Tabellenblatt", copy=False, readonly=True
    )
    legacy_source_row = fields.Integer(
        string="Import-Zeile", copy=False, readonly=True
    )

    space_units = fields.Float(
        string="Berechnete Platzeinheiten",
        compute="_compute_product_values",
        store=True,
    )
    mechanical_time_minutes = fields.Float(
        string="Berechnete Mechanikzeit in Minuten",
        compute="_compute_product_values",
        store=True,
    )
    wiring_time_minutes = fields.Float(
        string="Berechnete Verdrahtungszeit in Minuten",
        compute="_compute_product_values",
        store=True,
    )
    testing_time_minutes = fields.Float(
        string="Berechnete Prüfzeit in Minuten",
        compute="_compute_product_values",
        store=True,
    )
    additional_time_minutes = fields.Float(string="Zusatzzeit in Minuten", default=0.0)
    total_time_minutes = fields.Float(
        string="Gesamtzeit in Minuten",
        compute="_compute_total_time_minutes",
        store=True,
    )
    purchase_total = fields.Float(
        string="Material-EK gesamt",
        digits=(16, 4),
        compute="_compute_purchase_totals",
    )
    optional_purchase_total = fields.Float(
        string="Optionaler Material-EK",
        digits=(16, 4),
        compute="_compute_purchase_totals",
    )

    search_term_01 = fields.Char(string="Suchbegriff 1", index=True)
    search_term_02 = fields.Char(string="Suchbegriff 2", index=True)
    search_term_03 = fields.Char(string="Suchbegriff 3", index=True)
    search_term_04 = fields.Char(string="Suchbegriff 4", index=True)
    search_term_05 = fields.Char(string="Suchbegriff 5", index=True)
    search_term_06 = fields.Char(string="Suchbegriff 6", index=True)
    search_term_07 = fields.Char(string="Suchbegriff 7", index=True)
    search_term_08 = fields.Char(string="Suchbegriff 8", index=True)
    search_term_09 = fields.Char(string="Suchbegriff 9", index=True)
    search_term_10 = fields.Char(string="Suchbegriff 10", index=True)
    search_term_11 = fields.Char(string="Suchbegriff 11", index=True)
    search_term_12 = fields.Char(string="Suchbegriff 12", index=True)
    search_term_13 = fields.Char(string="Suchbegriff 13", index=True)
    search_term_14 = fields.Char(string="Suchbegriff 14", index=True)
    search_term_15 = fields.Char(string="Suchbegriff 15", index=True)
    search_term_16 = fields.Char(string="Suchbegriff 16", index=True)
    search_term_17 = fields.Char(string="Suchbegriff 17", index=True)
    search_term_18 = fields.Char(string="Suchbegriff 18", index=True)
    search_term_19 = fields.Char(string="Suchbegriff 19", index=True)
    search_term_20 = fields.Char(string="Suchbegriff 20", index=True)
    notes = fields.Text(string="Interne Hinweise")

    @api.depends(
        "product_line_ids.quantity",
        "product_line_ids.product_id.space_units",
        "product_line_ids.product_id.mechanical_time_minutes",
        "product_line_ids.product_id.wiring_time_minutes",
        "product_line_ids.product_id.testing_time_minutes",
        "mechanical_factor",
        "wiring_factor",
        "testing_factor",
        "space_factor",
    )
    def _compute_product_values(self):
        for record in self:
            base_space = base_mechanical = base_wiring = base_testing = 0.0
            for line in record.product_line_ids:
                if not line.product_id:
                    continue
                quantity = line.quantity or 0.0
                product = line.product_id
                base_space += product.space_units * quantity
                base_mechanical += product.mechanical_time_minutes * quantity
                base_wiring += product.wiring_time_minutes * quantity
                base_testing += product.testing_time_minutes * quantity
            record.space_units = base_space * record.space_factor
            record.mechanical_time_minutes = base_mechanical * record.mechanical_factor / 100.0
            record.wiring_time_minutes = base_wiring * record.wiring_factor / 100.0
            record.testing_time_minutes = base_testing * record.testing_factor / 100.0

    @api.depends(
        "mechanical_time_minutes",
        "wiring_time_minutes",
        "testing_time_minutes",
        "additional_time_minutes",
    )
    def _compute_total_time_minutes(self):
        for record in self:
            record.total_time_minutes = (
                record.mechanical_time_minutes
                + record.wiring_time_minutes
                + record.testing_time_minutes
                + record.additional_time_minutes
            )

    @api.depends("product_line_ids.purchase_total", "product_line_ids.optional")
    def _compute_purchase_totals(self):
        for record in self:
            normal_total = 0.0
            optional_total = 0.0
            for line in record.product_line_ids:
                if line.optional:
                    optional_total += line.purchase_total
                else:
                    normal_total += line.purchase_total
            record.purchase_total = normal_total
            record.optional_purchase_total = optional_total

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("calculation_number") or vals["calculation_number"] == "Neu":
                vals["calculation_number"] = sequence.next_by_code("sab.calculation.item") or "Neu"
        return super().create(vals_list)

    def write(self, vals):
        if "status" in vals:
            vals["active"] = vals["status"] != "archived"
        return super().write(vals)

    def action_set_active(self):
        self.write({"status": "active", "active": True})

    def action_set_inactive(self):
        self.write({"status": "inactive", "active": True})

    def action_set_phase_out(self):
        self.write({"status": "phase_out", "active": True})

    def action_archive_item(self):
        self.write({"status": "archived", "active": False})

    def action_restore_item(self):
        self.write({"status": "active", "active": True})
