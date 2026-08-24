# SAB-P Suite – Protokolle erstellen

> Sammelstand. Neue Masken und Dokumente werden fortlaufend analysiert und hier dauerhaft ergänzt.

## 1. Einordnung in die SAB-P Suite

Nach dem Bereich **Fertigung** wird ein eigener Hauptreiter bzw. Technik-Unterreiter **Protokolle erstellen** vorgesehen.

Vorgesehene Reihenfolge im technischen Prozess:

**Fertigung → Protokolle erstellen → Dokumentation / Projektabschluss**

Der Benutzer bleibt vollständig innerhalb der Oberfläche der SAB-P Suite.

## 2. Grundaufbau der Maske

Die vorgelegte Bestandsmaske zeigt zwei nebeneinanderliegende Protokollbereiche. Die neue SAB-P-Maske soll dieselbe fachliche Funktion abbilden, jedoch projekt- und schrankbezogen aus den vorhandenen SAB-P-Daten vorbelegt werden.

Je Protokollbereich sind aktuell folgende Felder erkennbar:

- Kunden-Nr.
- Kundenname
- Auftragsnummer
- Projektname
- Verteiler
- Schranktyp
- Schrankbreite
- Ort
- Projekt-Kunde
- Seriennummer
- Gerätetyp
- Prüfgerät
- Prüfprotokoll

Aktuell sichtbare Aktionen:

- **Protokoll erstellen**
- **Speichern**
- **Seriennr. generieren**
- **Altes Protokoll laden**

## 3. Analysierte Altdatei: A26.0303 - Konformitätserklärung.xls

Die hochgeladene Originaldatei liegt im alten binären Excel-Format `.xls` vor und ist als verbindliche fachliche Referenz für die Neuerstellung in der SAB-P Suite aufgenommen.

### 3.1 Erkannte Arbeitsblätter

Im Altbestand sind mindestens folgende Arbeitsblätter bzw. Dokumentbereiche enthalten:

- Übersicht
- Prüfprotokoll
- Herstellererklärung
- DGUV V3
- Konformitätserklärung EMV
- Konformitätserklärung NSR

Diese Struktur zeigt, dass die Datei nicht nur eine einzelne Konformitätserklärung enthält, sondern als zentrale Datenquelle mehrere voneinander abhängige Erklärungen und Prüfunterlagen erzeugt.

### 3.2 Erkannte zentrale Eingabe-/Referenzfelder

In der Arbeitsmappe sind als zentrale Bezeichnungen bzw. Referenzfelder erkennbar:

- Auftragsnummer
- DBO
- Kunde
- Monteur
- Name
- Ort
- Projekt
- Projekt2
- Prüfer
- PSC
- Seiten
- Teil
- Typ

Diese Felder werden in der neuen SAB-P-Lösung nicht als lose Excel-Zellverweise nachgebaut, sondern als strukturierte Datenfelder geführt. Alle abhängigen Dokumente greifen anschließend auf dieselben zentralen Werte zu.

### 3.3 Verbindliche Übertragungsregel

Die alte Excel-Logik mit Zellverweisen dient als fachliche Vorlage. In Odoo/SAB-P wird dieselbe Abhängigkeit sauber modelliert:

**Projekt/Auftrag/Verteiler/Schrank → zentrale Dokumentdaten → Konformitätserklärung / Prüfprotokoll / Herstellererklärung / DGUV-V3 / EMV / NSR**

Wird ein zentraler Wert geändert, werden noch nicht finalisierte Dokumente aus diesem Datensatz aktualisiert. Bereits finalisierte bzw. gedruckte Dokumente bleiben als Snapshot unverändert und werden nur über eine neue Revision geändert.

### 3.4 Ausgabeebene und Mengenregel

Die Konformitäts- und Prüfunterlagen werden je nach Dokumentart auf der fachlich richtigen Ebene erzeugt:

- Konformitätserklärung: mindestens je Verteiler; bei schrankbezogener Ausführung entsprechend je physischem Schrank.
- Prüfprotokoll: je physischem Schrank.
- Typenschild: je physischem Schrank.
- Hersteller-/DGUV-/EMV-/NSR-Unterlagen: entsprechend der später aus dem Originalblatt bestätigten Ausgabeebene.

Für alle als **pro physischem Schrank** definierten Dokumente gilt zwingend:

**Schrankmenge = Dokument-/Druckmenge.**

Beispiel: Schrankposition Menge 3 = drei Schrankinstanzen = drei Typenschilder und drei schrankbezogene Prüfprotokolle.

### 3.5 Noch technisch zu extrahierende Alt-Excel-Verweise

Die alte `.xls`-Datei enthält binäre Excel-Zell- und Formelreferenzen. Die Arbeitsblattstruktur und zentralen Referenznamen sind bereits identifiziert. Vor dem endgültigen Nachbau jedes einzelnen Layouts werden die konkreten Abhängigkeiten je Blatt noch gegen die Originaldatei geprüft und anschließend als explizite SAB-P-Datenquelle dokumentiert. Die Originaldatei muss dafür nicht erneut hochgeladen werden; sie ist im Gespräch vorhanden und fachlich in diesem Sammelstand referenziert.

## 4. Vorläufige fachliche Regeln

- Die Maske wird aus dem ausgewählten Projekt, Auftrag, Verteiler und physischen Schrank automatisch vorbelegt.
- Bei mehreren Verteilungen oder Schränken muss der Benutzer den konkreten Datensatz auswählen können.
- Jeder physische Schrank erhält eine eigene Seriennummer und ein eigenes Prüfprotokoll.
- Mehrere gleiche Schränke mit einer Menge größer 1 dürfen nicht zu einem einzigen Protokoll zusammengefasst werden.
- Kunden- und Projektdaten werden aus den vorhandenen SAB-P-Stammdaten übernommen.
- Schranktyp und Schrankbreite werden möglichst aus dem hinterlegten Schrankprodukt bzw. der Schrankposition übernommen.
- Gerätetyp, Prüfgerät und Prüfprotokoll müssen über administrativ pflegbare Auswahllisten bzw. Vorlagen steuerbar sein.
- Fehlende Pflichtdaten werden vor der Protokollerstellung deutlich angezeigt; ein unvollständiges Protokoll darf nicht unbemerkt erzeugt werden.
- Das Laden eines alten Protokolls darf ein historisches Protokoll nicht überschreiben. Änderungen müssen als neue Revision bzw. neuer Prüfvorgang gespeichert werden.
- Erzeugte Protokolle werden dauerhaft mit Projekt, Auftrag, Verteilung, Schrankinstanz, Seriennummer, Ersteller, Erstellungsdatum und Vorlagenversion verknüpft.

## 5. Noch offen bis zu den weiteren Unterlagen

Nach Analyse der weiteren Masken und Dokumente werden insbesondere festgelegt:

- genaue Bedeutung und Datenquelle jedes Feldes,
- Auswahl- und Filterlogik für Projekt, Verteiler und Schrank,
- Regel zur automatischen Seriennummernvergabe,
- Liste der Gerätetypen,
- Liste und Verwaltung der Prüfgeräte,
- konkrete Prüfprotokollvorlagen,
- Pflichtfelder und Plausibilitätsprüfungen,
- PDF-/Druckaufbau,
- Unterschriften, Prüfer und Freigaben,
- Wiederholungsprüfung und Revision,
- Ablage im Fertigungsordner und im Projektdokumentenbereich,
- mögliche Kundenfreigabe im Portal.
