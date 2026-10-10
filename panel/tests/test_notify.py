"""notify.py: reader alerts and the daily digest (Messaging > Alerts)."""

import datetime as dt

import pytest

from kei_panel import cron, notify

TODAY = dt.date(2026, 10, 12)

PREFS = "KohaAdminEmailAddress\tbiblioteca@example.org\nLibraryName\tBiblioteca Central\n"
LOANS = [
    # issue, reader, due, title, barcode, name, card, e-mail, phone
    ("1", "7", "2026-10-14", "Dom Casmurro", "B1", "Ana Souza", "C7", "ana@example.org", ""),
    ("2", "7", "2026-10-14", "Vidas secas", "B2", "Ana Souza", "C7", "ana@example.org", ""),
    ("3", "9", "2026-10-03", "Grande sertão", "B3", "Bruno Lima", "C9", "", "+5511987654321"),
    ("4", "11", "2026-10-12", "O cortiço", "B4", "Carla Dias", "C11", "carla@example.org", ""),
    ("5", "12", "2025-01-01", "Iracema", "B5", "Davi Reis", "C12", "davi@example.org", ""),
    ("6", "13", "2026-10-13", "Memórias", "B6", "Eva Cruz", "C13", "eva@example.org", ""),
]
STATUS = {"state": "ok", "services": {"apache2": "active", "mariadb": "active", "elasticsearch": "inactive"},
          "disk": {"total": 100e9, "free": 40e9}, "backup": {"last_epoch": 0}}


def fake_koha(loans=LOANS, smtp=""):
    seen = []

    def run(sql):
        seen.append(sql)
        if sql.startswith("SELECT variable"):
            return PREFS
        if "FROM issues i" in sql:
            until = sql.split("date_due < '")[1][:10]
            return "".join("\t".join(r) + "\n" for r in loans if r[2] < until)
        if sql.startswith("SELECT COUNT"):
            return f"{len(loans)}\n"
        if "smtp_servers" in sql:
            return smtp
        return ""
    run.seen = seen
    return run


class Recorder:
    """Channels that keep what they were asked to send."""

    def __init__(self, why_email="", why_chat="", fail=()):
        self.why_email, self.why_chat, self.fail = why_email, why_chat, set(fail)
        self.mails, self.chats = [], []

    def send_email(self, to, subject, body):
        if any(a in self.fail for a in to):
            raise OSError("connection refused")
        self.mails.append((to, subject, body))

    def send_chat(self, phone, text):
        if phone in self.fail:
            raise RuntimeError("WhatsApp: HTTP 500")
        self.chats.append((phone, text))
        return "whatsapp"


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_NOTIFY_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("KEI_NOTIFY_CONF", str(tmp_path / "notifications.conf"))


def go(s, ch, today=TODAY, dry_run=False, loans=LOANS):
    return notify.run("library", s, dry_run=dry_run, today=today, runner=fake_koha(loans),
                      status=lambda: STATUS, channels=ch)


# --- settings ---------------------------------------------------------

def test_everything_is_off_until_chosen(tmp_path):
    s = notify.load_settings(tmp_path / "missing.conf")
    assert not s.any_on() and (s.due_days, s.overdue_every, s.email, s.chat) == (2, 7, True, False)
    rep = go(s, Recorder())
    assert "Every alert is off" in rep.lines[-1]


def test_settings_round_trip_and_problems(tmp_path):
    s = notify.Settings(due_soon=True, due_days=3, overdue=True, overdue_every=0, digest=True,
                        digest_to="a@b.org, c@d.org", chat=True)
    notify.save_settings(s, tmp_path / "n.conf")
    assert notify.load_settings(tmp_path / "n.conf") == s
    assert (tmp_path / "n.conf").stat().st_mode & 0o777 == 0o644
    assert notify.parse_settings("due_soon=yes\ndue_days=x\nbogus=1\n") == notify.Settings(due_soon=True)
    assert notify.settings_problem(s) == ""
    assert notify.settings_problem(notify.Settings(due_days=30))
    assert notify.settings_problem(notify.Settings(overdue_every=61))
    assert notify.settings_problem(notify.Settings(digest_to="not an address"))
    assert notify.settings_problem(notify.Settings(overdue=True, email=False, chat=False))


# --- reader alerts ----------------------------------------------------

def test_due_soon_one_message_per_reader():
    ch = Recorder()
    rep = go(notify.Settings(due_soon=True), ch)
    assert len(ch.mails) == 1
    to, subject, body = ch.mails[0]
    assert to == ["ana@example.org"] and "2026-10-14" in subject
    assert "Dom Casmurro (B1)" in body and "Vidas secas (B2)" in body and "Biblioteca Central" in body
    assert rep.sent == {"due_soon": 1}


