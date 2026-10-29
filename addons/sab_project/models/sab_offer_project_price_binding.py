"""Bind direct LV/NTG article prices within one project and customer.

No upgrade backfill: historical amounts are not rewritten when the module is
loaded. New unit-first lines are bound at normal save; old unit-first rows are
captured before a price-input edit. Legacy-rounding offers and Bauteil children
retain their existing algorithm and are deliberately outside this increment.
"""
from contextvars import ContextVar

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .position_price_policy import PriceCandidate, PriceBindingConflict, select_project_price


_IN_PRICE_CREATE = ContextVar("sab_project_price_create", default=False)

BINDING_FIELDS = frozenset({
    "sab_project_price_bound", "sab_project_unit_price", "sab_project_price_currency_id",
    "sab_project_price_source_id", "sab_project_price_reference",
})
IDENTITY_FIELDS = frozenset({
    "order_id", "line_type", "parent_section_id", "calculation_item_id",
    "odoo_product_id", "lv_position", "is_ntg",
})
PRICE_FACTOR_FIELDS = frozenset({
    "sab_material_factor", "sab_aux_material_factor", "sab_hourly_rate",
    "sab_time_factor", "sab_difficulty_factor", "sab_packaging_factor",
    "sab_skonto_factor", "sab_margin_factor", "sab_rebate_factor",
})


