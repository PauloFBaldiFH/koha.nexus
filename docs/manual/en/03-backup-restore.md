# 3. Backup and restore

[Manual index](README.md) · [Getting started](02-panel.md)

## 3.1 Find the operations

Open **Backup center** from the sidebar or press `b` on the main screen. It brings together the latest backup, size and result indicators, the compression selector and the operation cards.

Available actions are:

| Card | Purpose |
| --- | --- |
| Download latest backup | Copy the newest file found to the computer, where possible |
| Generate manual backup and download to PC | Create a database copy now, check the file and offer a transfer |
| Export MARC21 records now | Export bibliographic and authority records |
| Restore database | Replace the current database with the selected backup |
| Configure cloud backup | Connect backup uploads to an external service |
| Test integrity of latest backup | Test import into a temporary database |

**Restore database is a card in Backup center.** Do not look for a top restore button or a separate restore action in the current panel's main menu.

The result card describes the last nightly run, whereas the date and size describe the newest backup found. They may refer to different runs.

Sources: the `backup` section in [menus.py](../../../panel/kei_panel/menus.py), [views/backup.py](../../../panel/kei_panel/views/backup.py) and [routines/backup.py](../../../panel/kei_panel/routines/backup.py).

## 3.2 Understand the types of copy

**SQL backup:** contains the Koha database. This is the file used to restore the database through Backup center. It is not a complete image of the computer, Windows or the entire Debian filesystem.

**MARC21 export:** packages bibliographic and authority records as MARC files inside a `.tar.gz` archive. It does not replace an SQL backup for recovering the complete database, including patrons and circulation.

**Restore safety backup:** before replacing a database that already contains tables, the flow creates and validates a copy of that database. If the current database is empty, this stage can be skipped because there are no tables to save.

Default directories are:

- Automatic SQL and safety copies: `/var/backups/koha_sql`.
- MARC archives: `/var/backups/koha_marc`.

Manual backup has its own destination, selected on screen. It defaults to the `backups` subdirectory of the home directory identified by the panel. Do not assume every manual backup is saved alongside automatic backups.

Safety copies are written to a temporary file ending in `.part` and promoted to the final file only after checks. Do not select a `.part` file as a completed backup.

Sources: `DIR_SQL`, `DIR_MARC`, `create_safety_backup` and `write_backup_scripts` in the [installer](../../../installer); [save_backup.py](../../../panel/kei_panel/save_backup.py); `manual_backup` and `marc_backup` in [routines/backup.py](../../../panel/kei_panel/routines/backup.py).

## 3.3 Choose compression

In **Compression**, select the format for new backups:

| Format | On-screen description |
| --- | --- |
| Gzip, `.sql.gz` | Broad compatibility |
| Zstandard, `.sql.zst` | Fast and smaller; suggested for large catalogues |
| XZ / LZMA, `.sql.xz` | Smallest file, slower to create |

The choice is saved when selected; there is no extra save button on this screen. It applies to new nightly, manual and safety backups. Existing files are not recompressed.

If the required program cannot be installed, the screen reports the problem and new backups continue to use gzip. Read the notice about the format actually used.

Restore recognises plain SQL and supported compressed files independently of the current selection. For this procedure, use `.sql`, `.sql.gz`, `.sql.zst` or `.sql.xz`; the extension alone does not establish valid content.

Sources: `CODECS`, `_set_codec` and `_show_codec` in [views/backup.py](../../../panel/kei_panel/views/backup.py); `backup_set_codec`, `dump_codec` and `restore_preflight` in the [installer](../../../installer).

## 3.4 Create a manual backup

1. Open **Generate manual backup and download to PC**.
2. Check the server directory field. Accept the proposed folder or choose a suitable writable destination.
3. Click **Save backup**.
4. Wait for generation and checking. The screen cannot close while saving or copying.
5. Check the resulting filename, size and path.
6. Copy it outside the server. Under WSL, use **Save to Windows Downloads** or **Choose folder in Windows**. Over a remote connection, copy the transfer command displayed and run it in a terminal on your own computer.
7. Check that the file reached its destination. Use **Finish and exit** to close the screen.

Windows folder buttons appear only under WSL. Do not copy an example command from another installation: the panel builds the command for the file and server it detected.

If the panel reports another backup or restore in progress, wait. The code uses a shared lock to prevent overlap; do not bypass it by starting a competing copy outside the panel.

Sources: [screens/save_backup.py](../../../panel/kei_panel/screens/save_backup.py), [save_backup.py](../../../panel/kei_panel/save_backup.py), `function_manual_backup` and `backup_lock_acquire` in the [installer](../../../installer).

## 3.5 Download the newest backup

Open **Download latest backup**. Under WSL or on a Linux desktop, the flow tries to copy the file to the corresponding computer's Downloads folder. Over SSH, if that folder is not accessible to the server, the screen provides a command to run on your own computer.

This action downloads an existing file; it does not generate a new backup. If no file is found, the panel reports that. Generate a manual backup when you need a current copy before an operation.

Source: `download_latest` and `download_file` in [routines/backup.py](../../../panel/kei_panel/routines/backup.py).

