import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill project-wide LV positions from existing quotation lines.

    The oldest known position for an article becomes the project mapping. Draft
    and sent quotations are aligned to that mapping. Confirmed historical
    quotations are never rewritten; conflicting historical positions are only
    logged for manual review.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env["sab.offer.calculation.line"].sudo()
    Mapping = env["sab.project.lv.mapping"].sudo()

    lines = Line.search([
        ("line_type", "=", "item"),
        ("order_id.sab_project_id", "!=", False),
        ("order_id.sab_calculation_source", "=", "lv"),
        "|",
        ("calculation_item_id", "!=", False),
        ("odoo_product_id", "!=", False),
    ], order="order_id asc, sequence asc, id asc")

    created = aligned = conflicts = 0
    for line in lines:
        order = line.order_id
        source_domain = [("project_id", "=", order.sab_project_id.id)]
        source_values = {}
        if line.calculation_item_id:
            source_domain.append(("calculation_item_id", "=", line.calculation_item_id.id))
            source_values["calculation_item_id"] = line.calculation_item_id.id
        elif line.odoo_product_id:
            source_domain.append(("odoo_product_id", "=", line.odoo_product_id.id))
            source_values["odoo_product_id"] = line.odoo_product_id.id
        else:
            continue

        mapping = Mapping.search(source_domain, limit=1)
        entered_position = (line.lv_position or "").strip()

        if not mapping and entered_position:
            is_ntg = bool(line.is_ntg or entered_position.upper().startswith("NTG"))
            values = {
                "project_id": order.sab_project_id.id,
                "position_code": entered_position,
                "is_ntg": is_ntg,
                "first_order_id": order.id,
                **source_values,
            }
            if is_ntg:
                try:
                    values["ntg_number"] = int(entered_position.split()[-1])
                except (ValueError, IndexError):
                    values["ntg_number"] = Mapping.next_ntg_number(order.sab_project_id)
                    values["position_code"] = f"NTG {values['ntg_number']}"
            mapping = Mapping.create(values)
            created += 1

        if not mapping:
            continue

        desired_position = mapping.position_code
        desired_ntg = mapping.is_ntg
        if entered_position == desired_position and line.is_ntg == desired_ntg:
            continue

        if order.state in ("draft", "sent"):
            cr.execute(
                "UPDATE sab_offer_calculation_line SET lv_position = %s, is_ntg = %s WHERE id = %s",
                [desired_position, desired_ntg, line.id],
            )
            aligned += 1
        elif entered_position and entered_position != desired_position:
            conflicts += 1
            _logger.warning(
                "SAB-P LV migration: historical conflict in order %s, line %s: %s != project mapping %s",
                order.sab_offer_reference or order.name,
                line.id,
                entered_position,
                desired_position,
            )

    if aligned:
        lines.invalidate_recordset(["lv_position", "is_ntg"])
    _logger.info(
        "SAB-P LV migration: created %s mappings, aligned %s editable lines, found %s historical conflicts",
        created,
        aligned,
        conflicts,
    )
