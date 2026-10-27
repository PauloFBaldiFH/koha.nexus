"""The AI server helper: allowlist, model answers, audit, script, screen."""

import asyncio
import json
import re
import subprocess
import time

import pytest
from conftest import INSTALLER
from textual.widgets import Input, RichLog

from kei_panel import aiclient, aiconf, serverhelper as sh
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen
from kei_panel.screens.loading import LoadingScreen


def _script() -> str:
    text = INSTALLER.read_text(encoding="utf-8")
    return re.search(r"cat <<'AIHSH'\n(.*?)\nAIHSH\n", text, re.S).group(1) + "\n"


def _shell_list(script: str, name: str) -> tuple[str, ...]:
    return tuple(re.search(rf'^{name}="([^"]*)"', script, re.M).group(1).split())


# ----------------------------------------------------------------------
# The allowlist
# ----------------------------------------------------------------------
def test_the_script_and_the_panel_allow_the_same_things():
    script = _script()
    assert _shell_list(script, "SERVICES") == sh.SERVICES
    assert _shell_list(script, "KOHA_LOGS") == sh.KOHA_LOGS
    cases = set(re.findall(r"^    ([a-z-]+)\)$", script, re.M))
    assert cases == set(sh.ACTIONS)


@pytest.fixture
def script_file(tmp_path):
    path = tmp_path / "kn-helper-action"
    path.write_text(_script())
    return path


@pytest.mark.parametrize("args", [
    [], ["nope"], ["restart"], ["restart", "ssh"], ["restart", "apache2;reboot"], ["restart", "apache2 mariadb"], ["restart", "*"], ["restart", "apache2", "x"],
    ["service-log", "../../etc/shadow"], ["koha-log", "library", "../../../etc/shadow"],
    ["reindex", "lib rary"], ["backup", "/tmp"], ["overview", "x"],
])
def test_the_script_refuses_anything_outside_its_list(script_file, args):
    p = subprocess.run(["sh", str(script_file), *args], capture_output=True, text=True, timeout=10)
    assert p.returncode == 2 and "refused" in p.stderr


def test_the_script_is_valid_sh(script_file):
    assert subprocess.run(["sh", "-n", str(script_file)]).returncode == 0


@pytest.mark.parametrize("action,args,why", [
    ("rm", ["-rf"], "unknown"), ("restart", [], "argument"), ("restart", ["sshd"], "not allowed"),
    ("restart", ["apache2", "mariadb"], "argument"), ("koha-log", ["passwd"], "not allowed"),
    ("clear-cache", ["library"], "argument"),
])
def test_check_args_refuses(action, args, why):
    with pytest.raises(sh.ActionError, match=why):
        sh.check_args(action, args, "library")


def test_instance_is_filled_in_and_checked():
    assert sh.argv("clear-cache", [], "library") == [
        "runuser", "-u", "kn-helper", "--", "sudo", "-n", sh.SCRIPT, "clear-cache", "library"]
    assert sh.argv("koha-log", ["opac-error"], "library")[-3:] == ["koha-log", "library", "opac-error"]
    with pytest.raises(sh.ActionError):
        sh.argv("reindex", [], "lib;rary")
    assert sh.effect_text("restart", ["apache2"], "library") == "systemctl restart apache2"
    assert sh.command_text("restart", ["apache2"], "library").endswith("kn-helper-action restart apache2")


def test_run_never_starts_a_refused_action(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("ran"))
    with pytest.raises(sh.ActionError):
        sh.run("restart", ["ssh"], "library")