def test_the_same_alert_is_never_sent_twice():
    s = notify.Settings(due_soon=True, overdue=True, chat=True, digest=True)
    ch = Recorder()
    go(s, ch)
    first = (len(ch.mails), len(ch.chats))
    assert first[0] >= 2 and first[1] == 1
    rep = go(s, ch)                       # cron ran again the same day
    assert (len(ch.mails), len(ch.chats)) == first
    assert "digest   already sent today" in rep.lines
    go(s, ch, today=TODAY + dt.timedelta(days=1))   # next day: Bruno's alert is not repeated yet,
    assert len(ch.chats) == 1                       # Carla's loan (due on the 12th) is late now
    assert [m[0] for m in ch.mails[first[0]:] if "Overdue" in m[1]] == [["carla@example.org"]]


def test_overdue_repeats_every_n_days_and_skips_old_loans():
    s = notify.Settings(overdue=True, overdue_every=7, chat=True)
    ch = Recorder()
    go(s, ch)
    assert ch.chats and ch.chats[0][0] == "+5511987654321" and "Grande sertão" in ch.chats[0][1]
    assert not any(m[0] == ["davi@example.org"] for m in ch.mails)    # overdue for 600 days: digest only
    for n in range(1, 7):
        go(s, ch, today=TODAY + dt.timedelta(days=n))
    assert len(ch.chats) == 1
    go(s, ch, today=TODAY + dt.timedelta(days=7))
    assert len(ch.chats) == 2
    once = notify.Settings(overdue=True, overdue_every=0, chat=True)
    go(once, ch, today=TODAY + dt.timedelta(days=30))
    assert len(ch.chats) == 2


def test_a_renewal_brings_a_new_reminder():
    s = notify.Settings(due_soon=True, due_days=1)
    ch = Recorder()
    go(s, ch, loans=[LOANS[5]])
    renewed = [("6", "13", "2026-10-20", "Memórias", "B6", "Eva Cruz", "C13", "eva@example.org", "")]
    go(s, ch, today=dt.date(2026, 10, 19), loans=renewed)
    assert [m[0] for m in ch.mails] == [["eva@example.org"], ["eva@example.org"]]


def test_failures_are_retried_next_run():
    s = notify.Settings(due_soon=True)
    bad = Recorder(fail={"ana@example.org"})
    rep = go(s, bad)
    assert rep.sent == {"failed": 1} and "connection refused" in rep.lines[-1]
    good = Recorder()
    go(s, good)
    assert len(good.mails) == 1


def test_missing_channels_say_why():
    s = notify.Settings(due_soon=True, overdue=True, email=True, chat=True)
    ch = Recorder(why_email="Koha's e-mail is off (Messaging > E-mail)", why_chat="WhatsApp & Telegram are not set up")
    rep = go(s, ch)
    assert not ch.mails and not ch.chats
    assert any("Koha's e-mail is off" in ln for ln in rep.lines)
    assert any("not set up" in ln for ln in rep.lines)


def test_dry_run_sends_and_records_nothing(tmp_path):
    s = notify.Settings(due_soon=True, overdue=True, digest=True, chat=True)
    ch = Recorder()
    rep = go(s, ch, dry_run=True)
    assert not ch.mails and not ch.chats
    assert not (tmp_path / "state" / "sent.tsv").exists()
    text = "\n".join(rep.lines)
    assert "e-mail ana@example.org" in text and "WhatsApp/Telegram +5511987654321" in text
    assert "Biblioteca Central - daily summary" in text
    go(s, ch)                                  # the real run afterwards still sends everything
    assert ch.mails and ch.chats


# --- digest -----------------------------------------------------------

def test_digest_lists_loans_and_server():
    s = notify.Settings(digest=True, digest_to="chefe@example.org")
    ch = Recorder()
    go(s, ch)
    (to, subject, body), = ch.mails
    assert to == ["chefe@example.org"] and "needs attention" in subject     # no backup found
    assert "Out now: 6" in body and "Due today: 1" in body and "Overdue: 2 (2 readers)" in body
    assert "Iracema" in body and "Grande sertão" in body
    assert "Free disk space: 40%" in body and "! No backup found." in body
    assert "elasticsearch" not in body    # off on purpose: not a problem


def test_digest_goes_to_the_library_address_by_default():
    ch = Recorder()
    go(notify.Settings(digest=True), ch)
    assert ch.mails[0][0] == ["biblioteca@example.org"]


def test_server_lines_flag_problems():
    lines = notify.server_lines({"state": "degraded", "services": {"apache2": "failed", "cron": "active"},
                                 "disk": {"total": 100, "free": 5}, "backup": {"last_epoch": 1}})
    assert lines[0].startswith("! ") and "apache2" in lines[1]
    assert lines[2].startswith("! Free disk space: 5%") and lines[3].startswith("! Last backup")
    assert notify.server_lines({}) == ["! The server's state could not be read."]


# --- Koha and channels ------------------------------------------------

def test_mysql_escapes_are_undone():
    run = lambda sql: "a\\tb\tc\\\\d\\ne\n" if "x" in sql else ""    # noqa: E731
    assert notify.rows(run, "x", 2) == [["a\tb", "c\\d\ne"]]


