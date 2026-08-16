# SAB-P Suite V1 – Produktivsetzungs- und Abnahmecheckliste

Stand: technischer Green Build auf `agent/leitfaden-gesamtstand`, Modulversion `19.0.5.22.0`.

Legende:
- `[x]` technisch durch automatisierten Odoo.sh-Test bzw. Branchprüfung nachgewiesen,
- `[ ]` benötigt noch realen Upgrade-/Praxis-/Fachdatenabgleich.

## A. Technische Abnahme

- [x] Neuester geprüfter Odoo.sh Build des Branches `agent/leitfaden-gesamtstand` erfolgreich.
- [ ] Modul `sab_project` auf einer bestehenden, produktionsnahen Datenbank explizit als Upgrade testen.
- [x] Keine SAB-P Testfehler im geprüften Green Build: 57 Tests, 0 Failures, 0 Errors.
- [x] Im geprüften Build keine SAB-P bezogenen Warnings festgestellt.
- [x] Automatisierter End-to-End-Test läuft vollständig durch.
- [x] Keine ungewollte Änderung an `main`; Entwicklungsbranch liegt vor `main`, nicht dahinter.
- [ ] Datenbankbackup unmittelbar vor Produktivupgrade vorhanden.
- [ ] Rollback auf letzten stabilen `main`-Stand organisatorisch und technisch praktisch verifizieren.

## B. Nummernkreise

- [ ] Projektpräfix fachlich final geprüft.
- [ ] Jahresdarstellung fachlich final geprüft.
- [ ] Projektstellenanzahl fachlich final geprüft.
- [ ] Angebotsstellenanzahl fachlich final geprüft.
- [ ] Startnummer für Produktivbetrieb fachlich final geprüft.
- [ ] Vorhandene Altprojekte ohne SAB-P Nummer für die reale Datenbank bewertet/nachnummeriert.
- [x] Automatischer Test: neues Projekt erhält erwartete `Axx.xxxx` Nummer.
- [x] Automatischer Test: erstes/zweites Angebot erhalten `-01`/`-02`.
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
- [x] Automatischer Test: Wiederholungsimport/Importlogik erhält technische SAB-P Daten und Rohpreis getrennt.
- [x] Automatischer Test: ABB-ZIP bevorzugt KurztextinklTyp-Datei.
- [ ] Lieferanten-EK-Freigabe mit realen Preisdateien praktisch prüfen.
- [ ] Z-Sätze im realen ABB-Paket identifizieren und bewerten.
- [ ] Falls Z-Sätze/NE-Metall/Staffelpreise preiswirksam benötigt werden: fachliche Regel dokumentieren und umsetzen.

## E. Einkauf und Lager

- [x] Einkaufsbedarf aus freigegebener Stückliste automatisiert geprüft.
- [x] Optionale Positionen werden nicht automatisch disponiert.
- [x] Wareneingang erzeugt genau einen Lagerzugang.
- [x] Reservierung/Freigabe/Entnahme automatisiert geprüft.
- [x] Bestands- und Reservierungslogik automatisiert geprüft.
- [x] Historische/gewichtete Lagerbewertung im Test geprüft.
- [ ] Lageranfangsbestände je Produkt festlegen/importieren.
- [ ] Anfangsbewertung der Lagerbestände fachlich freigeben.

## F. Fertigung und Mitarbeiteroberfläche

- [ ] Reale Mitarbeiterrollen festlegen.
- [ ] Gruppe `SAB-P Mitarbeiter` realen Benutzern zuweisen.
- [x] Record Rules: Mitarbeiter sieht nur eigene/freie Arbeit.
- [x] Automatischer Test: freie Arbeit kann übernommen werden.
- [x] Start funktioniert im Workflow-Test.
- [x] Pause/Fortsetzen funktioniert im Workflow-Test.
- [x] Fertigmeldung funktioniert im Workflow-Test.
- [x] Zeitbuchung ist technisch integriert und getestet.
- [x] Fahrtzeit ist als eigene Tätigkeit vorgesehen.
- [x] Foto-/Rückmeldung ist technisch getestet.
- [x] Materialbedarfsmeldung ist technisch geprüft.
- [x] Bestätigte Zeitbuchungen sind geschützt.
- [x] Abgeschlossene Fertigungsstände sind gegen unzulässige Änderungen geschützt.
- [ ] Smartphone- und Tabletansicht praktisch mit realen Geräten testen.

