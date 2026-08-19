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

- automatisierter Teststand vor dem Workflow-Paket `19.0.5.53.0` grün,
- Entwicklungsbranch `agent/leitfaden-gesamtstand`,
- `main` bleibt bis zur vollständigen Abnahme unverändert/stabil.

Der aktuelle Entwicklungsstand `19.0.5.53.0` enthält das neue Angebotsfreigabe-, Bauteil- und Beschaffungsworkflow-Paket. Dessen Odoo.sh-Upgrade- und Testlauf muss vor dem nächsten Browser-Test vollständig grün sein.

Der automatische technische Teststand muss bei jeder weiteren Änderung grün bleiben.

---

## 3. Bereits umgesetzt

### 3.1 Projekt / Angebot

- automatische, konfigurierbare SAB-P Projektnummern,
- automatische Angebotsnummern je Projekt,
- SAB-P Projektübersicht,
- Angebote und Angebotsrevisionen,
- Projektstatus, Klassifikationen, Kommission, Liefertermin und Wiedervorlage.

### 3.2 Kalkulationsartikel / Produkte / Einkaufspreise

- Kalkulationsartikel mit Suchbegriffen,
- mehrere Produktpositionen je Kalkulationsartikel,
- Produktfaktoren für Mechanik, Verdrahtung, Prüfung und Platz,
- SAB-Produkte mit absoluten Platzeinheiten und absoluten Zeiten,
- Herstellerbezug und Lieferanten/Lieferantenartikel,
- bevorzugte bzw. günstigste aktive Bezugsquelle,
- Einkaufspreis-/Rabattlogik,
- kalkulationswirksamer Netto-EK,
- historische Angebotssnapshots,
- Produktpreis kann als Lieferantenartikelpreis, Fixpreis oder Baugruppe aus mehreren Lieferantenartikeln ermittelt werden.

### 3.3 DATANORM 5

- Import realer DATANORM-5-Dateien,
- direkter `.001`-Upload und Lieferanten-ZIP,
- ABB-ZIP-Auswahl,
- Herstellerartikelnummer, Text, Typ, EAN, Einheit und DATANORM-Preis,
- wiederholbarer Aktualisierungsimport,
- technische SAB-P Werte werden nicht überschrieben,
- vorhandener EK bleibt erhalten; fehlt ein EK, kann der Listenpreis als Fallback dienen.

### 3.4 Verbindliche Angebotsfreigabe vor Auftragsannahme

- neuer Workflowstatus **In Bearbeitung / Zum Verschicken freigegeben**,
- eigener Button **Angebot zum Verschicken freigeben**,
- LV-Positionen werden erst mit dieser Freigabe projektweit festgeschrieben,
- Senden und PDF-Ausgabe eines SAB-P Angebots setzen die Freigabe voraus,
- ein freigegebenes Angebot ist einschließlich Kalkulation und kaufmännischer Positionen gesperrt,
- Änderungen erfolgen über eine neue, wieder bearbeitbare Angebotsrevision,
- der bisherige Odoo-Button **Bestätigen** heißt in der SAB-P Bedienoberfläche **Auftrag erhalten**,
- erst **Auftrag erhalten** setzt das Projekt auf Auftrag gewonnen und startet den eigentlichen Auftragsprozess,
- vorhandene gesendete bzw. bestätigte Altangebote werden beim Upgrade als freigegeben übernommen.

### 3.5 LV-/NTG- und Bauteilregeln

- ein zuvor freigegebenes LV-Angebot ist zwingende Grundlage für projektweite NTG-Zuordnungen,
- ohne freigegebenes LV-Angebot entstehen keine automatischen NTG-Positionen,
- einzeln ergänzte neue Positionen erhalten nach vorhandener LV-Grundlage fortlaufende NTG-Nummern,
- ein vollständiges Bauteil ist genau eine kaufmännische LV-/NTG-Position,
- alle Unterpositionen eines Bauteils übernehmen ausschließlich die Position des Bauteils,
- beim vollständigen Übernehmen eines Bauteils entstehen keine separaten NTG-Nummern für dessen Unterpositionen,
- dasselbe Bauteil wird in der rechten Projektpositionsliste nur einmal angezeigt,
- unter dem Bauteil werden alle Angebotsnummern aufgeführt, in denen es verwendet wird,
- nicht freigegebene Bauteile aus anderen Angebotsentwürfen werden nicht als projektweit feste Position angeboten,
- PDF und Kundenportal enthalten eine vollständige sichtbare Leerzeile vor und nach jedem Bauteilblock.

### 3.6 Stückliste → Einkauf / Lager

- die technische Stücklistenfreigabe ist der Projektleitung vorbehalten,
- eine freigegebene Gesamtstückliste wird automatisch in den Einkaufsarbeitsplatz übergeben,
- neuer Menübereich **Einkauf / Lager** mit **Neue Stücklisten** und **Beschaffungs-Dashboard**,
- Dashboard nach Projekt und Beschaffungsstatus,
- automatische Erzeugung der projektweiten Einkaufsbedarfe,
- automatische Prüfung und Reservierung des verfügbaren Lagerbestands,
- je Position sichtbarer Bedarf, Lagerbestand, Lagerwert, Projektreservierung, Fehlbestand, Lieferant und Bestellstatus,
- automatisch ermittelte Bestellvorschlagsmenge unter Berücksichtigung von Mindestbestellmenge und Verpackungseinheit,
- vom Einkauf bearbeitbares Feld **Jetzt bestellen**; Wert `0` schließt die Position aus der aktuellen Bestellung aus,
- ausgewählte Positionen werden lieferantenweise zu echten SAB-P Bestellvorschlägen zusammengefasst,
- die erzeugten Entwürfe erscheinen im offenen Bestellbereich und durchlaufen anschließend Bestellfreigabe, Versand und Wareneingang,
- technische Projektleitung erhält dadurch keine Einkaufsrechte; die automatische Übergabe läuft serverseitig, während Bearbeitung und Bestellung rollenbasiert bleiben,
- vorhandene freigegebene Gesamtstücklisten werden beim Upgrade in den neuen Einkaufsarbeitsplatz übernommen.

