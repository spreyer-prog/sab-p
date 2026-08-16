# SAB-P Suite – Leitfaden / Entwicklungsstand

## 1. Verbindliche Kernarchitektur

Die SAB-P Suite bildet den vereinbarten Gesamtprozess ab:

**Projekt → Angebot → Kalkulationsartikel → Kalkulationspositionen → SAB-Produkt → Lieferantenartikel → Lieferant/DATANORM → Stückliste → Einkauf/Lager → Fertigung → Dokumentation/Zeiten → Nachkalkulation → Kundenportal**

Zusätzlich gehören verbindlich zur V1:

- **Mitarbeiter-App / mobile Mitarbeiteroberfläche** für Fertigung, Montage und Service,
- **Kundenportal / Kunden-App** für ausdrücklich freigegebene Projektinformationen,
- **vollständige deutschsprachige Bedienungs- und Systemdokumentation**.

`main` bleibt bis zur vollständigen Abnahme stabil. Die Gesamtentwicklung erfolgt auf `agent/leitfaden-gesamtstand`.

---

## 2. Aktueller technischer Meilenstein

Zuletzt bestätigter grüner Odoo.sh-Härtungsstand:

- Modulversion: `19.0.5.35.0`,
- GitHub-Commit-Status `ci/odoo.sh (dev)`: eingerichtet und für den dokumentierten Härtungsstand erfolgreich,
- automatisierter End-to-End-Test: grün,
- Nummerierungs-/Projektübersichts-Tests einschließlich sichtbarer `A26.xxxx` Projektnummer: grün,
- Portal-/Kundentrennungstests: grün,
- Mitarbeiter-/Record-Rule-/Kundenfreigabe-Securitytests: grün,
- Mitarbeiterzugang, Arbeitsbereiche, Fremdbenutzer-Schutz für Zeit/Rückmeldung und kontrollierter Fertigungsstart technisch gehärtet,
- Entwicklungsbranch basiert weiterhin auf `main`; beim dokumentierten Vergleich war er 325 Commits voraus und 0 Commits zurück,
- `main` blieb auf Commit `28056e70766fdbb9072b23b2a9679dcdb307a902` unverändert.

Damit ist die reine Kernentwicklung der V1 weitgehend abgeschlossen. Ab jetzt gilt: **keine neuen Komfortfunktionen vor Abschluss der Upgrade-, Praxis- und Fachdatenabnahme.**

---

## 3. Bereits umgesetzt

### 3.1 Projekt / Angebot

- automatische, konfigurierbare SAB-P Projektnummern, standardmäßig `A26.0001` usw.,
- automatische Angebotsnummern je Projekt, z. B. `A26.0001-01`, `-02` usw.,
- Nachnummerierung bestehender Altprojekte bei erster SAB-P Nutzung,
- unveränderliche bereits vergebene Projekt-/Angebotsnummern,
- SAB-P Projektübersicht mit Projektnummer als verpflichtender erster Spalte,
- Projektnummer zusätzlich in der normalen Odoo-Projektliste,
- direktes **Neues Angebot** aus dem Projekt,
- Übersicht vorhandener Angebote im Projekt,
- Projektstatus, Klassifikationen, Kommission, Liefertermin und Wiedervorlage.

### 3.2 Kalkulationsartikel / Produkte / Einkaufspreise

- Kalkulationsartikel mit Suchbegriffen,
- mehrere Produktpositionen je Kalkulationsartikel,
- Produktfaktoren für Mechanik, Verdrahtung, Prüfung und Platz,
- SAB-Produkte mit absoluten Platzeinheiten und absoluten Zeiten,
- Hersteller, Lieferanten und Lieferantenartikel,
- bevorzugte bzw. günstigste aktive Bezugsquelle,
- Einkaufspreis-/Rabattlogik,
- kalkulationswirksamer Netto-EK,
- historische Angebotssnapshots.

### 3.3 DATANORM 5

