"""Which catalogue each Zeus targets[n] is, read from Zeus's own search page.

targets.json gives every zeus entry a target_index (the n of targets[n] in a
Zeus search). This reads the labels Zeus shows next to each target on its
search form and compares them with targets.json, so the mapping can be
checked against the live page:

    python -m sru_gateway.zeus_labels                 # fetches ZEUS_SRU_BASE_URL
    python -m sru_gateway.zeus_labels --page zeus.html  # a page saved by hand

It prints one line per zeus entry and exits 1 when an index is absent from
the page or its label does not name the catalogue.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path

from . import targets as tg
from .config import TARGETS_FILE

_INPUT = re.compile(r"<input\b[^>]*\bname\s*=\s*[\"']?targets\[(\d+)\][\"']?[^>]*>", re.I)
_ID = re.compile(r"\bid\s*=\s*[\"']?([^\"'\s>]+)", re.I)
_SELECT = re.compile(r"<select\b[^>]*\bname\s*=\s*[\"']?targets[^>]*>(.*?)</select>", re.I | re.S)
_OPTION = re.compile(r"<option\b[^>]*\bvalue\s*=\s*[\"']?(\d+)[\"']?[^>]*>(.*?)</option>", re.I | re.S)
# The text after a checkbox ends at the next control, line break or list item.
_TEXT_END = re.compile(r"<(?:input|br|/?li|/?tr|/?td|/?p|/?div|/label)\b", re.I)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_target_labels(page: str) -> dict[int, str]:
    """{n: label} for every targets[n] checkbox (or targets select option)."""
    labels: dict[int, str] = {}
    for m in _INPUT.finditer(page):
        n, label = int(m.group(1)), ""
        id_m = _ID.search(m.group(0))
        if id_m:
            for_m = re.search(r"<label\b[^>]*\bfor\s*=\s*[\"']?" + re.escape(id_m.group(1)) +
                              r"[\"']?[^>]*>(.*?)</label>", page, re.I | re.S)
            if for_m:
                label = _text(for_m.group(1))
        if not label:
            rest = page[m.end():]
            end = _TEXT_END.search(rest)
            label = _text(rest[:end.start() if end else 300])
        labels.setdefault(n, label)
    for sel in _SELECT.finditer(page):
        for opt in _OPTION.finditer(sel.group(1)):
            labels.setdefault(int(opt.group(1)), _text(opt.group(2)))
    return labels


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def names_match(name: str, label: str) -> bool:
    """The label names the catalogue: its acronym in parentheses (UFSC, USP)
    as a word, or every word of four letters or more of the rest of the name."""
    folded = _fold(label)
    acronym = re.search(r"\(([^)]+)\)", name)
    if acronym and re.search(r"\b" + re.escape(_fold(acronym.group(1))) + r"\b", folded):
        return True
    words = [w for w in re.findall(r"\w+", _fold(name.split("(")[0])) if len(w) >= 4]
    return bool(words) and all(re.search(r"\b" + w + r"\b", folded) for w in words)


def compare(table: dict[str, tg.Target], labels: dict[int, str]) -> list[tuple[str, int, str, str, bool]]:
    """(id, index, name, label on the page, matches) for every zeus entry."""
    rows = []
    for t in table.values():
        if t.kind == "zeus":
            label = labels.get(t.target_index, "")
            rows.append((t.id, t.target_index, t.name, label, bool(label) and names_match(t.name, label)))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sru_gateway.zeus_labels", description=__doc__.split("\n\n")[0])
    ap.add_argument("--page", type=Path, help="a Zeus search page saved by hand (else it is fetched)")
    ap.add_argument("--targets", type=Path, default=TARGETS_FILE)
    args = ap.parse_args(argv)
    if args.page:
        page = args.page.read_text(encoding="utf-8", errors="replace")
    else:
        import httpx
        from zeus_sru.config import Settings as ZeusSettings
        url = ZeusSettings.from_env().base_url
        page = httpx.get(url, timeout=20, follow_redirects=True,
                         headers={"User-Agent": "koha.nexus-sru-gateway/1.0"}).text
    labels = parse_target_labels(page)
    if not labels:
        print("No targets[n] found on the page: save it from a browser and use --page.", file=sys.stderr)
        return 2
    rows = compare(tg.load(args.targets), labels)
    for tid, n, name, label, ok in rows:
        print(f"{'ok ' if ok else 'BAD'} targets[{n:>2}] {tid:<10} {name}  <->  {label or '(not on the page)'}")
    print("\nOn the page:", ", ".join(f"{n}={labels[n]}" for n in sorted(labels)))
    return 0 if all(r[4] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
