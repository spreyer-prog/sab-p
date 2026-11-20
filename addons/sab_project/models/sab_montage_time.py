"""Article assembly minutes, represented once and priced only in quotations."""
import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplateMontageTime(models.Model):
    _inherit = "product.template"

    sab_is_montage_time = fields.Boolean(
        string="SAB-P Montagezeitprodukt", default=False, copy=False, readonly=True,
        help="Internes Zeitprodukt. Kein Material-EK, Lagerbestand oder Einkaufsbedarf.",
    )


class SabCalculationItemLineMontageTime(models.Model):
    _inherit = "sab.calculation.item.line"

    quantity = fields.Float(digits=(16, 4))

    is_auto_montage_time = fields.Boolean(
        string="Automatische Montagezeit", default=False, copy=True, readonly=True,
    )

    @api.depends("is_auto_montage_time", "odoo_product_id.product_tmpl_id.sab_is_montage_time")
    def _compute_purchase_values(self):
        super()._compute_purchase_values()
        for line in self:
            if line.is_auto_montage_time or line.odoo_product_id.sab_is_montage_time:
                # Money belongs to the quote's frozen hourly rate, never material EK.
                line.selected_supplier_product_id = False
                line.unit_purchase_price = 0.0
                line.purchase_total = 0.0

    @api.constrains("is_auto_montage_time", "odoo_product_id", "quantity", "unit",
                    "position_type", "optional", "fixed_quantity")
    def _check_auto_montage_shape(self):
        for line in self:
            if line.odoo_product_id.sab_is_montage_time and not line.is_auto_montage_time:
                raise ValidationError("Montagezeit bitte als Minuten am Kalkulationsartikel eintragen.")
            if not line.is_auto_montage_time:
                continue
            if (not line.odoo_product_id.sab_is_montage_time or line.unit != "min"
                    or line.position_type != "normal" or line.optional
                    or line.fixed_quantity or not math.isfinite(line.quantity)
                    or line.quantity <= 0):
                raise ValidationError(
                    "Die automatische Montageposition benötigt das Montagezeitprodukt "
                    "und eine positive Minutenmenge. Zeit bitte am Kalkulationsartikel ändern."
                )