# ----------------------------------------------------------------------
# The model's answers
# ----------------------------------------------------------------------
def test_parse_reply_keeps_only_allowed_actions():
    text = "```json\n" + json.dumps({
        "say": "Looking.",
        "read": [{"action": "overview", "args": []}, {"action": "restart", "args": ["apache2"]},
                 {"action": "shell", "args": ["rm -rf /"]}, {"action": "service-log", "args": ["apache2"]}],
        "propose": {"action": "restart", "args": ["koha-common"], "why": "w", "risk": "r"},
    }) + "\n```"
    r = sh.parse_reply(text, "library")
    assert r.say == "Looking."
    assert r.reads == [("overview", []), ("service-log", ["apache2"])]
    assert r.refused == ["restart", "shell"]                     # a change is never run as a read
    assert r.proposal == sh.Proposal("restart", ["koha-common"], "w", "r")

    r = sh.parse_reply(json.dumps({"say": "x", "propose": {"action": "restart", "args": ["ssh"]}}), "library")
    assert r.proposal is None and r.refused == ["restart"]
    assert sh.parse_reply("just words", "library").say == "just words"


def test_redact_hides_secrets_but_keeps_the_question():
    out = sh.redact("password=hunter2 token: abc Bearer eyJ.x sk-ant-0123456789abcdef AIzaSyD-0123456789abcdefghij "
                    "<pass>s3</pass> ana@biblioteca.org")
    for secret in ("hunter2", "abc", "eyJ", "sk-ant", "AIzaSy", "s3<", "ana@"):
        assert secret not in out
    assert sh.redact("the password reset page fails") == "the password reset page fails"


def test_conversation_reads_then_proposes():
    replies = iter([
        json.dumps({"say": "", "read": [{"action": "overview", "args": []}]}),
        json.dumps({"say": "Restart memcached.", "read": [],
                    "propose": {"action": "restart", "args": ["memcached"], "why": "failed"}}),
    ])
    sent, ran = [], []

    def chat(messages):
        sent.append([dict(m) for m in messages])
        return next(replies)

    def run(action, args):
        ran.append((action, args))
        return 0, "memcached failed\nDB password=secret1"

    conv = sh.Conversation("pt", "library")
    turn = conv.ask("pages are slow", chat, run)
    assert ran == [("overview", [])]
    assert turn.say == "Restart memcached." and turn.proposal.action == "restart"
    assert turn.readings[0][0].endswith("kn-helper-action overview")
    readings = sent[1][-1]["content"]
    assert "memcached failed" in readings and "secret1" not in readings
    assert "language whose code is pt" in sent[0][0]["content"]

    conv.ran(turn.proposal, approved=True, rc=0, out="memcached: active")
    assert conv.messages[-1]["content"].startswith("Result of the approved change")


def test_conversation_stops_after_a_few_rounds():
    chat = lambda m: json.dumps({"say": "more", "read": [{"action": "overview", "args": []}]})
    runs = []
    turn = sh.Conversation("en", "library").ask("?", chat, lambda a, b: runs.append(a) or (0, ""))
    assert len(runs) == sh.MAX_READ_ROUNDS and turn.say == "more"


# ----------------------------------------------------------------------
# Consent and audit
# ----------------------------------------------------------------------
def test_consent_and_audit_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDO_USER", "paulo")
    consent = tmp_path / "ai-helper.conf"
    assert not sh.accepted(consent)
    sh.accept(consent)
    assert sh.accepted(consent) and "paulo" in consent.read_text()
    assert consent.stat().st_mode & 0o777 == 0o600

    log = tmp_path / "ai-helper.log"
    sh.audit("approved", path=log, command="x restart apache2", provider="gemini", model="m")
    sh.audit("ran", path=log, command="x", rc=0, output="token=abc ok")
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert [x["event"] for x in lines] == ["approved", "ran"]
    assert lines[0]["user"] == "paulo" and lines[0]["provider"] == "gemini"
    assert "abc" not in lines[1]["output"]
    assert log.stat().st_mode & 0o777 == 0o640


