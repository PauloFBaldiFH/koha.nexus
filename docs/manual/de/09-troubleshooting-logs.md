# 9. Fehlersuche und Protokolle

[Inhalt](README.md)

Aktion, Uhrzeit, vollständige Meldung und noch funktionierende Bereiche notieren. Erreichbare Seite, laufender Dienst und erfolgreiche Suche sind verschieden. Nicht jeden Fehler zuerst mit Neuinstallation/restore behandeln.

## Diagnoseweg

**Control Dashboard** aktualisieren. **Diagnostics & maintenance center > Detailed server & Koha status**, dann **Full system health check** und Bericht lesen. **View latest validation report** öffnet erneut; **Export diagnostics** im Dashboard liefert Supportpfad. Trotz Schwärzung vertrauliche Benutzer-/Datei-/Netzadressen vor Weitergabe prüfen, nicht ganze Installation kopieren. Klassischer Rückfall bei Textual-Fehler setzt keine vorherige Operation zurück; Meldung/Log behalten.

| Ort | Inhalt |
| --- | --- |
| `/var/log/koha-easy-install/` | Hauptverzeichnis Linux |
| `apt.log` | Pakete und zugehörige Schritte |
| `validacao-*.log` | Datierte Prüfberichte |
| `new-panel.log` | Textual-Fehler/Traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/Export |
| `restore.log`, `restore-import.log` | Restore/SQL-Import |
| `zebra-rebuild.log`, `search-engine.log` | Suche/Index |
| `/var/log/koha-easy-install/tools/` | Werkzeuge |
| `C:\Koha\logs`, früher `C:\KohaEasy\logs` | Windows je Installation |

`*` bezeichnet datierte Dateien; vor erster Ausführung können sie fehlen. Genauen gemeldeten Pfad bevorzugen. **Library tools > View tool logs** nach Datum/Aufgabe wählen; eingeschränkt wegen möglicher Personendaten.

Bericht enthält Kontext, Datum, Version, OK/Warnung/Fehler/Info. Jede Meldung lesen, nicht nur Summe. **No critical failures** kann Warnungen enthalten; altes Backup verlangt andere Reaktion als Datenbankfehler. Nach Reparatur neu prüfen/vergleichen.

**Real-time Apache log auditing**: staff/OPAC und alter Alternativpfad bei Bedarf. Textual **Pause/p** pausiert Anzeige, nicht Apache; **Continue** weiter, **Back/Esc** zurück. Klassisch `Ctrl+C` für dieses Protokollverfolgen, nicht pauschal jede Aufgabe. Zeit und Kontext bei `error/fatal/denied/fail` lesen; Farbe beweist keine Ursache.

## Nach Symptom

- OPAC/staff nicht erreichbar: Apache/MariaDB/Plack/Cache und lokale/Netz-/VPN-/Tunneladresse. `localhost` ist Browserrechner. **Restart / repair Koha services (Memcached, Plack)** kann unterbrechen; Ergebnis lesen, neu validieren.
- Titel fehlt in Suche: Motor, Warteschlange, Index/Datenbank. **Search engine & indexing > Repair / rebuild indexing** mit Fragen prüfen/abwarten; Elasticsearch-Wechsel ist kein zwingender erster Schritt.
- Backup fehlt: Zeit/Ergebnis/Platz, Rechner/Linux beim cron aktiv? `.part` ist unfertig. `backup_sql.log`, Integritätstest oder manuell; letzte gültige Kopie nicht ohne sichere andere löschen, Konkurrenz vermeiden.
- Importfehler/Zahlen: Magic-Import-/MARC-Logs, Eingabe/Vorbereitung/Schreiben, Modus/Codes/Barcodes/Abweisungen/Dubletten. Vorschau beweist nicht ganze Datei; vollständig prüfen und abgeschlossene Schritte vor Wiederholung feststellen.
- Restorefehler: Schritt ermitteln. Indexfehler kann nach Datenbank-restore entstehen, rollback ebenso scheitern; Datenbank/Suche/Validierung prüfen.
- KI/Anreicherung langsam: Ollama, gespeicherte Wahl, Speicher oder Auftrag/Server/Limits; große Aufgaben nicht wegen Verzögerung verdoppeln. Remoteausfall und lokale RAM-Knappheit verschieden untersuchen.

## Windows-Symbol

PowerShell des angemeldeten Benutzers, **ohne Administrator**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Kann Verknüpfungen neu erstellen und Tray neu starten, also nicht rein lesend. Speichert `diagnose-<date>.txt` im ermittelten `logs`; Pfad/Fehler behalten. Anders als administrative Erstinstallation.

**Deep database optimization & log cleanup** wartet und startet Dienste, kann nützliche Historie löschen. Diagnosen vorher sichern, Wartung planen, Fehler nicht verdecken. Für Hilfe Version, Windows/WSL oder Distribution, Aktion/Zeit/vollständige Meldung, OPAC/staff/Suche und vorherige Operation nennen; Auszüge datenschutzgerecht prüfen.

**Noch zu bestätigen:** Ursache ohne vollständige Meldung und Log; nicht automatisch Netzwerk/Installation beschuldigen.

## Geprüfte Quellen

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
