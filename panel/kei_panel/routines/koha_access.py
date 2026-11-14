"""Koha with one port or two (U10, study 16.1), from Addresses and access.

Two ports (the default): the catalog on 80 and the staff on 8080, both by
this server's IP, with no names to set up. One port: the staff also
answers by name on 80 (admin.<domain>); both names must point to this
server, which the plan checks and only warns about. 8080 stays as the way
in from this server. The installer (kei_koha_access) applies it through
the same safe Apache site routine as the other platforms (configtest, the
other sites unchanged, rollback); nothing changes before the person's Yes.
"""

from __future__ import annotations

import re

from ..bridge import TaskOutcome
from ..i18n import t

TITLE = "🔀  One port or two"
DOMAIN = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]([a-z0-9-]{0,61}[a-z0-9])?$")
POINTS = {
    "here": "✓ points to this server",
    "elsewhere": "⚠ points to another address (right only if it is your router's public address)",
    "none": "⚠ does not point anywhere yet",
}
NETS = {"local": "Only the local networks (as the staff firewall)", "all": "Anyone who reaches this server"}
# Koha's own addresses (OPACBaseURL, staffClientBaseURL), in the review.
BASES = {"opac": "Koha's catalog address (OPACBaseURL)", "staff": "Koha's staff address (staffClientBaseURL)"}


def domain_error(value: str) -> str:
    """"" for a domain the installer takes, else what to fix."""
    v = (value or "").strip().lower()
    if not DOMAIN.match(v) or len(v) > 190 or v.startswith("admin."):
        return t("Type the institution's domain, for example biblioteca.org.br (no http://, no path).")
    return ""


def results(out) -> dict[str, list[str]]:
    """Every @@result of the task, by key (points repeats)."""
    return {k: [v for v in vs if v] for k, vs in out.lists.items()}


def plan_rows(r: dict[str, list[str]]) -> list[tuple[str, str]]:
    """The review lines of a plan."""
    one = (r.get("mode") or [""])[0] == "one"
    rows = [(t("Catalog"), (r.get("opac") or ["-"])[0]), (t("Staff"), (r.get("staff") or ["-"])[0])]
    if one:
        rows.append((t("Staff on this server"), (r.get("recovery") or ["-"])[0]))
        net = (r.get("staff_net") or [""])[0]
        rows.append((t("Who may open the staff by name"), t(NETS.get(net, NETS["all"]))))
        for p in r.get("points", []):
            name, _s, state = p.partition("|")
            rows.append((name, t(POINTS.get(state, POINTS["none"]))))
    for b in r.get("base", []):
        key, now, nxt, state = (b.split("|") + ["", "", "", ""])[:4]
        if key in BASES:
            rows.append((t(BASES[key]), base_text(now, nxt, state)))
    return rows


def base_text(now: str, nxt: str, state: str) -> str:
    """One of Koha's own addresses: what happens to it."""
    empty = t("(empty)")
    if state == "change":
        return f"{now or empty} → {nxt}"
    if state == "keep":
        return t("Kept: ${url} (another public name, as the tunnel's)", url=now)
    if state == "restore":
        return t("Back to what it was: ${url}", url=nxt or empty)
    return t("Unchanged: ${url}", url=now or empty)


def failed_bases(out) -> list[str]:
    return [v for v in (out.lists.get("base_failed") or []) if v] if isinstance(out, TaskOutcome) else []


async def choose(app, title: str, mode_now: str = "two", domain_now: str = "") -> tuple[str, str] | None:
    """Two ports or one, and the domain for one; None = cancelled."""
    from ..screens.dialogs import ChoiceScreen, InputScreen

    mode = await app.push_screen_wait(ChoiceScreen(
        title, t("How will people open the catalog and the staff area?"),
        [("two", t("Two ports (recommended): the catalog by this server's IP, the staff on port 8080")),
         ("one", t("One port, with names: the staff at admin.<your domain>"))],
        note=t("Two ports works by IP, with no names to set up in the network. One port needs a domain whose two "
               "names point to this server (DNS or tunnel); by IP only the catalog opens."),
        default=mode_now))
    if mode is None:
        return None
    domain = ""
    if mode == "one":
        domain = await app.push_screen_wait(InputScreen(
            title, t("The catalog will open at the domain and the staff at admin. followed by it. Both names "
                     "must point to this server. Koha's own site stays as it is; port 8080 keeps working."),
            t("Institution's domain:"), validate=domain_error, value=domain_now))
        if not domain:
            return None
        domain = domain.strip().lower()
    return mode, domain


def unpointed(r: dict[str, list[str]]) -> list[str]:
    return [p.partition("|")[0] for p in r.get("points", []) if p.partition("|")[2] != "here"]


async def koha_access(app) -> None:
    from ..screens.dialogs import MessageScreen
    from ..screens.install_flow import PlanSummaryScreen
    from .common import run_task, show_done, show_failure

    title = t(TITLE)
    now = await app.bridge.task("koha-access", "status")
    if not isinstance(now, TaskOutcome) or not now.ok:
        await app.push_screen_wait(MessageScreen(title, t(
            "The current choice could not be read. Update this panel and try again."), kind="error"))
        return
    cur = results(now)
    mode_now = (cur.get("mode") or ["two"])[0]
    domain_now = (cur.get("domain") or [""])[0]
    picked = await choose(app, title, mode_now, domain_now)
    if picked is None:
        return
    mode, domain = picked
    if mode == mode_now and domain == domain_now:
        await app.push_screen_wait(MessageScreen(title, t("This is already how Koha is opened: nothing to change."),
                                                 kind="info"))
        return
    plan = await app.bridge.task("koha-access", "plan", mode, *([domain] if domain else []))
    if not isinstance(plan, TaskOutcome) or not plan.ok:
        from ..tasks import TaskResult
        await show_failure(app, title, TaskResult(ok=True, value=plan))
        return
    r = results(plan)
    note = ""
    if mode == "one" and unpointed(r):
        note = t("Not every name points here yet. You can go on: the names start working once the DNS or the "
                 "tunnel points them to this server.")
    if not await app.push_screen_wait(PlanSummaryScreen(
            t("${title} · Review", title=title), plan_rows(r),
            body=t("Nothing was changed so far."), note=note, action=t("Apply"))):
        return
    result = await run_task(app, title, "koha-access", "apply", mode, *([domain] if domain else []), "confirm")
    done = t("Done. Use Test access to check each address.")
    bad = failed_bases(result.value)
    if bad:
        done += "\n\n" + t("⚠ Koha's own address could not be changed (${names}). Set it in Koha: Administration > "
                            "System preferences.", names=", ".join(bad))
    await show_done(app, title, result, done)
