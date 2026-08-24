import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Prepare multi-BOM switchboard structure and backfill Odoo product links."""
    cr.execute(
        """
        SELECT c.conname
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
         WHERE t.relname = 'sab_project_bom'
           AND c.contype = 'u'
           AND pg_get_constraintdef(c.oid) = 'UNIQUE (order_id)'
        """
    )
    for (constraint_name,) in cr.fetchall():
        cr.execute(
            sql.SQL("ALTER TABLE sab_project_bom DROP CONSTRAINT {}").format(
                sql.Identifier(constraint_name)
            )
        )
        _logger.info("Dropped legacy one-BOM-per-order constraint %s", constraint_name)

    cr.execute(
        """
        UPDATE sab_project_bom
           SET bom_scope = COALESCE(bom_scope, 'total'),
               scope_key = COALESCE(NULLIF(scope_key, ''), 'total')
        """
    )

    cr.execute(
        """
        UPDATE sab_project_bom_line bl
           SET odoo_product_id = p.odoo_product_id
          FROM sab_product p
         WHERE bl.product_id = p.id
           AND bl.odoo_product_id IS NULL
           AND p.odoo_product_id IS NOT NULL
        """
    )