class SabCalculationItemMontageTime(models.Model):
    _inherit = "sab.calculation.item"

    legacy_time_minutes = fields.Float(
        string="Montagezeit je Artikel (min)", digits=(16, 4), copy=True,
        help="Excel-Spalte K: Gesamtminuten je Kalkulationsartikel. Bei einem Wert "
             "größer null entsteht eine automatische Produktposition. Die Aufteilung "
             "erfolgt mit den Artikel-Zeitfaktoren; Geldwerte erst im Angebot.",
    )

    montage_time_allocation_missing = fields.Boolean(
        string="Montage-Aufteilung prüfen", compute="_compute_montage_allocation_missing",
    )

    @api.depends("legacy_time_minutes", "mechanical_factor", "wiring_factor", "testing_factor")
    def _compute_montage_allocation_missing(self):
        for item in self:
            shares = (item.mechanical_factor, item.wiring_factor, item.testing_factor)
            item.montage_time_allocation_missing = bool(
                item.legacy_time_minutes > 0 and (
                    any(not math.isfinite(value) or value < 0 for value in shares)
                    or abs(sum(shares) - 100.0) > 0.0001
                )
            )

    @api.constrains("legacy_time_minutes")
    def _check_montage_minutes(self):
        for item in self:
            if not math.isfinite(item.legacy_time_minutes) or item.legacy_time_minutes < 0:
                raise ValidationError("Die Montagezeit muss eine endliche Zahl ab null sein.")

    def _sync_auto_montage_time(self):
        """Idempotent: update one managed row; never remove unrelated material rows."""
        if not self:
            return
        # Serialise concurrent imports/edits of the same articles.
        self.env.cr.execute(
            "SELECT id FROM sab_calculation_item WHERE id IN %s ORDER BY id FOR UPDATE",
            [tuple(sorted(self.ids))],
        )
        self.invalidate_recordset(["product_line_ids"])
        Line = self.env["sab.calculation.item.line"]
        product = self.env.ref("sab_project.product_montage_time_minute")
        for item in self:
            managed = Line.search([
                ("calculation_item_id", "=", item.id),
                ("is_auto_montage_time", "=", True),
            ], order="id")
            minutes = item.legacy_time_minutes
            if minutes <= 0:
                managed.unlink()
                continue
            values = {
                "odoo_product_id": product.id, "product_id": False,
                "quantity": minutes, "unit": "min", "position_type": "normal",
                "is_auto_montage_time": True, "optional": False,
                "fixed_quantity": False,
                "note": "Montagezeit; Bewertung mit dem gespeicherten Angebots-Stundensatz.",
            }
            if managed:
                changed = {key: value for key, value in values.items()
                           if (managed[0][key].id if key.endswith('_id')
                               else managed[0][key]) != value}
                if changed:
                    managed[0].write(changed)
                # Only duplicate managed time rows, never material or manual work.
                managed[1:].unlink()
            else:
                values.update({
                    "calculation_item_id": item.id,
                    "sequence": max(item.product_line_ids.mapped("sequence") or [0]) + 10,
                })
                Line.create(values)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(lambda item: item.legacy_time_minutes > 0)._sync_auto_montage_time()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "legacy_time_minutes" in vals or "product_line_ids" in vals:
            self._sync_auto_montage_time()
        return result

    @api.depends("legacy_time_minutes", "mechanical_factor", "wiring_factor", "testing_factor",
                 "montage_time_allocation_missing")
    def _compute_product_values(self):
        super()._compute_product_values()
        for item in self:
            if item.legacy_time_minutes > 0:
                # Excel supplies TOTAL article minutes. Do not add product times again.
                if item.montage_time_allocation_missing:
                    # Some legacy helper rows store costs in D/E/F, not percentages.
                    # Never turn 30 source minutes into hundreds of labour minutes.
                    item.mechanical_time_minutes = 0.0
                    item.wiring_time_minutes = 0.0
                    item.testing_time_minutes = 0.0
                else:
                    item.mechanical_time_minutes = item.legacy_time_minutes * item.mechanical_factor / 100.0
                    item.wiring_time_minutes = item.legacy_time_minutes * item.wiring_factor / 100.0
                    item.testing_time_minutes = item.legacy_time_minutes * item.testing_factor / 100.0

    @api.depends("legacy_time_minutes", "additional_time_minutes")
    def _compute_total_time_minutes(self):
        super()._compute_total_time_minutes()
        for item in self:
            if item.legacy_time_minutes > 0:
                # The source minute quantity is authoritative, even before the
                # technical split is resolved. The quote applies its own factors.
                item.total_time_minutes = item.legacy_time_minutes + item.additional_time_minutes

    @api.model
    def _initialize_auto_montage_time(self):
        """Upgrade existing article masters, never existing offer snapshots."""
        items = self.search([("legacy_time_minutes", ">", 0)])
        items._sync_auto_montage_time()
        return True


class SabOfferCalculationLineMontageTime(models.Model):
    _inherit = "sab.offer.calculation.line"

    @api.constrains("odoo_product_id", "line_type")
    def _check_no_direct_montage_product(self):
        for line in self:
            if line.line_type == "item" and line.odoo_product_id.sab_is_montage_time:
                raise ValidationError(
                    "Montagezeit bitte über die Minuten des Kalkulationsartikels übernehmen, "
                    "nicht als direkte Materialposition."
                )

    def _component_commands(self, item):
        commands = super()._component_commands(item)
        time_line_ids = set(item.product_line_ids.filtered(
            lambda line: line.is_auto_montage_time or line.odoo_product_id.sab_is_montage_time
        ).ids)
        # Time is already frozen by _snapshot_values in unit_*_minutes.
        # It must never become a purchasable BOM component or counted material.
        return [command for command in commands
                if command[2].get("source_calculation_line_id") not in time_line_ids]
