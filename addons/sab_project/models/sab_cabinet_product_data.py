from odoo import fields, models


class ProductTemplateSabCabinetData(models.Model):
    _inherit = "product.template"

    sab_is_cabinet_product = fields.Boolean(
        string="Schrank / Gehäuse",
        default=False,
        index=True,
        help="Kennzeichnet Produkte, die als physischer Schaltschrank bzw. Gehäuse verwendet werden.",
    )
    sab_cabinet_width_mm = fields.Float(
        string="Schrankbreite (mm)",
        digits=(16, 1),
    )
    sab_nameplate_type_designation = fields.Char(
        string="Typenbezeichnung Typenschild",
    )
    sab_nameplate_cabinet_type = fields.Char(
        string="Schranktyp Typenschild",
    )
    sab_nameplate_standard_family = fields.Char(
        string="DIN EN",
        default="61439",
    )
    sab_nameplate_standard_part = fields.Char(
        string="Normteil",
        default="3",
    )
    sab_nameplate_rated_voltage = fields.Float(
        string="Bemessungsspannung (V)",
        default=400.0,
    )
    sab_nameplate_rated_current = fields.Float(
        string="Bemessungsstrom (A)",
        default=100.0,
    )
    sab_nameplate_frequency = fields.Float(
        string="Frequenz (Hz)",
        default=50.0,
    )
    sab_nameplate_busbar_current = fields.Float(
        string="Sammelschienenstrom (A)",
    )
    sab_nameplate_protection_class = fields.Char(
        string="Schutzklasse",
        default="2",
    )
    sab_nameplate_ip_rating = fields.Char(
        string="IP-Schutzart",
    )
    sab_nameplate_notes = fields.Text(
        string="Hinweise Typenschild / Schrank",
    )
