# 3. Backup och restore

[Innehåll](README.md)

## Funktioner, typer och mappar

**Backup center**, `b`, samlar datum, storlek, resultat, **Compression** och kort:

| Kort | Funktion |
| --- | --- |
| Download latest backup | Kopiera senaste hittade fil |
| Generate manual backup and download to PC | Skapa, kontrollera och överför databas |
| Export MARC21 records now | Exportera bibliografi och auktoriteter |
| Restore database | Ersätt aktuell databas |
| Configure cloud backup | Konfigurera extern uppladdning |
| Test integrity of latest backup | Prova tillfällig import |

**Restore database är ett kort**, inte övre knapp eller separat huvudmenyval. Resultat avser nattkörning, datum/storlek nyaste fil; olika körningar är möjliga.

SQL är Koha-databas, inte hel Windows-/Debian-avbildning. MARC21 innehåller bibliografi/auktoriteter i `.tar.gz`, inte full återhämtning av låntagare/cirkulation. Före restore av databas med tabeller skapas verifierad säkerhetskopia; tom databas kan hoppa över den.

Automatiskt SQL/säkerhet: `/var/backups/koha_sql`; MARC: `/var/backups/koha_marc`. Manuell backup har eget mål, normalt `backups` i identifierad hemmapp. `.part` är tillfällig tills kontroller och slutligt namn är klara.

## Komprimering och manuell kopia

**Compression**: gzip `.sql.gz` kompatibelt, Zstandard `.sql.zst` snabbt/mindre för stora kataloger, XZ/LZMA `.sql.xz` minst men långsamt. Sparas direkt utan extra knapp, gäller nya natt-/manuella/säkerhetskopior, inte omkomprimering. Saknas program eller installation misslyckas, läs verkligt format; gzip kan användas. Restore känner igen `.sql/.sql.gz/.sql.zst/.sql.xz` oberoende av valet; ändelse bevisar inte innehåll.

Öppna **Generate manual backup and download to PC**, kontrollera skrivbar servermapp, **Save backup**, invänta skapande/kontroll. Skärmen stängs inte under sparande/kopiering. Kontrollera namn/storlek/sökväg. WSL: **Save to Windows Downloads/Choose folder in Windows**; fjärråtkomst: kör visat överföringskommando på egen dator. Kontrollera mottagen fil och **Finish and exit**.

Windows-knappar bara i WSL. Återanvänd inte andra installationers kommandon; fil/server identifieras. Vänta om annan backup/restore körs; kringgå inte gemensamt lås med konkurrerande externa jobb.

**Download latest backup** hämtar befintlig fil, skapar inte ny. Desktop-Linux/WSL försöker Downloads, SSH kan visa lokalt kommando. Ingen fil: skapa manuellt.

## Test, MARC och moln

**Test integrity of latest backup**: fil/datum, **Choose another file** vid behov, bekräfta och vänta på tillfällig import. Framgång visar tabeller/titlar/låntagare utan att ersätta produktion. Gäller den filen i den miljön; behåll samma överförda kopia åtkomlig.

**Export MARC21 records now** bekräftas och skapar bibliografi/auktoritetspaket. Kontrollera sökväg/innehåll och följ hämtning/överföring. Koha fortsätter; konfigurerat moln rapporterar även uppladdning. Behåll SQL för hel databas.

**Configure cloud backup** erbjuder två Google Drive-vägar och bland annat OneDrive/MEGA/S3. Välj auktorisering på server/annan dator, följ endast visad URL. S3 skiljer tjänst, region/endpoint, bucket. Invänta faktiskt uppladdningstest och kontrollera mottagning; felaktig inställning är ingen pålitlig kopia. Privata uppgifter bara i installationen, inte offentliga texter/bilder/support; deras lagringsfiler anges inte här. Standard SQL dagligen 23:00, MARC söndag 03:00 i servertid; cron kan ha ändrats.

## Destruktiv restore

**Bekräftelsen tillåter ersättning av nuvarande databas.** Planera underhåll och extern kopia; detta råd utför panelen inte automatiskt åt dig.

Välj **Restore database** och serveråtkomlig fil, med överföringshjälp vid behov. WSL kan först kopiera från Windows till Linux. Läs åtkomst/innehåll/integritet/utrymme, utred misstänkt/ofullständig fil trots ändelse. Kontrollera igen i ersättningsbekräftelsen. Före den kan du avstå; efteråt vänta utan att stänga, ej avbrytbart.

SQL importeras först tillfälligt och väsentliga tabeller/antal kontrolleras. Fel stoppar före ersättning. Befintliga tabeller skyddas med verifierad SQL-kopia `pre_restore_safety_backup_`, datum/tid/komprimering. Kopieringsfel ska inte radera befintlig databas; tom kan hoppa över kopian.

Sedan stoppas klienter, databasen återskapas/importeras, schema uppdateras, sökning synkroniseras, index byggs och tjänster startas. Sparat tema återappliceras om tillgängligt, som ett försök.

Fel i test/kopia betyder inte genomförd ersättning. Vid återskapande/import/schema kan föregående tillstånd återhämtas beroende på steg/kopia, men **rollback kan också misslyckas**. Indexfel kan ske efter att databasen återställts utan att gamla katalogen kommer tillbaka.

Spara fullständigt fel och `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, indexets `/var/log/koha-easy-install/zebra-rebuild.log`. Återvänd till centrumkort, inte gamla menynummer; ta teknisk hjälp vid osäkert tillstånd. Kontrollera dashboard, poster och sökning i OPAC/staff. SQL-slut bevisar inte externa filers återställning.

## Kontrollerade källor

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
