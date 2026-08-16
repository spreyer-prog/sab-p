# SAB-P Suite V1 – Produktivsetzungs- und Abnahmecheckliste

Stand: technischer Green Build auf `agent/leitfaden-gesamtstand`, Basis-Modulversion `19.0.5.22.0`; nachfolgende Härtungstests müssen im nächsten Odoo.sh Build erneut grün bestätigt werden.

Legende:
- `[x]` technisch durch automatisierten Test bzw. Branchprüfung nachgewiesen,
- `[ ]` benötigt noch realen Upgrade-/Praxis-/Fachdatenabgleich.

## A. Technische Abnahme

- [x] Letzter vollständig geprüfter Odoo.sh Build des Branches `agent/leitfaden-gesamtstand` erfolgreich.
- [ ] Neuester Härtungsstand nach Nummernkreis-Erweiterung erneut durch Odoo.sh grün bestätigen.
- [ ] Modul `sab_project` auf einer bestehenden, produktionsnahen Datenbank explizit als Upgrade testen.
- [x] Keine SAB-P Testfehler im letzten vollständig geprüften Green Build: 57 Tests, 0 Failures, 0 Errors.
- [x] Im geprüften Build keine SAB-P bezogenen Warnings festgestellt.
- [x] Automatisierter End-to-End-Test läuft vollständig durch.
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
- [x] Automatischer Test vorhanden: Kalenderjahreswechsel führt zu getrenntem Jahreszähler und Reset `A26.000x` → `A27.0001`.
- [x] Automatischer Test vorhanden: Präfix, 2-/4-stelliges Jahr, Trennzeichen, Projektstellen, Startnummer, Angebotstrennzeichen und Angebotsstellen sind konfigurierbar.
- [x] Projektnummer ist in der SAB-P Projektübersicht verpflichtend erste Spalte.
- [x] Projektnummer ist zusätzlich in der normalen Odoo-Projektliste eingebunden.

## C. Kalkulation

- [ ] Globale Kalkulationsfaktoren fachlich freigegeben.
- [ ] Änderungsfreigabecode für Produktivbetrieb gesetzt und nur berechtigten Personen bekannt.
- [ ] Musterprojekt aus Alt-Excel 1:1 in Odoo nachgerechnet.
- [ ] Material-EK stimmt im realen Musterprojekt.
- [ ] Mechanik-/Verdrahtungs-/Prüfzeiten stimmen im realen Musterprojekt.
- [ ] Planungs-/Hilfsmaterial-/Zeit-/Schwierigkeits-/Verpackungs-/Skonto-/Marge-/Rabattfaktoren fachlich geprüft.
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

## F. Fertigung und Mitarbeiteroberfläche

- [ ] Reale Mitarbeiterrollen festlegen.
- [ ] Gruppe `SAB-P Mitarbeiter` realen Benutzern zuweisen.
- [x] Record Rules: Mitarbeiter sieht nur eigene/freie Arbeit.
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

- [x] Automatisierter End-to-End-Prozess vorhanden und im letzten Green Build bestanden.
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
- [ ] Smoke-Test nach Upgrade: Projekt/A26-Nummer, Angebot, Mitarbeiteransicht, Portal, Dokumentdownload.
