# SAB-P Suite – Protokolle erstellen

> Sammelstand. Weitere Masken, Dokumente und Feldzuordnungen folgen noch und werden anschließend ergänzt.

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

## 3. Vorläufige fachliche Regeln

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

## 4. Noch offen bis zu den weiteren Unterlagen

Nach Eingang der restlichen Masken und Dokumente werden insbesondere festgelegt:

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
