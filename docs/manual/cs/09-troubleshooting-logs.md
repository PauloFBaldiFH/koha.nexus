# 9. Diagnostika a protokoly

[Obsah](README.md)

Zapište akci/čas/úplnou chybu a fungující části. Stránka, služba a úspěšné hledání jsou odlišné testy. Reinstalace/restore není univerzální první pomoc.

## Diagnostika

Aktualizujte **Control Dashboard**. **Diagnostics & maintenance center > Detailed server & Koha status**, **Full system health check**, přečtěte zprávu. **View latest validation report** znovu otevře; **Export diagnostics** ukáže složku pro podporu. I po maskování prověřte osobní údaje/názvy/adresy, nesdílejte celou instalaci. Klasický fallback Textual nevrací staré operace; zprávu/log uchovat.

| Cesta | Obsah |
| --- | --- |
| `/var/log/koha-easy-install/` | Hlavní Linux |
| `apt.log` | Balíčky/kroky |
| `validacao-*.log` | Datované zprávy |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/export |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Index/hledání |
| `/var/log/koha-easy-install/tools/` | Nástroje |
| `C:\Koha\logs`, dříve `C:\KohaEasy\logs` | Windows dle instalace |

`*` znamená datované soubory, před prvním použitím nemusí existovat. Přesná zobrazená cesta přednostní. **Library tools > View tool logs** dle data/rutiny, omezeno kvůli soukromí. Kontext/datum/verze/OK/varování/chyba/info číst jednotlivě. **No critical failures** může obsahovat varování; starý backup není porucha databáze. Po opravě znovu validovat/porovnat.

**Real-time Apache log auditing** staff/OPAC, starší alternativní cesty. Textual **Pause/p** zastaví pohled, ne Apache; **Continue** pokračuje, **Back/Esc** zavře. Klasické `Ctrl+C` jen při tomto sledování, ne každá úloha. Čas/kontext `error/fatal/denied/fail`, barva není důkaz příčiny.

## Příznaky

- Nedostupný OPAC/staff: Apache/MariaDB/Plack/cache, lokální/síť/VPN/tunel. `localhost` je počítač prohlížeče. **Restart / repair Koha services (Memcached, Plack)** může přerušit: výsledek/nová kontrola.
- Nenalezený titul: motor/fronta/index-databáze. **Search engine & indexing > Repair / rebuild indexing**, číst a čekat; přechod Elasticsearch není povinný začátek.
- Chybějící backup: čas/výsledek/disk, server/Linux při cron, `.part` nedokončený. `backup_sql.log`, integrita/ruční; poslední platný nemazat bez jiné jisté kopie, bez souběhu.
- Import/počty: Magic Import/MARC-log, vstup/příprava/zápis, režim/kódy/barcode/odmítnutí/duplicity. Malý náhled neověří vše; kompletní test a hotové fáze před opakováním.
- Restore: zjistit fázi; index může selhat po databázi, rollback také. Databáze/hledání/validace ověřit.
- AI/obohacení pomalé: Ollama/volba/paměť nebo práce/servery/limity; velké úlohy neopakovat jen pro prodlení. Vnější služba a místní RAM různé příčiny.

## Windows ikona

PowerShell přihlášeného uživatele, **bez správce**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Může obnovit zástupce/restartovat tray, není jen čtení. `diagnose-<date>.txt` v rozpoznaném `logs`; cestu/chybu uložit. Odlišné od správcovské instalace.

**Deep database optimization & log cleanup** udržuje/restartuje, může odstranit užitečnou historii. Diagnostiku před údržbou uschovat, ne zakrývat chybu. Pro pomoc verze, Windows/WSL/distribuce, akce/čas/úplné sdělení, OPAC/staff/hledání, předchozí operace a soukromím zkontrolované výňatky.

**K potvrzení:** příčina bez celého sdělení/logu; neautomaticky síť/instalace.

## Ověřené zdroje

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
