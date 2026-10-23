# 7. Lokale KI

[Inhalt](README.md)

**AI**, `a`, bündelt Anbieter, Ollama und Foto-Katalogisierung in MARC Replace sowie staff-Assistent. Anbieterkonfiguration installiert Werkzeuge nicht automatisch.

## Lokal einrichten

Leistungshinweis lesen: CPU/RAM-Verbrauch kann Koha stark verlangsamen. **Ollama on this server > Check Ollama**, nötigenfalls **Install Ollama**. Listeneintrag wählen und **Download**; benötigt Netz/Platz. Keine festen Modellnamen, da Auswahl/Verfügbarkeit wechseln.

**Local Ollama** wählen, URL prüfen (Standard `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Fotos benötigen Bildverarbeitung; reiner Text genügt nicht. **Test connection/Save** oder **F5/Ctrl+S**; ein Feld setzen speichert noch nicht. Leerer Chat nutzt Bildauswahl. **Load models** fragt Anbieter; eingebaute Ersatzliste wird als solche gemeldet.

Installiert belegt Platte, geladen RAM. **Free memory** entlädt ohne Downloads zu löschen; bei Anfrage wieder ladbar. Ollama-Box bleibt bei anderem Anbieter sichtbar: gespeicherte URL/Anbieter prüfen statt lokale Verarbeitung allein aus Installation abzuleiten.

## MARC Replace und Bilder

Seite installieren/aktualisieren und öffnen; Installer prüft Kompilierung und staff-Verknüpfungen. Ein Titel je Vorgang: `.mrc/.xml` oder Text, `biblionumber` der Ersetzung, **Preview**, vergleichen, bestätigen. Leer erzeugt neuen Titel: Duplikate vermeiden. Vorhandene Exemplare bleiben, eingehende Exemplarfelder entfallen. Vorversion als MARCXML herunterladbar; erneut an gleiche Nummer senden zur Rücknahme, kein Ersatz für vollständiges Backup.

**AI cataloguing**: lesbare Fotos von Umschlag, Titelseite und Rückseite, soweit vorhanden; JPEG/PNG/WebP, mindestens eines. Framework oder Ersetzungsziel wählen, **Read the photos**, Entwurf mit Bildern vergleichen: Titel, Verantwortung, Veröffentlichung, ISBN, Klassifikation, Fehlendes. MARC vor Schreiben korrigieren. KI-Klassifikation anhand lokaler Tabellen prüfen; ISBN-Prüfziffer beweist keine passende Ausgabe. Entwurf speichert keine Exemplarfelder.

## Assistent

**Install, update or remove the assistant** ersetzt Nachrichtenblock auf staff-Startseite, ohne OPAC zu ändern. Koha-Suche und festgelegte Leseabfragen statt frei generiertem SQL; Links und Aktionsvorschläge möglich.

**Vorschlag ist noch keine ausgeführte Änderung.** Datensatz, Vorher/Nachher und Wirkung prüfen; **Approve & Execute** unter eigenen Rechten nötig. Zwischenzeitliche Änderung kann Ablehnung/Neuanfrage auslösen. Bestätigte Änderungen lassen sich einsehen; Unterhaltung löschen/Assistent entfernen macht sie nicht rückgängig. Entfernung löscht Gespräche, behält bestätigte Änderungshistorie.

Hardware/Koha beobachten; bei Langsamkeit keine weiteren Fotos starten, gegebenenfalls Speicher freigeben. Keine allgemeine Antwortzeitgarantie. Remoteanbieter erhält Anfragedaten: Datenschutz-/Bildrichtlinie prüfen, nicht mit echten Benutzerdaten testen. Kostenmarkierungen garantieren keine kostenlose Nutzung.

**Noch zu bestätigen:** RAM, Platte, Antwortzeiten je Auswahl/Hardware; Koha-Mindestwerte garantieren keine KI-Leistung.

## Geprüfte Quellen

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
