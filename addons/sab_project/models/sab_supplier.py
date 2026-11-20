from odoo import fields, models


class SabSupplier(models.Model):
    _name = "sab.supplier"
    _description = "SAB-P Lieferant"
    _order = "name"
    _rec_name = "name"

    active = fields.Boolean(string="Aktiv", default=True)
    name = fields.Char(string="Lieferant", required=True, index=True)
    supplier_number = fields.Char(string="Lieferantennummer", index=True)
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Kontakt-/Adressstamm",
        ondelete="restrict",
        index=True,
        help="Verknüpfter Odoo-Kontakt für Adresse, Ansprechpartner und Bankverbindungen.",
    )
    datanorm_identifier = fields.Char(string="DATANORM-Kennung", index=True)
    datanorm_price_as_purchase_price = fields.Boolean(
        string="DATANORM-Preis als EK übernehmen",
        default=False,
        help=(
            "Nur aktivieren, wenn fachlich geklärt ist, dass der im DATANORM-"
            "A-Satz gelieferte Preis für diesen Lieferanten als kalkulationswirksamer "
            "Einkaufspreis verwendet werden darf. Der rohe DATANORM-Preis wird "
            "unabhängig davon immer gespeichert."
        ),
    )
    website = fields.Char(string="Website")
    note = fields.Text(string="Interne Hinweise")
