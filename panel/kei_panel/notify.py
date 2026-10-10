"""Reader alerts and the daily status digest (Messaging > Alerts).

A job of Schedules & cron tasks (cron.py, preset "notify", daily at 07:00)
runs `/usr/local/bin/koha-kei-notify INSTANCE`, which runs this module. Three
alerts, each off until the library turns it on in notifications.conf:

  * due_soon: readers whose loans fall due in N days get one message listing
    them (once per loan and due date: a renewal brings a new reminder);
  * overdue: readers with loans past their due date get one message, sent
    again every N days while the loan stays out (0: once). Loans overdue for
    more than OVERDUE_LIMIT days are only listed in the digest;
  * digest: once a day, to the library's address, the state of the server
    (config.sh --status-json, the dashboard's JSON) and of the loans.

Koha is read through its own tables with koha-mysql, nothing is written to
them. E-mail goes out through Koha's default SMTP server (smtp_servers, or
the local mail server as Koha does without one) from the library's address;
WhatsApp and Telegram through the panel's KohaEasy::Messaging module when it
is installed. No new credentials.

What was sent is kept in a small file (sent.tsv, "key<TAB>date" lines) next
to a lock, so the job can run any number of times: a key is written only
after its message went out, and nothing is sent twice on the same day.
`--dry-run` prints what would be sent and changes nothing.

Standard library only: the cron job may run with the system's python3.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, fields
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Callable, Iterable

CONFIG_DIR = Path("/etc/koha-easy-install")
CONF_FILE = CONFIG_DIR / "notifications.conf"
LOG_FILE = Path("/var/log/koha-easy-install/notify.log")
INSTALLED_PANEL = Path("/usr/local/bin/config.sh")
PERL_DIR = Path("/usr/local/lib/site_perl")
OVERDUE_LIMIT = 90          # days: older overdue loans are only in the digest
DIGEST_LIST = 15            # overdue loans listed in the digest
KEEP_DAYS = 400             # sent.tsv forgets keys older than this

ALERTS = ("due_soon", "overdue", "digest")
_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def state_dir(instance: str) -> Path:
    return Path(os.environ.get("KEI_NOTIFY_STATE") or f"/var/lib/koha/{instance}/kei-notify")


def email_flag(instance: str) -> Path:
    """Written by koha-email-enable: Koha sends e-mail for this instance."""
    return Path(os.environ.get("KEI_KOHA_EMAIL_FLAG") or f"/var/lib/koha/{instance}/email.enabled")


def messaging_conf(instance: str) -> Path:
    return Path(os.environ.get("KEI_MESSAGING_CONF") or f"/etc/koha/sites/{instance}/kei-messaging.conf")


def conf_path() -> Path:
    return Path(os.environ.get("KEI_NOTIFY_CONF") or CONF_FILE)


# ----------------------------------------------------------------------
# Settings (notifications.conf, written by the panel's Alerts tab)
# ----------------------------------------------------------------------
@dataclass
class Settings:
    due_soon: bool = False
    due_days: int = 2           # remind this many days before the due date
    overdue: bool = False
    overdue_every: int = 7      # send again every N days while overdue (0: once)
    digest: bool = False
    digest_to: str = ""         # "" = the library's address (KohaAdminEmailAddress)
    email: bool = True          # readers' channels
    chat: bool = False          # WhatsApp / Telegram (KohaEasy::Messaging)

    def any_on(self) -> bool:
        return self.due_soon or self.overdue or self.digest


def _as_bool(v: str) -> bool:
    return v.strip().lower() in ("on", "yes", "1", "true")


def parse_settings(text: str) -> Settings:
    """key=value lines; unknown keys and bad numbers are ignored."""
    s = Settings()
    types = {f.name: f.type for f in fields(Settings)}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key not in types:
            continue
        kind = types[key]
        if kind in (bool, "bool"):
            setattr(s, key, _as_bool(value))
        elif kind in (int, "int"):
            if value.isdigit():
                setattr(s, key, int(value))
        else:
            setattr(s, key, value)
    return s


def render_settings(s: Settings) -> str:
    out = ["# koha.nexus: reader alerts and the daily digest (panel: Messaging > Alerts).",
           "# Sent by koha-kei-notify, a job of Schedules & cron tasks."]
    for f in fields(Settings):
        v = getattr(s, f.name)
        out.append(f"{f.name}={('on' if v else 'off') if isinstance(v, bool) else v}")
    return "\n".join(out) + "\n"


def settings_problem(s: Settings) -> str:
    """"" when the settings can be saved, else what to fix."""
    if not 0 <= s.due_days <= 14:
        return "Days before the due date: from 0 to 14."
    if not 0 <= s.overdue_every <= 60:
        return "Repeat overdue alerts every 0 to 60 days (0: once)."
    if s.digest_to and not all(_EMAIL.match(a) for a in _addresses(s.digest_to)):
        return "The digest address is not an e-mail address."
    if (s.due_soon or s.overdue) and not (s.email or s.chat):
        return "Choose how readers get the alerts: e-mail, WhatsApp/Telegram or both."
    return ""


def load_settings(path: Path | None = None) -> Settings:
    try:
        return parse_settings((path or conf_path()).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return Settings()


def save_settings(s: Settings, path: Path | None = None) -> None:
    path = path or conf_path()
    _write_atomic(path, render_settings(s), 0o644)


def _addresses(text: str) -> list[str]:
    return [a for a in re.split(r"[,;\s]+", text) if a]


def _write_atomic(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# ----------------------------------------------------------------------
# What was sent (sent.tsv)
# ----------------------------------------------------------------------
class SentLog:
    """key -> date of the last message for it. Saved after every message."""

    def __init__(self, path: Path, dry_run: bool = False):
        self.path, self.dry_run = path, dry_run
        self.sent: dict[str, dt.date] = {}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for line in text.splitlines():
            key, _, day = line.partition("\t")
            with contextlib.suppress(ValueError):
                self.sent[key] = dt.date.fromisoformat(day.strip())

    def last(self, key: str) -> dt.date | None:
        return self.sent.get(key)

    def mark(self, keys: Iterable[str], today: dt.date) -> None:
        for key in keys:
            self.sent[key] = today
        if self.dry_run:
            return
        oldest = today - dt.timedelta(days=KEEP_DAYS)
        self.sent = {k: d for k, d in self.sent.items() if d >= oldest}
        _write_atomic(self.path, "".join(f"{k}\t{d.isoformat()}\n" for k, d in sorted(self.sent.items())), 0o600)


@contextlib.contextmanager
def run_lock(folder: Path):
    """One run at a time: a second one stops (BlockingIOError)."""
    import fcntl
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


# ----------------------------------------------------------------------
# Koha (read only)
# ----------------------------------------------------------------------
Runner = Callable[[str], str]


def koha_mysql(instance: str) -> Runner:
    def run(sql: str) -> str:
        proc = subprocess.run(["koha-mysql", instance, "--default-character-set=utf8mb4", "-B", "-N", "-e", sql],
                              stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=300, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or "koha-mysql failed")
        return proc.stdout.decode("utf-8", "replace")
    return run


def _unescape(v: str) -> str:
    """mysql -B writes tabs, new lines and backslashes as \\t \\n \\\\."""
    return re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n", "0": "", "\\": "\\"}.get(m.group(1), m.group(1)), v)


def rows(run: Runner, sql: str, width: int) -> list[list[str]]:
    out = []
    for line in run(sql).splitlines():
        parts = [_unescape(p) for p in line.split("\t")]
        if len(parts) == width:
            out.append(parts)
    return out


@dataclass
class Loan:
    issue_id: str
    borrower: str
    due: dt.date
    title: str
    barcode: str
    name: str
    cardnumber: str
    email: str
    phone: str


@dataclass
class Koha:
    library: str = ""
    admin_email: str = ""
    loans: list[Loan] = field(default_factory=list)       # due by the reminder day, or overdue
    loans_out: int = 0
    smtp: dict[str, str] = field(default_factory=dict)


LOANS_SQL = """SELECT i.issue_id, i.borrowernumber, DATE(i.date_due),
  IFNULL(b.title, ''), IFNULL(it.barcode, ''),
  TRIM(CONCAT(IFNULL(p.firstname, ''), ' ', IFNULL(p.surname, ''))), IFNULL(p.cardnumber, ''),
  IFNULL(p.email, ''),
  COALESCE(NULLIF(p.smsalertnumber, ''), NULLIF(p.mobile, ''), NULLIF(p.phone, ''), '')
