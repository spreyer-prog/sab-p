"""Cabinet-first technical review and explicit, selected procurement handover.

The new UI entry point opts an order into this workflow. Historical BOMs are
not migrated, deleted or regenerated; the legacy API remains available only
for orders that have not entered the new flow. No quote prices are written.
"""
import math
from contextvars import ContextVar

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command

_FLOW_WRITE = ContextVar('sab_cabinet_first_internal_write', default=False)
_FLOW_RELEASE = ContextVar('sab_cabinet_first_release', default=False)
_META = {'sab_cabinet_first', 'sab_technical_released_at',
         'sab_technical_released_by_id', 'sab_handover_package_id'}


def _positive(value):
    return math.isfinite(value) and value > 0


class SaleOrderCabinetFirst(models.Model):
    _inherit = 'sale.order'

    sab_bom_cabinet_first = fields.Boolean(
        string='Einzelstücklisten vor Einkaufszusammenfassung', readonly=True,
        copy=False, default=False,
        help='Wird durch Einzelstücklisten erzeugen aktiviert; Altstücklisten bleiben erhalten.')

    def write(self, vals):
        if 'sab_bom_cabinet_first' in vals and not _FLOW_WRITE.get():
            raise ValidationError(_('Der Stücklistenablauf wird durch die Stücklistenerzeugung festgelegt.'))
        if vals.get('sab_bom_cabinet_first') is False and self.filtered('sab_bom_cabinet_first'):
            raise ValidationError(_('Der Einzelstücklistenablauf darf nicht zurückgesetzt werden.'))
        return super().write(vals)

    def _sab_lock_bom_order(self):
        # Engineering rights do not imply permission to reprice a sale order.
        self.check_access('read')
        ids = tuple(sorted(self.ids))
        if ids:
            self.env.cr.execute('SELECT id FROM sale_order WHERE id IN %s ORDER BY id FOR UPDATE', [ids])

    def _sab_activate_cabinet_first(self):
        self._sab_lock_bom_order()
        token = _FLOW_WRITE.set(True)
        try:
            self.filtered(lambda o: not o.sab_bom_cabinet_first).write({'sab_bom_cabinet_first': True})
        finally:
            _FLOW_WRITE.reset(token)

    def action_generate_sab_bom(self):
        self.ensure_one()
        if self.sab_bom_cabinet_first:
            return self.action_generate_sab_cabinet_boms()
        # Compatibility for historical API integrations; the UI uses the new
        # action below. Once opted in, this path can no longer regenerate a total.
        return super().action_generate_sab_bom()

    def action_generate_sab_cabinet_boms(self):
        self.ensure_one()
        if self.state not in ('sale', 'done') or not self.sab_project_id:
            raise ValidationError(_('Einzelstücklisten benötigen einen bestätigten Projektauftrag.'))
        if self.sab_calculation_source != 'schematic':
            raise ValidationError(_('Einzelstücklisten entstehen ausschließlich aus einem Schaltplan-Angebot.'))
        self._sab_lock_bom_order()
        self._sab_validate_schematic_lv_basis()
        self.sab_calculation_line_ids._normalize_section_membership()
        self._sab_validate_switchboard_structure()
        cabinets = self.sab_calculation_line_ids.filtered(lambda r: r.line_type == 'cabinet')
        if not cabinets:
            raise ValidationError(_('Bitte mindestens einen abgegrenzten Schaltschrank anlegen.'))
        Bom = self.env['sab.project.bom']
        with self.env.cr.savepoint():
            self._sab_activate_cabinet_first()
            result = Bom.browse()
            for cabinet in cabinets.sorted(key=lambda r: (r.sequence, r.id)):
                existing = Bom.search([('order_id', '=', self.id), ('bom_scope', '=', 'cabinet'),
                                       ('cabinet_line_id', '=', cabinet.id)])
                if len(existing) > 1:
                    raise ValidationError(_('Mehrere Einzelstücklisten für denselben Schrank gefunden. Bitte den Altbestand prüfen.'))
                if existing:
                    # Never overwrite a technical edit, even in draft and even
                    # when the list is temporarily empty during engineering.
                    result |= existing
                    continue
                lines = self.sab_calculation_line_ids.filtered(
                    lambda r: r.line_type == 'item' and r.parent_cabinet_id == cabinet)
                commands = self._sab_bom_values_for_lines(lines)
                if not commands:
                    raise ValidationError(_('Schrank %s enthält keine Materialpositionen.') % cabinet.description)
                token = _FLOW_WRITE.set(True)
                try:
                    result |= Bom.create({
                        'name': 'STL %s / %s' % (self.sab_offer_reference or self.name, cabinet.description),
                        'order_id': self.id, 'project_id': self.sab_project_id.id,
                        'bom_scope': 'cabinet', 'cabinet_line_id': cabinet.id,
                        'sab_cabinet_first': True, 'line_ids': commands,
                    })
                finally:
                    _FLOW_WRITE.reset(token)
        return {'type': 'ir.actions.act_window', 'name': _('Einzelstücklisten – technisch bearbeiten'),
                'res_model': 'sab.project.bom', 'view_mode': 'list,form',
                'domain': [('id', 'in', result.ids)], 'target': 'current'}

    def _sab_prepare_or_update_bom(self, scope, cabinet=False, line_commands=None):
        if self.sab_bom_cabinet_first:
            if scope == 'total':
                raise ValidationError(_('Die Gesamtstückliste wird aus ausgewählten freigegebenen Einzelstücklisten erstellt.'))
            if scope == 'cabinet' and cabinet:
                old = self.env['sab.project.bom'].search([
                    ('order_id', '=', self.id), ('bom_scope', '=', 'cabinet'),
                    ('cabinet_line_id', '=', cabinet.id)], limit=1)
                if old:
                    return old
        return super()._sab_prepare_or_update_bom(scope, cabinet, line_commands)

    def action_open_procurement_package_wizard(self):
        self.ensure_one()
        if not self.sab_bom_cabinet_first:
            return super().action_open_procurement_package_wizard()
        return self.env['sab.project.bom']._sab_selection_action(self)


