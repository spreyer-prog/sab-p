# SAB-P Suite – Fertigungsdruck und Typenschild-Automatik

> Sammelstand. Die noch hochzuladenden Fertigungsdokumente werden später einzeln analysiert und ergänzt.

## 1. Einordnung

Die Funktion wird innerhalb der **SAB-P Suite** im technischen Bereich umgesetzt:

**SAB-P Suite → Technik → Fertigungsunterlagen → Fertigungsdruck**

Der Benutzer bleibt in der SAB-P-Oberfläche.

## 2. Typenschild je physischem Schrank

Verbindliche Regel:

**Ein physischer Schrank erhält einen eigenen Typenschilddatensatz und einen eigenen Typenschildausdruck.**

Eine Verteilung kann mehrere Schränke enthalten. Auch wenn dasselbe Schrankprodukt mit einer Menge größer 1 verwendet wird, müssen daraus getrennte Schrankinstanzen entstehen.

Beispiel: Schrankprodukt mit Menge 3 = drei einzelne Schränke = drei Typenschilder und drei zuordenbare Dokumentensätze.

## 3. Automatische Vorbelegung

Der Typenschildbereich wird aus Projekt, Auftrag, Verteilung, Schrankposition und Schrankprodukt vorbelegt.

### Projektdaten

- Angebots-/Auftragsnummer
- Projektnummer
- Projektbezeichnung
- Kunde
- Bearbeiter
- Liefertermin

### Schrank- und Typenschilddaten

- Schranktyp
- Typenbezeichnung
- Verteilungsname
- Schrankposition bzw. laufende Schranknummer
- Baujahr
- DIN EN 61439 einschließlich Normteil
- Bemessungsspannung in V
- Bemessungsstrom in A
- Frequenz in Hz
- Sammelschienenstrom in A
- Schutzklasse
- Schutzart/IP-Code

Das Baujahr wird standardmäßig aus dem Fertigungsjahr vorbelegt.

## 4. Stammdaten am Schrankprodukt

Produkte, die als Schrank bzw. Schrankgehäuse verwendet werden, erhalten einen Bereich **Typenschild-/Schrankdaten**. Dort werden die oben genannten technischen Standardwerte und die zu verwendende Typenschildvorlage hinterlegt.

Die Auswahlliste der Schranktypen muss administrativ erweiterbar sein und darf nicht fest im Quellcode stehen. Als sichtbare Startwerte aus der bisherigen Maske sind unter anderem vorgemerkt:

- A (Zähler)
- A..D (Zähler)
- A
- B
- TH(G)
- TG(G)
- TL(G)
- TW(G)

## 5. Fehlende Daten und manuelle Ergänzung

Fehlende Pflichtdaten dürfen nicht unbemerkt leer gedruckt werden. Vor dem Druck muss je Schrank erkennbar sein:

- welche Werte automatisch übernommen wurden,
- welche Werte fehlen,
- welche Werte widersprüchlich sind.

Fehlen Schrank oder technische Angaben, kann der Benutzer über ein Auswahl- und Bearbeitungsfenster:

- ein vorhandenes Schrankprodukt auswählen,
- eine Schrankposition ergänzen,
- einen Schranktyp auswählen,
- technische Daten für den konkreten Schrank ergänzen oder korrigieren.

Manuelle Änderungen gelten zunächst nur für den konkreten Auftrag. Eine Übernahme in die Produktstammdaten erfolgt ausschließlich über eine ausdrückliche separate Aktion.

## 6. Fertigungsdruck – vorläufig sichtbare Dokumente

Die bisherige Maske enthält bzw. zeigt folgende auswählbare Ausdrucke:

- Laufkarte
- Bestellvorlage
- Blatt Endprüfung
- Blatt Versand
- Blatt Beipack
- Blatt Umbau
- Typenschild
- Prüfetikett
- Infoschild
- Kommissionierung
- Ordneretiketten

Die endgültige Dokumentliste, Datenfelder, Druckanzahl und Druckreihenfolge werden nach Analyse der Originaldokumente festgelegt.

## 7. Vorlagenverwaltung und Historie

Je Dokumentvorlage sind mindestens zu speichern:

- Dokumentart
- Vorlagenversion
- Erzeugungsebene: Projekt, Verteilung oder einzelner Schrank
- Pflichtdokument oder optional
- Anzahl der Ausdrucke
- Druckreihenfolge
- zu befüllende Felder und Datenquellen
- Pflichtfelder
- erlaubte manuelle Änderungen

Bei der endgültigen Erzeugung werden die verwendeten Werte als Snapshot am konkreten Schrank gespeichert. Spätere Änderungen am Produktstamm dürfen bereits erzeugte Typenschilder und Fertigungsdokumente nicht rückwirkend verändern. Wiederholungsdrucke verwenden den historischen Stand; geänderte Neuerzeugungen werden als neue Revision geführt.
