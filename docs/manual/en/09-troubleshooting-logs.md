# 9. Troubleshooting and logs

[Manual index](README.md) · [Previous: administration](08-administration.md)

Record the action, time, full error and what still works. A page opening, a running service and a successful search are different checks. Do not reinstall or restore the database as the first response to every error.

## Start with the panel

1. Open **Control Dashboard** and refresh the state.
2. Under **Diagnostics & maintenance center**, open **Detailed server & Koha status** to inspect services, search, machine and backup.
3. Run **Full system health check** and read its summary and report.
4. Open **View latest validation report** to consult details afterwards.
5. If support is needed, use **Export diagnostics** in Control Dashboard. Keep the reported path.

The exporter redacts passwords, tokens and keys. Still inspect the material before sharing: patron information, filenames and infrastructure addresses can be sensitive. Do not indiscriminately copy the entire installation directory.

If the Textual panel cannot open, the launcher has a classic fallback mode. This does not mean a previously started operation was undone. Keep the message and panel log.

## Where to look for logs

| Location | What to investigate |
| --- | --- |
| `/var/log/koha-easy-install/` | Directory for installer and Linux routine logs. |
| `apt.log` in that directory | Package installation and output from stages using this log. |
| `validacao-*.log` in that directory | Validation reports, separated by date and time. |
| `new-panel.log` in that directory | Textual panel errors, including tracebacks on execution failures. |
| `backup_sql.log` and `backup_marc.log` in that directory | SQL backup and MARC export results. |
| `restore.log` and `restore-import.log` in that directory | Restore stages and SQL import. |
| `zebra-rebuild.log` and `search-engine.log` in that directory | Search engine rebuilding and diagnostics. |
| `/var/log/koha-easy-install/tools/` | Tool logs, including import and bibliographic operations. |
| The Windows installation's `logs` directory | Windows-side logs; the current default is `C:\Koha\logs`, with support for older installations at `C:\KohaEasy\logs`. |

Names containing `*` represent multiple dated files, not a literal filename to create. A log may not exist before the routine first runs. For a tool operation, prefer the exact path shown in its summary or error.

Tool logs can contain personal data and are created with restricted access. Open **View tool logs** under Library tools and select the correct run by date and routine.

## Read a validation report

The report includes context, date, panel version and results. Markers distinguish OK, warning, failure and information. Read each failure's message; the final count alone does not explain the cause.

**No critical failures** can still accompany warnings. An old-backup warning requires a different response from a database or search failure. After fixing a problem, validate again and compare with the previous report.

## Inspect OPAC or staff errors

Under Diagnostics & maintenance center, open **Real-time Apache log auditing** and choose staff/intranet or OPAC. The panel finds the corresponding file and uses alternative paths for older installations.

In the Textual screen, **Pause** or **p** stops display updates without stopping Apache. **Continue** resumes them. **Back** or **Esc** closes the viewer. The classic panel has a different flow, using `Ctrl+C` to leave log monitoring; do not apply that shortcut to every panel operation.

Look for messages near the error time. Lines containing `error`, `fatal`, `denied` or `fail` are highlighted, but a highlighted word alone does not establish the cause. Include enough context, removing personal data before sending it to anyone.

## Procedures by symptom

### OPAC or staff does not open

Check Apache, MariaDB, Plack and cache states in detailed status. Determine whether the address is local, network, VPN or tunnel, and whether both interfaces are affected. `localhost` refers to the computer running the browser; it is not a universal remote server address.

Use **Restart / repair Koha services (Memcached, Plack)** when diagnostics indicate service problems. This can briefly interrupt access. Read the final message and validate again; do not assume success just because the button finished.

### A record exists but search cannot find it

Check the search engine, queue and index/database relationship in detailed status. Under **Search engine & indexing**, **Repair / rebuild indexing** handles repair or reconstruction. Read rebuild questions before confirming and wait for completion. Switching Zebra to Elasticsearch is not a mandatory first investigation step.

### A backup did not appear

Check the last run's time, result and free space. Confirm the computer and Linux were running at the cron time. A `.part` file still being written is not a completed backup. Inspect `backup_sql.log` and Backup center before starting overlapping operations.

Use the integrity check to test an existing backup. For an immediate copy, generate a manual backup and check its result. Do not delete the last valid backup to free space before retaining another safe copy.

### Import failed or counts are unexpected

Keep Magic Import logs and the MARC-stage log identified by the error. Compare input, preparation and actual import counts. Check mode, library and item type codes, barcodes, rejected records and duplicate policy.

A correct small preview does not establish validity of the full file. Use full mapping validation. If execution already reached database writing, identify completed stages before retrying to avoid duplicate records or patrons.

### Restore ended with an error

Read the failed stage and restore logs. An indexing failure after import differs from a failure before replacing the database. The mechanism can attempt to recover the previous state for some failures, but rollback can also fail. Do not declare complete recovery without checking the database, search and validation.

### AI or enrichment is slow

For AI, check Ollama state, the saved selection and loaded memory. For enrichment, inspect the job, servers and query limits. Do not repeat large jobs just because results were not immediate. An external service failure needs a different investigation from insufficient local RAM.

### Windows icon or tray does not work

The repository provides a specific diagnostic. Run it in the signed-in user's PowerShell, **without opening as administrator**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

This script is not purely read-only: it checks and can recreate shortcuts and restart the tray. Output is saved as `diagnose-<date>.txt` under the detected installation's `logs` directory. Keep the displayed path and full error details. This differs from initial installation through administrative PowerShell.

## Maintenance does not replace investigation

**Deep database optimization & log cleanup** performs maintenance and restarts services. Do not run it merely to hide an error: it can remove log history useful for investigation. Preserve relevant diagnostics first and choose a maintenance window.

## Information to include when asking for help

Give the installed version, Windows/WSL or Linux distribution, action, time, symptom and complete message. Say whether OPAC, staff and search work, and whether import, restore or update happened immediately beforehand. Add relevant diagnostic excerpts after checking privacy.

**To confirm:** the cause of a failure without its full message and execution log. This manual provides an investigation sequence; it does not automatically attribute every error to the network or installation.

## Checked sources

- [Diagnostics](../../../panel/kei_panel/routines/diagnostics.py), status, validation, Apache and export.
- [Log viewer](../../../panel/kei_panel/screens/logtail.py), Textual buttons and shortcuts.
- [Search](../../../panel/kei_panel/routines/search.py), repair and engine switching.
- [Installer](../../../installer), log directories and names, validation, panel fallback, status and maintenance.
- [Windows diagnostic](../../../windows/diagnose.ps1) and [Windows paths](../../../windows/KohaEasy.Core.psm1).