class SabProjectPositionPrice(models.Model):
    """Immutable commercial price, independent of the lifetime of an offer row.

    No public create/write path is allowed. The line adapter below establishes
    records from validated quote calculations, not from RPC-supplied amounts.
    """
    _name = "sab.project.position.price"
    _description = "SAB-P gespeicherter Projektpositionspreis"
    _rec_name = "position_code"
    _order = "project_id, position_code, id"

    project_id = fields.Many2one("project.project", required=True, ondelete="restrict", index=True)
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict", index=True)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    currency_id = fields.Many2one("res.currency", required=True, ondelete="restrict")
    position_code = fields.Char(required=True, index=True)
    is_ntg = fields.Boolean(required=True, default=False)
    source_kind = fields.Selection([("calculation", "Kalkulationsartikel"), ("product", "Produkt")], required=True)
    source_res_id = fields.Integer(required=True)
    unit_price = fields.Monetary(currency_field="currency_id", required=True)
    source_line_id = fields.Many2one("sab.offer.calculation.line", ondelete="set null")
    source_order_id = fields.Many2one("sale.order", ondelete="set null")
    source_reference = fields.Char(required=True)

    _scope_unique = models.Constraint(
        "UNIQUE(project_id, company_id, partner_id, position_code)",
        "Diese Projektposition besitzt bereits einen gespeicherten Einzelpreis.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        raise ValidationError("Projektpreise können nur aus einer Kalkulationsposition angelegt werden.")

    def write(self, vals):
        raise ValidationError("Ein gespeicherter Projektpositionspreis darf nicht überschrieben werden.")

    def unlink(self):
        raise ValidationError("Gespeicherte Projektpositionspreise bleiben als Preisgrundlage erhalten.")


class SabOfferProjectPriceBinding(models.Model):
    _inherit = "sab.offer.calculation.line"

    # The flag distinguishes 'not bound' from a legitimate price of 0.00.
    sab_project_price_bound = fields.Boolean(readonly=True, copy=True, index=True)
    sab_project_unit_price = fields.Monetary(
        string="Gespeicherter Projekt-Einzelpreis", currency_field="sab_project_price_currency_id",
        readonly=True, copy=True,
    )
    sab_project_price_currency_id = fields.Many2one("res.currency", readonly=True, copy=True)
    sab_project_price_source_id = fields.Many2one(
        "sab.offer.calculation.line", string="Preisquelle", readonly=True, copy=True,
        ondelete="set null", index=True,
    )
    sab_project_price_reference = fields.Char(string="Preisquelle Angebot", readonly=True, copy=True)
    sab_project_price_label = fields.Char(string="Preisbindung", compute="_compute_project_price_label")

    def _sab_can_bind_project_price(self):
        self.ensure_one()
        order = self.order_id
        return bool(
            self.line_type == "item" and not self.parent_section_id
            and (self.calculation_item_id or self.odoo_product_id)
            and (self.lv_position or "").strip() and order.sab_project_id
            and order.partner_id and order.currency_id
            and order.sab_price_rounding_version == "unit_v1"
        )

    def _sab_lock_price_projects(self):
        """Serialize first use, edits and simultaneous imports, in a stable order."""
        projects = self.mapped("order_id.sab_project_id")
        ids = sorted(projects.ids)
        if ids:
            # Row locking is the only raw SQL here; no data is modified by SQL.
            self.env.cr.execute(
                "SELECT id FROM project_project WHERE id IN %s ORDER BY id FOR UPDATE",
                [tuple(ids)],
            )

    def _sab_price_scope(self):
        self.ensure_one()
        order = self.order_id
        return (order.company_id.id, order.sab_project_id.id,
                order.partner_id.commercial_partner_id.id, order.currency_id.id)

    def _sab_price_identity(self):
        self.ensure_one()
        return (("calculation", self.calculation_item_id.id) if self.calculation_item_id
                else ("product", self.odoo_product_id.id))

    def _sab_price_registry_domain(self):
        self.ensure_one()
        company_id, project_id, partner_id, _currency_id = self._sab_price_scope()
        return [("company_id", "=", company_id), ("project_id", "=", project_id),
                ("partner_id", "=", partner_id),
                ("position_code", "=", (self.lv_position or "").strip())]

    def _sab_registry_price(self):
        self.ensure_one()
        # No public access to the registry is required. The domain is derived
        # only from an accessible quotation, never from arbitrary RPC arguments.
        return self.env["sab.project.position.price"].sudo().search(
            self._sab_price_registry_domain(), limit=1)

    def _sab_register_project_price(self, price, source):
        self.ensure_one()
        stored = self._sab_registry_price()
        if stored:
            return stored
        kind, source_id = self._sab_price_identity()
        source_line = self.browse(source.line_id).exists() if source and source.line_id else self
        reference = (source.reference if source else self.order_id.sab_offer_reference or self.order_id.name) or ("Angebot %s" % self.order_id.id)
        values = {
            "project_id": self.order_id.sab_project_id.id,
            "company_id": self.order_id.company_id.id,
            "partner_id": self.order_id.partner_id.commercial_partner_id.id,
            "currency_id": self.currency_id.id,
            "position_code": (self.lv_position or "").strip(), "is_ntg": bool(self.is_ntg),
            "source_kind": kind, "source_res_id": source_id, "unit_price": price,
            "source_line_id": source_line.id or False,
            "source_order_id": source_line.order_id.id or False,
            "source_reference": reference,
        }
        Registry = self.env["sab.project.position.price"].sudo()
        try:
            with self.env.cr.savepoint():
                # Bypass only the public immutable-model guard. Normal ORM
                # validation and the SQL uniqueness constraint still execute.
                return super(SabProjectPositionPrice, Registry).create([values])
        except IntegrityError as exc:
            if getattr(exc, "pgcode", None) != "23505":
                raise
            # Under a repeatable-read transaction a concurrent winner may not
            # yet be visible. Never guess a second price or suppress the conflict.
            raise ValidationError(
                "Eine andere Sitzung hat den Projektpreis inzwischen gespeichert. "
                "Bitte das Angebot neu laden und die Position erneut speichern.") from exc

    def _sab_previous_price_source(self):
        """Read only; never recalculate or write a source quotation.

        Restrict to predecessors so opening an older offer cannot adopt a later
        offer's price. No sudo: customer/project access rules remain effective.
        """
        self.ensure_one()
        if not self._sab_can_bind_project_price():
            return None
        order = self.order_id
        stored = self._sab_registry_price()
        if stored:
            if bool(stored.is_ntg) != bool(self.is_ntg):
                raise ValidationError("Die NTG-Kennzeichnung stimmt nicht mit dem gespeicherten Projektpreis überein.")
            kind, source_id = self._sab_price_identity()
            try:
                return select_project_price([PriceCandidate(
                    stored.source_line_id.id or 0, stored.source_kind, stored.source_res_id,
                    stored.currency_id.id, stored.unit_price, stored.source_order_id.sab_offer_reference or stored.source_reference,
                )], source_kind=kind, source_id=source_id, currency_id=order.currency_id.id)
            except PriceBindingConflict as exc:
                raise ValidationError(str(exc)) from exc
        origin_order_id = order._origin.id
        origin_line_id = self._origin.id
        domain = [
            ("order_id.company_id", "=", order.company_id.id),
            ("order_id.sab_project_id", "=", order.sab_project_id.id),
            ("order_id.partner_id.commercial_partner_id", "=", order.partner_id.commercial_partner_id.id),
            ("order_id.state", "!=", "cancel"),
            ("line_type", "=", "item"), ("parent_section_id", "=", False),
            ("lv_position", "=", (self.lv_position or "").strip()),
            ("is_ntg", "=", bool(self.is_ntg)),
        ]
        if origin_order_id:
            domain.append(("order_id", "<=", origin_order_id))
        if origin_line_id:
            domain.append(("id", "<", origin_line_id))
        rows = self.search(domain, order="id")
        candidates = []
        for row in rows:
            kind, source_id = row._sab_price_identity()
            candidates.append(PriceCandidate(
                line_id=row.id, source_kind=kind, source_id=source_id,
                currency_id=(row.sab_project_price_currency_id.id if row.sab_project_price_bound
                             else row.currency_id.id),
                unit_price=(row.sab_project_unit_price if row.sab_project_price_bound
                            else row.unit_recommended_net_price),
                reference=row.order_id.sab_offer_reference or row.order_id.name,
            ))
        kind, source_id = self._sab_price_identity()
        try:
            return select_project_price(candidates, source_kind=kind, source_id=source_id,
                                        currency_id=order.currency_id.id)
        except PriceBindingConflict as exc:
            raise ValidationError(str(exc)) from exc

    def _sab_bind_project_prices(self, allow_reuse_price=False):
        """Capture once; only the target line is written, with its current price.

        Existing predecessors are never rewritten as a side effect of reuse.
        Their own write path captures their old price before any factor edit.
        """
        candidates = self.filtered(lambda row: not row.sab_project_price_bound
                                    and row._sab_can_bind_project_price())
        candidates._sab_lock_price_projects()
        for line in candidates.sorted("id"):
            source = line._sab_previous_price_source()
            price = source.unit_price if source is not None else line.unit_recommended_net_price
            if (source is not None and not allow_reuse_price
                    and line.currency_id.compare_amounts(price, line.unit_recommended_net_price)):
                raise ValidationError(
                    "Der historische Einzelpreis dieser Position weicht vom gespeicherten "
                    "Projektpreis ab. Das bestehende Angebot wird nicht automatisch umgerechnet.")
            stored = line._sab_register_project_price(price, source)
            values = {
                "sab_project_price_bound": True,
                "sab_project_unit_price": stored.unit_price,
                "sab_project_price_currency_id": stored.currency_id.id,
                "sab_project_price_source_id": stored.source_line_id.id or False,
                "sab_project_price_reference": stored.source_reference,
            }
            # This private path changes only our metadata. Calling the standard
            # ORM writer retains ACLs, record rules and dependency recomputation,
            # but avoids re-running LV assignment / section normalization here.
            # The public write() below rejects these fields even in RPC context.
            models.Model.write(line, values)
        return candidates

    @api.depends("sab_project_price_bound", "sab_project_price_reference")
    def _compute_project_price_label(self):
        for line in self:
            line.sab_project_price_label = (
                "Projektpreis: %s" % (line.sab_project_price_reference or "gespeichert")
                if line.sab_project_price_bound else False
            )

    @api.depends(
        "sab_project_price_bound", "sab_project_unit_price", "sab_project_price_currency_id",
        "lv_position", "is_ntg", "calculation_item_id", "odoo_product_id",
        "parent_section_id", "order_id.sab_project_id", "order_id.partner_id",
        "quantity", "line_type", "currency_id", "order_id.sab_price_rounding_version",
    )
    def _compute_price(self):
        bound = self.filtered(lambda row: row.sab_project_price_bound
                              and row._sab_can_bind_project_price())
        unbound = self - bound
        if unbound:
            super(SabOfferProjectPriceBinding, unbound)._compute_price()
        for line in bound:
            if line.currency_id != line.sab_project_price_currency_id:
                raise ValidationError("Die Währung eines gebundenen Projektpreises darf nicht geändert werden.")
            line.unit_recommended_net_price = line.sab_project_unit_price
            line.recommended_net_price = line.currency_id.round(line.sab_project_unit_price * line.quantity)
        # Unsaved form preview: read existing prices, without creating records.
        for line in unbound:
            if isinstance(line.id, int) or not line._sab_can_bind_project_price():
                continue
            origin = line._origin
            same_origin = bool(
                origin and origin._sab_can_bind_project_price()
                and origin._sab_price_identity() == line._sab_price_identity()
                and origin._sab_price_scope() == line._sab_price_scope()
                and origin.lv_position == line.lv_position and origin.is_ntg == line.is_ntg
            )
            source = None if same_origin else line._sab_previous_price_source()
            if same_origin:
                price = origin.sab_project_unit_price if origin.sab_project_price_bound else origin.unit_recommended_net_price
            elif source is not None:
                price = source.unit_price
            else:
                continue
            line.unit_recommended_net_price = price
            line.recommended_net_price = line.currency_id.round(price * line.quantity)

    @api.model_create_multi
    def create(self, vals_list):
        # Even copy_data and a caller-supplied context cannot inject a snapshot.
        prepared = [{k: v for k, v in vals.items() if k not in BINDING_FIELDS | {"unit_recommended_net_price", "recommended_net_price"}}
                    for vals in vals_list]
        token = _IN_PRICE_CREATE.set(True)
        try:
            records = super().create(prepared)
        finally:
            _IN_PRICE_CREATE.reset(token)
        changed = records._sab_bind_project_prices(allow_reuse_price=True)
        if changed and not self.env.context.get("skip_sale_line_sync"):
            changed._sync_customer_order_lines()
        return records

    def write(self, vals):
        if BINDING_FIELDS.intersection(vals):
            raise ValidationError("Projektpreise werden ausschließlich aus der gespeicherten Kalkulation übernommen.")
        if {"unit_recommended_net_price", "recommended_net_price"}.intersection(vals):
            raise ValidationError("Berechnete Verkaufspreise dürfen nicht direkt überschrieben werden.")
        # A process-local marker cannot be forged through RPC context.
        technical = _IN_PRICE_CREATE.get()
        # Normalization during batch creation is not a completed commercial row.
        if not technical:
            self._sab_bind_project_prices()
        for line in self.filtered("sab_project_price_bound"):
            if {"unit_recommended_net_price", "recommended_net_price"}.intersection(vals):
                raise ValidationError("Der gespeicherte Projekt-Einzelpreis darf nicht überschrieben werden.")
            # Renumbering a draft is a different project position, not a price edit.
            # Changing its article or turning it into a Bauteil would invalidate the scope.
            for name in ("order_id", "calculation_item_id", "odoo_product_id", "parent_section_id"):
                if name in vals and (vals[name] or False) != (line[name].id or False):
                    raise ValidationError("Eine preisgebundene Artikelposition darf nicht umgewidmet werden. Bitte eine neue Position anlegen.")
            if "line_type" in vals and vals["line_type"] != line.line_type:
                raise ValidationError("Der Typ einer preisgebundenen Position darf nicht geändert werden.")
        # The LV release guard in the existing pipeline still applies. Draft
        # renumbering keeps the existing unit price instead of reading live masters.
        result = super().write(vals)
        if not technical and IDENTITY_FIELDS.intersection(vals):
            for line in self.filtered("sab_project_price_bound"):
                # A draft LV rename may keep its price, but it cannot contradict
                # an already existing price at the new LV code.
                source = line._sab_previous_price_source()
                if source is not None and source.unit_price != line.sab_project_unit_price:
                    raise ValidationError(
                        "Die gewählte LV-/NTG-Position besitzt einen anderen Projektpreis. "
                        "Bitte die gewünschte Position neu übernehmen statt umzunummerieren.")
                line._sab_register_project_price(line.sab_project_unit_price, source)
        changed = self._sab_bind_project_prices(allow_reuse_price=bool(IDENTITY_FIELDS.intersection(vals))) if not technical else self.browse()
        if changed and not self.env.context.get("skip_sale_line_sync"):
            changed._sync_customer_order_lines()
        return result

    def action_refresh_from_calculation_item(self):
        if self.filtered("sab_project_price_bound"):
            raise ValidationError(
                "Diese Projektposition besitzt einen gespeicherten Einzelpreis. "
                "Eine Aktualisierung aus den Stammdaten ist dafür gesperrt.")
        return super().action_refresh_from_calculation_item()


class SaleOrderProjectPriceBinding(models.Model):
    _inherit = "sale.order"

    def write(self, vals):
        lines = self.mapped("sab_calculation_line_ids")
        if PRICE_FACTOR_FIELDS.intersection(vals):
            # Capture historical unit-first rows before an intentional factor edit.
            # New rows added in the same call use the new factors on their first save.
            lines._sab_bind_project_prices()
        bound = lines.filtered("sab_project_price_bound")
        if bound and {"sab_project_id", "partner_id", "company_id", "currency_id", "pricelist_id"}.intersection(vals):
            for order in self:
                if not order.sab_calculation_line_ids.filtered("sab_project_price_bound"):
                    continue
                for field in ("sab_project_id", "company_id", "currency_id"):
                    if field in vals and (vals[field] or False) != (order[field].id or False):
                        raise ValidationError("Projekt, Firma und Währung dürfen nach der Preisbindung nicht geändert werden.")
                if "pricelist_id" in vals:
                    # Odoo derives currency_id from the pricelist. A currency
                    # switch must be rejected before the computed field changes,
                    # even when the caller does not pass currency_id explicitly.
                    pricelist = self.env["product.pricelist"].browse(
                        vals["pricelist_id"] or False
                    ).exists()
                    target_currency = pricelist.currency_id or order.company_id.currency_id
                    if target_currency != order.currency_id:
                        raise ValidationError(
                            "Eine Preisliste mit anderer Währung darf bei gebundenen "
                            "Projektpreisen nicht gewählt werden."
                        )
                if "partner_id" in vals:
                    partner = self.env["res.partner"].browse(vals["partner_id"]).exists()
                    if partner.commercial_partner_id != order.partner_id.commercial_partner_id:
                        raise ValidationError("Der Kunde darf nach der Projektpreisbindung nicht ausgetauscht werden.")
        return super().write(vals)
