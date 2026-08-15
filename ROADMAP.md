# SAB-P Suite – Leitfaden / Entwicklungsstand

## Festgelegte Kernarchitektur

Projekt → Angebot → Kalkulationsartikel → Kalkulationspositionen → SAB-Produkt → Lieferantenartikel → Lieferant/DATANORM → Stückliste → Einkauf/Lager → Fertigung → Dokumentation/Zeiten → Nachkalkulation

Ergänzend gehören zum festgelegten Gesamtumfang zwei Benutzeroberflächen außerhalb der klassischen Büroansicht:

- **Mitarbeiter-App / mobile Mitarbeiteroberfläche** für Fertigung, Montage und Service
- **Kundenportal / Kunden-App** für den freigegebenen Projekt- und Fertigungsstatus

Diese beiden Bereiche sind Bestandteil des Gesamtprojekts und keine optionalen späteren Ideen.

## Verbindliche Projektdokumentation / Bedienungsanleitung

Die SAB-P Suite gilt erst dann als vollständig fertiggestellt, wenn zusätzlich zum Programmcode eine vollständige deutschsprachige Bedienungs- und Systemdokumentation vorhanden ist. Diese Dokumentation ist ein fester Bestandteil des Projektumfangs und muss mit der Software mitgeführt und bei Funktionsänderungen aktualisiert werden.

Für **jede von SAB-P entwickelte Funktion, Ansicht, Schaltfläche, Statusänderung und Automatik** muss dokumentiert werden:

- Wo befindet sich die Funktion in Odoo bzw. in Mitarbeiter-App oder Kundenportal?
- Für welche Benutzerrolle ist sie bestimmt?
- Was zeigt die jeweilige Ansicht und was bedeuten die einzelnen Felder?
- Was bewirkt jede Schaltfläche / jeder Button konkret?
- Welche Voraussetzungen müssen erfüllt sein, bevor die Funktion verwendet werden kann?
- Welche Eingaben muss der Benutzer machen?
- Welche Daten erzeugt oder verändert das System im Hintergrund?
- Welche automatischen Folgeprozesse werden ausgelöst?
- Welche Sperren, Freigaben und Plausibilitätsprüfungen greifen?
- Welche Auswirkungen hat der Vorgang auf Kalkulation, Stückliste, Einkauf, Lager, Fertigung, Dokumente, Zeiterfassung, Nachkalkulation oder Kundenstatus?
- Was kann der Benutzer nach Abschluss des Vorgangs noch ändern und was ist bewusst gesperrt?
- Welche typischen Fehler oder Fehlermeldungen können auftreten und wie sind sie zu beheben?
- Welche Daten sind intern, welche für Mitarbeiter sichtbar und welche dürfen Kunden sehen?

Die Dokumentation muss nicht nur eine Klickanleitung sein, sondern auch die **Systemlogik im Hintergrund** erklären, damit später nachvollziehbar bleibt, warum Odoo einen Wert berechnet, einen Status setzt, eine Position sperrt oder einen Folgeprozess erzeugt.

### Vorgesehene Struktur des endgültigen Handbuchs

1. Systemüberblick und Gesamtprozess der SAB-P Suite
2. Benutzer, Rollen und Berechtigungen
3. Projekte und Projektnummern
4. Angebote, Angebotsnummern und Revisionen
5. Kalkulationsartikel, Suchbegriffe und Produktpositionen
6. SAB-Produkte, Hersteller, Lieferanten und Lieferantenartikel
7. DATANORM-Import einschließlich Preislogik
8. Angebotskalkulation, Faktoren, Snapshots und Freigaben
9. Auftragsübergabe und Stücklisten
10. Einkauf und Materialbedarf
11. Lager, Reservierungen, Entnahmen und Lagerbewertung
12. Fertigungsaufträge und sämtliche Fertigungsschritte
13. Dokumentenverwaltung, Freigaben und Revisionen
14. Service, Montage und Zeiterfassung
15. Nachkalkulation, Deckungsbeitrag und Reporting
16. Mitarbeiter-App / mobile Mitarbeiteroberfläche
17. Kundenportal / Kunden-App und Kundenstatus
18. Foto- und Dokumentfreigabe für Kunden
19. Einstellungen und administrativer Bereich
20. Fehlerbehebung und typische Bedienfehler
21. Backup, Upgrade, Rollback und technischer Betrieb
22. vollständiger Beispielprozess eines Projekts von Anfrage bis Abschluss

