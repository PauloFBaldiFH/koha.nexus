"""Diagnostics and maintenance center, as panel screens.

  status             services, search, machine and backup at a glance
  health             the full validation under Pac-Man -> summary + report
  validation_report  the latest report
  apache_log         staff or OPAC error log, followed live in the panel
  repair_services    restart Memcached/Plack/Koha -> what is running now
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..i18n import t
from ..screens.dialogs import ChoiceScreen, CredentialsScreen, TextScreen
from ..screens.logtail import LogTailScreen
from .common import failed, last_message, run_task, show_done, show_failure, tx
from .install import credential_groups


async def status(app) -> None:
    title = t("Server Status")
    result = await run_task(app, title, "status")
    if failed(result):
        await show_failure(app, title, result)
        return
    groups = credential_groups(result.value, key="row")
    await app.push_screen_wait(CredentialsScreen(title, "", groups, kind="info", copy=False))


async def health(app) -> None:
    title = t("Full system validation")
    result = await run_task(app, title, "health")
    if failed(result):
        await show_failure(app, title, result)
        return
    out = result.value
    kind, head, body = last_message(out)
    report = out.previews[-1][1] if out.previews else ""
    await app.push_screen_wait(TextScreen(head if head and head != "OK" else title, report,
                                          kind="ok" if kind == "ok" else "error", body=body))


async def validation_report(app) -> None:
    title = t("Diagnostic Report")
    out = await app.bridge.task("validation-report")
    if not out.previews:
        msg = out.last("error")
        await app.push_screen_wait(TextScreen(title, "", kind="error", body=msg[2] if msg else t("Unknown error.")))
        return
    await app.push_screen_wait(TextScreen(title, out.previews[-1][1]))


async def apache_log(app) -> None:
    title = t("Apache Log Auditing")
    choice = await app.push_screen_wait(ChoiceScreen(
        title, tx("Select the log for continuous monitoring:\n\n"
                  "(Press CTRL+C to stop viewing and return to the menu)").split("\n\n")[0],
        [("1", t("Staff / Intranet Errors (intranet-error.log)")), ("2", t("OPAC Errors (opac-error.log)"))]))
    if not choice:
        return
    out = await app.bridge.task("apache-log", choice)
    path = out.get("file")
    if not path:
        msg = out.last("error")
        await app.push_screen_wait(TextScreen(title, "", kind="error", body=msg[2] if msg else t("Unknown error.")))
        return
    await app.push_screen_wait(LogTailScreen(title, path))


async def repair_services(app) -> None:
    title = t("Restarting Koha services")
    await show_done(app, title, await run_task(app, title, "repair-services"))
