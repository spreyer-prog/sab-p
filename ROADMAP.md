# SAB-P Suite – Leitfaden / Entwicklungsstand

## Festgelegte Kernarchitektur

Projekt → Angebot → Kalkulationsartikel → Kalkulationspositionen → SAB-Produkt → Lieferantenartikel → Lieferant/DATANORM → Stückliste → Einkauf/Lager → Fertigung → Dokumentation/Zeiten → Nachkalkulation

## Im Entwicklungsbranch umgesetzt

### Projekt / Angebot / Kalkulation
- Projekt- und Angebotsnummern sowie konfigurierbarer Nummernkreis
- Projektübersicht und SAB-P Stammdaten
- Kalkulationsartikel mit 20 Suchbegriffen
- Excel-Import der Kalkulationshüllen
- Faktoren aus der Altkalkulation: Mechanik %, Verdrahtung %, Prüfung %, Platzfaktor als Dezimalwert
- Mehrere Produktpositionen je Kalkulationsartikel
- SAB-Produkte mit absoluten Platzeinheiten und absoluten Mechanik-/Verdrahtungs-/Prüfzeiten
- Lieferanten und Lieferantenartikel
- Einkaufspreis + Rabatt → Netto-Einkaufspreis
- Automatische Lieferantenartikelauswahl: bevorzugte aktive Bezugsquelle, sonst günstigste aktive Bezugsquelle
- Material-EK je Kalkulationsposition und Summen je Kalkulationsartikel
- Technische Berechnung Produktwert × Menge × Kalkulationsfaktor
- Angebotskalkulation mit Snapshots, Revisionen und kalkulatorischem Netto-Richtwert
- Änderungsprotokoll und geschützte Änderung von Kalkulationsparametern

### DATANORM 5
- Import auf Basis der realen ABB-DATANORM-5-Datei, Kennung 050
- Direkter Upload einer .001-Datei oder eines Lieferanten-ZIP
- ABB-ZIP: KurztextinklTyp-Variante wird automatisch bevorzugt
- Herstellerartikelnummer, Kurztext, Typ, EAN, Einheit und DATANORM-Preis werden übernommen
- Produktzeiten, Platzeinheiten, Kalkulationszuordnungen und Suchbegriffe werden durch DATANORM nicht überschrieben
- Vorhandene Artikel werden wiederholbar aktualisiert, fehlende Artikel können angelegt werden
- DATANORM-Preis und Preiskennzeichen werden getrennt vom kalkulationswirksamen EK gespeichert
- Übernahme des DATANORM-Preises in den EK muss je Lieferant ausdrücklich freigegeben werden
- Z-Sätze werden erkannt und gezählt; pauschale Preiswirkung ist bewusst nicht aktiviert

### Auftragsübergabe / Fertigung
- Bestätigtes Angebot kann eine gesperrte Projektstückliste aus Kalkulations-Snapshots erzeugen
- Fertigungsauftrag nur aus freigegebener Stückliste
- definierte Fertigungsschritte mit Status, Mitarbeiter, Start-/Endzeit und Fortschritt
- abgeschlossene Fertigungsaufträge und Schritte sind gesperrt

### Einkauf / Lager
- Einkaufsbedarf aus freigegebener Stückliste
- optionale Positionen werden nicht automatisch disponiert
- Lieferant, Lieferantenartikel, Menge und EK werden als Bedarf übernommen
- Status Offen → Bestellt → Geliefert
- Lieferung erzeugt genau einen Lagerzugang
- Lagerbewegungen: Zugang, Entnahme, Reservierung, Freigabe
- Bestand, reservierter Bestand und frei verfügbarer Bestand je Produkt
- Bewertungs-EK wird auf Lagerbewegungen historisch eingefroren
- Materialentnahmen werden mit gleitendem historischen Lagerwert bewertet

### Dokumente / Service / Nachkalkulation
- Projektbezogene Dokumente mit Dokumentarten, Datei, Freigabe und Revisionen
- freigegebene Dokumentstände sind unveränderlich; Änderungen laufen über Revisionen
- projektbezogene Zeiterfassung mit Mitarbeiter, Tätigkeit, Datum, Stunden und Kostensatz
- Fahrtzeit als eigene Tätigkeitsart
- gebuchte Zeiten sind gesperrt und fließen in Ist-Stunden ein
- Nachkalkulation mit Soll-/Ist-Stunden, Lohnkosten, historisch bewerteten Materialentnahmen, Direktkosten und Deckungsbeitrag
- Listen-, Pivot- und Diagrammansichten für Projektcontrolling

## Noch fachlich abzugleichen

- Bedeutung und Preiswirkung der ABB/DATANORM-Z-Sätze für tatsächlich benötigte NE-Metall-/Staffelpreisfälle
- Exakte Vergleichsrechnung Alt-Excel gegen neue Odoo-Kalkulation, insbesondere Planungszuschlag und Sonderfaktoren
- Grenzwerte/Interpretation des Deckungsbeitrags im späteren Management-Reporting

## Aktuelle Phase: Integration / Produktivsetzung

1. Odoo.sh Build-Warnings und Restfehler bereinigen
2. Vollständigen Modul-Upgrade-Test durchführen
3. Ein echtes Projekt Ende-zu-Ende durchspielen
4. Alt-Excel gegen Odoo mit identischem Musterprojekt vergleichen
5. Berechtigungen pro Benutzerrolle finalisieren
6. DATANORM-Import mit vollständigem ABB-Paket unter Odoo.sh testen
7. Lageranfangsbestände und Bewertungslogik für Produktivstart festlegen
8. Dokumentarten und Pflichtdokumente je Projektstatus fachlich prüfen
9. Backup-/Rollback-Ablauf vor Merge dokumentieren
10. Erst nach erfolgreichem Abnahmetest Merge in `main`

## Entwicklungsregel

- `main` bleibt stabil.
- Gesamtentwicklung erfolgt auf `agent/leitfaden-gesamtstand`.
- Keine automatische Sprachumstellung.
- Keine neuen Architekturideen außerhalb des festgelegten Leitfadens ohne fachliche Freigabe.
- Reale Odoo.sh-Buildfehler werden priorisiert korrigiert.
- Historische Angebots-, Dokument-, Zeit- und Lagerwerte dürfen durch spätere Stammdatenänderungen nicht rückwirkend verändert werden.
