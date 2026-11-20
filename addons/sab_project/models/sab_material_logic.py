"""Pure material arithmetic; no Odoo writes and no automatic quantity distribution."""
from collections import OrderedDict
from decimal import Decimal
import hashlib
import json
import math

UNITS = {'pcs', 'm', 'kg', 'min', 'h', 'flat'}


def number(value):
    if isinstance(value, bool):
        raise ValueError('Eine Zahl statt eines Wahrheitswerts eingeben.')
    result = float(value or 0)
    if not math.isfinite(result):
        raise ValueError('Mengen und Einkaufspreise müssen endlich sein.')
    return result


def material_key(row):
    native, legacy = row.get('odoo_product_id'), row.get('product_id')
    if not (native or legacy):
        raise ValueError('Jede Materialposition benötigt ein Produkt.')
    unit = row.get('unit', 'pcs')
    if unit not in UNITS:
        raise ValueError('Unbekannte Mengeneinheit.')
    return '%s:%s:%s:%s' % ('odoo' if native else 'sab', native or legacy,
                             unit, int(bool(row.get('optional'))))


def row_cost(row):
    quantity, price = number(row.get('quantity')), number(row.get('unit_purchase_price'))
    if quantity < 0 or price < 0:
        raise ValueError('Negative Mengen oder Einkaufspreise sind nicht zulässig.')
    return Decimal(str(quantity)) * Decimal(str(price))


def totals(rows):
    normal = Decimal('0')
    optional = Decimal('0')
    zero_prices = 0
    for row in rows:
        if row.get('removed'):
            continue
        cost = row_cost(row)
        if row.get('optional'):
            optional += cost
        else:
            normal += cost
            if number(row.get('quantity')) > 0 and number(row.get('unit_purchase_price')) == 0:
                zero_prices += 1
    return {'normal': float(normal), 'optional': float(optional), 'zero_prices': zero_prices}


def comparison(baseline, current, known=True):
    before, after = totals(baseline), totals(current)
    delta = after['normal'] - before['normal'] if known else None
    percent = delta / before['normal'] * 100 if known and before['normal'] != 0 else None
    return dict(base=before['normal'] if known else None, current=after['normal'],
                optional=after['optional'], delta=delta, percent=percent,
                zero_prices=after['zero_prices'])


def aggregate(rows):
    buckets = OrderedDict()
    for row in rows:
        if row.get('removed'):
            continue
        key = material_key(row)
        bucket = buckets.setdefault(key, {'key': key, 'line_ids': [], 'quantity': Decimal('0'),
            'cost': Decimal('0'), 'allocations': OrderedDict(), 'unit': row.get('unit', 'pcs'),
            'optional': bool(row.get('optional')), 'odoo_product_id': row.get('odoo_product_id'),
            'product_id': row.get('product_id')})
        bucket['line_ids'].append(row.get('id'))
        bucket['quantity'] += Decimal(str(number(row.get('quantity'))))
        bucket['cost'] += row_cost(row)
        allocation = (row.get('cabinet_id'), row.get('cabinet', ''), row.get('lv', '') or '')
        bucket['allocations'][allocation] = bucket['allocations'].get(allocation, Decimal('0')) + Decimal(str(number(row.get('quantity'))))
    result = []
    for bucket in buckets.values():
        bucket['quantity'] = float(bucket['quantity'])
        bucket['cost'] = float(bucket['cost'])
        bucket['unit_price'] = bucket['cost'] / bucket['quantity'] if bucket['quantity'] else 0.0
        bucket['allocation_text'] = '; '.join('%s: %g%s' %
            (name or 'Schrank #%s' % cid, qty, (' [LV %s]' % lv) if lv else '')
            for (cid, name, lv), qty in bucket['allocations'].items())
        bucket.pop('allocations')
        result.append(bucket)
    return result


def fingerprint(rows):
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda r: r.get('id', 0)),
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode()).hexdigest()


def validate_change(rows, permitted_cabinets, expected_source_ids):
    """Each old allocation is retained explicitly or marked removed; no guessing."""
    seen = set()
    for row in rows:
        cabinet = row.get('cabinet_id')
        if cabinet not in permitted_cabinets:
            raise ValueError('Jede Teilmenge benötigt einen zu dieser Gesamtstückliste gehörenden Schrank.')
        source = row.get('source_id')
        if source:
            if source in seen or source not in expected_source_ids:
                raise ValueError('Doppelte oder fremde Ursprungsposition.')
            seen.add(source)
        material_key(row)
        qty = number(row.get('quantity'))
        price = number(row.get('unit_purchase_price'))
        if price < 0 or qty < 0:
            raise ValueError('Negative Mengen oder Preise sind nicht zulässig.')
        if row.get('removed'):
            if not source:
                raise ValueError('Eine neue Position kann nicht gleichzeitig entfernt werden.')
        elif qty <= 0:
            raise ValueError('Menge muss größer null sein; zum Entfernen das Kontrollfeld verwenden.')
    if seen != set(expected_source_ids):
        raise ValueError('Eine ursprüngliche Zuordnung fehlt. Bitte ausdrücklich als Entfernen markieren.')
    return True


def technical_change(values, previous):
    keys = ('product_id', 'odoo_product_id', 'quantity', 'unit', 'optional')
    return (any(values.get(key) != previous.get(key) for key in keys)
            or bool(values.get('sab_material_removed')) != bool(previous.get('removed')))
