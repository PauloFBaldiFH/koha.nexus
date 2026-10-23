# 6. Darstellung von OPAC und staff

[Inhalt](README.md)

**OPAC and Staff Appearance**, `o`, hat getrennte Einstellungen für Öffentlichkeit und staff/Intranet.

## Geprüft anwenden

**Sync current OPAC settings** liest Livewerte, wendet noch nichts an. Eine Gruppe nach der anderen bearbeiten. **Preview** zeigt CSS/JavaScript/Inhalt, keine vollständige Browseransicht. **Apply** mit Zusammenfassung/Bestätigung erstellt vorher Datenbankbackup. Anschließend Start-, Such-, Titel- und Anmeldeseiten auch auf kleinem Bildschirm prüfen.

Blöcke gehen nach `OpacUserCSS/OpacUserJS` und gegebenenfalls `IntranetUserCSS/IntranetUserJS`. Eigene Blöcke bleiben, visuelle Konflikte mit anderen Anpassungen sind trotzdem möglich.

## Darstellung und Bilder

Textur, Unschärfe, Deckkraft, Rundungen, Akzent-/Hintergrundfarben; Hell/Dunkel und Startthema getrennt. Genügend Kontrast trotz Bild/Transparenz. Staff hat obere Leiste, Schnellsuche, Modulkarten, Tabellendichte, Textgröße/Kontrast. **Apply color theme to Staff Client** aktivieren. **Copy OPAC preset** füllt nur Felder; **Apply** speichert.

Serverdatei, angebotener Bilderdienst oder direkte HTTPS-URL. PNG/JPEG/GIF/WebP/ICO erlaubt, SVG abgewiesen. Nur auf Benutzerrechner vorhandene Datei muss erst serverseitig erreichbar sein. Nutzungsrechte und Alternativbeschreibung für Login beachten; Hostingseite ist nicht immer direkte Bildadresse. Externe Dienste konfigurieren, keine privaten Informationen veröffentlichen.

## Karussell und Inhalte

Neuheiten oder Koha-Liste; deren Nummer aus `shelfnumber=` eingeben. Titel, Anzahl, Stil, Geschwindigkeit, Autoplay und **Refresh carousel** nutzen. Fehlendes Cover bedeutet keinen gelöschten Titel; Verfügbarkeit von Datensätzen/Covern und Netzwerk zu externen Diensten zählt.

OPAC-/staff-Knöpfe getrennt, mit Text/Adresse/Ziel/Reihenfolge. **Add a button** ergänzt, Zeilenknopf entfernt vor Anwendung. Login erlaubt Bild/Beschreibung/HTML, filtert Skripte, Stile und Ereignisse. Keine internen Geheimhinweise. OPAC/staff-Nachrichten haben eigene Titel/Texte/Knöpfe; panelverwaltete Einträge ersetzen keine vorhandenen Bibliotheksnachrichten.

Fußzeile als `Field: value` nach angezeigten Feldern; Zusatzlinks Text `|` Adresse, maximal sechs. Nur öffentliche Angaben.

**Remove** bestätigt und sichert vor Entfernen der Themeblöcke, um Koha-Darstellung mit eigenen Anpassungen zurückzubringen. Kein gesamter restore oder Rücknahme anderer Administration. Fehlerhafte Gruppe korrigieren und anwenden; Fehlermeldung zur Diagnose behalten.

## Geprüfte Quellen

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
