# SAB-P Suite V1 – Bedienungs- und Systemhandbuch

> Stand: Entwicklungsbranch `agent/leitfaden-gesamtstand`. Dieses Handbuch beschreibt nur Funktionen, die im aktuellen Entwicklungsstand vorhanden sind. Screenshots werden erst nach finaler UI-Abnahme ergänzt.

## 1. Systemüberblick und Gesamtprozess

Die SAB-P Suite bildet den durchgängigen Prozess ab:

**Projekt → Angebot → Kalkulation → Stückliste → Einkauf → Lager → Fertigung → Dokumente/Zeiten → Nachkalkulation → Kundenportal**

Die zentrale fachliche Regel lautet: Werte, die für einen historischen Vorgang relevant sind, werden nach Möglichkeit als Snapshot gespeichert. Spätere Änderungen an Stammdaten dürfen alte Angebote, Stücklisten, Lagerbewegungen, Dokumentrevisionen oder Zeitbuchungen nicht rückwirkend verfälschen.

## 2. Benutzer, Rollen und Berechtigungen

### Interne Standardbenutzer
Interne Benutzer arbeiten in der SAB-P/Odoo-Oberfläche. Der konkrete Funktionsumfang richtet sich zusätzlich nach Odoo-Projekt- und SAB-P-Gruppen.

### SAB-P Mitarbeiter
Die Gruppe **SAB-P Mitarbeiter** ist für mobile Fertigungs-, Montage- und Serviceabläufe vorgesehen. Mitarbeiter sollen nur eigene bzw. freie Fertigungsschritte, eigene Zeiten und eigene Rückmeldungen sehen. Kaufmännische Kalkulationswerte, EK und Margen gehören nicht in die mobile Mitarbeiteroberfläche.

### Projektleiter
Projektleiter können projektübergreifend Fertigungsschritte, Zeiten und Rückmeldungen verwalten und interne Vorgänge bearbeiten.

### SAB-P Kundenfreigaben
Nur Benutzer mit der Gruppe **SAB-P Kundenfreigaben** dürfen Kundenstatus, Dokumente oder Fotos ausdrücklich für das Kundenportal freigeben bzw. eine Freigabe zurückziehen. Die Prüfung erfolgt serverseitig und nicht nur über die Sichtbarkeit von Buttons.

### Portalbenutzer/Kunde
Portalbenutzer sehen ausschließlich ausdrücklich freigegebene Informationen der Projekte ihres eigenen Kundenkontos. Die Portalrouten prüfen die Zuordnung über den kommerziellen Partner.

## 3. Projekte und Projektnummern

### Projektnummer
Neue SAB-P Projekte erhalten automatisch eine unveränderliche Nummer nach dem konfigurierten Schema, standardmäßig z. B. `A26.0001`.

Bestehende ältere Projekte ohne SAB-P Nummer können beim ersten SAB-P Vorgang nachnummeriert werden. Eine bereits vergebene Projektnummer darf nicht geändert werden.

### Projektübersicht
Die SAB-P Projektübersicht zeigt insbesondere Projektnummer, Datum, Status, Projektbezeichnung, Kommission, Kunde, Bearbeiter, Angebotswert und Klassifikationen.

### Kunde erforderlich
Für ein Angebot oder einen Kundenportalstatus muss dem Projekt ein Kunde zugeordnet sein.

## 4. Angebote, Angebotsnummern und Revisionen

### Neues Angebot aus dem Projekt
Im Projekt kann über **Neues Angebot** ein SAB-P Angebot angelegt werden. Projekt, Kunde und Bearbeiter werden vorbelegt.

### Angebotsnummer
Angebote erhalten fortlaufende Nummern je Projekt, z. B. `A26.0001-01`, `A26.0001-02` usw. Eine vergebene Angebotsnummer darf nicht nachträglich verändert werden.

### Revisionen
Ein bestehendes SAB-P Angebot kann als Revision kopiert werden. Die historische Kalkulation bleibt über Snapshots nachvollziehbar.

## 5. Kalkulationsartikel, Suchbegriffe und Produktpositionen

