# Odoo.sh-Buildstatus und GitHub-CI – SAB-P Suite

**Aktuelle technische Prüfung: 18.11.2026.** Dies ist eine Statusdokumentation, keine Odoo.sh-Freigabe.

## Branch und Codebasis

- Repository: `spreyer-prog/sab-p`
- Entwicklungsbranch: `agent/leitfaden-gesamtstand`
- Letzter bei dieser Prüfung gelesener **Code-/CI-Stand**: `1a2e21ebcd29ed7e8a30f9aa601f1867d5c6d312` (17.11.2026)
- Modulversion laut `addons/sab_project/__manifest__.py`: **`19.0.5.113.0`**
- `main`: `28056e70766fdbb9072b23b2a9679dcdb307a902`; bei dieser Prüfung unverändert.

## Verifizierte Ergebnisse (nicht verwechseln)

| Prüfsystem | Stand | Ergebnis / Nachweis |
| --- | --- | --- |
| GitHub Actions: isolierte Python-/JavaScript-Regressionen | Code-/CI-Commit `1a2e21e` | **Erfolgreich** am 17.11.2026: 54 isolierte Python-Tests, 8 Node-Tests und 32 weitere isolierte Frontend-Prüfungen. [Workflow-Lauf](https://github.com/spreyer-prog/sab-p/actions/runs/44088463318) |
| GitHub Commit Statuses: `ci/odoo.sh (dev)` | `1a2e21e`, vorheriger Code-Commit `44eb6eb` | **Keine Statusmeldungen vorhanden**. Dies beweist weder einen grünen noch einen fehlgeschlagenen Odoo.sh-Build. |
| Odoo.sh-Lauf / Datenbankupgrade / Odoo-Integrationstests | aktuelle Modulversion `19.0.5.113.0` | **Nicht verifiziert**: kein direkter Zugriff auf Odoo.sh-Buildlogs und kein erfolgreicher Odoo.sh-Status des aktuellen Entwicklungscommits verfügbar. |
| Odoo.sh `ci/odoo.sh (production)` auf `main` | `28056e7` (08.08.2026) | GitHub liefert **`success`** für diesen historischen Produktionscommit. Das ist **keine** Abnahme des Entwicklungsbranches. |
| Älterer Odoo.sh-Entwicklungsstand | `19.0.5.35.0` (historische Abnahme) und Basisstand vom 20.08.2026 | Die älteren grünen Prüfergebnisse sind in `docs/BRANCH_ABNAHME.md` und `docs/LEITFADEN_GESAMTSTAND.md` dokumentiert; sie bestätigen **nicht** die aktuelle Version. |

### Grenzen der Schnelltests

Die isolierten Tests prüfen Syntax, Materiallogik und Frontend-Verträge mit Mocks. Sie starten **weder Odoo 19 noch PostgreSQL**, führen **kein Modulupgrade** und **keine** echten Odoo-`TransactionCase`-Tests aus. Ein grüner GitHub-Actions-Workflow darf niemals als grüner Odoo.sh-Build ausgegeben werden.

## Konkreter Blocker und Prüfweg

1. In [Odoo.sh Builds](https://www.odoo.sh/project/spreyer-prog-sab-p/builds) den Branch `agent/leitfaden-gesamtstand` und dessen zuletzt tatsächlich gebauten Git-SHA ermitteln.
2. Den neuesten Build auf **success/error/failure**, Upgrade-Ergebnis, Odoo-19-Tests und Log-Warnings prüfen. Bei Fehlern den ersten ursächlichen Traceback und betroffene Modul-/Datenbankoperation notieren.
3. Falls der Odoo.sh-Build grün ist, aber GitHub unter `ci/odoo.sh (dev)` keinen Commitstatus erhält: Odoo.sh-Branch-/Statusintegration, App-/Token-Rechte (`Commit statuses: Read and write`), GitHub-Zugriff und Webhook prüfen. Der konkrete Grund ist bislang **nicht nachgewiesen**.
4. Erst wenn der aktuelle Entwicklungs-**Code**-Commit durch einen echten Odoo.sh-Lauf grün bestätigt ist, weitere riskante Odoo-Modell-/View-/Migrationsänderungen vornehmen und nach jedem Schritt den neuen Build wieder bestätigen.
5. Keine ungeprüfte Produktivänderung, kein automatischer Merge nach `main`. Die praktische Produktivabnahme erfolgt separat anhand `docs/PRODUKTIVSETZUNG_CHECKLISTE.md`.

## Historie

Am 16.08.2026 war die Rückmeldung von Odoo.sh-Commitstatus an GitHub als aktiviert dokumentiert. Zu diesem Zeitpunkt waren eine auf `sab-p` begrenzte Berechtigung `Commit statuses: Read and write` und der Entwicklungsbranch `agent/leitfaden-gesamtstand` vermerkt. Diese historische Dokumentation ersetzt keine aktuelle Berechtigungs- oder Funktionsprüfung; keine Tokens oder Zugangsdaten sind hier abgelegt.

## Codeprüfung 21.11.2026 – noch nicht laufzeitbestätigtes Dispositionsrisiko

**Prüfbefund (Quellcodeanalyse, kein Odoo-Integrationstest):** Bei mehreren offenen Materialanforderungen für **dasselbe Produkt** kann die **ausdrücklich angewählte** Mindestbestandsauffüllung möglicherweise mehrfach in Bestellvorschlägen berücksichtigt werden. In `addons/sab_project/models/sab_minimum_stock_fix.py` berechnet `_compute_minimum_stock_replenishment` den Produkt-Mindestbestandsfehlbetrag pro Anforderung aus dem gemeinsamen Produktbestand und den offenen Bedarfen. `addons/sab_project/models/sab_minimum_stock.py`, Methode `_sab_policy_order_quantity`, addiert diesen Wert bei aktivierter `include_minimum_stock_replenishment`-Option **für jede Anforderung einzeln**. Die vorhandenen `test_minimum_stock_and_delivery_overdue.py`-Tests legen jeweils nur **eine** Materialanforderung an; ein Test mit zwei Anforderungen desselben Produkts fehlt.

**Rechenbeispiel zur Reproduktion (hypothetisch, nicht als Datenbank-Istwert behauptet):** Produkt A: zwei offene Anforderungen mit jeweils 6 Stück Fehlbestand, frei verfügbar 0, unbestellt, Mindestbestand 5. Gesamter Projektfehlbestand 12 Stück; einmalige optionale Mindestbestandsauffüllung 5 Stück, also insgesamt 17 Stück. Wenn beide Anforderungen jeweils den gesamten Auffüllwert 5 addieren, ergeben sich zwei Vorschläge à 11 Stück = 22 Stück, also 5 Stück zu viel.

**Verbindlicher Prüf- und Abnahmeschritt nach Wiederherstellung eines echten Odoo.sh-Buildnachweises:**
1. In einem `TransactionCase` zwei offene Anforderungen für dasselbe Produkt, unterschiedliche Schränke/Projekte und eine gemeinsame Mindestbestandsregel erzeugen.
2. Ohne aktivierte Auffüllung exakt den realen Fehlbestand pro Position prüfen (keine automatische Rundung).
3. Auffüllung einmal und bei beiden Positionen aktivieren; die **gesamte** optional aufgefüllte Bestellmenge darf den gemeinsam berechneten Mindestbestandsfehlbetrag nur **einmal** zusätzlich zum Projektfehlbestand enthalten.
4. Bereits bestellte, teilweise empfangene und zurückgesendete Mengen sowie unterschiedliche Lieferanten als weitere Fälle prüfen; Projekt-/Schrankzuordnung und historische Preise müssen erhalten bleiben.
5. Erst nach bestandenem Odoo-19-Integrationstest und neuem grünen Odoo.sh-Build eine technische Korrektur als verifiziert bezeichnen.

**Status:** Verdachtsfall dokumentiert; **kein** Odoo-Modellcode, keine Bestellungen und keine Produktivdaten geändert. Die isolierten GitHub-Actions-Tests decken diese Mehrfachkonstellation derzeit nicht ab.