- Import realer DATANORM-5-Dateien mit Kennung 050,
- direkter `.001`-Upload und Lieferanten-ZIP,
- ABB-ZIP-Auswahl mit bevorzugter KurztextinklTyp-Datei,
- Herstellerartikelnummer, Text, Typ, EAN, Einheit und DATANORM-Preis,
- wiederholbarer Aktualisierungsimport,
- technische SAB-P Werte werden nicht überschrieben,
- DATANORM-Preis und kalkulationswirksamer EK bleiben getrennt,
- bewusste Lieferantenfreigabe für Preisübernahme,
- Z-Sätze werden erkannt und gezählt, aber nicht ohne fachliche Regel pauschal preiswirksam interpretiert.

### 3.4 Angebotskalkulation

- Kalkulationspositionen mit Snapshots,
- Material-/Zeit-/Platzberechnung,
- Kalkulationsfaktoren als Snapshot im Angebot,
- kalkulatorischer Netto-Richtwert,
- Angebotsrevisionen,
- geschützte Änderung zentraler Kalkulationsparameter,
- Änderungsprotokoll.

### 3.5 Stückliste / Einkauf / Lager

- Stückliste aus bestätigtem Auftrag und eingefrorenen Angebotskomponenten,
- Stücklistenfreigabe mit Sperre nach Freigabe,
- Einkaufsbedarf aus freigegebener Stückliste,
- optionale Positionen werden nicht automatisch disponiert,
- Status **Offen → Bestellt → Geliefert**,
- Lieferung erzeugt genau einen Lagerzugang,
- Lagerzugang, Entnahme, Reservierung und Freigabe,
- Bestand, reservierter Bestand und verfügbarer Bestand,
- historisch eingefrorener Bewertungs-EK,
- Materialentnahmen mit historischem/gleitendem Lagerwert.

### 3.6 Fertigung

- Fertigungsauftrag nur aus freigegebener Stückliste,
- Standard-Fertigungsschritte mit Arbeitsbereichen,
- Mitarbeiterprofil und technischer Benutzer getrennt nachvollziehbar,
- Auswahl und Übernahme nur bei passendem Arbeitsbereich,
- Start- und Fertigzeit,
- Fortschritt,
- Status **Offen → In Arbeit → Pausiert → Fertig** bzw. **Entfällt**,
- Arbeit übernehmen,
- Start / Fortsetzen,
- Pause,
- Fertigmeldung,
- normaler Mitarbeiter kann einen zulässigen Schritt starten; der übergeordnete Auftrag wird kontrolliert systemseitig gestartet, ohne allgemeine Schreibrechte zu vergeben,
- abgeschlossene/stornierte Fertigungsaufträge und Schritte gesperrt,
- Upgrade-Helfer für bestehende technische Benutzerzuordnungen und Arbeitsbereiche.

### 3.7 Dokumente

- projektbezogene Dokumente,
- Dokumentarten,
- Datei/Dateiname,
- interne Freigabe,
- revisionssichere neue Dokumentstände,
- überholte/freigegebene Versionen geschützt,
- getrennte Kundenfreigabe,
- Änderung von Kundentitel/Kundenhinweis zieht Freigabe zurück.

### 3.8 Zeit / Service / Montage

- projektbezogene Zeitbuchungen,
- Fertigungsschrittbezug,
- Mitarbeiter, Datum, Tätigkeit, Stunden, Kostensatz,
- Fahrtzeit als eigene Tätigkeit,
- Mitarbeiter kann keine Zeit unter fremdem Benutzer anlegen oder umschreiben,
- bestätigte Zeitbuchungen gesperrt,
- Ist-Stunden werden auf Projekt aktualisiert.

### 3.9 Nachkalkulation / Reporting

- Soll-/Ist-Stunden,
- Stundenabweichung absolut und prozentual,
- Ist-Lohnkosten,
- historisch bewertete Materialentnahmen,
- Ist-Direktkosten,
- Angebotssumme,
- Deckungsbeitrag absolut und prozentual,
- Ergebnisstatus,
- Listen-, Pivot- und Diagrammansichten,
- UI-Vertragstest schützt View-Modi und zentrale Reporting-Kennzahlen vor versehentlicher Entfernung.

### 3.10 Mitarbeiter-App / mobile Mitarbeiteroberfläche

Umgesetzt als responsive Odoo-Web-/PWA-orientierte Oberfläche:

