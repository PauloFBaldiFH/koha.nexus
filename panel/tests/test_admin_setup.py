"""Administrative access and the steps after a new installation (Paulo,
2026-11-06).

Administrative access (routines/admin_access.py): what each platform offers
by its state; a password typed twice in protected fields, confirmed, and
handed to the installer only in the environment of that one task (never in
its arguments); nothing runs when the person cancels, the passwords differ
or the confirmation is No. The assistant (routines/setup.py): no settings
of its own, each step opens the routine of its screen; "Do it later" only
records the step; closing records nothing; a done step is not asked again;
the reminder card follows the pending steps. The menus: one card per
platform group, the setup card only while a step is pending.
"""

import asyncio

import pytest

from kei_panel import menus, platforms
from kei_panel.bridge import TaskOutcome
from kei_panel.routines import ROUTINES, admin_access, setup
from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen

PW = "Correct-Horse-9"


def outcome(results=None, lists=None, rc=0, messages=None):
    out = TaskOutcome(rc=rc)
    for key, value in (results or {}).items():
        out.feed(f"@@result {key}={value}")
    for key, values in (lists or {}).items():
        for value in values:
            out.feed(f"@@result {key}={value}")
    out.messages.extend(messages or [])
    return out


class Result:
    def __init__(self, value):
        self.value, self.ok, self.cancelled = value, True, False


class FakeBridge:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def has_task(self, name):
        return True

    async def task(self, name, *args, **kwargs):
        self.calls.append((name, args))
        answer = self.answers.get(name, outcome())
        return answer(*args) if callable(answer) else answer


class FakeApp:
    """Answers each screen from a script: a function (screen) -> answer."""

    def __init__(self, script, answers=None):
        self.script, self.screens = list(script), []
        self.bridge = FakeBridge(answers or {})
        self.tasks = []

    async def push_screen_wait(self, screen):
        self.screens.append(screen)
        if isinstance(screen, MessageScreen):
            return None
        assert self.script, f"unexpected screen {type(screen).__name__}"
        return self.script.pop(0)(screen)

    def check_platforms(self):
        pass


@pytest.fixture
def tasks(monkeypatch):
    """run_task / show_done of the routines: recorded, answered ok."""
    ran = []

    async def run_task(app, title, name, *args, env=None, **kwargs):
        if name in app.bridge.answers:        # what is only read (admin-status)
            return Result(app.bridge.answers[name])
        ran.append((name, args, dict(env or {})))
        return Result(outcome(messages=[("info", "OK", "done")]))

    async def show(app, title, result, default=""):
        pass
    for mod in (admin_access, setup):
        if hasattr(mod, "run_task"):
            monkeypatch.setattr(mod, "run_task", run_task)
    monkeypatch.setattr(admin_access, "show_done", show)
    monkeypatch.setattr(admin_access, "show_failure", show)
    return ran


def pick(value):
    def answer(screen):
        assert isinstance(screen, ChoiceScreen)
        assert value in [v for v, _l in screen._options], (value, screen._options)
        return value
    return answer


def typed(value, password=True):
    def answer(screen):
        assert isinstance(screen, InputScreen) and screen._password is password
        return value
    return answer


def yes(answer=True):
    def reply(screen):
        assert isinstance(screen, ConfirmScreen)
        return answer
    return reply


def read(results, admins):
    return outcome(results, {"admin": admins})


def run(coro):
    return asyncio.run(coro)


def test_tainacan_initial_account_gets_its_own_password_only_through_the_environment(tasks):
    app = FakeApp([pick("own"), typed(PW), typed(PW), yes()], {
        "admin-status": read({"state": "initial", "initial": "kn_ab12"}, ["kn_ab12"])})
    run(admin_access.admin_access(app, "tainacan"))
    options = [v for v, _l in app.screens[0]._options]
    assert options == ["own", "reset", "create"]
    assert "generated at the installation" in app.screens[0]._prompt
    assert tasks == [("admin-password", ("tainacan", "kn_ab12"), {"KEI_ADMIN_PASSWORD": PW})]
    assert all(PW not in " ".join(args) for _n, args, _e in tasks)
    # Nothing shown after the typing repeats the password.
    for screen in app.screens:
        assert PW not in str(getattr(screen, "_prompt", "")) + str(getattr(screen, "_question", "")) \
            + str(getattr(screen, "_body", ""))


@pytest.mark.parametrize("script", [
    [pick("own"), typed(PW), typed("Different-Pass-1")],      # they differ
    [pick("own"), typed(PW), typed(PW), yes(False)],          # No
    [pick("own"), typed(None)],                               # cancelled
    [lambda s: None],                                         # closed
])
def test_nothing_changes_without_matching_passwords_and_a_yes(tasks, script):
    app = FakeApp(script, {"admin-status": read({"state": "initial", "initial": "kn_ab12"}, ["kn_ab12"])})
    run(admin_access.admin_access(app, "tainacan"))
    assert tasks == []


def test_a_short_password_is_refused_by_the_field():
    seen = []

    def capture(screen):
        seen.append(screen._validate)
        return None
    run(admin_access.ask_password(FakeApp([capture]), "t", "u"))
    assert seen[0]("short") and not seen[0]("ten-chars!")