def test_smtp_settings_come_from_koha():
    k = notify.read_koha(fake_koha(smtp="smtp.gmail.com\t587\t60\tstarttls\tlib@gmail.com\tsecret\n"), TODAY, 2)
    assert k.smtp == {"host": "smtp.gmail.com", "port": "587", "timeout": "60", "ssl_mode": "starttls",
                      "user": "lib@gmail.com", "password": "secret"}
    assert k.library == "Biblioteca Central" and k.loans_out == 6


def test_channels_check_koha_email_and_messaging(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_KOHA_EMAIL_FLAG", str(tmp_path / "email.enabled"))
    monkeypatch.setenv("KEI_MESSAGING_CONF", str(tmp_path / "kei-messaging.conf"))
    k = notify.Koha(admin_email="biblioteca@example.org")
    ch = notify.Channels("library", k)
    assert "e-mail is off" in ch.why_email and "not set up" in ch.why_chat
    (tmp_path / "email.enabled").touch()
    assert notify.Channels("library", k).why_email == ""
    assert "KohaAdminEmailAddress" in notify.Channels("library", notify.Koha()).why_email


def test_send_email_uses_koha_smtp(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=0, **kw):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, msg):
            calls.append(("send", msg["To"], msg["From"], msg["Subject"]))

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    k = notify.Koha(library="Biblioteca", admin_email="lib@example.org",
                    smtp={"host": "smtp.example.org", "port": "587", "ssl_mode": "starttls", "user": "u",
                          "password": "p"})
    _ch(k).send_email(["a@b.org"], "Hi", "Body")
    assert calls[0] == ("connect", "smtp.example.org", 587) and ("starttls",) in calls
    assert ("login", "u", "p") in calls and calls[-1] == ("send", "a@b.org", "Biblioteca <lib@example.org>", "Hi")
    calls.clear()
    _ch(notify.Koha(library="B", admin_email="lib@example.org")).send_email(["a@b.org"], "Hi", "Body")
    assert calls[0] == ("connect", "localhost", 25) and len(calls) == 2     # Koha's fallback, no login


def _ch(k):
    ch = notify.Channels.__new__(notify.Channels)
    ch.instance, ch.k = "library", k
    return ch


def test_a_second_run_waits_for_the_first(tmp_path):
    with notify.run_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with notify.run_lock(tmp_path):
                pass


def test_main_dry_run_and_bad_settings(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(notify, "koha_mysql", lambda inst: fake_koha())
    monkeypatch.setattr(notify, "server_status", lambda: STATUS)
    monkeypatch.setattr(notify, "translator", lambda: notify._identity)
    monkeypatch.setattr(notify, "LOG_FILE", tmp_path / "notify.log")
    monkeypatch.setenv("KEI_KOHA_EMAIL_FLAG", str(tmp_path / "email.enabled"))
    (tmp_path / "email.enabled").touch()
    assert notify.main(["library", "--dry-run", "--today", "2026-10-12"]) == 0
    assert "Every alert is off" in capsys.readouterr().out
    notify.save_settings(notify.Settings(due_soon=True, digest=True))
    assert notify.main(["library", "--dry-run", "--today", "2026-10-12"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "ana@example.org" in out
    assert not (tmp_path / "notify.log").exists()
    (tmp_path / "notifications.conf").write_text("due_days=99\n")
    assert notify.main(["library"]) == 2


def test_demo_dry_run():
    rep = notify.run("library", notify.Settings(due_soon=True, overdue=True, digest=True, chat=True),
                     dry_run=True, today=notify.DEMO_TODAY, runner=notify.demo_runner(),
                     status=lambda: STATUS, channels=notify.DemoChannels())
    text = "\n".join(rep.lines)
    assert "ana@example.org" in text and "+5511987654321" in text and "Out now: 348" in text


# --- the cron job -----------------------------------------------------

def test_cron_preset_daily_at_seven_off():
    p = cron.BY_KEY["notify"]
    assert (p.hour, p.minute, p.enabled) == (7, 0, False)
    job = cron.preset_job(p, "library")
    job.enabled = True
    assert job.line() == "0 7 * * * root /usr/local/bin/koha-kei-notify library >/dev/null 2>&1"


def test_with_job_on_switches_only_that_job():
    text = cron.render(cron.parse("PATH=/usr/bin\n15 22 * * * root /bin/bash /root/backup_sql.sh\n", "library"))
    assert "#off# 0 7 * * * root /usr/local/bin/koha-kei-notify library" in text
    new = cron.with_job_on(text, "notify", "library")
    assert "\n0 7 * * * root /usr/local/bin/koha-kei-notify library" in new
    assert "\n15 22 * * * root /bin/bash /root/backup_sql.sh" in new and cron.file_problem(new) == ""
    assert cron.with_job_on(new, "notify", "library") == ""
