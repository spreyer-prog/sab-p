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

## 2. Bereits umgesetzt

### 2.1 Projekt / Angebot

- automatische, konfigurierbare SAB-P Projektnummern, standardmäßig `A26.0001` usw.,
- automatische Angebotsnummern je Projekt, z. B. `A26.0001-01`, `-02` usw.,
- Nachnummerierung bestehender Altprojekte bei erster SAB-P Nutzung,
- unveränderliche bereits vergebene Projekt-/Angebotsnummern,
- SAB-P Projektübersicht mit sichtbarer Projektnummer,
- direktes **Neues Angebot** aus dem Projekt,
- Übersicht vorhandener Angebote im Projekt,
- Projektstatus, Klassifikationen, Kommission, Liefertermin und Wiedervorlage.

### 2.2 Kalkulationsartikel / Produkte / Einkaufspreise

- Kalkulationsartikel mit Suchbegriffen,
- mehrere Produktpositionen je Kalkulationsartikel,
- Produktfaktoren für Mechanik, Verdrahtung, Prüfung und Platz,
- SAB-Produkte mit absoluten Platzeinheiten und absoluten Zeiten,
- Hersteller, Lieferanten und Lieferantenartikel,
- bevorzugte bzw. günstigste aktive Bezugsquelle,
- Einkaufspreis-/Rabattlogik,
- kalkulationswirksamer Netto-EK,
- historische Angebotssnapshots.

### 2.3 DATANORM 5

- Import realer DATANORM-5-Dateien mit Kennung 050,
- direkter `.001`-Upload und Lieferanten-ZIP,
- ABB-ZIP-Auswahl mit bevorzugter KurztextinklTyp-Datei,
- Herstellerartikelnummer, Text, Typ, EAN, Einheit und DATANORM-Preis,
- wiederholbarer Aktualisierungsimport,
- technische SAB-P Werte werden nicht überschrieben,
- DATANORM-Preis und kalkulationswirksamer EK bleiben getrennt,
- bewusste Lieferantenfreigabe für Preisübernahme,
- Z-Sätze werden erkannt und gezählt, aber nicht ohne fachliche Regel pauschal preiswirksam interpretiert.

### 2.4 Angebotskalkulation

- Kalkulationspositionen mit Snapshots,
- Material-/Zeit-/Platzberechnung,
- Kalkulationsfaktoren als Snapshot im Angebot,
- kalkulatorischer Netto-Richtwert,
- Angebotsrevisionen,
- geschützte Änderung zentraler Kalkulationsparameter,
- Änderungsprotokoll.

### 2.5 Stückliste / Einkauf / Lager

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

### 2.6 Fertigung

- Fertigungsauftrag nur aus freigegebener Stückliste,
- Standard-Fertigungsschritte,
- Verantwortlicher/Mitarbeiter,
- Start- und Fertigzeit,
- Fortschritt,
- Status **Offen → In Arbeit → Pausiert → Fertig** bzw. **Entfällt**,
- Arbeit übernehmen,
- Start / Fortsetzen,
- Pause,
- Fertigmeldung,
- abgeschlossene/stornierte Fertigungsaufträge und Schritte gesperrt.

### 2.7 Dokumente

- projektbezogene Dokumente,
- Dokumentarten,
- Datei/Dateiname,
- interne Freigabe,
- revisionssichere neue Dokumentstände,
- überholte/freigegebene Versionen geschützt,
- getrennte Kundenfreigabe,
- Änderung von Kundentitel/Kundenhinweis zieht Freigabe zurück.

### 2.8 Zeit / Service / Montage

- projektbezogene Zeitbuchungen,
- Fertigungsschrittbezug,
- Mitarbeiter, Datum, Tätigkeit, Stunden, Kostensatz,
- Fahrtzeit als eigene Tätigkeit,
- bestätigte Zeitbuchungen gesperrt,
- Ist-Stunden werden auf Projekt aktualisiert.

### 2.9 Nachkalkulation / Reporting

- Soll-/Ist-Stunden,
- Stundenabweichung absolut und prozentual,
- Ist-Lohnkosten,
- historisch bewertete Materialentnahmen,
- Ist-Direktkosten,
- Angebotssumme,
- Deckungsbeitrag absolut und prozentual,
- Ergebnisstatus,
- Listen-, Pivot- und Diagrammansichten.

### 2.10 Mitarbeiter-App / mobile Mitarbeiteroberfläche

Umgesetzt als responsive Odoo-Web-/PWA-orientierte Oberfläche:

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
- Record Rules für eigene/freie Arbeit und eigene Mitarbeiterdaten,
- kaufmännische Kundenfreigabe von Mitarbeiterrechten getrennt.

