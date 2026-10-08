"""Security center, as panel screens.

  fail2ban        the jails' status (or why there is none: WSL, not installed)
  ufw             the firewall rules
  staff_firewall  block port 8080 from the internet, or open it -> result
  rotate_password confirm -> new password under Pac-Man -> the password,
                  with a Copy button
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..i18n import t
from ..screens.dialogs import ChoiceScreen, MessageScreen, TextScreen
from .common import asker, failed, last_message, run_task, show_done, tx


async def _show_text(app, title: str, name: str) -> None:
    result = await run_task(app, title, name)
    out = result.value
    if not failed(result) and out.previews:
        head, text = out.previews[-1]
        await app.push_screen_wait(TextScreen(head or title, text))
    else:
        await show_done(app, title, result)


async def fail2ban(app) -> None:
    await _show_text(app, t("🚨 Fail2ban"), "fail2ban")


async def ufw(app) -> None:
    await _show_text(app, t("🧱 UFW"), "ufw")


async def staff_firewall(app) -> None:
    title = t("Staff firewall")
    question = tx("Port 80 (OPAC) must stay open to the public.\nPort 8080 (staff) can be closed to the internet if "
                  "you use\nCloudflare Tunnel or only access it from the local network.\n\n"
                  "BLOCK direct external access to 8080?")
    choice = await app.push_screen_wait(ChoiceScreen(title, question, [
        ("block", t("Port 8080 now allowed only from 127.0.0.1 and the local network.")),
        ("open", t("Port 8080 is open."))]))
    if not choice:
        return
    answer = "yes" if choice == "block" else "no"
    await show_done(app, title, await run_task(app, title, "staff-firewall", env={"KEI_TASK_ANSWER": answer}))


async def rotate_password(app) -> None:
    title = t("Rotate Password")
    result = await run_task(app, title, "rotate-db-password", ask=asker(app, danger=(title,)), cancellable=False)
    out = result.value
    if out is not None and out.asks and not out.messages:
        return          # "no": nothing was changed
    password = out.get("password") if out is not None else ""
    if not password:            # nothing was changed
        await show_done(app, title, result)
        return
    # The new password is in force (even when Koha did not answer the test).
    error = out.last("error")
    kind, head, body = ("error", error[1], error[2]) if error else last_message(out)
    await app.push_screen_wait(MessageScreen(head if head and head != "OK" else title, body, kind=kind,
                                             command=password, is_command=False))
