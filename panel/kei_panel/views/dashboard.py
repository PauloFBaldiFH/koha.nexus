"""DashboardView: Koha's state at a glance, read from --status-json, the
addresses Koha answers on (Open / Copy), the server's health (read by the
panel itself, see health.py) and three quick actions: restart Koha, export
diagnostics and open the saved ones (screens/diagnostics.py).

The status is loaded in a worker with a one-line Pac-Man inside the view
(the same PacmanLoader as the modal, compact): a quick read does not need
to cover the screen, but it still never blocks it.
"""

from __future__ import annotations

import time

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button, Label

from .. import health
from ..i18n import t
from ..widgets.cards import LinkCard, StatusCard
from ..widgets.pacman import PacmanLoader
from .base import SectionView


def human_bytes(n: int | None) -> str:
    if not n:
        return "-"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return str(n)


def age(epoch: int | None, now: float | None = None) -> str:
    if not epoch:
        return "-"
    secs = max(0, int(time.time() if now is None else now) - int(epoch))
    if secs < 3600:
        return f"{secs // 60} min"
    if secs < 86400:
        return f"{secs // 3600} h"
    return f"{secs // 86400} d"


# The nightly backup runs once a day: over a day without one means a night
# was missed. (The validation report's "Backup SQL" line allows two days.)
BACKUP_FRESH_SECS = 86400


def backup_card(b: dict | None, now: float | None = None) -> tuple[str, str, str]:
    """The "Last backup" card from --status-json's "backup" block: the date
    and time of the newest backup (from its name, else its mtime: see the
    installer's latest_sql_backup), how long ago and which file. Green while
    it is under a day old and the last nightly run did not fail."""
    b = b or {}
    try:
        epoch = int(b.get("last_epoch") or 0)
    except (TypeError, ValueError):
        epoch = 0
    if epoch <= 0:
        return t("None yet"), t("No backup on this server yet"), "warn"
    now = time.time() if now is None else now
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))
    note = t("${age} ago", age=age(epoch, now)) + f" · {b.get('last_file') or '-'}"
    if now - epoch >= BACKUP_FRESH_SECS:
        note = t("No backup for ${age}", age=age(epoch, now)) + f" · {b.get('last_file') or '-'}"
    elif b.get("last_result") == "failed":
        note = t("The last nightly backup failed") + f" · {note}"
    else:
        return when, note, "ok"
    return when, note, "warn"


# The components the Koha window on Windows lists, in the order Koha needs
# them (KohaServices in windows/KohaEasy.Core.psm1), then the staff page.
COMPONENTS = (
    ("mariadb", "MariaDB"),
    ("apache2", "Apache"),
    ("rabbitmq-server", "RabbitMQ"),
    ("memcached", "Memcached"),
    ("koha-common", "Koha (koha-common)"),
)

# kei_overall_state in the installer: ok | degraded | stopped | not_installed.
OVERALL = {
    "ok": ("Running", "ok"),
    "running": ("Running", "ok"),
    "degraded": ("Attention", "warn"),
    "stopped": ("Stopped", "bad"),
    "not_installed": ("not installed", "warn"),
}


def unit_state(active: str | None) -> tuple[str, str]:
    """systemctl is-active as the Koha window shows it: text and card state."""
    if active == "active":
        return "Running", "ok"
    if active in ("activating", "reloading"):
        return "Starting", "warn"
    if active == "failed":
        return "Failed", "bad"
    if active in ("inactive", "deactivating"):
        return "Stopped", "bad"
    return "Unknown", "warn"


# The address cards: (where, page). Columns are where the browser is, rows
# the catalog then the staff interface.
WHERES = ("local", "lan", "public")
PAGES = ("opac", "staff")
LINK_TITLES = {
    ("local", "opac"): "Catalog (this computer)", ("lan", "opac"): "Catalog (local network)",
    ("public", "opac"): "Catalog (Internet)", ("local", "staff"): "Staff (this computer)",
    ("lan", "staff"): "Staff (local network)", ("public", "staff"): "Staff (Internet)",
}


def http_url(host: str, port: int) -> str:
    return f"http://{host}" if port == 80 else f"http://{host}:{port}"


