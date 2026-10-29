"""Explicit cost approval and allocated purchasing revision dialogs."""
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from .sab_bom_material_control import _SERVICE, _service, _purchaser, _engineer
from .sab_material_logic import fingerprint, totals, validate_change, technical_change


class MaterialCostReview(models.TransientModel):
    _name = 'sab.bom.material.review'
    _description = 'Materialkostenvergleich vor technischer Freigabe'
    bom_id = fields.Many2one('sab.project.bom', required=True, readonly=True)
    currency_id = fields.Many2one(related='bom_id.sab_material_currency_id')
    calculated_ek = fields.Monetary(related='bom_id.sab_material_calculated_ek', currency_field='currency_id')
    current_ek = fields.Monetary(related='bom_id.sab_material_current_ek', currency_field='currency_id')
    delta = fields.Monetary(related='bom_id.sab_material_delta', currency_field='currency_id')
    delta_percent = fields.Float(related='bom_id.sab_material_delta_percent')
    comparison_known = fields.Boolean(related='bom_id.sab_material_comparison_known')
    percent_known = fields.Boolean(related='bom_id.sab_material_percent_known')
    zero_price_count = fields.Integer(related='bom_id.sab_material_zero_price_count')
    acknowledge_unknown = fields.Boolean(string='Fehlende/Nullpreise bzw. fehlende Altbasis bewusst geprüft')
    expected_fingerprint = fields.Char(readonly=True)
    release_kind = fields.Selection([('technical', 'Technische Freigabe'), ('purchase', 'Einkaufsfreigabe')], default='technical', required=True, readonly=True)

    def _check_reviewer(self, kind):
        if kind == 'purchase':
            if not (self.env.is_superuser() or self.env.user.has_group('base.group_system') or self.env.user.has_group('sab_project.group_sab_purchase_approver')):
                raise AccessError(_('Die Einkaufsfreigabe benötigt Bestellfreigaberechte.'))
        else:
            _engineer(self.env)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            bom = self.env['sab.project.bom'].browse(incoming.get('bom_id')).exists()
            if not bom or len(bom) != 1:
                raise ValidationError(_('Bitte eine Stückliste auswählen.'))
            kind = incoming.get('release_kind', 'technical')
            if kind not in ('technical', 'purchase'):
                raise ValidationError(_('Unbekannte Freigabeart.'))
            self._check_reviewer(kind)
            bom.check_access('write')
            prepared.append({'bom_id': bom.id, 'release_kind': kind, 'expected_fingerprint': fingerprint(bom._sab_material_rows())})
        return super().create(prepared)

    def write(self, vals):
        if set(vals) - {'acknowledge_unknown'}:
            raise ValidationError(_('Der Freigabevergleich darf nicht umgeschrieben werden.'))
        return super().write(vals)

    def action_confirm(self):
        self.ensure_one()
        self._check_reviewer(self.release_kind)
        self.bom_id._sab_lock_technical_boms()
        if fingerprint(self.bom_id._sab_material_rows()) != self.expected_fingerprint:
            raise ValidationError(_('Die Stückliste wurde inzwischen geändert. Bitte den Kostenvergleich neu öffnen.'))
        if (self.zero_price_count or not self.comparison_known) and not self.acknowledge_unknown:
            raise ValidationError(_('Bitte die Hinweise zur fehlenden Preisbasis ausdrücklich bestätigen.'))
        if self.release_kind == 'purchase':
            return self.bom_id.action_release_for_purchase()
        self.bom_id.action_release()
        return {'type': 'ir.actions.act_window_close'}


