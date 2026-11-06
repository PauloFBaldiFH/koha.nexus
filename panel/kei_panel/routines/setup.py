"""The steps after a new installation (Paulo, 2026-11-06): administrative
access, public access, backup, then where everything lives.

The assistant has no settings of its own: each step opens the routine of
the screen it belongs to (the platform's Administrative access, Cloudflare
in Security & access or Tainacan's address, the backups of the Backup
center), which reads what already exists before proposing anything. "Do it
later" only records the step as postponed; the menus keep offering
everything, before and after the assistant. The installer keeps, per step,
done, later or pending (never a setting) and counts a step as done as soon
as the real state says so, whichever screen configured it. Only a new
installation starts it: an update of the panel never does.
"""

from __future__ import annotations

from ..bridge import TaskOutcome
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, MessageScreen

STEPS = ("admin", "public", "backup")
NAMES = {"koha": "Koha", "tainacan": "Tainacan"}
STATES = ("done", "later", "pending")


class Setup:
    """What setup-status said."""

    def __init__(self, out: TaskOutcome | None):
        r = out.results if out else {}
        self.open = r.get("setup") == "open"
        self.steps: dict[str, tuple[str, str]] = {}
        for line in (out.lists.get("step", []) if out else []):
            step, _sep, rest = line.partition("|")
            state, _sep, what = rest.partition("|")
            if step in STEPS:
                self.steps[step] = (state if state in STATES else "pending", what)
        try:
            self.pending = int(r.get("pending", "0"))
        except ValueError:
            self.pending = 0

    def state(self, step: str) -> str:
        return self.steps.get(step, ("pending", ""))[0]

    def what(self, step: str) -> str:
        return self.steps.get(step, ("pending", ""))[1]


async def read_setup(app, platform: str, quick: bool = False) -> Setup | None:
    """None when the installer in use has no such task or did not answer."""
    if not app.bridge.has_task("setup-status"):
        return None
    try:
        out = await app.bridge.task("setup-status", platform, *(["quick"] if quick else []))
    except Exception:  # noqa: BLE001 - the card then is not drawn
        return None
    return Setup(out) if out.ok else None


def step_label(platform: str, step: str) -> str:
    return {
        "admin": t("Administrative access"),
        "public": t("Public access"),
        "backup": t("Backup and cloud"),
    }[step]


def step_text(platform: str, step: str) -> str:
    """What the step does and where it stays in the menu."""
    if step == "admin":
        if platform == "koha":
            return t("Who manages Koha: finish the web installer or create a superlibrarian, or change the "
                     "password of one. Always in Koha > Administrative access.")
        return t("The account made at the installation has a generated password: set your own, or create "
                 "another administrator. Always in Tainacan > Administrative access.")
    if step == "public":
        if platform == "koha":
            return t("How people outside this network reach the catalogue: a Cloudflare tunnel with your own "
                     "domain or a free koha.nexus address. Always in Security & access hub > Cloudflare Tunnel Manager.")
        return t("The address of the collection: this server on the local network, or your own domain. "
                 "Always in Tainacan > Tainacan address.")
    if platform == "koha":
        return t("Koha already makes a local backup every night. Here, a copy in the cloud with its own "
                 "frequency and retention. Always in the Backup center.")
    return t("Encrypted backups of Tainacan: the key and its recovery phrase, then a daily backup with "
             "maintenance and a monthly restore test. Always in the Backup center.")


def overview(platform: str, setup: Setup) -> str:
    marks = {"done": "✓", "later": "…", "pending": "○"}
    words = {"done": t("done"), "later": t("for later"), "pending": t("to do")}
    lines = []
    for i, step in enumerate(STEPS, 1):
        state, what = setup.state(step), setup.what(step)
        line = f"{marks[state]} {i}  {step_label(platform, step)}: {words[state]}"
        lines.append(line + (f" ({what})" if what else ""))
    lines.append(f"  4  {t('Next steps and links')}")
    return "\n".join(lines)


