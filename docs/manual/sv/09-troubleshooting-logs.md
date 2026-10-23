# 9. Felsökning och loggar

[Innehåll](README.md)

Notera åtgärd/tid/fullständigt fel och fungerande delar. Öppen sida, aktiv tjänst och lyckad sökning är olika kontroller. Ominstallation/restore är ingen universell första lösning.

## Diagnos och loggar

Uppdatera **Control Dashboard**. **Diagnostics & maintenance center > Detailed server & Koha status**, sedan **Full system health check**, läs rapport. **View latest validation report** öppnar igen; **Export diagnostics** visar supportmapp. Trots maskning granska person-/fil-/nätuppgifter före delning, kopiera inte hela installationen. Klassisk reserv vid Textual-fel ångrar inte tidigare uppgift; behåll meddelande/logg.

| Plats | Innehåll |
| --- | --- |
| `/var/log/koha-easy-install/` | Linux huvudmapp |
| `apt.log` | Paket/berörda steg |
| `validacao-*.log` | Daterade rapporter |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/export |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Index/sökning |
| `/var/log/koha-easy-install/tools/` | Verktyg |
| `C:\Koha\logs`, äldre `C:\KohaEasy\logs` | Windows efter installation |

`*` avser daterade filer, kan saknas före första körning. Följ exakt visad sökväg. **Library tools > View tool logs** efter datum/uppgift; begränsad åtkomst på grund av personuppgifter. Rapport innehåller kontext/datum/version/OK/varning/fel/info. Läs varje meddelande; **No critical failures** kan ha varningar. Gammal backup är inte databasfel. Validera/jämför efter rättning.

**Real-time Apache log auditing** väljer staff/OPAC med gamla alternativvägar. Textual **Pause/p** pausar vy, inte Apache; **Continue** fortsätter, **Back/Esc** stänger. Klassiskt `Ctrl+C` för just denna loggföljning, inte varje operation. Tid/kontext runt `error/fatal/denied/fail`, markering ensam visar inte orsak.

## Efter symptom

- OPAC/staff ej nåbart: Apache/MariaDB/Plack/cache och lokal/nät/VPN/tunneladress. `localhost` är webbläsardator. **Restart / repair Koha services (Memcached, Plack)** kan avbryta åtkomst, läs och validera.
- Post ej sökbar: motor/kö/index-databas. **Search engine & indexing > Repair / rebuild indexing**, läs frågor/vänta; Elasticsearch-byte inte obligatoriskt först.
- Backup saknas: tid/resultat/disk och dator/Linux vid cron, `.part` är ofärdigt. `backup_sql.log`, integritetstest eller manuell kopia; radera inte sista giltiga utan annan säker, undvik överlapp.
- Importfel/antal: Magic Import/MARC-loggar, indata/förberedelse/skrivning, läge/koder/barcode/avvisningar/dubbletter. Litet prov validerar inte allt; full kontroll och avslutade steg före upprepning.
- Restorefel: identifiera steg; index kan fallera efter databas-restore, rollback också. Kontrollera databas/sökning/validering.
- AI/berikning långsam: Ollama/val/minne eller jobb/servrar/gränser; dubblera inte stora jobb på grund av dröjsmål. Fjärrfel och lokal RAM-brist utreds olika.

## Windows-ikon

PowerShell som inloggad användare, **inte administratör**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Kan återskapa genvägar/starta om tray, alltså inte bara läsning. Skriver `diagnose-<date>.txt` i hittad `logs`; spara sökväg/fel. Skilt från administrativ nyinstallation.

**Deep database optimization & log cleanup** underhåller/startar om men kan radera värdefull historik. Spara diagnostik före planerat underhåll, dölj inte fel. För hjälp: version, Windows/WSL/distribution, åtgärd/tid/fullständigt fel, OPAC/staff/sökning och föregående uppgift, integritetsgranskade utdrag.

**Att bekräfta:** orsak utan fullständigt fel/logg; skyll inte automatiskt på nät eller installation.

## Kontrollerade källor

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
