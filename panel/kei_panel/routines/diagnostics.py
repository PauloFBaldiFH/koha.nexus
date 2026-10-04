"""Diagnostics and maintenance center, as panel screens.

  status             services, search, machine and backup at a glance
  health             the full validation under Pac-Man -> summary + report
  validation_report  the latest report
  apache_log         staff or OPAC error log, followed live in the panel
  repair_services    restart Memcached/Plack/Koha -> what is running now
  restart_koha       the same, asked first (the dashboard's button)
  export_diagnostics the support folder (--export-diagnostics) -> its path
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..env import _is_wsl as is_wsl
from ..i18n import t
from ..opener import open_folder
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, CredentialsScreen, MessageScreen, TextScreen
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


async def restart_koha(app) -> None:
    title = t("Restart Koha")
    if not await app.push_screen_wait(ConfirmScreen(title, tx(
            "Restart Koha's services now?\n\n"
            "Memcached, Plack, the background workers and Apache are restarted. "
            "Koha's pages stop answering for a few seconds; nothing is lost."))):
        return
    await repair_services(app)


async def export_diagnostics(app) -> None:
    title = t("Export diagnostics")
    result = await run_task(app, title, "export-diagnostics")
    if failed(result):
        await show_failure(app, title, result)
        return
    path = result.value.get("path")
    saved = t("Logs and system status were saved in this folder:")
    note = tx("Passwords, tokens and keys are replaced by [REDACTED]. "
              "Send this folder to whoever gives you support.")
    if is_wsl() and not app.env.demo:
        # Windows can open the folder (\\wsl.localhost\...), so offer it.
        if await app.push_screen_wait(ConfirmScreen(
                title, f"{saved}\n\n{path}\n\n{note}\n\n{t('Open the folder in Windows Explorer?')}")):
            if not open_folder(path):
                app.notify(t("Windows Explorer could not be opened."), severity="warning")
        return
    await app.push_screen_wait(MessageScreen(title, "", kind="ok", command=path, command_help=saved,
                                             command_notes=note))