async def run_step(app, platform: str, step: str) -> None:
    """The routine of the screen the step belongs to."""
    from . import ROUTINES
    from .admin_access import admin_access
    from .platforms import backup_state

    if step == "admin":
        await admin_access(app, platform)
    elif step == "public":
        await ROUTINES["cloudflare" if platform == "koha" else "tainacan-address"](app)
    elif platform == "koha":
        await ROUTINES["backup-cloud"](app)
    else:
        state = await backup_state(app)
        if state.known and not state.key:
            await ROUTINES["pbackup-setup"](app)
            state = await backup_state(app)
            if not state.key:
                return
        await ROUTINES["pbackup-schedule"](app)


def links(platform: str) -> str:
    if platform == "koha":
        return t("Where everything is, at any time:\n"
                 "• addresses and state: Control Dashboard, Koha tab;\n"
                 "• administrators and first-access credentials: Koha > Administrative access;\n"
                 "• public address: Security & access hub > Cloudflare Tunnel Manager;\n"
                 "• backups, cloud and restore: Backup center (key b);\n"
                 "• every scheduled job: Schedules (key s).\n"
                 "Each of them can be checked, changed or turned off there, with its own confirmations.")
    return t("Where everything is, at any time:\n"
             "• addresses and state: Control Dashboard, Tainacan tab;\n"
             "• administrators: Tainacan > Administrative access;\n"
             "• address of the collection: Tainacan > Tainacan address;\n"
             "• backups, cloud and restore: Backup center (key b);\n"
             "• every scheduled job: Schedules (key s).\n"
             "Each of them can be checked, changed or turned off there, with its own confirmations.")


async def mark(app, platform: str, step: str, state: str) -> None:
    try:
        await app.bridge.task("setup-mark", platform, step, state)
    except Exception:  # noqa: BLE001 - the step stays as it was; nothing else depends on it
        pass


async def assistant(app, platform: str) -> None:
    """Steps 1 to 3, each "Set up now" or "Do it later", then the links."""
    title = t("Next steps: ${name}", name=NAMES[platform])
    setup = await read_setup(app, platform)
    if setup is None or not setup.open:
        await app.push_screen_wait(MessageScreen(title, t(
            "There is no setup in progress for ${name}: everything is in the menus as usual.",
            name=NAMES[platform])))
        return
    for i, step in enumerate(STEPS, 1):
        if setup.state(step) == "done":
            continue
        head = t("Step ${n} of 4: ${step}", n=i, step=step_label(platform, step))
        choice = await app.push_screen_wait(ChoiceScreen(
            title, overview(platform, setup) + "\n\n" + head + "\n" + step_text(platform, step),
            [("now", t("Set up now")), ("later", t("Do it later"))]))
        if choice is None:
            # Closed: nothing is recorded; "Continue the setup" stays.
            return
        if choice == "later":
            await mark(app, platform, step, "later")
        else:
            await run_step(app, platform, step)
        setup = await read_setup(app, platform) or setup
    await finish(app, platform, title, setup)


async def finish(app, platform: str, title: str, setup: Setup) -> None:
    """Step 4; then, with steps left for later, whether the reminder stays."""
    await app.push_screen_wait(MessageScreen(title, overview(platform, setup) + "\n\n" + links(platform)))
    if setup.pending == 0:
        await close(app, platform)
        return
    keep = await app.push_screen_wait(ChoiceScreen(title, t(
        "Some steps were left for later. The platform's screen can keep a \"Continue the setup\" card until "
        "they are done; the menus offer them either way."),
        [("keep", t("Keep the reminder")), ("close", t("Do not remind me again"))]))
    if keep == "close":
        await close(app, platform)


async def close(app, platform: str) -> None:
    try:
        await app.bridge.task("setup-close", platform)
    except Exception:  # noqa: BLE001 - the card then stays; closing again works
        pass


async def maybe_start(app, platform: str) -> None:
    """After an installation from the panel: the assistant, only when the
    installer started one (a new installation)."""
    setup = await read_setup(app, platform, quick=True)
    if setup is not None and setup.open and setup.pending:
        await assistant(app, platform)


async def koha_setup(app) -> None:
    await assistant(app, "koha")


async def tainacan_setup(app) -> None:
    await assistant(app, "tainacan")
