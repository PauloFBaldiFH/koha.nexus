"""The installer's task protocol, read by a desktop client.

`config.sh --task NAME` (the installer's PANEL TASKS section) runs a routine
with no dialog: what it would show becomes "@@TAG REST" lines on stderr,
and with KEI_TASK_INTERACTIVE=1 it waits on stdin for the answer to each
question. panel/kei_panel/bridge.py (TaskOutcome.feed, answer_prompt) is
the reference reader; this module reads the same lines into events a
window can draw, and writes the reply line for an answer.

    @@step LABEL            @@done RC LABEL         @@note TEXT
    @@title TEXT            @@stage STAGE<TAB>NOTE  @@msg KIND TITLE<TAB>TEXT
    @@say KIND TITLE<TAB>TEXT (waits)               @@ask TITLE<TAB>TEXT (waits)
    @@choose TITLE<TAB>PROMPT<TAB>DEFAULT<TAB>KEY<TAB>LABEL... (waits)
    @@input TITLE<TAB>PROMPT<TAB>DEFAULT<TAB>password (waits)
    @@check TITLE<TAB>PROMPT<TAB>KEY<TAB>LABEL<TAB>ON|OFF... (waits)
    @@file file|dir<TAB>TITLE<TAB>PROMPT<TAB>START<TAB>EXTS (waits)
    @@edit TITLE<TAB>PATH<TAB>NOTE (waits)          @@view TITLE<TAB>TEXT (waits)
    @@preview TITLE<TAB>TEXT                        @@result KEY=VALUE
    @@cancel on|off

New lines inside a text travel as a literal "\\n". Any other line is a log
line. Standard library only; nothing here starts a process.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Tags whose routine waits for a reply line (bridge._PROMPTS).
WAITS = frozenset({"ask", "choose", "input", "say", "view", "check", "file", "edit"})

# Steps of the routines that have a fixed count (the panel's routines/*.py),
# so a progress bar can be drawn from @@step lines.
STEP_TOTALS = {"install": 18, "restore": 10, "search-toggle": 9, "search-repair": 3}

# Exit codes of kei_task.
RC_OK, RC_FAILED, RC_USAGE, RC_CANCELLED = 0, 1, 2, 130

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")
_SHOWN = 2000


def unescape(text: str) -> str:
    """Texts carry new lines as a literal \\n (bridge.unescape)."""
    return text.replace("\\n", "\n")


def clean(raw: Union[bytes, str]) -> str:
    """One output line without colours, carriage returns or trailing space,
    cut at 2000 characters (bridge._clean)."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    line = _ANSI.sub("", text).rstrip()
    return line if len(line) <= _SHOWN else line[:_SHOWN] + " …"


@dataclass(frozen=True)
class Event:
    """One thing the routine said. kind is the tag ("log" for a plain line);
    data holds its fields; waits is True when a reply line must follow."""
    kind: str
    data: Dict[str, Any] = field(default_factory=dict)
    waits: bool = False

    def to_json(self) -> Dict[str, Any]:
        return {"kind": self.kind, "waits": self.waits, **self.data}


def _parts(rest: str, n: int) -> List[str]:
    parts = rest.split("\t")
    return parts + [""] * (n - len(parts)) if len(parts) < n else parts


