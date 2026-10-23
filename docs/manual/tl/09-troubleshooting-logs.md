# 9. Paglutas ng problema at mga log

[Nilalaman](README.md)

Itala ang ginawa, oras, buong mensahe ng error at mga bahaging gumagana pa. Magkahiwalay na suriin ang pahina, serbisyo at paghahanap. Ang pag-install muli o restore ay hindi unang lunas sa lahat ng problema.

**Control Dashboard** refresh. **Diagnostics & maintenance center > Detailed server & Koha status**, **Full system health check**, basahin report. **View latest validation report** balik, **Export diagnostics** support folder. Kahit may redaction, suriin tao/names/addresses bago share, hindi buong install. Classic fallback Textual hindi undo ng nauna; itago error/log.

| Path | Laman |
| --- | --- |
| `/var/log/koha-easy-install/` | Pangunahing Linux |
| `apt.log` | Packages/stages |
| `validacao-*.log` | May petsang reports |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/export |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Index/search |
| `/var/log/koha-easy-install/tools/` | Tools |
| `C:\Koha\logs`, dati `C:\KohaEasy\logs` | Windows ayon install |

`*` dated files, maaaring wala bago first run. Eksaktong ipinakitang path. **Library tools > View tool logs** date/task, restricted dahil personal data. Context/date/version/OK/warning/error basahin bawat isa. **No critical failures** puwedeng may warning; old backup hindi database failure. Test/compare pagkatapos.

**Real-time Apache log auditing** staff/OPAC/old alternatives. Textual **Pause/p** view lang, hindi Apache; **Continue**, **Back/Esc** exit. Classic `Ctrl+C` para ganitong pagsubaybay, hindi lahat tasks. `error/fatal/denied/fail` oras/context, kulay hindi sanhi.

- OPAC/staff inaccessible: Apache/MariaDB/Plack/cache, local/network/VPN/tunnel. `localhost` browser computer. **Restart / repair Koha services (Memcached, Plack)** may putol; basa/check muli.
- Record hindi makita: engine/queue/index-database, **Search engine & indexing > Repair / rebuild indexing**, basa/hintay; Elasticsearch hindi unang obligasyon.
- Backup wala: oras/result/space/system sa cron, `.part` di tapos. `backup_sql.log`, test/manual; huwag huling valid nang walang ibang ligtas, iwas overlap.
- Import/counts: Magic Import/MARC, input/prepare/write, mode/codes/barcode/rejections/duplicates. Maliit preview hindi buong validation; full test/natapos na stages bago ulit.
- Restore: alamin stage, index puwedeng fail pagkatapos database, rollback din; database/search/validation.
- AI/enrichment mabagal: Ollama/choice/memory o task/server/limits, huwag ulitin malaki dahil delay. External at local RAM iba ang pagsisiyasat.

## Windows icon

PowerShell ng naka-sign-in, **hindi administrator**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Maaaring muling gumawa ng mga shortcut at simulan muli ang tray; hindi lamang ito nagbabasa ng datos. `diagnose-<date>.txt` sa natukoy `logs`, itago path/error. Iba sa administrative install.

Maaaring magsagawa ng pagpapanatili at pagsisimulang muli ang **Deep database optimization & log cleanup**, at maaaring mabura ang kapaki-pakinabang na kasaysayan. Itabi muna ang ulat ng pagsusuri. Kapag humihingi ng tulong, ibigay ang bersiyon, Windows o distribusyon ng Linux, paggamit ng WSL, ginawa, oras, buong mensahe, kalagayan ng OPAC, staff at paghahanap, at naunang operasyon. Suriin muna ang pribadong datos sa mga siping ibabahagi.

**Kailangang kumpirmahin:** sanhi nang walang buong mensahe/log; hindi awtomatikong network/install.

## Sinuring sanggunian

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
