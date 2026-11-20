"""Explicit LV/NTG choices for unsaved direct article rows.

The browser only reads options and updates its form cache. New NTG numbers are
allocated by the existing locked save pipeline. Bauteil membership, prices and
released offers keep their existing guards. No migration or automatic release.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SabOfferPositionDialog(models.Model):
    _inherit = 'sab.offer.calculation.line'

    sab_position_choice = fields.Selection([
        ('auto', 'Bisherige Zuordnung'), ('pending', 'LV / NTG wählen'),
        ('existing', 'Vorhandene Position'), ('new_lv', 'Neue LV-Position'),
        ('new_ntg', 'Neue NTG – Nummer beim Speichern'),
    ], default='auto', required=True, copy=True, string='LV / NTG Auswahl')

    @api.model
    def sab_position_dialog_options(self, values):
        """Read-only RPC; only return accessible positions of the current project."""
        if not isinstance(values, dict):
            raise ValidationError('Ungültige Positionsanfrage.')

        def ident(name):
            value = values.get(name)
            if value in (None, False):
                return False
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValidationError('Ungültige Datensatznummer.')
            return value

        order_id = ident('order_id')
        order = self.env['sale.order'].browse(order_id).exists()
        if order_id and not order:
            raise ValidationError('Das Angebot existiert nicht mehr.')
        if order:
            order.check_access('read')
            project, company, partner = order.sab_project_id, order.company_id, order.partner_id
            editable = order.state in ('draft', 'sent') and order.sab_offer_release_state != 'released'
        else:
            project = self.env['project.project'].browse(ident('project_id')).exists()
            company = self.env['res.company'].browse(ident('company_id') or self.env.company.id).exists()
            partner = self.env['res.partner'].browse(ident('partner_id')).exists()
            if company not in self.env.companies:
                raise AccessError('Kein Zugriff auf diese Firma.')
            if partner:
                partner.check_access('read')
            editable = True
        if not project:
            return {'positions': [], 'can_new_lv': False, 'can_new_ntg': False}
        project.check_access('read')
        item_id, product_id = ident('calculation_item_id'), ident('odoo_product_id')
        if item_id:
            product_id = False
        article = self.env['sab.calculation.item' if item_id else 'product.product'].browse(item_id or product_id).exists()
        if not article:
            return {'positions': [], 'can_new_lv': False, 'can_new_ntg': False}
        article.check_access('read')
        line_id = ident('line_id')
        target = self.browse(line_id).exists()
        if line_id:
            if not target or not order or target.order_id != order:
                raise ValidationError('Die Zeile gehört nicht zum Angebot.')
            target.check_access('read')
            if target.parent_section_id or target.line_type != 'item':
                raise ValidationError('Bauteil-Unterpositionen erhalten keine eigene LV-/NTG-Auswahl.')
            editable = editable and not target.sab_project_price_bound and not target.lv_position_locked
        scope = [('order_id.sab_project_id', '=', project.id),
                 ('order_id.company_id', '=', company.id), ('order_id.state', '!=', 'cancel')]
        if partner:
            scope.append(('order_id.partner_id.commercial_partner_id', '=', partner.commercial_partner_id.id))
        if order:
            scope.append(('order_id', '<=', order.id))
        direct = scope + [('line_type', '=', 'item'), ('parent_section_id', '=', False), ('lv_position', '!=', False)]
        if line_id:
            direct.append(('id', '!=', line_id))
        identity = [('calculation_item_id', '=', item_id)] if item_id else [
            ('calculation_item_id', '=', False), ('odoo_product_id', '=', product_id)]
        sources = self.search(direct + identity, order='order_id, sequence, id')
        entries = {}
        for source in sources:
            code = (source.lv_position or '').strip()
            if not code:
                continue
            key = (code, bool(source.is_ntg))
            if key not in entries:
                entries[key] = {
                    'code': code, 'is_ntg': bool(source.is_ntg),
                    'description': source.description or article.display_name,
                    'offer': source.order_id.sab_offer_reference or source.order_id.name,
                    'status': 'Entwurf', 'price': source.unit_recommended_net_price,
                    'currency': source.currency_id.name,
                }
            if source.order_id.sab_offer_release_state == 'released':
                entries[key]['status'] = 'Festgeschrieben'
        domain = [('project_id', '=', project.id), ('first_order_id.company_id', '=', company.id)]
        if partner:
            domain.append(('first_order_id.partner_id.commercial_partner_id', '=', partner.commercial_partner_id.id))
        if order:
            domain.append(('first_order_id', '<=', order.id))
        maps = self.env['sab.project.lv.mapping'].search(domain + identity)
        for mapping in maps:
            key = (mapping.position_code, bool(mapping.is_ntg))
            if key not in entries:
                entries[key] = {
                    'code': key[0], 'is_ntg': key[1], 'description': article.display_name,
                    'offer': mapping.first_order_id.sab_offer_reference or mapping.first_order_id.name,
                    'price': None, 'currency': mapping.first_order_id.currency_id.name,
                }
            entries[key]['status'] = 'Festgeschrieben'
        basis_domain = scope + [('order_id.sab_calculation_source', '=', 'lv'),
            ('line_type', 'in', ('item', 'section')), ('parent_section_id', '=', False),
            ('lv_position', '!=', False), ('is_ntg', '=', False)]
        if order:
            basis_domain.append(('order_id', '<', order.id))
        basis = bool(self.search_count(basis_domain))
        positions = sorted(entries.values(), key=lambda row: (row['is_ntg'], row['code']))
        return {'positions': positions, 'can_new_lv': bool(editable),
                'can_new_ntg': bool(editable and basis), 'article': article.display_name}

    def _sab_lv_mapping(self, order=None, calculation_item_id=False, odoo_product_id=False):
        # An unresolved direct row must not inherit the lock of an arbitrary
        # single mapping: its user is explicitly deciding existing vs. NEW.
        if len(self) == 1 and not (self.lv_position or '').strip() and self.sab_position_choice != 'auto':
            return self.env['sab.project.lv.mapping']
        return super()._sab_lv_mapping(order, calculation_item_id, odoo_product_id)

    @api.onchange('calculation_item_id', 'odoo_product_id')
    def _onchange_sab_saved_project_position(self):
        if self.sab_position_choice in ('pending', 'new_lv', 'new_ntg') and not self.parent_section_id:
            return
        return super()._onchange_sab_saved_project_position()

    def _sab_apply_project_position(self, vals, order):
        existing = self if len(self) == 1 and self._origin.id else self.browse()
        mode = vals.get('sab_position_choice', existing.sab_position_choice if existing else 'auto')
        line_type = vals.get('line_type', existing.line_type if existing else 'item')
        parent = self._sab_parent_section_from_values(vals)
        if parent or line_type != 'item' or not order or not order.sab_project_id:
            # Keep the already working Bauteil implementation completely intact.
            return super()._sab_apply_project_position(vals, order)
        code = (vals.get('lv_position', existing.lv_position if existing else False) or '').strip()
        has_article = vals.get('calculation_item_id', existing.calculation_item_id.id if existing else False) or vals.get(
            'odoo_product_id', existing.odoo_product_id.id if existing else False)
        if mode == 'pending':
            if code:
                # A manual LV entry after closing the dialog is an explicit choice.
                vals['sab_position_choice'] = 'existing'
                return super()._sab_apply_project_position(vals, order)
            vals.update(lv_position=False, is_ntg=False)
            return vals
        if mode == 'new_ntg' and not code and has_article:
            if not (self._sab_has_prior_lv_offer(order) or self._sab_has_saved_lv_basis(order)):
                raise ValidationError('Eine neue NTG benötigt ein vorheriges LV-Angebot mit Positionen.')
            number = self.env['sab.project.lv.mapping'].next_ntg_number(order.sab_project_id)
            vals.update(lv_position='NTG %s' % number, is_ntg=True, sab_position_choice='existing')
            return vals
        if mode == 'new_lv' and code and has_article:
            if code.upper().startswith('NTG'):
                raise ValidationError('Für einen Nachtrag bitte „Neue NTG“ wählen.')
            unchanged = bool(existing and code == (existing.lv_position or '').strip())
            if not unchanged:
                domain = [('order_id.sab_project_id', '=', order.sab_project_id.id),
                    ('order_id.state', '!=', 'cancel'), ('parent_section_id', '=', False),
                    ('line_type', 'in', ('item', 'section')), ('lv_position', '=', code)]
                if existing:
                    domain.append(('id', '!=', existing.id))
                Mapping = self.env['sab.project.lv.mapping']
                registered = self.env['sab.project.position.price'].sudo().search_count([
                    ('project_id', '=', order.sab_project_id.id), ('company_id', '=', order.company_id.id),
                    ('partner_id', '=', order.partner_id.commercial_partner_id.id), ('position_code', '=', code)])
                if registered or self.search_count(domain) or Mapping.search_count([
                        ('project_id', '=', order.sab_project_id.id), ('position_code', '=', code)]):
                    raise ValidationError('Diese LV-Nummer existiert bereits. Bitte vorhandene Position übernehmen oder eine neue Nummer angeben.')
            vals.update(lv_position=code, is_ntg=False, sab_position_choice='existing')
            return vals
        return super()._sab_apply_project_position(vals, order)