Kalkulationsartikel bilden wiederverwendbare Kalkulationsbausteine. Sie können mehrere SAB-Produkte enthalten und besitzen Faktoren für Mechanik, Verdrahtung, Prüfung und Platzbedarf. Suchbegriffe erleichtern die Wiederverwendung in der Angebotskalkulation.

Änderungen am Kalkulationsstamm sollen bestehende Angebots-Snapshots nicht rückwirkend verändern.

## 6. SAB-Produkte, Hersteller, Lieferanten und Lieferantenartikel

### SAB-Produkt
Ein SAB-Produkt enthält u. a. Bezeichnung, Hersteller, Herstellerartikelnummer, DATANORM-Nummer, Platzeinheiten sowie absolute Zeiten für Mechanik, Verdrahtung und Prüfung.

### Lieferantenartikel
Ein SAB-Produkt kann mehrere Bezugsquellen besitzen. Die Beschaffungslogik berücksichtigt aktive und bevorzugte Lieferantenartikel; ansonsten kann die günstigste aktive Bezugsquelle verwendet werden.

### Einkaufspreis
Lieferantenpreise und Rabatte werden zum kalkulationswirksamen Netto-EK verarbeitet. Historische Angebote und Lagerentnahmen verwenden eingefrorene Werte und werden nicht mit später geänderten Preisen neu bewertet.

## 7. DATANORM-Import einschließlich Preislogik

Der DATANORM-Import ist für DATANORM 5, insbesondere ABB-Dateien mit Kennung 050, ausgelegt.

Unterstützt werden:
- direkte `.001`-Dateien,
- Lieferanten-ZIP-Dateien,
- ABB-ZIP-Auswahl mit bevorzugter KurztextinklTyp-Datei,
- Herstellerartikelnummer, Kurztext, Typ, EAN, Einheit und DATANORM-Preis,
- wiederholbare Aktualisierung vorhandener Artikel,
- optionales Anlegen fehlender Artikel.

Technische SAB-P Werte wie Zeiten, Platzeinheiten und Kalkulationszuordnungen werden durch DATANORM nicht überschrieben.

DATANORM-Preis und kalkulationswirksamer EK bleiben getrennt. Eine Übernahme in den EK muss je Lieferant bewusst freigegeben sein.

**Offener fachlicher Abnahmepunkt:** Die konkrete Preiswirkung von ABB-Z-Sätzen/NE-Metall-/Staffelpreisfällen wird erst anhand real benötigter Lieferantendaten festgelegt. Z-Sätze werden derzeit erkannt, aber nicht pauschal preiswirksam interpretiert.

## 8. Angebotskalkulation, Faktoren, Snapshots und Freigaben

Die Angebotskalkulation übernimmt Kalkulationsartikel als Snapshot in das jeweilige Angebot. Material-EK, Zeiten und technische Werte werden je Kalkulationsposition berechnet.

Zentrale Kalkulationsfaktoren werden am Angebot gespeichert, damit spätere Änderungen der globalen Einstellungen ein altes Angebot nicht verändern.

Änderungen geschützter Kalkulationsparameter erfordern den vorgesehenen Freigabecode und werden protokolliert.

Der kalkulatorische Netto-Richtwert ist eine Kalkulationsinformation und überschreibt den Odoo-Verkaufspreis nicht ungefragt.

## 9. Auftragsübergabe und Stücklisten

Eine Projektstückliste kann nur aus einem bestätigten Auftrag mit SAB-P Kalkulationspositionen erzeugt werden.

Die Stückliste wird aus den im Angebot eingefrorenen Komponentensnapshots erstellt. Nach Freigabe ist die Stückliste gesperrt. Freigegebene Positionen dürfen nicht still verändert oder gelöscht werden.

## 10. Einkauf und Materialbedarf

Aus einer freigegebenen Stückliste kann Einkaufsbedarf erzeugt werden.

Automatisch übernommen werden insbesondere Produkt, Menge, Einheit, Lieferantenartikel, Lieferant und historischer EK. Optionale Stücklistenpositionen werden nicht automatisch disponiert.

