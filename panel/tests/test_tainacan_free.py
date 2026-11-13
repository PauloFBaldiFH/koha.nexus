"""The free koha.nexus address of the collection (Paulo, 2026-11-06).

routines/platforms.py: Tainacan address offers it next to keeping the
address, the local network and a domain of the person's own; when the
address service cannot give it now the option says so and shows the
reason, running nothing; in use, it can be stopped. Its questions and its
Yes are the installer's own wizard (tainacan-free on|off). The Tainacan
installation asks where the collection will answer: the local network, a
domain, the free address (made right after the installation) or later.
"""

import asyncio

import pytest

from kei_panel.routines import common, platforms
from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from kei_panel.screens.install_flow import PlanSummaryScreen
from test_admin_setup import FakeApp, Result, outcome, pick


@pytest.fixture
def ran(monkeypatch):
    """run_task and run_interactive of the routines: recorded, answered ok."""
    calls = []

    async def run_task(app, title, name, *args, **kwargs):
        calls.append((name, args))
        return Result(outcome(messages=[("ok", "OK", "done")]))

    async def run_interactive(app, title, name, *args, **kwargs):
        calls.append((name, args))
        return Result(outcome(messages=[("ok", "OK", "done")]))

    async def show(app, title, result, default=""):
        pass
    monkeypatch.setattr(common, "run_task", run_task)
    monkeypatch.setattr(common, "run_interactive", run_interactive)
    monkeypatch.setattr(common, "show_done", show)
    return calls


def free(**results):
    return outcome(results)


def run(coro):
    return asyncio.run(coro)


def options(screen):
    return [v for v, _l in screen._options]


def test_the_free_address_is_offered_and_made_by_the_installers_wizard(ran):
    app = FakeApp([pick("free")], {"tainacan-free-status": free(available="yes", library="koha",
                                                                   preview="biblioteca-acervo.koha.nexus")})
    run(platforms.tainacan_address(app))
    assert options(app.screens[0]) == ["keep", "domain", "local", "free"]
    assert ran == [("tainacan-free", ("on",))]
    # The step after the installation is done.
    assert ("setup-mark", ("tainacan", "public", "done")) in app.bridge.calls


def test_when_the_service_cannot_give_it_the_reason_is_shown_and_nothing_runs(ran):
    reason = "The free address service does not offer addresses for collections yet."
    app = FakeApp([pick("free")], {"tainacan-free-status": free(available="no", reason=reason)})
    run(platforms.tainacan_address(app))
    assert "(not available now)" in dict(app.screens[0]._options)["free"]
    shown = [s for s in app.screens if isinstance(s, MessageScreen)]
    assert shown and reason in shown[0]._body
    assert ran == [] and not any(n == "setup-mark" for n, _a in app.bridge.calls)


def test_in_use_it_can_be_stopped(ran):
    app = FakeApp([pick("free-off")], {"tainacan-free-status": free(host="biblioteca-acervo.koha.nexus",
                                                                       available="yes", library="koha")})
    run(platforms.tainacan_address(app))
    assert options(app.screens[0]) == ["keep", "domain", "local", "free-off"]
    assert ran == [("tainacan-free", ("off",))]


def test_an_installer_without_it_offers_the_other_choices_only(ran):
    app = FakeApp([pick("local"), lambda s: isinstance(s, ConfirmScreen) and True])
    app.bridge.has_task = lambda name: name != "tainacan-free-status"
    run(platforms.tainacan_address(app))
    assert options(app.screens[0]) == ["keep", "domain", "local"]
    assert ran == [("tainacan-address", ("local",))]


def test_a_domain_is_asked_and_confirmed_before_it_changes(ran):
    app = FakeApp([pick("domain"), lambda s: isinstance(s, InputScreen) and "https://acervo.example.org/",
                   lambda s: False], {"tainacan-free-status": free(available="yes")})
    run(platforms.tainacan_address(app))
    assert ran == []                     # No at the confirmation
    app = FakeApp([pick("domain"), lambda s: "https://acervo.example.org", lambda s: True],
                  {"tainacan-free-status": free(available="yes")})
    run(platforms.tainacan_address(app))
    assert ran == [("tainacan-address", ("https://acervo.example.org",))]


def port(s):
    """The PortField (U9): the proposed port, free."""
    from kei_panel.screens.port_field import PortScreen, PortState
    assert isinstance(s, PortScreen) and s._first == 8090 and s._host == "192.168.0.10"
    return PortState(8090, "free", lan="192.168.0.10")


@pytest.mark.parametrize("mode, after", [
    ("free", [("tainacan-free", ("on",))]),
    ("local", []),
    ("later", []),
])
def test_the_installation_asks_where_the_collection_will_answer(ran, mode, after):
    # Local and later ask the port (U9); the free address does not.
    answers = [pick(mode)] + ([port] if mode != "free" else []) + [lambda s: isinstance(s, PlanSummaryScreen)]
    app = FakeApp(answers, {
        "tainacan-free-status": free(available="yes"),
        "tainacan-plan": outcome({"plan": "install", "address": "http://192.168.0.10:8090"})})
    run(platforms.tainacan_install(app))
    assert options(app.screens[0]) == ["local", "domain", "free", "later"]
    assert ran == [("tainacan-install", ("confirm", "http://192.168.0.10:8090"))] + after
    marked = ("setup-mark", ("tainacan", "public", "done")) in app.bridge.calls
    # Local on purpose is the step done; later stays for later; free is done by its wizard.
    assert marked == (mode == "local")


def test_the_installation_shows_why_the_free_address_cannot_be_chosen_and_asks_again(ran):
    app = FakeApp([pick("free"), pick("later"), port, lambda s: True], {
        "tainacan-free-status": free(available="no", reason="Koha on this server has no free address yet."),
        "tainacan-plan": outcome({"plan": "install", "address": "http://192.168.0.10:8090"})})
    run(platforms.tainacan_install(app))
    assert any(isinstance(s, MessageScreen) and "no free address yet" in s._body for s in app.screens)
    assert [type(s) for s in app.screens[:3]] == [ChoiceScreen, MessageScreen, ChoiceScreen]
    assert ran == [("tainacan-install", ("confirm", "http://192.168.0.10:8090"))]
