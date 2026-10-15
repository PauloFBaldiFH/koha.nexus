import sys
import textwrap
import threading
import time

import pytest

from koha_nexus_win import engine

# A stand-in for `installer --task`: speaks the @@ protocol and reads answers.
FAKE = textwrap.dedent(r"""
    import sys
    def say(s):
        sys.stderr.write(s + "\n"); sys.stderr.flush()
    say("@@title Restore")
    say("@@step Checking the file")
    say("@@done 0 Checking the file")
    print("plain output line", flush=True)
    say("@@ask Restore\tReplace the catalog?")
    reply = sys.stdin.readline().strip()
    say("@@note answered " + reply)
    say("@@input Name\tYour name:\t")
    name = sys.stdin.readline().strip()[len("ok "):]
    say("@@result who=" + name)
    if reply != "yes":
        sys.exit(130)
    sys.exit(0)
""")

SLOW = "import time, sys\nsys.stderr.write('@@step Waiting\\n'); sys.stderr.flush()\ntime.sleep(30)\n"


def collector():
    events, cond = [], threading.Condition()

    def sink(run_id, ev):
        with cond:
            events.append((run_id, ev))
            cond.notify_all()

    def wait_for(pred, timeout=10):
        end = time.time() + timeout
        with cond:
            while not any(pred(e) for _, e in events):
                left = end - time.time()
                if left <= 0:
                    raise AssertionError(f"timed out; got {[e for _, e in events]}")
                cond.wait(left)
    return events, sink, wait_for


def fake_argv(script_path):
    return lambda name, args: [sys.executable, str(script_path), *args]


def test_task_argv():
    argv = engine.task_argv("backup-manual", ["/var/backups/koha"], exe="wsl.exe")
    assert argv == ["wsl.exe", "-d", "koha", "-u", "root", "--", "env", "KEI_TASK_INTERACTIVE=1", "LANG=C.UTF-8",
                    "/usr/local/bin/koha-panel", "--task", "backup-manual", "/var/backups/koha"]
    assert "KEI_TASK_INTERACTIVE=1" not in engine.task_argv("status", exe="wsl.exe", interactive=False)
    for bad in ("Status", "status; rm -rf /", "", "-x"):
        with pytest.raises(ValueError):
            engine.task_argv(bad)


def test_mnt_path():
    assert engine.mnt_path("C:\\Users\\ana\\acervo.mrc") == "/mnt/c/Users/ana/acervo.mrc"
    assert engine.mnt_path("/already/linux") == "/already/linux"


def test_a_task_streams_events_and_takes_answers(tmp_path):
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    events, sink, wait_for = collector()
    eng = engine.Engine(sink, argv=fake_argv(script), log_dir=tmp_path / "logs")
    started = eng.start("restore")
    assert started["ok"] and started["total"] == 10
    run_id = started["id"]
    wait_for(lambda e: e["kind"] == "ask")
    assert eng.start("status")["busy"] == run_id  # one task at a time
    assert eng.answer(run_id, True)
    assert not eng.answer(run_id, True)  # nothing waits any more
    wait_for(lambda e: e["kind"] == "input")
    assert eng.answer(run_id, "Ana")
    wait_for(lambda e: e["kind"] == "end")
    kinds = [e["kind"] for _, e in events]
    assert kinds[:3] == ["title", "step", "done"]
    assert {"kind": "log", "waits": False, "text": "plain output line"} in [e for _, e in events]
    assert any(e["kind"] == "note" and e["text"] == "answered yes" for _, e in events)
    assert any(e["kind"] == "result" and e["value"] == "Ana" for _, e in events)
    done = next(e for _, e in events if e["kind"] == "done")
    assert done["progress"] == pytest.approx(0.1)
    end = events[-1][1]
    assert end["rc"] == 0 and not end["cancelled"]
    logs = list((tmp_path / "logs").glob("*-restore.log"))
    assert logs and "<< yes" in logs[0].read_text(encoding="utf-8")
    text = logs[0].read_text(encoding="utf-8")
    assert "<< ok\n" in text and "<< ok Ana" not in text  # typed answers stay out of the log


def test_cancel_ends_the_process(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text(SLOW)
    events, sink, wait_for = collector()
    eng = engine.Engine(sink, argv=fake_argv(script))
    run_id = eng.start("search-repair")["id"]
    wait_for(lambda e: e["kind"] == "step")
    assert eng.cancel(run_id)
    wait_for(lambda e: e["kind"] == "end")
    assert events[-1][1]["rc"] == 130 and events[-1][1]["cancelled"]
    assert not eng.cancel(run_id)


def test_a_missing_wsl_is_an_error_event():
    events, sink, _ = collector()

    def broken(*a, **k):
        raise FileNotFoundError("wsl.exe")
    eng = engine.Engine(sink, popen=broken, argv=lambda n, a: ["wsl.exe"])
    eng.start("status")
    assert [e["kind"] for _, e in events] == ["msg", "end"]
    assert events[-1][1]["rc"] == -1


def test_the_pump_batches_events():
    delivered = []
    pump = engine.EventPump(delivered.append, every=0.01, limit=3)
    for i in range(5):
        pump.push(1, {"kind": "log", "text": str(i)})
    assert pump.pump_once() == 3
    assert pump.pump_once() == 2
    assert pump.pump_once() == 0
    assert [len(b) for b in delivered] == [3, 2]
    assert delivered[0][0] == {"run": 1, "kind": "log", "text": "0"}
    pump.start()
    pump.push(2, {"kind": "end"})
    time.sleep(0.1)
    pump.stop()
    assert delivered[-1] == [{"run": 2, "kind": "end"}]


def test_a_failing_delivery_does_not_stop_the_pump():
    def boom(batch):
        raise RuntimeError("page reloading")
    pump = engine.EventPump(boom)
    pump.push(1, {"kind": "log"})
    assert pump.pump_once() == 1