Statusfolge:
**Offen → Bestellt → Geliefert**

Eine Position wird nicht mehrfach als Einkaufsbedarf erzeugt. Die Lieferung erzeugt genau einen Lagerzugang.

## 11. Lager, Reservierungen, Entnahmen und Lagerbewertung

Unterstützte Lagerbewegungen:
- Zugang,
- Entnahme,
- Reservierung,
- Freigabe einer Reservierung.

Je Produkt werden Bestand, reservierter Bestand und verfügbarer Bestand berechnet.

Entnahmen dürfen nicht unbemerkt bereits reservierte Mengen verbrauchen. Die Bewertung einer Bewegung wird historisch auf der Bewegung gespeichert. Materialentnahmen verwenden den zu diesem Zeitpunkt ermittelten Lagerwert und verändern sich nicht, wenn Lieferantenpreise später geändert werden.

## 12. Fertigungsaufträge und Fertigungsschritte

Ein Fertigungsauftrag kann nur aus einer freigegebenen Stückliste entstehen.

Standard-Fertigungsschritte:
1. Mechanische Fertigung
2. Mechanischer Aufbau
3. Bestückung Geräte
4. Bestückung Klemmen
5. Vorbereitung Verdrahtung
6. Elektrische Fertigung
7. Prüfung
8. Endkontrolle

Arbeitsschritte kennen die Zustände **Offen, In Arbeit, Pausiert, Fertig, Entfällt**.

### Übernehmen
Ein freier Arbeitsschritt kann von einem berechtigten Mitarbeiter übernommen werden.

### Start / Fortsetzen
Start setzt den Schritt auf **In Arbeit**, weist bei Bedarf den aktuellen Mitarbeiter zu und speichert die erste Startzeit. Ein pausierter Schritt kann fortgesetzt werden, ohne die ursprüngliche Startzeit zu verlieren.

### Pause
Nur ein laufender Schritt kann pausiert werden. Die Pausenzeit wird gespeichert.

### Fertig melden
Ein Schritt kann aus Offen/In Arbeit/Pausiert fertiggemeldet werden. Die Fertigzeit wird gespeichert.

### Fertigungsauftrag abschließen
Ein Fertigungsauftrag kann erst abgeschlossen werden, wenn alle Schritte entweder **Fertig** oder **Entfällt** sind. Danach ist der Auftrag weitgehend gesperrt.

## 13. Dokumentenverwaltung, Freigaben und Revisionen

Projektdokumente besitzen Dokumentart, Datei, Dateiname, Version und Status.

Dokumentarten umfassen u. a. Kundenbestellung, Zeichnung/Plan, Stückliste, Prüfprotokoll, Errichter-/Konformitätserklärung, Lieferschein, Foto, Korrespondenz und Sonstiges.

### Interne Freigabe
Ein Dokument muss intern freigegeben sein, bevor es für Kunden freigegeben werden kann.

### Revision
Freigegebene Dokumentstände werden nicht überschrieben. Änderungen erfolgen über eine neue Revision. Der alte Stand bleibt als überholt erhalten.

### Kundenfreigabe
Nur ein intern freigegebenes Dokument mit Kundenprojekt kann durch einen Benutzer mit **SAB-P Kundenfreigaben** im Kundenportal sichtbar gemacht werden. Änderungen an kundensichtbaren Bezeichnungen/Hinweisen ziehen die Freigabe zurück, damit geänderter Inhalt erneut bewusst freigegeben werden muss.

## 14. Service, Montage und Zeiterfassung

Zeitbuchungen enthalten Projekt, Mitarbeiter, Datum, Tätigkeitsart, Stunden und Kostensatz. Fahrtzeit ist eine eigene Tätigkeitsart.

Zeit kann direkt aus einem Fertigungsschritt vorbelegt werden. Gebuchte Zeiten dürfen nicht nachträglich in ihren wesentlichen Abrechnungsdaten verändert oder gelöscht werden.

Die Summe gebuchter Zeiten aktualisiert die Ist-Stunden des Projekts.

## 15. Nachkalkulation, Deckungsbeitrag und Reporting

