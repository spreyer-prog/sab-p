import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Apply one simple rule to editable offers: one position per Bauteil.

    Existing child rows inherit the LV-/NTG-position of their Bauteil. Provisional
    NTG mappings that were created only for such child rows are removed, while
    genuine direct project positions remain untouched.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute(
        """
        UPDATE sab_offer_calculation_line AS section
           SET is_ntg = TRUE
          FROM sale_order AS order_record
         WHERE section.order_id = order_record.id
           AND order_record.state IN ('draft', 'sent')
           AND section.line_type = 'section'
           AND section.lv_position IS NOT NULL
           AND UPPER(BTRIM(section.lv_position)) LIKE 'NTG %%'
           AND section.is_ntg = FALSE
        """
    )
    marked_sections = cr.rowcount

    cr.execute(
        """
        UPDATE sab_offer_calculation_line AS child
           SET lv_position = section.lv_position,
               is_ntg = section.is_ntg
          FROM sab_offer_calculation_line AS section,
               sale_order AS order_record
         WHERE child.parent_section_id = section.id
           AND child.order_id = order_record.id
           AND order_record.state IN ('draft', 'sent')
           AND child.line_type = 'item'
           AND (
                child.lv_position IS DISTINCT FROM section.lv_position
                OR child.is_ntg IS DISTINCT FROM section.is_ntg
           )
        """
    )
    aligned_children = cr.rowcount

    Line = env["sab.offer.calculation.line"].sudo()
    Mapping = env["sab.project.lv.mapping"].sudo()
    Line.invalidate_model(["lv_position", "is_ntg"])

    removed_mappings = 0
    provisional = Mapping.search([
        ("is_ntg", "=", True),
        ("first_order_id.state", "in", ("draft", "sent")),
    ])
    for mapping in provisional:
        source_domain = []
        if mapping.calculation_item_id:
            source_domain.append(("calculation_item_id", "=", mapping.calculation_item_id.id))
        elif mapping.odoo_product_id:
            source_domain.append(("odoo_product_id", "=", mapping.odoo_product_id.id))
        else:
            continue

        child = Line.search([
            ("order_id", "=", mapping.first_order_id.id),
            ("line_type", "=", "item"),
            ("parent_section_id", "!=", False),
            *source_domain,
        ], limit=1)
        if not child or not child.parent_section_id.lv_position:
            continue
        if child.parent_section_id.lv_position == mapping.position_code:
            continue

        direct_use = Line.search_count([
            ("order_id.sab_project_id", "=", mapping.project_id.id),
            ("line_type", "=", "item"),
            ("parent_section_id", "=", False),
            ("lv_position", "=", mapping.position_code),
            *source_domain,
        ])
        if direct_use:
            continue

        mapping.unlink()
        removed_mappings += 1

    _logger.info(
        "SAB-P Bauteil migration: marked %s NTG sections, aligned %s child rows, "
        "removed %s provisional child mappings",
        marked_sections,
        aligned_children,
        removed_mappings,
    )