class BomCabinetFirst(models.Model):
    _inherit = 'sab.project.bom'

    sab_cabinet_first = fields.Boolean(readonly=True, copy=False, default=False)
    sab_technical_released_at = fields.Datetime(string='Technisch freigegeben am', readonly=True, copy=False)
    sab_technical_released_by_id = fields.Many2one('res.users', string='Technisch freigegeben von', readonly=True, copy=False)
    sab_handover_package_id = fields.Many2one('sab.project.bom', string='Enthalten in Gesamtstückliste',
                                              readonly=True, copy=False, ondelete='restrict', index=True)
    sab_engineering_status = fields.Selection([
        ('editing', 'In technischer Bearbeitung'), ('ready', 'Zur Bestellung freigegeben'),
        ('combined', 'In Gesamtstückliste enthalten'), ('handed_over', 'An Einkauf übergeben'),
        ('legacy', 'Altbestand / bisheriger Ablauf')], compute='_compute_engineering_status',
        string='Bearbeitungsstand')
    sab_material_summary = fields.Html(string='Material gesamt', compute='_compute_material_summary', sanitize=True)

    @api.depends('bom_scope', 'state', 'order_id.sab_bom_cabinet_first', 'sab_cabinet_first',
                 'purchase_release_state', 'sab_handover_package_id',
                 'sab_handover_package_id.purchase_release_state')
    def _compute_engineering_status(self):
        for bom in self:
            if bom.bom_scope == 'cabinet':
                package = bom.sab_handover_package_id
                bom.sab_engineering_status = ('handed_over' if package.purchase_release_state == 'released'
                    else 'combined' if package else 'ready' if bom.state == 'released' else 'editing')
            elif bom.bom_scope == 'procurement':
                bom.sab_engineering_status = 'handed_over' if bom.purchase_release_state == 'released' else 'combined'
            else:
                bom.sab_engineering_status = 'legacy'

    @api.depends('line_ids.product_id', 'line_ids.odoo_product_id', 'line_ids.quantity',
                 'line_ids.unit', 'line_ids.optional')
    def _compute_material_summary(self):
        for bom in self:
            buckets = {}
            for line in bom.line_ids:
                product = line.odoo_product_id or line.product_id.odoo_product_id or line.product_id
                key = (product._name, product.id, line.unit, line.optional)
                if key not in buckets:
                    buckets[key] = [product.display_name, line.unit, line.optional, 0.0]
                buckets[key][3] += line.quantity
            rows = [Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td class="text-end">%s</td></tr>') %
                    (label, unit, _('Optional') if optional else '', '%g' % qty)
                    for label, unit, optional, qty in buckets.values()]
            bom.sab_material_summary = (Markup('<table class="table table-sm"><thead><tr><th>Produkt</th>'
                '<th>Einheit</th><th>Optional</th><th>Menge gesamt</th></tr></thead><tbody>')
                + Markup('').join(rows) + Markup('</tbody></table>')) if rows else False

    def _sab_lock_technical_boms(self):
        managed = self.filtered(lambda b: b.order_id.sab_bom_cabinet_first)
        if managed:
            managed.check_access('write')
            managed.mapped('order_id')._sab_lock_bom_order()
            self.env.cr.execute('SELECT id FROM sab_project_bom WHERE id IN %s ORDER BY id FOR UPDATE',
                                [tuple(sorted(managed.ids))])
            managed.invalidate_recordset(['state', 'sab_handover_package_id'])
        return True

    def _sab_internal_write(self, values):
        token = _FLOW_WRITE.set(True)
        try:
            return self.write(values)
        finally:
            _FLOW_WRITE.reset(token)

    def _sab_released_bom_allowed_fields(self):
        return super()._sab_released_bom_allowed_fields() | _META

    def _sab_check_technical_content(self):
        for bom in self:
            if not bom.line_ids:
                raise ValidationError(_('Eine leere Einzelstückliste kann nicht freigegeben werden.'))
            for row in bom.line_ids:
                if not _positive(row.quantity):
                    raise ValidationError(_('Vor Freigabe müssen alle Mengen endlich und größer als null sein.'))
                if not (row.product_id or row.odoo_product_id):
                    raise ValidationError(_('Jede Stücklistenposition benötigt ein Produkt.'))

    @api.model_create_multi
    def create(self, vals_list):
        if not _FLOW_WRITE.get() and any(_META.intersection(v) for v in vals_list):
            raise ValidationError(_('Technische Freigabedaten werden nur durch den Stücklistenablauf gesetzt.'))
        if not _FLOW_RELEASE.get():
            for vals in vals_list:
                order = self.env['sale.order'].browse(vals.get('order_id')).exists()
                if order.sab_bom_cabinet_first and vals.get('state') == 'released':
                    raise ValidationError(_('Bitte die Stückliste über den technischen Freigabeknopf freigeben.'))
        return super().create(vals_list)

    def write(self, vals):
        if _META.intersection(vals) and not _FLOW_WRITE.get():
            raise ValidationError(_('Freigabe- und Übergabedaten dürfen nicht manuell geändert werden.'))
        if vals.get('state') == 'released':
            pending = self.filtered(lambda b: b.order_id.sab_bom_cabinet_first and b.state != 'released')
            if pending and not _FLOW_RELEASE.get():
                raise ValidationError(_('Bitte die Stückliste über den technischen Freigabeknopf freigeben.'))
            self.filtered(lambda b: b.bom_scope == 'cabinet' and b.order_id.sab_bom_cabinet_first)._sab_check_technical_content()
            # In the new workflow, even a historic total is not a shortcut for
            # silently approving cabinet lists that nobody has checked.
            for total in self.filtered(lambda b: b.bom_scope == 'total' and b.order_id.sab_bom_cabinet_first):
                if total.order_id.sab_bom_ids.filtered(lambda b: b.bom_scope == 'cabinet' and b.state != 'released'):
                    raise ValidationError(_('Bitte jede Einzelstückliste separat technisch freigeben.'))
        if {'bom_scope', 'cabinet_line_id', 'order_id', 'project_id'}.intersection(vals):
            for bom in self.filtered(lambda b: b.sab_cabinet_first or b.order_id.sab_bom_cabinet_first):
                for key in ('cabinet_line_id', 'order_id', 'project_id'):
                    if key in vals and (vals[key] or False) != (bom[key].id or False):
                        raise ValidationError(_('Eine technische Einzelstückliste darf nicht einem anderen Schrank zugeordnet werden.'))
                if 'bom_scope' in vals and vals['bom_scope'] != bom.bom_scope:
                    raise ValidationError(_('Die Stücklistenart darf in diesem Ablauf nicht geändert werden.'))
        return super().write(vals)

    def action_release(self):
        self.check_access('write')
        self.mapped('order_id')._sab_lock_bom_order()
        self._sab_lock_technical_boms()
        # Pre-validate the whole batch before any release can run.
        cabinets = self.filtered(lambda b: b.bom_scope == 'cabinet' and b.state != 'released')
        cabinets.filtered(lambda b: b.order_id.sab_bom_cabinet_first)._sab_check_technical_content()
        for total in self.filtered(lambda b: b.bom_scope == 'total' and b.order_id.sab_bom_cabinet_first):
            if total.order_id.sab_bom_ids.filtered(lambda b: b.bom_scope == 'cabinet' and b.state != 'released'):
                raise ValidationError(_('Eine Gesamtfreigabe ersetzt nicht die technische Einzelprüfung.'))
        token = _FLOW_RELEASE.set(True)
        try:
            result = super().action_release()
        finally:
            _FLOW_RELEASE.reset(token)
        if cabinets:
            cabinets._sab_internal_write({'sab_technical_released_at': fields.Datetime.now(),
                                           'sab_technical_released_by_id': self.env.user.id})
            for bom in cabinets:
                bom.message_post(body=_('Einzelstückliste technisch geprüft und zur Bestellung freigegeben.'))
        return result

    def action_combine_released_cabinets(self):
        if not self:
            raise ValidationError(_('Bitte die freigegebenen Einzelstücklisten markieren.'))
        orders = self.mapped('order_id')
        if len(orders) != 1:
            raise ValidationError(_('Bitte nur Einzelstücklisten desselben Auftrags auswählen.'))
        self._sab_validate_selection(orders)
        return self._sab_selection_action(orders, selected=self)

    @api.model
    def _sab_selection_action(self, order, selected=None):
        if not (self.env.is_superuser() or self.env.user.has_group('project.group_project_manager')
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Nur Projektleitung oder Administration darf die Einkaufszusammenfassung erstellen.'))
        return {'type': 'ir.actions.act_window', 'name': _('Freigegebene Einzelstücklisten zusammenfassen'),
                'res_model': 'sab.procurement.package.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'default_order_id': order.id, 'default_sab_cabinet_first': True,
                            'default_cabinet_bom_ids': [Command.set(selected.ids if selected else [])]}}

    def _sab_validate_selection(self, order):
        self.check_access('read')
        if not self:
            raise ValidationError(_('Bitte mindestens eine freigegebene Einzelstückliste auswählen.'))
        if self.filtered(lambda b: b.bom_scope != 'cabinet' or b.state != 'released'
                         or b.order_id != order or b.project_id != order.sab_project_id):
            raise ValidationError(_('Nur technisch freigegebene Einzelstücklisten desselben Auftrags sind zulässig.'))
        self._sab_check_technical_content()
        existing = self.env['sab.project.bom'].search([
            ('bom_scope', '=', 'procurement'), ('source_cabinet_bom_ids', 'in', self.ids)])
        if existing or self.filtered('sab_handover_package_id'):
            raise ValidationError(_('Mindestens ein ausgewählter Schrank ist bereits in einer Gesamtstückliste enthalten. Keine doppelte Bestellung.'))

    def action_open_procurement_package_from_bom(self):
        self.ensure_one()
        if self.bom_scope == 'cabinet':
            return self.action_combine_released_cabinets()
        if self.order_id.sab_bom_cabinet_first and self.bom_scope == 'total':
            return self._sab_selection_action(self.order_id)
        return super().action_open_procurement_package_from_bom()

    def _sab_push_to_procurement_workspace(self):
        # The old release chain pushes every procurement package immediately.
        # New summaries wait for explicit handover; old packages stay unchanged.
        eligible = self.filtered(lambda b: not b.sab_cabinet_first
                                 or b.purchase_release_state == 'released')
        if not eligible:
            return True
        return super(BomCabinetFirst, eligible)._sab_push_to_procurement_workspace()

    def action_open_procurement_workspace(self):
        self.ensure_one()
        if self.sab_cabinet_first and self.purchase_release_state != 'released':
            raise ValidationError(_('Bitte die Gesamtstückliste zuerst ausdrücklich an den Einkauf freigeben.'))
        return super().action_open_procurement_workspace()

    def action_release_for_purchase(self):
        self.ensure_one()
        if self.bom_scope == 'total' and self.order_id.sab_bom_cabinet_first:
            raise ValidationError(_('Bitte zuerst ausgewählte freigegebene Einzelstücklisten zu einer Gesamtstückliste für den Einkauf zusammenfassen.'))
        if self.sab_cabinet_first and self.bom_scope == 'procurement':
            if self.source_cabinet_bom_ids.filtered(lambda b: b.state != 'released'):
                raise ValidationError(_('Alle enthaltenen Einzelstücklisten müssen technisch freigegeben sein.'))
        return super().action_release_for_purchase()

    def action_generate_purchase_requirements(self):
        if self.filtered(lambda b: b.bom_scope == 'total' and b.order_id.sab_bom_cabinet_first):
            raise ValidationError(_('Einkaufsbedarf entsteht in diesem Ablauf nur aus der ausgewählten Einkaufs-Gesamtstückliste.'))
        return super().action_generate_purchase_requirements()