Die Projektnachkalkulation ermittelt:
- kalkulierte Stunden,
- Ist-Stunden,
- Stundenabweichung absolut und in Prozent,
- Ist-Lohnkosten,
- historisch bewertete Materialentnahmen,
- Ist-Direktkosten,
- Angebotssumme,
- Deckungsbeitrag vor Gemeinkosten,
- Deckungsbeitrag in Prozent,
- Ergebnisstatus.

Listen-, Pivot- und Diagrammansichten unterstützen die Auswertung.

**Offener fachlicher Abnahmepunkt:** Die endgültigen Grenzwerte für Management-Warnungen müssen mit realen SAB-P Projekten bestätigt werden.

## 16. Mitarbeiter-App / mobile Mitarbeiteroberfläche

Die Mitarbeiteroberfläche ist als responsive Odoo-Weboberfläche/PWA-orientierter Workflow ausgelegt.

Bereitgestellt werden:
- Meine Arbeit,
- freie Arbeit,
- Übernehmen,
- Start/Fortsetzen,
- Pause,
- Fertigmeldung,
- Zeit erfassen,
- Rückmeldung,
- Foto hochladen,
- Materialbedarf melden,
- eigene Zeiten,
- eigene Rückmeldungen.

Mitarbeiter sehen über Record Rules nur die für sie vorgesehenen eigenen bzw. freien Arbeitsdaten. Kaufmännische Daten gehören nicht in diese Oberfläche.

## 17. Kundenportal / Kunden-App und Kundenstatus

Das Kundenportal ist eine responsive Web-/Portalansicht unter `/my/sab-projects`.

Kunden sehen ausschließlich freigegebene eigene Projekte mit Projektnummer, Projektbezeichnung, freigegebenem Kundenstatus, Fortschritt, ggf. Liefertermin, Kundentext, freigegebenen Dokumenten und freigegebenen Fotos.

Interne Projekt-, Einkaufs-, Lieferanten-, Kalkulations-, Mangel- oder Margendaten werden vom Portalcontroller nicht als Portalinhalt bereitgestellt.

## 18. Foto- und Dokumentfreigabe für Kunden

Fertigungsfotos entstehen als Mitarbeiter-Rückmeldungen. Ein Foto muss intern bearbeitet sein, bevor es für den Kunden freigegeben werden kann.

Nur Benutzer mit **SAB-P Kundenfreigaben** dürfen diese Freigabe setzen. Bildtextänderungen ziehen eine vorhandene Kundenfreigabe zurück.

Dokumente folgen demselben Grundprinzip: intern freigeben → Kundeninhalt festlegen → ausdrücklich für Kunden freigeben.

## 19. Einstellungen und administrativer Bereich

Im Einstellungsbereich liegen u. a. Nummernkreis- und Kalkulationsparameter. Kalkulationsrelevante Änderungen werden geschützt und protokolliert.

Vor Produktivstart sind Nummernkreis, Kalkulationsfaktoren, Benutzergruppen und Lageranfangsbestände zu prüfen.

## 20. Fehlerbehebung und typische Bedienfehler

### „Bitte zuerst einen Kunden im Projekt hinterlegen“
Dem Projekt fehlt der Kunde. Kunde setzen und Vorgang erneut ausführen.

### „Stückliste kann erst ... erzeugt werden“
Das Angebot ist noch nicht bestätigt oder enthält keine SAB-P Kalkulationspositionen.

### „Eine freigegebene Stückliste ist gesperrt“
Freigegebene Stücklisten sind bewusst unveränderlich. Änderungen müssen über den vorgesehenen neuen Vorgang/Neuaufbau vor Freigabe erfolgen.

### „Fertigungsauftrag ... erst abgeschlossen ...“
Es existieren noch offene, laufende oder pausierte Fertigungsschritte.

### „Sie haben keine Berechtigung für Kundenportal-Freigaben“
Der Benutzer gehört nicht zur Gruppe **SAB-P Kundenfreigaben**.

