"""The platforms this panel knows, and what is known about each on this server.

Koha is optional: the panel opens and stays usable on a server without it.
Four facts are kept apart for every platform, never folded into one
"operational" flag:

  supported  this version of the panel can install and administer it
             (Koha and Tainacan; AtoM and DSpace are planned)
  detected   an installation was found (Koha: its koha-conf.xml exists,
             the installer's is_koha_installed); None = not looked for
  services   its system services: active, partial, inactive, unknown, or
             none (nothing installed)
  health     a functional check (a search answers, a page shows records):
             unknown, healthy or failing. Koha's is not checked yet, so it
             stays "unknown" (not verified): a configuration file or a
             running service is no proof that the platform works.
             Tainacan's is: its collections API answers with JSON and
             lists as many published collections as its database has.

The installer reports the same facts in `config.sh --status-json` under
"platforms"; an older installer without that key still says
"koha_installed", which is read instead. Detection here is a file test
only: the panel never opens Koha's database to decide what to show.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .i18n import t

KOHA = "koha"
TAINACAN = "tainacan"

SERVICES = ("active", "partial", "inactive", "unknown", "none")
HEALTH = ("unknown", "healthy", "failing")


@dataclass(frozen=True)
class Platform:
    id: str
    name: str
    role: str          # one line: what it is for (an English key of the dictionaries)
    supported: bool


CATALOG: tuple[Platform, ...] = (
    Platform(KOHA, "Koha", "Library management: catalogue, patrons and circulation", True),
    Platform("tainacan", "Tainacan", "Digital collections and museum holdings", True),
    Platform("atom", "AtoM", "Archival description and access", False),
    Platform("dspace", "DSpace", "Institutional repository", False),
)


@dataclass(frozen=True)
class PlatformState:
    platform: Platform
    detected: bool | None = None
    services: str = "none"
    health: str = "unknown"
    units: tuple[tuple[str, str], ...] = ()

    @property
    def id(self) -> str:
        return self.platform.id

    @property
    def supported(self) -> bool:
        return self.platform.supported


def koha_conf(instance: str) -> Path:
    """The file whose presence means "Koha is installed" (installer:
    KOHA_CONF). KEI_KOHA_CONF points elsewhere for tests."""
    return Path(os.environ.get("KEI_KOHA_CONF") or f"/etc/koha/sites/{instance}/koha-conf.xml")


def koha_detected(env) -> bool:
    """Is Koha installed here? A file test, as the installer's
    is_koha_installed. Demo mode pretends it is, unless KEI_PANEL_DEMO_KOHA=0."""
    if getattr(env, "demo", False):
        return os.environ.get("KEI_PANEL_DEMO_KOHA", "1") != "0"
    return koha_conf(getattr(env, "instance", "library")).is_file()


def tainacan_state_file() -> Path:
    """Tainacan's state file (installer: KEI_TAINACAN_DIR/state). Its
    status=installed line means "Tainacan is installed here"."""
    base = os.environ.get("KEI_TAINACAN_DIR") or \
        os.path.join(os.environ.get("KEI_OWNED_DIR") or "/var/lib/koha-nexus", "platforms", "tainacan")
    return Path(base) / "state"


def tainacan_detected(env) -> bool:
    """Is Tainacan installed here? A file test, as for Koha: the status line
    of its state file. Demo mode pretends it is not, unless
    KEI_PANEL_DEMO_TAINACAN=1."""
    if getattr(env, "demo", False):
        return os.environ.get("KEI_PANEL_DEMO_TAINACAN", "0") == "1"
    try:
        lines = tainacan_state_file().read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    status = [ln.partition("=")[2] for ln in lines if ln.startswith("status=")]
    return bool(status) and status[-1] == "installed"


def _norm(value: object, allowed: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def from_status(status: dict | None) -> list[PlatformState]:
    """Every platform of the catalog with what --status-json says about it.
    Unknown ids in the JSON are left out; missing ones are "not looked for"."""
    status = status or {}
    reported = {p.get("id"): p for p in status.get("platforms") or [] if isinstance(p, dict)}
    if KOHA not in reported and "koha_installed" in status:
        # An installer older than the "platforms" key.
        reported[KOHA] = {"id": KOHA, "detected": bool(status.get("koha_installed")), "health": "unknown"}
    states = []
    for p in CATALOG:
        r = reported.get(p.id)
        if r is None:
            states.append(PlatformState(p))
            continue
        detected = r.get("detected")
        units = r.get("units") if isinstance(r.get("units"), dict) else {}
        states.append(PlatformState(
            p, detected=detected if isinstance(detected, bool) else None,
            services=_norm(r.get("services"), SERVICES, "unknown" if detected else "none"),
            health=_norm(r.get("health"), HEALTH, "unknown"),
            units=tuple((str(k), str(v)) for k, v in units.items())))
    return states


def describe(state: PlatformState) -> tuple[str, str, str]:
    """(value, note, card state) for a status card."""
    if not state.supported:
        return t("Planned"), t("Not available in this version of the panel"), ""
    if state.detected is None:
        return t("Unknown"), t("Not checked"), ""
    if not state.detected:
        return t("Not installed"), t("Optional: install it when you need it"), ""
    services = {
        "active": t("services running"), "partial": t("some services stopped"),
        "inactive": t("services stopped"), "unknown": t("services not read"),
    }.get(state.services, t("services not read"))
    health = {"healthy": t("healthy"), "failing": t("failing")}.get(state.health, t("health not verified"))
    card = "ok" if state.services == "active" and state.health != "failing" else (
        "bad" if state.services == "inactive" or state.health == "failing" else "warn")
    return t("Installed"), f"{services} · {health}", card


# The web server in front of the platforms (installer: kei_proxy_detect).
PROXY_MODES = ("none", "apache-nexus", "apache-shared", "external")


@dataclass(frozen=True)
class ProxyState:
    mode: str | None = None     # None = not reported (an older installer)
    server: str = ""
    sites: int = 0


def proxy_from_status(status: dict | None) -> ProxyState:
    """The "proxy" object of --status-json; unknown values are not trusted."""
    raw = (status or {}).get("proxy")
    if not isinstance(raw, dict):
        return ProxyState()
    mode = raw.get("mode") if raw.get("mode") in PROXY_MODES else None
    server = raw.get("server") if isinstance(raw.get("server"), str) else ""
    sites = raw.get("sites") if isinstance(raw.get("sites"), int) and raw.get("sites") >= 0 else 0
    return ProxyState(mode, server[:40], sites)


def describe_proxy(state: ProxyState) -> tuple[str, str, str]:
    """(value, note, card state) for the web proxy card. Read only: this
    version installs nothing in front of the platforms."""
    if state.mode is None:
        return t("Unknown"), t("Not checked"), ""
    if state.mode == "none":
        return t("No web server"), t("Nothing answers on ports 80 and 443"), ""
    if state.mode == "apache-nexus":
        return "Apache", t("Koha's sites only, plus ${n} of other platforms", n=state.sites), "ok"
    if state.mode == "apache-shared":
        return "Apache", t("Also serves other sites: they are never changed"), "warn"
    return state.server or t("Another web server"), \
        t("Another web server answers on 80/443: Koha.Nexus would only print its configuration block"), "warn"


# Docker, for the platforms in containers (installer: kei_docker_detect, the
# "docker" of --status-json). Optional: installed only when the person
# accepts the plan the installer shows (config.sh --task docker-plan).
@dataclass(frozen=True)
class DockerState:
    known: bool = False          # False = not reported (an older installer)
    installed: bool = False
    package: str = ""
    engine: str = ""
    compose: str = ""
    running: bool = False
    installed_by_nexus: bool = False
    others: int = 0              # containers of other programs
    networks: int = 0            # the platforms' networks


def _count(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _text(value, limit: int = 40) -> str:
    return value[:limit] if isinstance(value, str) else ""


def docker_from_status(status: dict | None) -> DockerState:
    """The "docker" object of --status-json; unknown values are not trusted."""
    raw = (status or {}).get("docker")
    if not isinstance(raw, dict):
        return DockerState()
    others = raw.get("others") if isinstance(raw.get("others"), dict) else {}
    return DockerState(
        known=True, installed=raw.get("installed") is True, package=_text(raw.get("package")),
        engine=_text(raw.get("engine")), compose=_text(raw.get("compose")), running=raw.get("running") is True,
        installed_by_nexus=raw.get("installed_by") == "koha-nexus", others=_count(others.get("containers")),
        networks=_count(raw.get("platform_networks")))


def describe_docker(state: DockerState) -> tuple[str, str, str]:
    """(value, note, card state) for the Docker card."""
    if not state.known:
        return t("Unknown"), t("Not checked"), ""
    if not state.installed:
        return t("Not installed"), t("Optional: only the platforms in containers need it"), ""
    value = f"Docker {state.engine}" if state.engine else "Docker"
    if not state.running:
        return value, t("Installed, but not running"), "warn"
    if not state.compose:
        return value, t("Without Compose v2, which the platforms need"), "warn"
    origin = t("Installed by Koha.Nexus") if state.installed_by_nexus else \
        t("Found on this server: used as it is, never changed")
    if state.others:
        origin += " · " + t("${n} containers of other programs", n=state.others)
    return value, origin, "ok"


def docker_can_install(state: DockerState) -> bool:
    """The install button: only when the installer says Docker is absent."""
    return state.known and not state.installed


def docker_can_remove(state: DockerState) -> bool:
    """The remove button: only a Docker Koha.Nexus installed, running, with
    no platform network and no container of anyone (the installer checks
    again, volumes and networks included)."""
    return state.installed_by_nexus and state.running and not state.networks and not state.others


# Tainacan (installer: kei_tainacan_*; its entry of "platforms" carries
# "status" and "url" too). Installed in containers, only after the plan
# and a Yes; its data is backed up and restored by the installer.
TAINACAN_STATUS = ("absent", "installing", "installed", "failed", "kept")


@dataclass(frozen=True)
class TainacanState:
    known: bool = False          # False = not reported (an older installer)
    status: str = "absent"
    url: str = ""
    services: str = "none"
    health: str = "unknown"
    events: str = "off"          # Nexus Eventos: "on" only after the plan and a Yes
    events_dependency: str = ""  # Events Manager: "ours" (Koha.Nexus put it there), "preexisting", ""
    admin_url: str = ""
    checked: tuple[tuple[str, str], ...] = ()   # the last diagnosis kept (installer: last-status)

    def check(self, key: str) -> str:
        return dict(self.checked).get(key, "")

    @property
    def checked_at(self) -> int:
        value = self.check("checked_at")
        return int(value) if value.isdigit() else 0

    @property
    def failed_at(self) -> int:
        """When the last diagnosis failed, if after the last good one."""
        value = self.check("failed_at")
        return int(value) if value.isdigit() and int(value) > self.checked_at else 0


# The fields of the last diagnosis the summary shows, and what each may hold.
CHECKED_FIELDS = {
    "checked_at": r"[0-9]{1,12}", "failed_at": r"[0-9]{1,12}",
    "collections": r"[0-9]{1,9}", "items": r"[0-9]{1,9}", "attachments": r"[0-9]{1,9}",
    "attachments_missing": r"[0-9]{1,9}",
    "wordpress_version": r"[0-9][0-9A-Za-z.+-]{0,30}", "tainacan_version": r"[0-9][0-9A-Za-z.+-]{0,30}",
    "disk_db": r"[0-9][0-9.]{0,9} ?[kKMGT]?i?B", "disk_wp": r"[0-9][0-9.]{0,9} ?[kKMGT]?i?B",
    "lang": r"[a-z]{2,3}(_[A-Z]{2})?",
}


def _checked(raw: object) -> tuple[tuple[str, str], ...]:
    import re
    if not isinstance(raw, dict):
        return ()
    return tuple((k, raw[k]) for k, pattern in CHECKED_FIELDS.items()
                 if isinstance(raw.get(k), str) and re.fullmatch(pattern, raw[k]))


def _web_url(value: object) -> str:
    return value[:200] if isinstance(value, str) and value.startswith(("http://", "https://")) \
        and not any(c.isspace() for c in value) else ""


def tainacan_from_status(status: dict | None) -> TainacanState:
    for raw in (status or {}).get("platforms") or []:
        if isinstance(raw, dict) and raw.get("id") == "tainacan" and raw.get("supported") is True:
            return TainacanState(
                known=True, status=_norm(raw.get("status"), TAINACAN_STATUS, "absent"),
                url=_web_url(raw.get("url")),
                services=_norm(raw.get("services"), SERVICES, "none"),
                health=_norm(raw.get("health"), HEALTH, "unknown"),
                events=_norm(raw.get("events"), ("off", "on"), "off"),
                events_dependency=_norm(raw.get("events_dependency"), ("ours", "preexisting"), ""),
                admin_url=_web_url(raw.get("admin_url")), checked=_checked(raw.get("checked")))
    return TainacanState()


def describe_tainacan(state: TainacanState, docker: DockerState) -> tuple[str, str, str]:
    """(value, note, card state) for the Tainacan card."""
    if not state.known:
        return t("Planned"), t("Not available in this version of the panel"), ""
    if state.status == "kept":
        return t("Not installed"), t("Its data was kept: installing it again uses it"), ""
    if state.status == "failed":
        return t("Installation incomplete"), t("Install again: it goes on where it stopped"), "warn"
    if state.status in ("absent", "installing"):
        if not docker.installed:
            return t("Not installed"), t("Needs Docker: install Docker first"), ""
        return t("Not installed"), t("Optional: install it when you need it"), ""
    services = {
        "active": t("services running"), "partial": t("some services stopped"),
        "inactive": t("services stopped"), "unknown": t("services not read"),
    }.get(state.services, t("services not read"))
    health = {"healthy": t("healthy"), "failing": t("failing")}.get(state.health, t("health not verified"))
    card = "ok" if state.services == "active" and state.health == "healthy" else (
        "bad" if state.services == "inactive" or state.health == "failing" else "warn")
    note = f"{services} · {health}"
    if state.events == "on":
        note += " · " + t("events on")
    if state.url:
        note += f" · {state.url}"
    return t("Installed"), note, card


def tainacan_can_install(state: TainacanState, docker: DockerState) -> bool:
    return state.known and state.status != "installed" and docker.installed and docker.running


def tainacan_installed(state: TainacanState) -> bool:
    return state.known and state.status == "installed"


# Events in Tainacan (installer: --task tainacan-events): optional and off
# until the person turns them on, after the plan and a Yes. The buttons only
# follow --status-json; the installer checks everything again.
def events_buttons(state: TainacanState, has_task: bool) -> dict[str, bool]:
    """Which events buttons the Tainacan card shows: none without Tainacan
    installed or with an installer that has no events tasks; "on" while they
    are off, "off" while they are on, and their state always."""
    if not (has_task and tainacan_installed(state)):
        return {"on": False, "off": False, "status": False}
    return {"on": state.events != "on", "off": state.events == "on", "status": True}


def events_off_choices(state: TainacanState) -> list[tuple[str, str]]:
    """What turning events off does to Events Manager, safest first: one
    that was there before stays on unless the person says otherwise; one
    Koha.Nexus installed goes off with them unless asked to stay. (key =
    the installer's argument: "" by default, keep-dependency, dependency.)"""
    if state.events_dependency == "ours":
        return [("default", t("Turn Events Manager off too (Koha.Nexus installed it)")),
                ("keep-dependency", t("Keep Events Manager on"))]
    return [("default", t("Keep Events Manager on: it was in this WordPress before")),
            ("dependency", t("Turn Events Manager off too (whatever else uses it stops)"))]


def missing_reason(platform: str) -> str:
    """Why a routine or a screen of `platform` cannot open on this server."""
    if platform == KOHA:
        return t("Koha is not installed on this server, so this is not available. "
                 "Install it with \"Install Koha server\" when you need it.")
    if platform == TAINACAN:
        return t("Tainacan is not installed on this server, so this is not available. "
                 "Install it in Platforms when you need it.")
    return t("This needs a platform that is not installed on this server.")


# The Tainacan summary (its section and the dashboard's tab): what
# --status-json and the backup engine already say, and the last diagnosis
# kept, with the time it was read. Nothing here reads the server.
def when(epoch: int) -> str:
    """"2026-11-05 14:30" in local time, or "" for 0."""
    import time
    if not epoch:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))