- eigene SAB-P Mitarbeiterverwaltung mit Name, Login, E-Mail, Aktivstatus, Rollen und Arbeitsbereichen,
- Anlegen/Aktualisieren, Einladung, Deaktivieren und Reaktivieren des Odoo-Zugangs,
- persönliche Mitarbeiteranmeldung über Odoo-Benutzer,
- **Meine Arbeit**,
- **Freie Arbeit**,
- Übernehmen,
- Start/Fortsetzen,
- Pause,
- Fertig melden,
- Zeit erfassen,
- Fahrt-/Servicezeit über Zeitbuchung,
- interne Rückmeldung,
- Foto hochladen,
- Materialbedarf melden,
- eigene Zeiten,
- eigene Rückmeldungen,
- Rückmeldung kann nur durch Projektleitung intern als bearbeitet gesetzt werden,
- Record Rules für eigene/freie Arbeit und eigene Mitarbeiterdaten,
- kaufmännische Kundenfreigabe von Mitarbeiterrechten getrennt.

### 3.11 Kundenportal / Kunden-App

Umgesetzt als responsive Portaloberfläche:

- `/my/sab-projects`,
- kundenbezogener Portalzugang,
- Kunde sieht nur Projekte seines kommerziellen Partners,
- Projektnummer und Projektbezeichnung,
- Liefertermin, sofern hinterlegt,
- kundenfreundliche Meilensteine,
- Fortschrittsanzeige,
- Kundentext,
- ausschließlich explizit freigegebene Dokumente,
- ausschließlich intern bearbeitete und explizit freigegebene Fotos,
- fremde Projekt-/Dokument-/Foto-URLs werden serverseitig geprüft,
- interne Einkaufs-, Lieferanten-, Kalkulations-, Margen- und Problemwerte werden nicht als Portalinhalt bereitgestellt.

### 3.12 Statuskopplung intern → Kunde

- interner Fertigungsstatus und Kundenstatus getrennt,
- Kundenmeilenstein wird aus internem Stand nur **vorgeschlagen**,
- Vorschlag kann manuell übernommen werden,
- keine automatische Veröffentlichung,
- jede relevante Statusänderung erfordert anschließend wieder eine bewusste Kundenfreigabe,
- Kundenfreigabe ist eine eigenständige Rolle und verleiht keine Projektleiterrechte.

### 3.13 Tests / Härtung

Automatisiert geprüft werden u. a.:

- Nummerierung und sichtbare Projektnummer,
- Kalkulationskern,
- DATANORM,
- Angebotskalkulation,
- Snapshots/Stückliste,
- Fertigung einschließlich Pause/Fortsetzen und Arbeitsbereichsprüfung,
- kontrollierter Fertigungsstart durch normale Mitarbeiter,
- Einkauf,
- Lager,
- Dokumentrevisionen/Kundenfreigabe,
- Zeiterfassung einschließlich Fremdbenutzer-Schutz,
- Mitarbeiter-Rückmeldungen einschließlich Fremdbenutzer- und Bearbeitungsstatus-Schutz,
- Mitarbeiter-Record-Rules,
- vertrauliche Mitarbeiterdaten,
- Kundenstatus,
- Kunden-A/Kunden-B-Trennung,
- Rollen-/Kundenfreigaberechte,
- Reporting-View-Verträge für Liste/Pivot/Diagramm,
- End-to-End-Prozess vom Projekt bis Nachkalkulation/Kundenstatus.

### 3.14 Dokumentation

Im Repository vorhanden:

- `docs/SAB-P_HANDBUCH.md` – Bedienungs- und Systemhandbuch,
- `docs/PRODUKTIVSETZUNG_CHECKLISTE.md` – verbindliche Abnahme-/Go-live-Checkliste,
- `docs/MORGEN_TESTABLAUF.md` – praktischer Testablauf,
- `docs/BUILD_STATUS.md` – Buildstatus-Dokumentation,
- `docs/BRANCH_ABNAHME.md` – dokumentierter technischer Branch-Abnahmestand und Merge-Gate,
- `docs/ROLLBACK_PLAN.md` – stabiler Code-Referenzpunkt und Wiederherstellungsablauf.

Screenshots werden erst nach finalem praktischen UI-Abnahmestand ergänzt.

---

## 4. Noch technisch abzuarbeiten

