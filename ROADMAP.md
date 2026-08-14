# SAB-P Suite – Leitfaden / Entwicklungsstand

## Festgelegte Kernarchitektur

Projekt → Angebot → Kalkulationsartikel → Kalkulationspositionen → SAB-Produkt → Lieferantenartikel → Lieferant/DATANORM

## Abgeschlossen / im aktuellen Stand vorhanden

- Projekt- und Angebotsnummern sowie konfigurierbarer Nummernkreis
- Projektübersicht und SAB-P Stammdaten
- Kalkulationsartikel mit 20 Suchbegriffen
- Excel-Import der Kalkulationshüllen
- Faktoren aus der Altkalkulation: Mechanik %, Verdrahtung %, Prüfung %, Platzfaktor als Dezimalwert
- Mehrere Produktpositionen je Kalkulationsartikel
- SAB-Produkte mit absoluten Platzeinheiten und absoluten Mechanik-/Verdrahtungs-/Prüfzeiten
- Lieferanten und Lieferantenartikel
- Einkaufspreis + Rabatt → Netto-Einkaufspreis
- Automatische Lieferantenartikelauswahl in der Kalkulationsposition: bevorzugte aktive Bezugsquelle, sonst günstigste aktive Bezugsquelle
- Material-EK je Kalkulationsposition und Summen je Kalkulationsartikel
- Technische Berechnung Produktwert × Menge × Kalkulationsfaktor

## Nächster Block

### DATANORM-Synchronisation

Ziel:
- DATANORM-/Lieferantendaten aktualisieren Lieferantenartikel, nicht die technische Kalkulationslogik.
- Produktzeiten, Platzeinheiten, Kalkulationszuordnungen und Suchbegriffe dürfen durch Preisupdates nicht überschrieben werden.
- Vorhandene Lieferantenartikel werden aktualisiert; neue Datensätze werden nachvollziehbar angelegt/zugeordnet.
- Import muss wiederholbar und dublettensicher sein.

Das konkrete DATANORM-Dateiformat und die Feldzuordnung werden nicht geraten. Die Synchronisation wird auf Basis einer realen SAB-P/Lieferanten-Datei finalisiert.

## Danach gemäß Leitfaden

1. Kalkulations-/Preisengine vollständig abschließen
2. Angebotskalkulation und Angebotsversionierung
3. Stücklisten
4. Fertigung
5. Einkauf
6. Lager
7. Dokumente
8. Service / Zeiterfassung
9. Nachkalkulation / Reporting
10. Produktivsetzung SAB-P Suite

## Entwicklungsregel

- `main` bleibt stabil.
- Gesamtentwicklung erfolgt zunächst auf `agent/leitfaden-gesamtstand`.
- Keine automatische Sprachumstellung.
- Keine neuen Architekturideen außerhalb des festgelegten Leitfadens ohne fachliche Freigabe.
- Reale Odoo.sh-Buildfehler werden nach dem Gesamtstand nacheinander korrigiert.
