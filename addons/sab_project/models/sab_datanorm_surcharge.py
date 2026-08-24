from odoo import fields, models


class SabDatanormSurcharge(models.Model):
    _name = "sab.datanorm.surcharge"
    _description = "SAB-P DATANORM Zu-/Abschlag"
    _order = "supplier_product_id, record_number, id"

    supplier_product_id = fields.Many2one(
        comodel_name="sab.supplier.product",
        string="Lieferantenartikel",
        required=True,
        ondelete="cascade",
        index=True,
    )
    supplier_id = fields.Many2one(
        related="supplier_product_id.supplier_id",
        string="Lieferant",
        store=True,
        index=True,
    )
    product_id = fields.Many2one(
        related="supplier_product_id.product_id",
        string="SAB-P Produkt",
        store=True,
        index=True,
    )
    datanorm_article_number = fields.Char(
        string="DATANORM-Artikelnummer",
        required=True,
        index=True,
    )
    record_number = fields.Char(
        string="Z-Satz Nummer",
        index=True,
    )
    surcharge_code = fields.Char(
        string="Zuschlagsart",
        index=True,
        help="Kennung aus dem DATANORM-Z-Satz, z. B. CU für Kupfer.",
    )
    raw_record = fields.Text(
        string="Original DATANORM-Z-Satz",
        required=True,
        help=(
            "Der Z-Satz wird vollständig und verlustfrei gespeichert. "
            "Eine automatische Preiswirkung erfolgt erst, wenn die jeweilige "
            "Zuschlagslogik fachlich eindeutig definiert ist."
        ),
    )
    source_date = fields.Date(string="Datenstand")
