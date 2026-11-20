import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _component_signature(section):
    children = section.child_line_ids.filtered(
        lambda line: line.line_type == "item"
        and (line.calculation_item_id or line.odoo_product_id)
    ).sorted(key=lambda line: (line.sequence, line.id))
    return tuple(
        (
            "calculation" if child.calculation_item_id else "product",
            child.calculation_item_id.id or child.odoo_product_id.id,
            round(child.quantity or 0.0, 6),
        )
        for child in children
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Order = env["sale.order"].sudo()
    Mapping = env["sab.project.lv.mapping"].sudo()
    Line = env["sab.offer.calculation.line"].sudo()
    Bom = env["sab.project.bom"].sudo()

    # Existing sent quotations and customer orders were already treated as the
    # binding project basis before the explicit release button was introduced.
    released_orders = Order.search(
        [
            ("sab_project_id", "!=", False),
            ("state", "in", ("sent", "sale", "done")),
        ]
    )
    if released_orders:
        cr.execute(
            """
            UPDATE sale_order
               SET sab_offer_release_state = 'released',
                   sab_offer_released_at = COALESCE(sab_offer_released_at, write_date),
                   sab_offer_released_by_id = COALESCE(sab_offer_released_by_id, write_uid)
             WHERE id = ANY(%s)
            """,
            [released_orders.ids],
        )
        Order.invalidate_model(
            [
                "sab_offer_release_state",
                "sab_offer_released_at",
                "sab_offer_released_by_id",
            ]
        )

    # A mapping created only from an unreleased draft must no longer reserve a
    # project position. Keep it only if the same position is demonstrably used
    # by another explicitly released offer.
    removed_mappings = 0
    reassigned_mappings = 0
    for mapping in Mapping.search([]):
        if (
            mapping.first_order_id
            and mapping.first_order_id.sab_offer_release_state == "released"
            and mapping.first_order_id.state != "cancel"
        ):
            continue
        domain = [
            ("order_id.sab_project_id", "=", mapping.project_id.id),
            ("order_id.sab_offer_release_state", "=", "released"),
            ("order_id.state", "!=", "cancel"),
            ("line_type", "=", "item"),
            ("parent_section_id", "=", False),
            ("lv_position", "=", mapping.position_code),
        ]
        if mapping.calculation_item_id:
            domain.append(
                ("calculation_item_id", "=", mapping.calculation_item_id.id)
            )
        else:
            domain.append(("odoo_product_id", "=", mapping.odoo_product_id.id))
        released_line = Line.search(domain, order="order_id, sequence, id", limit=1)
        if released_line:
            mapping.write({"first_order_id": released_line.order_id.id})
            reassigned_mappings += 1
        else:
            mapping.unlink()
            removed_mappings += 1

    # Link historical duplicate component occurrences to one project identity.
    grouped_sections = {}
    linked_sections = 0
    sections = Line.search(
        [
            ("line_type", "=", "section"),
            ("order_id.sab_project_id", "!=", False),
            ("order_id.state", "!=", "cancel"),
        ],
        order="order_id, sequence, id",
    )
    for section in sections:
        position = (section.lv_position or "").strip()
        if not position:
            continue
        key = (
            section.order_id.sab_project_id.id,
            position,
            (section.description or "").strip().casefold(),
            _component_signature(section),
        )
        origin = grouped_sections.get(key)
        if not origin:
            grouped_sections[key] = section.component_origin_id or section
            continue
        if section.component_origin_id != origin:
            section.with_context(
                sab_offer_release_write=True,
                sab_inherit_section_position=True,
                skip_section_normalize=True,
                skip_sale_line_sync=True,
            ).write({"component_origin_id": origin.id})
            linked_sections += 1

    # Existing released total BOMs must also appear in the new procurement
    # dashboard. The operation is idempotent and preserves order/receipt history.
    pushed_boms = 0
    for bom in Bom.search(
        [
            ("state", "=", "released"),
            ("bom_scope", "=", "total"),
        ]
    ):
        try:
            bom._sab_push_to_procurement_workspace()
            pushed_boms += 1
        except Exception:
            _logger.exception(
                "Could not initialize procurement workspace for BOM %s",
                bom.display_name,
            )

    _logger.info(
        "SAB-P 19.0.5.53.0 migration: released %s legacy offers, "
        "reassigned %s mappings, removed %s draft mappings, linked %s component "
        "duplicates and initialized %s procurement workspaces",
        len(released_orders),
        reassigned_mappings,
        removed_mappings,
        linked_sections,
        pushed_boms,
    )
