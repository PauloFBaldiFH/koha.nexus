"""Installing Koha and the first-access credentials, as panel screens.

  install_koha  system check (report) -> ports in use -> start? -> timezone
                (detected one, or region and city) -> an existing instance:
                erase it? + type REINSTALL -> the installation under Pac-Man
                (cannot be cancelled halfway; stages in the loader) ->
                addresses and passwords -> report if the final check
                complained -> reboot now or later
  credentials   addresses, SSH and database user/password, each with Copy
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, CredentialsScreen, InputScreen, MessageScreen, TextScreen
from .common import failed, run_task, show_done, show_failure, tx

INSTALL_STEPS = 18   # tui_run steps of function_install_koha (some are optional)


def _num(out, key: str) -> int:
    value = out.get(key, "0")
    return int(value) if value.isdigit() else 0


def credential_groups(out) -> list[tuple[str, list[tuple[str, str]]]]:
    """`@@result cred=GROUP<TAB>LABEL<TAB>VALUE` lines, grouped in order."""
    groups: list[tuple[str, list[tuple[str, str]]]] = []
    for line in out.lists.get("cred", []):
        group, _, rest = line.partition("\t")
        label, _, value = rest.partition("\t")
        if not groups or groups[-1][0] != group:
            groups.append((group, []))
        groups[-1][1].append((label, value))
    return groups


def _failed_reasons(report: str, limit: int = 4) -> str:
    return "\n".join([line[2:].strip() for line in report.splitlines() if line.startswith("❌")][:limit])


async def _choose_timezone(app, detected: str) -> str:
    """The detected zone, or one picked by region and city ("" keeps it)."""
    if await app.push_screen_wait(ConfirmScreen(
            t("Timezone Configuration"),
            tx("Detected system timezone: ${detected_tz}\n\nDo you want to use this timezone?", detected_tz=detected))):
        return detected
    zones = (await app.bridge.task("timezones")).lists.get("tz", [])
    regions = sorted({z.split("/", 1)[0] for z in zones if z})
    while True:
        region = await app.push_screen_wait(ChoiceScreen(
            t("Global Timezone Selection"), t("Select your region/continent:"), [(r, r) for r in regions]))
        if not region:
            return ""
        if region == "UTC":
            return "UTC"
        cities = sorted(z.split("/", 1)[1] for z in zones if z.startswith(region + "/"))
        if not cities:
            continue
        city = await app.push_screen_wait(ChoiceScreen(
            t("Global Timezone Selection"), t("Select the closest city/timezone:"), [(c, c) for c in cities]))
        if city:
            return f"{region}/{city}"


async def install_koha(app) -> None:
    title = t("Install Koha server")
    check = await run_task(app, t("Checking the system"), "install-check")
    if failed(check):
        await show_failure(app, title, check)
        return
    out = check.value
    report = out.previews[-1][1] if out.previews else ""

    if _num(out, "v_fail"):
        text = tx("System does not meet minimum requirements (%s critical error).\n\nReason(s):\n%s\n\n"
                  "Do you want to open the full report for more details?")
        text = "\n\n".join(text.split("\n\n")[:-1])  # the question is the report below
        body = text.replace("%s", str(_num(out, "v_fail")), 1).replace("%s", _failed_reasons(report), 1)
        await app.push_screen_wait(MessageScreen(t("Pre-validation Failed"), body, kind="error"))
        await app.push_screen_wait(TextScreen(t("Diagnostic Report"), report, kind="error"))
        return

    if out.get("busy_ports").strip():
        question = "\n\n".join([t("The following ports required by Koha are currently in use:"),
                                out.get("port_info").rstrip("\n"),
                                t("Do you want to stop the occupying services to free the ports automatically?")])
        if await app.push_screen_wait(ConfirmScreen(t("Occupied Ports Detected"), question)):
            freed = await run_task(app, t("Occupied Ports Detected"), "install-free-ports")
            if failed(freed):
                await show_failure(app, title, freed)
                return

    welcome = "\n\n".join([
        t("This project democratizes collection management, automating the setup of a robust, fast and free "
          "infrastructure for libraries."),
        t("The wizard will install and tune MariaDB, Apache, Memcached and Koha."),
        t("Estimated time: 10 to 30 minutes.") + "\n" + t("Please do not close the terminal during installation."),
        f"{t('No critical errors.')}  {t('OK')}: {_num(out, 'v_ok')}   {t('Warnings')}: {_num(out, 'v_warn')}",
        t("Start the installation now?"),
    ])
    if not await app.push_screen_wait(ConfirmScreen(t("Welcome to Koha Easy Installer!"), welcome,
                                                    preview=report, preview_title=t("Diagnostic Report"))):
        return

    tz = await _choose_timezone(app, out.get("tz", "UTC"))

    env = {"KEI_TASK_TZ": tz}
    if out.get("exists") == "yes":
        if not await app.push_screen_wait(ConfirmScreen(t("Instance already exists"), tx(
                "A Koha installation already exists on this machine.\n\nREINSTALLING DELETES the ${DB_NAME} "
                "database and all configuration.\nThis CANNOT be undone by this script.\n\n"
                "Continue to the final confirmation?", DB_NAME=out.get("db_name")), danger=True)):
            return
        word = await app.push_screen_wait(InputScreen(
            t("FINAL CONFIRMATION"), tx("Type exactly the word below to erase everything:\n\nREINSTALL"), "",
            validate=lambda v: "" if v == "REINSTALL" else t("Wrong confirmation. Nothing was deleted.")))
        if word != "REINSTALL":
            return
        env["KEI_TASK_REINSTALL"] = word

    result = await run_task(app, title, "install", env=env, total_steps=INSTALL_STEPS, cancellable=False)
    if failed(result):
        await show_failure(app, title, result)
        return
    done = result.value
    fails, warns = _num(done, "v_fail"), _num(done, "v_warn")
    head = t("Your library is ready!") if not fails else \
        t("Koha was installed, but the final check found ${fails} problem(s).", fails=fails)
    await app.push_screen_wait(CredentialsScreen(head, t("Open these addresses in the browser:"),
                                                 credential_groups(done), kind="error" if fails else "ok"))

    if fails or warns:
        if fails:
            question = tx("Final validation found issues (Failures: $V_FAIL | Warnings: $V_WARN).\n\n"
                          "Do you want to see the detailed report now to know what failed?",
                          V_FAIL=fails, V_WARN=warns)
        else:
            question = tx("Final validation completed with notices (Failures: 0 | Warnings: $V_WARN).\n\n"
                          "Do you want to see the detailed report now?", V_WARN=warns)
        if await app.push_screen_wait(ConfirmScreen(t("View Diagnostics"), question)):
            rep = await app.bridge.task("validation-report")
            if rep.previews:
                await app.push_screen_wait(TextScreen(t("Diagnostic Report"), rep.previews[-1][1]))

    if done.get("can_reboot") != "yes":
        await app.push_screen_wait(MessageScreen(t("Koha is ready"), tx(
            "All set! Koha services were restarted.\n\nCredentials have been saved to /root/koha_credentials.txt.")))
        return
    if await app.push_screen_wait(ConfirmScreen(t("Reboot Server (Recommended)"), tx(
            "To enable full Plack speed, initialize SWAP, and ensure peak catalog performance, rebooting the "
            "system now is strongly recommended.\n\nCredentials have been saved to /root/koha_credentials.txt.\n\n"
            "Do you want to reboot the server immediately?"))):
        await show_done(app, t("Reboot Server (Recommended)"),
                        await run_task(app, t("Rebooting in 5 seconds to consolidate services..."), "reboot",
                                       cancellable=False))
    else:
        await app.push_screen_wait(MessageScreen(t("Pending Reboot"), tx(
            "All set! You chose to reboot later.\n\nRemember: if the catalog feels sluggish, restart the server "
            "via option 16 in the panel before heavy indexing."), kind="info"))


async def credentials(app) -> None:
    title = t("Access Credentials")
    result = await run_task(app, title, "credentials")
    if failed(result):
        await show_failure(app, title, result)
        return
    await app.push_screen_wait(CredentialsScreen(title, "", credential_groups(result.value)))
