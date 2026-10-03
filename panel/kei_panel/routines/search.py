"""Search engine and indexing, as panel screens.

  toggle  Zebra <-> Elasticsearch: the routine's questions (switch? low
          disk?) are asked over its loader; the switch itself cannot be
          cancelled halfway -> result -> validation report
  repair  diagnostics + repair? + rebuild everything? (Elasticsearch) or
          unlock and rebuild (Zebra) -> result -> validation report
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from ..i18n import t
from .common import asker, offer_report, run_task, show_done

TOGGLE_STEPS = 9
REPAIR_STEPS = 3


async def toggle(app) -> None:
    title = t("Search Engine")
    result = await run_task(app, title, "search-toggle", ask=asker(app), total_steps=TOGGLE_STEPS,
                            cancellable=False)
    out = result.value
    if out is not None and out.asks and not out.steps:
        return          # "no" to the first question: nothing was done
    await show_done(app, title, result)
    await offer_report(app, result)


async def repair(app) -> None:
    title = t("Repairing the search index")
    result = await run_task(app, title, "search-repair", ask=asker(app), total_steps=REPAIR_STEPS,
                            cancellable=False)
    out = result.value
    if out is not None and out.asks and not out.steps:
        return
    await show_done(app, title, result)
    await offer_report(app, result)
