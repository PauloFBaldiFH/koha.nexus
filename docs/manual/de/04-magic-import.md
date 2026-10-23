# 4. Magischer Import

[Inhalt](README.md)

## Eingabe vorbereiten

Magic Import liest bibliografische Daten, Exemplare, Benutzer und Normdaten. Erkanntes Format garantiert keine korrekte Zuordnung aller Felder, insbesondere ohne Überschriften und bei lokalen Feldern. Original und geprüftes Backup behalten, repräsentative Stichprobe mit mehreren Exemplaren, Umlauten, leeren Werten und Ausnahmen prüfen; Quell- und Vorschauzahlen vergleichen. Benutzerexporte nicht veröffentlichen.

**Magic Import Tool**, `i`, dann Karte öffnen. Datei/Ordner muss für das Linux des Panels erreichbar sein; nur auf dem Browser-/Fernterminalrechner vorhanden bedeutet nicht auf dem Server.

| Eingabe | Prüfung |
| --- | --- |
| MARC21 ISO 2709, MARCXML, MARC-Text | Titel, Zeichen, Normdaten, Exemplare. MarcEdit `.mrk` wird erkannt, keine Konvertierung allein wegen Endung nötig. |
| CSV/TSV, `.xlsx`, `.xls`, `.ods`, `.dbf` | Trennzeichen, Überschriften, Werte und Ziele; Inhalt und vorhandene Überschriften dienen der Erkennung. |
| Tabellarisches JSON/XML | Struktur prüfen; beliebiges XML ist nicht automatisch MARCXML. |
| Tabellarisches SQL ohne Überschriften möglich | Erkannte Daten/Beziehungen werden gelesen, nicht als Migrationsprogramm ausgeführt; Mehrdeutigkeiten prüfen. |
| ISIS | Erkannter PostgreSQL-Export mit `acervo`; CDS/ISIS `.mst` aus WinISIS als ISO 2709 exportieren. |
| Biblioteca Fácil | Erkanntes Backup/Datenverzeichnis mit zusammengehörigen Tabellen; Titel, Benutzer, Ausleihen, Vormerkungen getrennt prüfen. |
| Vollständiges Koha-Backup | Weiterleitung zu restore statt Ergänzen von Datensätzen. |

Fremder PostgreSQL-Dump, besonders binäres `pg_dump`, ist keine fertige MariaDB-Basis. Bei Ablehnung MARC/Tabellen im Quellsystem exportieren. Archivmitglieder einzeln prüfen. PDF, Bilder, Dokumente, Programme sind keine lesbaren bibliografischen Exporte dieses Lesers.

## Integrierte manuelle Zuordnung

**Bibliographic/Patrons/Authorities** prüfen und falschen Modus korrigieren. Raster und Ziele untersuchen, Trenner oder **Ctrl+Up/Down** ändern Höhe. Erhalten, Umleiten, Festtext oder Ignorieren wählen; Bezüge vor Entfernen eines Identifikators verstehen.

**Values of this Koha** zeigt verfügbare Codes, Standardbibliothek/-typ/-kategorie und Quelle/Ziel-Ersetzungen. **Record preview** zeigt Ergebnis, **Check the whole file** prüft gesamte Vorbereitung ohne Koha-Import. Profil benennen/**Save**, auswählen/**Use**, bei Strukturänderung neu prüfen. **Apply/Ctrl+S** akzeptiert Mapping, nicht endgültiges Schreiben. **Skip: import as it is** bzw. **Esc** überspringt Mapping, bricht nicht alles ab.

Gruppierung und Textkorrektur erst nach Vorschau; keine blinde Änderung von Kürzeln, Eigennamen und Codes.

## Exemplare, Benutzer und Normdaten

Native `952` bleiben erhalten, Bibliothek/Typ können angefordert umcodiert werden. Gültigen abweichenden Code nicht nur wegen Standard ersetzen. Barcode, Heimat-/aktuelle Bibliothek, Signatur, Typ, Standort, Zugang prüfen. Lokale `949/852/950/990` sind bei Pergamum/Biblivre nicht zwangsläufig gleich belegt.

Pflichtexemplarvermerk `DL` mit Datum erzeugt nicht automatisch lokales Exemplar. Ausschlüsse und unabhängige Inventarbelege prüfen. Fehlender Barcode fordert standardmäßig Überprüfung; Erzeugung braucht ausdrückliche Wahl und stabile Migrations-/Quellidentität, ohne stille Kollisionsumbenennung. SQL-Beziehungen müssen erkannt sein, nicht aus Spaltenposition/Zeilenfolge angenommen werden. Unklare Verknüpfung vor Import korrigieren.

**Patrons**: Vorname, Nachname, Ausweis, Kontakt, Adresse, Daten, Bibliothek/existierende Kategorie prüfen. E-Mail, CPF und Datumsform sind Indizien; Geburt/Anmeldung/Ablauf können ähnlich sein. Aktualisierung bestehender Benutzer wird per Ausweiszuordnung abgefragt und unterscheidet sich von ausschließlich neuen. Rechte/Authentifizierung nicht anhand vermuteter Spaltenbedeutung vergeben.

**Authorities**: Identifikator, bevorzugte Form, Varianten, Beziehungen, Typ prüfen. Moduswechsel erfindet keine fehlenden Informationen.

## Bestätigen und prüfen

Zahlen, Abweisungen, Rückfragen lesen. Bestehende Titel behalten und nur neue Exemplare ergänzen, mit Eingang ersetzen oder ohne Vergleich neue Titel erstellen: passend wählen, keine versehentliche Wiederholung.

**Später Fehler kann frühere Importe bestehen lassen.** Zusammenfassung/Logs behalten und abgeschlossene Schritte vor Wiederholung prüfen. Stichproben, Exemplare, Benutzer und Normdatenlinks in Koha kontrollieren. **Library tools > Undo a MARC import** behandelt MARC-Chargen, nicht universell Benutzer/Ausleihe/Vormerkungen. Gesamte Datenbank nur mit Backup-center-Vorsicht retten.

**Noch zu bestätigen:** proprietäres Layout oder konkrete Exportversion ohne Stichprobe und Ergebnisprüfung.

## Geprüfte Quellen

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