def tainacan_summary(state: TainacanState, docker: "DockerState", backups: "BackupState") -> dict[str, tuple[str, str, str]]:
    """Card id -> (value, note, card state) for the summary."""
    cards: dict[str, tuple[str, str, str]] = {"state": describe_tainacan(state, docker)}
    cards["events"] = (t("Turned on"), t("Nexus Eventos and Events Manager"), "ok") if state.events == "on" else \
        (t("Turned off"), t("Optional: turn them on in the Tainacan section"), "")
    if not backups.known:
        cards["backup"] = (t("Not checked"), "", "")
    elif backups.last:
        name, _sep, rest = backups.last.partition("|")
        created = rest.partition("|")[0]
        cards["backup"] = (created or name, t("${n} complete backups", n=backups.count), "ok")
    else:
        cards["backup"] = (t("None yet"), t("Back up in Platforms"), "warn")
    if backups.verified:
        bits = backups.verified.split()
        cards["restore-test"] = ((t("Passed") if bits[-1:] == ["ok"] else t("Failed")), " ".join(bits[:2]),
                                 "ok" if bits[-1:] == ["ok"] else "bad")
    else:
        cards["restore-test"] = (t("Not yet"), t("Test a restore in Platforms"), "warn" if backups.count else "")
    failed = t("The diagnosis at ${when} failed: run it again", when=when(state.failed_at)) \
        if state.failed_at else ""
    if state.checked_at:
        missing = state.check("attachments_missing")
        read = t("read at ${when}", when=when(state.checked_at))
        cards["content"] = (t("${c} collections · ${i} items · ${a} attachments", c=state.check("collections") or "?",
                              i=state.check("items") or "?", a=state.check("attachments") or "?"), f"{read} · {failed}" if failed else read,
                            "warn" if failed or (missing and missing != "0") else "ok")
        versions = []
        if state.check("wordpress_version"):
            versions.append(f"WordPress {state.check('wordpress_version')}")
        if state.check("tainacan_version"):
            versions.append(f"Tainacan {state.check('tainacan_version')}")
        disk = " + ".join(v for v in (state.check("disk_db"), state.check("disk_wp")) if v)
        cards["versions"] = (" · ".join(versions) or t("Not read"),
                             (t("Space") + f" {disk} · " if disk else "") + t("read at ${when}", when=when(state.checked_at)),
                             "")
    else:
        cards["content"] = (t("Not read yet"), failed or t("Run Diagnosis to read collections, items and attachments"),
                            "warn" if failed else "")
        cards["versions"] = (t("Not read yet"), t("Run Diagnosis to read the versions"), "")
    return cards