def access_links(s: dict) -> dict[tuple[str, str], tuple[str, str, str]]:
    """--status-json's "access" (and "services") as (where, page) ->
    (url, note, card state). An empty url means none, the note says why."""
    a = s.get("access") or {}
    ports = {"opac": int(a.get("opac_port") or 80), "staff": int(a.get("staff_port") or 8080)}
    links: dict[tuple[str, str], tuple[str, str, str]] = {}
    for page in PAGES:
        links[("local", page)] = (http_url("localhost", ports[page]), t("On the server itself"), "")
        ip = a.get("lan_ip") or ""
        if a.get("lan_reachable") and ip:
            links[("lan", page)] = (http_url(ip, ports[page]), t("Other computers on the network"), "")
        elif s.get("platform", "").startswith("wsl"):
            links[("lan", page)] = ("", t("Not reachable from other computers (WSL NAT networking)"), "")
        else:
            links[("lan", page)] = ("", t("No local network address"), "")
    online = (s.get("services") or {}).get("cloudflared") == "active"
    mode = a.get("tunnel_mode") or ""
    where = t("Free koha.nexus address") if mode == "free" else t("Cloudflare Tunnel")
    for page in PAGES:
        host = a.get(f"public_{page}") or ""
        if host:
            links[("public", page)] = (f"https://{host}", f"{where} · {t('online') if online else t('offline')}",
                                       "ok" if online else "bad")
        elif mode == "free" and page == "staff":
            links[("public", page)] = ("", t("Remote staff access is off"), "")
        elif a.get("public_ip"):
            # A cloud server on a private address (10.0.0.60): the address
            # the Internet sees, which works once the cloud firewall lets
            # ports 80 and 8080 in.
            links[("public", page)] = (http_url(a["public_ip"], ports[page]),
                                       t("Public IP: open ports 80 and 8080 in the cloud firewall, or use a "
                                         "Cloudflare Tunnel"), "")
        else:
            links[("public", page)] = ("", t("Not published on the Internet"), "")
    return links


# ----------------------------------------------------------------------
# Health: one card per fact, (value, note, state) like backup_card. A fact
# the panel could not read is "-" with a quiet note, never red.
# ----------------------------------------------------------------------
HEALTH_CARDS = (
    ("cpu", "CPU"), ("memory", "Memory"), ("db", "Database"),
    ("backup-dir", "Backup folder"), ("errors", "Errors (last 24 h)"), ("updates", "Updates"),
    ("tunnel", "Cloudflare Tunnel"), ("sru", "SRU gateway (sru.koha.nexus)"), ("z3950", "Z39.50 servers"),
)
UNREAD = ("-", "Could not read", "")


def _unread() -> tuple[str, str, str]:
    return UNREAD[0], t(UNREAD[1]), UNREAD[2]


def cpu_card(cpu: dict | None) -> tuple[str, str, str]:
    if not cpu or cpu.get("busy") is None:
        return _unread()
    busy, cores = cpu["busy"], int(cpu.get("cores") or 1)
    note = t("${n} cores", n=cores) + f" · {t('load')} {cpu.get('load', 0):.2f}"
    return t("${pct}% in use", pct=f"{busy:.0f}"), note, "warn" if busy >= 90 else "ok"


def memory_card(m: dict | None) -> tuple[str, str, str]:
    m = m or {}
    total, avail = int(m.get("total") or 0), int(m.get("available") or 0)
    if total <= 0:
        return _unread()
    used = max(0, total - avail)
    pct = 100 * used / total
    note = t("${pct}% used", pct=f"{pct:.0f}") + " · " + t("${size} free", size=human_bytes(avail))
    return f"{human_bytes(used)} / {human_bytes(total)}", note, "bad" if pct >= 95 else "warn" if pct >= 85 else "ok"


def db_card(size: int | None, instance: str = "library") -> tuple[str, str, str]:
    if size is None:
        return _unread()
    return human_bytes(size) if size else "0 B", f"koha_{instance}", "ok"


def backup_dir_card(backups: dict | None, disk: dict | None, last_size: int = 0) -> tuple[str, str, str]:
    """The backup folders' size and whether the disk still has room: two
    more backups the size of the last one, and a tenth of the disk."""
    if backups is None:
        return _unread()
    disk = disk or {}
    free, total = int(disk.get("free") or 0), int(disk.get("total") or 0)
    value = human_bytes(backups.get("bytes")) if backups.get("bytes") else "0 B"
    if total and (free < 2 * last_size or free / total < 0.1):
        return value, t("Low disk space: the next backups may not fit") + f" ({human_bytes(free)})", "bad"
    return value, t("${n} files", n=backups.get("files", 0)), "ok"


