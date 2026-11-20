# SAB-P Suite – Leitfaden Gesamtstand

Stand: 20.08.2026

Dieser Leitfaden ist die verbindliche fachliche Reihenfolge für die weitere Entwicklung der SAB-P Suite. Neue Anforderungen, Screenshots, Excel-/PDF-/Word-Dateien und sonstige Vorlagen werden zuerst analysiert und anschließend in diesen Leitfaden oder einen eindeutig verlinkten Sammelstand übernommen. Erst danach wird die Funktion implementiert.

## 1. Grundregel zur weiteren Entwicklung

Die Entwicklung erfolgt in kleinen, kontrollierten Schritten. Jeder fachlich abgeschlossene Schritt wird separat committed und anschließend durch automatisierte Tests bzw. Odoo.sh-Builds abgesichert.

### Priorität

Verbindliche Priorität ist **zuerst die vollständige fachliche Umsetzung aller vom Nutzer übergebenen technischen Anforderungen und Prozessschritte**. Ein grüner Build ist wichtig, darf aber nicht dazu führen, dass fachlich noch offene Anforderungen zurückgestellt, vereinfacht oder entfernt werden.

Reihenfolge:

1. neue Anforderung oder Datei analysieren und dauerhaft dokumentieren,
2. fachlich richtige Stelle im Gesamtprozess bestimmen,
3. Funktion vollständig umsetzen,
4. Abhängigkeiten zu bereits umgesetzten Funktionen berücksichtigen,
5. danach technische Fehler, Migrationen, Tests und Odoo.sh-Build systematisch bereinigen,
6. am Ende muss sowohl der Leitfaden vollständig umgesetzt als auch der Build grün sein.

Ein Buildfehler wird sofort behoben, wenn er die weitere Entwicklung technisch blockiert. Andernfalls bleibt die fachliche Gesamtumsetzung vorrangig.

Die Reihenfolge dieses Leitfadens darf nicht durch neue Einzelwünsche verloren gehen. Neue Anforderungen werden an der fachlich richtigen Stelle ergänzt, ohne bereits festgelegte Prozessschritte zu verdrängen.

Für jede neu bereitgestellte Datei oder Maske gilt verbindlich:

1. Datei/Maske analysieren.
2. Zweck und Prozessstelle bestimmen.
3. alle sichtbaren Felder, Auswahlwerte, Pflichtfelder und Ausgaberegeln erfassen.
4. Datenquelle jedes automatisch vorzufüllenden Feldes festlegen.
5. festlegen, ob die Ausgabe pro Projekt, Verteilung oder physischem Schrank erfolgt.
6. Druckanzahl, Reihenfolge, Revision und Wiederholungsdruck festlegen.
7. Ergebnis im Repository dokumentieren.
8. erst danach programmieren.

Dadurch bleiben die aus einer hochgeladenen Vorlage gewonnenen Anforderungen dauerhaft im Projekt dokumentiert und müssen nicht erneut fachlich hergeleitet werden.

## 2. Oberflächenstruktur der SAB-P Suite

Der Benutzer arbeitet möglichst vollständig innerhalb der SAB-P Suite. Odoo-Standardmodelle werden im Hintergrund verwendet, aber über SAB-P-Menüs und SAB-P-Actions geöffnet.

Hauptbereiche:

1. Projekte
2. Kalkulation / Kalkulationsdatenbank
3. Einkauf / Lager
4. Technik
5. Mitarbeiter
6. Einstellungen

Unter Technik gehören mindestens:

- Fertigungsaufträge
- Gesamt- und Einzelstücklisten
- Fertigungsunterlagen / Fertigungsdruck
- Typenschilder
- Protokolle
- spätere Revisions- und Enddokumentation

## 3. Verbindliche Gesamtprozess-Reihenfolge

### Phase A – Angebot und Auftrag

1. Projekt anlegen.
2. Angebot kalkulieren.
3. Mengen von Bauteilen und Positionen vollständig berücksichtigen.
4. MwSt. aus den hinterlegten Kalkulations-/Steuereinstellungen übernehmen.
5. Solange der Vorgang nur Angebot ist, bleiben Material- und Beschaffungsfortschritt in der Projektliste leer.
6. Angebot freigeben und versenden.
7. Auftrag erhalten / Verkaufsauftrag bestätigen.

### Phase B – Technik und Stücklistenfreigabe

8. Gesamtstückliste erzeugen.
9. Einzelstücklisten je Verteiler/Schaltschrank erzeugen.
10. Gesamtstückliste technisch freigeben.
11. Vor Einkaufsübergabe Abfrage anzeigen, ob die Einzelstücklisten zusätzlich einzeln geprüft/freigegeben werden sollen.
12. Für die Einkaufsübergabe reicht grundsätzlich die freigegebene Gesamtstückliste. Nur bei ausdrücklicher Auswahl müssen die Einzelstücklisten zusätzlich einzeln freigegeben sein.

