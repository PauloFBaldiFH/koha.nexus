"""The "summary" block of --status-json (study 11, U7): every system in one look.

config.sh builds the rest of --status-json and pipes the parts this needs
into `python -m kei_panel.status_summary` (stdin: one JSON object with
"state", "services", "http", "backup", "platforms", "docker", "names",
"generated_at"); the block is printed on stdout. The Windows tray, the
panel and nexus_core read it; none of them computes it again.

    {"state": "attention", "checked_at": 1794390000,
     "systems": [{"id": "koha", "name": "Biblioteca Central", "state": "ok", "reason": ""},
                 {"id": "dspace", "name": "Repositório Institucional",
                  "state": "attention", "reason": "installing"}]}

A system's state:
    ok         installed and answering (Koha: HTTP of the application;
               Tainacan: WordPress's health check)
    attention  needs a look: installing, a late or failed backup, unknown
    critical   a needed part is down: its database, the application, the
               web server or Docker
    stopped    stopped on purpose (DSpace stopped from the panel, Koha's
               services all off): not counted while others run
Only installed systems are listed. The overall state is the worst of the
systems that are not stopped: "none" without any system, "stopped" when
every one is stopped.

Standard library only: config.sh runs it without the panel's packages.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping

SYSTEMS = (("koha", "Koha"), ("tainacan", "Tainacan"), ("dspace", "DSpace"))
ORDER = {"ok": 0, "attention": 1, "critical": 2}
BACKUP_LATE_S = 3 * 86400          # the nightly SQL backup: three nights missed


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int(value: Any) -> int:
    try:
        return int(value) if not isinstance(value, bool) else 0
    except (TypeError, ValueError):
        return 0


def koha(data: Mapping[str, Any], now: int) -> tuple[str, str] | None:
    state = data.get("state")
    if state not in ("ok", "degraded", "stopped"):
        return None                                       # not installed (or an unknown word)
    services = _map(data.get("services"))
    staff = _int(_map(data.get("http")).get("staff"))
    if state == "stopped":
        return "stopped", "stopped"
    if state == "degraded":
        if services.get("mariadb") != "active":
            return "critical", "database_stopped"
        if services.get("apache2") != "active":
            return "critical", "web_server_stopped"
        if not staff or staff >= 500:
            return "critical", "not_responding"
        return "attention", "services_partial"
    backup = _map(data.get("backup"))
    if backup.get("last_result") == "failed":
        return "attention", "backup_failed"
    last = _int(backup.get("last_epoch"))
    if last and now - last > BACKUP_LATE_S:
        return "attention", "backup_late"
    return "ok", ""


def tainacan(row: Mapping[str, Any], docker: Mapping[str, Any]) -> tuple[str, str] | None:
    if row.get("detected") is not True:
        return None
    status = row.get("status")
    if status == "installing":
        return "attention", "installing"
    if status == "failed":
        return "critical", "install_failed"
    if status != "installed":
        return "attention", "unknown"
    services = row.get("services")
    if services == "unknown" or docker.get("running") is False:
        return "critical", "docker_stopped"
    if services == "inactive":
        return "critical", "not_running"
    if services != "active":
        return "critical", "services_partial"
    if row.get("health") == "failing":
        return "critical", "not_responding"
    if row.get("health") != "healthy":
        return "attention", "not_checked"
    return "ok", ""


def dspace(row: Mapping[str, Any]) -> tuple[str, str] | None:
    if row.get("detected") is not True:
        return None
    detail = _map(row.get("detail"))
    status = detail.get("status")
    if status in (None, "absent"):
        return None
    if status == "installed":
        return ("ok", "") if row.get("services") == "active" else ("critical", "services_partial")
    if status == "stopped":
        return "stopped", "stopped"
    if status == "installing":
        return "attention", "installing"
    if status == "failed":
        return "critical", "install_failed"
    if status == "unavailable":
        return "critical", "docker_stopped"
    if status == "degraded":
        return "critical", "services_partial"
    return "attention", "unknown"


def summary(data: Mapping[str, Any], now: int | None = None) -> dict:
    now = _int(data.get("generated_at")) if now is None else now
    rows = {r.get("id"): r for r in data.get("platforms") or [] if isinstance(r, Mapping)}
    docker = _map(data.get("docker"))
    names = _map(data.get("names"))
    apache = _map(data.get("services")).get("apache2")
    found = {"koha": koha(data, now), "tainacan": tainacan(_map(rows.get("tainacan")), docker),
             "dspace": dspace(_map(rows.get("dspace")))}
    systems = []
    for key, system in SYSTEMS:
        seen = found[key]
        if seen is None:
            continue
        state, reason = seen
        # Apache is shared: Koha needs it, and it publishes the others.
        if apache not in (None, "active") and state in ("ok", "attention") and key == "koha":
            state, reason = "critical", "web_server_stopped"
        name = names.get(key) if isinstance(names.get(key), str) and names.get(key).strip() else system
        systems.append({"id": key, "name": name.strip(), "state": state, "reason": reason})
    counted = [s["state"] for s in systems if s["state"] != "stopped"]
    if not systems:
        overall = "none"
    elif not counted:
        overall = "stopped"
    else:
        overall = max(counted, key=ORDER.__getitem__)
    return {"state": overall, "checked_at": now, "systems": systems}


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if not isinstance(data, dict):
            raise ValueError
        print(json.dumps(summary(data), ensure_ascii=False, separators=(",", ":")))
    except Exception:  # noqa: BLE001 - --status-json stays valid: "summary": null
        print("null")
    return 0


if __name__ == "__main__":
    sys.exit(main())
