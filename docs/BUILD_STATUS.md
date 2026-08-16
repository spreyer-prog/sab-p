# Odoo.sh Build-Status

Stand: 16.08.2026

Für das Odoo.sh-Projekt ist die Rückmeldung von Build-Status auf GitHub aktiviert.

- Repository: `spreyer-prog/sab-p`
- Entwicklungsbranch: `agent/leitfaden-gesamtstand`
- GitHub-Berechtigung: Commit statuses `Read and write`
- Scope des Tokens: ausschließlich Repository `sab-p`
- Token selbst wird nicht im Repository gespeichert.

## Ziel

Neue Odoo.sh Builds sollen ihren Commit-Status an GitHub zurückmelden. Damit kann der Entwicklungsstand nach jedem Push über den zugehörigen GitHub-Commit auf `pending`, `success`, `failure` oder `error` geprüft werden.

## Vorgehen bei rotem Status

1. Keine weiteren Komfortfunktionen hinzufügen.
2. Odoo.sh Buildfehler priorisiert auswerten.
3. Errors und Failures zuerst beheben.
4. Danach SAB-P bezogene Warnings beseitigen.
5. Erneut pushen und nächsten Status prüfen.

## Freigaberegel

Ein Merge nach `main` erfolgt erst nach grünem Build, praktischem Smoke-Test und abgeschlossener V1-Abnahme gemäß `PRODUKTIVSETZUNG_CHECKLISTE.md`.
