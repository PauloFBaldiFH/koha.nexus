"""Pieces every ported routine uses."""

from __future__ import annotations

from ..bridge import TaskOutcome, unescape
from ..i18n import t
from ..screens.dialogs import MessageScreen
from ..screens.loading import LoadingScreen
from ..tasks import TaskResult, task_job


def tx(src: str, **values: object) -> str:
    """t() for an installer text written here with real new lines: the
    installer's key has a literal \\n there (whiptail reads it so)."""
    return unescape(t(src.replace("\n", "\\n"), **values))


async def facts(app) -> TaskOutcome:
    """`--task info`: paths and the newest backup (fast, no loader)."""
    return await app.bridge.task("info")


async def run_task(app, title: str, name: str, *args: str, cancellable: bool = True,
                   **kwargs) -> TaskResult:
    """The routine's work behind Pac-Man; returns when the loader closes."""
    return await app.push_screen_wait(
        LoadingScreen(title, task_job(app.bridge, name, *args, **kwargs), cancellable=cancellable))


def failed(result: TaskResult) -> bool:
    """True (after telling the person) when the task did not do its job."""
    out = result.value if isinstance(result.value, TaskOutcome) else None
    if result.ok and out and out.ok:
        return False
    return True


async def show_failure(app, title: str, result: TaskResult) -> None:
    if result.cancelled:
        app.notify(f"{title}: {t('Cancelled')}", severity="warning")
        return
    out = result.value if isinstance(result.value, TaskOutcome) else None
    msg = out.last("error") if out else None
    body = msg[2] if msg else (result.error or (f"exit {out.rc}" if out else t("Unknown error.")))
    head = msg[1] if msg and msg[1] else title
    await app.push_screen_wait(MessageScreen(head, body, kind="error", log=result.log))


def last_message(out: TaskOutcome, default: str = "") -> tuple[str, str, str]:
    return out.last("ok", "info") or ("ok", "", default)
