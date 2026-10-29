# SAB-P Suite V1 – praktischer Testablauf

Ziel: In kurzer Zeit feststellen, ob der aktuelle Entwicklungsstand praktisch testfähig ist. Nicht als fachliche Endabnahme verwenden.

## 1. Build und Anmeldung

1. Odoo.sh Branch `agent/leitfaden-gesamtstand` öffnen.
2. Prüfen, dass der neueste Build grün ist.
3. Als Projektleiter/Administrator anmelden.
4. Unter SAB-P Suite prüfen, dass Projekte, Mitarbeiterverwaltung, Fertigung und Kundenportal-Menüs erreichbar sind.

## 2. Mitarbeiter anlegen

1. Einstellungen → Mitarbeiterverwaltung öffnen.
2. Einen Testmitarbeiter anlegen: Name, Login, E-Mail.
3. Arbeitsbereiche zuweisen, z. B. Mechanischer Aufbau und Mechanische Fertigung.
4. `Mitarbeiter-App` aktivieren.
5. `Zugang anlegen / aktualisieren` ausführen.
6. Optional `Einladung / Passwortlink senden` ausführen.
7. Kontrollieren, dass der Odoo-Benutzer verknüpft und aktiv ist.

Negativtest: Ein normaler interner Benutzer ohne Rolle `SAB-P Mitarbeiter` darf die Mitarbeiter-App/Fertigungsdaten nicht nutzen.

## 3. Projekt und Angebot

1. Neues Projekt anlegen.
2. Prüfen, dass sofort eine Projektnummer im Format `A26.xxxx` vergeben wird.
3. In der Projektübersicht prüfen, dass die Projektnummer als erste Spalte sichtbar ist.
4. Aus dem Projekt ein Angebot anlegen.
5. Prüfen, dass das erste Angebot `A26.xxxx-01` erhält.
6. Zweites Angebot/Revision anlegen und `-02` prüfen.

## 4. Kalkulation und Stückliste

1. Einen vorhandenen Kalkulationsartikel ins Angebot übernehmen.
2. Material, Zeiten und kalkulatorische Werte prüfen.
3. Angebot/Auftrag bestätigen.
4. Stückliste erzeugen und freigeben.
5. Prüfen, dass spätere Stammdatenänderungen den gespeicherten Angebotsstand nicht rückwirkend verändern.

## 5. Einkauf und Lager

1. Einkaufsbedarf aus der freigegebenen Stückliste erzeugen.
2. Bestellung/Wareneingang simulieren.
3. Prüfen, dass der Lagerbestand genau einmal erhöht wird.
4. Reservierung und Materialentnahme für das Projekt durchführen.
5. Prüfen, dass reservierter Bestand nicht doppelt entnommen werden kann.

## 6. Fertigung und Mitarbeiter-App

1. Fertigungsauftrag aus der freigegebenen Stückliste erstellen.
2. Prüfen, dass die Standard-Fertigungsschritte Arbeitsbereiche besitzen.
3. Einen Schritt `Mechanischer Aufbau` dem Testmitarbeiter zuweisen.
4. Prüfen, dass ein Mitarbeiter ohne passenden Arbeitsbereich nicht auswählbar bzw. serverseitig abgewiesen wird.
5. Als Testmitarbeiter anmelden.
6. `Mitarbeiter → Meine Arbeit` und `Freie Arbeit` öffnen.
7. Arbeit übernehmen, starten, pausieren, fortsetzen und fertigmelden.
8. Zeit erfassen.
9. Foto/Rückmeldung erfassen.
10. Materialbedarf melden.
11. Prüfen, dass der Mitarbeiter keine Arbeit eines anderen Mitarbeiters öffnen kann.

## 7. Dokumente und Kundenportal

1. Projektdokument hochladen und intern freigeben.
2. Mit Rolle `SAB-P Kundenfreigaben` Dokument für Portal freigeben.
3. Fertigungsfoto intern bearbeiten und anschließend für Kunden freigeben.
4. Kundenstatus setzen und explizit freigeben.
5. Testkunde A im Portal anmelden und Projekt, Status, Dokument und Foto prüfen.
6. Testkunde B anmelden und sicherstellen, dass keinerlei Daten von Kunde A sichtbar/abrufbar sind.

## 8. Nachkalkulation

1. Nachkalkulation des Testprojekts öffnen.
2. Prüfen, dass bestätigte Ist-Zeiten enthalten sind.
3. Materialentnahmen und historische Materialwerte prüfen.
4. Ist-Lohnkosten und Deckungsbeitrag plausibilisieren.

## 9. Abbruchkriterien

Test sofort stoppen und Fehler dokumentieren, wenn:
- Odoo.sh Build rot ist,
- Modulinstallation/Upgrade fehlschlägt,
- Projektnummer fehlt oder doppelt ist,
- fremde Mitarbeiter- oder Kundendaten sichtbar sind,
- Lagerbewegungen doppelt gebucht werden,
- freigegebene historische Kalkulations-/Dokumentstände nachträglich verändert werden können.

## 10. Noch keine Blocker für den ersten Funktionstest

Folgende Punkte dürfen nach dem ersten Funktionstest fachlich verfeinert werden, solange die Grundfunktion funktioniert:
- endgültige Kalkulationsfaktoren,
- reale Lageranfangsbestände,
- vollständiges ABB-DATANORM-Sonderfallpaket,
- endgültige Management-Grenzwerte,
- endgültige Pflichtdokumente je Projektstatus.