### „Gebuchte Zeiten dürfen nicht ... verändert werden“
Die Zeit ist bereits bestätigt. Historische Ist-Zeiten werden nicht nachträglich überschrieben.

### Kunde sieht ein Projekt/Dokument/Foto nicht
Prüfen: richtiger Projektkunde, Kundenstatus ausdrücklich freigegeben, Dokument intern freigegeben und kundensichtbar, Foto intern bearbeitet und kundensichtbar.

## 21. Backup, Upgrade, Rollback und technischer Betrieb

Entwicklung erfolgt auf `agent/leitfaden-gesamtstand`. `main` bleibt bis zur Abnahme stabil.

Vor einem Merge in `main` müssen mindestens erfüllt sein:
- vollständiger Odoo.sh Modul-Upgrade-Build ohne SAB-P Testfehler,
- relevante SAB-P Warnings bereinigt,
- End-to-End-Test bestanden,
- Rollen-/Portaltrennung geprüft,
- Daten-/Kalkulationsabnahme erfolgt,
- Produktivcheckliste abgearbeitet.

Rollback-Grundsatz: Vor Produktivmerge muss der letzte stabile `main`-Commit dokumentiert bleiben. Odoo.sh-Backups/Snapshots sind unmittelbar vor Modulupgrade und Produktivumschaltung zu erzeugen. Ein fehlgeschlagenes Upgrade wird nicht durch manuelle Datenbankkorrekturen „gerettet“, sondern auf den letzten konsistenten Stand zurückgeführt und im Entwicklungsbranch behoben.

## 22. Vollständiger Beispielprozess

1. Projekt mit Kunde anlegen → automatische `Axx.xxxx` Projektnummer.
2. Im Projekt **Neues Angebot** öffnen → Kunde/Projekt sind vorbelegt.
3. Kalkulationsartikel in die SAB-P Angebotskalkulation übernehmen.
4. Material, Zeiten, Faktoren und Richtwert prüfen.
5. Angebot bestätigen.
6. SAB-P Stückliste aus den Angebots-Snapshots erzeugen.
7. Stückliste prüfen und freigeben.
8. Einkaufsbedarf erzeugen; optionale Positionen bleiben außen vor.
9. Bedarf auf **Bestellt**, bei Eingang auf **Geliefert** setzen → Lagerzugang entsteht.
10. Fertigungsauftrag aus der freigegebenen Stückliste erzeugen.
11. Mitarbeiter übernimmt Arbeitsschritt, startet, kann pausieren/fortsetzen, Zeiten und Rückmeldungen erfassen und fertigmelden.
12. Alle Fertigungsschritte abschließen bzw. begründet auf **Entfällt** setzen.
13. Fertigungsauftrag abschließen.
14. Projektdokumente intern freigeben und ggf. revisionssicher aktualisieren.
15. Kundenstatus öffnen; internen Statusvorschlag prüfen und bewusst übernehmen.
16. Kundentext festlegen und Kundenstatus ausdrücklich freigeben.
17. Nur ausgewählte Dokumente/Fotos ausdrücklich für Kunden freigeben.
18. Kunde sieht unter `/my/sab-projects` ausschließlich seine freigegebenen Inhalte.
19. Nachkalkulation öffnen und Soll-/Ist-Zeiten, Materialkosten und Deckungsbeitrag prüfen.
20. Projekt fachlich abschließen und Ergebnisse für spätere Kalkulationsverbesserungen verwenden.

## Verbleibende Abnahmepunkte vor Produktivfreigabe

Diese Punkte können nicht seriös aus Programmlogik erfunden werden und müssen mit realen SAB-P Daten bestätigt werden:
- Alt-Excel gegen Odoo mit identischem Musterprojekt,
- ABB-Z-Satz-/NE-Metall-Sonderfälle, sofern tatsächlich verwendet,
- endgültige Deckungsbeitrags-Grenzwerte,
- finale Rollenzuordnung realer Mitarbeiter,
- Lageranfangsbestände und Anfangsbewertung,
- Pflichtdokumente je realem Projektstatus,
- finaler Odoo.sh Upgrade-/Portaltest auf der vorgesehenen Produktivdatenbank.
