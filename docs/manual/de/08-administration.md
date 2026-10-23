# 8. Verwaltung, Nachrichten und VPN

[Inhalt](README.md)

Vor Administration Zustand und aktuelles Backup prüfen. Einrichtung beweist keine Funktion im Bibliotheksnetz; anschließend testen.

## Zeitpläne

**Schedules & cron tasks**, `s`: Aktivierung, Häufigkeit, Uhrzeit und je nach Rhythmus Tag/eigener Ausdruck. **Reload**, nur Benötigtes einschalten, `HH:MM`, **Preview**, **Save** mit Bestätigung, erneut laden. Verwaltet `/etc/cron.d/koha_tasks`, vorherige Version `koha_tasks.bak`. Ausgeschaltete Aufgaben bleiben auskommentiert mit Zeit; eigene Zeilen bleiben erhalten. **Defaults** füllt, benötigt Speichern.

Standard SQL täglich 23:00, MARC Sonntag 03:00; Zeitzone/eigene Einstellungen prüfen. Rechner/Linux müssen laufen, cron schaltet Windows nicht zugesichert ein. Koha-Mitteilungen nutzen eigenen Mechanismus.

## VPN

**Security & access hub > WireGuard VPN**, `v`: öffentliche Adresse/Name und UDP-Port. **Set up the VPN** zeigt Netzänderungen; Router muss UDP zum Server weiterleiten. Jedes Gerät benennen, **Add device**, **QR code & profile** für WireGuard; Verbindung/staff/Verkehr prüfen.

Profil/QR nicht veröffentlichen. **Revoke** sperrt Profil, neues zur Rückkehr nötig. **Turn off** trennt, behält Profile. Geteilter Tunnel nur `10.66.0.0/24`, Internet/DNS bleiben beim Gerät; staff unter `http://10.66.0.1:8080`. WSL ohne mirrored networking wird nicht direkt erreichbar gemeldet, diese VPN bleibt aus.

## Nachrichten und Schnittstellen

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. E-Mail aktivieren, Standard-SMTP prüfen. Knöpfe öffnen SMTP, Bibliotheksadresse, Mitteilungen/Belege, Überfälligkeitsregeln. Aktivierung füllt nicht alle Regeln/Empfänger/Vorlagen; Anbieteranmeldung nur privat konfigurieren.

**Set up WhatsApp and Telegram** richtet Dienst, Landes-/Ortsvorwahl, Tests, Aktivierung und Telefonprüfung ein. WhatsApp braucht Gateway, Telegram Bot/Empfänger. Vor Produktion an berechtigten Empfänger testen; Formate/Vorlagen vor Massenkorrektur prüfen. SMS führt zu `SMSSendDriver` und Benutzerpräferenzen; kompatibler Dienst/Treiber nötig, Name allein reicht nicht.

**Alerts**: Fälligkeits-/Überfälligkeitshinweise, Wiederholung, Tagesübersicht mit Kanälen; speichern und **Dry run (sends nothing)** simulieren. Aktiviert entsprechende cron-Aufgabe: prüfen. Doppelsendungen mit Koha-Hinweisen vermeiden. SIP2: Port/Netz/Bibliothek/Geräterechte, Beispiele entfernen, nötiges Konto über Knopf anlegen; Gerät/Server müssen passen. Nicht alle Netze für lokalen Test öffnen. Z39.50 führt zu Kapitel 5; Ein-/Ausgang unterscheiden.

## Sicherheit und weitere Verwaltung

Hub enthält Cloudflare Tunnel, UFW, staff-Port 8080, HTTPS, Fail2ban. Zustand/Vorschau lesen, unterschiedliche Reichweite von VPN/Tunnel/direktem Zugriff beachten. Remote-Firewall nicht ohne verbleibenden Administrationsweg ändern. **Noch zu bestätigen:** Domain-, Router-, Provider- und Institutionsvorgaben; Code liefert kein universelles Veröffentlichungsrezept.

**Koha settings & parameters**: Speicher/Worker, Superbibliothekar, Zeitzone; breite Rechte begrenzen. **Koha languages** unterscheidet Download/Aktivierung, nur Download, installierte aktivieren und Auflisten. Ergebnis in Panel/OPAC/staff prüfen.

**Update center** trennt Systempakete/Schema vom GitHub-Panelupdate. Backup/Wartungsfenster; Panelupdate kann Sitzung zum Neuladen beenden. Scheitert Schemamigration, beweist Neustart keine Reparatur.

**Library tools** bietet Normdatenlinks/-abgleich, Dubletten, SQL-Berichte, Kategorien, Qualität, Datenschutz. Unterschiedliche Quell-/Zielkategorie, Auswahlregel/Bibliothek und Simulation vor gesicherter Bestätigung. Qualitätsprüfung liest, repariert nicht alles. Anonymisierung entfernt alte Historienbezüge zu Benutzern nach Koha-Regeln, nicht ganze Bibliografie. Benutzerlöschung verlangt Filter, Simulation, Zahlenbestätigung: destruktiv, Aufbewahrung prüfen. Ähnliche Namen beweisen keine identische Person. Verborgene Katalogisierungskarten gelten nicht als verfügbar.

## Geprüfte Quellen

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
