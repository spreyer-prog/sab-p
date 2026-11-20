from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    products = env["sab.product"].with_context(active_test=False).search([])
    # Batchweise synchronisieren, damit bereits importierte DATANORM-Produkte nach dem
    # Upgrade sofort im normalen Odoo-Produktstamm verfügbar sind.
    batch_size = 1000
    for offset in range(0, len(products), batch_size):
        products[offset:offset + batch_size]._sync_to_odoo_product()