# Backups of the platforms (installer: kei_backup_*, the common engine):
# `--task platform-backup-status` reports key=value lines, read here. The
# installer decides everything again; the card only shows the state.
@dataclass(frozen=True)
class BackupState:
    known: bool = False          # False = not reported (an older installer)
    key: str = ""                # the fingerprint of the backup key, "" = not set up
    restic: str = ""             # restic's version, "" = not installed
    kit: str = ""                # the path of the recovery kit
    repo: str = ""               # Tainacan's restic repository, "" = self-contained packages
    copy: str = ""               # the cloud copy, REMOTE:PATH
    schedule: str = ""           # HH:MM, "" = off
    last: str = ""               # NAME|created|mode of the newest complete package
    count: int = 0
    incomplete: int = 0
    verified: str = ""           # "DATE TIME NAME ok|failed"
    maintained: str = ""



def backup_from_results(results: dict | None, platform: str = "tainacan") -> BackupState:
    import re
    r = results or {}
    if not r or "key" not in r:
        return BackupState()

    def val(key: str, limit: int = 200) -> str:
        v = r.get(key)
        return v[:limit] if isinstance(v, str) else ""

    def num(key: str) -> int:
        v = val(key, 9)
        return int(v) if v.isdigit() else 0

    key = val("key", 64)
    sched = val(f"{platform}.schedule", 5)
    return BackupState(
        known=True, key=key if re.fullmatch(r"[0-9A-F]{40,64}", key) else "",
        restic=val("restic", 20), kit=val("kit"), repo=val(f"{platform}.repo"),
        copy=val(f"{platform}.copy"), schedule=sched if re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", sched) else "",
        last=val(f"{platform}.last"), count=num(f"{platform}.count"),
        incomplete=num(f"{platform}.incomplete"), verified=val(f"{platform}.verified"),
        maintained=val(f"{platform}.maintained"))


def describe_backups(state: BackupState) -> tuple[str, str, str]:
    """(value, note, card state) for the "Platform backups" card."""
    if not state.known:
        return t("Not checked"), t("Not available in this version of the panel"), ""
    parts: list[str] = []
    if state.repo:
        parts.append(t("files in a restic repository") + (" (rclone)" if state.repo.startswith("rclone:") else ""))
    if state.copy:
        parts.append(t("copied to") + f" {state.copy}")
    parts.append((t("daily at") + f" {state.schedule}") if state.schedule else t("not scheduled"))
    if state.verified:
        bits = state.verified.split()
        when = " ".join(bits[:2])
        parts.append((t("last restore test passed") if bits[-1:] == ["ok"] else t("last restore test failed"))
                     + f" ({when})")
    else:
        parts.append(t("no restore test yet"))
    if state.incomplete:
        parts.append(t("incomplete backup to resume or discard"))
    value = t("Encrypted") if state.key else t("Configuration not encrypted")
    card = "ok" if state.key and state.schedule and not state.incomplete and state.verified.endswith(" ok") \
        else ("bad" if state.verified.endswith(" failed") else "warn")
    return value, " · ".join(parts), card
