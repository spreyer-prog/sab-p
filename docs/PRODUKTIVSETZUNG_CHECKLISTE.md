# SAB-P Suite V1 – Produktivsetzungs- und Abnahmecheckliste

## A. Technische Abnahme

- [ ] Neuester Odoo.sh Build des Branches `agent/leitfaden-gesamtstand` erfolgreich.
- [ ] Modul `sab_project` lässt sich auf bestehender Datenbank upgraden.
- [ ] Keine SAB-P Testfehler.
- [ ] SAB-P bezogene Warnings geprüft und bereinigt oder fachlich dokumentiert.
- [ ] End-to-End-Test läuft vollständig durch.
- [ ] Keine ungewollte Änderung an `main`.
- [ ] Datenbankbackup unmittelbar vor Produktivupgrade vorhanden.
- [ ] Rollback auf letzten stabilen `main`-Stand organisatorisch und technisch möglich.

## B. Nummernkreise

- [ ] Projektpräfix geprüft.
- [ ] Jahresdarstellung geprüft.
- [ ] Projektstellenanzahl geprüft.
- [ ] Angebotsstellenanzahl geprüft.
- [ ] Startnummer geprüft.
- [ ] Altprojekte ohne SAB-P Nummer bewertet/nachnummeriert.
- [ ] Test: neues Projekt erhält erwartete `Axx.xxxx` Nummer.
- [ ] Test: erstes/zweites Angebot erhalten `-01`/`-02`.

## C. Kalkulation

- [ ] Globale Kalkulationsfaktoren fachlich freigegeben.
- [ ] Änderungsfreigabecode gesetzt und nur berechtigten Personen bekannt.
- [ ] Musterprojekt aus Alt-Excel 1:1 in Odoo nachgerechnet.
- [ ] Material-EK stimmt im Musterprojekt.
- [ ] Mechanik-/Verdrahtungs-/Prüfzeiten stimmen.
- [ ] Planungs-/Hilfsmaterial-/Zeit-/Schwierigkeits-/Verpackungs-/Skonto-/Marge-/Rabattfaktoren geprüft.
- [ ] Kalkulatorischer Netto-Richtwert gegen Altsystem bewertet.
- [ ] Snapshot-Verhalten mit nachträglicher Stammdatenänderung geprüft.

## D. DATANORM

- [ ] Vollständiges reales ABB-DATANORM-Paket importiert.
- [ ] Wiederholungsimport aktualisiert vorhandene Artikel ohne technische SAB-P Daten zu überschreiben.
- [ ] Lieferanten-EK-Freigabe geprüft.
- [ ] Z-Sätze in realem Paket identifiziert.
- [ ] Falls Z-Sätze/NE-Metall preiswirksam benötigt werden: fachliche Regel dokumentiert und umgesetzt.

## E. Einkauf und Lager

- [ ] Einkaufsbedarf aus freigegebener Stückliste geprüft.
- [ ] Optionale Positionen werden nicht automatisch disponiert.
- [ ] Wareneingang erzeugt genau einen Lagerzugang.
- [ ] Reservierung/Freigabe/Entnahme geprüft.
- [ ] Reservierter Bestand kann nicht ungewollt entnommen werden.
- [ ] Historische Lagerbewertung geprüft.
- [ ] Lageranfangsbestände je Produkt festgelegt/importiert.
- [ ] Anfangsbewertung der Lagerbestände fachlich freigegeben.

## F. Fertigung und Mitarbeiteroberfläche

- [ ] Reale Mitarbeiterrollen festgelegt.
- [ ] Gruppe `SAB-P Mitarbeiter` zugewiesen.
- [ ] Mitarbeiter sieht nur eigene/freie Arbeit.
- [ ] Übernehmen funktioniert.
- [ ] Start funktioniert.
- [ ] Pause/Fortsetzen funktioniert.
- [ ] Fertigmeldung funktioniert.
- [ ] Zeitbuchung funktioniert.
- [ ] Fahrtzeit funktioniert.
- [ ] Foto-/Rückmeldung funktioniert.
- [ ] Materialbedarfsmeldung funktioniert.
- [ ] Gebuchte Zeiten sind gesperrt.
- [ ] Abgeschlossene Fertigungsaufträge sind gesperrt.
- [ ] Smartphone- und Tabletansicht praktisch getestet.

## G. Dokumente

- [ ] Dokumentarten fachlich vollständig.
- [ ] Pflichtdokumente je Projektstatus festgelegt.
- [ ] Interne Dokumentfreigabe geprüft.
- [ ] Revision erzeugt neuen Stand und erhält Historie.
- [ ] Überholte/freigegebene Stände sind geschützt.
- [ ] Kundenfreigabe nur mit eigener Berechtigungsgruppe möglich.
- [ ] Änderung von Kundentitel/-hinweis zieht Freigabe zurück.

## H. Kundenportal

- [ ] Portalzugang für Testkunde A angelegt.
- [ ] Portalzugang für Testkunde B angelegt.
- [ ] Kunde A sieht ausschließlich Projekte von Kunde A.
- [ ] Direkter URL-Aufruf eines Projekts von Kunde B liefert keinen Zugriff.
- [ ] Direkter Dokumentdownload eines fremden Kunden ist gesperrt.
- [ ] Direkter Fotoaufruf eines fremden Kunden ist gesperrt.
- [ ] Nur freigegebener Kundenstatus sichtbar.
- [ ] Nur freigegebene Dokumente sichtbar.
- [ ] Nur intern bearbeitete und freigegebene Fotos sichtbar.
- [ ] Interne Notizen, EK, Lieferanten, Probleme und Margen erscheinen nirgendwo im Portal.
- [ ] Smartphone-/Tabletansicht praktisch getestet.

## I. Nachkalkulation / Reporting

- [ ] Ist-Stunden stimmen mit gebuchten Zeiten überein.
- [ ] Ist-Lohnkosten stimmen.
- [ ] Materialentnahmen stimmen mit Lagerbewegungen überein.
- [ ] Historische Materialbewertung stimmt.
- [ ] Deckungsbeitrag stimmt im Musterprojekt.
- [ ] Management-Grenzwerte für positiv/kritisch/negativ fachlich festgelegt.
- [ ] Listen-, Pivot- und Diagrammansicht geprüft.

## J. End-to-End-Praxistest

- [ ] Echtes oder vollständig realistisches Projekt angelegt.
- [ ] Angebot erstellt und kalkuliert.
- [ ] Auftrag bestätigt.
- [ ] Stückliste erzeugt und freigegeben.
- [ ] Einkaufsbedarf erzeugt.
- [ ] Wareneingang/Lager gebucht.
- [ ] Fertigungsauftrag erzeugt.
- [ ] Fertigung mobil rückgemeldet.
- [ ] Zeiten/Fotos/Materialmeldungen erfasst.
- [ ] Dokumente freigegeben.
- [ ] Kundenstatus freigegeben.
- [ ] Kundenportal aus Kundensicht geprüft.
- [ ] Nachkalkulation geprüft.

## K. Merge / Go-live

- [ ] Handbuch entspricht exakt dem getesteten Softwarestand.
- [ ] Produktivbackup vorhanden.
- [ ] Verantwortliche für Rollback benannt.
- [ ] Branch-Abnahme dokumentiert.
- [ ] Erst danach Merge von `agent/leitfaden-gesamtstand` nach `main`.
- [ ] Produktivupgrade kontrolliert ausgeführt.
- [ ] Smoke-Test nach Upgrade: Projekt, Angebot, Mitarbeiteransicht, Portal, Dokumentdownload.
