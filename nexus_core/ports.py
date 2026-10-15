"""What a platform provides to the shared logic.

Each platform writes one adapter per interface; nothing here imports an
operating-system module. On Windows the Runner goes through wsl.exe into
the "koha" distro; on Debian/Ubuntu it would run config.sh on the same
machine. Tests use small fakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class RunResult:
    code: int
    out: str


class Runner(Protocol):
    """Runs a koha.nexus verb (config.sh / koha-panel) wherever Koha lives."""

    def installed(self) -> bool:
        """Is the system that holds Koha there at all (the WSL distro)?"""
        ...

    def running(self) -> bool:
        """Is it up? Must never start it: a status check only reads."""
        ...

    def verb(self, args: Sequence[str], timeout: float = 30) -> RunResult:
        """`config.sh ARGS` (for example ["--status-json"]), its exit code and stdout."""
        ...


class Notifier(Protocol):
    def notify(self, title: str, text: str, level: str = "info") -> str:
        """Shows one notification; returns how ("toast", "balloon", "log")."""
        ...


class StateStore(Protocol):
    """The saved state (state.json on Windows): what the librarian asked
    for and what was already notified."""

    def load(self) -> Dict[str, Any]:
        ...

    def save(self, changes: Mapping[str, Any]) -> None:
        """Merges `changes` into the saved state."""
        ...
