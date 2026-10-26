"""Searching Catálogo Zeus (catalogo.bu.ufsc.br/zeus/) live, for the kind
zeus targets: Zeus is a federated catalogue whose search form lists other
libraries' catalogues as targets[n] checkboxes; one search asks one of them
and the result page carries each record as MARCXML (or a rawRecord ISO 2709
value).

Only the server gateway does this: it runs when NEXUS_GATEWAY_ZEUS_URL is
set (the VPS behind sru.koha.nexus); a library's own gateway leaves it unset.
/sru/_union asks Zeus once for all its catalogues (UNION_ID, search_many):
one page with every targets[n] ticked, as the old bridge did, up to 15 a
request.

targets.json's target_index values were never checked against the live
page, so the index searched is taken from the labels on Zeus's own search
form (fetched once, again after ZEUS_LABELS_TTL): a target whose name is on
the page is searched under that n; one that is not is not searched at all,
rather than under a guessed n that would bring another library's records.
"""

from __future__ import annotations

import html
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from nexus_enrich import marc

from .targets import Target

USER_AGENT = "Mozilla/5.0 (koha.nexus-gateway)"
MAX_BYTES = 20_000_000
ZEUS_LABELS_TTL = 6 * 3600          # the form is fetched again after this
LABELS_RETRY = 600                  # a failed fetch is tried again after this
SEARCH_TYPE = {"isbn": 7, "title": 4, "author": 1003, "keywords": 1016}
UNION_ID = "_zeus"                  # the one live "target" /sru/_union asks for every zeus catalogue
CHUNK = 15                          # Zeus refuses more targets[n] than this in one request


class ZeusError(Exception):
    """Zeus did not answer, or its page could not be read."""


# ----------------------------------------------------------------------
# the search form's labels
# ----------------------------------------------------------------------
_INPUT = re.compile(r"<input\b[^>]*\bname\s*=\s*[\"']?targets\[(\d+)\][\"']?[^>]*>", re.I)
_ID = re.compile(r"\bid\s*=\s*[\"']?([^\"'\s>]+)", re.I)
_SELECT = re.compile(r"<select\b[^>]*\bname\s*=\s*[\"']?targets[^>]*>(.*?)</select>", re.I | re.S)
_OPTION = re.compile(r"<option\b[^>]*\bvalue\s*=\s*[\"']?(\d+)[\"']?[^>]*>(.*?)</option>", re.I | re.S)
# The text after a checkbox ends at the next control, line break or list item.
_TEXT_END = re.compile(r"<(?:input|br|/?li|/?tr|/?td|/?p|/?div|/label)\b", re.I)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_labels(page: str) -> dict[int, str]:
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


def index_for(target: Target, labels: dict[int, str]) -> int | None:
    """The n whose label names the target: its target_index when that label
    matches, else the first label that does, else None."""
    if target.target_index in labels and names_match(target.name, labels[target.target_index]):
        return target.target_index
    for n in sorted(labels):
        if names_match(target.name, labels[n]):
            return n
    return None


def compare(targets: list[Target], labels: dict[int, str]) -> list[dict]:
    """One row per zeus target: the configured n, the n found, the label."""
    rows = []
    for t in targets:
        n = index_for(t, labels)
        rows.append({"id": t.id, "name": t.name, "target_index": t.target_index, "found": n,
                     "label": labels.get(n, "") if n is not None else ""})
    return rows