### 3.7 Artikel-Ampel – Grundstufe

- eindeutige Einfachauswahl **Grün / Gelb / Rot** am Artikel,
- Standardwert neuer und bestehender Artikel ist Grün,
- bei Gelb wird die Höchstmenge je Bestellposition eingeblendet,
- Gelb ohne Höchstmenge größer `0` ist technisch unzulässig,
- Ampel und Höchstmenge bleiben bei DATANORM- und Preisimporten erhalten.

### 3.8 bis 3.17 Weitere bestehende V1-Bereiche

Die bereits umgesetzten Bereiche Angebotskalkulation, Stückliste, Einkauf/Lager, Fertigung, Dokumente, Zeit/Service/Montage, Nachkalkulation/Reporting, Mitarbeiteroberfläche, Kundenportal, Kundenstatus, Tests/Härtung und Dokumentation bleiben verbindlicher Bestandteil des Gesamtstands.

---

## 4. Verbindlich vorgemerkt: vollständiger Artikel-Ampel-Freigabeworkflow

Für **jedes SAB-Produkt / jeden bestellbaren Artikel** wird die bereits angelegte Einkaufsampel im tatsächlichen Bestellprozess vollständig erzwungen.

### Grün – Standardartikel

- Der Artikel darf ohne besondere Mengenbegrenzung über den normalen Einkaufsprozess bestellt werden.
- Keine zusätzliche Begründung oder Ampelfreigabe erforderlich.

### Gelb – mengenbegrenzter Artikel

- Bis einschließlich der hinterlegten Höchstmenge kann der Artikel über den normalen Einkaufsprozess bestellt werden.
- Wird die Höchstmenge überschritten, öffnet sich zwingend ein Eingabefenster mit **Begründung als Pflichtfeld**.
- Ohne Begründung kann die Bestellung nicht weitergeführt werden.
- Die Freigabeanforderung wird an die berechtigten Freigeber gestellt. **Einkaufsleiter oder Geschäftsführung** können die Überschreitung freigeben.
- Eine Ablehnung sperrt die Bestellung in der beantragten Menge; für einen neuen Versuch ist eine neue bzw. geänderte Anforderung erforderlich.
- Antragsteller, Artikel, normale Höchstmenge, beantragte Menge, Überschreitung, Begründung, Projekt/Bestellbezug, Zeitpunkt, Entscheidung und Freigebender werden nachvollziehbar gespeichert.
- Die Mengenprüfung muss im tatsächlichen Bestell-/Freigabeprozess technisch erzwungen werden und darf nicht nur ein Hinweis sein.

### Rot – freigabepflichtiger Artikel

- Der Artikel darf unabhängig von der Menge nicht ohne ausdrückliche Begründung bestellt werden.
- Ohne Begründung kann der Vorgang nicht weitergeführt werden.
- Anschließend wird eine Freigabeanforderung an die **Geschäftsführung** gesendet; der **Einkaufsleiter** wird zusätzlich informiert.
- Die Bestellung darf erst nach dokumentierter Freigabe durch einen dafür berechtigten Freigeber fortgesetzt werden.
- Begründung, Antragsteller, Artikel, Menge, Projekt/Bestellbezug, Zeitpunkt, Freigabeentscheidung und Freigebender müssen nachvollziehbar gespeichert werden.

---

## 5. Noch technisch/fachlich abzuarbeiten

- aktuellen Odoo.sh-Upgrade- und Testlauf für `19.0.5.53.0` grün abschließen,
- expliziter Upgrade-Test auf bestehender/produktionsnaher Datenbank,
- Browser-/Mobil-Smoke-Test,
- reales Projekt Ende-zu-Ende,
- Alt-Excel gegen Odoo vergleichen,
- ABB-DATANORM praktisch prüfen,
- Lageranfangsbestände und Anfangsbewertung,
- Pflichtdokumente/Rollen/Managementgrenzen,
- **gelben und roten Artikel-Ampel-Freigabeworkflow vollständig implementieren und testen**,
- Geschäftsführer- und Einkaufsleiter-Benutzer/E-Mail für Ampelfreigaben konfigurierbar machen,
- Handbuch und Produktivcheckliste finalisieren,
- Backup-/Rollback-Test,
- erst nach vollständiger Abnahme Merge in `main`.

---

## 6. Entwicklungsregeln

- `main` bleibt stabil und wird vor der Abnahme nicht als Entwicklungsbranch benutzt.
- Entwicklungsbranch: `agent/leitfaden-gesamtstand`.
- Keine Architekturideen außerhalb dieses Leitfadens ohne fachliche Freigabe.
- Reale Odoo.sh Buildfehler haben Vorrang vor neuen Komfortfunktionen.
- Historische Angebots-, Stücklisten-, Dokument-, Zeit- und Lagerwerte dürfen durch spätere Stammdatenänderungen nicht rückwirkend verfälscht werden.
- Mitarbeiter-App, Kundenportal und vollständige Dokumentation sind fester V1-Umfang.
- Interne Informationen dürfen niemals automatisch ungefiltert an Kunden veröffentlicht werden.
- Kundenfreigaben müssen bewusst und serverseitig berechtigt erfolgen.
- Ohne grüne technische Abnahme und vollständige Dokumentation erfolgt kein Merge in `main`.
