# SAB-P Suite V1 – Branch-Abnahme

Stand dieser Abnahme: Entwicklungsbranch `agent/leitfaden-gesamtstand` auf Basis des zuletzt bestätigten grünen Odoo.sh-Stands der Modulversion `19.0.5.35.0`.

## Technisch bestätigter Stand

- Odoo.sh Commit-Status `ci/odoo.sh (dev)` ist eingerichtet und der zuletzt bestätigte Härtungsstand war grün.
- Der Entwicklungsbranch basiert direkt auf `main` und ist gegenüber `main` ausschließlich voraus; beim dokumentierten Vergleich war er 325 Commits voraus und 0 Commits zurück.
- `main` stand beim Abgleich unverändert auf Commit `28056e70766fdbb9072b23b2a9679dcdb307a902` (`Version 0.7.8.2 - Remove invalid language setup`).
- Die automatisierten SAB-P Tests decken Nummerierung, Kalkulation/Snapshots, DATANORM, Einkauf/Lager, Fertigung, Mitarbeiterrechte, Dokumente, Portaltrennung, Zeiten, Nachkalkulation und End-to-End-Ablauf ab.
- Für die Nachkalkulation sind Listen-, Pivot- und Diagrammansicht vorhanden; ein UI-Vertragstest schützt diese Ansichten gegen versehentliche Entfernung zentraler Kennzahlen.

## Noch nicht als Produktivabnahme erledigt

Diese Branch-Abnahme ersetzt keine reale Produktivabnahme. Vor einem Merge nach `main` bleiben insbesondere offen:

- Upgrade des Moduls auf einer Kopie einer bestehenden produktionsnahen Datenbank,
- Datenbankbackup unmittelbar vor dem Produktivupgrade,
- reale Nummernkreis- und Kalkulationsparameter,
- realer ABB-DATANORM-Import und Preisabgleich,
- reale Mitarbeiter, Arbeitsbereiche und Zugänge,
- Smartphone-/Tablet-Praxistest,
- zwei reale Kundenportal-Testkonten,
- reales Musterprojekt inklusive Nachkalkulation,
- praktischer Rollback-Test mit Datenbankwiederherstellung.

## Merge-Gate

Ein Merge nach `main` ist erst freigegeben, wenn der dann aktuelle Branch-Head einen grünen `ci/odoo.sh (dev)` Status besitzt und die produktionsrelevanten offenen Punkte der `PRODUKTIVSETZUNG_CHECKLISTE.md` abgearbeitet sind. Bei einem roten Build darf nicht gemergt werden.
