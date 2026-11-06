"""Koha's backup facts the Backup center (views/backups.py) shows: the
compressions of new backups and the result of the last nightly run."""

from __future__ import annotations

# BACKUP_COMPRESSION in backup.conf (installer: backup_set_codec). Restores
# read any of them, whatever this setting says.
CODECS = {
    "gz": "Gzip (.sql.gz) · opens anywhere",
    "zst": "Zstandard (.sql.zst) · fast and smaller: large catalogs",
    "xz": "XZ / LZMA (.sql.xz) · smallest, slow to make: long-term storage",
}
# The last nightly run, as backup_sql.log tells it (kei_backup_summary).
RESULTS = {
    "ok": ("OK", "ok"),
    "failed": ("FAILED", "bad"),
    "skipped": ("Skipped (busy)", "warn"),
    "none": ("Not run yet", "warn"),
}
CODEC_NOTE = ("Used by the nightly backup, manual backups and the safety copies made before a change. "
              "Restore database recognises .sql, .sql.gz, .sql.zst and .sql.xz on its own.")