# ----------------------------------------------------------------------
# The chat request, as KohaEasy::Assistant sends it
# ----------------------------------------------------------------------
def test_chat_bodies_and_replies():
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
    c = aiconf.with_defaults({"provider": "anthropic", "token": "k", "chat_model": "claude-haiku-5-5"})
    body = aiclient.chat_body(c, msgs)
    assert body["system"] == "S" and body["messages"] == [{"role": "user", "content": "a\n\nb"}]
    assert body["model"] == "claude-haiku-5-5"
    assert aiclient.chat_endpoint(c) == "https://api.anthropic.com/v1/messages"
    assert aiclient.reply_text("anthropic", {"content": [{"type": "text", "text": "{}"}]}) == "{}"

    c = aiconf.with_defaults({"provider": "ollama"})
    body = aiclient.chat_body(c, msgs)
    assert body["format"] == "json" and body["options"]["num_ctx"] == aiclient.OLLAMA_CTX
    assert aiclient.chat_endpoint(c) == "http://127.0.0.1:11434/api/chat"
    assert aiclient.reply_text("ollama", {"message": {"content": "x"}}) == "x"

    c = aiconf.with_defaults({"provider": "gemini", "token": "k"})
    assert aiclient.chat_body(c, msgs)["response_format"] == {"type": "json_object"}
    assert aiclient.chat_endpoint(c).endswith("/v1beta/openai/chat/completions")
    assert aiclient.reply_text("gemini", {"choices": [{"message": {"content": "y"}}]}) == "y"

    with pytest.raises(RuntimeError, match="API key"):
        aiclient.chat(aiconf.with_defaults({"provider": "gemini"}), msgs)


# ----------------------------------------------------------------------
# The screen, in demo mode
# ----------------------------------------------------------------------
async def _until(pilot, cond, wait=5.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_helper_screen_asks_proposes_and_runs_only_after_approval(tmp_path, monkeypatch):
    from kei_panel.app import KohaPanelApp
    from kei_panel.screens.serverhelper import ServerHelperScreen

    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    aiconf.save_all(tmp_path / "kei-demo-ai" / "vision.conf", aiconf.with_defaults({"provider": "ollama"}))
    monkeypatch.setattr(sh, "audit", lambda *a, **k: pytest.fail("demo must not write the audit log"))

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("a")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-ai")
            assert not view.query_one("#ai-helper").disabled
            assert "potentially dangerous" in str(view.query_one("#ai-helper-text").render())
            view.open_helper()
            await pilot.pause(0.3)
            screen = app.screen
            assert isinstance(screen, ServerHelperScreen)
            assert "Potentially dangerous" in str(screen.query_one("#helper-warning").render())
            assert "nothing leaves the machine" in str(screen.query_one("#helper-provider").render())

            screen.query_one("#helper-input", Input).value = "the staff pages are slow"
            screen.send()
            await _until(pilot, lambda: not isinstance(app.screen, LoadingScreen) and screen.proposal)
            assert screen.query_one("#helper-proposal").display
            command = str(screen.query_one("#helper-command").render())
            assert "kn-helper-action restart memcached" in command and "systemctl restart memcached" in command

            ran = []
            monkeypatch.setattr("kei_panel.screens.serverhelper._demo_run",
                                lambda a, args: ran.append((a, args)) or (0, "memcached: active"))
            screen.approve()
            await pilot.pause(0.2)
            assert isinstance(app.screen, ConfirmScreen) and ran == []      # a second, explicit yes
            app.screen.dismiss(False)
            await pilot.pause(0.2)
            assert ran == [] and screen.proposal                            # still waiting

            screen.approve()
            await pilot.pause(0.2)
            app.screen.dismiss(True)
            await _until(pilot, lambda: ran == [("restart", ["memcached"])] and app.screen is screen)
            await pilot.pause(0.2)
            assert not screen.query_one("#helper-proposal").display
            assert screen.conversation.messages[-1]["content"].startswith("Result of the approved change")
            assert len(screen.query_one("#helper-log", RichLog).lines) > 3

    asyncio.run(main())
