"""The direct Z39.50 servers on-demand enrichment may ask: the "servers" of
panel/kei_panel/data/z3950_direct.json, and nothing else (not the list's
"fallback" block, not nexus_gateway/targets.json).

An entry is skipped, with its reason, when it is not protocol z3950, lacks
a host, port or database, or the policy refuses it (policy.name_refusal).
Alternates are checked the same way; a refused alternate is dropped.

A loaded server can still be unusable for now (Target.unusable): UNIMARC
servers are skipped in v1 (no conversion to MARC21 yet), and a server
with login_env needs <login_env>_USER in the environment (the unit reads
the panel's .env). Logins never come from the file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .policy import name_refusal

# In a checkout; the installer points NEXUS_ONDEMAND_DIRECT_LIST at its copy.
DEFAULT_LIST = Path(__file__).resolve().parents[2] / "panel" / "kei_panel" / "data" / "z3950_direct.json"
_LOGIN_ENV = re.compile(r"^KEI_Z3950_[A-Z0-9_]{1,40}$")
MARC21 = ("MARC21", "USMARC")

# Hosts that share one operator's infrastructure, so one limit covers them
# all (limits.py): (provider, host suffix or exact name).
PROVIDERS = (
    ("exlibris-alma", ".alma.exlibrisgroup.com"),
    ("loc", "loc.gov"),
)


def provider_of(host: str) -> str:
    """The operator HOST belongs to, or "" (then only its own limit applies)."""
    name = host.strip().lower().rstrip(".")
    for provider, suffix in PROVIDERS:
        if suffix.startswith("."):
            if name.endswith(suffix):
                return provider
        elif name == suffix or name.endswith("." + suffix):
            return provider
    return ""


@dataclass(frozen=True)
class Address:
    """One way to reach a catalogue."""
    host: str
    port: int
    db: str
    note: str = ""

    @property
    def key(self) -> str:
        """The health key: a breaker per address, so alternates have their own."""
        return f"{self.host.lower()}:{self.port}/{self.db}"

    @property
    def host_key(self) -> str:
        """The limit key: one session at a time per host and port."""
        return f"{self.host.lower()}:{self.port}"

    @property
    def provider(self) -> str:
        return provider_of(self.host)


@dataclass(frozen=True)
class Target:
    id: str
    name: str
    address: Address
    country: str = ""
    category: str = ""
    syntax: str = "MARC21"
    recordtype: str = "biblio"
    preselect: bool = False
    unconfirmed: bool = False
    login_env: str = ""
    user: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    alternates: tuple[Address, ...] = ()
    notes: str = ""
    covers: str = ""                        # the gateway target id of the same library ("sru_fallback")

    @property
    def addresses(self) -> tuple[Address, ...]:
        """The primary address, then the alternates, in the list's order."""
        return (self.address,) + self.alternates

    @property
    def unusable(self) -> str:
        """Why on-demand cannot ask this server now, or ""."""
        if self.syntax not in MARC21:
            return f"{self.syntax}, not merged in v1"
        if self.login_env and not self.user:
            return f"login needed ({self.login_env}_USER)"
        return ""


@dataclass
class Catalog:
    targets: dict[str, Target]
    skipped: list[tuple[str, str]]          # (id, reason)
    sha256: str = ""                        # of the list file: a change clears "misconfigured"

    def usable(self, recordtype: str = "biblio") -> list[Target]:
        return [t for t in self.targets.values() if t.recordtype == recordtype and not t.unusable]


class ListError(ValueError):
    """The list file is not a direct server list."""


def _address(raw: dict) -> tuple[Address | None, str]:
    host = str(raw.get("host", "")).strip()
    try:
        port = int(raw.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    db = str(raw.get("db", "")).strip()
    if not (host and port and db):
        return None, "needs host, port and db"
    reason = name_refusal(host, port, db)
    if reason:
        return None, f"refused by policy: {reason}"
    return Address(host, port, db, str(raw.get("note", ""))), ""


def make_target(raw: dict, env=os.environ) -> tuple[Target | None, str]:
    """(Target, "") or (None, why it is skipped)."""
    if str(raw.get("protocol", "z3950")).strip().lower() != "z3950":
        return None, f"protocol {raw.get('protocol')} is not z3950"
    address, why = _address(raw)
    if address is None:
        return None, why
    alternates = []
    for alt in raw.get("alternates") or []:
        a, _ = _address(alt) if isinstance(alt, dict) else (None, "")
        if a is not None and a != address:
            alternates.append(a)
    login_env = str(raw.get("login_env", "")).strip().upper()
    if login_env and not _LOGIN_ENV.match(login_env):
        return None, f"login_env {login_env!r} is not a KEI_Z3950_ name"
    user = env.get(login_env + "_USER", "") if login_env else ""
    password = env.get(login_env + "_PASSWORD", "") if login_env else ""
    return Target(
        id=str(raw["id"]).strip().lower(), name=str(raw.get("name") or raw["id"]), address=address,
        country=str(raw.get("country", "")).strip().upper()[:2], category=str(raw.get("category", "")),
        syntax=str(raw.get("syntax", "MARC21")).strip().upper(),
        recordtype=str(raw.get("recordtype", "biblio")).strip().lower(),
        preselect=bool(raw.get("preselect")), unconfirmed=bool(raw.get("unconfirmed")),
        login_env=login_env, user=user, password=password, alternates=tuple(alternates),
        notes=str(raw.get("notes", "")), covers=str(raw.get("sru_fallback", "")).strip().lower(),
    ), ""


def load(path: Path | str | None = None, env=os.environ) -> Catalog:
    path = Path(path or os.environ.get("NEXUS_ONDEMAND_DIRECT_LIST") or DEFAULT_LIST)
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ListError(f"{path}: not JSON ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("servers"), list):
        raise ListError(f"{path}: no \"servers\" list")
    targets: dict[str, Target] = {}
    skipped: list[tuple[str, str]] = []
    for entry in data["servers"]:
        sid = str(entry.get("id", "")).strip().lower() if isinstance(entry, dict) else ""
        if not sid:
            skipped.append(("?", "no id"))
            continue
        if sid in targets:
            skipped.append((sid, "listed twice"))
            continue
        target, why = make_target(entry, env)
        if target is None:
            skipped.append((sid, why))
        else:
            targets[sid] = target
    return Catalog(targets, skipped, hashlib.sha256(raw).hexdigest())
