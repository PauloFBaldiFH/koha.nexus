"""The "Addresses and access" screen of each system (study 17.4).

Three things are kept apart, so that no address is called usable without a
test:

  configured    the address the application builds its links and
                redirections with (Koha OPACBaseURL / staffClientBaseURL,
                WordPress home, DSpace's URL): the only one with "use this"
  alternatives  other names of this server for the same port (localhost,
                its other network addresses), with the effect to expect
  checked       each test says where it was made from and when: "from this
                server" (the installer's addresses test); from Windows only
                after the Windows side tested it (U7: until then "? not
                checked from Windows")

The installer (`--task addresses PLATFORM [test]`) gives the addresses; the
panel only reads them here.
"""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .i18n import t

KIND_NAMES = {"opac": "OPAC", "staff": "Staff interface", "site": "Site"}
PREFERENCE = {"opac": "OPACBaseURL", "staff": "staffClientBaseURL"}

# What another name of the server does, by system, before any test.
EXPECTED = {
    "koha": "Opens, but Koha's links and redirections go to the configured address",
    "tainacan": "WordPress sends it to the configured address; login works only there",
    "dspace": "May fail: DSpace answers fully only at the configured address",
}


@dataclass
class Check:
    code: str
    redirect: str = ""
    at: int = 0


@dataclass
class Addresses:
    platform: str
    host_platform: str = "linux"          # "wsl": Windows reaches it through WSL
    configured: list[tuple[str, str]] = field(default_factory=list)
    unset: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, str]] = field(default_factory=list)
    checks: dict[str, Check] = field(default_factory=dict)


def _url(value: str) -> str:
    """An http(s) address with a host, else ""."""
    try:
        parts = urlsplit(value or "")
    except ValueError:
        return ""
    return value if parts.scheme in ("http", "https") and parts.hostname else ""


def parse(platform: str, out) -> Addresses:
    """From `--task addresses` (a TaskOutcome)."""
    a = Addresses(platform)
    if out is None:
        return a
    a.host_platform = out.get("platform") or "linux"

    def rows(key: str) -> list[str]:
        return out.lists.get(key) or ([out.get(key)] if out.get(key) else [])

    for row in rows("configured"):
        kind, _, url = row.partition("|")
        if kind in KIND_NAMES and _url(url):
            a.configured.append((kind, url))
    a.unset = [k for k in rows("unset") if k in PREFERENCE]
    for row in rows("alternative"):
        kind, _, url = row.partition("|")
        if kind in KIND_NAMES and _url(url):
            a.alternatives.append((kind, url))
    for row in rows("check"):
        parts = row.split("|")
        if len(parts) == 4 and _url(parts[0]):
            url, code, redirect, at = parts
            a.checks[url] = Check(code if code.isdigit() else "000", redirect if _url(redirect) else "",
                                  int(at) if at.isdigit() else 0)
    return a


def is_local(url: str) -> bool:
    """localhost or an address of a private network: not on the internet."""
    host = urlsplit(url).hostname or ""
    if host == "localhost" or "." not in host:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def ago(at: int, now: float | None = None) -> str:
    seconds = max(0, int((now or time.time()) - at))
    if seconds < 90:
        return t("just now")
    if seconds < 5400:
        return t("${n} min ago", n=seconds // 60)
    return t("${n} h ago", n=seconds // 3600)


def check_text(check: Check | None, now: float | None = None) -> tuple[str, str]:
    """(line, state) for a configured address."""
    if check is None:
        return t("? not checked yet: press Test access"), ""
    when = ago(check.at, now)
    code = int(check.code) if check.code.isdigit() else 0
    if 200 <= code < 400:
        return t("✓ answered from this server (HTTP ${code}, ${when})", code=check.code, when=when), "ok"
    if code:
        return t("✖ error from this server (HTTP ${code}, ${when})", code=check.code, when=when), "bad"
    return t("✖ no answer from this server (${when})", when=when), "bad"


def _same_site(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.hostname, pa.port) == (pb.scheme, pb.hostname, pb.port)


def alternative_text(platform: str, url: str, configured: list[tuple[str, str]], check: Check | None) -> str:
    """The effect to expect from another name of the server."""
    if check is not None:
        code = int(check.code) if check.code.isdigit() else 0
        if check.redirect and any(_same_site(check.redirect, c) for _k, c in configured):
            return t("Leads to the configured address")
        if not code:
            return t("No answer from this server")
        if code >= 400:
            return t("Error (HTTP ${code})", code=check.code)
    return t(EXPECTED.get(platform, ""))


def internet_text(platform: str, a: Addresses, public: list[str]) -> str:
    """The addresses on the internet: a tunnel's or a public configured one."""
    shown = [u for u in public if u] + [u for _k, u in a.configured if not is_local(u) and u not in public]
    return ", ".join(dict.fromkeys(shown)) if shown else t("Not published")