def parse_line(line: str) -> Optional[Event]:
    """The event of one cleaned line; None for an empty one."""
    if not line:
        return None
    if not line.startswith("@@"):
        return Event("log", {"text": line})
    tag, _, rest = line[2:].partition(" ")
    waits = tag in WAITS
    if tag == "step":
        return Event("step", {"label": rest})
    if tag == "done":
        rc_text, _, label = rest.partition(" ")
        rc = int(rc_text) if rc_text.lstrip("-").isdigit() else RC_FAILED
        return Event("done", {"rc": rc, "label": label})
    if tag in ("note", "title"):
        return Event(tag, {"text": unescape(rest)})
    if tag == "stage":
        stage, _, note = rest.partition("\t")
        return Event("stage", {"stage": stage, "note": unescape(note)})
    if tag in ("msg", "say"):
        level, _, rest = rest.partition(" ")
        title, _, text = rest.partition("\t")
        return Event(tag, {"level": level, "title": title, "text": unescape(text)}, waits)
    if tag == "ask":
        title, _, text = rest.partition("\t")
        return Event("ask", {"title": title, "text": unescape(text)}, waits)
    if tag in ("view", "preview"):
        title, _, text = rest.partition("\t")
        return Event(tag, {"title": title, "text": unescape(text)}, waits)
    if tag == "choose":
        parts = _parts(rest, 3)
        items = parts[3:]
        options = [{"key": k, "label": v} for k, v in zip(items[::2], items[1::2])]
        return Event("choose", {"title": parts[0], "text": unescape(parts[1]), "default": parts[2],
                                "options": options}, waits)
    if tag == "input":
        parts = _parts(rest, 4)
        return Event("input", {"title": parts[0], "text": unescape(parts[1]), "default": parts[2],
                               "password": parts[3] == "password"}, waits)
    if tag == "check":
        parts = _parts(rest, 2)
        items = parts[2:]
        options = [{"key": items[i], "label": items[i + 1], "on": items[i + 2].upper() == "ON"}
                   for i in range(0, len(items) - 2, 3)]
        return Event("check", {"title": parts[0], "text": unescape(parts[1]), "options": options}, waits)
    if tag == "file":
        mode, title, text, start, exts = _parts(rest, 5)[:5]
        return Event("file", {"mode": mode or "file", "title": title, "text": unescape(text),
                              "start": start, "exts": exts.split()}, waits)
    if tag == "edit":
        title, path, note = _parts(rest, 3)[:3]
        return Event("edit", {"title": title, "path": path, "note": unescape(note)}, waits)
    if tag == "result":
        key, _, value = rest.partition("=")
        return Event("result", {"key": key, "value": unescape(value)})
    if tag == "cancel":
        return Event("cancel", {"on": rest.strip() == "on"})
    # A tag this reader does not know yet: kept, as a log line.
    return Event("log", {"text": line})


def _one_line(text: str) -> str:
    """A reply is one line: a new line inside it would answer the next question."""
    return " ".join(str(text).splitlines())


def reply_for(event: Event, answer: Any) -> str:
    """The reply line (without its new line) for the person's answer:
    ask -> bool; say, view -> anything; edit -> bool (saved);
    choose -> key or None; input -> text or None; file -> path or None;
    check -> list of keys or None. None or False means cancel or no."""
    kind = event.kind
    if kind == "ask":
        return "yes" if answer else "no"
    if kind in ("say", "view"):
        return "ok"
    if kind == "edit":
        return "ok" if answer else "cancel"
    if kind == "check":
        if answer is None:
            return "cancel"
        keys: Sequence[str] = answer
        return "ok " + "\t".join(_one_line(k).replace("\t", " ") for k in keys)
    if kind in ("choose", "file"):
        return f"ok {_one_line(answer)}" if answer else "cancel"
    if kind == "input":
        return "cancel" if answer is None else f"ok {_one_line(answer)}"
    raise ValueError(f"{kind} takes no reply")


@dataclass
class Progress:
    """Steps done of a routine with a known count (STEP_TOTALS), as the
    panel's loader draws them; fraction is None when the count is unknown."""
    total: int = 0
    steps: List[Tuple[str, Optional[int]]] = field(default_factory=list)
    stage: str = ""

    @classmethod
    def for_task(cls, name: str) -> "Progress":
        return cls(total=STEP_TOTALS.get(name, 0))

    def feed(self, event: Event) -> None:
        if event.kind == "step":
            self.steps.append((event.data["label"], None))
        elif event.kind == "done":
            label = event.data["label"]
            for i in range(len(self.steps) - 1, -1, -1):
                if self.steps[i][0] == label and self.steps[i][1] is None:
                    self.steps[i] = (label, event.data["rc"])
                    break
        elif event.kind == "stage":
            self.stage = event.data["stage"]

    @property
    def finished(self) -> int:
        return sum(1 for _, rc in self.steps if rc is not None)

    @property
    def fraction(self) -> Optional[float]:
        if not self.total:
            return None
        return min(self.finished, self.total) / self.total

    @property
    def failed(self) -> List[str]:
        return [label for label, rc in self.steps if rc not in (None, 0)]
