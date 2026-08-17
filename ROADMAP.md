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

- automatisierter Teststand weiterhin grün,
- Entwicklungsbranch `agent/leitfaden-gesamtstand`,
- `main` bleibt bis zur vollständigen Abnahme unverändert/stabil.

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

### 3.4 bis 3.14 Weitere bestehende V1-Bereiche

Die bereits umgesetzten Bereiche Angebotskalkulation, Stückliste, Einkauf/Lager, Fertigung, Dokumente, Zeit/Service/Montage, Nachkalkulation/Reporting, Mitarbeiteroberfläche, Kundenportal, Kundenstatus, Tests/Härtung und Dokumentation bleiben verbindlicher Bestandteil des Gesamtstands.

---

## 4. Verbindlich vorgemerkt: Artikel-Ampel für Einkauf und Freigabe

Für **jedes SAB-Produkt / jeden bestellbaren Artikel** wird eine zwingende Einkaufsfreigabe-Klassifizierung vorgesehen. Die Auswahl erfolgt als eindeutige Ampel-Kategorie; es darf immer nur **eine** Kategorie aktiv sein.

### Grün – Standardartikel

- Standardwert bei jeder Neuanlage eines Artikels ist **Grün**.
- Der Artikel darf ohne besondere Mengenbegrenzung über den normalen Einkaufsprozess bestellt werden.
- Keine zusätzliche Begründung oder Geschäftsführungsfreigabe erforderlich.

### Gelb – mengenbegrenzter Artikel

- Für den Artikel wird eine **maximal zulässige Bestellmenge** hinterlegt.
- Bestellungen sind nur bis zu dieser festgelegten Maximumgrenze ohne Sonderfreigabe zulässig.
- Die Mengenprüfung muss im tatsächlichen Bestell-/Freigabeprozess technisch erzwungen werden und darf nicht nur ein Hinweis sein.
- Die genaue Bezugsgröße der Maximumgrenze (z. B. je Bestellung, Projekt oder Zeitraum) wird vor Implementierung fachlich festgelegt.

### Rot – freigabepflichtiger Artikel

- Der Artikel darf nicht ohne ausdrückliche Begründung bestellt werden.
- Sobald ein roter Artikel bestellt bzw. zur Bestellung freigegeben werden soll, öffnet sich zwingend ein Eingabe-/Auswahlfenster.
- In diesem Fenster muss der Mitarbeiter eine **Begründung als Pflichtfeld** erfassen.
- Ohne Begründung kann der Vorgang nicht weitergeführt werden.
- Anschließend wird eine Freigabeanforderung an den **Geschäftsführer** gesendet.
- Der **Einkaufsleiter** erhält die Benachrichtigung zusätzlich in CC.
- Die Bestellung darf erst nach dokumentierter Freigabe durch den dafür berechtigten Geschäftsführer fortgesetzt/freigegeben werden.
- Begründung, Antragsteller, Artikel, Menge, Projekt/Bestellbezug, Zeitpunkt, Freigabeentscheidung und Freigebender müssen nachvollziehbar gespeichert werden.

### Bedien- und Datenregel

- Die Ampel muss am Artikel sichtbar und zwingend gepflegt sein.
- Technisch ist sie als **Einfachauswahl** (Grün/Gelb/Rot) umzusetzen, nicht als drei unabhängig gleichzeitig aktivierbare Häkchen. Damit werden widersprüchliche Zustände ausgeschlossen.
- In der Oberfläche kann die Auswahl farblich mit Grün, Gelb und Rot dargestellt werden.
- Bei neu angelegten Artikeln wird automatisch **Grün** vorbelegt.
- Bestehende Artikel erhalten bei der Einführung ebenfalls Grün, sofern keine abweichende Einstufung bewusst vorgenommen wird.
- Die Ampelklassifizierung muss bei DATANORM-/Preisimporten erhalten bleiben und darf durch Lieferanten- oder Preisupdates nicht überschrieben werden.

---

## 5. Noch technisch/fachlich abzuarbeiten

- expliziter Upgrade-Test auf bestehender/produktionsnaher Datenbank,
- Browser-/Mobil-Smoke-Test,
- reales Projekt Ende-zu-Ende,
- Alt-Excel gegen Odoo vergleichen,
- ABB-DATANORM praktisch prüfen,
- Lageranfangsbestände und Anfangsbewertung,
- Pflichtdokumente/Rollen/Managementgrenzen,
- **Artikel-Ampel mit Mengenlimit und rotem Freigabeworkflow implementieren und testen**,
- für Gelb verbindlich festlegen, worauf sich die Maximumgrenze bezieht,
- Geschäftsführer- und Einkaufsleiter-E-Mail/Benutzer für den Freigabeworkflow konfigurierbar machen,
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
