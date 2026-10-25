# 5. Anreicherung und Z39.50/SRU

[Inhalt](README.md)

## Vorhandene Datensätze anreichern

Import übernimmt Exportdaten; Anreicherung sucht Ergänzungen oder ein neues Buch. Titelübereinstimmung ersetzt keine bibliografische Prüfung. **Library tools > Enrich from world catalogues**, Taste `n`; alte bibliografische Stapeloberfläche ist nicht mehr der aktuelle Menüweg.

`all` oder `biblionumbers` wie `101, 102, 500-510`, dann **Search**. Auftrag/Server verfolgen; große Aufträge arbeiten im Hintergrund und können nach Neustart fortsetzen, benötigen verfügbaren Rechner. **Pause/Resume** pausiert Suche, macht keine Änderungen rückgängig. Bericht öffnen, Sacherschließung, Klassifikation, Anmerkungen und physische Beschreibung vergleichen. **Search more servers** fragt bisher ungenutzte Quellen, **Choose donor** wählt Spender für Feldgruppen vorhandener Ergebnisse. **Apply** erst nach Prüfung/Bestätigung; Suche und Bericht schreiben noch nichts.

Aktuell direkte Z39.50-Suche. Serverlimits/Ausfälle können verzögern; kein Treffer beweist keine Abwesenheit. Keine allgemeine 50-Datensatz-Grenze: Schwelle betrifft Schutz beim Anwenden, Datensatzkopien für klein, geprüftes vollständiges Backup für groß. Prüfung bleibt Pflicht.

**Revert** stellt alte Versionen gemäß Schutzregeln her, erhält nach Anwendung bearbeitete Datensätze. Kein globaler restore und kein Rückgängigmachen aller Fremdbearbeitungen.

## Neues Buch und Normdaten

ISBN/Titel, ergänzend Autor/Jahr, **Find**, Quellen prüfen und auswählen. **Import as new record** fügt nach Bestätigung hinzu, ersetzt keinen gleichen ISBN-Titel. Lokale `9XX` des Spenders werden entfernt, Herkunft festgehalten, damit fremde Exemplare nicht eigene werden. Titel prüfen und lokale Exemplare regulär anlegen; passende MARC-Charge über **Undo a MARC import** behandeln.

**Enrich & standardize authorities**, `h`: Umfang und exakte/ähnliche Formen wählen. Ähnliche können Schreibkorrektur/vorläufige Normdaten vorschlagen, besonders prüfen. Erst eigene Normdaten, dann Anreicherungsbasis/direkte Server; brasilianische Quellen bevorzugt, Sachbegriffe nur daraus. Keine Garantie für lokale Erschließungspolitik.

Bericht vor **Apply** lesen; erstellt nötige Normdaten/Links mit Sicherheitsbackup, hält seit Bericht bearbeitete Titel unverändert. Revert löscht neu erzeugte Normdaten nicht, solange Links bestehen.

## Server

**Z39.50 / SRU servers**, `z`: Eingangsserver lässt andere Bibliotheken suchen und ändert seinen Firewall-Port beim Umschalten. Gemeinschaftsnetz ist eine andere Quelle als direkte Anreicherungsserver. Gesundheitsanzeige mit **Reset/Reset all** ermöglicht erneuten Versuch, repariert keinen entfernten Dienst.

Zum Kopieren per Leertaste markieren, **Scan** mit echter Datensatzsuche, **Add to Koha** für gewählte funktionierende Quellen. SRU-Konfiguration bedeutet nicht SRU für jede Anreicherungsabfrage. Externe Suche verlangt keine Öffnung des Eingangsservers.

**Noch zu bestätigen:** Verfügbarkeit, Abdeckung, Zugang jeder Quelle im jeweiligen Bibliotheksnetz und Nutzungszeitpunkt.

## Geprüfte Quellen

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
