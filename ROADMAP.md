# SAB-P Suite – Leitfaden / Entwicklungsstand

## Festgelegte Kernarchitektur

Projekt → Angebot → Kalkulationsartikel → Kalkulationspositionen → SAB-Produkt → Lieferantenartikel → Lieferant/DATANORM

## Im Entwicklungsbranch umgesetzt

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

### DATANORM 5

- Import auf Basis der realen ABB-DATANORM-5-Datei, Kennung 050
- Direkter Upload einer .001-Datei oder eines Lieferanten-ZIP
- ABB-ZIP: KurztextinklTyp-Variante wird automatisch bevorzugt
- Herstellerartikelnummer, Kurztext, Typ, EAN, Einheit und DATANORM-Preis werden übernommen
- Produktzeiten, Platzeinheiten, Kalkulationszuordnungen und Suchbegriffe werden durch DATANORM nicht überschrieben
- Vorhandene Artikel werden wiederholbar aktualisiert, fehlende Artikel können angelegt werden
- DATANORM-Preis und Preiskennzeichen werden getrennt vom kalkulationswirksamen EK gespeichert
- Übernahme des DATANORM-Preises in den EK muss je Lieferant ausdrücklich freigegeben werden
- Z-Sätze werden erkannt und gezählt, aber noch nicht pauschal preiswirksam verarbeitet
- Datenmodell für gezielte spätere Zu-/Abschläge ist vorbereitet

### Angebotskalkulation / Versionierung

- Ein Angebot kann mehrere SAB-P Kalkulationsartikel mit eigener Menge enthalten
- Material-EK, Mechanik-, Verdrahtungs-, Prüfzeiten, Gesamtstunden und Platzeinheiten werden automatisch summiert
- Beim Einfügen eines Kalkulationsartikels wird ein Snapshot der aktuellen Kalkulationswerte im Angebot gespeichert
- Spätere DATANORM-, Preis- oder Zeitänderungen verändern bestehende Angebotsstände nicht rückwirkend
- Bestätigte Angebote sperren die SAB-P Kalkulationspositionen
- Angebotsrevision erzeugt eine neue Angebotsnummer und kopiert den historischen Kalkulationsstand
- Kalkulationskonstanten aus der Altkalkulation sind zentral konfigurierbar
- Material- und Lohnkosten sowie ein transparenter kalkulatorischer Netto-Richtwert werden berechnet
- Der Richtwert überschreibt Odoo-Verkaufspreise bewusst nicht automatisch

## Noch fachlich/technisch abzugleichen

- Bedeutung und Preiswirkung der ABB/DATANORM-Z-Sätze für die tatsächlich benötigten NE-Metall-/Staffelpreisfälle
- Exakte Vergleichsrechnung Alt-Excel gegen neue Odoo-Kalkulation, insbesondere Planungszuschlag und Sonderfaktoren
- Änderungsprotokoll/Freigabecode für bewusste manuelle Kalkulationsänderungen gemäß Fragenkatalog

## Danach gemäß Leitfaden

1. Stücklisten / Auftragsübergabe aus freigegebenem Angebot
2. Fertigung
3. Einkauf
4. Lager
5. Dokumente
6. Service / Zeiterfassung
7. Nachkalkulation / Reporting
8. Produktivsetzung SAB-P Suite

## Entwicklungsregel

- `main` bleibt stabil.
- Gesamtentwicklung erfolgt zunächst auf `agent/leitfaden-gesamtstand`.
- Keine automatische Sprachumstellung.
- Keine neuen Architekturideen außerhalb des festgelegten Leitfadens ohne fachliche Freigabe.
- Reale Odoo.sh-Buildfehler werden nach dem Gesamtstand nacheinander korrigiert.
