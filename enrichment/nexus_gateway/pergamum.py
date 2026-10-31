"""Searching Rede Pergamum (the PUCPR CRP catalogue) live, for the kind
pergamum target: its search page answers Sajax calls, and a search is two
kinds of GET on pesquisa.php:

  rs=ajax_resultados        the result list; each hit links mostrar_marc(<acervo id>)
  rs=ajax_conteudo_pastas   one record's tabs; the MARC text sits between
                            <inicio> and <fim>, one field a line

Only the server gateway does this: it runs when NEXUS_GATEWAY_PERGAMUM_URL
is set (the VPS behind sru.koha.nexus), and never from /sru/_union. Ported
from the retired bridge (sru-bridge/pergamum_sru, kept on the
backup/sru-bridge branch), whose parsing rules each come from a record Koha
refused.
"""

from __future__ import annotations

import concurrent.futures
import html
import http.cookiejar
import logging
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

from nexus_enrich import marc

log = logging.getLogger(__name__)

BASE_URL = "https://www.pergamum.pucpr.br/redepergamum/consultas/site_CRP/pesquisa.php"
# Pergamum answers a browser; Python's default agent is not what the
# working script sent.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
MAX_BYTES = 5_000_000
PAGE_SIZE = 50              # ids Pergamum lists per search (its "50" argument)
CONCURRENCY = 5             # MARC records fetched at once
DEFAULT_LEADER = "00000cam a2200000 a 4500"
SEARCH_TYPE = {"isbn": "ISBN", "author": "AUTOR"}       # else TITULO, also for keywords
RESULT_CEILING = 500        # Pergamum lists no hit at all past this many


class PergamumError(Exception):
    """Pergamum did not answer, or its page could not be read."""


class PergamumExcessiveResultsError(PergamumError):
    """Pergamum refused the search: more than RESULT_CEILING hits ("Resultado
    maior que 500 linhas. Refine melhor a busca !"). Its answer then lists no
    id, so without this the search read as 0 records; the term has to be
    narrowed (a longer title, author and title, an ISBN)."""

    def __init__(self, ptype: str = "", term: str = ""):
        self.ptype, self.term = ptype, term
        what = f" for {ptype} {term!r}" if term else ""
        super().__init__(f"Pergamum found more than {RESULT_CEILING} records{what} and lists none: "
                         "refine the search")


# ----------------------------------------------------------------------
# the pages
# ----------------------------------------------------------------------
_COUNT_RE = re.compile(r"N\S{0,8}?mero de Registros Encontrados\s*:?\s*(?:<[^>]*>\s*)*(\d[\d.]*)", re.I)
_ID_RE = re.compile(r"mostrar_marc\((\d+)\)")
_MARC_RE = re.compile(r"(?:<|&lt;)inicio(?:>|&gt;)(.*?)(?:<|&lt;)fim(?:>|&gt;)", re.S)
# "Resultado maior que 500 linhas. Refine melhor a busca !", whatever the
# page's encoding did to it and however it is wrapped.
_TOO_MANY_RE = re.compile(r"Resultado\s+maior\s+que\s+(\d[\d.]*)\s+linhas", re.I)
_SUBFIELD = re.compile(r"\$([a-zA-Z0-9])\s*([^$]+)")
# Characters XML 1.0 cannot carry (tab and newline are dealt with before).
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def search_type(kind: str) -> str:
    return SEARCH_TYPE.get(kind, "TITULO")


def sanitize_term(term: str, ptype: str) -> str:
    """The term without quotes and outer spaces; an ISBN keeps only its
    digits and X (Pergamum finds nothing for 978-85-...)."""
    t = term.strip().strip('"').strip("'").strip()
    if ptype == "ISBN":
        return re.sub(r"[^\dX]", "", t.upper())
    return t


def search_params(term: str, ptype: str, page_size: int = PAGE_SIZE) -> list[tuple[str, str]]:
    args = ["0", term, ptype, "obra", str(page_size), "", "", "", "-1"]
    return [("rs", "ajax_resultados"), ("rst", ""), ("rsrnd", "1234567890")] + [("rsargs[]", a) for a in args]


def record_params(acervo_id: str) -> list[tuple[str, str]]:
    return [("rs", "ajax_conteudo_pastas"), ("rst", ""), ("rsrnd", "1234567890"), ("rsargs[]", acervo_id)]


def too_many_results(page: str) -> bool:
    """Pergamum's answer is its "more than 500 lines" refusal."""
    return bool(_TOO_MANY_RE.search(html.unescape(page)))


def parse_results(page: str, ptype: str = "", term: str = "") -> tuple[int, list[str]]:
    """The count Pergamum reports (the ids listed when absent) and the
    acervo ids, in order. Raises PergamumExcessiveResultsError when
    Pergamum refused the search for having more than 500 hits."""
    if too_many_results(page):
        raise PergamumExcessiveResultsError(ptype, term)
    m = _COUNT_RE.search(page)
    count = int(m.group(1).replace(".", "")) if m else 0
    ids = list(dict.fromkeys(_ID_RE.findall(page)))
    return count or len(ids), ids


def extract_marc(page: str) -> str | None:
    m = _MARC_RE.search(page)
    return m.group(1) if m else None