def test_koha_without_a_superlibrarian_offers_the_web_installer_paths(tasks, monkeypatch):
    opened = []
    monkeypatch.setitem(ROUTINES, "superlibrarian", lambda app: _note(opened, "superlibrarian"))
    app = FakeApp([pick("create")], {"admin-status": read({"state": "web-installer"}, [])})
    run(admin_access.admin_access(app, "koha"))
    assert [v for v, _l in app.screens[0]._options] == ["create", "credentials"]
    assert "web installer" in app.screens[0]._prompt
    assert opened == ["superlibrarian"] and tasks == []


def test_koha_reset_asks_which_superlibrarian_and_never_offers_others(tasks):
    app = FakeApp([pick("reset"), pick("ana"), typed(PW), typed(PW), yes()],
                  {"admin-status": read({"state": "ready"}, ["admin", "ana", "bad name;"])})
    run(admin_access.admin_access(app, "koha"))
    assert [v for v, _l in app.screens[1]._options] == ["admin", "ana"]
    assert tasks == [("admin-password", ("koha", "ana"), {"KEI_ADMIN_PASSWORD": PW})]


def test_tainacan_another_administrator(tasks):
    app = FakeApp([pick("create"), typed("ana", False), typed("ana@x.org", False), typed(PW), typed(PW), yes()],
                  {"admin-status": read({"state": "own", "initial": "kn_ab12"}, ["kn_ab12"])})
    run(admin_access.admin_access(app, "tainacan"))
    assert [v for v, _l in app.screens[0]._options] == ["reset", "create"]
    assert tasks == [("admin-create", ("tainacan", "ana", "ana@x.org"), {"KEI_ADMIN_PASSWORD": PW})]


async def _note(seen, name):
    seen.append(name)


def status(steps, pending=None, open_=True):
    if not open_:
        return outcome({"setup": "none"})
    lines = [f"{s}|{st}|{w}" for s, st, w in steps]
    n = sum(1 for _s, st, _w in steps if st != "done") if pending is None else pending
    return outcome({"setup": "open", "pending": str(n)}, {"step": lines})


def test_the_assistant_opens_each_screens_routine_and_later_only_records(monkeypatch):
    opened = []
    for name in ("cloudflare", "backup-cloud"):
        monkeypatch.setitem(ROUTINES, name, lambda app, n=name: _note(opened, n))

    async def fake_admin(app, platform):
        opened.append(f"admin-{platform}")
    monkeypatch.setattr(admin_access, "admin_access", fake_admin)
    states = iter([
        status([("admin", "pending", ""), ("public", "pending", ""), ("backup", "pending", "")]),
        status([("admin", "done", "superlibrarian: admin"), ("public", "pending", ""), ("backup", "pending", "")]),
        status([("admin", "done", "superlibrarian: admin"), ("public", "later", ""), ("backup", "pending", "")]),
        status([("admin", "done", "superlibrarian: admin"), ("public", "later", ""), ("backup", "done", "1")]),
    ])
    app = FakeApp([pick("now"), pick("later"), pick("now"), pick("keep")],
                  {"setup-status": lambda *a: next(states)})
    run(setup.assistant(app, "koha"))
    assert opened == ["admin-koha", "backup-cloud"]
    assert ("setup-mark", ("koha", "public", "later")) in app.bridge.calls
    assert not any(n == "setup-close" for n, _a in app.bridge.calls)
    first = app.screens[0]._prompt
    assert "Step 1 of 4" in first and "Koha > Administrative access" in first
    # The overview says what is configured; step 4 is the links.
    assert any(isinstance(s, MessageScreen) and "Backup center (key b)" in s._body for s in app.screens)


def test_closing_a_step_records_nothing_and_a_done_step_is_not_asked(monkeypatch):
    app = FakeApp([lambda s: None], {"setup-status": status(
        [("admin", "done", "x"), ("public", "pending", ""), ("backup", "later", "")])})
    run(setup.assistant(app, "tainacan"))
    assert "Step 2 of 4" in app.screens[0]._prompt
    assert [n for n, _a in app.bridge.calls] == ["setup-status"]


def test_all_done_closes_the_setup_and_no_setup_means_no_assistant():
    app = FakeApp([], {"setup-status": status([(s, "done", "") for s in setup.STEPS])})
    run(setup.assistant(app, "koha"))
    assert ("setup-close", ("koha",)) in app.bridge.calls
    app = FakeApp([], {"setup-status": status([], open_=False)})
    run(setup.maybe_start(app, "tainacan"))
    assert [n for n, _a in app.bridge.calls] == ["setup-status"] and app.screens == []


def test_one_admin_card_per_group_and_the_setup_card_only_while_pending():
    koha = [e.action for e in menus.section("koha").entries]
    tainacan = [e.action for e in menus.section("tainacan").entries]
    assert "admin-koha" in koha and "admin-tainacan" in tainacan
    assert "setup-koha" in koha and "setup-tainacan" in tainacan
    for action in ("admin-koha", "admin-tainacan", "setup-koha", "setup-tainacan", "tainacan-address"):
        assert action in ROUTINES and menus.DESCRIPTIONS.get(action)
    facts = platforms.Facts(status={}, koha=True, has_task=lambda n: True)
    assert not platforms.entry_shown("setup-koha", "", "installed", facts)
    facts = platforms.Facts(status={}, koha=True, has_task=lambda n: True, setup={"koha": 2})
    assert platforms.entry_shown("setup-koha", "", "installed", facts)
    assert not platforms.entry_shown("setup-tainacan", "", "installed", facts)