### 2.11 Kundenportal / Kunden-App

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

### 2.12 Statuskopplung intern → Kunde

- interner Fertigungsstatus und Kundenstatus getrennt,
- Kundenmeilenstein wird aus internem Stand nur **vorgeschlagen**,
- Vorschlag kann manuell übernommen werden,
- keine automatische Veröffentlichung,
- jede relevante Statusänderung erfordert anschließend wieder eine bewusste Kundenfreigabe,
- Kundenfreigabe ist eine eigenständige Rolle und verleiht keine Projektleiterrechte.

### 2.13 Tests / Härtung

Vorhanden sind automatisierte Tests für u. a.:

- Nummerierung,
- Kalkulationskern,
- DATANORM,
- Angebotskalkulation,
- Snapshots/Stückliste,
- Fertigung einschließlich Pause/Fortsetzen,
- Einkauf,
- Lager,
- Dokumentrevisionen/Kundenfreigabe,
- Zeiterfassung,
- Mitarbeiter-Rückmeldungen,
- Kundenstatus,
- Rollen-/Kundenfreigaberechte,
- End-to-End-Prozess vom Projekt bis Nachkalkulation/Kundenstatus.

### 2.14 Dokumentation

Im Repository vorhanden:

- `docs/SAB-P_HANDBUCH.md` – Bedienungs- und Systemhandbuch,
- `docs/PRODUKTIVSETZUNG_CHECKLISTE.md` – verbindliche Abnahme-/Go-live-Checkliste.

Screenshots werden erst nach finalem UI-Abnahmestand ergänzt.

---

## 3. Noch technisch abzuarbeiten

Diese Punkte kann die Entwicklung ohne fachliche Erfindungen weiter abarbeiten:

1. jeden neuen Odoo.sh Build auswerten und echte SAB-P Fehler/Warnings korrigieren,
2. vollständigen Modul-Upgrade-Test auf Odoo.sh durchführen,
3. XML-/Model-/Security-Warnings bis auf nicht durch SAB-P verursachte Framework-Meldungen bereinigen,
4. End-to-End-Test nach jedem relevanten Integrationsblock grün halten,
5. Portal-/Berechtigungshärtung weiter testen,
6. UI-Arbeitswege und Feldbezeichnungen auf Konsistenz prüfen,
7. Handbuch bei jeder Änderung mitführen,
8. Backup-/Rollback-Ablauf vor Merge final gegen den realen Odoo.sh Prozess prüfen.

---

## 4. Noch fachlich mit realen SAB-P Daten abzugleichen

Diese Punkte dürfen nicht erfunden werden:

- reale Alt-Excel-Kalkulation gegen identisches Odoo-Musterprojekt,
- exakte Preiswirkung von ABB/DATANORM-Z-Sätzen/NE-Metall-/Staffelpreisfällen, sofern real verwendet,
- endgültige Grenzwerte des Deckungsbeitrags-Managementstatus,
- endgültige reale Mitarbeiter-/Rollenverteilung,
- endgültige Kundenmeilensteine bzw. Freigabepraxis nach Praxistest,
- Lageranfangsbestände und Anfangsbewertung,
- endgültige Pflichtdokumente je Projektstatus,
- reale Portalbenutzer/Kunden A/B für Abnahmetest.

Diese Punkte werden als Abnahmepunkte markiert und nicht durch Annahmen ersetzt.

---

## 5. Verbindliche Reihenfolge bis V1-Fertigstellung

1. **Odoo.sh Restfehler und SAB-P Warnings bereinigen.**
2. **Vollständigen Modul-Upgrade-Test grün bekommen.**
3. **Automatische Test-Suite vollständig grün bekommen.**
4. **Portal- und Rollenprüfung mit zwei getrennten Kundenkonten durchführen.**
5. **Echtes/realistisches Projekt Ende-zu-Ende durchspielen.**
6. **Alt-Excel gegen Odoo vergleichen.**
7. **ABB-DATANORM-Gesamtpaket praktisch prüfen.**
8. **Lageranfangsbestände und Anfangsbewertung festlegen.**
9. **Pflichtdokumente/Rollen/Managementgrenzen fachlich abnehmen.**
10. **Handbuch und Produktivcheckliste gegen den tatsächlich getesteten Stand verifizieren.**
11. **Odoo.sh Backup-/Rollback-Punkt festlegen.**
12. **Erst nach vollständiger Abnahme Merge in `main`.**

---

## 6. Entwicklungsregeln

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