### Phase C – Materialbedarf und Lagerprüfung

13. Materialanforderung/Beschaffungspaket erzeugen.
14. Bedarf je Projekt und Verteiler erhalten.
15. realen Odoo-Lagerbestand prüfen.
16. bereits für andere Projekte reservierte Mengen berücksichtigen.
17. für das Projekt verfügbare Menge reservieren.
18. tatsächlichen Fehlbestand ermitteln.
19. Mindestbestand separat prüfen.
20. Ohne hinterlegten Mindestbestand darf nur der reale Fehlbestand bestellt werden.
21. Bei unterschrittenem Mindestbestand muss der Benutzer ausdrücklich entscheiden, ob zusätzlich bis zum Mindestbestand aufgefüllt wird.
22. Verpackungseinheiten und Mindestbestellmengen des Lieferanten sind als Einkaufshinweis zu berücksichtigen; sie dürfen den realen Projektfehlbestand nicht ungefragt erhöhen.

### Phase D – Bestellvorschlag und Bestellung

23. Fehlbestände nach dem tatsächlichen Lieferanten gruppieren.
24. je Lieferant einen Bestellvorschlag erzeugen.
25. Projekt, Verteiler/Schaltschrank und Ursprungsposition an jeder Bestellposition erhalten.
26. Bestellvorschlag durch Einkauf prüfen und bearbeiten.
27. Bestellung zur Freigabe vorlegen.
28. Bestellfreigabe durch getrennte Rolle/Freigeber.
29. aus dem SAB-P-Prozess eine echte Odoo-`purchase.order` erzeugen bzw. verwenden.
30. Bestellung aus der SAB-P Suite versenden/drucken.
31. doppelte Bestellung derselben Bedarfsposition technisch verhindern.

### Phase E – Lieferanten-Auftragsbestätigung und Terminverfolgung

32. Lieferanten-Auftragsbestätigung erfassen.
33. AB-Nummer, AB-Datum und Originaldokument speichern.
34. bestätigten Preis, bestätigte Menge und bestätigten Liefertermin je Position erfassen.
35. Abweichungen zur Bestellung sichtbar machen.
36. Liefertermine überwachen.
37. überfällige Positionen anzeigen.
38. Lieferanten-Erinnerung/Nachfrage auslösen und protokollieren.
39. Auswirkungen auf Projekt und Verteiler sichtbar halten.

### Phase F – Wareneingang

40. echte Odoo-Wareneingänge (`stock.picking`) verwenden.
41. Lieferanten-Lieferscheinnummer und Lieferscheindatum erfassen.
42. Lieferschein als Datei/Scan am Wareneingang speichern.
43. tatsächlich gelieferte Menge je Position buchen.
44. Teilwareneingänge zulassen.
45. bei Teillieferung einen echten Odoo-Rückstand/Backorder für die Restmenge erzeugen.
46. jede weitere Teillieferung erhält ihren eigenen Lieferscheinbezug.
47. Mehr-/Minderlieferungen sichtbar machen.
48. beschädigte oder falsche Ware kennzeichnen.
49. Lieferantenrücksendung über Odoo-Lagerprozess ermöglichen.
50. Projekt- und Verteilerzuordnung durch alle Lagerbewegungen erhalten.

### Phase G – Einlagerung und Kommissionierung

51. Wareneingang in den tatsächlichen Odoo-Lagerbestand buchen.
52. eingegangene projektbezogene Ware automatisch/gezielt reservieren.
53. Kommissionierung je Materialanforderung und Verteiler durchführen.
54. Odoo-Lagerbewegung für die tatsächliche Materialausgabe verwenden.
55. nicht verwendetes Material zurückbuchen können.
56. Inventur, Umlagerung, Bestandskorrektur, Ausschuss/Schwund und Rückgaben müssen nachvollziehbar bleiben.

### Phase H – Eingangsrechnung und kaufmännischer Abschluss

57. Lieferantenrechnung als echte Odoo-Eingangsrechnung (`account.move`) erzeugen/erfassen.
58. Rechnungsnummer, Rechnungsdatum, Liefer-/Leistungsdatum, Zahlungsziel, Steuer, Netto, Brutto und Skonto erfassen.
59. Rechnung mit Bestellung und Wareneingang verknüpfen.
60. Drei-Wege-Abgleich durchführen: Bestellung ↔ Wareneingang ↔ Eingangsrechnung.
61. Preis-, Mengen- und Steuerabweichungen vor Freigabe sichtbar machen.
62. doppelte Lieferantenrechnungen verhindern/erkennen.
63. Gutschriften und Rechnungskorrekturen unterstützen.
64. Zahlungsstatus und Fälligkeit sichtbar machen.
65. Bestellung erst kaufmännisch abschließen, wenn offene Lieferungen, Rückstände, Retouren und Rechnungsabweichungen geklärt sind.