Nach dem Green Build bleiben technisch nur noch Punkte, die nicht seriös durch einen frischen Installations-/Testlauf ersetzt werden können:

1. **expliziter Upgrade-Test** des Moduls auf einer bestehenden/produktionsnahen Odoo.sh Datenbank,
2. Upgrade-Log erneut auf SAB-P Fehler/Warnings prüfen,
3. manueller Browser-Smoke-Test der wichtigsten Arbeitswege,
4. Smartphone-/Tablet-Praxistest der Mitarbeiteroberfläche und des Kundenportals,
5. dokumentierten Backup-/Rollback-Ablauf vor dem späteren Merge/Produktivupgrade praktisch mit einer Datenbankkopie testen,
6. Handbuch nach dem manuellen Praxistest final gegen tatsächliche UI-Bezeichnungen abgleichen.

Der automatische technische Teststand muss bei jeder weiteren Änderung grün bleiben.

---

## 5. Noch fachlich mit realen SAB-P Daten abzugleichen

Diese Punkte dürfen nicht erfunden werden:

- reale Alt-Excel-Kalkulation gegen identisches Odoo-Musterprojekt,
- exakte Preiswirkung von ABB/DATANORM-Z-Sätzen/NE-Metall-/Staffelpreisfällen, sofern real verwendet,
- endgültige Grenzwerte des Deckungsbeitrags-Managementstatus,
- endgültige reale Mitarbeiter-/Rollenverteilung,
- endgültige Kundenmeilensteine bzw. Freigabepraxis nach Praxistest,
- Lageranfangsbestände und Anfangsbewertung,
- endgültige Pflichtdokumente je Projektstatus,
- reale Portalbenutzer/Kunden A/B für Abnahmetest,
- endgültige Produktiv-Nummernkreisparameter einschließlich Startnummer.

Diese Punkte werden als Abnahmepunkte markiert und nicht durch Annahmen ersetzt.

---

## 6. Verbindliche Reihenfolge bis V1-Fertigstellung

1. **Green Build halten – zuletzt bestätigt für Modulversion `19.0.5.35.0`.**
2. **Expliziten Modul-Upgrade-Test auf bestehender/produktionsnaher Datenbank grün bekommen.**
3. **Manuellen Browser-/Mobil-Smoke-Test durchführen.**
4. **Portal- und Rollenprüfung mit zwei realen getrennten Kundenkonten durchführen.**
5. **Echtes/realistisches Projekt Ende-zu-Ende durchspielen.**
6. **Alt-Excel gegen Odoo vergleichen.**
7. **ABB-DATANORM-Gesamtpaket praktisch prüfen.**
8. **Lageranfangsbestände und Anfangsbewertung festlegen.**
9. **Pflichtdokumente/Rollen/Managementgrenzen fachlich abnehmen.**
10. **Handbuch und Produktivcheckliste final gegen den praktisch getesteten Stand verifizieren.**
11. **Produktivbackup erzeugen, Rollback-Verantwortliche benennen und dokumentierten Wiederherstellungsablauf praktisch verifizieren.**
12. **Erst nach vollständiger Abnahme Merge in `main`.**

---

## 7. Entwicklungsregeln

- `main` bleibt stabil und wird vor der Abnahme nicht als Entwicklungsbranch benutzt.
- Entwicklungsbranch: `agent/leitfaden-gesamtstand`.
- Keine automatische Sprachumstellung als Teil der SAB-P Logik.
- Keine Architekturideen außerhalb dieses Leitfadens ohne fachliche Freigabe.
- Reale Odoo.sh Buildfehler haben Vorrang vor neuen Komfortfunktionen.
- Historische Angebots-, Stücklisten-, Dokument-, Zeit- und Lagerwerte dürfen durch spätere Stammdatenänderungen nicht rückwirkend verfälscht werden.
- Mitarbeiter-App, Kundenportal und vollständige Dokumentation sind fester V1-Umfang.
- Interne Informationen dürfen niemals automatisch ungefiltert an Kunden veröffentlicht werden.
- Kundenfreigaben müssen bewusst und serverseitig berechtigt erfolgen.
- Ohne grüne technische Abnahme und vollständige Dokumentation erfolgt kein Merge in `main`.
