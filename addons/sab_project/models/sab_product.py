from odoo import fields, models


class SabProduct(models.Model):
    _name = "sab.product"
    _description = "SAB-P Produkt"
    _order = "manufacturer_id, manufacturer_article_number, name"
    _rec_name = "name"

    # ---------------------------------------------------------
    # Grunddaten
    # ---------------------------------------------------------

    active = fields.Boolean(
        string="Aktiv",
        default=True,
    )


    
    product_type = fields.Selection(
        selection=[
            ("material", "Material"),
            ("mechanical", "Mechanik"),
            ("wiring", "Verdrahtung"),
            ("testing", "Prüfung"),
            ("labeling", "Beschriftung"),
            ("documentation", "Dokumentation"),
            ("transport", "Transport"),
            ("packaging", "Verpackung"),
            ("other", "Sonstiges"),
        ],
        string="Produkttyp",
        required=True,
        default="material",
        index=True,
    )
    name = fields.Char(
        string="Bezeichnung",
        required=True,
        index=True,
    )

    manufacturer_id = fields.Many2one(
        comodel_name="sab.manufacturer",
        string="Hersteller",
        ondelete="restrict",
        index=True,
    )

    manufacturer_article_number = fields.Char(
        string="Herstellerartikelnummer",
        index=True,
    )

    datanorm_number = fields.Char(
        string="DATANORM-Nummer",
        index=True,
    )

    # ---------------------------------------------------------
    # Absolute technische Kalkulationswerte des Produktes
    #
    # Diese Werte gehören zum echten Produkt.
    # Der Kalkulationsartikel enthält dagegen nur Faktoren.
    # ---------------------------------------------------------

    space_units = fields.Float(
        string="Platzeinheiten",
        default=0.0,
    )

    mechanical_time_minutes = fields.Float(
        string="Mechanikzeit in Minuten",
        default=0.0,
    )

    wiring_time_minutes = fields.Float(
        string="Verdrahtungszeit in Minuten",
        default=0.0,
    )

    testing_time_minutes = fields.Float(
        string="Prüfzeit in Minuten",
        default=0.0,
    )

    # ---------------------------------------------------------
    # Interne Hinweise
    # ---------------------------------------------------------

    notes = fields.Text(
        string="Interne Hinweise",
    )