# ----------------------------------------------------------------------
# the result page
# ----------------------------------------------------------------------
_MARCXML = re.compile(r"<(?:marc:)?record\b[^>]*>.*?</(?:marc:)?record>", re.S | re.I)
_RAW_INPUT = re.compile(r"""<input\b[^>]*\bname\s*=\s*["']?rawRecord["']?[^>]*>""", re.I)
_VALUE = re.compile(r"""\bvalue\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_RAW_PARAM = re.compile(r"""rawRecord(?:=|%3D)([^"'&\s<>]+)""", re.I)


def _raw_values(page: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for m in _RAW_INPUT.finditer(page):
        v = _VALUE.search(m.group(0))
        if v:
            found.append((m.start(), v.group(1) if v.group(1) is not None else v.group(2)))
    for m in _RAW_PARAM.finditer(page):
        found.append((m.start(), m.group(1)))
    return [v for _, v in sorted(found) if v]


def _from_raw(value: str) -> marc.Record | None:
    data = urllib.parse.unquote_to_bytes(html.unescape(value.strip()).replace("+", " "))
    try:
        return marc.from_iso2709(data)
    except (marc.RecordError, ValueError, IndexError):
        pass
    try:            # offsets counted in characters, not bytes
        return marc.from_iso2709_text(data.decode("utf-8", "replace"))
    except (marc.RecordError, ValueError, IndexError):
        return None


def parse_results(page: str) -> list[marc.Record]:
    """Every record on a Zeus result page, in page order, without repeats."""
    out, seen = [], set()
    for m in _MARCXML.finditer(page):
        block = m.group(0)
        if "leader>" not in block or block in seen:
            continue
        seen.add(block)
        block = re.sub(r"<(/?)marc:", r"<\1", block)
        try:
            out.extend(marc.parse_xml(block)[:1])
        except (marc.RecordError, ValueError, SyntaxError):
            continue
    for value in _raw_values(page):
        if value in seen:
            continue
        seen.add(value)
        rec = _from_raw(value)
        if rec is not None:
            out.append(rec)
    return out


# ----------------------------------------------------------------------
# the client
# ----------------------------------------------------------------------
def _get(url: str, timeout: float) -> str:
    base = url.split("/zeus")[0] + "/"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": base,
                                               "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 (http/https only)
            body = resp.read(MAX_BYTES + 1)
            charset = resp.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ZeusError(f"Zeus did not answer: {type(exc).__name__}: {exc}") from exc
    if len(body) > MAX_BYTES:
        raise ZeusError(f"Zeus answered more than {MAX_BYTES} bytes")
    return body.decode(charset, "replace")


class Zeus:
    """One Catálogo Zeus address; thread-safe (the live loop runs searches
    in worker threads)."""

    def __init__(self, url: str, get=_get, members: list[Target] | None = None):
        self.url = url
        self.get = get
        self.members = list(members or [])      # the zeus catalogues /sru/_union searches
        self._labels: dict[int, str] | None = None
        self._labels_at = 0.0
        self._lock = threading.Lock()

    def labels(self, timeout: float = 20.0) -> dict[int, str]:
        with self._lock:
            age = time.monotonic() - self._labels_at
            if self._labels is not None and age < (ZEUS_LABELS_TTL if self._labels else LABELS_RETRY):
                return self._labels
            try:
                self._labels = parse_labels(self.get(self.url, timeout))
            except ZeusError:
                self._labels = self._labels or {}
            self._labels_at = time.monotonic()
            return self._labels

    def search(self, target: Target, kind: str, term: str, timeout: float) -> tuple[int, list[marc.Record]]:
        labels = self.labels(min(timeout, 20.0))
        if not labels:
            raise ZeusError("Zeus's search form could not be read, so no target can be picked")
        n = index_for(target, labels)
        if n is None:
            raise ZeusError(f"{target.name} is not among the targets on Zeus's search form")
        params = [("searchString", term), ("searchType", str(SEARCH_TYPE.get(kind, SEARCH_TYPE["keywords"]))),
                  ("operator", "and"), (f"targets[{n}]", "on")]
        page = self.get(self.url + ("&" if "?" in self.url else "?") + urllib.parse.urlencode(params), timeout)
        records = parse_results(page)
        return len(records), records

    def search_many(self, targets: list[Target], kind: str, term: str, timeout: float
                    ) -> tuple[int, list[marc.Record]]:
        """Every catalogue of `targets` that is on the form, in one request
        per CHUNK of them; records in page order, without repeats."""
        labels = self.labels(min(timeout, 20.0))
        if not labels:
            raise ZeusError("Zeus's search form could not be read, so no target can be picked")
        ns = sorted({n for n in (index_for(t, labels) for t in targets) if n is not None})
        if not ns:
            raise ZeusError("none of the catalogues is among the targets on Zeus's search form")
        records: list[marc.Record] = []
        seen: set[tuple[str, str]] = set()
        errors = []
        for i in range(0, len(ns), CHUNK):
            params = [("searchString", term), ("searchType", str(SEARCH_TYPE.get(kind, SEARCH_TYPE["keywords"]))),
                      ("operator", "and")] + [(f"targets[{n}]", "on") for n in ns[i:i + CHUNK]]
            try:
                page = self.get(self.url + ("&" if "?" in self.url else "?") + urllib.parse.urlencode(params), timeout)
            except ZeusError as exc:
                errors.append(exc)
                continue
            for rec in parse_results(page):
                key = (rec.control("001").strip(), " ".join(f.text() for f in rec.get_fields("245")))
                if key[0] and key in seen:
                    continue
                seen.add(key)
                records.append(rec)
        if errors and not records:
            raise errors[0]
        return len(records), records


def union_target() -> Target:
    """The live "target" that stands for every zeus catalogue in /sru/_union."""
    return Target(id=UNION_ID, name="Catálogo Zeus", kind="zeus", group="national", status="verified")
