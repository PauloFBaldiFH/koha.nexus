# 3. Backup en restore

[Inhoud](README.md)

## Centrum, soorten en locaties

**Backup center**, `b`, toont laatste backup, omvang, resultaat, **Compression** en kaarten.

| Kaart | Doel |
| --- | --- |
| Download latest backup | Nieuwste gevonden bestand kopiëren |
| Generate manual backup and download to PC | Databasekopie maken, controleren, overdragen |
| Export MARC21 records now | Bibliografische en autoriteitsrecords exporteren |
| Restore database | Huidige database vervangen |
| Configure cloud backup | Externe upload instellen |
| Test integrity of latest backup | Tijdelijke import testen |

**Restore database is een kaart**, geen bovenste knop of los hoofdmenu-item. Resultaat beschrijft laatste nachtloop; datum/omvang nieuwste bestand, mogelijk andere uitvoering.

SQL bevat Koha-database, geen volledige Windows-/Debian-image of alle bestanden. MARC21 bevat bibliografie/autoriteiten in `.tar.gz`, vervangt SQL niet voor leners/uitleningen. Voor restore van database met tabellen wordt geldige veiligheidskopie gemaakt; leeg kan die overslaan.

Standaard `/var/backups/koha_sql` voor automatisch SQL/veiligheid, `/var/backups/koha_marc` voor MARC. Handmatige backup heeft eigen doel, standaard `backups` onder gedetecteerde persoonlijke map. `.part` is tijdelijk en wordt pas na controles definitief.

## Compressie

**Compression**: gzip `.sql.gz` breed leesbaar; Zstandard `.sql.zst` snel/kleiner, grote catalogi; XZ/LZMA `.sql.xz` kleinst/langzamer. Keuze direct opgeslagen zonder extra knop, geldt voor nieuwe nacht-/handmatige/veiligheidskopieën, niet bestaande hercompressie. Mist programma of installatie faalt, lees melding/werkelijk formaat: gzip kan terugval zijn. Restore herkent onafhankelijk `.sql/.sql.gz/.sql.zst/.sql.xz`; extensie bewijst geen geldigheid.

## Maken, downloaden, testen

1. **Generate manual backup and download to PC**, beschrijfbare servermap controleren.
2. **Save backup**, generatie/controle afwachten; tijdens opslaan/kopiëren sluit scherm niet.
3. Naam/omvang/pad controleren. WSL: **Save to Windows Downloads**, **Choose folder in Windows**. Op afstand: getoonde opdracht op eigen computer uitvoeren.
4. Ontvangen bestand controleren, **Finish and exit**.

Windows-knoppen alleen WSL; opdrachten van andere installaties niet kopiëren, omdat server/bestand worden bepaald. Bij andere actieve backup/restore wachten, gezamenlijke vergrendeling niet omzeilen met concurrerende taken buiten paneel.

**Download latest backup** haalt bestaand bestand, maakt geen nieuwe kopie. Desktop-Linux/WSL probeert Downloads, SSH kan lokale opdracht tonen. Geen bestand: handmatig maken.

**Test integrity of latest backup**: datum/bestand controleren, **Choose another file** wisselt, bevestigen en tijdelijke import afwachten. Succes meldt tabellen/titels/leners zonder productie te vervangen. Geldt voor die kopie in dat systeem; dezelfde overgedragen kopie bereikbaar bewaren.

## MARC en cloud

**Export MARC21 records now** bevestigen, pakket bibliografie/autoriteiten afwachten, pad/inhoud controleren en download/overdracht volgen. Koha blijft werken; ingestelde cloud meldt uploadresultaat. SQL behouden voor volledig databaseherstel.

**Configure cloud backup** biedt twee Google-Drive-routes en andere diensten, waaronder OneDrive/MEGA/S3. Autorisatie op server of andere computer passend kiezen, uitsluitend getoonde URL/instructies volgen. S3 onderscheidt dienst, regio/endpoint, bucket. Echte uploadtest en ontvangst controleren; mislukte instelling is geen betrouwbare kopie.

Privégegevens uitsluitend in eigen installatie invoeren, niet handleiding/openbare afbeeldingen/support. Opslagbestanden daarvoor worden hier niet genoemd. Standaard SQL dagelijks 23:00, MARC zondag 03:00 in servertijd; eigen cron-instelling kan verschillen.

## Destructieve restore

**Bevestiging staat vervanging van huidige database toe.** Plan onderhoud en externe kopie; dit advies is geen automatisch uitgevoerd extra transport.

1. **Restore database**, serverbereikbaar bestand kiezen en zo nodig overdracht volgen. WSL kan Windows-bestand eerst naar lokale Linux-opslag kopiëren.
2. Lees toegang/inhoud/integriteit/ruimte; onderzoek verdacht/onvolledig bestand ondanks juiste extensie.
3. Bestand in vervangingsbevestiging opnieuw controleren. Tot dan teruggaan mogelijk; daarna wachten zonder sluiten, niet annuleerbaar.

Eerst SQL tijdelijk importeren en essentiële tabellen/aantal controleren; fout stopt vóór vervanging. Bestaande tabellen krijgen gecontroleerde kopie SQL met `pre_restore_safety_backup_`, datum/tijd/compressie. Faalt deze, bestaande database niet wissen; lege mag kopie overslaan.

Daarna clients stoppen, database opnieuw maken/importeren, schema bijwerken, zoeken synchroniseren, indexen opbouwen, diensten herstarten. Bewaard thema wordt zo mogelijk opnieuw toegepast.

Fout in tijdelijke test/veiligheidskopie betekent niet dat vervanging gebeurde. Bij opnieuw maken/import/schema kan afhankelijk van fase/kopie vorig herstel worden geprobeerd; **ook rollback kan mislukken**. Indexfout kan optreden nadat database al teruggezet is, zonder oude catalogus terug te brengen.

Bewaar volledig bericht en `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, voor index `/var/log/koha-easy-install/zebra-rebuild.log`. Gebruik centrumkaart, geen oude menunummers; technische hulp bij onzekere toestand. Controleer dashboard, records en zoekopdrachten OPAC/staff. SQL-voltooiing bewijst geen herstel van externe bestanden.

## Gecontroleerde bronnen

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
