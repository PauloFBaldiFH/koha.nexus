import re
from pathlib import Path

import pytest

from nexus_core import taskproto as tp

INSTALLER = Path(__file__).resolve().parents[2] / "installer"
KNOWN = {"step", "done", "note", "title", "stage", "msg", "say", "ask", "choose", "input",
         "check", "file", "edit", "view", "preview", "result", "cancel"}


def test_every_tag_the_installer_emits_is_read():
    """Contract: a new @@ tag in the installer must be taught to this reader
    (and to the Windows window) before it ships."""
    if not INSTALLER.exists():
        pytest.skip("installer not in this checkout")
    emitted = set(re.findall(r"kei_emit ([a-z]+)", INSTALLER.read_text(encoding="utf-8", errors="replace")))
    assert emitted, "no kei_emit call found: the protocol moved"
    assert emitted <= KNOWN, f"tags not read by nexus_core.taskproto: {sorted(emitted - KNOWN)}"


def test_the_waiting_tags_match_the_panel():
    assert tp.WAITS == {"ask", "choose", "input", "say", "view", "check", "file", "edit"}


def test_clean_strips_colours_and_cuts():
    assert tp.clean(b"\x1b[1;32mok\x1b[0m  \r\n") == "ok"
    assert tp.clean("x" * 2100).endswith(" …")
    assert tp.parse_line("") is None


def test_plain_lines_and_unknown_tags_are_log_lines():
    assert tp.parse_line("Copying files").to_json() == {"kind": "log", "waits": False, "text": "Copying files"}
    assert tp.parse_line("@@progress 3 10").kind == "log"


def test_steps_and_progress():
    p = tp.Progress.for_task("restore")
    for line in ("@@step Stopping Koha", "@@done 0 Stopping Koha", "@@step Importing", "@@done 1 Importing"):
        p.feed(tp.parse_line(line))
    assert p.finished == 2 and p.fraction == pytest.approx(0.2)
    assert p.failed == ["Importing"]
    assert tp.parse_line("@@done x Lost").data["rc"] == tp.RC_FAILED
    assert tp.Progress.for_task("status").fraction is None


def test_stage_message_and_texts_with_new_lines():
    st = tp.parse_line("@@stage [3/7] Database\tKeep this window open.\\nIt takes a while.")
    assert st.data == {"stage": "[3/7] Database", "note": "Keep this window open.\nIt takes a while."}
    p = tp.Progress()
    p.feed(st)
    assert p.stage == "[3/7] Database"
    msg = tp.parse_line("@@msg error Something needs attention\tLine one\\nLine two")
    assert msg.data == {"level": "error", "title": "Something needs attention", "text": "Line one\nLine two"}
    assert not msg.waits
    say = tp.parse_line("@@say ok OK\tDone.")
    assert say.waits and tp.reply_for(say, None) == "ok"


def test_ask():
    ev = tp.parse_line("@@ask Restore\tReplace the whole catalog?")
    assert ev.waits and ev.data["title"] == "Restore"
    assert tp.reply_for(ev, True) == "yes"
    assert tp.reply_for(ev, False) == "no"


def test_choose_and_input():
    ev = tp.parse_line("@@choose Language\tPick one:\tpt\ten\tEnglish\tpt\tPortuguês")
    assert ev.data["default"] == "pt"
    assert ev.data["options"] == [{"key": "en", "label": "English"}, {"key": "pt", "label": "Português"}]
    assert tp.reply_for(ev, "pt") == "ok pt"
    assert tp.reply_for(ev, None) == "cancel"
    pw = tp.parse_line("@@input Database\tNew password:\t\tpassword")
    assert pw.data["password"] is True and pw.data["default"] == ""
    assert tp.reply_for(pw, "s3cret") == "ok s3cret"
    assert tp.reply_for(pw, "") == "ok "
    assert tp.reply_for(pw, None) == "cancel"


def test_a_reply_never_spans_two_lines():
    ev = tp.parse_line("@@input Name\tName:\t")
    assert tp.reply_for(ev, "a\nyes") == "ok a yes"


def test_check_file_edit_view():
    ev = tp.parse_line("@@check Jobs\tTurn on:\tbackup\tNightly backup\tON\tmarc\tMARC export\toff")
    assert ev.data["options"] == [{"key": "backup", "label": "Nightly backup", "on": True},
                                  {"key": "marc", "label": "MARC export", "on": False}]
    assert tp.reply_for(ev, ["backup", "marc"]) == "ok backup\tmarc"
    assert tp.reply_for(ev, None) == "cancel"
    f = tp.parse_line("@@file file\tFile Explorer\tPick the backup:\t/root\tsql sql.gz")
    assert f.data == {"mode": "file", "title": "File Explorer", "text": "Pick the backup:", "start": "/root",
                      "exts": ["sql", "sql.gz"]}
    assert tp.reply_for(f, "/mnt/c/Users/ana/koha.sql.gz") == "ok /mnt/c/Users/ana/koha.sql.gz"
    assert tp.reply_for(f, None) == "cancel"
    e = tp.parse_line("@@edit Cron\t/etc/cron.d/koha\tSave to apply")
    assert e.data["path"] == "/etc/cron.d/koha"
    assert tp.reply_for(e, True) == "ok" and tp.reply_for(e, False) == "cancel"
    v = tp.parse_line("@@view Report\tline 1\\nline 2")
    assert v.waits and v.data["text"] == "line 1\nline 2"
    pv = tp.parse_line("@@preview Changes\t3 records")
    assert not pv.waits and pv.kind == "preview"


def test_result_and_cancel():
    r = tp.parse_line("@@result row=Koha\tVersion\t25.05")
    assert r.data == {"key": "row", "value": "Koha\tVersion\t25.05"}
    assert tp.parse_line("@@cancel on").data == {"on": True}
    assert tp.parse_line("@@cancel off").data == {"on": False}


def test_events_without_a_reply_refuse_one():
    with pytest.raises(ValueError):
        tp.reply_for(tp.parse_line("@@note hi"), True)
