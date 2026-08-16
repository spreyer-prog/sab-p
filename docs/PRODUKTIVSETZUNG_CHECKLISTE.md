# SAB-P Suite V1 – Produktivsetzungs- und Abnahmecheckliste

Stand: letzter bestätigter Green Build auf `agent/leitfaden-gesamtstand`; aktueller Härtungsstand Modulversion `19.0.5.34.0` wird durch Odoo.sh erneut geprüft. GitHub-Commit-Status ist eingerichtet und liefert `ci/odoo.sh (dev)`.

Legende:
- `[x]` technisch im Code/Test abgedeckt bzw. im letzten Green Build nachgewiesen,
- `[ ]` benötigt noch aktuellen Build-, Upgrade-, Praxis- oder Fachdatenabgleich.

## A. Technische Abnahme

- [x] Letzter vollständig geprüfter Odoo.sh Build des Branches `agent/leitfaden-gesamtstand` erfolgreich.
- [ ] Aktuellen Stand `19.0.5.34.0` erneut durch Odoo.sh grün bestätigen.
- [x] Odoo.sh GitHub-Commit-Status eingerichtet; neue Builds sind über `ci/odoo.sh (dev)` verfolgbar.
- [ ] Modul `sab_project` auf einer bestehenden, produktionsnahen Datenbank explizit als Upgrade testen.
- [x] Keine SAB-P Testfehler im letzten vollständig geprüften Green Build: 57 Tests, 0 Failures, 0 Errors.
- [x] Im geprüften Build keine SAB-P bezogenen Warnings festgestellt.
- [x] Automatisierter End-to-End-Test vorhanden; aktueller Stand bindet Mitarbeiterprofile/Arbeitsbereiche ein.
- [x] Keine ungewollte Änderung an `main`.
- [ ] Datenbankbackup unmittelbar vor Produktivupgrade vorhanden.
- [ ] Rollback auf letzten stabilen `main`-Stand organisatorisch und technisch praktisch verifizieren.

## B. Nummernkreise

- [ ] Projektpräfix für Produktivbetrieb fachlich final bestätigen.
- [ ] Jahresdarstellung für Produktivbetrieb fachlich final bestätigen.
- [ ] Projektstellenanzahl für Produktivbetrieb fachlich final bestätigen.
- [ ] Angebotsstellenanzahl für Produktivbetrieb fachlich final bestätigen.
- [ ] Startnummer für Produktivbetrieb fachlich final bestätigen.
- [ ] Vorhandene Altprojekte ohne SAB-P Nummer für die reale Datenbank bewerten/nachnummerieren.
- [x] Automatischer Test: neues Projekt erhält erwartete `Axx.xxxx` Nummer.
- [x] Automatischer Test: erstes/zweites Angebot erhalten `-01`/`-02`.
- [x] Automatischer Test: Kalenderjahreswechsel führt zu getrenntem Jahreszähler und Reset `A26.000x` → `A27.0001`.
- [x] Automatischer Test: Präfix, Jahr, Trennzeichen, Stellen und Startnummer sind konfigurierbar.
- [x] Projektnummer ist in der SAB-P Projektübersicht verpflichtend erste Spalte.
- [x] Projektnummer ist zusätzlich in der normalen Odoo-Projektliste eingebunden.

## C. Kalkulation

- [ ] Globale Kalkulationsfaktoren fachlich freigegeben.
- [ ] Änderungsfreigabecode für Produktivbetrieb gesetzt und nur berechtigten Personen bekannt.
- [ ] Musterprojekt aus Alt-Excel 1:1 in Odoo nachgerechnet.
- [ ] Material-EK stimmt im realen Musterprojekt.
- [ ] Mechanik-/Verdrahtungs-/Prüfzeiten stimmen im realen Musterprojekt.
- [ ] Kalkulationsfaktoren fachlich geprüft.
- [ ] Kalkulatorischer Netto-Richtwert gegen Altsystem bewertet.
- [x] Snapshot-Verhalten mit nachträglicher Stammdatenänderung automatisiert geprüft.

