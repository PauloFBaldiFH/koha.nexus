"""MarcExportScreen: the MARC21 export (the weekly /root/backup_marc.sh run
now) in the same screen as the manual SQL backup (screens/save_backup.py):
the folder of the server on the left, what the export makes on the right,
then the download button and the scp command.

  ╭ 📚 Export MARC21 records ──────────────── ① Folder › ② Exporting › ③ Download ╮
  │ [Home] [Backups] ... [Up] [📁 New folder]          ╭ The file that will be... ╮ │
  │ [/home/ana/backups__________________________]     │ koha_marc_<date>.tar.gz  │ │
  │ ╭ folder tree (folders and MARC21 packages) ╮      │ Format MARC21 (ISO 2709) │ │
  │ ╰───────────────────────────────────────────╯      ├ What is exported ────────┤ │
  │                                                    │ 12 840 bibliographic ... │ │
  │                                                    ├ Last export ─────────────┤ │
  │                                [📚 Export MARC21 here] [Cancel]                 │
  ╰──────────────────────────────────────────────────────────────────────────────────╯

The installer's backup-marc task makes the package in DIR_MARC as always
(the weekly rotation and the cloud copy keep working) and copies it to the
folder chosen here, owned by the person so scp as that user can read it.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Static

from .. import save_backup
from ..i18n import t
from .save_backup import SaveBackupScreen

MARC_SUFFIXES = (".tar.gz", ".mrc")


def _count(text: str | None) -> str:
    """"12840" as "12,840"; "—" when the database did not answer."""
    text = (text or "").strip()
    return f"{int(text):,}" if text.isdigit() else "—"


class MarcExportScreen(SaveBackupScreen):
    TASK = "backup-marc"
    TREE_SUFFIXES = MARC_SUFFIXES
    WANTED = staticmethod(save_backup.is_marc_package)

    def __init__(self, info: dict, marc: dict):
        super().__init__(info)
        self._marc = marc
        self._estimate = save_backup.size_bytes(marc.get("newest_size") or "")
        self._dir_marc = marc.get("dir_marc") or "/var/backups/koha_marc"

    # --- texts --------------------------------------------------------------
    def _title_text(self) -> str:
        return t("📚 Export MARC21 records")

    def _prompt_text(self) -> str:
        return t("Save the MARC21 package in this folder of the server:")

    def _save_label(self) -> str:
        return t("📚 Export MARC21 here")

    def _saving_text(self) -> str:
        return t("Exporting the MARC21 records...")

    def _ok_text(self) -> str:
        return t("✅ MARC21 records exported and checked")

    def _wait_text(self) -> str:
        return t("Wait until the export ends.")

    def _step_labels(self) -> tuple[str, str, str]:
        return t("Folder"), t("Exporting"), t("Download")

    def _after_title(self) -> str:
        return t("After the export")

    def _then_text(self) -> str:
        if self._wsl:
            way = t("a button copies it to your Windows Downloads, or to a folder you choose in Windows")
        else:
            way = t("a button opens a page of this server where your browser downloads it")
        return t("The package is checked when it is made. Then ${way}, and the scp command for another "
                 "computer is ready to copy.", way=way)

    def _need_text(self, size: str) -> str:
        return t("about ${size} (the newest package)", size=size)

    def _tight_text(self) -> str:
        return t("⚠ Little room: the export writes the records and then packs them, about twice the size "
                 "of a package.")

    def _there_text(self, n: int, size: str, name: str) -> str:
        return t("${n} MARC21 package(s), ${size} in all.\nNewest: ${name}", n=n, size=size, name=name)

    def _none_there_text(self) -> str:
        return t("No MARC21 package in this folder yet.")

    def _created_later_text(self) -> str:
        return t("The folder will be created when the export runs.")

    def _tips_text(self) -> str:
        return t("• The package stays on this server; Finish and exit deletes nothing.\n"
                 "• Open it with 7-Zip, WinRAR or tar: it holds two .mrc files (ISO 2709), one with the "
                 "bibliographic records and one with the authorities.\n"
                 "• MarcEdit, another Koha (Cataloguing > Stage records for import) or a union catalogue "
                 "read them.\n"
                 "• It is not a full backup: loans, patrons and settings are only in the database backup.")

    # --- the file and the side ----------------------------------------------
    def _file_name(self) -> str:
        return save_backup.marc_file_name()

    def _format_rows(self) -> ComposeResult:
        stamp = save_backup.marc_file_name()[len("koha_marc_"):-len(".tar.gz")]
        yield self._row(t("Format"), "sb-pv-codec", t("MARC21 (ISO 2709) in a .tar.gz package"))
        yield self._row(t("Contents"), "sb-pv-contents", f"biblios_{stamp}.mrc\nauthorities_{stamp}.mrc")
        yield self._row(t("Size"), "sb-pv-size", "—")
        yield Static(t("A copy also stays in ${folder} with the weekly MARC21 backups, and goes to the "
                       "cloud when one is set.", folder=self._dir_marc),
                     classes="dialog-note sb-note", markup=False)

    def _extra_side(self) -> ComposeResult:
        with self._card(t("What is exported"), "sb-records"):
            yield self._row(t("Bibliographic"), "sb-biblios", _count(self._marc.get("biblios")))
            yield self._row(t("Authorities"), "sb-auths", _count(self._marc.get("authorities")))
            yield Static(t("Every record in the catalogue, as Koha's own export writes it. Koha keeps "
                           "working while it runs."), classes="sb-hint sb-note", markup=False)
        with self._card(t("Last export"), "sb-last"):
            newest = self._marc.get("newest")
            if newest:
                yield self._row(t("File"), "sb-last-name", Path(newest).name)
                yield self._row(t("Date"), "sb-last-date", self._marc.get("newest_date") or "—")
                yield self._row(t("Size"), "sb-last-size", self._marc.get("newest_size") or "—")
            else:
                yield Static(t("No MARC21 export was made on this server yet."), classes="sb-hint",
                             markup=False)

    def _preview(self) -> None:
        super()._preview()
        if self._file is None and not self._busy:
            stamp = save_backup.marc_file_name()[len("koha_marc_"):-len(".tar.gz")]
            self.query_one("#sb-pv-contents", Static).update(f"biblios_{stamp}.mrc\nauthorities_{stamp}.mrc")

    def _after_save(self, out) -> None:
        contents = (out.get("contents") or "").split()
        if contents:
            self.query_one("#sb-pv-contents", Static).update("\n".join(contents))
        if out.get("cloud") == "yes":
            self.app.notify(t("The package was also sent to the cloud."), timeout=6)
