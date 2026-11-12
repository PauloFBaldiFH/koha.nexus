"""`config.sh --status-json` (schema 1) as dataclasses.

The installer prints one JSON object on stdout (kei_status_json in
`installer`, section 21.5); a wrapper may print other lines before it, so
the final complete JSON object is read, as Get-KohaLinuxStatus does.
Older serializers may place newlines inside that object. Every field has a default: an older installer that lacks a block, or
a value of the wrong type, reads as "nothing known" instead of failing.
Keys this module does not know are kept in `raw`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

SCHEMA = 1


def _int(v: Any) -> int:
    """A JSON number (or numeric string) as int; anything else is 0."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v.strip())
        except ValueError:
            return 0
    return 0


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _bool(v: Any) -> bool:
    return v is True or v == "true"


def _block(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    v = data.get(key)
    return v if isinstance(v, Mapping) else {}


@dataclass(frozen=True)
class Backup:
    """The newest SQL backup and the last line of backup_sql.log."""

    last_file: str = ""
    last_epoch: int = 0
    last_size: int = 0
    last_kind: str = "none"
    last_result: str = "none"   # ok | failed | skipped | none
    log_epoch: int = 0

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "Backup":
        return cls(_str(d.get("last_file")), _int(d.get("last_epoch")), _int(d.get("last_size")),
                   _str(d.get("last_kind")) or "none", _str(d.get("last_result")) or "none",
                   _int(d.get("log_epoch")))


@dataclass(frozen=True)
class Recovery:
    """The repair after an unclean stop (stop_guard_summary)."""

    epoch: int = 0
    state: str = "none"         # none | running | done
    finished: int = 0
    db: str = "-"               # ok | errors | unreachable | -
    backup: str = "-"           # ok | failed | -
    index: str = "-"            # ok | failed | -

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "Recovery":
        return cls(_int(d.get("epoch")), _str(d.get("state")) or "none", _int(d.get("finished")),
                   _str(d.get("db")) or "-", _str(d.get("backup")) or "-", _str(d.get("index")) or "-")


@dataclass(frozen=True)
class Access:
    """Where people reach Koha (kei_access_json)."""

    opac_port: int = 80
    staff_port: int = 8080
    lan_ip: str = ""
    lan_reachable: bool = False
    tunnel_mode: str = ""       # free | own | ""
    public_opac: str = ""
    public_staff: str = ""
    public_ip: str = ""

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "Access":
        return cls(_int(d.get("opac_port")) or 80, _int(d.get("staff_port")) or 8080, _str(d.get("lan_ip")),
                   _bool(d.get("lan_reachable")), _str(d.get("tunnel_mode")), _str(d.get("public_opac")),
                   _str(d.get("public_staff")), _str(d.get("public_ip")))


@dataclass(frozen=True)
class Space:
    """Bytes: the root filesystem ("disk") or the memory ("memory")."""

    total: int = 0
    free: int = 0


SUMMARY_STATES = ("ok", "attention", "critical", "stopped")
SUMMARY_OVERALL = SUMMARY_STATES + ("none",)


@dataclass(frozen=True)
class SystemSummary:
    """One installed system in "summary" (U7): koha, tainacan or dspace."""

    id: str
    name: str
    state: str                  # ok | attention | critical | stopped
    reason: str = ""


@dataclass(frozen=True)
class Summary:
    """Every system in one look (kei_panel/status_summary.py, study 11)."""

    state: str                  # ok | attention | critical | stopped | none
    checked_at: int = 0
    systems: tuple = ()

    @classmethod
    def from_json(cls, d: Any) -> Optional["Summary"]:
        """None for an older installer (no block), null or a bad block."""
        if not isinstance(d, Mapping) or d.get("state") not in SUMMARY_OVERALL:
            return None
        systems = []
        for row in d.get("systems") if isinstance(d.get("systems"), list) else []:
            if (isinstance(row, Mapping) and row.get("id") in ("koha", "tainacan", "dspace")
                    and row.get("state") in SUMMARY_STATES and _str(row.get("name")).strip()):
                systems.append(SystemSummary(row["id"], _str(row["name"]).strip()[:120], row["state"],
                                             _str(row.get("reason"))[:48]))
        return cls(d["state"], _int(d.get("checked_at")), tuple(systems))


@dataclass(frozen=True)
class LinuxStatus:
    """Koha's own view of itself, as config.sh --status-json prints it."""

    schema: int = 0
    generated_at: int = 0
    panel_version: str = ""
    platform: str = ""
    wsl_net: str = ""
    autostart: str = ""
    state: str = ""             # ok | degraded | stopped | not_installed
    koha_installed: bool = False
    services: Dict[str, str] = field(default_factory=dict)   # unit -> systemctl is-active
    plack: bool = False
    http_staff: int = 0         # HTTP code, 0 when nothing answers
    http_opac: int = 0
    backup: Backup = field(default_factory=Backup)
    recovery: Recovery = field(default_factory=Recovery)
    access: Access = field(default_factory=Access)
    disk: Space = field(default_factory=Space)
    memory: Space = field(default_factory=Space)
    summary: Optional[Summary] = None      # U7; None from an older installer
    raw: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "LinuxStatus":
        services = {str(k): _str(v) or "unknown" for k, v in _block(data, "services").items()}
        http = _block(data, "http")
        disk = _block(data, "disk")
        mem = _block(data, "memory")
        return cls(
            schema=_int(data.get("schema")),
            generated_at=_int(data.get("generated_at")),
            panel_version=_str(data.get("panel_version")),
            platform=_str(data.get("platform")),
            wsl_net=_str(data.get("wsl_net")),
            autostart=_str(data.get("autostart")),
            state=_str(data.get("state")),
            koha_installed=_bool(data.get("koha_installed")),
            services=services,
            plack=_bool(data.get("plack")),
            http_staff=_int(http.get("staff")),
            http_opac=_int(http.get("opac")),
            backup=Backup.from_json(_block(data, "backup")),
            recovery=Recovery.from_json(_block(data, "recovery")),
            access=Access.from_json(_block(data, "access")),
            disk=Space(_int(disk.get("total")), _int(disk.get("free"))),
            memory=Space(_int(mem.get("total")), _int(mem.get("available"))),
            summary=Summary.from_json(data.get("summary")),
            raw=dict(data),
        )

    def service(self, unit: str) -> str:
        """systemctl is-active of one unit, "unknown" when not listed."""
        return self.services.get(unit, "unknown")


def last_json_line(output: str) -> Optional[Dict[str, Any]]:
    """Read a complete final object after optional legacy text/older objects.

    Consume objects from their opening line. A malformed/truncated object
    cannot fall back to a nested object's line and look like a valid status.
    The public function name is kept for compatibility with older clients.
    """
    output = output or ""
    if len(output) > 4 * 1024 * 1024:
        return None
    decoder = json.JSONDecoder()
    position = 0
    while position < len(output):
        newline = output.find("\n", position)
        line_end = newline if newline >= 0 else len(output)
        line = output[position:line_end]
        if not line.lstrip().startswith("{"):
            position = line_end + 1
            continue
        start = position + len(line) - len(line.lstrip())
        try:
            data, end = decoder.raw_decode(output, start)
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        if not output[end:].strip():
            return data
        # Only a new line may separate a completed older object from the
        # preamble/response that follows it; trailing inline text is invalid.
        newline = output.find("\n", end)
        if newline < 0 or output[end:newline].strip():
            return None
        position = newline + 1
    return None


def parse_status(output: str) -> Optional[LinuxStatus]:
    """The output of `config.sh --status-json` as a LinuxStatus, or None.

    A newer schema is still read: fields keep their schema-1 meaning, and
    new ones stay in `raw`, so an old client never stops working when the
    installer adds a field."""
    data = last_json_line(output)
    if data is None:
        return None
    return LinuxStatus.from_json(data)
