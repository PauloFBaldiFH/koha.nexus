"""The only door between the Textual panel and the bash installer.

Two ways in, matching the two kinds of menu entries:

  run_interactive(app, action)  suspends Textual and gives the real
      terminal to `config.sh --run <action>`: the routine's whiptail
      questions work exactly as today. Textual takes the screen back when
      the routine ends.
  stream(argv, reporter)        runs a non-interactive installer verb as an
      async subprocess (inside a worker, see tasks.py), feeding each output
      line to the loader's log; cancelling the worker kills the process.

Demo mode (--demo / KEI_PANEL_DEMO=1) answers with simulated data, so the
panel can be developed and tested without root or Koha.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from typing import TYPE_CHECKING

from .env import PanelEnv

if TYPE_CHECKING:
    from textual.app import App

    from .tasks import Reporter

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, env: PanelEnv):
        self.env = env
        self._verbs: set[str] | None = None

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def supports(self, verb: str) -> bool:
        """True when the installer in use answers this verb without a menu.

        Read from its own KEI_CLI_MODE line, so a newer installer that adds
        a verb (e.g. --backup-now) lights up the background path by itself,
        and an older one keeps the interactive routine. An unknown argument
        would open the bash main menu, so it is never sent blind."""
        if self.env.demo:
            return True
        if self._verbs is None:
            self._verbs = set()
            if self.env.installer:
                text = self.env.installer.read_text(encoding="utf-8", errors="replace")
                m = re.search(r'^case "\$\{1:-\}" in ([^)]*)\) KEI_CLI_MODE=', text, re.M)
                if m:
                    self._verbs = {v.strip() for v in m.group(1).split("|")}
        return verb in self._verbs

    def _argv(self, *args: str) -> list[str]:
        if not self.env.installer:
            raise BridgeError("installer not found (set KEI_INSTALLER)")
        return ["bash", str(self.env.installer), *args]

    # ------------------------------------------------------------------
    # Interactive routines
    # ------------------------------------------------------------------
    def run_interactive(self, app: "App", action: str) -> int:
        """Must be called from the app's thread (an event handler)."""
        if self.env.demo:
            app.notify(f"[demo] config.sh --run {action}", timeout=3)
            return 0
        argv = self._argv("--run", action)
        with app.suspend():
            rc = subprocess.run(argv, env=self.env.child_env(), check=False).returncode
        return rc

    # ------------------------------------------------------------------
    # Background verbs
    # ------------------------------------------------------------------
    async def stream(self, argv: list[str], reporter: "Reporter") -> int:
        """Run argv, every output line to reporter.log; returns the exit code."""
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, env=self.env.child_env())
        assert proc.stdout is not None
        try:
            async for raw in proc.stdout:
                line = _ANSI.sub("", raw.decode("utf-8", errors="replace")).rstrip()
                if line:
                    reporter.log(line)
            return await proc.wait()
        except asyncio.CancelledError:
            # Worker cancelled (Esc / Cancel): the task must not outlive the screen.
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 5)
            except asyncio.TimeoutError:
                proc.kill()
            raise

    async def run_verb(self, verb: tuple[str, ...], reporter: "Reporter") -> int:
        if self.env.demo:
            return await _demo_task(" ".join(verb), reporter)
        return await self.stream(self._argv(*verb), reporter)

    async def status(self) -> dict:
        """config.sh --status-json, the same JSON the Windows window reads."""
        if self.env.demo:
            await asyncio.sleep(1.2)
            return _DEMO_STATUS | {"generated_at": int(time.time())}
        proc = await asyncio.create_subprocess_exec(
            *self._argv("--status-json"), stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=self.env.child_env())
        out, _ = await proc.communicate()
        lines = [ln for ln in out.decode("utf-8", "replace").splitlines() if ln.lstrip().startswith("{")]
        if proc.returncode != 0 or not lines:
            raise BridgeError(f"--status-json failed (exit {proc.returncode})")
        return json.loads(lines[-1])

    async def koha_tables(self, reporter: "Reporter") -> list[tuple[str, int, int]]:
        """(table, rows, bytes) of the Koha database, largest first. Read-only."""
        if self.env.demo:
            for i, (name, _rows, _size) in enumerate(_DEMO_TABLES):
                reporter.progress(i + 1, len(_DEMO_TABLES))
                reporter.status(name)
                await asyncio.sleep(0.15)
            return list(_DEMO_TABLES)
        sql = ("SELECT table_name, IFNULL(table_rows,0), IFNULL(data_length+index_length,0) "
               "FROM information_schema.tables WHERE table_schema = DATABASE() "
               "ORDER BY data_length+index_length DESC")
        proc = await asyncio.create_subprocess_exec(
            "koha-mysql", self.env.instance, "-B", "-N", "-e", sql,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise BridgeError(err.decode("utf-8", "replace").strip() or "koha-mysql failed")
        rows = []
        for line in out.decode("utf-8", "replace").splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                rows.append((parts[0], int(parts[1] or 0), int(parts[2] or 0)))
        return rows


# ----------------------------------------------------------------------
# Demo data
# ----------------------------------------------------------------------
_DEMO_STATUS = {
    "schema": 1, "panel_version": "1.4.0", "platform": "wsl", "state": "running",
    "koha_installed": True,
    "services": {"apache2": "active", "mariadb": "active", "memcached": "active",
                 "koha-common": "active", "cron": "active", "elasticsearch": "inactive",
                 "cloudflared": "inactive"},
    "plack": True, "http": {"staff": 200, "opac": 200},
    "backup": {"last_file": "koha-library-20261002-0300.sql.gz", "last_epoch": 1790910000,
               "last_size": 48_300_000, "last_result": "ok", "log_epoch": 1790910060},
    "disk": {"total": 64_000_000_000, "free": 41_500_000_000},
    "memory": {"total": 8_000_000_000, "available": 5_200_000_000},
}

_DEMO_TABLES = [
    ("biblio_metadata", 48210, 412_000_000), ("items", 61877, 58_200_000),
    ("action_logs", 390112, 51_000_000), ("statistics", 205334, 33_600_000),
    ("biblio", 48210, 12_400_000), ("old_issues", 88120, 11_900_000),
    ("borrowers", 3921, 2_100_000), ("reserves", 211, 180_000),
]


async def _demo_task(name: str, reporter: "Reporter") -> int:
    steps = ["Checking the lock", "Dumping the database", "Compressing", "Verifying the copy",
             "Writing the checksum"]
    for i, step in enumerate(steps, 1):
        reporter.status(step)
        for n in range(8):
            reporter.log(f"[{name}] {step.lower()}: chunk {n + 1}/8")
            await asyncio.sleep(0.12)
        reporter.progress(i, len(steps))
    return 0
