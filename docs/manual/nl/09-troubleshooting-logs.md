# 9. Problemen en logboeken

[Inhoud](README.md)

Noteer actie/tijd/volledige fout en wat werkt. Open pagina, actieve dienst en geslaagde zoekactie zijn verschillende controles. Herinstallatie/restore is geen universele eerste oplossing.

## Diagnose en locaties

**Control Dashboard** verversen. **Diagnostics & maintenance center > Detailed server & Koha status**, dan **Full system health check**, rapport lezen. **View latest validation report** heropent, **Export diagnostics** toont supportpad. Ondanks afscherming privégegevens, leners/namen/adressen vóór delen controleren, niet hele installatie kopiëren. Klassiek fallback bij Textual-fout maakt eerder werk niet ongedaan; bericht/log bewaren.

| Locatie | Inhoud |
| --- | --- |
| `/var/log/koha-easy-install/` | Hoofdmap Linux |
| `apt.log` | Pakketten en betreffende fasen |
| `validacao-*.log` | Gedateerde rapporten |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/export |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Index/zoeken |
| `/var/log/koha-easy-install/tools/` | Hulpmiddelen |
| `C:\Koha\logs`, vroeger `C:\KohaEasy\logs` | Windows volgens installatie |

`*` duidt gedateerde bestanden aan, mogelijk afwezig vóór eerste taak. Exacte getoonde pad voorkeur. **Library tools > View tool logs** op datum/routine, beperkt wegens persoonsgegevens. Rapport met context/datum/versie/OK/waarschuwing/fout/info: afzonderlijk lezen. **No critical failures** kan waarschuwingen hebben; oude backup is anders dan databasefout. Na herstel opnieuw valideren/vergelijken.

**Real-time Apache log auditing** kiest staff/OPAC en oude alternatieve paden. Textual **Pause/p** stopt weergave, niet Apache; **Continue** hervat, **Back/Esc** sluit. Klassiek gebruikt `Ctrl+C` voor dit volgen, niet elke taak. Tijd/context rond `error/fatal/denied/fail` lezen; markering bewijst geen oorzaak.

## Per symptoom

- OPAC/staff onbereikbaar: Apache/MariaDB/Plack/cache en lokaal/netwerk/VPN/tunneladres. `localhost` is browsercomputer. **Restart / repair Koha services (Memcached, Plack)** kan onderbreken; uitkomst lezen en hercontroleren.
- Record niet vindbaar: motor/wachtrij/index-database. **Search engine & indexing > Repair / rebuild indexing**, bevestigingen lezen/wachten. Elasticsearch-wissel niet verplicht eerste stap.
- Backup ontbreekt: tijd/resultaat/ruimte en server/Linux bij cron, `.part` onvoltooid. `backup_sql.log`, integriteit of handmatig; laatste geldige niet zonder andere veilige kopie wissen, geen overlappende taken.
- Importfout/aantallen: Magic-Import-/MARC-logs, invoer/voorbereiding/schrijven, modus/codes/barcodes/afwijzingen/dubbelen. Kleine preview valideert niet alles; volledig controleren en afgeronde fasen vóór herhalen bepalen.
- Restorefout: fase vaststellen; index kan na database-restore falen, rollback eveneens. Database/zoeken/validatie controleren.
- AI/verrijking traag: Ollama/keuze/geheugen of taak/servers/limieten; grote taak niet dupliceren wegens vertraging. Externe dienst en lokale RAM vragen andere diagnose.

## Windows-pictogram

PowerShell van aangemelde gebruiker, **niet als administrator**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Kan snelkoppelingen herstellen en tray herstarten, dus niet alleen lezen. Schrijft `diagnose-<date>.txt` in gevonden `logs`; pad/fout bewaren. Anders dan administratieve eerste installatie.

**Deep database optimization & log cleanup** onderhoudt/herstart maar kan nuttige geschiedenis wissen. Diagnoses bewaren en onderhoud plannen, geen fouten verbergen. Voor hulp: versie, Windows/WSL of distributie, actie/tijd/volledig bericht, OPAC/staff/zoeken en voorgaande handeling; fragmenten op privacy controleren.

**Nog te bevestigen:** oorzaak zonder volledig bericht/log; niet automatisch netwerk/installatie aanwijzen.

## Gecontroleerde bronnen

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
