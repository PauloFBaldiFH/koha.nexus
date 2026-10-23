# 3. Backup at restore

[Nilalaman](README.md)

## Sentro at uri ng kopya

**Backup center**, `b`: petsa, laki, resulta, **Compression**, cards.

| Card | Layunin |
| --- | --- |
| Download latest backup | Kopyahin pinakabagong nahanap |
| Generate manual backup and download to PC | Gumawa/suriin/ilipat database |
| Export MARC21 records now | Bibliograpiya at authority records |
| Restore database | Palitan ang kasalukuyang database |
| Configure cloud backup | Panlabas na pagpapadala |
| Test integrity of latest backup | Pansamantalang import-test |

**Card ang Restore database**, hindi button sa itaas o hiwalay na pangunahing menu. Resulta sa huling gabi, petsa/laki sa pinakabagong file, maaaring magkaibang operasyon.

SQL ang Koha database, hindi buong Windows/Debian image. MARC21 bibliograpiya/awtoridad sa `.tar.gz` ay hindi kapalit ng SQL para mambabasa/sirkulasyon. May napatunayang safety copy bago restore ng may tables; maaaring laktawan kung walang laman.

Awtomatikong SQL/safety `/var/backups/koha_sql`, MARC `/var/backups/koha_marc`. May sariling destinasyon ang mano-mano, karaniwang `backups` sa natukoy na home. Pansamantala ang `.part` hanggang checks/rename.

## Compression at paglilipat

**Compression**: gzip `.sql.gz` malawak ang suporta, Zstandard `.sql.zst` mabilis/mas maliit sa malaking katalogo, XZ/LZMA `.sql.xz` pinakamaliit/mabagal. Agad nasasave, walang dagdag na button, para bagong gabi/manual/safety, hindi muling pinipiga ang dati. Kapag kulang/nabigo ang programa, maaaring gzip; basahin ang aktuwal na format. Hiwalay kinikilala ng restore `.sql/.sql.gz/.sql.zst/.sql.xz`; hindi patunay ang extension.

**Generate manual backup and download to PC**: masusulatan na server folder, **Save backup**, hintayin paggawa/check. Hindi nagsasara habang nagse-save/kopya. Suriin pangalan/laki/path. WSL **Save to Windows Downloads/Choose folder in Windows**; remote, patakbuhin ang ipinakitang utos sa sariling computer. Tiyakin natanggap, **Finish and exit**.

Windows buttons WSL lang; huwag mangopya ng utos ng ibang instalasyon, depende sa file/server. Kung may ibang backup/restore, maghintay, huwag lampasan shared lock gamit sabayang panlabas na gawain. **Download latest backup** kumukuha ng umiiral, hindi gumagawa. Desktop-Linux/WSL sumusubok Downloads, SSH maaaring lokal na utos; kung wala, gumawa manual.

## Test, MARC, cloud

**Test integrity of latest backup**: petsa/file, **Choose another file**, kumpirmahin at pansamantalang import. Tagumpay: tables/records/mambabasa, hindi pinapalitan production. Para lamang sa file/kapaligirang iyon; panatilihing maaabot ang parehong nailipat na kopya.

**Export MARC21 records now** kumpirmahin, hintayin pakete, tingnan path/laman/transfer. Umaandar pa Koha; ulat din cloud kung naka-configure. Itago SQL para buong database.

**Configure cloud backup**: dalawang Google Drive na paraan, pati OneDrive/MEGA/S3. Pahintulot server/ibang computer, ipinakitang URL/instruction lang. S3 hiwalay serbisyo/rehiyon/endpoint/bucket. Hintayin totoong upload-test at pagtanggap; huwag umasa sa bigong setup. Pribado sa instalasyon lang, hindi dokumento/larawang publiko/support; hindi tinutukoy ang taguang file. Default SQL araw-araw 23:00, MARC Linggo 03:00 oras server; maaaring iba cron.

## Mapanirang restore

**Pahintulot na palitan ang database ang pagkumpirma.** Magplano ng maintenance/panlabas na kopya; hindi awtomatikong ginagawa ng panel ang payong ito.

**Restore database**, maaabot na file, transfer kung kailangan. Maaaring kopyahin muna WSL Windows patungong Linux. Basahin akses/laman/integridad/espasyo, siyasatin kahina-hinala/kulang kahit tama extension. Muling suriin bago pumayag; hanggang doon maaaring umatras, pagkatapos maghintay nang walang pagsara, walang pagkansela.

Una temporary SQL-import, mahalagang tables/bilang. Bigong test humihinto bago palitan. May tables: napatunayang SQL `pre_restore_safety_backup_` may petsa/oras/compression; bigong kopya hindi dapat bumura kasalukuyan. Walang laman maaaring laktawan.

Sunod ihinto clients, likhain/import, schema, sync search, indexes, services. Sinusubukang ilapat muli ang naka-save na tema kung mayroon. Bigong test/kopya hindi patunay na napalitan. Create/import/schema maaaring subukang bumalik ayon sa yugto/kopya, **pero maaari ring mabigo ang rollback**. Posibleng index-error pagkatapos restore ng database, hindi pagbabalik ng lumang katalogo.

Itago buong mensahe, `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, index `/var/log/koha-easy-install/zebra-rebuild.log`. Card ng sentro, hindi lumang numero; teknikal na tulong kung hindi tiyak. Suriin dashboard/record/search OPAC-staff. Tapos SQL ay hindi patunay ng panlabas na files.

## Sinuring sanggunian

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