### Dokumentationsregel während der Entwicklung

- Neue Funktionen dürfen nicht nur programmiert werden; ihre Bedienung und Hintergrundlogik müssen für das spätere Handbuch nachvollziehbar festgehalten werden.
- Vor Produktivsetzung wird der tatsächlich vorhandene Softwarestand noch einmal vollständig gegen das Handbuch geprüft.
- Nicht vorhandene oder verworfene Funktionen dürfen im endgültigen Handbuch nicht beschrieben werden.
- Das endgültige Handbuch wird aus dem tatsächlich getesteten Produktivstand erstellt, nicht aus Annahmen oder nur aus der ursprünglichen Planung.
- Screenshots/Abbildungen werden erst auf Basis der finalen Oberflächen ergänzt, damit sie nicht durch spätere UI-Änderungen veraltet sind.

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

## Fest vereinbarter noch zu programmierender Umfang

### Mitarbeiter-App / mobile Mitarbeiteroberfläche
Die Mitarbeiteroberfläche muss für Smartphone und Tablet geeignet sein und soll ohne Zugriff auf die kaufmännische Volloberfläche die für den jeweiligen Mitarbeiter notwendigen Vorgänge bereitstellen.

Vorgesehener Umfang:
- Anmeldung mit persönlichem Mitarbeiterzugang
- eigene bzw. zugewiesene Fertigungsaufträge und Arbeitsschritte anzeigen
- Fertigungsschritt starten, pausieren bzw. fertig melden
- tatsächliche Arbeitszeit direkt dem Projekt/Fertigungsauftrag zuordnen
- Service-/Montagezeiten und Fahrtzeiten erfassen
- Bemerkungen und interne Rückmeldungen erfassen
- Fotos vom Fertigungs-, Prüf-, Montage- oder Mangelzustand aufnehmen/hochladen
- Materialbedarf bzw. fehlendes Material melden
- Prüf- und Endkontrollschritte bearbeiten
- klare mobile Statusanzeige, welche Arbeit als Nächstes ansteht
- rollenbasierter Zugriff: Mitarbeiter sieht nur die für seine Arbeit notwendigen Daten; EK, Margen und kaufmännische Kalkulation bleiben geschützt
- mobile/PWA-Ausführung als erste Zielarchitektur; native iOS-/Android-App nur, wenn dafür später ein zwingender fachlicher Grund besteht

### Kundenportal / Kunden-App
Kunden erhalten einen geschützten Zugang und dürfen ausschließlich freigegebene Informationen ihrer eigenen Projekte sehen.

Vorgesehener Umfang:
- kundenbezogener Login/Zugang
- Übersicht der eigenen laufenden Projekte/Verteilungen
- Projektnummer, Projektbezeichnung und freigegebener Liefertermin
- kundenfreundlicher Fertigungsfortschritt über definierte Meilensteine
- keine ungefilterte 1:1-Anzeige interner Fertigungsschritte
- vorgesehene Kundenmeilensteine: Auftrag eingegangen, Planung, Materialbeschaffung, mechanische Fertigung, Verdrahtung, Prüfung, fertig/versandbereit bzw. ausgeliefert
- Fortschrittsanzeige je Verteilung/Projekt
- nur ausdrücklich für Kunden freigegebene Fotos anzeigen
- nur ausdrücklich für Kunden freigegebene Dokumente zum Download bereitstellen
- mögliche Dokumente: freigegebene Pläne, Prüfprotokolle, Errichter-/Konformitätserklärungen, Lieferscheine und Projektdokumentation
- interne Bemerkungen, EK, Kalkulation, Lieferanteninformationen und interne Probleme niemals im Kundenportal veröffentlichen
- spätere Benachrichtigungen bei relevanten freigegebenen Statusänderungen vorsehen
- responsive Web/PWA als erste Zielarchitektur; Installation als App-Icon auf Smartphone/Tablet ermöglichen

