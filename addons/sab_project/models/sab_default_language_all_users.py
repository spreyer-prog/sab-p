from odoo import api, models


class ResUsersSabDefaultGerman(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            # Neue interne/Portal-Benutzer starten in SAB-P immer auf Deutsch.
            # Eine spätere bewusste Benutzeränderung bleibt weiterhin möglich.
            vals.setdefault("lang", "de_DE")
            prepared.append(vals)
        return super().create(prepared)

    def init(self):
        # Auch vorhandene Benutzer einer neu aufgebauten Odoo.sh-Datenbank
        # müssen schon beim ersten Login Deutsch verwenden. res.users.lang wird
        # über den Partner gespeichert; SQL vermeidet Abhängigkeiten von der
        # Reihenfolge, in der Demo-Benutzer und SAB-P-Daten geladen werden.
        self.env.cr.execute(
            """
            UPDATE res_partner p
               SET lang = 'de_DE'
              FROM res_users u
             WHERE u.partner_id = p.id
               AND COALESCE(p.lang, '') <> 'de_DE'
            """
        )
