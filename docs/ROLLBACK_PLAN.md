# SAB-P Suite V1 – Rollback-Plan

## Referenzpunkt vor V1-Merge

Beim dokumentierten Abgleich stand `main` auf:

`28056e70766fdbb9072b23b2a9679dcdb307a902` – `Version 0.7.8.2 - Remove invalid language setup`

Dieser Commit ist der technische Code-Referenzpunkt vor dem späteren V1-Merge. Der Entwicklungsbranch `agent/leitfaden-gesamtstand` war beim Vergleich 325 Commits voraus und 0 Commits hinter `main`; der Merge-Base entsprach diesem `main`-Commit.

## Zwingende Regel

Ein Code-Rollback ersetzt keinen Datenbank-Rollback. Nach einem Modulupgrade können Schema, Daten oder Migrationen verändert sein. Deshalb muss unmittelbar vor dem Produktivupgrade ein belastbares Odoo.sh-Datenbankbackup vorhanden sein.

## Vorgehen bei fehlgeschlagenem Produktivupgrade

1. Produktivsystem nicht mit weiteren Schreibvorgängen belasten.
2. Fehlgeschlagenen Build/Upgrade-Stand und Zeitpunkt dokumentieren.
3. Produktivdatenbank aus dem unmittelbar vor dem Upgrade erzeugten Backup wiederherstellen.
4. Code auf den vor dem Merge dokumentierten stabilen Stand bzw. auf den ausdrücklich freigegebenen letzten Produktivcommit zurückführen.
5. Datenbank und Code gemeinsam starten; niemals nur den Code zurückdrehen und eine bereits migrierte Datenbank ungeprüft weiterverwenden.
6. Smoke-Test durchführen: Anmeldung, Projektliste, bestehende Projekte, Angebot, zentrale Stammdaten und Dokumentzugriff.
7. Erst nach erfolgreichem Smoke-Test wieder für Benutzer freigeben.

## Noch praktisch zu verifizieren

Vor dem echten Go-live muss der Ablauf einmal auf einer nicht produktiven Kopie mit echter Backup-Wiederherstellung durchgespielt werden. Erst dann darf der Punkt „Rollback praktisch verifiziert“ in der Produktivsetzungscheckliste als erledigt markiert werden.
