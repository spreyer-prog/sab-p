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
- Keine zusätzliche Begründung oder Freigabe erforderlich.

### Gelb – mengenbegrenzter Artikel

- Sobald **Gelb** ausgewählt wird, erscheint am Artikel zwingend das Feld **Höchstmenge**.
- Ohne eingetragene Höchstmenge darf ein gelber Artikel nicht gespeichert bzw. nicht als vollständig konfiguriert gelten.
- Bis einschließlich der hinterlegten Höchstmenge kann der Artikel über den normalen Einkaufsprozess bestellt werden.
- Wird die Höchstmenge überschritten, greift automatisch derselbe begründungs- und freigabepflichtige Workflow wie bei einem roten Artikel.
- Beim Überschreiten öffnet sich zwingend ein Eingabefenster mit **Begründung als Pflichtfeld**.
- Ohne Begründung kann die Bestellung nicht weitergeführt werden.
- Die Freigabeanforderung wird an die berechtigten Freigeber gestellt. **Einkaufsleiter oder Geschäftsführung** können die Überschreitung freigeben.
- Sobald einer der dafür berechtigten Freigeber die Anforderung genehmigt hat, darf der Bestellvorgang fortgesetzt werden.
- Eine Ablehnung sperrt die Bestellung in der beantragten Menge; für einen neuen Versuch ist eine neue bzw. geänderte Anforderung erforderlich.
- Antragsteller, Artikel, normale Höchstmenge, beantragte Menge, Überschreitung, Begründung, Projekt/Bestellbezug, Zeitpunkt, Entscheidung und Freigebender werden nachvollziehbar gespeichert.
- Die Mengenprüfung muss im tatsächlichen Bestell-/Freigabeprozess technisch erzwungen werden und darf nicht nur ein Hinweis sein.
- Die Höchstmenge ist zunächst als **zulässige Menge je Bestellvorgang/Bestellposition** vorgesehen. Eine spätere zusätzliche Projekt- oder Zeitraumgrenze kann separat ergänzt werden, falls fachlich gewünscht.

### Rot – freigabepflichtiger Artikel

- Der Artikel darf unabhängig von der Menge nicht ohne ausdrückliche Begründung bestellt werden.
- Sobald ein roter Artikel bestellt bzw. zur Bestellung freigegeben werden soll, öffnet sich zwingend ein Eingabe-/Auswahlfenster.
- In diesem Fenster muss der Mitarbeiter eine **Begründung als Pflichtfeld** erfassen.
- Ohne Begründung kann der Vorgang nicht weitergeführt werden.
- Anschließend wird eine Freigabeanforderung an die **Geschäftsführung** gesendet; der **Einkaufsleiter** wird zusätzlich informiert/CC gesetzt.
- Die Bestellung darf erst nach dokumentierter Freigabe durch einen dafür berechtigten Freigeber fortgesetzt werden.
- Begründung, Antragsteller, Artikel, Menge, Projekt/Bestellbezug, Zeitpunkt, Freigabeentscheidung und Freigebender müssen nachvollziehbar gespeichert werden.

### Bedien- und Datenregel

- Die Ampel muss am Artikel sichtbar und zwingend gepflegt sein.
- Technisch ist sie als **Einfachauswahl** (Grün/Gelb/Rot) umzusetzen, nicht als drei unabhängig gleichzeitig aktivierbare Häkchen. Damit werden widersprüchliche Zustände ausgeschlossen.
- In der Oberfläche wird die Auswahl farblich mit Grün, Gelb und Rot dargestellt.
- Bei Auswahl **Gelb** wird das Feld **Höchstmenge** eingeblendet und verpflichtend.
- Bei neu angelegten Artikeln wird automatisch **Grün** vorbelegt.
- Bestehende Artikel erhalten bei der Einführung ebenfalls Grün, sofern keine abweichende Einstufung bewusst vorgenommen wird.
- Die Ampelklassifizierung und eine hinterlegte Höchstmenge müssen bei DATANORM-/Preisimporten erhalten bleiben und dürfen durch Lieferanten- oder Preisupdates nicht überschrieben werden.

---

## 5. Noch technisch/fachlich abzuarbeiten

- expliziter Upgrade-Test auf bestehender/produktionsnaher Datenbank,
- Browser-/Mobil-Smoke-Test,
- reales Projekt Ende-zu-Ende,
- Alt-Excel gegen Odoo vergleichen,
- ABB-DATANORM praktisch prüfen,
- Lageranfangsbestände und Anfangsbewertung,
- Pflichtdokumente/Rollen/Managementgrenzen,
- **Artikel-Ampel mit gelber Höchstmenge sowie gelbem/rotem Freigabeworkflow implementieren und testen**,
- Geschäftsführer- und Einkaufsleiter-Benutzer/E-Mail für Freigaben konfigurierbar machen,
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
