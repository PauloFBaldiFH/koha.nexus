# 2. Erste Schritte und Bedienoberfläche

[Inhalt](README.md)

## Öffnen und bedienen

Auf vorbereitetem Debian/Ubuntu:

```bash
sudo config.sh
```

Unter Windows das **Koha**-Symbol oder die MSIX-Anwendung öffnen. Der Erststart kann die Sprache abfragen. Scheitert Textual-Vorbereitung, kann die klassische Oberfläche erscheinen. Dieses Handbuch beschreibt vorwiegend Textual, nicht alte Menünummern.

Seitenleiste mit Pfeilen markieren, mit **Enter** öffnen oder klicken. Markieren allein führt nichts aus. Aufgabenkarte öffnen und Rückfragen lesen. **Tab** wechselt den Fokus; vor Buchstabenkürzeln ein Eingabefeld verlassen.

| Taste | Aktion |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Debian-Terminal |
| `Ctrl+B` | Seitenleiste ein-/ausblenden |
| `q` | Panel verlassen |

Verlassen im Leerlauf ist kein Herunterfahren. Bei laufenden Aufgaben gilt deren Abbruchhinweis. Installation und restore enthalten nicht abbrechbare Schritte; gewaltsames Schließen ist nicht sicher.

## Status verstehen

Dashboard zeigt Koha-Gesamtzustand und verfügbaren RAM, letztes Backup mit Datum/Alter/Datei, freien Speicher, Zugriffsadressen und MariaDB, Apache, RabbitMQ, Memcached sowie Koha mit HTTP-Prüfungen.

Backupanzeige berücksichtigt Dateialter und letzten nächtlichen Lauf. Neue Datei und fehlgeschlagener Nachtlauf können zusammen auftreten. Beides lesen; grüne Anzeige ersetzt keinen restore-Test. HTTP-Antwort beweist weder abgeschlossenen Koha-Webinstaller noch sämtliche Bibliotheksfunktionen.

**Refresh** liest neu. **Restart Koha** fordert Dienstreparatur/Neustart an; aktuelle Nutzer berücksichtigen. **Export diagnostics** erstellt Supportinformationen. Funktionen können deaktiviert sein, wenn der installierte Installer die Aufgabe nicht unterstützt.

## Adressen und erste Nutzung

Adresskarten öffnen/kopieren URL; ohne Browserstart die kopierte Adresse im eigenen Browser öffnen. Lokal auf dem Server: OPAC `http://localhost/`, staff `http://localhost:8080/`, Ports 80/8080. Auf anderen Rechnern die Netzwerkadresse nutzen, nicht deren eigenes `localhost`. Meldet WSL-NAT keine LAN-Erreichbarkeit, Windows-Netzvorbereitung mit der verantwortlichen Person prüfen; kein Zugriff von jedem Rechner voraussetzen.

Zeigt staff den Koha-Webinstaller, zuerst abschließen. Versionsabhängige Bildschirme sind möglich. **Create super librarian** unter **Koha settings & parameters** erstellt anschließend ein Konto; private Werte nur dort eingeben.

Vor Betrieb: Dashboard aktualisieren, Komponenten/Adressen prüfen, OPAC/staff passend öffnen, Backup erzeugen/testen, externe Kopie und Wiederherstellungszuständigkeit prüfen. Letzteres ist betriebliche Empfehlung: Erst fertig übertragene und geprüfte Datei ist eine nutzbare externe Kopie.

## Geprüfte Quellen

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
