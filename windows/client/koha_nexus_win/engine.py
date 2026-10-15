"""Runs installer tasks for the window, with no console (Phase A).

Each operation is one hidden process:

    wsl.exe -d koha -u root -- env KEI_TASK_INTERACTIVE=1 LANG=C.UTF-8 \\
        /usr/local/bin/koha-panel --task NAME ARGS...

the call the Textual panel makes inside Debian (bridge.task). A reader
thread turns each output line into an event (nexus_core.taskproto) and
hands it to a sink; the window's EventPump sends them to the page in small
batches. A question waits until the page answers it: the reply line goes to
the routine's stdin. Cancel ends the process, as the panel's loader does.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import subprocess
import threading
import time
from itertools import count
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from nexus_core import taskproto

from . import config
from .wsl import CREATE_NO_WINDOW, wsl_exe

log = logging.getLogger(__name__)

TASK_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_LINE_LIMIT = 1 << 20

Sink = Callable[[int, Dict[str, Any]], None]


def task_argv(name: str, args: Sequence[str] = (), *, exe: Optional[str] = None,
              distro: str = config.DISTRO, panel: str = config.PANEL_PATH,
              interactive: bool = True) -> List[str]:
    """The wsl.exe command line of one task. Variables travel through
    `env`, so they reach Debian whatever WSLENV says."""
    if not TASK_NAME.match(name):
        raise ValueError(f"not a task name: {name!r}")
    env = ["KEI_TASK_INTERACTIVE=1"] if interactive else []
    return [exe or wsl_exe(), "-d", distro, "-u", "root", "--",
            "env", *env, "LANG=C.UTF-8", panel, "--task", name, *args]


def mnt_path(windows_path: str) -> str:
    """C:\\Users\\ana\\a.mrc -> /mnt/c/Users/ana/a.mrc, WSL's default mount
    (used when wslpath cannot be asked)."""
    p = windows_path.replace("\\", "/")
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        return f"/mnt/{p[0].lower()}{p[2:]}"
    return p


class TaskRun:
    """One running task: its process, its pending question, its exit code."""

    def __init__(self, run_id: int, name: str, argv: Sequence[str], sink: Sink,
                 popen: Callable[..., Any] = subprocess.Popen, log_dir: Optional[Path] = None):
        self.id = run_id
        self.name = name
        self.argv = list(argv)
        self.sink = sink
        self._popen = popen
        self.log_dir = log_dir
        self.progress = taskproto.Progress.for_task(name)
        self.pending: Optional[taskproto.Event] = None
        self.rc: Optional[int] = None
        self.cancelled = False
        self.proc: Any = None
        self._lock = threading.Lock()
        self._log: Any = None
        self.thread: Optional[threading.Thread] = None

    # --- life --------------------------------------------------------
    def start(self) -> "TaskRun":
        env = dict(os.environ, WSL_UTF8="1")
        self._open_log()
        try:
            self.proc = self._popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=env,
                                    creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        except OSError as e:
            self._emit(taskproto.Event("msg", {"level": "error", "title": "wsl.exe", "text": str(e)}))
            self._finish(-1)
            return self
        self.thread = threading.Thread(target=self._read, name=f"task-{self.name}", daemon=True)
        self.thread.start()
        return self

    def _read(self) -> None:
        out = self.proc.stdout
        try:
            for raw in iter(lambda: out.readline(_LINE_LIMIT), b""):
                line = taskproto.clean(raw)
                self._write_log(line)
                ev = taskproto.parse_line(line)
                if ev is None:
                    continue
                self.progress.feed(ev)
                if ev.waits:
                    with self._lock:
                        self.pending = ev
                self._emit(ev)
        except (OSError, ValueError):
            log.exception("reading task %s failed", self.name)
        self._finish(self.proc.wait())

    def _emit(self, ev: taskproto.Event) -> None:
        data = ev.to_json()
        if ev.kind in ("step", "done", "stage"):
            data["progress"] = self.progress.fraction
        try:
            self.sink(self.id, data)
        except Exception:  # noqa: BLE001 - a closed window must not stop the task
            log.exception("task event not delivered")

    def _finish(self, rc: int) -> None:
        self.rc = taskproto.RC_CANCELLED if self.cancelled else rc
        with self._lock:
            self.pending = None
        self._write_log(f"-- exit {self.rc}")
        if self._log:
            self._log.close()
            self._log = None
        try:
            self.sink(self.id, {"kind": "end", "waits": False, "rc": self.rc, "cancelled": self.cancelled,
                                "failed": self.progress.failed})
        except Exception:  # noqa: BLE001
            log.exception("task end not delivered")

    @property
    def running(self) -> bool:
        return self.rc is None

    # --- the page's side ----------------------------------------------
    def answer(self, value: Any) -> bool:
        """The person's answer to the pending question; False when nothing waits."""
        with self._lock:
            ev, self.pending = self.pending, None
        if ev is None or self.proc is None or self.proc.stdin is None:
            return False
        line = taskproto.reply_for(ev, value)
        self._write_log(f"<< {line.split(' ', 1)[0] if ev.kind == 'input' else line}")
        try:
            self.proc.stdin.write((line + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return False
        return True

    def cancel(self) -> None:
        self.cancelled = True
        if self.proc is not None and self.rc is None:
            try:
                self.proc.terminate()
            except OSError:
                pass

    # --- log file -----------------------------------------------------
    def _open_log(self) -> None:
        if not self.log_dir:
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            name = time.strftime("%Y%m%d-%H%M%S-") + self.name + ".log"
            self._log = open(self.log_dir / name, "a", encoding="utf-8")
            self._log.write("$ " + " ".join(self.argv) + "\n")
        except OSError:
            self._log = None

    def _write_log(self, line: str) -> None:
        if self._log:
            try:
                self._log.write(line + "\n")
                self._log.flush()
            except OSError:
                pass


class Engine:
    """The window's tasks: one runs at a time (the installer takes its own
    locks, and a librarian follows one job), older ones are remembered."""

    def __init__(self, sink: Sink, popen: Callable[..., Any] = subprocess.Popen,
                 log_dir: Optional[Path] = None, argv: Callable[..., List[str]] = task_argv):
        self.sink = sink
        self.popen = popen
        self.log_dir = log_dir
        self.argv = argv
        self.runs: Dict[int, TaskRun] = {}
        self._ids = count(1)

    def busy(self) -> Optional[TaskRun]:
        return next((r for r in self.runs.values() if r.running), None)

    def start(self, name: str, args: Sequence[str] = ()) -> Dict[str, Any]:
        current = self.busy()
        if current is not None:
            return {"ok": False, "busy": current.id, "name": current.name}
        run = TaskRun(next(self._ids), name, self.argv(name, args), self.sink, self.popen, self.log_dir)
        self.runs[run.id] = run
        run.start()
        return {"ok": True, "id": run.id, "name": name, "total": run.progress.total}

    def answer(self, run_id: int, value: Any) -> bool:
        run = self.runs.get(run_id)
        return bool(run and run.answer(value))

    def cancel(self, run_id: int) -> bool:
        run = self.runs.get(run_id)
        if not run or not run.running:
            return False
        run.cancel()
        return True


class EventPump:
    """Collects task events from reader threads and delivers them in
    batches, at most every `every` seconds, to deliver(list): the window's
    evaluate_js. One call per batch keeps a chatty import from flooding the
    page."""

    def __init__(self, deliver: Callable[[List[Dict[str, Any]]], None], every: float = 0.1,
                 limit: int = 500):
        self.deliver = deliver
        self.every = every
        self.limit = limit
        self._q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def push(self, run_id: int, event: Dict[str, Any]) -> None:
        self._q.put({"run": run_id, **event})

    def drain(self) -> List[Dict[str, Any]]:
        batch: List[Dict[str, Any]] = []
        while len(batch) < self.limit:
            try:
                batch.append(self._q.get_nowait())
            except queue.Empty:
                break
        return batch

    def pump_once(self) -> int:
        batch = self.drain()
        if batch:
            try:
                self.deliver(batch)
            except Exception:  # noqa: BLE001 - the page may be reloading
                log.exception("events not delivered")
        return len(batch)

    def _loop(self) -> None:
        while not self._stop.wait(self.every):
            self.pump_once()
        self.pump_once()

    def start(self) -> "EventPump":
        self._thread = threading.Thread(target=self._loop, name="event-pump", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(2)