## 4. Fertigung

66. Fertigungsauftrag je vorgesehenem Fertigungsumfang erzeugen.
67. Materialstatus und Kommissionierungsstatus müssen vor bzw. während der Fertigung sichtbar sein.
68. Fertigungsschritte, Bearbeiter, Start/Pause/Fertigmeldung und Prüfung protokollieren.
69. Physische Schränke/Verteiler müssen eindeutig identifizierbar sein.
70. Bei einer Menge größer 1 eines Schrankprodukts entstehen getrennte physische Schrankinstanzen.

## 5. Fertigungsdruck und Typenschild

Dieser Abschnitt wird durch `docs/FERTIGUNGSDRUCK_TYPENSCHILD_SAMMELSTAND.md` konkretisiert.

71. Fertigungsdruck wird unter **SAB-P Suite → Technik → Fertigungsunterlagen/Fertigungsdruck** geführt.
72. Ein physischer Schrank erhält einen eigenen Typenschilddatensatz und einen eigenen Typenschildausdruck.
73. **Die Schrankmenge ist gleichzeitig die Druckmenge aller als „pro physischem Schrank“ definierten Dokumente. Beispiel: Schrankmenge 3 = drei physische Schrankinstanzen = drei Typenschilder und drei Ausgaben jedes schrankbezogenen Pflichtdokuments.**
74. Typenschilddaten werden möglichst aus Projekt, Auftrag, Verteilung, physischer Schrankinstanz und dem verwendeten Schrankprodukt vorbelegt.
75. Schrankprodukt erhält Stammdaten für Typenschild/Schrankdaten.
76. Fehlende oder widersprüchliche Pflichtdaten müssen vor Druck angezeigt werden.
77. Fehlt eine automatische Zuordnung, muss ein Auswahl-/Bearbeitungsfenster die manuelle Auswahl eines Schrankprodukts und die Ergänzung technischer Daten erlauben.
78. Manuelle projektspezifische Änderungen dürfen nicht ungefragt den Produktstamm verändern.
79. Drucke werden als Snapshot/Revision gespeichert, damit spätere Stammdatenänderungen alte Ausdrucke nicht verändern.

Vorgemerkte Typenschildfelder:

- Auftragsnummer
- Projektnummer
- Projekt
- Kunde
- Bearbeiter
- Liefertermin
- Verteilung
- Schrankposition / laufende Schranknummer
- Schranktyp
- Typenbezeichnung
- Baujahr
- DIN EN 61439
- Normteil
- Bemessungsspannung
- Bemessungsstrom
- Frequenz
- Sammelschienenstrom
- Schutzklasse
- IP-Schutzart

## 6. Protokolle nach/bei Fertigung

Dieser Abschnitt wird durch `docs/PROTOKOLLERSTELLUNG_SAMMELSTAND.md` konkretisiert.

80. Unter Technik gibt es einen eigenen Reiter **Protokolle**.
81. Protokolle werden projektbezogen gestartet, aber verteiler-/schrankbezogen erzeugt.
82. Projekt- und Kundendaten werden automatisch vorausgefüllt.
83. Die Verteiler werden aus dem Auftrag/Projekt eingelesen und einzeln auswählbar dargestellt.
84. Dokumente werden je Verteiler bzw. je physischem Schrank gemäß Dokumentdefinition erzeugt.
85. Dokumenttyp bestimmt die Pflichtfelder und das Drucklayout.
86. Konformitätserklärung wird für jeden Verteiler separat erzeugt; sofern die Dokumentdefinition auf physischem Schrank basiert, gilt zusätzlich die Schrankmenge als Dokumentmenge.
87. Prüfprotokolle werden als echte strukturierte Prüfdaten gespeichert; nicht nur als statische PDF-Datei.
88. Die jeweils verwendeten Daten werden als Dokument-Snapshot gespeichert.
89. Wiederholungsdruck verwendet den historischen Stand; fachlich geänderte Neuerzeugung erzeugt eine neue Revision.

Aktuell vorgemerkte Dokumentarten:

- Konformitätserklärung
- Prüfprotokoll Fertigung
- Prüfprotokoll Endkontrolle
- Laufkarte
- Bestellung/Übersicht Fehlteile
- Typenschild
- Prüfetikett / Infoschild
- Beipackzettel
- Blatt Versand
- Blatt Umbau
- Kommissionierungsdruck
- Ordneretiketten

