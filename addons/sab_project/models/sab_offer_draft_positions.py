"""Reuse saved project positions without prematurely releasing quotations.

Draft suggestions and immutable mappings remain separate. No migration, price
recalculation or source-quotation write is performed by this extension.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


def choose_position(candidates, explicit=False):
    """Return a unique (code, NTG) choice; never choose the first of several."""
    unique = {(str(code).strip(), bool(ntg)) for code, ntg in candidates if str(code or '').strip()}
    explicit = (explicit or '').strip()
    if explicit:
        matches = {value for value in unique if value[0] == explicit}
        return next(iter(matches)) if len(matches) == 1 else None
    return next(iter(unique)) if len(unique) == 1 else None


def record_id(record):
    return record._origin.id if record else False


class ProjectPositionMapping(models.Model):
    _inherit = 'sab.project.lv.mapping'

    @api.constrains('project_id', 'calculation_item_id', 'odoo_product_id', 'position_code')
    def _check_unique_mapping(self):
        # One article may legitimately occur under several LV positions.
        # It is the position, not the article alone, that must be unambiguous.
        for mapping in self:
            if self.search_count([
                ('project_id', '=', mapping.project_id.id),
                ('position_code', '=', mapping.position_code), ('id', '!=', mapping.id),
            ]):
                raise ValidationError('Diese LV-/NTG-Nummer ist im Projekt bereits zugeordnet.')

    @api.model
    def next_ntg_number(self, project):
        self.env.cr.execute('SELECT id FROM project_project WHERE id = %s FOR UPDATE', [project.id])
        return super().next_ntg_number(project)


class DraftPositionLine(models.Model):
    _inherit = 'sab.offer.calculation.line'

    sab_lv_choice_required = fields.Boolean(compute='_compute_sab_lv_choice_required')

    @api.model
    def _sab_position_sources(self, order, item_id=False, product_id=False):
        """Earlier saved offers only; no later offer can redefine its predecessor."""
        project_id, order_id = record_id(order.sab_project_id), record_id(order)
        if not project_id or not order_id or not (item_id or product_id):
            return self.browse()
        domain = [
            ('order_id.sab_project_id', '=', project_id),
            ('order_id.company_id', '=', order.company_id.id),
            ('order_id.state', '!=', 'cancel'),
            '|', ('order_id', '<', order_id),
            '&', ('order_id', '=', order_id), ('is_ntg', '=', True),
            ('line_type', '=', 'item'), ('parent_section_id', '=', False),
            ('lv_position', '!=', False),
        ]
        domain += [('calculation_item_id', '=', item_id)] if item_id else [
            ('calculation_item_id', '=', False), ('odoo_product_id', '=', product_id)]
        return self.search(domain, order='order_id, sequence, id').filtered(
            lambda line: bool((line.lv_position or '').strip()))

    @api.model
    def _sab_position_mappings(self, order, item_id=False, product_id=False):
        Mapping = self.env['sab.project.lv.mapping']
        if not order or not order.sab_project_id or not (item_id or product_id):
            return Mapping
        domain = [('project_id', '=', record_id(order.sab_project_id))]
        domain += [('calculation_item_id', '=', item_id)] if item_id else [
            ('calculation_item_id', '=', False), ('odoo_product_id', '=', product_id)]
        return Mapping.search(domain)

    def _sab_position_choices(self, order, item_id=False, product_id=False):
        mappings = self._sab_position_mappings(order, item_id, product_id)
        sources = self._sab_position_sources(order, item_id, product_id)
        return [(m.position_code, m.is_ntg) for m in mappings] + [
            (line.lv_position, line.is_ntg) for line in sources]

    @api.model
    def _sab_has_saved_lv_basis(self, order):
        if not record_id(order) or not order.sab_project_id:
            return False
        return bool(self.search_count([
            ('order_id.sab_project_id', '=', record_id(order.sab_project_id)),
            ('order_id.company_id', '=', order.company_id.id),
            ('order_id', '<', record_id(order)), ('order_id.state', '!=', 'cancel'),
            ('order_id.sab_calculation_source', '=', 'lv'),
            ('line_type', 'in', ('item', 'section')), ('parent_section_id', '=', False),
            ('lv_position', '!=', False), ('is_ntg', '=', False),
        ]))

    def _sab_lv_mapping(self, order=None, calculation_item_id=False, odoo_product_id=False):
        order = order or self.order_id
        mappings = self._sab_position_mappings(order, calculation_item_id, odoo_product_id)
        if len(self) == 1 and self.lv_position:
            return mappings.filtered(lambda m: m.position_code == self.lv_position)[:1]
        return mappings if len(mappings) == 1 else mappings.browse()

    def _sab_apply_project_position(self, vals, order):
        if self.env.context.get('sab_inherit_section_position') or not order or not order.sab_project_id:
            return vals
        existing = self if len(self) == 1 and record_id(self) else self.browse()
        line_type = vals.get('line_type') or (existing.line_type if existing else 'item')
        parent = self._sab_parent_section_from_values(vals)
        if line_type == 'item' and parent:
            vals.update(lv_position=parent.lv_position or False,
                        is_ntg=bool(parent.lv_position and parent.is_ntg))
            return vals
        # Quantity/description/technical writes must not allocate a fresh NTG.
        identity_changed = bool(existing and any(
            name in vals and (vals[name] or False) != (existing[name].id or False)
            for name in ('calculation_item_id', 'odoo_product_id')
        ))
        if existing and not identity_changed and not {'lv_position', 'is_ntg'}.intersection(vals):
            if (existing.lv_position or '').strip():
                return vals
            if not {'calculation_item_id', 'odoo_product_id'}.intersection(vals):
                return vals
        basis = self._sab_has_prior_lv_offer(order) or self._sab_has_saved_lv_basis(order)
        if order.sab_calculation_source == 'schematic' and not basis:
            return super()._sab_apply_project_position(vals, order)
        if line_type not in ('item', 'section'):
            return vals
        code = (vals.get('lv_position') or '').strip()
        if existing and not identity_changed and 'lv_position' not in vals:
            code = (existing.lv_position or '').strip()
        if line_type == 'section':
            if not code and basis:
                code = 'NTG %s' % self.env['sab.project.lv.mapping'].next_ntg_number(order.sab_project_id)
            if code:
                vals.update(lv_position=code, is_ntg=code.upper().startswith('NTG'))
            return vals
        item_id = vals.get('calculation_item_id', existing.calculation_item_id.id if existing else False)
        product_id = vals.get('odoo_product_id', existing.odoo_product_id.id if existing else False)
        if item_id:
            product_id = False
        if not (item_id or product_id):
            return vals
        choices = self._sab_position_choices(order, item_id, product_id)
        selection = choose_position(choices, code)
        if selection:
            vals.update(lv_position=selection[0], is_ntg=selection[1])
        elif code:
            # Explicit position entry in the first LV and copied positions remain intact.
            # Existing immutable mappings are still protected by write/release guards.
            vals.update(lv_position=code, is_ntg=bool(vals.get('is_ntg')) or code.upper().startswith('NTG'))
        elif choices:
            vals.update(lv_position=False, is_ntg=False)  # ambiguous: explicit choice required
        elif basis:
            number = self.env['sab.project.lv.mapping'].next_ntg_number(order.sab_project_id)
            vals.update(lv_position='NTG %s' % number, is_ntg=True)
        return vals

    @api.depends('order_id', 'calculation_item_id', 'odoo_product_id', 'lv_position', 'parent_section_id')
    def _compute_sab_lv_choice_required(self):
        for line in self:
            choices = line._sab_position_choices(line.order_id, line.calculation_item_id.id, line.odoo_product_id.id) if line.order_id else []
            line.sab_lv_choice_required = bool(
                line.line_type == 'item' and not line.parent_section_id and not line.lv_position
                and choices and not choose_position(choices))

    @api.onchange('calculation_item_id', 'odoo_product_id')
    def _onchange_sab_saved_project_position(self):
        if self.line_type != 'item' or self.parent_section_id or not self.order_id:
            return
        choices = self._sab_position_choices(self.order_id, self.calculation_item_id.id, self.odoo_product_id.id)
        choice = choose_position(choices, self.lv_position) or choose_position(choices)
        if choice:
            self.lv_position, self.is_ntg = choice
        elif choices and not self.lv_position:
            return {'warning': {'title': 'LV-Position auswählen', 'message':
                'Dieser Artikel kommt unter mehreren LV-Positionen vor: %s. '
                'Bitte LV wählen oder rechts die gewünschte Position übernehmen.' %
                ', '.join(sorted({code for code, _ in choices})), 'type': 'notification'}}
        # New NTG numbers are allocated on save, not inside an onchange pseudo-record.

    @api.model_create_multi
    def create(self, vals_list):
        # Serialise automatic number allocation and persist each reservation before
        # processing the next row of an import/batch.
        project_ids = sorted(set(self.env['sale.order'].browse([
            vals['order_id'] for vals in vals_list if vals.get('order_id')
        ]).mapped('sab_project_id').ids))
        if project_ids:
            self.env.cr.execute('SELECT id FROM project_project WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(project_ids)])
        result = self.browse()
        for vals in vals_list:
            result |= super().create([vals])
        return result

    def _sab_create_mapping_from_line(self):
        if not self.env.context.get('sab_offer_release_mapping'):
            return True
        Mapping = self.env['sab.project.lv.mapping']
        for line in self.filtered(lambda l: l.line_type == 'item' and not l.parent_section_id
                                  and l.order_id.sab_project_id and l.lv_position
                                  and (l.calculation_item_id or l.odoo_product_id)):
            code = line.lv_position.strip()
            mappings = line._sab_position_mappings(line.order_id, line.calculation_item_id.id, line.odoo_product_id.id)
            exact = mappings.filtered(lambda m: m.position_code == code)
            if exact:
                if exact.is_ntg != line.is_ntg:
                    raise ValidationError('Die NTG-Kennzeichnung der festgeschriebenen Position darf nicht geändert werden.')
                continue
            number = 0
            if line.is_ntg:
                try:
                    number = int(code.split()[-1])
                except (ValueError, IndexError):
                    raise ValidationError('Eine NTG-Position benötigt eine Nummer, zum Beispiel NTG 1.')
            Mapping.create({
                'project_id': line.order_id.sab_project_id.id,
                'calculation_item_id': line.calculation_item_id.id or False,
                'odoo_product_id': line.odoo_product_id.id if not line.calculation_item_id else False,
                'position_code': code, 'is_ntg': line.is_ntg, 'ntg_number': number,
                'first_order_id': line.order_id.id,
            })
        return True

    def action_sab_choose_lv_position(self):
        self.ensure_one()
        sources = self._sab_position_sources(self.order_id, self.calculation_item_id.id, self.odoo_product_id.id)
        return {'type': 'ir.actions.act_window', 'name': 'LV-Position auswählen',
                'res_model': self._name, 'view_mode': 'list', 'target': 'new',
                'views': [(self.env.ref('sab_project.sab_lv_position_choice_list').id, 'list')],
                'domain': [('id', 'in', sources.ids)],
                'context': dict(self.env.context, sab_lv_target_line_id=self.id)}

    def action_sab_apply_lv_choice(self):
        self.ensure_one()
        target = self.browse(self.env.context.get('sab_lv_target_line_id')).exists()
        if not target or len(target) != 1 or self not in target._sab_position_sources(
                target.order_id, target.calculation_item_id.id, target.odoo_product_id.id):
            raise ValidationError('Diese LV-Position ist für die Zielposition nicht zulässig.')
        target.write({'lv_position': self.lv_position, 'is_ntg': self.is_ntg})
        return {'type': 'ir.actions.act_window_close'}


class DraftPositionPanel(models.Model):
    _inherit = 'sale.order'

    def sab_offer_reuse_payload(self):
        self.ensure_one()
        payload = super().sab_offer_reuse_payload()
        if not self.sab_project_id:
            return payload
        Line, Mapping = self.env['sab.offer.calculation.line'], self.env['sab.project.lv.mapping']
        seen = set()
        for entry in payload['lv_positions']:
            mapping = Mapping.browse(entry['id'])
            seen.add((mapping.calculation_item_id.id, mapping.odoo_product_id.id, mapping.position_code))
            entry['position_status'] = 'Festgeschrieben'
        sources = Line.search([
            ('order_id.sab_project_id', '=', self.sab_project_id.id),
            ('order_id.company_id', '=', self.company_id.id), ('order_id.state', '!=', 'cancel'),
            ('line_type', '=', 'item'), ('parent_section_id', '=', False), ('lv_position', '!=', False),
        ], order='order_id, sequence, id')
        for source in sources:
            code = (source.lv_position or '').strip()
            key = (source.calculation_item_id.id, source.odoo_product_id.id, code)
            if not code or key in seen or not (source.calculation_item_id or source.odoo_product_id):
                continue
            seen.add(key)
            payload['lv_positions'].append({
                'id': -source.id, 'position': code, 'is_ntg': source.is_ntg,
                'source_type': 'Kalkulationsartikel' if source.calculation_item_id else 'Produkt',
                'source_name': (source.calculation_item_id or source.odoo_product_id).display_name,
                'first_offer': source.order_id.sab_offer_reference or source.order_id.name,
                'position_status': 'Entwurf' if source.order_id.sab_offer_release_state != 'released' else 'Freigegeben',
            })
        payload['lv_positions'].sort(key=lambda e: (bool(e['is_ntg']), e['position'], e['id']))
        return payload

    def sab_offer_add_reuse_entry(self, entry_kind, entry_id):
        self.ensure_one()
        if entry_kind != 'lv':
            return super().sab_offer_add_reuse_entry(entry_kind, entry_id)
        self._sab_offer_reuse_assert_editable()
        if self.sab_offer_release_state == 'released':
            raise ValidationError('Das freigegebene Angebot darf nicht verändert werden.')
        entry_id = int(entry_id)
        Line = self.env['sab.offer.calculation.line']
        if entry_id < 0:
            source = Line.browse(-entry_id).exists()
            if (not source or source.order_id.sab_project_id != self.sab_project_id
                    or source.order_id.company_id != self.company_id or source.order_id.state == 'cancel'
                    or source.line_type != 'item' or source.parent_section_id or not source.lv_position):
                raise ValidationError('Die ausgewählte Entwurfsposition gehört nicht zu diesem Projekt.')
            item, product, code, ntg = source.calculation_item_id, source.odoo_product_id, source.lv_position, source.is_ntg
        else:
            mapping = self.env['sab.project.lv.mapping'].browse(entry_id).exists()
            if not mapping or mapping.project_id != self.sab_project_id:
                raise ValidationError('Die ausgewählte Position gehört nicht zu diesem Projekt.')
            item, product, code, ntg = mapping.calculation_item_id, mapping.odoo_product_id, mapping.position_code, mapping.is_ntg
            source = Line.search([
                ('order_id', '=', mapping.first_order_id.id), ('lv_position', '=', code),
                ('calculation_item_id', '=', item.id or False), ('odoo_product_id', '=', product.id or False),
                ('line_type', '=', 'item'), ('parent_section_id', '=', False),
            ], limit=1)
        pending = self.sab_calculation_line_ids.filtered(lambda l: l.line_type == 'item'
            and not l.parent_section_id and not l.lv_position
            and l.calculation_item_id == item and l.odoo_product_id == product)
        if len(pending) > 1:
            raise ValidationError('Mehrere Zeilen warten auf eine LV-Zuordnung. Bitte in der gewünschten Zeile LV wählen verwenden.')
        if pending:
            pending.write({'lv_position': code, 'is_ntg': ntg})
        else:
            sequence = self._sab_offer_reuse_prepare_insertion(adding_component=False)
            values = {'order_id': self.id, 'line_type': 'item', 'quantity': 1.0, 'sequence': sequence,
                      'calculation_item_id': item.id or False, 'odoo_product_id': product.id or False,
                      'lv_position': code, 'is_ntg': ntg, 'group_id': False,
                      'parent_section_id': False, 'parent_cabinet_id': False}
            if source:
                values = source.copy_data(values)[0]
            self._sab_offer_reuse_create_lines([values])
        return {'message': 'LV-/NTG-Position %s wurde übernommen.' % code}
