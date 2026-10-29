"""Material-only baseline, grouped purchasing UI and controlled source revisions.

Released BOMs remain locked through their public CRUD methods. The explicit
purchasing wizard alone may apply validated allocation changes atomically.
No sales, LV price binding, or calculation-master record is written here.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import math

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command

from .sab_project_bom import SabProjectBomLine
from .sab_material_logic import aggregate, comparison, fingerprint, totals, validate_change

_SERVICE = ContextVar('sab_material_control_service', default=False)
_PROTECTED = {'sab_material_baseline', 'sab_material_baseline_known',
              'sab_material_recheck', 'sab_material_release_ek', 'sab_material_release_known',
              'sab_material_revision', 'sab_material_reviewed_by_id', 'sab_material_reviewed_at',
              'sab_material_handover_ek', 'sab_material_handover_known', 'sab_material_handover_at'}


@contextmanager
def _service():
    token = _SERVICE.set(True)
    try:
        yield
    finally:
        _SERVICE.reset(token)


def _purchaser(env):
    if not (env.is_superuser() or env.user.has_group('base.group_system')
            or env.user.has_group('sab_project.group_sab_purchasing')):
        raise AccessError(_('Materialänderungen im Einkauf sind Einkauf oder Administration vorbehalten.'))


def _engineer(env):
    if not (env.is_superuser() or env.user.has_group('base.group_system')
            or env.user.has_group('project.group_project_manager')):
        raise AccessError(_('Die technische Freigabe benötigt Projektleitungsrechte.'))


def _window(model, record, title):
    return {'type': 'ir.actions.act_window', 'res_model': model, 'res_id': record.id,
            'view_mode': 'form', 'target': 'new', 'name': title}


class MaterialBomGeneration(models.Model):
    _inherit = 'sale.order'

    def _sab_bom_values_for_lines(self, calculation_lines):
        self.ensure_one()
        if not self.sab_bom_cabinet_first:
            return super()._sab_bom_values_for_lines(calculation_lines)
        # Delegate material inclusion, fixed quantities and snapshot valuation
        # to the existing generator, but do not merge different LV origins away.
        commands = []
        for calc in calculation_lines.filtered(lambda r: r.line_type == 'item'):
            for operation, record_id, original in super()._sab_bom_values_for_lines(calc):
                if operation != 0:
                    raise ValidationError(_('Unerwartete Stücklistenoperation beim Materialaufbau.'))
                values = dict(original)
                values.update(sequence=(len(commands) + 1) * 10,
                    sab_lv_position=(calc.parent_section_id.lv_position or calc.lv_position or '').strip(),
                    sab_source_calculation_line_id=calc.id)
                commands.append(Command.create(values))
        return commands


class MaterialBom(models.Model):
    _inherit = 'sab.project.bom'

    sab_material_baseline = fields.Json(string='Ursprüngliche Materialkalkulation', readonly=True, copy=False)
    sab_material_baseline_known = fields.Boolean(readonly=True, copy=False)
    sab_material_currency_id = fields.Many2one(related='order_id.company_id.currency_id', readonly=True)
    sab_material_calculated_ek = fields.Monetary(string='Kalkulierter Material-EK',
        currency_field='sab_material_currency_id', compute='_compute_material_ek')
    sab_material_current_ek = fields.Monetary(string='Aktueller Material-EK',
        currency_field='sab_material_currency_id', compute='_compute_material_ek')
    sab_material_optional_ek = fields.Monetary(string='Optionaler Material-EK (separat)',
        currency_field='sab_material_currency_id', compute='_compute_material_ek')
    sab_material_delta = fields.Monetary(string='Abweichung Material-EK',
        currency_field='sab_material_currency_id', compute='_compute_material_ek')
    sab_material_delta_percent = fields.Float(string='Abweichung (%)', compute='_compute_material_ek', digits=(16, 2))
    sab_material_percent_known = fields.Boolean(compute='_compute_material_ek')
    sab_material_comparison_known = fields.Boolean(compute='_compute_material_ek')
    sab_material_zero_price_count = fields.Integer(string='Positionen mit EK 0,00', compute='_compute_material_ek')
    sab_material_release_ek = fields.Monetary(string='Material-EK letzte technische Freigabe',
        currency_field='sab_material_currency_id', readonly=True, copy=False)
    sab_material_release_known = fields.Boolean(readonly=True, copy=False)
    sab_material_handover_ek = fields.Monetary(string='Material-EK bei erster Einkaufsfreigabe',
        currency_field='sab_material_currency_id', readonly=True, copy=False)
    sab_material_handover_known = fields.Boolean(readonly=True, copy=False)
    sab_material_handover_at = fields.Datetime(string='Erste Einkaufsfreigabe', readonly=True, copy=False)
    sab_material_revision = fields.Integer(string='Materialrevision', readonly=True, copy=False)
    sab_material_reviewed_by_id = fields.Many2one('res.users', string='Materialprüfung durch', readonly=True, copy=False)
    sab_material_reviewed_at = fields.Datetime(string='Materialprüfung am', readonly=True, copy=False)
    sab_material_recheck = fields.Boolean(string='Einkaufsänderung technisch prüfen', readonly=True, copy=False)
    sab_material_recheck_required = fields.Boolean(compute='_compute_material_ek', string='Technische Prüfung offen')
    sab_material_group_ids = fields.One2many('sab.bom.material.group', 'bom_id', string='Gesamtmaterial nach Artikel', readonly=True)
    sab_material_change_ids = fields.One2many('sab.bom.material.change', 'bom_id', string='Materialänderungsprotokoll', readonly=True)
    sab_engineering_status = fields.Selection(selection_add=[('recheck', 'Einkaufsänderung – technische Prüfung offen')])

    def _sab_material_rows(self):
        self.ensure_one()
        return [line._sab_material_row() for line in self.line_ids.sorted('id')]

    def _sab_material_baseline_rows(self):
        self.ensure_one()
        if self.bom_scope == 'procurement' and self.sab_cabinet_first:
            cabinets = self.source_cabinet_bom_ids
            return (all(c.sab_material_baseline_known for c in cabinets) and bool(cabinets),
                    [r for c in cabinets for r in (c.sab_material_baseline or [])])
        return self.sab_material_baseline_known, self.sab_material_baseline or []

    @api.depends('line_ids.quantity', 'line_ids.unit_purchase_price', 'line_ids.optional',
        'line_ids.sab_material_removed', 'sab_material_baseline', 'sab_material_baseline_known',
        'source_cabinet_bom_ids.sab_material_baseline', 'source_cabinet_bom_ids.sab_material_baseline_known',
        'sab_material_recheck', 'source_cabinet_bom_ids.sab_material_recheck')
    def _compute_material_ek(self):
        for bom in self:
            known, baseline = bom._sab_material_baseline_rows()
            data = comparison(baseline, bom._sab_material_rows(), known)
            bom.sab_material_calculated_ek = data['base'] or 0.0
            bom.sab_material_current_ek = data['current']
            bom.sab_material_optional_ek = data['optional']
            bom.sab_material_delta = data['delta'] or 0.0
            bom.sab_material_delta_percent = data['percent'] or 0.0
            bom.sab_material_percent_known = data['percent'] is not None
            bom.sab_material_comparison_known = known
            bom.sab_material_zero_price_count = data['zero_prices']
            bom.sab_material_recheck_required = bom.sab_material_recheck or any(
                bom.source_cabinet_bom_ids.mapped('sab_material_recheck'))

    @api.depends('bom_scope', 'state', 'order_id.sab_bom_cabinet_first', 'sab_cabinet_first',
        'purchase_release_state', 'sab_handover_package_id', 'sab_handover_package_id.purchase_release_state',
        'sab_material_recheck', 'source_cabinet_bom_ids.sab_material_recheck')
    def _compute_engineering_status(self):
        super()._compute_engineering_status()
        for bom in self:
            if bom.sab_material_recheck_required:
                bom.sab_engineering_status = 'recheck'

    def _sab_material_metadata(self, values):
        if set(values) - _PROTECTED:
            raise ValidationError(_('Unzulässiges internes Materialfeld.'))
        with _service():
            return self.write(values)

    def _sab_released_bom_allowed_fields(self):
        return super()._sab_released_bom_allowed_fields() | _PROTECTED

    @api.model_create_multi
    def create(self, vals_list):
        if not _SERVICE.get() and any(_PROTECTED.intersection(v) for v in vals_list):
            raise ValidationError(_('Die Materialbasis und Prüfdaten werden ausschließlich vom Ablauf gespeichert.'))
        records = super().create(vals_list)
        for bom, vals in zip(records, vals_list):
            if bom.bom_scope == 'cabinet' and vals.get('sab_cabinet_first') and vals.get('line_ids'):
                # Capture after all generation hooks, once only, before engineering edits.
                bom._sab_material_metadata({'sab_material_baseline': bom._sab_material_rows(),
                                            'sab_material_baseline_known': True})
        return records

    def write(self, vals):
        if _PROTECTED.intersection(vals) and not _SERVICE.get():
            raise ValidationError(_('Kalkulationsbasis und Materialfreigaben sind nicht manuell überschreibbar.'))
        return super().write(vals)

    def _sab_check_technical_content(self):
        managed = self.filtered(lambda b: b.order_id.sab_bom_cabinet_first)
        for bom in managed:
            lines = bom.line_ids.filtered(lambda l: not l.sab_material_removed)
            if not lines:
                raise ValidationError(_('Eine leere technische Stückliste kann nicht freigegeben werden.'))
            for line in lines:
                line._sab_validate_material_values()
        if self - managed:
            return super(MaterialBom, self - managed)._sab_check_technical_content()
        return True

    def _sab_assert_material_ready(self):
        if self.filtered('sab_material_recheck_required'):
            raise ValidationError(_('Einkaufsänderungen müssen zuerst technisch geprüft werden. Bitte die betroffenen Einzelstücklisten freigeben.'))
        return True

    def _sab_validate_selection(self, order):
        self._sab_assert_material_ready()
        return super()._sab_validate_selection(order)

    def action_review_purchase_costs(self):
        self.ensure_one()
        self.check_access('write')
        if not (self.env.is_superuser() or self.env.user.has_group('base.group_system')
                or self.env.user.has_group('sab_project.group_sab_purchase_approver')):
            raise AccessError(_('Die Einkaufsfreigabe benötigt Bestellfreigaberechte.'))
        wizard = self.env['sab.bom.material.review'].create({'bom_id': self.id, 'release_kind': 'purchase'})
        return _window(wizard._name, wizard, _('Material-EK vor Einkaufsfreigabe vergleichen'))

    def action_review_material_costs(self):
        self.ensure_one()
        _engineer(self.env)
        self.check_access('write')
        wizard = self.env['sab.bom.material.review'].create({'bom_id': self.id})
        return _window(wizard._name, wizard, _('Material-EK vor Freigabe vergleichen'))

    def action_release(self):
        result = super().action_release()
        for bom in self.filtered(lambda b: b.bom_scope == 'cabinet' and b.order_id.sab_bom_cabinet_first):
            bom._sab_material_metadata({'sab_material_release_ek': bom.sab_material_current_ek,
                'sab_material_release_known': True, 'sab_material_recheck': False,
                'sab_material_reviewed_by_id': self.env.user.id,
                'sab_material_reviewed_at': fields.Datetime.now()})
            if bom.sab_handover_package_id:
                bom.sab_handover_package_id._sab_push_to_procurement_workspace()
        return result

    def action_create_production_order(self):
        self._sab_assert_material_ready()
        return super().action_create_production_order()

    def action_release_for_purchase(self):
        self.mapped('order_id')._sab_lock_bom_order()
        self._sab_assert_material_ready()
        result = super().action_release_for_purchase()
        for bom in self.filtered(lambda b: b.sab_cabinet_first and not b.sab_material_handover_known):
            bom._sab_material_metadata({'sab_material_handover_ek': bom.sab_material_current_ek,
                'sab_material_handover_known': True, 'sab_material_handover_at': fields.Datetime.now()})
        return result

    def _sab_push_to_procurement_workspace(self):
        ready = self.filtered(lambda b: not b.sab_material_recheck_required)
        return super(MaterialBom, ready)._sab_push_to_procurement_workspace() if ready else True

    def action_generate_purchase_requirements(self):
        self.ensure_one()
        if not (self.sab_cabinet_first and self.bom_scope == 'procurement'):
            return super().action_generate_purchase_requirements()
        self._sab_assert_material_ready()
        if self.state != 'released':
            raise ValidationError(_('Die Gesamtstückliste muss technisch freigegeben sein.'))
        # Preserve existing access checks. This method never elevates permissions.
        if not self.env.context.get('sab_procurement_release'):
            self._sab_check_project_manager()
        Requirement = self.env['sab.purchase.requirement']
        existing = self.purchase_requirement_ids.mapped('bom_line_id')
        for line in self.line_ids.filtered(lambda l: not l.optional and not l.sab_material_removed):
            if line not in existing:
                Requirement.create({'bom_line_id': line.id})
        return {'type': 'ir.actions.act_window', 'name': _('Materialanforderung'),
                'res_model': 'sab.purchase.requirement', 'view_mode': 'list,form',
                'domain': [('bom_id', '=', self.id), ('state', '!=', 'cancel')]}

    def _sab_sync_material_groups(self):
        Group = self.env['sab.bom.material.group'].sudo()
        for bom in self.filtered(lambda b: b.bom_scope == 'procurement' and b.sab_cabinet_first):
            known = {g.material_key: g for g in Group.with_context(active_test=False).search([('bom_id', '=', bom.id)])}
            with _service():
                for bucket in aggregate(bom._sab_material_rows()):
                    values = {'bom_id': bom.id, 'material_key': bucket['key'], 'active': True,
                              'line_ids': [Command.set(bucket['line_ids'])]}
                    old = known.pop(bucket['key'], None)
                    if old:
                        old.sudo().write(values)
                    else:
                        Group.create(values)
                for old in known.values():
                    old.sudo().write({'active': False, 'line_ids': [Command.clear()]})
        return True

    def action_open_material_groups(self):
        self.ensure_one()
        self.check_access('read')
        if not (self.sab_cabinet_first and self.bom_scope == 'procurement'):
            raise ValidationError(_('Diese Artikelübersicht benötigt die neue Einkaufs-Gesamtstückliste.'))
        self._sab_sync_material_groups()
        return {'type': 'ir.actions.act_window', 'name': _('Gesamtstückliste – ein Artikel je Zeile'),
                'res_model': 'sab.bom.material.group', 'view_mode': 'list',
                'domain': [('bom_id', '=', self.id)], 'target': 'current'}

    def action_open_procurement_workspace(self):
        action = super().action_open_procurement_workspace()
        if self.sab_cabinet_first and self.bom_scope == 'procurement':
            return self.action_open_material_groups()
        return action

    def _sab_check_changeable_material(self, lines):
        """Do not rewrite supplier orders, stock postings or production history."""
        self.ensure_one()
        if not (self.bom_scope == 'procurement' and self.sab_cabinet_first and self.state == 'released'):
            raise ValidationError(_('Nur eine freigegebene Einkaufs-Gesamtstückliste des neuen Ablaufs kann bearbeitet werden.'))
        if lines - self.line_ids:
            raise ValidationError(_('Fremde Materialposition.'))
        cabinets = lines.mapped('source_cabinet_bom_id')
        if cabinets.filtered(lambda c: c.production_order_ids):
            raise ValidationError(_('Für einen betroffenen Schrank besteht bereits ein Fertigungsauftrag. Bitte eine abgestimmte technische Revision durchführen.'))
        Requirement = self.env['sab.purchase.requirement'].sudo()
        reqs = Requirement.search([('bom_line_id', 'in', lines.ids)])
        if reqs.filtered(lambda r: r.state not in ('open', 'cancel')
                or r.purchase_order_line_id or r.odoo_purchase_line_id):
            raise ValidationError(_('Für diese Position besteht bereits eine Bestellung. Erst Bestelländerung/Storno klären; historische Mengen werden nicht überschrieben.'))
        if reqs.stock_movement_ids.filtered(lambda m: m.movement_type not in ('reserve', 'release')):
            raise ValidationError(_('Material wurde bereits gebucht oder kommissioniert. Eine rückwirkende Stücklistenänderung ist gesperrt.'))
        if reqs and self.env['stock.move'].sudo().search_count([
                ('sab_purchase_requirement_id', 'in', reqs.ids), ('state', '!=', 'cancel')]):
            raise ValidationError(_('Es bestehen Lagerbewegungen für diese Position. Bitte zuerst den Lagerablauf klären.'))
        return reqs


class MaterialBomLine(models.Model):
    _inherit = 'sab.project.bom.line'

    sab_lv_position = fields.Char(string='LV / NTG (optional)', copy=True)
    sab_source_calculation_line_id = fields.Many2one('sab.offer.calculation.line',
        string='Ursprüngliche Kalkulationsposition', readonly=True, copy=True, ondelete='restrict')
    sab_material_removed = fields.Boolean(string='Durch Revision entfallen', readonly=True, copy=False)
    sab_cabinet_label = fields.Char(string='Verteiler / Schrank', compute='_compute_material_cabinet')

    @api.depends('bom_id.cabinet_line_id.description', 'source_cabinet_bom_id.cabinet_line_id.description')
    def _compute_material_cabinet(self):
        for line in self:
            cabinet = line.bom_id if line.bom_id.bom_scope == 'cabinet' else line.source_cabinet_bom_id
            line.sab_cabinet_label = cabinet.cabinet_line_id.description or cabinet.name or ''

    def _sab_material_row(self):
        self.ensure_one()
        native = self.odoo_product_id or self.product_id.odoo_product_id
        cabinet = self.bom_id if self.bom_id.bom_scope == 'cabinet' else self.source_cabinet_bom_id
        return {'id': self.id, 'product_id': self.product_id.id or False,
            'odoo_product_id': native.id or False, 'product': (native or self.product_id).display_name,
            'quantity': self.quantity, 'unit': self.unit, 'optional': self.optional,
            'unit_purchase_price': self.unit_purchase_price, 'removed': self.sab_material_removed,
            'cabinet_id': cabinet.id or False, 'cabinet': self.sab_cabinet_label,
            'lv': self.sab_lv_position or '', 'supplier_product_id': self.supplier_product_id.id or False,
            'source_id': self.source_cabinet_line_id.id or False,
            'note': self.note or '', 'write_date': str(self.write_date or '')}

    def _sab_validate_material_values(self):
        for line in self:
            product = line.odoo_product_id or line.product_id.odoo_product_id
            if not (product or line.product_id) or (product and (product.sab_is_montage_time or product.type == 'service')):
                raise ValidationError(_('Eine normale Materialposition benötigt ein Materialprodukt, kein Montagezeitprodukt.'))
            if not math.isfinite(line.quantity) or line.quantity <= 0:
                raise ValidationError(_('Materialmengen müssen endlich und größer null sein.'))
            if not math.isfinite(line.unit_purchase_price) or line.unit_purchase_price < 0:
                raise ValidationError(_('Material-Einkaufspreise müssen endlich und nicht negativ sein.'))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            if vals.get('sab_material_removed') and not _SERVICE.get():
                raise ValidationError(_('Entfallene Positionen werden nur über den Änderungsdialog gekennzeichnet.'))
            if vals.get('source_cabinet_line_id'):
                source = self.browse(vals['source_cabinet_line_id']).exists()
                vals['sab_lv_position'] = source.sab_lv_position or False
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if 'sab_material_removed' in vals and not _SERVICE.get():
            raise ValidationError(_('Bitte Positionen über den Materialänderungsdialog entfernen.'))
        if 'sab_source_calculation_line_id' in vals:
            raise ValidationError(_('Der Kalkulationsursprung darf nicht ausgetauscht werden.'))
        return super().write(vals)

    def _sab_apply_controlled_values(self, values):
        """Only called after role, allocation, history and concurrency validation."""
        if not _SERVICE.get():
            raise AccessError(_('Kein freigegebener Materialänderungsvorgang.'))
        allowed = {'product_id', 'odoo_product_id', 'quantity', 'unit', 'optional',
                   'unit_purchase_price', 'supplier_product_id', 'note', 'sab_material_removed'}
        if set(values) - allowed:
            raise ValidationError(_('Unzulässige Änderung an der Schrankzuordnung.'))
        # Deliberately bypass the original immutable-line CRUD guard only for
        # this explicit, whitelisted revision. ORM ACLs/constraints still run.
        return super(SabProjectBomLine, self).write(values)

    @api.model
    def _sab_create_controlled_values(self, values):
        values = dict(values)
        if values.get('sab_material_removed') is False:
            values.pop('sab_material_removed')
        if not _SERVICE.get():
            raise AccessError(_('Kein Materialänderungsvorgang.'))
        allowed = {'bom_id', 'sequence', 'product_id', 'odoo_product_id', 'quantity', 'unit',
                   'optional', 'unit_purchase_price', 'supplier_product_id', 'note',
                   'source_cabinet_bom_id', 'source_cabinet_line_id', 'sab_lv_position'}
        if set(values) - allowed:
            raise ValidationError(_('Unzulässiges Materialfeld.'))
        return super(SabProjectBomLine, self).create(values)


class MaterialGroup(models.Model):
    _name = 'sab.bom.material.group'
    _description = 'SAB-P Gesamtmaterial mit Schrankaufteilung'
    _order = 'id'

    bom_id = fields.Many2one('sab.project.bom', required=True, readonly=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='bom_id.order_id.company_id', store=True, readonly=True)
    active = fields.Boolean(default=True, readonly=True)
    material_key = fields.Char(required=True, readonly=True, index=True)
    line_ids = fields.Many2many('sab.project.bom.line', 'sab_material_group_line_rel',
        'group_id', 'line_id', readonly=True)
    name = fields.Char(string='Artikel', compute='_compute_values')
    odoo_product_id = fields.Many2one('product.product', string='Produkt', compute='_compute_values')
    quantity = fields.Float(string='Gesamtbedarf', compute='_compute_values', digits=(16, 3))
    unit = fields.Char(string='Einheit', compute='_compute_values')
    optional = fields.Boolean(string='Optional', compute='_compute_values')
    allocation_text = fields.Text(string='Schränke / Teilmengen / LV', compute='_compute_values')
    currency_id = fields.Many2one(related='bom_id.sab_material_currency_id', readonly=True)
    unit_purchase_price = fields.Float(string='EK je Einheit (gewichtet)', digits=(16, 4), compute='_compute_values')
    purchase_total = fields.Monetary(string='EK gesamt', currency_field='currency_id', compute='_compute_values')
    _group_unique = models.Constraint('UNIQUE(bom_id, material_key)', 'Der Artikel ist bereits zusammengefasst.')

    @api.depends('line_ids', 'line_ids.quantity', 'line_ids.unit_purchase_price', 'line_ids.sab_lv_position',
        'line_ids.sab_cabinet_label', 'line_ids.sab_material_removed', 'line_ids.odoo_product_id',
        'line_ids.product_id', 'line_ids.unit', 'line_ids.optional')
    def _compute_values(self):
        for group in self:
            values = aggregate([line._sab_material_row() for line in group.line_ids])
            value = values[0] if values else {}
            native = group.line_ids[:1].odoo_product_id or group.line_ids[:1].product_id.odoo_product_id
            group.odoo_product_id = native
            group.name = (native or group.line_ids[:1].product_id).display_name or ''
            group.quantity = value.get('quantity', 0)
            group.unit_purchase_price = value.get('unit_price', 0)
            group.purchase_total = value.get('cost', 0)
            group.unit = value.get('unit', '')
            group.optional = value.get('optional', False)
            group.allocation_text = value.get('allocation_text', '')

    @api.model_create_multi
    def create(self, vals_list):
        if not _SERVICE.get():
            raise AccessError(_('Artikelzusammenfassungen werden aus den Schrankzuordnungen aufgebaut.'))
        return super().create(vals_list)

    def write(self, vals):
        if not _SERVICE.get():
            raise AccessError(_('Bitte „Zuordnung / Material bearbeiten“ verwenden.'))
        return super().write(vals)

    def unlink(self):
        if not _SERVICE.get():
            raise AccessError(_('Zusammenfassungen dürfen nicht einzeln gelöscht werden.'))
        return super().unlink()

    def action_open_requirement_details(self):
        self.check_access('read')
        if self.mapped('bom_id').filtered(lambda b: b.purchase_release_state != 'released'):
            raise ValidationError(_('Die Gesamtstückliste wurde noch nicht an den Einkauf freigegeben.'))
        return {'type': 'ir.actions.act_window', 'name': _('Schrankbedarf und Bestellstatus'),
                'res_model': 'sab.purchase.requirement', 'view_mode': 'list,form',
                'domain': [('bom_line_id', 'in', self.mapped('line_ids').ids), ('state', '!=', 'cancel')]}

    def action_prepare_purchase(self):
        _purchaser(self.env)
        self.check_access('read')
        if not self:
            raise ValidationError(_('Bitte Artikel für den Bestellvorschlag markieren.'))
        packages = self.mapped('bom_id')
        packages.mapped('order_id')._sab_lock_bom_order()
        packages._sab_assert_material_ready()
        if packages.filtered(lambda b: b.purchase_release_state != 'released'):
            raise ValidationError(_('Die ausgewählten Gesamtstücklisten müssen zuerst an den Einkauf freigegeben werden.'))
        requirements = self.env['sab.purchase.requirement'].search([
            ('bom_line_id', 'in', self.mapped('line_ids').ids), ('state', '=', 'open'), ('optional', '=', False)])
        return requirements.action_create_purchase_orders()

    def action_edit_allocations(self):
        self.ensure_one()
        _purchaser(self.env)
        self.check_access('read')
        self.bom_id.check_access('write')
        self.bom_id._sab_check_changeable_material(self.line_ids)
        wizard = self.env['sab.bom.material.edit'].create({'group_id': self.id})
        return _window(wizard._name, wizard, _('Material und Schrankaufteilung bearbeiten'))


class MaterialPackageWizard(models.TransientModel):
    _inherit = 'sab.procurement.package.wizard'

    def action_create_procurement_package(self):
        action = super().action_create_procurement_package()
        package = self.env['sab.project.bom'].browse(action.get('res_id')).exists()
        if package.sab_cabinet_first:
            package._sab_sync_material_groups()
        return action


class MaterialRequirementGuard(models.Model):
    _inherit = 'sab.purchase.requirement'

    def action_create_purchase_orders(self):
        self.mapped('order_id')._sab_lock_bom_order()
        boms = self.mapped('bom_id')
        (boms | boms.mapped('source_cabinet_bom_ids')).invalidate_recordset(['sab_material_recheck'])
        boms._sab_assert_material_ready()
        return super().action_create_purchase_orders()


class MaterialChange(models.Model):
    _name = 'sab.bom.material.change'
    _description = 'SAB-P unveränderliches Materialänderungsprotokoll'
    _order = 'id desc'
    bom_id = fields.Many2one('sab.project.bom', required=True, ondelete='restrict', readonly=True)
    company_id = fields.Many2one(related='bom_id.order_id.company_id', store=True, readonly=True)
    reason = fields.Text(string='Änderungsgrund', required=True, readonly=True)
    before_values = fields.Json(string='Vorher', readonly=True)
    after_values = fields.Json(string='Nachher', readonly=True)
    changed_by_id = fields.Many2one('res.users', string='Geändert durch', readonly=True, required=True)
    changed_at = fields.Datetime(string='Geändert am', default=fields.Datetime.now, readonly=True)
    cabinet_ids = fields.Many2many('sab.project.bom', string='Betroffene Schränke', readonly=True)
    before_ek = fields.Float(string='Material-EK vorher', readonly=True, digits=(16, 4))
    after_ek = fields.Float(string='Material-EK nachher', readonly=True, digits=(16, 4))

    @api.model_create_multi
    def create(self, vals_list):
        if not _SERVICE.get():
            raise AccessError(_('Änderungsprotokolle werden nur beim Anwenden erzeugt.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_('Ein Materialänderungsprotokoll ist unveränderlich.'))

    def unlink(self):
        raise AccessError(_('Ein Materialänderungsprotokoll darf nicht gelöscht werden.'))
