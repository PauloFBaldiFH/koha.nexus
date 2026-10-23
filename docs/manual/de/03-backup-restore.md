# 3. Backup und restore

[Inhalt](README.md)

## Zentrum, Kopien und Speicherorte

**Backup center**, Taste `b`, bündelt Datum, Größe, Ergebnis, **Compression** und Karten.

| Karte | Aufgabe |
| --- | --- |
| Download latest backup | Neueste gefundene Datei kopieren |
| Generate manual backup and download to PC | Datenbankkopie erstellen, prüfen, übertragen |
| Export MARC21 records now | Bibliografische Daten und Normdaten exportieren |
| Restore database | Aktuelle Datenbank ersetzen |
| Configure cloud backup | Externen Upload einrichten |
| Test integrity of latest backup | Temporären Import testen |

**Restore database ist eine Karte**, kein oberer Knopf und kein separater Hauptmenüpunkt. Ergebnis bezieht sich auf letzten Nachtlauf; Datum/Größe auf neueste Datei, möglicherweise aus anderem Lauf.

SQL enthält Koha-Datenbank, kein vollständiges Windows-/Debian-Abbild. MARC21 enthält bibliografische und Normdatensätze in `.tar.gz`, ersetzt SQL für Benutzer/Ausleihe nicht. Vor restore einer Datenbank mit Tabellen wird eine geprüfte Sicherheitskopie erstellt; eine leere Datenbank kann dies überspringen.

Standard: `/var/backups/koha_sql` für automatisches SQL/Sicherheitskopien, `/var/backups/koha_marc` für MARC. Manuelles Backup hat eigenes Ziel, standardmäßig `backups` im ermittelten Benutzerverzeichnis. `.part` bleibt vorläufig und wird erst nach Prüfung zur fertigen Datei.

## Komprimierung

**Compression**: gzip `.sql.gz` für Kompatibilität, Zstandard `.sql.zst` schnell/kleiner für große Kataloge, XZ/LZMA `.sql.xz` kleinste Datei/langsamer. Auswahl speichert sofort ohne weiteren Knopf, betrifft neue nächtliche/manuelle/Sicherheitskopien, komprimiert bestehende nicht neu.

Fehlt ein benötigtes Programm oder scheitert seine Installation, Meldung und tatsächliches Format beachten; gzip kann als Ersatz dienen. Restore erkennt unterstützte Formate unabhängig von der Auswahl. `.sql`, `.sql.gz`, `.sql.zst`, `.sql.xz` verwenden; Endung garantiert keinen gültigen Inhalt.

## Erstellen, herunterladen, prüfen

1. **Generate manual backup and download to PC** öffnen; Serverordner prüfen, beschreibbares Ziel wählen.
2. **Save backup**, Erzeugung und Prüfung abwarten; beim Speichern/Kopieren schließt das Fenster nicht.
3. Name/Größe/Pfad prüfen. WSL: **Save to Windows Downloads** oder **Choose folder in Windows**. Bei Fernzugriff angezeigten Übertragungsbefehl auf eigenem Rechner ausführen.
4. Empfangene Datei prüfen und **Finish and exit**.

Windows-Knöpfe nur unter WSL. Keine Befehle anderer Installationen kopieren: Server/Datei werden ermittelt. Bei aktivem Backup/restore warten; gemeinsame Sperre nicht durch konkurrierende externe Vorgänge umgehen.

**Download latest backup** lädt bestehende Datei, erzeugt keine neue. Desktop-Linux/WSL versucht Downloads; SSH kann lokalen Befehl zeigen. Fehlt Datei, manuelles Backup erstellen.

**Test integrity of latest backup**: Datei/Datum prüfen, **Choose another file** wechselt, bestätigen, temporären Import abwarten. Erfolg zeigt Tabellen-, Titel- und Benutzerzahlen, ohne Produktion zu ersetzen. Gilt für diese Datei in dieser Umgebung; dieselbe übertragene Kopie zugänglich aufbewahren.

## MARC und Cloud

**Export MARC21 records now** bestätigen, Paket mit Bibliografie/Normdaten abwarten, Pfad/Inhalt prüfen und angebotenen Download/Befehl nutzen. Koha läuft weiter; konfigurierter Cloud-Upload wird im Ergebnis gemeldet. SQL für vollständige Datenbankrettung behalten.

**Configure cloud backup** bietet zwei Google-Drive-Wege und andere Dienste einschließlich OneDrive, MEGA, S3. Autorisierung auf Server oder anderem Rechner passend wählen, ausschließlich angezeigte URL/Anweisungen nutzen. S3 unterscheidet Dienst, Region/Endpoint und Bucket. Tatsächlichen Uploadtest und Empfang prüfen; fehlerhafte Konfiguration ist keine verlässliche Kopie.

Private Autorisierungsdaten nur im eigenen System eingeben, nicht öffentlich dokumentieren, fotografieren oder an Support weitergeben. Dieses Handbuch nennt keine Speicherdateien dafür. Standardzeiten: SQL täglich 23:00, MARC Sonntag 03:00, Serverzeit; individuelle cron-Einstellungen gehen vor.

## Restore: destruktiv

**Bestätigung erlaubt das Ersetzen der aktuellen Datenbank.** Wartungsfenster und externe Kopie planen; dies ist Betriebsempfehlung, kein automatisch erledigter Zusatzschritt.

1. **Restore database**, serverseitig erreichbare Datei wählen, bei Bedarf Übertragungshinweis befolgen. WSL kann Windows-Datei zuerst lokal nach Linux kopieren.
2. Lesbarkeit, Inhalt, Integrität und Platz prüfen. Verdächtige/unvollständige Datei untersuchen, nicht nur Endung vertrauen.
3. Datei bei Ersetzungsbestätigung erneut kontrollieren. Bis dahin kann man zurück; danach nicht schließen, Ablauf ist nicht abbrechbar.

SQL wird zuerst temporär importiert und auf wesentliche Tabellen/Anzahl geprüft. Fehler stoppt vor Ersatz. Bei bestehenden Tabellen entsteht geprüfte Kopie mit `pre_restore_safety_backup_`, Datum/Zeit/Komprimierung im SQL-Ordner. Scheitert sie, darf bestehende Datenbank nicht gelöscht werden; leere kann die Kopie auslassen.

Danach Clients anhalten, Datenbank neu erstellen/importieren, Schema aktualisieren, Suche synchronisieren, Index aufbauen, Dienste starten. Gespeichertes Theme wird bei vorhandenem Zustand erneut anzuwenden versucht.

Fehler im temporären Test oder Sicherheitskopie bedeutet noch keinen Ersatz. Bei Neuerstellung/Import/Schema kann je nach Schritt/Kopie Rückholung versucht werden; **auch rollback kann scheitern**. Indexfehler können nach erfolgreichem Datenbank-restore auftreten, ohne dass der alte Katalog zurück ist.

Vollständige Meldung und `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, für Index `/var/log/koha-easy-install/zebra-rebuild.log` behalten. Zur Zentrumskarte zurück statt alter Menünummern; bei unklarem Zustand technische Hilfe. Abschließend Dashboard, Datensätze und Suche in OPAC/staff prüfen. SQL-Abschluss beweist keine Wiederherstellung externer Dateien.

## Geprüfte Quellen

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