def clean_text(block: str) -> str:
    """Line ends to \\n, entities decoded, separators out.

    Lines end in \\r alone: left in, the first tag reads "\\r0" and Koha
    stops with 'Tag "\\r0" is not a valid tag'. The Sajax answer may also
    carry them escaped (a backslash and an r)."""
    text = block.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text.replace("&nbsp;", " "))
    text = text.replace("\u001e", " ")
    return _XML_INVALID.sub(" ", text)


def text_to_record(block: str) -> marc.Record:
    """Pergamum's MARC tab ("245 10 $a Dom Casmurro / $c Machado de Assis.")
    as a record. A datafield with no subfield ("852    $") is dropped: Koha
    stops with "Field 852 must have at least one subfield"."""
    rec = marc.Record(leader=DEFAULT_LEADER)
    for raw_line in clean_text(block).split("\n"):
        line = raw_line.strip()
        if len(line) < 3:
            continue
        tag, rest = line[:3], line[3:].strip()
        if tag in ("LDR", "000"):
            if len(rest) == 24:
                rec.leader = rest
            continue
        if not tag.isdigit():
            continue
        if int(tag) < 10:
            if rest:
                rec.fields.append(marc.Field(tag, data=rest))
            continue
        ind1 = ind2 = " "
        if rest and not rest.startswith("$"):
            parts = rest.split("$", 1)
            inds = parts[0].replace(" ", "").replace("#", " ")
            if len(inds) >= 1:
                ind1 = inds[0]
            if len(inds) >= 2:
                ind2 = inds[1]
            rest = "$" + parts[1] if len(parts) > 1 else ""
        subfields = [(c, v.strip()) for c, v in _SUBFIELD.findall(rest) if v.strip()]
        if subfields:
            rec.fields.append(marc.Field(tag, ind1, ind2, subfields))
    return rec


# ----------------------------------------------------------------------
# the client
# ----------------------------------------------------------------------
class _Fetcher:
    """GETs that keep Pergamum's PHPSESSID cookie: its Sajax calls need the
    cookie its search page sets, so the page is opened once first."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self._lock = threading.Lock()
        self._has_session = False

    def _open(self, url: str, timeout: float) -> tuple[int, str]:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": self.base_url})
        try:
            with self.opener.open(req, timeout=timeout) as resp:          # noqa: S310 (http/https only)
                status, body, charset = resp.status, resp.read(MAX_BYTES + 1), resp.headers.get_content_charset()
        except urllib.error.HTTPError as exc:
            status, body, charset = exc.code, exc.read(MAX_BYTES + 1), exc.headers.get_content_charset()
        if len(body) > MAX_BYTES:
            raise PergamumError(f"Pergamum answered more than {MAX_BYTES} bytes")
        if charset:
            return status, body.decode(charset, "replace")
        try:
            return status, body.decode("utf-8")
        except UnicodeDecodeError:
            return status, body.decode("iso-8859-1")

    def __call__(self, params: list[tuple[str, str]], timeout: float) -> str:
        try:
            with self._lock:
                if not self._has_session:
                    self._open(self.base_url, timeout)
                    self._has_session = True
            status, body = self._open(self.base_url + "?" + urllib.parse.urlencode(params), timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise PergamumError(f"Pergamum did not answer: {type(exc).__name__}: {exc}") from exc
        # A search with no hits answers HTTP 500 with a valid Sajax body
        # ("+:..."): that is an empty result, not an error. The "more than
        # 500 lines" refusal goes to the parser whatever the status, so it
        # is reported as such and not as a bare HTTP error.
        if (status == 500 and body.startswith("+:")) or too_many_results(body):
            return body
        if status >= 400:
            raise PergamumError(f"Pergamum answered HTTP {status}")
        return body


class Pergamum:
    """One Pergamum address; thread-safe (the live loop runs searches in
    worker threads)."""

    def __init__(self, url: str = BASE_URL, get=None):
        self.url = url
        self.get = get or _Fetcher(url)

    def record(self, acervo_id: str, timeout: float) -> marc.Record | None:
        try:
            block = extract_marc(self.get(record_params(acervo_id), timeout))
        except PergamumError:
            return None
        if block is None:
            return None
        rec = text_to_record(block)
        return rec if rec.fields else None

    def search(self, kind: str, term: str, limit: int, timeout: float) -> tuple[int, list[marc.Record]]:
        """(the count Pergamum reports, the first `limit` records in its order)."""
        ptype = search_type(kind)
        clean = sanitize_term(term, ptype)
        if not clean:
            return 0, []
        try:
            count, ids = parse_results(self.get(search_params(clean, ptype), timeout), ptype, clean)
        except PergamumExcessiveResultsError:
            log.warning("Pergamum: %s %r has more than %d hits, Pergamum lists none; the search needs "
                        "refining", ptype, clean, RESULT_CEILING)
            raise
        ids = ids[:limit]
        if not ids:
            return 0, []
        with concurrent.futures.ThreadPoolExecutor(min(CONCURRENCY, len(ids))) as pool:
            records = [r for r in pool.map(lambda i: self.record(i, timeout), ids) if r is not None]
        return max(count, len(records)), records
