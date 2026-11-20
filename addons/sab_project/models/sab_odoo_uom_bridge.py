from odoo import models


class SabSupplierProductOdooUomBridge(models.Model):
    _inherit = "sab.supplier.product"

    def _sab_odoo_uom(self):
        self.ensure_one()
        xmlid = {
            "m": "uom.product_uom_meter",
            "kg": "uom.product_uom_kgm",
            "pcs": "uom.product_uom_unit",
            "set": "uom.product_uom_unit",
            "pack": "uom.product_uom_unit",
            "other": "uom.product_uom_unit",
        }.get(self.unit or "pcs", "uom.product_uom_unit")
        return self.env.ref(xmlid)

    def _sab_sync_product_uom(self):
        StockMove = self.env["stock.move"].sudo()
        for supplier_product in self.filtered("active"):
            product = (
                supplier_product.odoo_product_id
                or supplier_product.product_id.odoo_product_id
            )
            if not product:
                continue
            target_uom = supplier_product._sab_odoo_uom()
            template = product.product_tmpl_id.sudo()
            if template.uom_id == target_uom:
                continue
            if StockMove.search_count([("product_id", "=", product.id)]):
                # Odoo schützt bereits verwendete Mengeneinheiten. Die
                # Bestellerzeugung prüft später, ob die vorhandene Einheit zur
                # SAB-P-Position passt, statt historische Bewegungen umzubauen.
                continue
            template.write({"uom_id": target_uom.id})
        return True

    def _sab_sync_supplierinfo(self):
        self._sab_sync_product_uom()
        return super()._sab_sync_supplierinfo()

    def init(self):
        super().init()
        unit_uom = self.env.ref("uom.product_uom_unit").id
        meter_uom = self.env.ref("uom.product_uom_meter").id
        kilogram_uom = self.env.ref("uom.product_uom_kgm").id
        self.env.cr.execute(
            """
            WITH selected_unit AS (
                SELECT DISTINCT ON (supplier_product.odoo_product_id)
                       supplier_product.odoo_product_id,
                       supplier_product.unit
                  FROM sab_supplier_product supplier_product
                 WHERE supplier_product.active
                   AND supplier_product.odoo_product_id IS NOT NULL
                 ORDER BY supplier_product.odoo_product_id,
                          supplier_product.preferred DESC,
                          supplier_product.id
            )
            UPDATE product_template template
               SET uom_id = CASE selected_unit.unit
                                WHEN 'm' THEN %s
                                WHEN 'kg' THEN %s
                                ELSE %s
                            END
              FROM selected_unit
              JOIN product_product product
                ON product.id = selected_unit.odoo_product_id
             WHERE template.id = product.product_tmpl_id
               AND NOT EXISTS (
                    SELECT 1
                      FROM stock_move movement
                     WHERE movement.product_id = product.id
               )
            """,
            (
                meter_uom,
                kilogram_uom,
                unit_uom,
            ),
        )