## D. DATANORM

- [ ] Vollständiges reales ABB-DATANORM-Paket praktisch importieren.
- [x] Wiederholungsimport und Schutz technischer SAB-P Werte automatisiert geprüft.
- [ ] Lieferanten-EK-Freigabe praktisch mit realem Lieferanten prüfen.
- [ ] Z-Sätze im realen Paket identifizieren.
- [ ] Falls Z-Sätze/NE-Metall preiswirksam benötigt werden: fachliche Regel dokumentieren und umsetzen.

## E. Einkauf und Lager

- [x] Einkaufsbedarf aus freigegebener Stückliste automatisiert geprüft.
- [x] Optionale Positionen werden nicht automatisch disponiert.
- [x] Wareneingang erzeugt genau einen Lagerzugang.
- [x] Reservierung/Freigabe/Entnahme automatisiert geprüft.
- [x] Reservierter Bestand kann nicht ungewollt entnommen werden.
- [x] Historische Lagerbewertung automatisiert geprüft.
- [ ] Lageranfangsbestände je Produkt festlegen/importieren.
- [ ] Anfangsbewertung der Lagerbestände fachlich freigeben.

## F. Mitarbeiterverwaltung, Fertigung und Mitarbeiteroberfläche

- [x] Eigene SAB-P Mitarbeiterverwaltung technisch angelegt.
- [x] Mitarbeiterstammdaten enthalten Name, Login, E-Mail, Aktivstatus und verknüpften Odoo-Benutzer.
- [x] Arbeitsbereiche als eigene Stammdaten angelegt, u. a. Mechanische Fertigung, Mechanischer Aufbau, Elektrische Verdrahtung, Prüfung, Endkontrolle und Service/Montage.
- [x] Mitarbeiter können einem oder mehreren Arbeitsbereichen zugeordnet werden.
- [x] Rollenfelder für Mitarbeiter-App, Projektleiter und Kundenfreigaben vorhanden.
- [x] Odoo-Zugang kann aus dem SAB-P Mitarbeiterdatensatz angelegt, aktualisiert, eingeladen, deaktiviert und reaktiviert werden.
- [x] Fertigungsschritte sind mit Arbeitsbereichen verknüpft.
- [x] Auswahl/Übernahme eines Mitarbeiters wird auf passende Arbeitsbereiche geprüft.
- [x] Mitarbeiter-App zeigt Mitarbeiter und Arbeitsbereich am Fertigungsschritt.
- [x] Freie Arbeit ist serverseitig auf passende Arbeitsbereiche begrenzt.
- [x] Normaler interner Benutzer erhält keine Mitarbeiter-/Fertigungs-App-Rechte.
- [x] SAB-P Mitarbeiter erhält nur notwendige Rechte; Projektleitung erhält Vollzugriff.
- [x] Mitarbeiter kann nur das eigene Mitarbeiterprofil lesen; Projektleitung kann alle verwalten.
- [x] Mitarbeiter kann Zeitbuchungen und Rückmeldungen nicht unter fremdem Benutzer anlegen/umschreiben.
- [x] Rückmeldungen können nur durch Projektleitung intern auf `Bearbeitet` gesetzt werden.
- [x] Automatisierter Migrationstest erhält alte Benutzerzuordnung und ergänzt vorhandenes Mitarbeiterprofil/Arbeitsbereich.
- [x] Odoo-19 `end-migrate.py` für bestehende Fertigungsschritte vorhanden.
- [ ] Reale Mitarbeiter mit Namen/Login/E-Mail anlegen.
- [ ] Reale Arbeitsbereiche je Mitarbeiter zuweisen.
- [ ] Reale Rechteverteilung je Mitarbeiter festlegen.
- [ ] Erstzugang/Passwort bzw. Einladung je realem Benutzer praktisch durchführen.
- [x] Record Rules: Mitarbeiter sieht nur eigene oder passende freie Arbeit.
- [x] Übernehmen automatisiert geprüft.
- [x] Start automatisiert geprüft.
- [x] Pause/Fortsetzen automatisiert geprüft.
- [x] Fertigmeldung automatisiert geprüft.
- [x] Zeitbuchung automatisiert geprüft.
- [x] Fahrtzeit ist als Tätigkeitsart vorhanden.
- [x] Foto-/Rückmeldung technisch geprüft.
- [x] Materialbedarfsmeldung technisch geprüft.
- [x] Gebuchte Zeiten sind geschützt.
- [x] Abgeschlossene Fertigungsaufträge sind geschützt.
- [ ] Smartphone- und Tabletansicht praktisch testen.

