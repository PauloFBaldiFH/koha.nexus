# 3. Backup a restore

[Obsah](README.md)

## Centrum a kopie

**Backup center**, `b`: poslední backup, velikost, výsledek, **Compression** a karty.

| Karta | Účel |
| --- | --- |
| Download latest backup | Nejnovější nalezený soubor |
| Generate manual backup and download to PC | Vytvořit, ověřit, přenést databázi |
| Export MARC21 records now | Bibliografie a autority |
| Restore database | Nahradit současnou databázi |
| Configure cloud backup | Externí odesílání |
| Test integrity of latest backup | Dočasný import k testu |

**Restore database je karta**, ne horní tlačítko ani samostatné hlavní menu. Výsledek je poslední noc, datum/velikost nejnovější soubor, nemusí stejná úloha.

SQL obsahuje databázi Koha, ne celý obraz Windows/Debian. MARC21 má bibliografii/autority v `.tar.gz`, nenahradí SQL pro čtenáře/výpůjčky. Před restore databáze s tabulkami vzniká ověřená bezpečnostní kopie, prázdná ji může přeskočit.

SQL automatické/bezpečnostní `/var/backups/koha_sql`, MARC `/var/backups/koha_marc`. Ruční má vlastní cíl, výchozí `backups` ve zjištěném domovském adresáři. `.part` je dočasný do kontrol a přejmenování.

## Komprese a přenos

**Compression**: gzip `.sql.gz` kompatibilní, Zstandard `.sql.zst` rychlý/menší pro velké katalogy, XZ/LZMA `.sql.xz` nejmenší/pomalejší. Uloženo ihned, bez dalšího tlačítka, pro nové noční/ruční/bezpečnostní, ne rekompresi starých. Chybí-li program/selže instalace, může nastoupit gzip: čtěte skutečný formát. Restore nezávisle pozná `.sql/.sql.gz/.sql.zst/.sql.xz`; přípona nedokládá obsah.

**Generate manual backup and download to PC**: zapisovatelný adresář serveru, **Save backup**, čekat na tvorbu/kontrolu. Při zápisu/kopírování nelze zavřít. Jméno/velikost/cesta; WSL **Save to Windows Downloads/Choose folder in Windows**. Vzdáleně spusťte zobrazený příkaz na vlastním počítači. Ověřte přijetí, **Finish and exit**.

Tlačítka Windows jen WSL, cizí příkazy nepřebírat: odvozeny ze serveru/souboru. Při jiném backup/restore čekejte, neobcházejte společný zámek souběžným externím procesem. **Download latest backup** přenáší existující, nevytváří. Desktop-Linux/WSL zkusí Downloads, SSH může ukázat lokální příkaz. Bez souboru vytvořte ruční.

## Test, MARC a cloud

**Test integrity of latest backup**: datum/soubor, **Choose another file**, potvrzení a dočasný import. Úspěch hlásí tabulky/záznamy/čtenáře bez náhrady produkce; platí pro danou kopii/prostředí. Zachovejte přístup ke stejné přenesené kopii.

**Export MARC21 records now** potvrdit, balík bibliografie/autorit, ověřit cestu/obsah a přenos. Koha běží dál; cloud, je-li nastaven, hlásí i odeslání. SQL ponechat pro kompletní databázi.

**Configure cloud backup** nabízí dvě cesty Google Drive a mj. OneDrive/MEGA/S3. Autorizace na serveru/jiném počítači, pouze uvedená URL/instrukce. S3 rozlišuje službu, region/endpoint, bucket. Skutečný test odeslání a kontrola příjmu; nespoléhat na chybnou konfiguraci. Soukromé údaje jen v instalaci, nikoli veřejné texty/obrázky/podpora; jejich soubory zde neuvádíme. Výchozí SQL denně 23:00, MARC neděle 03:00 v čase serveru; cron může lišit.

## Destruktivní restore

**Potvrzení dovoluje nahradit nynější databázi.** Naplánujte údržbu a externí kopii; panel toto doporučení automaticky neprovede.

V **Restore database** vyberte dostupný soubor, případně přeneste. WSL může nejprve kopírovat Windows do Linux. Čtěte přístup/obsah/integritu/místo, prošetřete podezřelý/neúplný soubor. Při potvrzení opět ověřte: do té chvíle lze odstoupit, poté nezavírat, nejde zrušit.

Nejdříve dočasný SQL-import, kontrola zásadních tabulek/počtu. Chyba zastaví před nahrazením. Existující tabulky chrání ověřená kopie SQL `pre_restore_safety_backup_` s datem/časem/kompresí; její chyba nemá smazat stávající databázi. Prázdná může přeskočit.

Pak zastavení klientů, vytvoření/import, upgrade schématu, synchronizace vyhledávání, indexy a služby. Uložený motiv se zkusí znovu aplikovat, je-li dostupný. Chyba testu/kopie není důkaz náhrady. Vytvoření/import/schéma může podle fáze/kopie spustit návrat, **ale rollback může také selhat**. Index může selhat po restore databáze bez návratu starého katalogu.

Zachovejte celou zprávu a `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, pro index `/var/log/koha-easy-install/zebra-rebuild.log`. Karta centra místo starých čísel, technická pomoc při nejistotě. Prověřte dashboard/záznamy/hledání OPAC/staff. Dokončené SQL nedokládá externí soubory.

## Ověřené zdroje

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
