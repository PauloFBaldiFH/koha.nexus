"""Koha settings and parameters, as panel screens.

  sizing            RAM profile (the recommended one highlighted) -> applied
                    behind Pac-Man, reverted if MariaDB does not start
  email             e-mail for the instance + what is left to do in Koha
  superlibrarian    login, card, password twice, names -> the new account
  interoperability  enable Z39.50 and SIP2? -> what is running
  clock             the detected timezone, or region and city -> applied
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..i18n import t
from .common import facts, run_interactive, run_task, show_done
from .install import _choose_timezone


async def sizing(app) -> None:
    await run_interactive(app, t("Sizing"), "sizing")


async def email(app) -> None:
    title = t("Email Setup")
    await show_done(app, title, await run_task(app, title, "email"))


async def superlibrarian(app) -> None:
    await run_interactive(app, t("👑  Create super librarian"), "superlibrarian")


async def interoperability(app) -> None:
    await run_interactive(app, t("SIP2 & Z39.50"), "interoperability")


async def clock(app) -> None:
    info = await facts(app)
    tz = await _choose_timezone(app, info.get("timezone", "UTC"))
    title = t("Timezone Configuration")
    await show_done(app, title, await run_task(app, title, "clock", env={"KEI_TASK_TZ": tz}))