## G. Dokumente

- [ ] Dokumentarten fachlich vollständig bestätigen.
- [ ] Pflichtdokumente je Projektstatus festlegen.
- [x] Interne Dokumentfreigabe technisch geprüft.
- [x] Revision erzeugt neuen Stand und erhält Historie.
- [x] Überholte/freigegebene Stände sind geschützt.
- [x] Kundenfreigabe nur mit eigener Berechtigungsgruppe möglich.
- [x] Änderung von Kundentitel/-hinweis zieht Freigabe zurück.

## H. Kundenportal

- [ ] Portalzugang für realen Testkunde A anlegen.
- [ ] Portalzugang für realen Testkunde B anlegen.
- [x] Automatisierter Kunde-A/Kunde-B-Datentrennungstest vorhanden.
- [x] Fremde Projekt-/Dokument-/Fotozugriffe werden serverseitig geprüft.
- [x] Nur freigegebener Kundenstatus wird bereitgestellt.
- [x] Nur freigegebene Dokumente werden bereitgestellt.
- [x] Nur intern bearbeitete und freigegebene Fotos werden bereitgestellt.
- [x] Interne Kalkulations-/EK-/Margendaten werden vom Portal nicht bereitgestellt.
- [ ] Browser-/Smartphone-/Tabletansicht praktisch mit zwei realen Portalkonten testen.

## I. Nachkalkulation / Reporting

- [x] Ist-Stunden aus bestätigten Zeitbuchungen technisch geprüft.
- [x] Ist-Lohnkosten technisch berechnet.
- [x] Materialentnahmen mit Lagerbewegungen verknüpft.
- [x] Historische Materialbewertung technisch geprüft.
- [ ] Deckungsbeitrag mit realem Musterprojekt fachlich gegenprüfen.
- [ ] Management-Grenzwerte für positiv/kritisch/negativ fachlich festlegen.
- [ ] Listen-, Pivot- und Diagrammansicht praktisch prüfen.

## J. End-to-End-Praxistest

- [x] Automatisierter End-to-End-Prozess vorhanden; aktueller Test umfasst echtes SAB-P-Mitarbeiterprofil und Arbeitsbereiche.
- [ ] Aktuellen Härtungsstand im Odoo.sh Build bestätigen.
- [ ] Zusätzlich echtes oder vollständig realistisches SAB-P Projekt praktisch durchspielen.
- [ ] Angebot/Kalkulation gegen bekannte Altwerte prüfen.
- [ ] Einkauf/Lager mit realen Artikeln prüfen.
- [ ] Fertigung mobil praktisch rückmelden.
- [ ] Dokumente/Kundenstatus praktisch freigeben.
- [ ] Kundenportal aus realer Kundensicht prüfen.
- [ ] Nachkalkulation gegen reale Erwartungswerte prüfen.

## K. Merge / Go-live

- [ ] Handbuch nach praktischem UI-Test final gegen tatsächliche Bezeichnungen prüfen.
- [ ] Produktivbackup vorhanden.
- [ ] Verantwortliche für Rollback benannt.
- [ ] Branch-Abnahme dokumentiert.
- [ ] Erst danach Merge von `agent/leitfaden-gesamtstand` nach `main`.
- [ ] Produktivupgrade kontrolliert ausführen.
- [ ] Smoke-Test nach Upgrade: Projekt/A26-Nummer, Angebot, Mitarbeiterverwaltung, Mitarbeiter-App, Portal, Dokumentdownload.