## G. Dokumente

- [ ] Dokumentarten fachlich auf Vollständigkeit für SAB-P prüfen.
- [ ] Pflichtdokumente je Projektstatus festlegen.
- [x] Interne Dokumentfreigabe technisch geprüft.
- [x] Revision erzeugt neuen Stand und erhält Historie.
- [x] Überholte/freigegebene Stände sind geschützt.
- [x] Kundenfreigabe nur mit eigener Berechtigungsgruppe möglich.
- [x] Änderung von Kundentitel/-hinweis zieht Freigabe zurück.

## H. Kundenportal

- [ ] Portalzugang für realen Testkunden A anlegen.
- [ ] Portalzugang für realen Testkunden B anlegen.
- [x] Automatischer Test: Kunde A sieht nur Inhalte von Kunde A.
- [x] Serverseitige Prüfung verhindert Zugriff auf fremde Projekte.
- [x] Serverseitige Prüfung verhindert fremden Dokumentzugriff.
- [x] Serverseitige Prüfung verhindert fremden Fotozugriff.
- [x] Nur freigegebener Kundenstatus wird bereitgestellt.
- [x] Nur freigegebene Dokumente werden bereitgestellt.
- [x] Nur intern bearbeitete und anschließend freigegebene Fotos werden bereitgestellt.
- [x] Kundenfreigabe ist von Mitarbeiter- und Projektleiterrechten getrennt.
- [ ] Portal mit zwei echten Portalbenutzern praktisch aus Kundensicht testen.
- [ ] Smartphone-/Tabletansicht des Portals praktisch testen.

## I. Nachkalkulation / Reporting

- [x] Automatischer Test: bestätigte Ist-Stunden fließen in Projekt/Nachkalkulation ein.
- [x] Ist-Lohnkostenlogik technisch vorhanden und im End-to-End-Prozess enthalten.
- [x] Materialentnahmen sind mit Lagerbewegungen gekoppelt.
- [x] Historische Materialbewertung technisch getestet.
- [ ] Deckungsbeitrag mit realem Musterprojekt gegenprüfen.
- [ ] Management-Grenzwerte für positiv/kritisch/negativ fachlich festlegen.
- [ ] Listen-, Pivot- und Diagrammansicht praktisch im Browser prüfen.

## J. End-to-End-Praxistest

Automatisiert nachgewiesen:

- [x] Projekt anlegen und nummerieren.
- [x] Angebot erstellen und kalkulieren.
- [x] Auftrag bestätigen.
- [x] Stückliste erzeugen/freigeben.
- [x] Einkaufsbedarf erzeugen.
- [x] Wareneingang/Lager buchen.
- [x] Fertigungsauftrag erzeugen.
- [x] Fertigungs-/Zeitprozess integrieren.
- [x] Kundenstatus integrieren.
- [x] Nachkalkulationswerte erzeugen.

Noch als echter Praxistest:

- [ ] Ein vollständig realistisches SAB-P Kundenprojekt manuell durchspielen.
- [ ] Fertigung auf Smartphone/Tablet rückmelden.
- [ ] Reale Zeiten/Fotos/Materialmeldungen erfassen.
- [ ] Reale Projektdokumente freigeben.
- [ ] Kundenportal aus zwei realen Kundenzugängen prüfen.
- [ ] Nachkalkulation gegen Alt-/Sollwerte fachlich abnehmen.

## K. Merge / Go-live

- [ ] Handbuch nach Abschluss der realen Praxistests final gegen den getesteten Softwarestand abgleichen.
- [ ] Produktivbackup vorhanden.
- [ ] Verantwortliche für Rollback benennen.
- [ ] Branch-Abnahme dokumentieren.
- [ ] Erst danach Merge von `agent/leitfaden-gesamtstand` nach `main`.
- [ ] Produktivupgrade kontrolliert ausführen.
- [ ] Smoke-Test nach Upgrade: Projekt, A26-Projektnummer, Angebot, Mitarbeiteransicht, Portal, Dokumentdownload.