## 3.6 Test integrity and restore capability

1. Open **Test integrity of latest backup**.
2. Check the proposed file and date. Use **Choose another file** to select a different one.
3. Confirm the test.
4. Wait for import into a temporary database and its checks.
5. Read the result, which identifies the file and reports table, bibliographic record and patron counts when successful.

This tests the file without replacing the production database. A successful result applies to the tested file in that environment; complete the transfer and retain access to that same file for later recovery.

Source: `test_backup` in [routines/backup.py](../../../panel/kei_panel/routines/backup.py) and `function_test_backup` in the [installer](../../../installer).

## 3.7 Export MARC21

1. Open **Export MARC21 records now**.
2. Read the confirmation and authorise the export.
3. Wait for the archive containing bibliographic and authority records.
4. Check the path and contents reported on screen.
5. Use the download offered locally or the displayed command to transfer the archive.

Koha continues operating during the export. If cloud upload is configured, the result also reports its outcome. Keep the MARC archive for record exchange; retain SQL for complete database recovery.

Source: `marc_backup` in [routines/backup.py](../../../panel/kei_panel/routines/backup.py) and `function_marc_backup` in the [installer](../../../installer).

## 3.8 Configure a cloud copy

Open **Configure cloud backup**. The flow offers two express Google Drive routes and a route for other services, including OneDrive, MEGA and S3.

1. Choose the route suitable for where the panel is running: authorisation on the server itself or a flow completed on another computer.
2. Follow only the address and instructions shown by your installation.
3. For another provider, choose the service and enter the connection name and requested fields. The S3 flow distinguishes the service, region or provider endpoint, and destination bucket.
4. Wait for the real upload test and read its result. Resolve a failure before relying on that copy.
5. Check that the copy arrived at the chosen destination.

Enter private authorisation information only in your installation's fields. Do not include it in the manual, public images or support messages. This procedure does not publish values or paths of files that store that information.

The installer defaults to an SQL backup every day at 23:00 and a MARC export on Sundays at 03:00, in server time. Cron settings can change these schedules; they are not a promise about an already customised installation.

Sources: `cloud_backup`, `cloud_provider`, `_provider_values` and `_cloud_result` in [routines/backup.py](../../../panel/kei_panel/routines/backup.py); `write_cron_tasks` in the [installer](../../../installer).

## 3.9 Restore the database

**Destructive action: confirmation authorises replacement of the current database.** Arrange a maintenance window and keep a copy outside the server before starting. This is an operational recommendation, not an extra step the panel automatically performs on your computer.

1. Open **Restore database** in Backup center.
2. Select the backup that should replace the current database. If the file is on your computer and the panel runs on another server, follow the on-screen transfer guidance and then select the server copy.
3. Under Windows with WSL, a file from the Windows drive may be copied into local Linux storage before restore.
4. Read the readability, content, integrity and space checks. Investigate warnings about a suspicious or possibly incomplete file; do not confirm simply because its extension looks correct.
5. Check the file again in the replacement confirmation. You can withdraw through the screen up to that confirmation.
6. Once authorised, wait without closing the window. Restore is non-cancellable in the panel.

### What the process does

First, SQL is imported into a temporary database. The code checks the table count and essential Koha tables. If the test fails, it stops before replacing the current catalogue.

If the current database has tables, a safety backup is created and validated in the SQL directory. Its name begins with `pre_restore_safety_backup_`, followed by the date, time and compression extension. If creation fails, the flow should not erase the current database. An empty database may skip this copy.

Next, the process stops Koha database clients, recreates and imports the database, upgrades its schema, synchronises the search engine, rebuilds indexes and restarts services. It also attempts to reapply saved OPAC and staff appearance when saved theme state exists.

### Interpret failures

- **Temporary test failure:** that stage did not replace the current catalogue.
- **Safety copy creation failure:** the operation stops before replacing a database containing tables.
- **Recreation, import or schema upgrade failure:** depending on the stage and availability of a safety copy, the code attempts to recover the previous database. That recovery can fail; automatic rollback is not guaranteed in every situation.
- **Index rebuild failure:** the database may already have been restored. An error message alone does not establish that the previous contents were recovered.

Read the full message and retain the files it identifies. Operation logs are `/var/log/koha-easy-install/restore.log` and `/var/log/koha-easy-install/restore-import.log`. For indexing failures, the code also points to `/var/log/koha-easy-install/zebra-rebuild.log`.

Do not follow old menu numbers to attempt recovery. In the current panel, return to **Restore database** in Backup center to select the appropriate copy, with technical support if the database state is uncertain.

### After completion

Refresh Control Dashboard, open the staff interface and catalogue, and check records and searches. These are operational checks. Completion of the routine alone does not establish recovery of files outside the SQL database.

Sources: `restore`, `_copy_in` and `_restore_file` in [routines/backup.py](../../../panel/kei_panel/routines/backup.py); `restore_preflight`, `_function_restore_database`, `create_safety_backup`, `restore_failed`, `restored_search_engine` and `restore_task_reindex` in the [installer](../../../installer).
