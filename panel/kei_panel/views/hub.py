"""HubView: messaging & interoperability on one screen.

Six tabs: E-mail (SMTP), WhatsApp & Telegram, SMS, Alerts, SIP2 and Z39.50
(its state, and the way to the Z39.50 / SRU servers screen, where it is
turned on or off). Each
shows what Koha has now (`config.sh --task hub-status`: no passwords), the
buttons that set it up from the panel, and links that open the exact Koha
staff page (through opener.py) instead of a wall of instructions.

The SIP2 tab is a form: it reads SIPconfig.xml, sip.py writes the new one
(the listener, the self-check login, its library and what the machine may
do; Koha's example logins with published passwords are taken out) and
`config.sh --task sip-apply` puts it in place after a backup and restarts
the SIP2 server. No XML to edit by hand.

The Alerts tab chooses what notify.py sends (due-date reminders, overdue
alerts, the daily digest) and by which of the channels above; it saves
notifications.conf and switches on the "Reader alerts & daily digest" job
of Schedules & cron tasks when an alert is on. Its dry run shows what
would go out today and sends nothing.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Select, Static, Switch, TabbedContent, TabPane

from .. import cron, notify, sip
from ..i18n import t
from ..screens.dialogs import ConfirmScreen, TextScreen
from .base import SectionView

# Koha staff pages the links open (staff address + path).
LINKS = {
    "h-l-smtp": "/cgi-bin/koha/admin/smtp_servers.pl",
    "h-l-smtp-add": "/cgi-bin/koha/admin/smtp_servers.pl?op=add_form",
    "h-l-admin-email": "/cgi-bin/koha/admin/preferences.pl?op=search&searchfield=KohaAdminEmailAddress",
    "h-l-notices": "/cgi-bin/koha/tools/letter.pl",
    "h-l-overdue": "/cgi-bin/koha/tools/overduerules.pl",
    "h-l-msg-notices": "/cgi-bin/koha/tools/letter.pl",
    "h-l-sms": "/cgi-bin/koha/admin/preferences.pl?op=search&searchfield=SMSSendDriver",
    "h-l-msgprefs": "/cgi-bin/koha/admin/preferences.pl?op=search&searchfield=EnhancedMessagingPreferences",
    "h-l-sip-patron": "/cgi-bin/koha/members/memberentry.pl?op=add_form",
    "h-l-z3950": "/cgi-bin/koha/admin/z3950servers.pl",
}
APP_PASSWORDS = "https://myaccount.google.com/apppasswords"
GMAIL = (   # the cheat sheet: field of Koha's SMTP server form, value
    ("Host", "smtp.gmail.com"),
    ("Port", "587"),
    ("Timeout", "60"),
    ("SSL", "STARTTLS"),
    ("User name", "the library's Gmail address"),
    ("Password", "an app password (16 letters), not the Gmail password"),
    ("Default server", "Yes"),
)
POLICY = {"checkout": "Check out", "checkin": "Check in", "renewal": "Renew",
          "status_update": "Change patron data"}
# Buttons that run a panel routine (menus.py entries of this section).
ROUTINE_BUTTONS = {"h-email-setup": "email", "h-msg-setup": "messaging"}


class HubView(SectionView):
    loaded = False

    def __init__(self, section):
        super().__init__(section)
        self.status: dict[str, str] = {}
        self.smtp: list[list[str]] = []
        self.branches: list[tuple[str, str]] = []
        self.staff_url = ""
        self.sip_logins: list[str] = []

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
            yield Button(t("Reload"), id="h-reload", classes="small")
        yield Static(t("How Koha talks to readers and to other systems: e-mail, WhatsApp and Telegram, SMS, "
                       "self-check machines (SIP2) and other libraries' catalogues (Z39.50). The links open the "
                       "right page of Koha's staff interface."), classes="view-prompt", markup=False)
        with TabbedContent(id="hub-tabs"):
            with TabPane(t("📧  E-mail"), id="hub-email"):
                yield from self.compose_email()
            with TabPane(t("💬  WhatsApp & Telegram"), id="hub-msg"):
                yield from self.compose_messaging()
            with TabPane(t("📱  SMS"), id="hub-sms"):
                yield from self.compose_sms()
            with TabPane(t("🔔  Alerts"), id="hub-alerts"):
                yield from self.compose_alerts()
            with TabPane(t("🏧  SIP2"), id="hub-sip"):
                yield from self.compose_sip()
            with TabPane(t("📡  Z39.50"), id="hub-z3950"):
                yield from self.compose_z3950()

    def compose_email(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="h-email-state", classes="hub-state")
        with Horizontal(classes="form-buttons"):
            yield Button(t("Turn on Koha's e-mail"), id="h-email-setup", variant="primary")
            yield Button(t("SMTP servers"), id="h-l-smtp")
            yield Button(t("New SMTP server"), id="h-l-smtp-add")
            yield Button(t("Library e-mail address"), id="h-l-admin-email")
        yield DataTable(id="h-smtp", show_cursor=False, classes="hub-table")
        with Vertical(id="h-gmail", classes="hub-box"):
            yield Static(t("Gmail: fill Koha's New SMTP server form with these values. Google asks for an app "
                           "password (2-step verification must be on): create one and paste it as the password."),
                         classes="ai-note", markup=False)
            yield DataTable(id="h-gmail-table", show_cursor=False, classes="hub-table")
            with Horizontal(classes="form-buttons"):
                yield Button(t("Create a Google app password"), id="h-apppass")
                yield Button(t("📋 Copy smtp.gmail.com"), id="h-copy-host")
        with Horizontal(classes="form-buttons"):
            yield Button(t("Notices & slips"), id="h-l-notices")
            yield Button(t("Overdue notice triggers"), id="h-l-overdue")

    def compose_messaging(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="h-msg-state", classes="hub-state")
        yield Static(t("Sends Koha's notices (holds waiting, overdue, due soon) by WhatsApp or Telegram too, "
                       "with the reader's mobile number. The setup asks for the service's keys."),
                     classes="ai-note", markup=False)
        with Horizontal(classes="form-buttons"):
            yield Button(t("Set up WhatsApp and Telegram"), id="h-msg-setup", variant="primary")
            yield Button(t("Notices & slips"), id="h-l-msg-notices")
            yield Button(t("Readers' messaging preferences"), id="h-l-msgprefs")

    def compose_sms(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="h-sms-state", classes="hub-state")
        yield Static(t("Koha sends SMS through an SMS::Send driver of your SMS provider (for example Twilio "
                       "or an e-mail gateway). Type the driver's name in the SMSSendDriver preference, then turn "
                       "on the readers' messaging preferences."), classes="ai-note", markup=False)
        with Horizontal(classes="form-buttons"):
            yield Button(t("SMS driver (SMSSendDriver)"), id="h-l-sms", variant="primary")
            yield Button(t("Readers' messaging preferences"), id="h-l-msgprefs-sms")

    def compose_alerts(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="h-al-state", classes="hub-state")
        yield Static(t("Messages the server sends by itself every morning: reminders before the due date and "
                       "overdue alerts to readers, and a daily summary of the loans and of the server to the "
                       "library. Everything is off until you switch it on. Nothing is sent twice on the same day."),
                     classes="ai-note", markup=False)
        with Vertical(id="h-al-form", classes="hub-box"):
            yield from _row(t("Due-date reminders"), Switch(False, id="h-al-due"))
            yield from _row(t("Days before"), Input("2", id="h-al-days", max_length=2, type="integer"))
            yield from _row(t("Overdue alerts"), Switch(False, id="h-al-overdue"))
            yield from _row(t("Repeat every (days)"), Input("7", id="h-al-every", max_length=2, type="integer",
                                                            tooltip=t("0: once")))
            yield from _row(t("Readers get them by e-mail"), Switch(True, id="h-al-email"))
            yield from _row(t("and by WhatsApp or Telegram"), Switch(False, id="h-al-chat"))
            yield from _row(t("Daily summary"), Switch(False, id="h-al-digest"))
            yield from _row(t("Send it to"), Input("", id="h-al-to", placeholder=t("the library's e-mail address")))
        with Horizontal(classes="form-buttons"):
            yield Button(t("Save"), id="h-al-save", variant="success")
            yield Button(t("Dry run (sends nothing)"), id="h-al-dry")
            yield Button(t("⏰  Schedules & cron tasks"), id="h-al-cron")
        yield Static(t("Koha's own notices (Overdue notice triggers, readers' messaging preferences) can send "
                       "reminders too: use one or the other, or readers get two messages. Loans overdue for more "
                       "than ${n} days are only listed in the summary.", n=notify.OVERDUE_LIMIT),
                     classes="ai-note", markup=False)

    def compose_sip(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="h-sip-state", classes="hub-state")
        yield Static(t("The self-check machine (or RFID gate) signs in to Koha's SIP2 server with a login of its "
                       "own. Fill in the form and Save: SIPconfig.xml is written for you (a copy of the old one "
                       "is kept) and the SIP2 server restarts."), classes="ai-note", markup=False)
        with Vertical(id="h-sip-form", classes="hub-box"):
            yield from _row(t("Port"), Input("6001", id="h-sip-port", max_length=5, type="integer"))
            yield from _row(t("Network"), Select([(t("Only this server (127.0.0.1)"), "local"),
                                                  (t("Every network (opens the firewall port)"), "public")],
                                                 value="local", allow_blank=False, id="h-sip-public"))
            yield from _row(t("SIP login"), Input("", id="h-sip-login", max_length=64, placeholder="selfcheck"))
            yield from _row(t("Password"), Input("", id="h-sip-password", password=True,
                                                 placeholder=t("at least 8 characters")))
            yield from _row(t("Library"), Select([], id="h-sip-branch", prompt=t("Choose the library")))
            for key, label in POLICY.items():
                yield from _row(t(label), Switch(key != "status_update", id=f"h-sip-{key}"))
            yield from _row(t("Remove examples"), Switch(True, id="h-sip-examples"))
            yield Label(t("Koha's example logins (term1, koha...) have passwords anyone can read: leave this on."),
                        classes="ai-note")
        with Horizontal(classes="form-buttons"):
            yield Button(t("Save"), id="h-sip-save", variant="success")
            yield Button(t("Create the SIP patron in Koha"), id="h-l-sip-patron")
        yield Static(t("The SIP login must also be a Koha patron with the same user name and password, and the "
                       "circulate permission."), classes="ai-note", markup=False)

    def compose_z3950(self) -> ComposeResult:
        yield Label(t("Not checked yet."), id="h-z-state", classes="hub-state")
        yield Static(t("This catalogue's Z39.50/SRU server (on or off), the koha.nexus network and the catalogues "
                       "Koha copies records from are all on the Z39.50 / SRU servers screen."),
                     classes="ai-note", markup=False)
        with Horizontal(classes="form-buttons"):
            yield Button(t("📡  Z39.50 / SRU servers"), id="h-z-servers", variant="primary")
            yield Button(t("Z39.50/SRU servers in Koha"), id="h-l-z3950")

    def on_mount(self) -> None:
        self.query_one("#h-sip-form").border_title = t("SIP2 server")
        self.query_one("#h-al-form").border_title = t("Alerts")
        self.query_one("#h-gmail").border_title = "Gmail"
        table = self.query_one("#h-gmail-table", DataTable)
        table.add_columns(t("Field"), t("Value"))
        for field, value in GMAIL:
            table.add_row(t(field), t(value))
        smtp = self.query_one("#h-smtp", DataTable)
        smtp.add_columns(t("SMTP server"), t("Host"), t("Port"), t("SSL"), t("User name"), t("Default"))

    def on_show(self) -> None:
        if not self.loaded:
            self.loaded = True
            self.reload()

    # ------------------------------------------------------------------
    # What Koha has now
    # ------------------------------------------------------------------
    def reload(self) -> None:
        self.run_worker(self._reload(), exclusive=True, group="hub-load", exit_on_error=False)

    async def _reload(self) -> None:
        try:
            out = await self.app.bridge.task("hub-status")
        except Exception:     # noqa: BLE001 (no installer, no database: the screen stays as it is)
            return
        self.status = dict(out.results)
        self.staff_url = out.get("staff_url").rstrip("/")
        self.smtp = [row.split("\t") for row in out.lists.get("smtp", [])]
        self.branches = []
        for row in out.lists.get("branch", []):
            code, _, name = row.partition("\t")
            if code:
                self.branches.append((code, name or code))
        self.show_status()
        self.load_sip()
        self.load_alerts()

    def show_status(self) -> None:
        s = self.status
        on = s.get("email") == "on"
        default = next((r[0] for r in self.smtp if len(r) > 5 and r[5] == "1"), "")
        email = t("E-mail: on") if on else t("E-mail: off (Koha sends no notices)")
        if s.get("admin_email"):
            email += "  ·  " + t("Library address: ${address}", address=s["admin_email"])
        email += "  ·  " + (t("Default SMTP server: ${name}", name=default) if default
                            else t("No SMTP server yet: Koha uses this server's own mail."))
        self.query_one("#h-email-state", Label).update(email)
        table = self.query_one("#h-smtp", DataTable)
        table.clear()
        for row in self.smtp:
            row = (row + [""] * 6)[:6]
            table.add_row(*row[:5], t("Yes") if row[5] == "1" else "")
        table.display = bool(self.smtp)
        self.query_one("#h-msg-state", Label).update(
            t("WhatsApp & Telegram: installed") if s.get("messaging") == "yes"
            else t("WhatsApp & Telegram: not set up"))
        driver = s.get("sms_driver", "")
        self.query_one("#h-sms-state", Label).update(
            t("SMS driver: ${driver}", driver=driver) if driver else t("SMS: no driver chosen"))
        self.query_one("#h-sip-state", Label).update(_running("SIP2", s.get("sip")))
        self.query_one("#h-z-state", Label).update(_running("Z39.50", s.get("z3950")))

    # ------------------------------------------------------------------
    # SIP2 form
    # ------------------------------------------------------------------
    def sip_file(self) -> Path:
        return sip.conf_path(self.app.env.instance)

    def sip_text(self) -> str:
        """SIPconfig.xml now (Koha's template when there is none or in the demo)."""
        path = self.sip_file()
        if self.app.env.demo or not path.exists():
            return sip.TEMPLATE
        return path.read_text(encoding="utf-8")

    def load_sip(self) -> None:
        q = self.query_one
        branch = q("#h-sip-branch", Select)
        branch.set_options([(f"{name} ({code})", code) for code, name in self.branches])
        try:
            text = self.sip_text()
            s = sip.read_settings(text)
            self.sip_logins = [lg["id"] for lg in sip.logins(text)]
        except (OSError, ValueError, SyntaxError) as e:
            self.app.notify(t("SIPconfig.xml could not be read: ${error}", error=str(e)), severity="error")
            return
        q("#h-sip-port", Input).value = str(s.port)
        q("#h-sip-public", Select).value = "public" if s.public else "local"
        q("#h-sip-login", Input).value = s.login
        q("#h-sip-password", Input).value = ""
        codes = [code for code, _ in self.branches]
        if s.institution in codes:
            branch.value = s.institution
        elif len(codes) == 1:
            branch.value = codes[0]
        for key in POLICY:
            q(f"#h-sip-{key}", Switch).value = getattr(s, key)
        q("#h-sip-examples", Switch).value = s.remove_examples or not s.login

    def sip_settings(self) -> tuple[sip.SipSettings, str]:
        q = self.query_one
        port = q("#h-sip-port", Input).value.strip()
        if not port.isdigit():
            return sip.SipSettings(), t("The port must be between 1024 and 65535.")
        branch = q("#h-sip-branch", Select).value
        s = sip.SipSettings(
            port=int(port), public=q("#h-sip-public", Select).value == "public",
            login=q("#h-sip-login", Input).value.strip(), password=q("#h-sip-password", Input).value,
            institution="" if branch is Select.BLANK else str(branch),
            remove_examples=q("#h-sip-examples", Switch).value,
            **{key: q(f"#h-sip-{key}", Switch).value for key in POLICY})
        problem = sip.problem(s, self.sip_logins, [code for code, _ in self.branches])
        return s, t(problem) if problem else ""

    def sip_save(self) -> None:
        s, problem = self.sip_settings()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        self.app.run_worker(self._sip_save(s), group="routine", exclusive=True, exit_on_error=False)

    async def _sip_save(self, s: sip.SipSettings) -> None:
        from ..routines.common import run_task, show_done
        title = t("🏧  SIP2")
        try:
            text = sip.apply(self.sip_text(), s)
        except (OSError, ValueError, SyntaxError) as e:
            self.app.notify(t("SIPconfig.xml could not be read: ${error}", error=str(e)), severity="error")
            return
        allowed = [t(label) for key, label in POLICY.items() if getattr(s, key)]
        summary = "\n".join([
            t("Listens on: ${address}", address=f"{'0.0.0.0' if s.public else '127.0.0.1'}:{s.port}"),
            t("SIP login: ${login}", login=s.login) + ("" if s.password else "  " + t("(password kept)")),
            t("Library: ${code}", code=s.institution),
            t("The machine may: ${what}", what=", ".join(allowed) or "-"),
        ] + ([t("Koha's example logins are removed.")] if s.remove_examples else []))
        if not await self.app.push_screen_wait(ConfirmScreen(title, t("Write SIPconfig.xml and restart SIP2?"),
                                                             preview=summary)):
            return
        path = sip.write_temp(text)
        try:
            result = await run_task(self.app, title, "sip-apply", str(path), str(s.port),
                                    "yes" if s.public else "no")
        finally:
            path.unlink(missing_ok=True)
        await show_done(self.app, title, result)
        self.reload()

    # ------------------------------------------------------------------
    # Alerts (notify.py)
    # ------------------------------------------------------------------
    def load_alerts(self) -> None:
        s = notify.load_settings()
        q = self.query_one
        q("#h-al-due", Switch).value = s.due_soon
        q("#h-al-days", Input).value = str(s.due_days)
        q("#h-al-overdue", Switch).value = s.overdue
        q("#h-al-every", Input).value = str(s.overdue_every)
        q("#h-al-email", Switch).value = s.email
        q("#h-al-chat", Switch).value = s.chat
        q("#h-al-digest", Switch).value = s.digest
        q("#h-al-to", Input).value = s.digest_to
        self.show_alerts(s)

    def show_alerts(self, s: notify.Settings) -> None:
        on = [t(label) for flag, label in ((s.due_soon, "Due-date reminders"), (s.overdue, "Overdue alerts"),
                                           (s.digest, "Daily summary")) if flag]
        if not on:
            text = t("Alerts: all off")
        else:
            job = cron.parse(cron.read(), self.app.env.instance).job("notify")
            when = cron.describe(job) if job and job.enabled else t("the schedule is off: Save switches it on")
            text = t("Alerts on: ${list}", list=", ".join(on)) + "  ·  " + when
        self.query_one("#h-al-state", Label).update(text)

    def alert_settings(self) -> tuple[notify.Settings, str]:
        q = self.query_one
        days, every = q("#h-al-days", Input).value.strip(), q("#h-al-every", Input).value.strip()
        if not days.isdigit() or not every.isdigit():
            return notify.Settings(), t("Type the days as a number.")
        s = notify.Settings(
            due_soon=q("#h-al-due", Switch).value, due_days=int(days),
            overdue=q("#h-al-overdue", Switch).value, overdue_every=int(every),
            digest=q("#h-al-digest", Switch).value, digest_to=q("#h-al-to", Input).value.strip(),
            email=q("#h-al-email", Switch).value, chat=q("#h-al-chat", Switch).value)
        problem = notify.settings_problem(s)
        return s, t(problem) if problem else ""

    def alerts_save(self) -> None:
        s, problem = self.alert_settings()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        self.app.run_worker(self._alerts_save(s), group="routine", exclusive=True, exit_on_error=False)

    async def _alerts_save(self, s: notify.Settings) -> None:
        from ..routines.common import run_task, show_done
        try:
            if not self.app.env.demo:
                notify.save_settings(s)
        except OSError as e:
            self.app.notify(str(e), severity="error")
            return
        new = cron.with_job_on(cron.read(), "notify", self.app.env.instance) if s.any_on() else ""
        if not new:
            self.app.notify(t("Saved."))
            self.show_alerts(s)
            return
        title = t("⏰  Schedules & cron tasks")
        path = cron.write_temp(new)
        try:
            result = await run_task(self.app, title, "cron-apply", str(path))
        finally:
            path.unlink(missing_ok=True)
        await show_done(self.app, title, result)
        self.show_alerts(s)

    def alerts_dry_run(self) -> None:
        s, problem = self.alert_settings()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        self.app.run_worker(self._alerts_dry_run(s), group="hub-dry", exclusive=True, exit_on_error=False)

    async def _alerts_dry_run(self, s: notify.Settings) -> None:
        demo = self.app.env.demo
        try:
            status = await self.app.bridge.status()
        except Exception:     # noqa: BLE001 (the summary says the state could not be read)
            status = {}
        instance = self.app.env.instance
        try:
            rep = await asyncio.to_thread(
                notify.run, instance, s, dry_run=True, status=lambda: status, t=t,
                runner=notify.demo_runner() if demo else None,
                channels=notify.DemoChannels() if demo else None,
                today=notify.DEMO_TODAY if demo else dt.date.today())
        except (RuntimeError, OSError) as e:
            self.app.notify(str(e), severity="error")
            return
        await self.app.push_screen_wait(TextScreen(t("Dry run: what would be sent today"), "\n".join(rep.lines)))

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def staff_link(self, path: str) -> str:
        return (self.staff_url or "http://localhost:8080") + path

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        link = LINKS.get(bid) or LINKS.get(bid.removesuffix("-sms"))
        if link:
            event.stop()
            self.app.open_url(self.staff_link(link))
        elif bid in ROUTINE_BUTTONS:
            event.stop()
            self.app.run_native(ROUTINE_BUTTONS[bid], after=self.reload)
        elif bid == "h-apppass":
            event.stop()
            self.app.open_url(APP_PASSWORDS)
        elif bid == "h-copy-host":
            event.stop()
            self.app.copy_to_clipboard("smtp.gmail.com")
        elif bid == "h-z-servers":
            event.stop()
            self.app.screen.action_show("z3950")
        elif bid == "h-sip-save":
            event.stop()
            self.sip_save()
        elif bid == "h-al-save":
            event.stop()
            self.alerts_save()
        elif bid == "h-al-dry":
            event.stop()
            self.alerts_dry_run()
        elif bid == "h-al-cron":
            event.stop()
            self.app.screen.action_show("crons")
        elif bid == "h-reload":
            event.stop()
            self.reload()

    def refresh_data(self) -> None:
        self.reload()


def _row(label: str, widget) -> ComposeResult:
    with Horizontal(classes="form-row"):
        yield Label(label, classes="form-label")
        yield widget


def _running(name: str, state: str | None) -> str:
    if state == "running":
        return t("${name}: running", name=name)
    if state == "stopped":
        return t("${name}: stopped", name=name)
    return t("${name}: not checked", name=name)