class CabinetFirstPackageWizard(models.TransientModel):
    _inherit = 'sab.procurement.package.wizard'

    sab_cabinet_first = fields.Boolean(default=False, readonly=True)

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        order = self.env['sale.order'].browse(result.get('order_id')).exists()
        if self.env.context.get('default_sab_cabinet_first') or order.sab_bom_cabinet_first:
            result.update(sab_cabinet_first=True, require_individual_cabinet_release=True)
            # Respect explicit marked rows; never silently add other green lists.
            result['cabinet_bom_ids'] = self.env.context.get('default_cabinet_bom_ids', [Command.clear()])
        return result

    def action_create_procurement_package(self):
        self.ensure_one()
        if not (self.sab_cabinet_first or self.order_id.sab_bom_cabinet_first):
            return super().action_create_procurement_package()
        order = self.order_id
        self.env['sab.project.bom']._sab_selection_action(order)  # role check
        if order.state not in ('sale', 'done') or order.sab_calculation_source != 'schematic':
            raise ValidationError(_('Die Einkaufszusammenfassung benötigt einen bestätigten Schaltplan-Auftrag.'))
        cabinets = self.cabinet_bom_ids.sorted('id')
        order._sab_lock_bom_order()
        cabinets.check_access('write')
        if cabinets:
            self.env.cr.execute('SELECT id FROM sab_project_bom WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(cabinets.ids)])
            cabinets.invalidate_recordset(['state', 'sab_handover_package_id'])
        cabinets._sab_validate_selection(order)
        with self.env.cr.savepoint():
            order._sab_activate_cabinet_first()
            reference = self.env['ir.sequence'].next_by_code('sab.procurement.request')
            if not reference:
                raise ValidationError(_('Die Materialanforderungsnummer konnte nicht erzeugt werden.'))
            values = []
            for cabinet in cabinets:
                for line in cabinet.line_ids.sorted(key=lambda r: (r.sequence, r.id)):
                    values.append(Command.create({
                        'sequence': (len(values) + 1) * 10,
                        'product_id': line.product_id.id or False,
                        'odoo_product_id': line.odoo_product_id.id or False,
                        'quantity': line.quantity, 'unit': line.unit, 'optional': line.optional,
                        'supplier_product_id': line.supplier_product_id.id or False,
                        'unit_purchase_price': line.unit_purchase_price, 'note': line.note,
                        'source_cabinet_bom_id': cabinet.id, 'source_cabinet_line_id': line.id,
                    }))
            token = _FLOW_WRITE.set(True)
            try:
                package = self.env['sab.project.bom'].create({
                    'name': '%s / GESAMT – %s' % (reference, ', '.join(cabinets.mapped('name'))),
                    'procurement_reference': reference, 'order_id': order.id,
                    'project_id': order.sab_project_id.id, 'bom_scope': 'procurement',
                    'sab_cabinet_first': True, 'source_cabinet_bom_ids': [Command.set(cabinets.ids)],
                    'line_ids': values, 'note': self.note,
                })
                # Source-row update also provides concurrency conflict detection
                # under repeatable-read; no two sessions can claim one cabinet.
                cabinets.write({'sab_handover_package_id': package.id})
            finally:
                _FLOW_WRITE.reset(token)
            package.action_release()
        return {'type': 'ir.actions.act_window', 'name': _('Gesamtstückliste für Einkauf'),
                'res_model': 'sab.project.bom', 'res_id': package.id,
                'view_mode': 'form', 'target': 'current'}


class TechnicalBomLine(models.Model):
    _inherit = 'sab.project.bom.line'

    def _sab_new_product_values(self, values):
        """Keep native/legacy identities consistent when engineering swaps parts."""
        vals = dict(values)
        if vals.get('product_id'):
            product = self.env['sab.product'].browse(vals['product_id']).exists()
            vals['odoo_product_id'] = product.odoo_product_id.id or False
            vals.setdefault('unit_purchase_price', product.calculated_purchase_price)
            vals.setdefault('supplier_product_id', False)
        elif vals.get('odoo_product_id'):
            product = self.env['product.product'].browse(vals['odoo_product_id']).exists()
            vals['product_id'] = False
            vals.setdefault('unit_purchase_price', product.standard_price)
            vals.setdefault('supplier_product_id', False)
        return vals

    @api.onchange('product_id')
    def _onchange_technical_legacy_product(self):
        if self.bom_id.bom_scope == 'cabinet' and self.bom_id.order_id.sab_bom_cabinet_first and self.product_id:
            self.update(self._sab_new_product_values({'product_id': self.product_id.id}))

    @api.onchange('odoo_product_id')
    def _onchange_technical_native_product(self):
        if (self.bom_id.bom_scope == 'cabinet' and self.bom_id.order_id.sab_bom_cabinet_first
                and self.odoo_product_id and self.product_id.odoo_product_id != self.odoo_product_id):
            self.update(self._sab_new_product_values({'odoo_product_id': self.odoo_product_id.id}))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        self.env['sab.project.bom'].browse([v['bom_id'] for v in vals_list if v.get('bom_id')])._sab_lock_technical_boms()
        for vals in vals_list:
            bom = self.env['sab.project.bom'].browse(vals.get('bom_id')).exists()
            if bom.bom_scope == 'cabinet' and bom.order_id.sab_bom_cabinet_first:
                vals = self._sab_new_product_values(vals)
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        target = self.env['sab.project.bom'].browse(vals.get('bom_id')).exists() if 'bom_id' in vals else self.env['sab.project.bom']
        (self.mapped('bom_id') | target)._sab_lock_technical_boms()
        if target.state == 'released':
            raise ValidationError(_('Positionen dürfen nicht in eine freigegebene Stückliste verschoben werden.'))
        if {'product_id', 'odoo_product_id'}.intersection(vals):
            for line in self:
                current = dict(vals)
                if line.bom_id.bom_scope == 'cabinet' and line.bom_id.order_id.sab_bom_cabinet_first:
                    old_sab, old_native = line.product_id.id, line.odoo_product_id.id
                    if ('odoo_product_id' in vals and vals['odoo_product_id'] != old_native
                            and not vals.get('product_id')):
                        current['product_id'] = False
                    if ('product_id' in current and current['product_id'] != old_sab
                            or 'odoo_product_id' in current and current['odoo_product_id'] != old_native):
                        current = line._sab_new_product_values(current)
                super(TechnicalBomLine, line).write(current)
            return True
        return super().write(vals)

    def unlink(self):
        self.mapped('bom_id')._sab_lock_technical_boms()
        return super().unlink()
