"""Database tables section: deep maintenance and the SQL reports pack.

Both ask before changing anything: the installer's dry run (preview and
question, KEI_TASK_ANSWER=no) is shown first, then the routine runs.
"""

from __future__ import annotations

from ..i18n import t
from ..screens.dialogs import ChoiceScreen
from .common import preview_then_run


async def deep_maintenance(app) -> None:
    await preview_then_run(app, t("Deep Maintenance"), t("Deep maintenance"), "db-maintenance",
                           total_steps=3)


async def reports_pack(app) -> None:
    title = t("Essential reports pack")
    choice = await app.push_screen_wait(ChoiceScreen(
        title, t("Read-only SQL reports for Koha (Reports > Saved reports):"), [
            ("install", t("Install or update the pack")),
            ("remove", t("Remove the pack")),
        ]))
    if choice == "install":
        await preview_then_run(app, title, t("Preview (dry run)"), "reports-install")
    elif choice == "remove":
        await preview_then_run(app, title, t("Preview (dry run)"), "reports-remove", danger=True)
