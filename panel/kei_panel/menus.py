"""The panel's menu tree, as data.

Labels are the installer's English texts, icon included, byte for byte:
they are the keys of the translation dictionaries. Every leaf names the
routine it runs with its --run action (panel_action_function in the
installer); tests/test_menus.py checks each one still exists there.

kind:
  interactive  the routine still asks its own questions (whiptail): the
               panel suspends and hands the terminal to config.sh --run.
  background   non-interactive: runs in a worker under the Pacman loader.
  native       ported: the panel's own screens ask the questions and the
               work runs as `config.sh --task` (routines/); no whiptail.
verb: a read-only/idempotent installer verb (--rebuild-search-index...)
      that does the same job without questions. When the installer in use
      supports it, the entry runs in the background with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    label: str
    action: str
    kind: str = "interactive"
    verb: tuple[str, ...] = ()
    confirm: str = ""


@dataclass(frozen=True)
class Section:
    id: str
    label: str            # main-menu text
    title: str = ""       # sub-menu box title in bash
    prompt: str = ""      # sub-menu question in bash
    entries: tuple[Entry, ...] = field(default_factory=tuple)
    view: str = "section"  # which view draws it (views/__init__.py)
    key: str = ""         # shortcut key


SECTIONS: tuple[Section, ...] = (
    Section("dashboard", "Control Dashboard", view="dashboard", key="d"),
    Section("install", "📦  Install Koha server", entries=(
        Entry("📦  Install Koha server", "install", kind="native"),)),
    Section("credentials", "🔑  View first-access credentials", entries=(
        Entry("🔑  View first-access credentials", "credentials", kind="native"),)),
    Section("restore", "📥  Restore database", entries=(
        Entry("📥  Restore database", "restore", kind="native"),)),
    Section("backup", "💾  Backup center", "💾 Backup Center", "Choose a backup routine:", (
        Entry("💾  Generate manual backup and download to PC", "backup-manual", kind="native"),
        Entry("📤  Configure cloud backup (Google Drive)", "backup-cloud", kind="native"),
        Entry("🧾  Test integrity of latest backup", "backup-test", kind="native"),
        Entry("📥  Restore database", "restore", kind="native"),
    ), view="backup", key="b"),
    # New screen: Koha's tables at a glance (no bash menu of its own).
    Section("database", "📑  Database tables", "📑  Database tables", entries=(
        Entry("🧹  Deep database optimization & log cleanup", "db-maintenance", kind="native"),
        Entry("📋  Essential SQL reports pack", "reports", kind="native"),
    ), view="database", key="t"),
    # New screen (Module 1): AI provider setup for the cataloguing tabs of
    # the staff web UI; its MARC Replace hook opens the routine below.
    Section("ai", "🪄  AI cataloguing", "🪄  AI cataloguing", entries=(
        Entry("🔀  Replace a MARC record (staff tool)", "marc-replace"),
        # Module 2: the chat on the Koha staff home page (in place of the news).
        Entry("💬  AI assistant on the staff home page", "ai-assistant"),
    ), view="ai", key="a"),
    Section("search", "🔍  Search engine & indexing", "🔍 Search Engine & Indexing", "Choose an action:", (
        Entry("🔃  Toggle search engine (Zebra ⇄ Elasticsearch)", "search-toggle", kind="native"),
        Entry("🔨  Repair / rebuild indexing", "search-repair", kind="native"),
    )),
    Section("publish", "🌐  Publish system to internet", "🌐 Publish System to Internet",
            "Choose a publishing method:", (
        Entry("🌉  Cloudflare Tunnel Manager (Recommended)", "cloudflare"),
        Entry("🔏  Free SSL certificate (Certbot / Apache)", "ssl"),
        Entry("🔎  Google Search Console Assistant", "search-console"),
    )),
    Section("diagnostics", "🩺  Diagnostics & maintenance center", "🩺 Diagnostics & Maintenance Center",
            "Choose a tool:", (
        Entry("📡  Detailed server & Koha status", "status", kind="native"),
        Entry("🏥  Full system health check", "health", kind="native"),
        Entry("📄  View latest validation report", "validation-report", kind="native"),
        Entry("📜  Real-time Apache log auditing", "apache-log", kind="native"),
        Entry("🧹  Deep database optimization & log cleanup", "db-maintenance", kind="native"),
        Entry("🔁  Restart / repair Koha services (Memcached, Plack)", "repair-services", kind="native"),
    )),
    Section("security", "🔒  Security center", "🔒 Security Center", "Choose a security routine:", (
        Entry("🚨  Fail2ban status (intrusion attempts)", "fail2ban", kind="native"),
        Entry("🚧  Staff firewall (restrict port 8080)", "staff-firewall", kind="native"),
        Entry("🔐  Rotate database password", "rotate-db-password", kind="native"),
        Entry("🧱  Show active UFW rules", "ufw", kind="native"),
    )),
    Section("settings", "🔧  Koha settings & parameters", "🔧 Koha Settings & Parameters", "Choose a parameter:", (
        Entry("📏  Server sizing (memory / workers)", "sizing", kind="native"),
        Entry("📧  Configure email and circulation notices", "email", kind="native"),
        Entry("👑  Create super librarian", "superlibrarian", kind="native"),
        Entry("🔌  Enable interoperability (SIP2 and Z39.50)", "interoperability", kind="native"),
        Entry("🕒  Clock and timezone (NTP)", "clock", kind="native"),
    )),
    Section("library", "📚  Library tools", entries=(
        Entry("📚  Library tools", "library-tools"),)),
    Section("tools", "🧰  General tools", "🧰 General Tools", "Choose a tool:", (
        Entry("📊  Resource monitoring (Htop / Nethogs)", "monitor"),
        Entry("🌐  Terminal web browser (Links)", "links"),
        Entry("📂  File explorer (Midnight Commander)", "mc"),
    )),
    Section("crons", "⏰  Schedules & cron tasks", entries=(
        Entry("⏰  Schedules & cron tasks", "crons"),)),
    Section("languages", "🌍  Koha languages", entries=(
        Entry("🌍  Koha languages", "languages"),)),
    Section("update", "🔄  Update center", "🔄 Update Center", "Choose what to update:", (
        Entry("🆙  Update OS packages & Koha schemas", "update-system"),
        Entry("🆕  Update this panel via GitHub", "update-panel"),
    )),
    Section("about", "💡  About the program & support", entries=(
        Entry("💡  About the program & support", "about"),)),
    Section("reboot", "🔁  Reboot server", entries=(
        Entry("🔁  Reboot server", "reboot"),)),
)


def section(section_id: str) -> Section:
    for s in SECTIONS:
        if s.id == section_id:
            return s
    raise KeyError(section_id)


def all_actions() -> set[str]:
    return {e.action for s in SECTIONS for e in s.entries}
