"""Administrative access of each platform (Paulo, 2026-11-06), one card in
the platform's group.

Koha: whether the web installer was finished (a superlibrarian exists),
the first-access credentials, creating a superlibrarian (the routine of
before) and a new password for a superlibrarian (through Koha itself: the
rules of its category). Tainacan: whether the account made at the
installation still has the generated password, setting one's own, a new
password for an administrator and one more administrator.

A password is typed twice in a protected field, confirmed, and goes to the
installer in the environment of that one task (KEI_ADMIN_PASSWORD), which
hands it to Koha or WordPress on standard input: never on a command line,
in a log, in a result or on a screen afterwards. Nothing is created,
removed or changed without the person choosing that account; the keys of
Koha and WordPress are never touched.
"""

from __future__ import annotations

import re

from ..bridge import TaskOutcome
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from .common import run_task, show_done, show_failure

MIN_LENGTH = 10                       # the installer's KEI_ADMIN_MIN
USER_RE = re.compile(r"^[A-Za-z0-9._@-]{1,60}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAMES = {"koha": "Koha", "tainacan": "Tainacan"}


def _ok(result) -> bool:
    out = result.value if isinstance(result.value, TaskOutcome) else None
    return bool(out is not None and out.ok and not getattr(result, "cancelled", False))


class Admins:
    """What admin-status said: never a password."""

    def __init__(self, out: TaskOutcome | None):
        r = out.results if out else {}
        self.state = r.get("state", "")
        self.initial = r.get("initial", "")
        self.admins = [a for a in (out.lists.get("admin", []) if out else []) if USER_RE.match(a)]


async def read_admins(app, platform: str) -> Admins | None:
    result = await run_task(app, t("Reading the administrators"), "admin-status", platform, cancellable=False)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    if out is None or not out.ok or result.cancelled:
        await show_failure(app, t("🔐  Administrative access"), result)
        return None
    return Admins(out)


def describe(platform: str, admins: Admins) -> str:
    if platform == "koha":
        if admins.state == "web-installer":
            return t("Koha has no superlibrarian yet: the web installer was not finished. Open the staff "
                     "interface with the first-access credentials and finish it, or create a superlibrarian here.")
        return t("Superlibrarians: ${names}.", names=", ".join(admins.admins) or "-")
    text = t("Administrators: ${names}.", names=", ".join(admins.admins) or "-")
    if admins.state == "initial":
        text = t("The initial account (${name}) still has the password generated at the installation. Set your "
                 "own password: the generated one then stops working and is no longer kept.",
                 name=admins.initial) + "\n\n" + text
    return text


async def ask_password(app, title: str, user: str) -> str | None:
    """Typed twice, in protected fields; None when cancelled."""
    def long_enough(value: str) -> str:
        return "" if len(value) >= MIN_LENGTH else t("At least ${n} characters.", n=MIN_LENGTH)

    first = await app.push_screen_wait(InputScreen(
        title, t("The new password of ${user}. It is not stored by the panel and is not shown again: keep it "
                 "safe.", user=user), t("New password (at least ${n} characters):", n=MIN_LENGTH),
        validate=long_enough, password=True))
    if not first:
        return None
    again = await app.push_screen_wait(InputScreen(title, "", t("Type the password again:"), password=True))
    if again is None:
        return None
    if again != first:
        await app.push_screen_wait(MessageScreen(title, t("The passwords do not match. Nothing was changed."),
                                                 kind="error"))
        return None
    return first


async def change_password(app, platform: str, user: str) -> bool:
    title = t("🔐  Administrative access")
    password = await ask_password(app, title, user)
    if password is None:
        return False
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "Change the password of ${user} (${platform})? Only this account changes; the other accounts and "
            "the keys of the site are not touched.", user=user, platform=NAMES[platform]))):
        return False
    result = await run_task(app, t("Changing the password"), "admin-password", platform, user,
                            env={"KEI_ADMIN_PASSWORD": password}, cancellable=False)
    password = ""
    await show_done(app, title, result, t("Password changed."))
    return _ok(result)


async def create_admin(app) -> bool:
    """One more WordPress administrator (Tainacan)."""
    title = t("🔐  Administrative access")
    user = await app.push_screen_wait(InputScreen(
        title, t("A new administrator of Tainacan. A name or e-mail that already belongs to an account is "
                 "refused: no account is recreated or changed."), t("User name:"),
        validate=lambda v: "" if USER_RE.match(v or "") else t("Letters, digits, dot, @, hyphen or underscore.")))
    if not user:
        return False
    email = await app.push_screen_wait(InputScreen(
        title, "", t("E-mail:"), validate=lambda v: "" if EMAIL_RE.match(v or "") else t("Invalid e-mail address.")))
    if not email:
        return False
    password = await ask_password(app, title, user)
    if password is None:
        return False
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "Create the administrator ${user} (${email}) in Tainacan?", user=user, email=email))):
        return False
    result = await run_task(app, t("Creating the administrator"), "admin-create", "tainacan", user, email,
                            env={"KEI_ADMIN_PASSWORD": password}, cancellable=False)
    password = ""
    await show_done(app, title, result, t("Administrator created."))
    return _ok(result)


async def admin_access(app, platform: str) -> bool:
    """The card's flow; True when something was set (for the assistant)."""
    from . import ROUTINES
    title = t("🔐  Administrative access")
    admins = await read_admins(app, platform)
    if admins is None:
        return False
    options: list[tuple[str, str]] = []
    if platform == "koha":
        if admins.admins:
            options.append(("reset", t("Change the password of a superlibrarian")))
        options.append(("create", t("Create a superlibrarian")))
        options.append(("credentials", t("View the first-access credentials")))
    else:
        if admins.state == "initial":
            options.append(("own", t("Set my password for ${name}", name=admins.initial)))
        if admins.admins:
            options.append(("reset", t("Change the password of an administrator")))
        options.append(("create", t("Create another administrator")))
    choice = await app.push_screen_wait(ChoiceScreen(title, describe(platform, admins), options))
    if choice is None:
        return False
    if choice == "own":
        return await change_password(app, platform, admins.initial)
    if choice == "reset":
        user = admins.admins[0] if len(admins.admins) == 1 else await app.push_screen_wait(
            ChoiceScreen(title, t("Which account?"), [(a, a) for a in admins.admins]))
        return bool(user) and await change_password(app, platform, user)
    if choice == "create" and platform == "tainacan":
        return await create_admin(app)
    if choice == "create":
        await ROUTINES["superlibrarian"](app)
        return True
    if choice == "credentials":
        await ROUTINES["credentials"](app)
    return False


async def koha_admin(app) -> None:
    await admin_access(app, "koha")


async def tainacan_admin(app) -> None:
    await admin_access(app, "tainacan")
