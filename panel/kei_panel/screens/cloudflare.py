"""CloudflareScreen: the Cloudflare Tunnel, all of it in one screen, laid out
like the backup, MARC21 export and cloud backup screens: the work on the
left (in tabs), what is true now on the right.

  ╭ 🌉 Cloudflare Tunnel ──────────────────── ✅ Online: catalog.lib.org ─╮
  │ [🌐 Addresses] [🛠 Set up & manage] [🩺 Test] [📜 Log]                 │
  │ ┌ addresses ───────────────────────────────┐  ╭ Status ─────────────╮ │
  │ │ ✅ Catalog (OPAC) https://catalog...  :80 │  │ service, at boot,   │ │
  │ │ 🔐 Staff          https://admin...  :8080 │  │ since, connections  │ │
  │ └───────────────────────────────────────────┘  │ [Restart] [Pause]   │ │
  │ [📋 Copy] [🌍 Open] [📱 QR code]                ├ Public addresses ───┤ │
  │ ╭ Koha's own addresses ────────────────────╮  ├ cloudflared ────────┤ │
  │ │ OPACBaseURL ✅ / ⚠ [🔧 Use the tunnel's] │  │ version [⬆ Update]  │ │
  │ ╰──────────────────────────────────────────╯  ╰─────────────────────╯ │
  ╰───────────────────────────────────────────────────────────────────────╯

The state comes from `config.sh --task cf-status`; the test, the service
(restart, pause, resume), Koha's addresses, the QR code and the update of
cloudflared are tasks of their own (installer section 14.2). The wizards
that ask questions (free address, own domain, remote staff access, the
recovery file, giving the address up...) are the installer's, started with
`--task cf-run NAME` over this screen, as every routine of the panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, ProgressBar, Static, TabbedContent, TabPane

from .. import opener
from ..i18n import t
from ..widgets.copy import CopyButton
from .dialogs import ConfirmScreen, MessageScreen

# The steps of cf-check, in the order a reader's request takes them.
CHECKS: dict[str, tuple[str, str]] = {
    "setup": ("The tunnel is set up",
              "Set it up in 🛠 Set up & manage: a free address or your own domain."),
    "service": ("cloudflared is running on this server",
                "Press 🔁 Restart (or ▶ Resume when paused). If it stops again, see 📜 Log."),
    "origin-opac": ("Apache answers the catalog here (port 80)",
                    "Koha's OPAC does not answer on this server: Diagnostics > Restart / repair Koha services."),
    "origin-staff": ("Apache answers the staff interface here (port 8080)",
                     "The staff interface does not answer on this server: Diagnostics > Restart / repair Koha "
                     "services."),
    "dns-opac": ("The catalog's name exists on the internet (DNS)",
                 "A new name can take a few minutes. Own domain: the record must be in your Cloudflare DNS."),
    "public-opac": ("The catalog opens from the internet",
                    "Cloudflare does not reach this server: restart the tunnel; free address: 🔄 Reconnect."),
    "public-staff": ("The staff interface opens from the internet",
                     "Restart the tunnel. 401 is fine: the free address asks the remote access password first."),
    "koha-url": ("Koha uses the public address (OPACBaseURL)",
                 "Press 🔧 Use the tunnel's addresses: links in e-mails, the sitemap and Google use it."),
}

STATE_MARK = {"ok": "✅", "warn": "⚠", "fail": "❌", "skip": "·"}


@dataclass
class Check:
    id: str
    state: str
    detail: str = ""

    @property
    def label(self) -> str:
        return t(CHECKS[self.id][0]) if self.id in CHECKS else self.id

    @property
    def advice(self) -> str:
        if self.state == "ok" or self.id not in CHECKS:
            return ""
        return t(CHECKS[self.id][1])


@dataclass
class TunnelState:
    """What `--task cf-status` said."""
    mode: str = "none"                 # none | pending | broker | domain
    opac: str = ""
    staff: str = ""
    staff_host: str = ""               # free address: the staff name, even while off
    staff_remote: bool = False
    listing: bool = False
    service: str = "absent"            # active | inactive | failed | activating | absent
    enabled: str = ""
    since: str = ""
    restarts: str = ""
    version: str = ""
    package: bool = False
    cert: bool = False
    tunnel_id: str = ""
    recovery: str = ""
    local_ip: str = ""
    opac_base: str = ""
    staff_base: str = ""
    connections: int = 0
    edges: list[str] = field(default_factory=list)
    ingress: list[tuple[str, str]] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.service == "active"

    @property
    def paused(self) -> bool:
        return self.service != "absent" and not self.running and self.enabled not in ("enabled", "")

    @property
    def opac_url(self) -> str:
        return f"https://{self.opac}" if self.opac else ""

    @property
    def staff_url(self) -> str:
        return f"https://{self.staff}" if self.staff else ""

    def koha_urls(self) -> tuple[str, str]:
        """OPACBaseURL and staffClientBaseURL as the tunnel wants them (as cf_public_urls)."""
        if not self.opac:
            return "", ""
        staff = self.staff_url or (f"http://{self.local_ip}:8080" if self.local_ip else "")
        return self.opac_url, staff

    @property
    def koha_ok(self) -> bool:
        return bool(self.opac) and self.opac_base.rstrip("/") == self.opac_url


def parse_status(results: dict[str, str], lists: dict[str, list[str]]) -> TunnelState:
    s = TunnelState()
    g = results.get
    s.mode = g("mode", "none") or "none"
    s.opac, s.staff, s.staff_host = g("opac", ""), g("staff", ""), g("staff_host", "")
    s.staff_remote, s.listing = g("staff_remote") == "yes", g("listing") == "yes"
    s.service, s.enabled = g("service", "absent") or "absent", g("enabled", "")
    s.since, s.restarts, s.version = g("since", ""), g("restarts", ""), g("version", "")
    s.package, s.cert = g("package") == "yes", g("cert") == "yes"
    s.tunnel_id, s.recovery, s.local_ip = g("tunnel_id", ""), g("recovery", ""), g("local_ip", "")
    s.opac_base, s.staff_base = g("opac_base", ""), g("staff_base", "")
    s.connections = int(g("connections", "0")) if g("connections", "0").isdigit() else 0
    s.edges = sorted(e for e in lists.get("edge", []) if e)
    for line in lists.get("ingress", []):
        host, _, service = line.partition("\t")
        if host:
            s.ingress.append((host, service))
    s.log = list(lists.get("log", []))
    return s


def parse_checks(lines: list[str]) -> list[Check]:
    out = []
    for line in lines:
        cid, _, rest = line.partition("\t")
        state, _, detail = rest.partition("\t")
        if cid:
            out.append(Check(cid, state or "skip", detail))
    return out


@dataclass
class Address:
    what: str
    url: str
    local: str
    kind: str          # opac | staff | other


def addresses(s: TunnelState) -> list[Address]:
    """The rows of the Addresses tab: what the tunnel publishes."""
    rows: list[Address] = []
    if s.mode == "domain" and s.ingress:
        for host, service in s.ingress:
            kind = "opac" if service.endswith(":80") else "staff" if service.endswith(":8080") else "other"
            what = {"opac": t("Catalog (OPAC)"), "staff": t("Staff interface")}.get(kind, t("Other service"))
            rows.append(Address(what, f"https://{host}", service, kind))
        return rows
    if s.opac:
        rows.append(Address(t("Catalog (OPAC)"), s.opac_url, "http://localhost:80", "opac"))
    if s.staff:
        rows.append(Address(t("Staff interface"), s.staff_url, "http://localhost:8080", "staff"))
    elif s.mode == "broker" and s.staff_host:
        rows.append(Address(t("Staff interface"), t("local network only"),
                            f"http://{s.local_ip or 'IP'}:8080", "staff"))
    return rows


def pill(s: TunnelState) -> Text:
    if s.mode == "none":
        return Text(" " + t("○ Not published: Koha only on the local network") + " ", style="bold reverse yellow")
    if s.mode == "pending":
        return Text(" " + t("⏳ Free address waiting for approval") + " ", style="bold reverse yellow")
    if s.running:
        return Text(" " + t("✅ Online: ${host}", host=s.opac or "—") + " ", style="bold reverse green")
    if s.paused:
        return Text(" " + t("⏸ Paused: the catalog is off the internet") + " ", style="bold reverse yellow")
    return Text(" " + t("⚠ Tunnel stopped") + " ", style="bold reverse red")


class _Reporter:
    """bridge.task's reporter: the busy line of the screen."""

    cancelled = False

    def __init__(self, screen: "CloudflareScreen"):
        self._screen = screen

    def log(self, line: str) -> None:
        self._screen.busy_text(line)

    status = notice = log

    def cancellable(self, on: bool) -> None:
        pass

    def progress(self, current: float, total: float) -> None:
        self._screen.query_one("#cf-bar", ProgressBar).update(total=total or None, progress=current)


class CloudflareScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", t("Close")), Binding("f5", "reload", t("Refresh"))]

    def __init__(self):
        super().__init__()
        self.state = TunnelState()
        self.checks: list[Check] = []
        self.qr: list[str] = []
        self.qr_png = ""
        self._busy = False
        self._loaded = False

    # --- layout -----------------------------------------------------------
    @staticmethod
    def _row(key: str, value_id: str, value: str = "") -> Horizontal:
        return Horizontal(Label(key, classes="sb-key", markup=False),
                          Static(value, id=value_id, classes="sb-val", markup=False), classes="sb-row")

    @staticmethod
    def _card(title: str, card_id: str, *classes: str) -> Vertical:
        card = Vertical(classes=" ".join(("sb-card",) + classes), id=card_id)
        card.border_title = title
        return card

    def compose(self) -> ComposeResult:
        with Vertical(id="cf-box"):
            with Horizontal(id="sb-head"):
                yield Label(t("🌉 Cloudflare Tunnel"), classes="dialog-title", id="cf-title", markup=False)
                yield Static("", id="cf-pill")
            with Horizontal(id="cf-body"):
                with TabbedContent(id="cf-tabs"):
                    with TabPane(t("🌐 Addresses"), id="cf-tab-addr"):
                        with VerticalScroll():
                            yield Static(t("What the tunnel publishes: the address people open, and where "
                                           "Cloudflare delivers it on this server. No port is opened on the "
                                           "router."), classes="sb-hint", markup=False)
                            yield DataTable(id="cf-addr", cursor_type="row", zebra_stripes=True)
                            with Horizontal(classes="sb-card-buttons"):
                                yield CopyButton(id="cf-copy-addr")
                                yield Button(t("🌍 Open in the browser"), id="cf-open")
                                yield Button(t("📱 QR code"), id="cf-qr", variant="primary")
                            with self._card(t("Koha's own addresses"), "cf-koha"):
                                yield Static(t("Koha writes these in e-mails, the sitemap and the pages' links: "
                                               "they should be the public ones."), classes="sb-hint", markup=False)
                                yield self._row("OPACBaseURL", "cf-k-opac")
                                yield self._row("staffClientBaseURL", "cf-k-staff")
                                yield Static("", id="cf-k-note", classes="sb-note", markup=False)
                                with Horizontal(classes="sb-card-buttons"):
                                    yield Button(t("🔧 Use the tunnel's addresses"), id="cf-fix-urls")
                            with self._card(t("Share the catalog"), "cf-qr-card", "-download"):
                                yield Static("", id="cf-qr-code", markup=False)
                                yield Static("", id="cf-qr-note", classes="sb-hint", markup=False)
                                with Horizontal(classes="sb-card-buttons"):
                                    yield CopyButton(id="cf-copy-png")
                                    yield Button(t("📱 More ways to share"), id="cf-share")
                    with TabPane(t("🛠 Set up & manage"), id="cf-tab-setup"):
                        with VerticalScroll():
                            with self._card(t("🆓 Free address (no domain needed)"), "cf-free"):
                                yield Static("", id="cf-free-text", classes="sb-hint", markup=False)
                                yield self._row(t("Remote staff"), "cf-b-staff")
                                yield self._row(t("Public list"), "cf-b-list")
                                yield self._row(t("Recovery file"), "cf-b-rec")
                                with Horizontal(classes="sb-card-buttons", id="cf-free-new"):
                                    yield Button(t("🆓 Get or restore a free address"), id="cf-run-free",
                                                 variant="success")
                                with Horizontal(classes="sb-card-buttons", id="cf-free-manage"):
                                    yield Button(t("🔐 Remote staff access"), id="cf-run-staff")
                                    yield Button(t("📇 Public list"), id="cf-run-listing")
                                    yield Button(t("💾 Save recovery file"), id="cf-run-recovery")
                                with Horizontal(classes="sb-card-buttons", id="cf-free-manage2"):
                                    yield Button(t("🔄 Reconnect"), id="cf-run-reconnect")
                                    yield Button(t("🔑 Renew the token"), id="cf-run-rotate")
                                    yield Button(t("🚪 Give up the address"), id="cf-run-leave", variant="error")
                            with self._card(t("🏠 Your own domain (Cloudflare account)"), "cf-domain"):
                                yield Static("", id="cf-domain-text", classes="sb-hint", markup=False)
                                yield self._row(t("Tunnel"), "cf-d-id")
                                yield self._row(t("Cloudflare login"), "cf-d-cert")
                                yield Static("", id="cf-d-ingress", markup=False)
                                with Horizontal(classes="sb-card-buttons"):
                                    yield Button(t("🏠 Set up my own domain"), id="cf-run-domain", variant="primary")
                                    yield Button(t("🛑 Remove the tunnel"), id="cf-run-remove", variant="error")
                    with TabPane(t("🩺 Test"), id="cf-tab-test"):
                        yield Static(t("Follows a reader's visit step by step: this server, Apache, the name on "
                                       "the internet and the public address. The first ❌ is where it breaks."),
                                     classes="sb-hint", markup=False)
                        yield DataTable(id="cf-checks", cursor_type="row", zebra_stripes=True)
                        yield Static("", id="cf-check-sum", classes="sb-note", markup=False)
                        yield Static("", id="cf-check-row", classes="sb-hint sb-note", markup=False)
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("▶ Run the test"), id="cf-test", variant="primary")
                    with TabPane(t("📜 Log"), id="cf-tab-log"):
                        yield Static(t("The last lines of the cloudflared service (tokens are left out)."),
                                     classes="sb-hint", markup=False)
                        with VerticalScroll(id="cf-log-box"):
                            yield Static("", id="cf-log", markup=False)
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("🔄 Refresh"), id="cf-log-reload")
                            yield CopyButton(id="cf-copy-log")
                with VerticalScroll(id="cf-side"):
                    with self._card(t("Status"), "cf-state"):
                        yield self._row(t("Way"), "cf-s-mode")
                        yield self._row(t("Service"), "cf-s-service")
                        yield self._row(t("At startup"), "cf-s-boot")
                        yield self._row(t("Running since"), "cf-s-since")
                        yield self._row(t("Connections"), "cf-s-conn")
                        yield self._row(t("Restarts"), "cf-s-restarts")
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("🔁 Restart"), id="cf-restart")
                            yield Button(t("⏸ Pause"), id="cf-pause")
                    with self._card(t("Public addresses"), "cf-where", "-download"):
                        yield Static("", id="cf-w-list", markup=False)
                        with Horizontal(classes="sb-card-buttons"):
                            yield CopyButton(id="cf-copy-opac")
                    with self._card("cloudflared", "cf-cloudflared"):
                        yield self._row(t("Version"), "cf-c-version")
                        yield self._row(t("Installed from"), "cf-c-source")
                        with Horizontal(classes="sb-card-buttons"):
                            yield Button(t("⬆ Update cloudflared"), id="cf-update")
                    with self._card(t("Good to know"), "cf-tips"):
                        yield Static(self._tips(), classes="sb-hint", markup=False)
            with Horizontal(id="cf-busy"):
                yield Label("", id="cf-busy-text", markup=False)
                yield ProgressBar(total=None, show_eta=False, id="cf-bar")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("🔄 Refresh"), id="cf-reload")
                yield Button(t("Close"), id="cf-close", variant="primary")

    @staticmethod
    def _tips() -> str:
        return "\n".join([
            t("• The tunnel goes out from this server to Cloudflare: no port is opened on the router, and the "
              "server's own IP stays hidden."),
            t("• HTTPS comes from Cloudflare: no certificate is needed on this server."),
            t("• Pause takes the catalog off the internet without losing anything; Resume brings it back."),
            t("• Free address: keep the recovery file away from this server, to keep the address on a new "
              "installation."),
        ])

    def on_mount(self) -> None:
        self.query_one("#cf-addr", DataTable).add_columns(" ", t("What"), t("Public address"), t("On this server"))
        self.query_one("#cf-checks", DataTable).add_columns(" ", t("Step"), t("Result"))
        self.query_one("#cf-busy").display = False
        self.query_one("#cf-qr-card").display = False
        self._reload()

    # --- running the installer's tasks ---------------------------------------
    def busy_text(self, text: str) -> None:
        self.query_one("#cf-busy-text", Label).update(text)

    def _set_busy(self, text: str | None) -> None:
        self._busy = text is not None
        self.query_one("#cf-busy").display = self._busy
        if text is not None:
            self.busy_text(text)
            self.query_one("#cf-bar", ProgressBar).update(total=None, progress=0)

    async def task(self, label: str, name: str, *args: str, quiet: bool = False):
        """One `--task cf-*`; its error box (if any) is shown unless quiet."""
        self._set_busy(label)
        try:
            out = await self.app.bridge.task(name, *args, reporter=_Reporter(self))
        except Exception as e:  # noqa: BLE001 - shown, the screen stays usable
            self._set_busy(None)
            if not quiet:
                await self._say(t("Error"), f"{type(e).__name__}: {e}", "error")
            return None
        self._set_busy(None)
        if not out.ok and not quiet:
            msg = out.last("error")
            await self._say(msg[1] if msg and msg[1] else label, msg[2] if msg else f"exit {out.rc}", "error")
        return out

    async def _say(self, title: str, body: str, kind: str = "ok") -> None:
        await self.app.push_screen_wait(MessageScreen(title, body.replace("\\n", "\n"), kind=kind))

    def _guard(self) -> bool:
        if self._busy:
            self.app.notify(t("Wait: the tunnel is still answering."), severity="warning")
            return False
        return True

    # --- loading ---------------------------------------------------------------
    @work(exclusive=True, group="cf-load", exit_on_error=False)
    async def _reload(self) -> None:
        await self.refresh_all()
        if not self._loaded:
            self._loaded = True
            if self.state.opac:
                await self.run_checks(quiet=True)

    async def refresh_all(self) -> None:
        out = await self.task(t("Reading the tunnel..."), "cf-status", quiet=True)
        if out is not None:
            self.state = parse_status(out.results, out.lists)
        self._draw()

    async def run_checks(self, quiet: bool = False) -> None:
        out = await self.task(t("Testing the way to the catalog..."), "cf-check", quiet=True)
        if out is None:
            return
        self.checks = parse_checks(out.lists.get("check", []))
        self._draw_checks()
        self._draw_addresses()
        if not quiet:
            bad = next((c for c in self.checks if c.state == "fail"), None)
            if bad is None:
                self.app.notify(t("✅ The catalog answers from the internet."), timeout=5)
            else:
                self.app.notify(t("❌ ${step}", step=bad.label), severity="error", timeout=8)

    # --- drawing -----------------------------------------------------------------
    def _draw(self) -> None:
        s = self.state
        self.query_one("#cf-pill", Static).update(pill(s))
        self._draw_side()
        self._draw_addresses()
        self._draw_koha()
        self._draw_setup()
        self._draw_checks()
        self._draw_log()

    def _mode_text(self) -> str:
        return {"none": t("not published"), "pending": t("free address (waiting for approval)"),
                "broker": t("free address"), "domain": t("own domain")}.get(self.state.mode, self.state.mode)

    def _draw_side(self) -> None:
        s = self.state
        put = self._put
        put("#cf-s-mode", self._mode_text())
        service = {"active": t("✅ running"), "activating": t("⏳ starting"), "failed": t("❌ failed"),
                   "absent": t("not installed")}.get(s.service, t("⏸ stopped"))
        put("#cf-s-service", service)
        put("#cf-s-boot", "—" if s.service == "absent" else
            t("starts with the server") if s.enabled == "enabled" else t("does not start"))
        put("#cf-s-since", s.since or "—")
        conn = "—"
        if s.running:
            conn = t("${n} to Cloudflare", n=s.connections) + (f" ({', '.join(s.edges)})" if s.edges else "")
        put("#cf-s-conn", conn)
        put("#cf-s-restarts", s.restarts or "—")
        pause = self.query_one("#cf-pause", Button)
        pause.label = t("▶ Resume") if not s.running and s.service != "absent" else t("⏸ Pause")
        pause.disabled = s.service == "absent"
        self.query_one("#cf-restart", Button).disabled = s.service == "absent"
        lines = []
        for a in addresses(s):
            lines.append(f"{a.what}\n  {a.url}")
        put("#cf-w-list", "\n".join(lines) if lines else t(
            "None yet: Koha is only on the local network. Publish it in 🛠 Set up & manage."))
        self.query_one("#cf-copy-opac", Button).disabled = not s.opac
        put("#cf-c-version", s.version or t("not installed"))
        put("#cf-c-source", t("Cloudflare's repository (apt)") if s.package else ("—" if not s.version else
                                                                                   t("another source")))
        self.query_one("#cf-update", Button).disabled = not s.package

    def _put(self, sel: str, value: str) -> None:
        self.query_one(sel, Static).update(value)

    def _check(self, kind: str) -> Check | None:
        cid = {"opac": "public-opac", "staff": "public-staff"}.get(kind, "")
        return next((c for c in self.checks if c.id == cid), None)

    def _draw_addresses(self) -> None:
        table = self.query_one("#cf-addr", DataTable)
        keep = table.cursor_row or 0
        table.clear()
        rows = addresses(self.state)
        for a in rows:
            c = self._check(a.kind)
            mark = STATE_MARK.get(c.state, "") if c else ("🏠" if not a.url.startswith("https") else "")
            table.add_row(mark, a.what, a.url, a.local)
        if not rows:
            table.add_row("", t("(nothing published)"), t("Use 🛠 Set up & manage"), "")
        else:
            table.move_cursor(row=min(keep, len(rows) - 1))
        public = bool(self.state.opac)
        for b in ("#cf-copy-addr", "#cf-open", "#cf-qr"):
            self.query_one(b, Button).disabled = not public

    def _draw_koha(self) -> None:
        s = self.state
        self._put("#cf-k-opac", s.opac_base or "—")
        self._put("#cf-k-staff", s.staff_base or "—")
        fix = self.query_one("#cf-fix-urls", Button)
        if not s.opac:
            note = t("Publish the catalog first.")
        elif s.koha_ok:
            note = t("✅ Koha uses the catalog's public address.")
        else:
            note = t("⚠ Koha does not use the public address ${url}: links in e-mails and the sitemap point "
                     "elsewhere.", url=s.opac_url)
        self._put("#cf-k-note", note)
        fix.disabled = not s.opac
        fix.variant = "warning" if s.opac and not s.koha_ok else "default"

    def _draw_setup(self) -> None:
        s = self.state
        broker = s.mode == "broker"
        free = t("No domain or Cloudflare account is needed: the catalog gets an address of the koha.nexus "
                 "network right away. The staff interface stays on the local network until remote staff "
                 "access is turned on (a password checked before anyone reaches Koha).")
        if broker:
            free = t("This server uses the free address ${host}.", host=s.opac or "—")
        elif s.mode == "pending":
            free = t("A request for a free address is waiting for approval. Press the button to see it or "
                     "continue.")
        elif s.mode == "domain":
            free = t("This server publishes your own domain. A free address would replace it.")
        self._put("#cf-free-text", free)
        for sel in ("#cf-b-staff", "#cf-b-list", "#cf-b-rec"):
            self.query_one(sel).parent.display = broker
        if broker:
            self._put("#cf-b-staff", (t("on: ${url}", url=s.staff_url) if s.staff_remote else t("off")))
            self._put("#cf-b-list", t("shown") if s.listing else t("hidden"))
            self._put("#cf-b-rec", s.recovery or t("⚠ not saved yet"))
        self.query_one("#cf-free-new").display = not broker
        self.query_one("#cf-free-manage").display = broker
        self.query_one("#cf-free-manage2").display = broker

        domain = s.mode == "domain"
        text = t("Use a domain you already activated in Cloudflare (free plan). The panel signs in to "
                 "Cloudflare, creates the tunnel, registers catalog.<domain> and admin.<domain> and starts it.")
        if broker:
            text = t("This server uses a free address. Leave it first (Free address menu), then set up your own "
                     "domain.")
        elif domain:
            text = t("This server publishes your own domain. Setting it up again changes the domain or the "
                     "subdomains; the tunnel is reused.")
        self._put("#cf-domain-text", text)
        self.query_one("#cf-d-id").parent.display = domain
        self.query_one("#cf-d-cert").parent.display = domain or s.cert
        self._put("#cf-d-id", s.tunnel_id or "—")
        self._put("#cf-d-cert", t("✅ done (cert.pem)") if s.cert else t("not yet"))
        rules = "\n".join(f"  {h}  →  {svc}" for h, svc in s.ingress)
        self._put("#cf-d-ingress", (t("Rules (config.yml):") + "\n" + rules) if domain and rules else "")
        self.query_one("#cf-run-domain", Button).disabled = broker
        self.query_one("#cf-run-domain", Button).label = (t("🏠 Change the domain") if domain
                                                         else t("🏠 Set up my own domain"))
        self.query_one("#cf-run-remove", Button).display = domain

    def _draw_checks(self) -> None:
        table = self.query_one("#cf-checks", DataTable)
        table.clear()
        for c in self.checks:
            detail = c.detail
            if c.id == "public-opac" and c.state == "fail" and not detail:
                detail = t("no answer")
            table.add_row(STATE_MARK.get(c.state, ""), c.label, detail)
        if not self.checks:
            table.add_row("", t("Not tested yet"), t("Press ▶ Run the test"))
            summary = ""
        else:
            bad = next((c for c in self.checks if c.state == "fail"), None)
            warn = next((c for c in self.checks if c.state == "warn"), None)
            if bad:
                summary = t("❌ It breaks at: ${step}", step=bad.label) + "\n" + bad.advice
            elif warn:
                summary = t("⚠ Works, with a warning: ${step}", step=warn.label) + "\n" + warn.advice
            else:
                summary = t("✅ Every step works: the catalog answers from the internet.")
        self._put("#cf-check-sum", summary)

    def _draw_log(self) -> None:
        self._put("#cf-log", "\n".join(self.state.log) if self.state.log else t("No lines yet."))

    def _draw_qr(self) -> None:
        card = self.query_one("#cf-qr-card")
        card.display = bool(self.qr)
        self._put("#cf-qr-code", "\n".join(self.qr))
        self._put("#cf-qr-note", (t("Image to print: ${file}", file=self.qr_png) if self.qr_png else "")
                  + "\n" + self.state.opac_url)
        self.query_one("#cf-copy-png", Button).disabled = not self.qr_png

    # --- actions -----------------------------------------------------------------
    def selected(self) -> Address | None:
        """The highlighted address, or the first public one."""
        rows = addresses(self.state)
        if not rows:
            return None
        row = rows[min(self.query_one("#cf-addr", DataTable).cursor_row or 0, len(rows) - 1)]
        if row.url.startswith("https://"):
            return row
        return next((a for a in rows if a.url.startswith("https://")), None)

    @on(Button.Pressed, "#cf-copy-addr")
    def _copy_addr(self) -> None:
        a = self.selected()
        if a:
            self.app.copy_to_clipboard(a.url)

    @on(Button.Pressed, "#cf-copy-opac")
    def _copy_opac(self) -> None:
        if self.state.opac_url:
            self.app.copy_to_clipboard(self.state.opac_url)

    @on(Button.Pressed, "#cf-copy-png")
    def _copy_png(self) -> None:
        if self.qr_png:
            self.app.copy_to_clipboard(self.qr_png)

    @on(Button.Pressed, "#cf-copy-log")
    def _copy_log(self) -> None:
        self.app.copy_to_clipboard("\n".join(self.state.log))

    @on(Button.Pressed, "#cf-open")
    def _open(self) -> None:
        a = self.selected()
        if a is None:
            return
        if self.app.env.demo or not opener.open_url(a.url):
            self.app.notify(t("Open this address in your browser: ${url}", url=a.url), timeout=8)

    @on(Button.Pressed, "#cf-qr")
    def _qr_pressed(self) -> None:
        if self._guard():
            self.run_worker(self._make_qr(), group="cf-qr", exclusive=True, exit_on_error=False)

    async def _make_qr(self) -> None:
        out = await self.task(t("Making the QR code..."), "cf-qr")
        if out is None or not out.ok:
            return
        self.qr = [line for line in out.lists.get("qr", [])]
        self.qr_png = out.get("png")
        self._draw_qr()
        self.query_one("#cf-qr-card").scroll_visible()

    @on(Button.Pressed, "#cf-fix-urls")
    def _fix_pressed(self) -> None:
        if self._guard():
            self.run_worker(self._fix_urls(), group="cf-urls", exclusive=True, exit_on_error=False)

    async def _fix_urls(self) -> None:
        opac, staff = self.state.koha_urls()
        if not await self.app.push_screen_wait(ConfirmScreen(
                t("🔧 Use the tunnel's addresses"),
                t("Koha's addresses become:\n\nOPACBaseURL: ${opac}\nstaffClientBaseURL: ${staff}\n\nKoha's "
                  "cache is cleared and Plack restarted (a few seconds). Go on?", opac=opac, staff=staff))):
            return
        out = await self.task(t("Changing Koha's addresses..."), "cf-urls")
        if out is not None and out.ok:
            msg = out.last("ok")
            await self._say(t("🔧 Use the tunnel's addresses"), msg[2] if msg else "", "ok")
        await self.refresh_all()

    @on(DataTable.RowHighlighted, "#cf-checks")
    def _check_moved(self, event: DataTable.RowHighlighted) -> None:
        row = event.cursor_row
        c = self.checks[row] if 0 <= row < len(self.checks) else None
        self._put("#cf-check-row", (f"{c.label}: {c.advice}" if c and c.advice else ""))

    @on(Button.Pressed, "#cf-test")
    def _test_pressed(self) -> None:
        if self._guard():
            self.run_worker(self.run_checks(), group="cf-test", exclusive=True, exit_on_error=False)

    @on(Button.Pressed, "#cf-restart")
    def _restart_pressed(self) -> None:
        if self._guard():
            self.run_worker(self._service("restart"), group="cf-svc", exclusive=True, exit_on_error=False)

    @on(Button.Pressed, "#cf-pause")
    def _pause_pressed(self) -> None:
        if self._guard():
            action = "pause" if self.state.running else "resume"
            self.run_worker(self._service(action), group="cf-svc", exclusive=True, exit_on_error=False)

    async def _service(self, action: str) -> None:
        if action == "pause" and not await self.app.push_screen_wait(ConfirmScreen(
                t("⏸ Pause the tunnel"),
                t("The catalog goes off the internet (it stays on the local network) until you press ▶ Resume, "
                  "also after a restart of the server. Nothing is deleted.\n\nPause now?"), danger=True)):
            return
        label = {"restart": t("Restarting the tunnel..."), "pause": t("Pausing the tunnel..."),
                 "resume": t("Resuming the tunnel...")}[action]
        out = await self.task(label, "cf-service", action)
        if out is not None and out.ok:
            msg = out.last("ok")
            self.app.notify(msg[2] if msg else t("Done."), timeout=6)
        await self.refresh_all()
        if out is not None and out.ok and action != "pause" and self.state.opac:
            await self.run_checks(quiet=True)

    @on(Button.Pressed, "#cf-update")
    def _update_pressed(self) -> None:
        if self._guard():
            self.run_worker(self._update(), group="cf-update", exclusive=True, exit_on_error=False)

    async def _update(self) -> None:
        out = await self.task(t("Updating cloudflared..."), "cf-update")
        if out is not None and out.ok:
            msg = out.last("ok")
            await self._say("cloudflared", msg[2] if msg else "", "ok")
        await self.refresh_all()

    # The installer's wizards: their questions over this screen.
    WIZARDS = {
        "cf-run-free": ("free", "🆓  Free Address (no domain needed)"),
        "cf-run-domain": ("domain", "🏠  Use My Own Domain (Cloudflare account)"),
        "cf-share": ("share", "📱  Share the Catalog Link (QR code, link)"),
        "cf-run-remove": ("remove", "🛑  Disable and Remove Tunnel (Go Offline)"),
        "cf-run-staff": ("staff", "Remote staff access (password at the edge)"),
        "cf-run-reconnect": ("reconnect", "Reconnect the tunnel (fetch the token again)"),
        "cf-run-rotate": ("rotate", "Renew the tunnel token"),
        "cf-run-recovery": ("recovery", "Save the recovery file (to move this address to a new installation)"),
        "cf-run-listing": ("listing", "Show or hide the catalog on the public list of catalogs"),
        "cf-run-leave": ("leave", "Give up the free address"),
    }

    @on(Button.Pressed, ", ".join(f"#{k}" for k in WIZARDS))
    def _wizard_pressed(self, event: Button.Pressed) -> None:
        if self._guard() and event.button.id:
            name, title = self.WIZARDS[event.button.id]
            self.run_worker(self._wizard(name, t(title)), group="cf-wizard", exclusive=True, exit_on_error=False)

    async def _wizard(self, name: str, title: str) -> None:
        from ..routines.common import run_interactive
        self._busy = True
        try:
            await run_interactive(self.app, title, "cf-run", name)
        finally:
            self._busy = False
        await self.refresh_all()
        if name in ("free", "domain", "reconnect", "rotate", "staff") and self.state.opac:
            await self.run_checks(quiet=True)

    @on(Button.Pressed, "#cf-log-reload")
    @on(Button.Pressed, "#cf-reload")
    def action_reload(self) -> None:
        if self._guard():
            self.run_worker(self.refresh_all(), group="cf-load", exclusive=True, exit_on_error=False)

    @on(Button.Pressed, "#cf-close")
    def action_close(self) -> None:
        if self._busy:
            self.app.notify(t("Wait: the tunnel is still answering."), severity="warning")
            return
        self.dismiss(None)