### Statuskopplung intern → Kunde
- interner Fertigungsstatus und Kundenstatus werden getrennt geführt
- definierte Regeln ordnen interne Arbeitsschritte einem kundenfreundlichen Meilenstein zu
- Kundenstatus darf nur aus freigegebenen Informationen gespeist werden
- interne Rücksetzungen, Nacharbeiten oder Sperrvermerke werden nicht automatisch ungefiltert veröffentlicht
- Freigabe von Kundenfotos und Kundendokumenten muss explizit erfolgen

## Noch fachlich abzugleichen

- Bedeutung und Preiswirkung der ABB/DATANORM-Z-Sätze für tatsächlich benötigte NE-Metall-/Staffelpreisfälle
- Exakte Vergleichsrechnung Alt-Excel gegen neue Odoo-Kalkulation, insbesondere Planungszuschlag und Sonderfaktoren
- Grenzwerte/Interpretation des Deckungsbeitrags im späteren Management-Reporting
- endgültige Mitarbeiterrollen und welche Fertigungsschritte welche Rolle bearbeiten darf
- endgültige Kundenmeilensteine und welche Statuswechsel automatisch bzw. manuell freigegeben werden

## Aktuelle Phase / weitere Reihenfolge

1. Odoo.sh Build-Warnings und Restfehler des bisherigen Kernsystems bereinigen
2. Vollständigen Modul-Upgrade-Test durchführen
3. Mitarbeiter-App / mobile Mitarbeiteroberfläche programmieren und testen
4. Kundenportal / Kunden-App mit getrenntem Kundenstatus programmieren und testen
5. Foto-/Dokumentfreigabe und Statuskopplung intern → Kunde fertigstellen
6. Ein echtes Projekt Ende-zu-Ende einschließlich Mitarbeiter- und Kundensicht durchspielen
7. Alt-Excel gegen Odoo mit identischem Musterprojekt vergleichen
8. Berechtigungen pro Benutzerrolle finalisieren
9. DATANORM-Import mit vollständigem ABB-Paket unter Odoo.sh testen
10. Lageranfangsbestände und Bewertungslogik für Produktivstart festlegen
11. Dokumentarten und Pflichtdokumente je Projektstatus fachlich prüfen
12. vollständige Bedienungs- und Systemdokumentation gegen den finalen Softwarestand fertigstellen
13. kompletten Beispielprozess und Fehlerbehebungskapitel im Handbuch verifizieren
14. Backup-/Rollback-Ablauf vor Merge dokumentieren
15. Erst nach erfolgreichem Abnahmetest **und vollständiger Bedienungsanleitung** Merge in `main`

## Entwicklungsregel

- `main` bleibt stabil.
- Gesamtentwicklung erfolgt auf `agent/leitfaden-gesamtstand`.
- Keine automatische Sprachumstellung.
- Keine neuen Architekturideen außerhalb des festgelegten Leitfadens ohne fachliche Freigabe.
- Reale Odoo.sh-Buildfehler werden priorisiert korrigiert.
- Historische Angebots-, Dokument-, Zeit- und Lagerwerte dürfen durch spätere Stammdatenänderungen nicht rückwirkend verändert werden.
- Mitarbeiter-App und Kundenportal sind fester Projektumfang und dürfen bei der Produktivsetzung nicht als optionale Nachträge entfallen.
- Die vollständige Bedienungs- und Systemdokumentation ist ebenfalls fester Projektumfang. Ohne sie ist die SAB-P Suite nicht abnahme- bzw. produktionsfertig.