FROM issues i
JOIN items it ON it.itemnumber = i.itemnumber
JOIN biblio b ON b.biblionumber = it.biblionumber
JOIN borrowers p ON p.borrowernumber = i.borrowernumber
WHERE i.date_due < '{until}'
ORDER BY i.date_due, i.issue_id"""

PREFS_SQL = ("SELECT variable, IFNULL(value, '') FROM systempreferences "
             "WHERE variable IN ('KohaAdminEmailAddress', 'LibraryName')")
SMTP_SQL = ("SELECT host, port, timeout, ssl_mode, IFNULL(user_name, ''), IFNULL(password, '') "
            "FROM smtp_servers WHERE is_default = 1 ORDER BY id LIMIT 1")
BRANCH_SQL = "SELECT branchname FROM branches ORDER BY branchname LIMIT 1"


def read_koha(run: Runner, today: dt.date, due_days: int) -> Koha:
    k = Koha()
    prefs = dict((r[0], r[1]) for r in rows(run, PREFS_SQL, 2))
    k.admin_email = prefs.get("KohaAdminEmailAddress", "").strip()
    k.library = prefs.get("LibraryName", "").strip()
    if not k.library:
        k.library = next((r[0] for r in rows(run, BRANCH_SQL, 1)), "") or "Koha"
    until = today + dt.timedelta(days=due_days + 1)
    for r in rows(run, LOANS_SQL.format(until=until.isoformat()), 9):
        with contextlib.suppress(ValueError):
            k.loans.append(Loan(r[0], r[1], dt.date.fromisoformat(r[2]), *r[3:]))
    total = rows(run, "SELECT COUNT(*) FROM issues", 1)
    k.loans_out = int(total[0][0]) if total and total[0][0].isdigit() else 0
    try:
        smtp = rows(run, SMTP_SQL, 6)
    except RuntimeError:         # Koha before 21.05: no smtp_servers table
        smtp = []
    if smtp:
        k.smtp = dict(zip(("host", "port", "timeout", "ssl_mode", "user", "password"), smtp[0]))
    return k


# ----------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------
@dataclass
class Message:
    kind: str               # due_soon, overdue, digest
    keys: list[str]         # marked as sent once it went out
    who: str                # for the report: reader card number or the library
    subject: str
    body: str
    email: list[str] = field(default_factory=list)
    phone: str = ""


def _identity(src: str, **values: object) -> str:
    for k, v in values.items():
        src = src.replace("${" + k + "}", str(v))
    return src


def translator() -> Callable[..., str]:
    """The panel's t() in the panel's language; English when the panel's
    own modules cannot be loaded (the system's python3 without Rich)."""
    try:
        from .env import PanelEnv
        from .i18n import Translator
        env = PanelEnv.detect()
        return Translator(env.lang, env.installer, plain=False)
    except Exception:      # noqa: BLE001 (any failure: English)
        return _identity


def fmt_date(d: dt.date, t: Callable[..., str]) -> str:
    """ISO in English; the language's own order where the dictionary has one."""
    return d.strftime(t("%Y-%m-%d"))


def _by_reader(loans: Iterable[Loan]) -> dict[str, list[Loan]]:
    out: dict[str, list[Loan]] = {}
    for loan in loans:
        out.setdefault(loan.borrower, []).append(loan)
    return out


def plan(s: Settings, k: Koha, log: SentLog, today: dt.date, t: Callable[..., str] = _identity) -> list[Message]:
    """The reader messages due today (the digest is built after they went out)."""
    msgs: list[Message] = []
    if s.due_soon:
        day = today + dt.timedelta(days=s.due_days)
        due = [ln for ln in k.loans if ln.due == day and not log.last(f"due:{ln.issue_id}:{ln.due}")]
        for loans in _by_reader(due).values():
            first = loans[0]
            items = "\n".join(f"  - {ln.title}" + (f" ({ln.barcode})" if ln.barcode else "") for ln in loans)
            body = t("Hello ${name},\n\nThese items you borrowed from ${library} are due on ${date}:\n${items}\n\n"
                     "You can renew them in the library catalogue or at the desk.",
                     name=first.name or first.cardnumber, library=k.library, date=fmt_date(day, t), items=items)
            msgs.append(Message("due_soon", [f"due:{ln.issue_id}:{ln.due}" for ln in loans], first.cardnumber,
                                t("Reminder: items due on ${date}", date=fmt_date(day, t)), body,
                                _addresses(first.email), first.phone))
    if s.overdue:
        oldest = today - dt.timedelta(days=OVERDUE_LIMIT)
        late = []
        for ln in k.loans:
            if not oldest <= ln.due < today:
                continue
            last = log.last(f"overdue:{ln.issue_id}")
            if last is None or (s.overdue_every and (today - last).days >= s.overdue_every):
                late.append(ln)
        for loans in _by_reader(late).values():
            first = loans[0]
            items = "\n".join(f"  - {ln.title}" + t(" (due ${date})", date=fmt_date(ln.due, t)) for ln in loans)
            body = t("Hello ${name},\n\nThese items borrowed from ${library} are past their due date:\n${items}\n\n"
                     "Please return or renew them.",
                     name=first.name or first.cardnumber, library=k.library, items=items)
            msgs.append(Message("overdue", [f"overdue:{ln.issue_id}" for ln in loans], first.cardnumber,
                                t("Overdue items at ${library}", library=k.library), body,
                                _addresses(first.email), first.phone))
    return msgs


def digest(s: Settings, k: Koha, status: dict, sent: dict[str, int], today: dt.date,
           t: Callable[..., str] = _identity) -> Message:
    late = [ln for ln in k.loans if ln.due < today]
    lines = [t("${library} - daily summary, ${date}", library=k.library, date=fmt_date(today, t)), "",
             t("Loans"), "  " + t("Out now: ${n}", n=k.loans_out),
             "  " + t("Due today: ${n}", n=sum(1 for ln in k.loans if ln.due == today)),
             "  " + t("Overdue: ${n} (${readers} readers)", n=len(late),
                      readers=len({ln.borrower for ln in late}))]
    for ln in sorted(late, key=lambda x: x.due)[:DIGEST_LIST]:
        lines.append(f"    {(today - ln.due).days:>4}d  {ln.title[:60]}  [{ln.cardnumber}]")
    if len(late) > DIGEST_LIST:
        lines.append("    " + t("... and ${n} more", n=len(late) - DIGEST_LIST))
    lines += ["", t("Alerts sent to readers today"),
              "  " + t("Due-date reminders: ${n}", n=sent.get("due_soon", 0)),
              "  " + t("Overdue alerts: ${n}", n=sent.get("overdue", 0))]
    if sent.get("failed"):
        lines.append("  " + t("Not delivered: ${n} (see ${log})", n=sent["failed"], log=str(LOG_FILE)))
    server = server_lines(status, t)
    lines += ["", t("Server")] + ["  " + ln for ln in server]
    to = _addresses(s.digest_to) or _addresses(k.admin_email)
    problem = any(ln.startswith("!") for ln in server)
    subject = t("${library}: daily summary", library=k.library) + (" - " + t("needs attention") if problem else "")
    return Message("digest", [f"digest:{today.isoformat()}"], t("the library"), subject, "\n".join(lines), to)


def server_lines(status: dict, t: Callable[..., str] = _identity) -> list[str]:
    """The dashboard's facts, a "!" in front of what needs a look."""
    if not status:
        return ["! " + t("The server's state could not be read.")]
    out = []
    state = status.get("state", "")
    out.append(("" if state == "ok" else "! ") + t("Koha: ${state}", state=state or "?"))
    down = [name for name, st in (status.get("services") or {}).items()
            if st not in ("active", "inactive", "unknown") or (st == "inactive" and name in
                                                                ("apache2", "mariadb", "koha-common"))]
    if down:
        out.append("! " + t("Services not running: ${list}", list=", ".join(down)))
    disk = status.get("disk") or {}
    total, free = disk.get("total") or 0, disk.get("free") or 0
    if total:
        pct = round(100 * free / total)
        out.append(("! " if pct < 10 else "") + t("Free disk space: ${pct}% (${gb} GB)", pct=pct,
                                                  gb=f"{free / 1e9:.1f}"))
    backup = status.get("backup") or {}
    epoch = backup.get("last_epoch") or 0
    if epoch:
        days = int((time.time() - epoch) // 86400)
        out.append(("! " if days > 2 else "") + t("Last backup: ${days} days ago (${file})", days=days,
                                                  file=backup.get("last_file") or "-"))
    else:
        out.append("! " + t("No backup found."))
    return out


def server_status(installer: Path | None = None, timeout: int = 180) -> dict:
    """config.sh --status-json (read only), or {} when it cannot run."""
    installer = installer or Path(os.environ.get("KEI_INSTALLER") or INSTALLED_PANEL)
    try:
        proc = subprocess.run(["bash", str(installer), "--status-json"], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    lines = [ln for ln in proc.stdout.decode("utf-8", "replace").splitlines() if ln.lstrip().startswith("{")]
    try:
        return json.loads(lines[-1]) if lines else {}
    except ValueError:
        return {}


# ----------------------------------------------------------------------
# Sending
# ----------------------------------------------------------------------
class Channels:
    """E-mail through Koha's SMTP server, WhatsApp/Telegram through the
    panel's Perl module. why_* say why a channel cannot be used ("" = ok)."""

    def __init__(self, instance: str, k: Koha):
        self.instance, self.k = instance, k
        self.why_email = ""
        if not email_flag(instance).exists():
            self.why_email = "Koha's e-mail is off (Messaging > E-mail)"
        elif not _EMAIL.match(k.admin_email):
            self.why_email = "the library's e-mail address (KohaAdminEmailAddress) is empty"
        self.why_chat = ""
        if not (PERL_DIR / "KohaEasy" / "Messaging.pm").exists() or not messaging_conf(instance).exists():
            self.why_chat = "WhatsApp & Telegram are not set up (Messaging)"

    def send_email(self, to: list[str], subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = formataddr((self.k.library, self.k.admin_email))
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid(domain=self.k.admin_email.rpartition("@")[2] or None)
        msg.set_content(body)
        c = self.k.smtp
        host, port = c.get("host") or "localhost", int(c.get("port") or 25)
        timeout = int(c.get("timeout") or 60)
        mode = (c.get("ssl_mode") or "disabled").lower()
        ctx = ssl.create_default_context()
        if mode == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        with server:
            if mode == "starttls":
                server.starttls(context=ctx)
            if c.get("user"):
                server.login(c["user"], c.get("password", ""))
            server.send_message(msg)

    def send_chat(self, phone: str, text: str) -> str:
        script = ("use KohaEasy::Messaging; my $c = KohaEasy::Messaging::load_conf($ARGV[0]); "
                  "my ($ok, $info) = KohaEasy::Messaging::send_message($c, $ARGV[1], $ARGV[2]); "
                  "print $info; exit($ok ? 0 : 1);")
        proc = subprocess.run(["perl", f"-I{PERL_DIR}", "-e", script, str(messaging_conf(self.instance)), phone,
                               text], stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=False)
        info = proc.stdout.decode("utf-8", "replace").strip() or proc.stderr.decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise RuntimeError(info or "the message could not be sent")
        return info


def deliver(m: Message, s: Settings, ch: Channels, dry_run: bool) -> tuple[bool, str]:
    """(sent?, how or why not). A reader alert goes by e-mail and/or chat as
    chosen; it counts as sent when one channel took it."""
    ways: list[str] = []
    why: list[str] = []
    use_email = m.kind == "digest" or s.email
    use_chat = m.kind != "digest" and s.chat
    if use_email:
        if not m.email:
            why.append("no e-mail address")
        elif ch.why_email:
            why.append(ch.why_email)
        elif dry_run:
            ways.append("e-mail " + ", ".join(m.email))
        else:
            try:
                ch.send_email(m.email, m.subject, m.body)
                ways.append("e-mail")
            except (OSError, smtplib.SMTPException, ValueError) as e:
                why.append(f"e-mail: {e}")
    if use_chat:
        if not m.phone:
            why.append("no mobile number")
        elif ch.why_chat:
            why.append(ch.why_chat)
        elif dry_run:
            ways.append("WhatsApp/Telegram " + m.phone)
        else:
            try:
                ways.append(ch.send_chat(m.phone, f"{m.subject}\n\n{m.body}") or "chat")
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
                why.append(str(e))
    return (bool(ways), ", ".join(ways) if ways else "; ".join(why) or "no channel")


# ----------------------------------------------------------------------
# Demo (panel --demo: the dry run without Koha)
# ----------------------------------------------------------------------
DEMO_TODAY = dt.date(2026, 10, 12)


def demo_runner() -> Runner:
    loans = [("101", "7", "2026-10-14", "Dom Casmurro", "0001234", "Ana Souza", "2201", "ana@example.org", ""),
             ("102", "7", "2026-10-14", "Vidas secas", "0001240", "Ana Souza", "2201", "ana@example.org", ""),
             ("103", "9", "2026-10-03", "Grande sertão: veredas", "0000987", "Bruno Lima", "2310", "",
              "+5511987654321"),
             ("104", "11", "2026-10-12", "O cortiço", "0000555", "Carla Dias", "2405", "carla@example.org", "")]

    def run(sql: str) -> str:
        if sql.startswith("SELECT variable"):
            return "KohaAdminEmailAddress\tbiblioteca@example.org\nLibraryName\tBiblioteca Central\n"
        if "FROM issues i" in sql:
            return "".join("\t".join(r) + "\n" for r in loans)
        if sql.startswith("SELECT COUNT"):
            return "348\n"
        return ""
    return run


class DemoChannels:
    why_email = why_chat = ""


# ----------------------------------------------------------------------
# One run
# ----------------------------------------------------------------------
@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    sent: dict[str, int] = field(default_factory=dict)

    def add(self, line: str) -> None:
        self.lines.append(line)

    def count(self, kind: str) -> None:
        self.sent[kind] = self.sent.get(kind, 0) + 1


def run(instance: str, s: Settings, *, dry_run: bool = False, today: dt.date | None = None,
        runner: Runner | None = None, status: Callable[[], dict] | None = None,
        channels: Channels | None = None, t: Callable[..., str] = _identity) -> Report:
    today = today or dt.date.today()
    rep = Report()
    head = "dry run: nothing is sent" if dry_run else "run"
    rep.add(f"koha-kei-notify {instance} {today.isoformat()} ({head})")
    if not s.any_on():
        rep.add("Every alert is off (Messaging > Alerts): nothing to do.")
        return rep
    k = read_koha(runner or koha_mysql(instance), today, s.due_days if s.due_soon else 0)
    log = SentLog(state_dir(instance) / "sent.tsv", dry_run=dry_run)
    ch = channels or Channels(instance, k)
    for m in plan(s, k, log, today, t):
        ok, how = deliver(m, s, ch, dry_run)
        if ok:
            log.mark(m.keys, today)
            rep.count(m.kind)
        else:
            rep.count("failed")
        rep.add(f"{_verb(ok, dry_run)}  {m.kind:<8} {m.who}: {len(m.keys)} loan(s) - {how}")
    if s.digest:
        key = f"digest:{today.isoformat()}"
        if log.last(key):
            rep.add("digest   already sent today")
        else:
            m = digest(s, k, (status or server_status)(), rep.sent, today, t)
            ok, how = deliver(m, s, ch, dry_run)
            if ok:
                log.mark(m.keys, today)
            rep.add(f"{_verb(ok, dry_run)}  digest   {', '.join(m.email) or '-'} - {how}")
            if dry_run:
                rep.add("")
                rep.add(m.subject)
                rep.add(m.body)
    if len(rep.lines) == 1:
        rep.add("Nothing to send today.")
    return rep


def _verb(ok: bool, dry_run: bool) -> str:
    if dry_run:
        return "would send" if ok else "could NOT send"
    return "sent" if ok else "NOT sent"


def _append_log(lines: list[str]) -> None:
    with contextlib.suppress(OSError):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n" + "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="koha-kei-notify", description=__doc__.split("\n\n")[0])
    ap.add_argument("instance", nargs="?", default=os.environ.get("KEI_INSTANCE", "library"))
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent; send and record nothing")
    ap.add_argument("--today", help="YYYY-MM-DD (tests)")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", a.instance):
        ap.error("bad instance name")
    today = dt.date.fromisoformat(a.today) if a.today else None
    s = load_settings()
    problem = settings_problem(s)
    if problem:
        print(f"{conf_path()}: {problem}", file=sys.stderr)
        return 2
    try:
        with run_lock(state_dir(a.instance)):
            rep = run(a.instance, s, dry_run=a.dry_run, today=today, t=translator())
    except BlockingIOError:
        print("Another run is in progress.", file=sys.stderr)
        return 1
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        _append_log([f"koha-kei-notify {a.instance}: {e}"])
        print(f"koha-kei-notify: {e}", file=sys.stderr)
        return 1
    print("\n".join(rep.lines))
    if not a.dry_run:
        _append_log(rep.lines)
    return 1 if rep.sent.get("failed") and not a.dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
