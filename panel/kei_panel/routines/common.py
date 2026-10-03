"""Pieces every ported routine uses."""

from __future__ import annotations

from ..bridge import TaskOutcome, unescape
from ..i18n import t
from ..screens.dialogs import ConfirmScreen, MessageScreen
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


async def show_done(app, title: str, result: TaskResult, default: str = "") -> None:
    """The routine's own last box (ok or info), or its failure."""
    if failed(result):
        await show_failure(app, title, result)
        return
    kind, head, body = last_message(result.value, default or t("Done!"))
    await app.push_screen_wait(MessageScreen(head if head and head != "OK" else title, body, kind=kind))


async def preview_then_run(app, title: str, loader_title: str, name: str, *args: str,
                           total_steps: int = 0, danger: bool = False) -> None:
    """A routine that shows a preview and asks before changing anything:
    run once with KEI_TASK_ANSWER=no (the dry run stops at its question),
    show the preview and the question, then run again with yes."""
    dry = await run_task(app, loader_title, name, *args, env={"KEI_TASK_ANSWER": "no"})
    if failed(dry):
        await show_failure(app, title, dry)
        return
    out = dry.value
    if not out.asks:
        # Nothing to ask (e.g. "not installed, nothing was changed").
        await show_done(app, title, dry)
        return
    ask_title, question = out.asks[-1]
    preview_title, preview = out.previews[-1] if out.previews else ("", "")
    if not await app.push_screen_wait(ConfirmScreen(ask_title or title, question, danger=danger,
                                                    preview=preview, preview_title=preview_title)):
        return
    result = await run_task(app, loader_title, name, *args, env={"KEI_TASK_ANSWER": "yes"},
                            total_steps=total_steps)
    await show_done(app, title, result)


def asker(app, danger: tuple[str, ...] = ()):
    """The questions of an interactive routine, asked over its loader while
    it waits. An info box it showed just before the question (diagnostics)
    is shown above it; its "View Report" question is answered yes silently,
    so the report comes back as a preview that offer_report() shows later."""
    shown: set[int] = set()

    async def ask(out: TaskOutcome, title: str, text: str) -> bool:
        if title == t("View Report"):
            return True
        preview_title = preview = ""
        for i, (kind, head, body) in enumerate(out.messages):
            if kind == "info" and i not in shown:
                shown.add(i)
                preview_title, preview = head, body
        return await app.push_screen_wait(ConfirmScreen(title, text, danger=title in danger,
                                                        preview=preview, preview_title=preview_title))
    return ask


async def offer_report(app, result: TaskResult) -> None:
    """The validation report a routine produced, if the person wants it."""
    from ..screens.dialogs import TextScreen
    out = result.value if isinstance(result.value, TaskOutcome) else None
    if not out or not out.previews:
        return
    title, report = out.previews[-1]
    question = tx("Do you want to see the detailed system validation report now?") if out.ok else \
        tx("Do you want to see the validation report to investigate the issues now?")
    if await app.push_screen_wait(ConfirmScreen(t("View Report"), question)):
        await app.push_screen_wait(TextScreen(title or t("Diagnostic Report"), report))
