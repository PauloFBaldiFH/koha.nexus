"""The platforms this panel knows, and what is known about each on this server.

Koha is optional: the panel opens and stays usable on a server without it.
Four facts are kept apart for every platform, never folded into one
"operational" flag:

  supported  this version of the panel can install and administer it
             (Koha only, for now; Tainacan, AtoM and DSpace are planned)
  detected   an installation was found (Koha: its koha-conf.xml exists,
             the installer's is_koha_installed); None = not looked for
  services   its system services: active, partial, inactive, unknown, or
             none (nothing installed)
  health     a functional check (a search answers, a page shows records):
             unknown, healthy or failing. Nothing checks it yet, so it is
             always "unknown" (not verified): a configuration file or a
             running service is no proof that the platform works.

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
    Platform("tainacan", "Tainacan", "Digital collections and museum holdings", False),
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


def missing_reason(platform: str) -> str:
    """Why a routine or a screen of `platform` cannot open on this server."""
    if platform == KOHA:
        return t("Koha is not installed on this server, so this is not available. "
                 "Install it with \"Install Koha server\" when you need it.")
    return t("This needs a platform that is not installed on this server.")