## 7. Regel für neue hochgeladene Dokumente

Jede weitere vom Nutzer bereitgestellte Fertigungs-, Prüf-, Bescheinigungs- oder Druckvorlage wird in der vorgegebenen Reihenfolge analysiert.

Das Analyseergebnis muss mindestens enthalten:

- Originalbezeichnung/Dateiname
- fachlicher Zweck
- Prozessphase
- Ausgabeebene: Projekt / Verteilung / physischer Schrank
- automatisch vorzufüllende Felder
- manuell auszufüllende Felder
- Auswahlfelder und zulässige Werte
- Pflichtfelder
- Prüflogik / Plausibilitätsprüfung
- Unterschrift/Prüfer/Freigabe, sofern vorhanden
- Druckanzahl
- Druckreihenfolge
- Dateiformat
- Archivierungs- und Revisionsregel
- Verknüpfung zu Projekt, Auftrag, Verteiler und Schrank

Die Erkenntnisse werden dauerhaft im Repository unter `docs/` gesichert. Bereits analysierte Vorlagen werden bei späterer Entwicklung aus diesen Spezifikationen weiterverwendet; der fachliche Inhalt soll nicht erneut vom Nutzer abgefragt werden.

## 8. Technische Leitplanke

SAB-P ist die individuelle Oberfläche und Prozesssteuerung. Für stabile Kernprozesse werden die Odoo-Standardmodelle verwendet:

- Bestellung: `purchase.order` / `purchase.order.line`
- Wareneingang, Rückstand, Rücksendung und Lagerbewegung: `stock.picking` / `stock.move`
- Eingangsrechnung/Gutschrift: `account.move` / `account.move.line`

SAB-P hält zusätzlich die projekt-, verteiler- und schrankbezogene Zuordnung und zeigt die Odoo-Dokumente innerhalb der SAB-P Suite an.

Es darf dauerhaft keine zweite, widersprüchliche Wahrheit für Bestellung, Bestand oder Rechnung entstehen.

## 9. Bestätigter technischer Entwicklungsstand

### Odoo.sh-Basisstand 20.08.2026

Der zuletzt bestätigte Odoo.sh-Basisstand vor Erweiterung der Lieferantenrückgabe umfasst **138 Tests mit 0 Failures und 0 Errors**. Damit sind insbesondere folgende integrierte Standard-Odoo-Abläufe als gemeinsame Basis bestätigt:

- Erzeugung echter Odoo-Bestellungen aus SAB-P-Materialbedarfen,
- getrennte Bestellfreigabe und Rollenprüfung,
- Lieferanten-Auftragsbestätigung mit Abweichungsprüfung,
- vollständiger und teilweiser Wareneingang,
- Odoo-Backorder bei Teillieferungen,
- Erhalt der SAB-P-Projekt-/Bedarfs-/Schrankzuordnung im Backorder,
- Odoo-Kommissionierung und Lagerreservierung,
- Erzeugung und Buchung echter Lieferantenrechnungen,
- Drei-Wege-Abgleich Bestellung ↔ Wareneingang ↔ Eingangsrechnung einschließlich expliziter Abweichungsfreigabe.

Dieser grüne Stand ist die Referenzbasis für nachfolgende Erweiterungen. Neue Funktionen dürfen erst nach eigenem Odoo.sh-Build als build-bestätigt bezeichnet werden.

### Lieferantenrückgabe – aktueller nächster Schritt

Die Lieferantenrückgabe nach bereits gebuchtem Wareneingang ist implementiert und besitzt einen eigenen Regressionstest, ist aber noch **nicht Odoo.sh-buildbestätigt**.

Verbindlicher Sollablauf:

1. vollständiger Wareneingang wird gebucht,
2. Rückgabe wird über den echten Odoo-Return-Wizard `stock.return.picking` erzeugt,
3. die Rückgabebewegung behält Materialbedarf, Projekt, Beschaffungspaket und Schrankzuordnung,
4. die Rücksendung reduziert die effektive Odoo-Eingangsmenge,
5. SAB-P gibt die entsprechende Projektreservierung frei,
6. der Bedarf wechselt bei verbleibender Unterdeckung wieder auf `ordered` / `partial_received`,
7. der reale Fehlbestand wird wieder als Bestellbedarf sichtbar,
8. die Rücksendung wird als eigener nachvollziehbarer Lagerabgang protokolliert.

Referenztest: 6 Stück erhalten → 2 Stück an Lieferant zurück → 4 Stück effektiv erhalten → 2 Stück Fehlbestand.