def errors_card(apache: dict | None, koha: dict | None, now: float | None = None) -> tuple[str, str, str]:
    if apache is None and koha is None:
        return _unread()
    a, k = (apache or {}).get("count", 0), (koha or {}).get("count", 0)
    counts = f"Apache {a if apache is not None else '-'} · Koha {k if koha is not None else '-'}"
    if not a and not k:
        return t("No errors"), counts, "ok"
    newest = max((x for x in (apache, koha) if x and x.get("count")), key=lambda x: x.get("last_epoch", 0))
    when = t("${age} ago", age=age(int(newest.get("last_epoch") or 0), now))
    note = f"{counts} · {when}: {health.short_error(newest.get('last', ''), 50)}"
    return t("${n} errors", n=a + k), note, "warn"


def tunnel_card(check: dict | None, status: dict) -> tuple[str, str, str]:
    host = health.tunnel_host(status)
    running = (status.get("services") or {}).get("cloudflared") == "active"
    if not host:
        return t("Not used"), t("No Cloudflare Tunnel on this server"), ""
    if check is None:
        return _unread()
    code = int(check.get("code") or 0)
    if 0 < code < 500:
        return t("Answers (HTTP ${code})", code=code), f"{host} · {check.get('ms', 0)} ms", "ok"
    why = t("cloudflared is stopped") if not running else (f"HTTP {code}" if code else t("no answer"))
    return t("Does not answer"), f"{host} · {why}", "bad"


def sru_card(check: dict | None) -> tuple[str, str, str]:
    if check is None:
        return _unread()
    code = int(check.get("code") or 0)
    if 0 < code < 500:
        return t("Answers (HTTP ${code})", code=code), f"{check.get('ms', 0)} ms", "ok"
    return t("Does not answer"), (f"HTTP {code}" if code else t("no answer (Internet or the service is down)")), \
        "warn"


def z3950_card(z: dict | None, now: float | None = None) -> tuple[str, str, str]:
    if z is None:
        return _unread()
    if not z.get("tested"):
        return t("Not tested yet"), t("Show servers in the Z39.50 screen tests them"), "warn"
    when = int(z.get("when") or 0)
    note = t("of ${n} tested", n=z["tested"]) + (f" · {t('${age} ago', age=age(when, now))}" if when else "")
    return t("${n} working", n=z.get("ok", 0)), note, "ok" if z.get("ok") else "warn"


def updates_card(current: str, latest: str | None, koha: tuple[str, str] | None) -> tuple[str, str, str]:
    parts, newer = [], False
    if latest and health.version_tuple(latest) > health.version_tuple(current):
        parts.append(t("Panel ${old} → ${new}", old=current, new=latest))
        newer = True
    elif latest:
        parts.append(t("Panel ${v}", v=current))
    if koha:
        installed, candidate = koha
        if candidate not in ("", "(none)") and candidate != installed:
            parts.append(t("Koha ${old} → ${new}", old=installed, new=candidate))
            newer = True
        else:
            parts.append(t("Koha ${v}", v=installed))
    if not parts:
        return _unread()
    return (t("Update available") if newer else t("Up to date")), " · ".join(parts), "warn" if newer else "ok"