class MaterialEdit(models.TransientModel):
    _name = 'sab.bom.material.edit'
    _description = 'Kontrollierte Materialänderung des Einkaufs'
    group_id = fields.Many2one('sab.bom.material.group', readonly=True, required=True, ondelete='restrict')
    bom_id = fields.Many2one(related='group_id.bom_id', readonly=True)
    available_cabinet_ids = fields.Many2many(related='bom_id.source_cabinet_bom_ids', readonly=True)
    currency_id = fields.Many2one(related='bom_id.sab_material_currency_id', readonly=True)
    reason = fields.Text(string='Änderungsgrund')
    confirm_allocation = fields.Boolean(string='Teilmengen, Schrankzuordnungen und Auswirkungen geprüft')
    line_ids = fields.One2many('sab.bom.material.edit.line', 'wizard_id', string='Verbindliche Aufteilung je Schrank / LV')
    original_values = fields.Json(readonly=True)
    expected_fingerprint = fields.Char(readonly=True)
    old_quantity = fields.Float(string='Menge vorher', readonly=True, digits=(16, 3))
    new_quantity = fields.Float(string='Menge nachher (aus Teilmengen)', compute='_compute_preview', digits=(16, 3))
    old_ek = fields.Monetary(string='Material-EK der Auswahl vorher', currency_field='currency_id', readonly=True)
    new_ek = fields.Monetary(string='Material-EK der Auswahl nachher', currency_field='currency_id', compute='_compute_preview')
    base_ek = fields.Monetary(string='Ursprünglich kalkulierter Material-EK gesamt', currency_field='currency_id', related='bom_id.sab_material_calculated_ek')
    current_total_ek = fields.Monetary(string='Material-EK Gesamtstückliste vorher', currency_field='currency_id', related='bom_id.sab_material_current_ek')
    preview_total_ek = fields.Monetary(string='Material-EK Gesamtstückliste nachher', currency_field='currency_id', compute='_compute_preview')

    @api.depends('line_ids.quantity', 'line_ids.unit_purchase_price', 'line_ids.optional',
                 'line_ids.remove', 'original_values', 'bom_id.sab_material_current_ek')
    def _compute_preview(self):
        for wizard in self:
            rows = [line._values_for_validation() for line in wizard.line_ids]
            try:
                new = totals(rows)['normal']
                qty = sum(row['quantity'] for row in rows if not row['removed'])
            except ValueError:
                new = qty = 0.0  # Invalid input is rejected by action_apply.
            wizard.new_quantity = qty
            wizard.new_ek = new
            wizard.preview_total_ek = wizard.current_total_ek - wizard.old_ek + new

    def _current_fingerprint(self):
        self.ensure_one()
        rows = self.bom_id._sab_material_rows()
        source_rows = [r._sab_material_row() for r in self.group_id.line_ids.mapped('source_cabinet_line_id').sorted('id')]
        return fingerprint([{'id': 1, 'package': rows, 'sources': source_rows,
            'group_ids': sorted(self.group_id.line_ids.ids),
            'revision': self.bom_id.sab_material_revision}])

    @api.model_create_multi
    def create(self, vals_list):
        _purchaser(self.env)
        prepared = []
        for incoming in vals_list:
            group = self.env['sab.bom.material.group'].browse(incoming.get('group_id')).exists()
            if not group or len(group) != 1:
                raise ValidationError(_('Bitte einen zusammengefassten Materialartikel auswählen.'))
            group.check_access('read'); group.bom_id.check_access('write')
            group.bom_id._sab_check_changeable_material(group.line_ids)
            if not group.line_ids or group.line_ids.filtered(lambda l: not l.source_cabinet_line_id):
                raise ValidationError(_('Die Ursprungszuordnung ist unvollständig; keine automatische Zuordnung aus Artikeltexten.'))
            rows = [l._sab_material_row() for l in group.line_ids.sorted('id')]
            commands = []
            for line in group.line_ids.sorted('id'):
                commands.append(Command.create({'package_line_id': line.id,
                    'cabinet_bom_id': line.source_cabinet_bom_id.id,
                    'lv_position': line.sab_lv_position or False,
                    'odoo_product_id': (line.odoo_product_id or line.product_id.odoo_product_id).id or False,
                    'legacy_product_id': line.product_id.id or False,
                    'quantity': line.quantity, 'unit': line.unit, 'optional': line.optional,
                    'unit_purchase_price': line.unit_purchase_price,
                    'supplier_product_id': line.supplier_product_id.id or False, 'note': line.note}))
            prepared.append({'group_id': group.id, 'reason': incoming.get('reason', ''),
                'original_values': rows, 'old_quantity': sum(r['quantity'] for r in rows),
                'old_ek': totals(rows)['normal'], 'line_ids': commands})
        with _service():
            records = super().create(prepared)
            for record in records:
                super(MaterialEdit, record).write({'expected_fingerprint': record._current_fingerprint()})
        return records

    def write(self, vals):
        if set(vals) - {'reason', 'confirm_allocation', 'line_ids'}:
            raise ValidationError(_('Der ursprüngliche Änderungsstand darf nicht manipuliert werden.'))
        return super().write(vals)

    def action_apply(self):
        self.ensure_one()
        _purchaser(self.env)
        self.bom_id.check_access('write')
        if not (self.reason or '').strip() or not self.confirm_allocation:
            raise ValidationError(_('Änderungsgrund und ausdrückliche Prüfung der Schrankaufteilung sind erforderlich.'))
        package = self.bom_id
        sources = self.group_id.line_ids.mapped('source_cabinet_line_id')
        package.mapped('order_id')._sab_lock_bom_order()
        cabinets = package.source_cabinet_bom_ids
        (package | cabinets)._sab_lock_technical_boms()
        locked = self.group_id.line_ids | sources
        if locked:
            self.env.cr.execute('SELECT id FROM sab_project_bom_line WHERE id IN %s ORDER BY id FOR UPDATE',
                                [tuple(sorted(locked.ids))])
            locked.invalidate_recordset()
        package.invalidate_recordset(['line_ids', 'sab_material_revision'])
        self.group_id.invalidate_recordset(['line_ids'])
        if self.expected_fingerprint != self._current_fingerprint():
            raise ValidationError(_('Material oder Schrankzuordnung wurde zwischenzeitlich geändert. Bitte den Dialog erneut öffnen.'))
        original_ids = {r['id'] for r in self.original_values}
        rows = [line._values_for_validation() for line in self.line_ids]
        try:
            validate_change(rows, set(cabinets.ids), original_ids)
        except ValueError as error:
            raise ValidationError(str(error)) from error
        original = {r['id']: {**r, 'note': r.get('note') or False} for r in self.original_values}
        changed = []
        for edit in self.line_ids:
            old = original.get(edit.package_line_id.id)
            if old and (edit.cabinet_bom_id.id != old['cabinet_id']
                        or (edit.lv_position or '') != old['lv']):
                raise ValidationError(_('Vorhandene Schrank-/LV-Zuordnung bleibt erhalten. Für eine Umverteilung Mengen anpassen und eine neue Zuordnung ergänzen.'))
            values = edit._line_values()
            if not old or any(values.get(key) != old.get(key) for key in (
                'odoo_product_id', 'product_id', 'quantity', 'unit', 'optional',
                'unit_purchase_price', 'supplier_product_id', 'note')) or edit.remove:
                changed.append((edit, values))
        if not changed:
            return {'type': 'ir.actions.act_window_close'}
        affected_old = self.line_ids.filtered(lambda l: l.package_line_id).mapped('package_line_id')
        reqs = package._sab_check_changeable_material(affected_old)
        if reqs:
            self.env.cr.execute('SELECT id FROM sab_purchase_requirement WHERE id IN %s ORDER BY id FOR UPDATE',
                                [tuple(sorted(reqs.ids))])
            reqs.invalidate_recordset()
            package._sab_check_changeable_material(affected_old)
        for edit, values in changed:
            if edit.cabinet_bom_id.production_order_ids:
                raise ValidationError(_('Ein betroffener Schrank hat bereits einen Fertigungsauftrag. Bitte eine abgestimmte Revision durchführen.'))
            old_line = edit.package_line_id
            if old_line:
                source = old_line.source_cabinet_line_id
                if (not source or source.bom_id != edit.cabinet_bom_id
                        or source.bom_id not in cabinets or source.bom_id.state != 'released'):
                    raise ValidationError(_('Die verbindliche Einzelstücklistenzuordnung ist ungültig.'))
                for key in ('quantity', 'unit', 'optional', 'unit_purchase_price', 'sab_lv_position'):
                    if source[key] != old_line[key]:
                        raise ValidationError(_('Einzel- und Gesamtstückliste weichen bereits voneinander ab. Bitte vor der Änderung klären.'))
        before_rows = package._sab_material_rows()
        old_total = package.sab_material_current_ek
        affected = self.env['sab.project.bom']
        recheck = self.env['sab.project.bom']
        Line = self.env['sab.project.bom.line'].sudo()
        changed_package_lines = self.env['sab.project.bom.line']
        with self.env.cr.savepoint(), _service():
            for edit, values in changed:
                cabinet = edit.cabinet_bom_id
                affected |= cabinet
                old_line = edit.package_line_id
                req = reqs.filtered(lambda r: r.bom_line_id == old_line) if old_line else reqs.browse()
                if req:
                    req._release_project_reservation()
                if old_line:
                    source = old_line.source_cabinet_line_id
                    technical = technical_change(values, source._sab_material_row())
                    source.sudo()._sab_apply_controlled_values(values)
                    old_line.sudo()._sab_apply_controlled_values(values)
                    changed_package_lines |= old_line
                else:
                    technical = True
                    source = Line._sab_create_controlled_values({**values,
                        'bom_id': cabinet.id, 'sequence': max(cabinet.line_ids.mapped('sequence') or [0]) + 10,
                        'sab_lv_position': edit.lv_position or False})
                    new_line = Line._sab_create_controlled_values({**values,
                        'bom_id': package.id, 'sequence': max(package.line_ids.mapped('sequence') or [0]) + 10,
                        'source_cabinet_bom_id': cabinet.id, 'source_cabinet_line_id': source.id,
                        'sab_lv_position': edit.lv_position or False})
                    changed_package_lines |= new_line
                if technical:
                    recheck |= cabinet
                if req:
                    req.write({'quantity': values['quantity'], 'unit_purchase_price': values['unit_purchase_price'],
                        'supplier_product_id': values['supplier_product_id'], 'note': values['note'],
                        'state': 'cancel' if values['sab_material_removed'] or values['optional'] else 'open'})
            affected._sab_check_technical_content()
            for cabinet in affected:
                cabinet._sab_material_metadata({'sab_material_revision': cabinet.sab_material_revision + 1,
                    'sab_material_recheck': cabinet.sab_material_recheck or cabinet in recheck})
            package._sab_material_metadata({'sab_material_revision': package.sab_material_revision + 1})
            after_rows = package._sab_material_rows()
            self.env['sab.bom.material.change'].sudo().create({
                'bom_id': package.id, 'reason': self.reason.strip(),
                'before_values': before_rows, 'after_values': after_rows,
                'changed_by_id': self.env.user.id, 'cabinet_ids': [Command.set(affected.ids)],
                'before_ek': old_total, 'after_ek': package.sab_material_current_ek})
            body = Markup('<p>%s</p><p>%s</p><p>%s</p>') % (
                _('Einkaufsänderung in Einzel- und Gesamtstückliste übernommen.'), self.reason.strip(),
                _('Technische Prüfung erforderlich.') if recheck else _('Nur Einkaufsdaten geändert.'))
            for bom in package | affected:
                bom.message_post(body=body)
            package._sab_sync_material_groups()
            package._sab_push_to_procurement_workspace()
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class MaterialEditLine(models.TransientModel):
    _name = 'sab.bom.material.edit.line'
    _description = 'Verbindliche Schrankteilmenge im Einkaufsdialog'
    _order = 'id'
    wizard_id = fields.Many2one('sab.bom.material.edit', required=True, ondelete='cascade')
    package_line_id = fields.Many2one('sab.project.bom.line', readonly=True, ondelete='restrict')
    cabinet_bom_id = fields.Many2one('sab.project.bom', string='Verteiler / Schrank', required=True)
    lv_position = fields.Char(string='LV / NTG (optional)')
    odoo_product_id = fields.Many2one('product.product', string='Produkt')
    legacy_product_id = fields.Many2one('sab.product', readonly=True)
    quantity = fields.Float(string='Teilmenge', required=True, digits=(16, 3), default=1)
    unit = fields.Selection([('pcs', 'Stück'), ('m', 'Meter'), ('kg', 'kg'), ('min', 'Minute'),
        ('h', 'Stunde'), ('flat', 'Pauschal')], required=True, default='pcs', string='Einheit')
    optional = fields.Boolean(string='Optional')
    unit_purchase_price = fields.Float(string='Material-EK je Einheit', digits=(16, 4), required=True)
    supplier_product_id = fields.Many2one('sab.supplier.product', string='Lieferantenartikel')
    note = fields.Char(string='Bemerkung')
    remove = fields.Boolean(string='Entfernen')

    @api.onchange('odoo_product_id')
    def _onchange_product(self):
        for line in self:
            old = line.package_line_id.odoo_product_id or line.package_line_id.product_id.odoo_product_id
            if line.odoo_product_id and line.odoo_product_id != old:
                line.unit_purchase_price = line.odoo_product_id.with_company(line.wizard_id.bom_id.order_id.company_id).standard_price
                line.supplier_product_id = False

    @api.onchange('supplier_product_id')
    def _onchange_supplier(self):
        for line in self:
            if line.supplier_product_id:
                line.unit_purchase_price = line.supplier_product_id.net_purchase_price

    @api.model_create_multi
    def create(self, vals_list):
        if not _SERVICE.get():
            parents = self.env['sab.bom.material.edit'].browse([v['wizard_id'] for v in vals_list if v.get('wizard_id')])
            parents.check_access('write')
        if not _SERVICE.get() and any(v.get('package_line_id') or v.get('legacy_product_id') for v in vals_list):
            raise ValidationError(_('Ursprungspositionen werden ausschließlich durch den Änderungsdialog geladen.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'package_line_id', 'legacy_product_id', 'wizard_id'}.intersection(vals):
            raise ValidationError(_('Eine vorhandene Zuordnung darf nicht auf eine andere Ursprungszeile umgebogen werden.'))
        return super().write(vals)

    def _values_for_validation(self):
        self.ensure_one()
        return {'source_id': self.package_line_id.id or False, 'cabinet_id': self.cabinet_bom_id.id,
            'odoo_product_id': self.odoo_product_id.id or False, 'product_id': self.legacy_product_id.id or False,
            'quantity': self.quantity, 'unit': self.unit, 'optional': self.optional,
            'unit_purchase_price': self.unit_purchase_price, 'removed': self.remove}

    def _line_values(self):
        self.ensure_one()
        product = self.odoo_product_id
        legacy = self.legacy_product_id
        if product and product != legacy.odoo_product_id:
            legacy = self.env['sab.product']
        if (not product and not legacy) or (product and (product.sab_is_montage_time or product.type == 'service')):
            raise ValidationError(_('Bitte ein Materialprodukt auswählen; Montagezeit ist kein Material.'))
        if product.company_id and product.company_id != self.wizard_id.bom_id.order_id.company_id:
            raise ValidationError(_('Das Produkt gehört zu einem anderen Unternehmen.'))
        supplier = self.supplier_product_id
        if supplier and ((supplier.odoo_product_id or supplier.product_id.odoo_product_id) != product
                         and (not legacy or supplier.product_id != legacy)):
            raise ValidationError(_('Der Lieferantenartikel gehört nicht zum ausgewählten Materialprodukt.'))
        return {'product_id': legacy.id or False, 'odoo_product_id': product.id or False,
            'quantity': 0.0 if self.remove else self.quantity, 'unit': self.unit, 'optional': self.optional,
            'unit_purchase_price': self.unit_purchase_price, 'supplier_product_id': supplier.id or False,
            'note': self.note or False, 'sab_material_removed': self.remove}
