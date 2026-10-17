"""A job's scope: "all" (the whole catalogue) or biblionumbers such as
"101, 102, 500-550"."""

from __future__ import annotations

import re

MAX_IDS = 2_000_000


class ScopeError(ValueError):
    pass


def parse(text: str) -> list[tuple[int, int]] | None:
    """None for the whole catalogue, else sorted, merged (first, last)
    ranges."""
    text = (text or "").strip().lower()
    if text in ("", "all", "*"):
        return None
    ranges = []
    for part in re.split(r"[,\s;]+", text):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ScopeError(f"not a biblionumber or a range: {part!r}")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if a < 1 or b < a:
            raise ScopeError(f"not a valid range: {part!r}")
        ranges.append((a, b))
    if not ranges:
        return None
    ranges.sort()
    merged = [ranges[0]]
    for a, b in ranges[1:]:
        if a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    if sum(b - a + 1 for a, b in merged) > MAX_IDS:
        raise ScopeError(f"more than {MAX_IDS} biblionumbers: use the whole catalogue instead")
    return merged


def text(ranges: list[tuple[int, int]] | None) -> str:
    if ranges is None:
        return "all"
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges)


def ids(ranges: list[tuple[int, int]]):
    for a, b in ranges:
        yield from range(a, b + 1)