class DashboardView(SectionView):
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            icon = "" if self.app.env.plain else f"{self.section.icon} "
            yield Label(icon + t("Control Dashboard"), classes="view-title")
            yield Button(t("Refresh"), id="refresh", classes="small")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Restart Koha"), id="restart-koha", classes="small")
            yield Button(t("Export diagnostics"), id="export-diagnostics", classes="small")
            yield Button(t("Open diagnostics"), id="open-diagnostics", classes="small")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="status-loader")
        with Grid(classes="status-grid"):
            yield StatusCard(t("Koha"), id="card-state")
            yield StatusCard(t("Last backup"), id="card-backup")
            yield StatusCard(t("Disk free"), id="card-disk")
        yield Label(t("Addresses"), classes="view-prompt")
        with Grid(classes="status-grid", id="addresses"):
            for page in PAGES:
                for where in WHERES:
                    yield LinkCard(t(LINK_TITLES[where, page]), id=f"link-{where}-{page}")
        yield Label(t("Components"), classes="view-prompt")
        with Grid(classes="status-grid", id="components"):
            for unit, name in COMPONENTS:
                yield StatusCard(t(name), id=f"card-{unit}")
            yield StatusCard(t("HTTP response"), id="card-http")
        yield Label(t("Server health"), classes="view-prompt")
        with Grid(classes="status-grid", id="health"):
            for key, title in HEALTH_CARDS:
                yield StatusCard(t(title), id=f"health-{key}")

    def on_mount(self) -> None:
        # An installer older than the panel has no such task: the button stays off.
        for action in ("restart-koha", "export-diagnostics"):
            task = "repair-services" if action == "restart-koha" else action
            ok = self.app.env.demo or (self.app.bridge.supports_tasks() and self.app.bridge.has_task(task))
            self.query_one(f"#{action}", Button).disabled = not ok
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "refresh":
            self.refresh_data()
        elif bid in ("restart-koha", "export-diagnostics", "open-diagnostics"):
            self.app.run_native(bid, after=self.refresh_data if bid == "restart-koha" else None)

    @on(LinkCard.Pressed)
    def _link(self, event: LinkCard.Pressed) -> None:
        if event.copy:
            self.app.copy_to_clipboard(event.url)
        else:
            self.app.open_url(event.url)

    def refresh_data(self) -> None:
        self.query_one("#status-loader").display = True
        self.run_worker(self._load(), exclusive=True, group="status", exit_on_error=False)

    async def _load(self) -> None:
        try:
            status = await self.app.bridge.status()
        except Exception as e:  # shown in the card, never a crash
            self.query_one("#card-state", StatusCard).set(t("Unknown"), str(e)[:60], "bad")
            status = None
        finally:
            self.query_one("#status-loader").display = False
        if status:
            self.show(status)
            self.run_worker(self._load_health(status), exclusive=True, group="health", exit_on_error=False)

    async def _load_health(self, status: dict) -> None:
        env = self.app.env
        if env.demo:
            h = health.demo_health()
        else:
            h = await health.collect(status, env.instance, env.installer)
        self.show_health(status, h)

    def show_health(self, s: dict, h: "health.Health") -> None:
        cards = {
            "cpu": cpu_card(h.cpu),
            "memory": memory_card(s.get("memory")),
            "db": db_card(h.db_size, self.app.env.instance),
            "backup-dir": backup_dir_card(h.backups, s.get("disk"), int((s.get("backup") or {}).get("last_size") or 0)),
            "errors": errors_card(h.apache_errors, h.koha_errors),
            "updates": updates_card(str(s.get("panel_version") or ""), h.panel_latest, h.koha),
            "tunnel": tunnel_card(h.tunnel, s),
            "sru": sru_card(h.sru),
            "z3950": z3950_card(h.z3950),
        }
        for key, values in cards.items():
            self.query_one(f"#health-{key}", StatusCard).set(*values)

    def show(self, s: dict) -> None:
        text, state = OVERALL.get(s.get("state", ""), ("Unknown", "bad"))
        m = s.get("memory", {})
        self.query_one("#card-state", StatusCard).set(
            t(text), f"v{s.get('panel_version', '?')} · {s.get('platform', '')}"
            f" · {t('Memory available')} {human_bytes(m.get('available'))}", state)
        self.query_one("#card-backup", StatusCard).set(*backup_card(s.get("backup")))
        d = s.get("disk", {})
        free, total = d.get("free") or 0, d.get("total") or 0
        self.query_one("#card-disk", StatusCard).set(
            human_bytes(free), f"/ {human_bytes(total)}",
            "bad" if total and free / total < 0.1 else "ok")
        svcs = s.get("services", {})
        for unit, _name in COMPONENTS:
            text, state = unit_state(svcs.get(unit))
            self.query_one(f"#card-{unit}", StatusCard).set(t(text), unit, state)
        http = s.get("http", {})
        staff, opac = http.get("staff"), http.get("opac")
        answers = isinstance(staff, int) and 0 < staff < 500
        self.query_one("#card-http", StatusCard).set(
            t("Answers (HTTP ${code})", code=staff) if answers else t("Does not answer"),
            f"{t('Staff / OPAC')}: {staff or '-'} / {opac or '-'}", "ok" if answers else "bad")
        for (where, page), (url, note, state) in access_links(s).items():
            self.query_one(f"#link-{where}-{page}", LinkCard).set_url(url, note, state)
