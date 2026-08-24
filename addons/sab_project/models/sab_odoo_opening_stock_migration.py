from odoo import models
from odoo.tools.float_utils import float_is_zero


class SabSupplierProductOdooOpeningStockMigration(models.Model):
    _inherit = "sab.supplier.product"

    def init(self):
        super().init()

        # On a completely fresh module installation Odoo calls model init()
        # while SAB-P's own tables are still being created. In that situation
        # there is no legacy stock to migrate and sab_stock_movement does not
        # exist yet. Never let an optional migration block the whole registry.
        self.env.cr.execute("SELECT to_regclass('public.sab_stock_movement')")
        if not self.env.cr.fetchone()[0]:
            return

        company = self.env.company
        parameter_key = (
            f"sab_project.odoo_opening_stock_migrated_v1_company_{company.id}"
        )
        parameters = self.env["ir.config_parameter"].sudo()
        if parameters.get_param(parameter_key):
            return

        warehouse = self.env["stock.warehouse"].sudo().search(
            [("company_id", "=", company.id)],
            order="id",
            limit=1,
        )
        if not warehouse:
            return

        self.env.cr.execute(
            """
            SELECT movement.odoo_product_id AS product_id,
                   ARRAY_AGG(DISTINCT movement.unit) AS units,
                   SUM(
                       CASE movement.movement_type
                           WHEN 'receipt' THEN movement.quantity
                           WHEN 'issue' THEN -movement.quantity
                           ELSE 0
                       END
                   ) AS quantity
              FROM sab_stock_movement movement
             WHERE movement.odoo_product_id IS NOT NULL
               AND movement.movement_type IN ('receipt', 'issue')
             GROUP BY movement.odoo_product_id
            """
        )
        balances = self.env.cr.dictfetchall()
        Product = self.env["product.product"].sudo()
        Quant = self.env["stock.quant"].sudo()
        StockMove = self.env["stock.move"].sudo()
        unit_map = {
            "pcs": self.env.ref("uom.product_uom_unit"),
            "m": self.env.ref("uom.product_uom_meter"),
            "kg": self.env.ref("uom.product_uom_kgm"),
        }

        skipped = []
        migrated = 0
        for balance in balances:
            product = Product.browse(balance["product_id"]).exists()
            units = balance["units"] or []
            if not product or len(units) != 1 or units[0] not in unit_map:
                skipped.append(balance["product_id"])
                continue

            target_uom = unit_map[units[0]]
            template = product.product_tmpl_id
            if template.uom_id != target_uom:
                if StockMove.search_count([("product_id", "=", product.id)]):
                    skipped.append(product.id)
                    continue
                template.write({"uom_id": target_uom.id})
            if not template.is_storable:
                template.is_storable = True

            desired_quantity = balance["quantity"] or 0.0
            current_quantity = product.with_context(
                location=warehouse.lot_stock_id.id,
            ).qty_available
            difference = desired_quantity - current_quantity
            if float_is_zero(
                difference,
                precision_rounding=product.uom_id.rounding,
            ):
                continue

            Quant._update_available_quantity(
                product,
                warehouse.lot_stock_id,
                quantity=difference,
            )
            migrated += 1

        parameters.set_param(parameter_key, "1")
        self.env["ir.logging"].sudo().create(
            {
                "name": "SAB-P Odoo-Lagerübernahme",
                "type": "server",
                "dbname": self.env.cr.dbname,
                "level": "INFO" if not skipped else "WARNING",
                "message": (
                    f"Einmalige Lagerübernahme abgeschlossen: {migrated} "
                    f"Produkt(e) angepasst, {len(skipped)} Produkt(e) wegen "
                    "unklarer oder bereits verwendeter Mengeneinheit übersprungen."
                ),
                "path": __name__,
                "func": "init",
                "line": "0",
            }
        )
