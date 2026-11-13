"""Removing Koha (U11, study 17.3), from Platforms > Remove instance.

Its own step, never a package uninstall. The plan is shown first: what
goes (the instance, its database, its sites, its scheduled tasks), what
stays (the packages, the other systems, the firewall, the tunnel, the
backups and the instance's files) and where the safety package goes.
After the Yes, the installer (kei_koha_remove) makes the joint package of
Koha alone, checks it and only then removes; without a complete package
that passed its check nothing goes. The scheduled tasks are moved aside,
not deleted. Koha comes back with a new installation of the same major
version and the Backup center's assisted restore.
"""

from __future__ import annotations

from ..bridge import TaskOutcome
from ..i18n import t

TITLE = "🗑  Remove Koha"
GO = {
    "instance": "The instance (koha-remove)",
    "database": "Its database and database user",
    "apache-site": "Its web site",
    "cron": "A scheduled task (moved aside, not deleted)",
}
KEEP = {
    "packages": "The packages (koha-common, MariaDB, Apache, Elasticsearch)",
    "firewall": "The firewall",
    "tunnel": "The tunnel and the free address",
    "backups": "The backups already made",
    "files": "The instance's files under /var/lib/koha",
}


def results(out) -> dict[str, list[str]]:
    return {k: [v for v in vs if v] for k, vs in out.lists.items()}


def first(r: dict[str, list[str]], key: str) -> str:
    return (r.get(key) or [""])[0]


def plan_rows(r: dict[str, list[str]]) -> list[tuple[str, str]]:
    """The review lines: what goes, what stays, the package."""
    rows: list[tuple[str, str]] = []
    for item in r.get("go", []):
        what, _s, where = item.partition("|")
        rows.append(("✗ " + t("Goes"), t(GO.get(what, what)) + ": " + where))
    for item in r.get("keep", []):
        rows.append(("✓ " + t("Stays"), t(KEEP.get(item, item))))
    others = first(r, "others")
    if others:
        rows.append(("✓ " + t("Stays"), t("The other systems: ${names}", names=", ".join(others.split()))))
    rows.append((t("Safety package"), first(r, "dest") or "-"))
    return rows


def recovery_note(r: dict[str, list[str]]) -> str:
    ver = first(r, "version")
    major = ".".join(ver.split(".")[:2]) if ver else ""
    return (t("To bring it back: install Koha again, the same major version (${version}), then Backup center > "
              "Assisted restore with this package.", version=major) if major else
            t("To bring it back: install Koha again, the same major version, then Backup center > Assisted "
              "restore with this package."))


async def koha_remove(app) -> None:
    from ..screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen
    from ..screens.install_flow import PlanSummaryScreen
    from ..tasks import TaskResult
    from .common import run_task, show_done, show_failure

    title = t(TITLE)
    plan = await app.bridge.task("koha-remove", "plan")
    if not isinstance(plan, TaskOutcome) or not plan.ok:
        await show_failure(app, title, TaskResult(ok=True, value=plan))
        return
    r = results(plan)
    extra: list[str] = []
    if first(r, "secrets") == "needs-choice":
        choice = await app.push_screen_wait(ChoiceScreen(title, t(
            "There is no backup key on this server, so Koha's secrets (its encryption key in koha-conf.xml, the "
            "SIP2 logins and the panel's logins) cannot go into the safety package: they never go in clear. "
            "Without them, what Koha encrypted cannot be read on another installation."), [
            ("key", t("Set up the backup key first (recommended)")),
            ("data", t("Make the package without Koha's secrets (data only)"))]))
        if choice is None:
            return
        if choice == "key":
            from . import ROUTINES
            await ROUTINES["pbackup-setup"](app)
            await app.push_screen_wait(MessageScreen(title, t(
                "Nothing of Koha was removed. With the backup key set up, open Remove instance again."),
                kind="info"))
            return
        extra = ["no-secrets"]
    name = first(r, "instance")
    if not await app.push_screen_wait(PlanSummaryScreen(
            t("${title} · Review", title=title), plan_rows(r),
            body=t("Before anything goes, a package of Koha (\"${name}\") is made and checked. Without a complete "
                   "package that passed its check, nothing is removed. Nothing was changed so far.", name=name),
            note=recovery_note(r), action=t("Remove Koha"), danger=True)):
        return
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "Remove Koha (\"${name}\") from this server now? The catalog and the staff stop answering.",
            name=name), danger=True)):
        return
    result = await run_task(app, title, "koha-remove", "apply", "keep", "confirm", *extra, cancellable=False)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    pkg = (out.lists.get("package") or [""])[0] if out else ""
    done = t("Koha was removed. The safety package is kept: ${file}", file=pkg) + "\n\n" + recovery_note(r)
    await show_done(app, title, result, done)
    app.check_platforms()
