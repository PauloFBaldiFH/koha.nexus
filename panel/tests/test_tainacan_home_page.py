"""The panel's cards for Tainacan's public home page and for starting a
stopped Tainacan (installer: --task tainacan-site, tainacan-start): the
plan first, a Yes, then the change; a "No" changes nothing."""

import asyncio

import pytest

from kei_panel import platforms
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv


@pytest.fixture(autouse=True)
def tainacan_only(monkeypatch):
    monkeypatch.setenv("KEI_PANEL_DEMO_KOHA", "0")
    monkeypatch.setenv("KEI_PANEL_DEMO_TAINACAN", "1")


def make_app(patch=None, checked=None, ran=None):
    app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
    real_task, real_status = app.bridge.task, app.bridge.status

    async def task(name, *args, **kwargs):
        if ran is not None:
            ran.append((name, args))
        return await real_task(name, *args, **kwargs)

    async def status(*args, **kwargs):
        st = dict(await real_status(*args, **kwargs))
        st["platforms"] = [p if p["id"] != "tainacan" else
                           {**p, **(patch or {}), "checked": {**p["checked"], **(checked or {})}}
                           for p in st["platforms"]]
        return st
    app.bridge.task, app.bridge.status = task, status
    return app


async def open_view(app, pilot, section):
    await pilot.pause(0.3)
    app.screen.query_one("#sidebar").blur()
    app.screen.action_show(section)
    await pilot.pause(2.0)
    from textual.widgets import ContentSwitcher
    switcher = app.screen.query_one("#views", ContentSwitcher)
    return switcher.query_one(f"#{switcher.current}")


def shown(view):
    from kei_panel.widgets.cards import ActionCard
    return [c.entry.action for c in view.query(ActionCard) if c.display]


def choose(view, action):
    from kei_panel.widgets.cards import ActionCard
    next(c for c in view.query(ActionCard) if c.entry.action == action and c.display).action_choose()


def test_the_public_card_says_what_the_visitors_see():
    def card(**kw):
        return platforms.tainacan_summary(platforms.TainacanState(True, "installed", **kw), platforms.DockerState(),
                                          platforms.BackupState())["public"]
    assert card(checked=(("site", "blog"),))[:1] == ("WordPress's sample blog",) and \
        card(checked=(("site", "blog"),))[2] == "warn"
    assert card(checked=(("site", "ready"),))[2] == "ok"
    assert card(home="prepared")[0] == "Prepared"
    assert card(checked=(("site", "custom"),))[0] == "A page of this site"      # someone's own page: kept
    assert card()[0] == "Not read yet"
    # Unknown values from --status-json are not trusted.
    st = platforms.tainacan_from_status({"platforms": [{"id": "tainacan", "supported": True, "status": "installed",
                                                        "home": "yes", "checked": {"site": "rm -rf"}}]})
    assert st.home == "" and st.check("site") == ""


@pytest.mark.parametrize("answer", ["no", "yes"])
def test_a_blog_home_page_is_said_and_prepared_only_after_the_plan_and_a_yes(answer):
    from kei_panel.screens.dialogs import ConfirmScreen

    async def main():
        ran = []
        app = make_app(patch={"home": ""}, checked={"site": "blog"}, ran=ran)
        async with app.run_test(size=(160, 48)) as pilot:
            view = await open_view(app, pilot, "tainacan")
            cards = shown(view)
            problem = str(view.query_one("#platform-problem").render())
            choose(view, "tainacan-site")
            await pilot.pause(1.5)
            preview = app.screen._preview if isinstance(app.screen, ConfirmScreen) else ""
            await pilot.click(f"#{answer}")
            await pilot.pause(2.0)
            return cards, problem, preview, [r for r in ran if r[0] == "tainacan-site"]

    cards, problem, preview, ran = asyncio.run(main())
    assert "tainacan-site" in cards and "sample blog" in problem
    assert "Nothing is deleted" in preview and "Undo" in preview
    expected = [("tainacan-site", ("plan",))]
    if answer == "yes":
        expected.append(("tainacan-site", ("apply", "confirm")))
    assert ran == expected


def test_a_prepared_home_page_is_not_offered_again_and_can_be_undone():
    async def main():
        ran = []
        app = make_app(ran=ran)               # the demo: prepared, read as ready
        async with app.run_test(size=(160, 48)) as pilot:
            home = shown(await open_view(app, pilot, "tainacan"))
            maint = shown(await open_view(app, pilot, "tainacan-maintenance"))
            view = await open_view(app, pilot, "tainacan-maintenance")
            choose(view, "tainacan-site-undo")
            await pilot.pause(1.0)
            await pilot.click("#yes")
            await pilot.pause(2.0)
            return home, maint, [r for r in ran if r[0] == "tainacan-site"]

    home, maint, ran = asyncio.run(main())
    assert "tainacan-site" not in home and "tainacan-site" not in maint
    assert "tainacan-site-undo" in maint
    assert ran == [("tainacan-site", ("undo", "confirm"))]


@pytest.mark.parametrize("answer", ["no", "yes"])
def test_a_stopped_tainacan_is_started_after_the_plan_and_a_yes_never_restored(answer):
    from kei_panel.screens.dialogs import ConfirmScreen

    async def main():
        ran = []
        app = make_app(patch={"services": "inactive", "units": {"db": "exited", "wordpress": "exited"}}, ran=ran)
        async with app.run_test(size=(160, 48)) as pilot:
            view = await open_view(app, pilot, "tainacan")
            cards = shown(view)
            choose(view, "tainacan-start")
            await pilot.pause(1.5)
            preview = app.screen._preview if isinstance(app.screen, ConfirmScreen) else ""
            await pilot.click(f"#{answer}")
            await pilot.pause(2.0)
            return cards, preview, [r for r in ran if r[0].startswith("tainacan-")]

    cards, preview, ran = asyncio.run(main())
    assert cards[0] == "tainacan-start" and "tainacan-restore" not in cards
    assert "nothing is restored" in preview
    expected = [("tainacan-start", ())]
    if answer == "yes":
        expected.append(("tainacan-start", ("confirm",)))
    assert [r for r in ran if r[0] == "tainacan-start"] == expected
    assert not [r for r in ran if r[0] in ("tainacan-restore", "tainacan-restore-test")]
