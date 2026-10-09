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
  view         opens another section's screen (action = its section id),
               for a screen that lives inside a hub (the VPN in the
               Security & access hub).
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
    # Dormant: not drawn (the routine and its code stay; Paulo, 2026-10-08:
    # the cataloguing aids do not work yet, so their cards are hidden).
    hidden: bool = False


@dataclass(frozen=True)
class Section:
    id: str
    label: str            # main-menu text
    title: str = ""       # sub-menu box title in bash
    prompt: str = ""      # sub-menu question in bash
    entries: tuple[Entry, ...] = field(default_factory=tuple)
    view: str = "section"  # which view draws it (views/__init__.py)
    key: str = ""         # shortcut key
    icon: str = ""        # drawn before a label that has no icon of its own
    sidebar: bool = True  # False: reached from a hub entry (and its key) only
    parent: str = ""      # the hub highlighted in the sidebar while it is shown


SECTIONS: tuple[Section, ...] = (
    Section("dashboard", "Control Dashboard", view="dashboard", key="d", icon="📊"),
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
    # Every import in one place, right under the backups (Paulo, 2026-10-09).
    Section("import", "🪄  Magic Import Tool", entries=(
        Entry("🪄  Magic Import Tool (drop anything here)", "magic-import", kind="native"),), key="i"),
    # New screen: Koha's tables at a glance (no bash menu of its own).
    Section("database", "📑  Database tables", "📑  Database tables", entries=(
        Entry("🧹  Deep database optimization & log cleanup", "db-maintenance", kind="native"),
        Entry("📋  Essential SQL reports pack", "reports", kind="native"),
    ), view="database", key="t"),
    # New screen: both AI tools on one page (views/ai.py). AI cataloguing
    # (Module 1: MARC Replace, which opens the routine below) and the AI
    # assistant (Module 2: the chat on the Koha staff home page) share the
    # provider, each with its own model; Ollama models download from there.
    Section("ai", "🤖  AI", "🤖  AI", entries=(
        Entry("🔀  Replace a MARC record (staff tool)", "marc-replace", kind="native"),
        Entry("💬  AI assistant on the staff home page", "ai-assistant", kind="native"),
    ), view="ai", key="a"),
    # New screen: this Koha's Z39.50/SRU server (on/off), the koha.nexus
    # Catalog Network, and public catalogues for copy cataloguing (Z39.50 and
    # SRU), scanned and ranked, added to Koha's z3950servers (no bash menu).
    Section("z3950", "📡  Z39.50 / SRU servers", "📡  Z39.50 / SRU servers", view="z3950", key="z"),
    # New screen: the public catalogue's look (textures, wallpaper, dark mode,
    # New arrivals carousel), written into OpacUserCSS / OpacUserJS (no bash menu).
    Section("opac", "🎨  OPAC appearance", "🎨  OPAC appearance", view="opac", key="o"),
    # Messaging & interoperability: e-mail, WhatsApp/Telegram, SMS, SIP2 and
    # Z39.50 on one screen (views/hub.py); its buttons run these routines.
    # This Koha's Z39.50/SRU server is turned on and off on the z3950 screen:
    # the classic "SIP2 and Z39.50" routine stays reachable, but no button runs it.
    Section("hub", "📨  Messaging & interoperability", "📨  Messaging & interoperability", entries=(
        Entry("📧  Configure email and circulation notices", "email", kind="native"),
        Entry("💬  Messaging: WhatsApp and Telegram", "messaging", kind="native"),
        Entry("🔌  Enable interoperability (SIP2 and Z39.50)", "interoperability", kind="native", hidden=True),
    ), view="hub", key="m"),
    # WireGuard VPN for the staff interface and SSH (views/vpn.py), opened
    # from the Security & access hub (or its key).
    Section("vpn", "🔐  WireGuard VPN", "🔐  WireGuard VPN", view="vpn", key="v", sidebar=False,
            parent="security"),
    # Security, remote access and the firewall in one hub: VPN, Cloudflare
    # Tunnel, UFW, HTTPS and Fail2ban (it replaces "Publish system to
    # internet" and "Security center").
    Section("security", "🔒  Security & access hub", "🔒 Security & Access Hub",
            "Choose a security or remote-access tool:", (
        Entry("🔐  WireGuard VPN", "vpn", kind="view"),
        Entry("🌉  Cloudflare Tunnel Manager (Recommended)", "cloudflare", kind="native"),
        Entry("🧱  Show active UFW rules", "ufw", kind="native"),
        Entry("🚧  Staff firewall (restrict port 8080)", "staff-firewall", kind="native"),
        Entry("🔏  Free SSL certificate (Certbot / Apache)", "ssl", kind="native"),
        Entry("🚨  Fail2ban status (intrusion attempts)", "fail2ban", kind="native"),
        Entry("🔐  Rotate database password", "rotate-db-password", kind="native"),
        Entry("🔎  Google Search Console Assistant", "search-console", kind="native"),
    ), key="x"),
    Section("search", "🔍  Search engine & indexing", "🔍 Search Engine & Indexing", "Choose an action:", (
        Entry("🔃  Toggle search engine (Zebra ⇄ Elasticsearch)", "search-toggle", kind="native"),
        Entry("🔨  Repair / rebuild indexing", "search-repair", kind="native"),
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
    Section("settings", "🔧  Koha settings & parameters", "🔧 Koha Settings & Parameters", "Choose a parameter:", (
        Entry("📏  Server sizing (memory / workers)", "sizing", kind="native"),
        Entry("👑  Create super librarian", "superlibrarian", kind="native"),
        Entry("🕒  Clock and timezone (NTP)", "clock", kind="native"),
    )),
    Section("library", "📚  Library tools", "📚  Library tools",
            "Changes are always previewed first and protected by a verified backup.", (
        Entry("🔙  Undo a MARC import", "marc-undo", kind="native"),
        Entry("🔗  Sync & link authorities", "authority-sync", kind="native"),
        Entry("📋  Essential SQL reports pack", "reports", kind="native"),
        Entry("🎓  School-year turnover (patron categories)", "patron-category", kind="native"),
        Entry("🧪  Catalog data-quality check", "data-quality", kind="native"),
        Entry("🎭  Privacy (LGPD): anonymise old history", "privacy-anonymise", kind="native"),
        Entry("🚮  Privacy (LGPD): delete old patrons", "privacy-delete", kind="native"),
        Entry("📜  View tool logs", "tool-logs", kind="native"),
        Entry("🌎  Brazil: localization", "brazil", kind="native"),
        Entry("📝  Cataloguing aids: PHA, Cutter, CDD", "cataloguing", kind="native", hidden=True),
        Entry("🔎  CDD lookup in the cataloguing (staff tool)", "cdd", kind="native", hidden=True),
        Entry("🧩  Koha plugins (turn on or off)", "plugins", kind="native"),
        Entry("🧮  Cutter Calculator", "cutter", kind="native", hidden=True),
    ), key="l"),
    Section("tools", "🧰  General tools", "🧰 General Tools", "Choose a tool:", (
        Entry("📊  Resource monitoring (Htop / Nethogs)", "monitor", kind="native"),
        Entry("📂  File explorer (Midnight Commander)", "mc", kind="native"),
    )),
    # The visual cron manager (views/crons.py); the entry is the classic routine.
    Section("crons", "⏰  Schedules & cron tasks", entries=(
        Entry("⏰  Schedules & cron tasks", "crons", kind="native"),), view="crons", key="s"),
    Section("languages", "🌍  Koha languages", entries=(
        Entry("🌍  Koha languages", "languages", kind="native"),)),
    Section("update", "🔄  Update center", "🔄 Update Center", "Choose what to update:", (
        Entry("🆙  Update OS packages & Koha schemas", "update-system", kind="native"),
        Entry("🆕  Update this panel via GitHub", "update-panel", kind="native"),
    )),
    Section("about", "💡  About the program & support", entries=(
        Entry("💡  About the program & support", "about", kind="native"),)),
    Section("reboot", "🔁  Reboot server", entries=(
        Entry("🔁  Reboot server", "reboot", kind="native"),)),
)


def section(section_id: str) -> Section:
    for s in SECTIONS:
        if s.id == section_id:
            return s
    raise KeyError(section_id)


def all_actions() -> set[str]:
    """Installer actions (a view entry opens a screen, not a routine)."""
    return {e.action for s in SECTIONS for e in s.entries if e.kind != "view"}


# The line under each card (widgets/cards.py): what the routine does, in a
# few words. English keys like the labels; pt.cache holds the PT-BR texts.
# tests/test_menus.py checks every entry has one.
DESCRIPTIONS: dict[str, str] = {
    "install": "Installs Koha with MariaDB and Apache on this server",
    "credentials": "Shows the logins and passwords of the first access",
    "restore": "Replaces Koha's database with a backup, tested first",
    "backup-manual": "Makes a full backup and shows how to copy it to a PC",
    "backup-cloud": "Connects Google Drive to keep the backups in the cloud",
    "backup-test": "Imports a backup into a test database to check it",
    "magic-import": "Imports catalogs in any format: MARC, ISIS, CSV, backups",
    "db-maintenance": "Optimizes the tables and clears old logs, with a preview",
    "reports": "Adds ready-made SQL reports to Koha's Reports module",
    "marc-replace": "Installs a staff page that replaces a record's MARC",
    "ai-assistant": "Puts an AI chat on the staff interface home page",
    "email": "Sets up the SMTP server and the circulation e-mails",
    "messaging": "Sends Koha's notices through WhatsApp and Telegram",
    "interoperability": "Turns on Koha's SIP2 and Z39.50 servers",
    "vpn": "Creates the WireGuard VPN and the devices' profiles",
    "cloudflare": "Publishes the OPAC and the staff site through Cloudflare",
    "ufw": "Lists the firewall rules active on this server",
    "staff-firewall": "Blocks or opens the staff port 8080 to the internet",
    "ssl": "Gets a free HTTPS certificate from Let's Encrypt",
    "fail2ban": "Shows the banned IPs and the intrusion attempts",
    "rotate-db-password": "Makes a new MariaDB password for Koha",
    "search-console": "Checks the OPAC and helps Google index it",
    "search-toggle": "Switches the catalog search between Zebra and Elasticsearch",
    "search-repair": "Repairs the search engine and reindexes the catalog",
    "status": "Shows services, search, disk and the last backup",
    "health": "Runs every check and writes a validation report",
    "validation-report": "Opens the latest validation report",
    "apache-log": "Follows the staff or OPAC error log live",
    "repair-services": "Restarts Memcached, Plack and Koha's services",
    "sizing": "Tunes memory and workers to this server's RAM",
    "superlibrarian": "Creates a staff account with every permission",
    "clock": "Sets the timezone and syncs the clock with NTP",
    "marc-undo": "Removes the records of an imported MARC batch",
    "authority-sync": "Links the catalog headings to their authorities",
    "patron-category": "Moves patrons from one category to another",
    "data-quality": "Finds records with missing or broken data",
    "privacy-anonymise": "Anonymises loans and holds that ended long ago",
    "privacy-delete": "Deletes expired patrons with no loans, after a backup",
    "tool-logs": "Shows what the library tools did and when",
    "brazil": "CPF check, Pimaco labels, holidays, ABNT and census",
    "cataloguing": "PHA, Cutter and CDD helpers for cataloguers",
    "cdd": "Adds a CDD lookup to the cataloguing editor",
    "plugins": "Turns Koha plugins on or off and sets their sources",
    "cutter": "Finds the Cutter number of an author",
    "monitor": "Watches CPU, memory and network live",
    "mc": "Browses the server's files in Midnight Commander",
    "crons": "Turns Koha's scheduled jobs on or off",
    "languages": "Installs or removes Koha's interface languages",
    "update-system": "Updates the system packages and Koha's database",
    "update-panel": "Downloads the newest version of this panel",
    "about": "Version, license and where to get help",
    "reboot": "Restarts the whole server",
}


def description(entry: Entry) -> str:
    return DESCRIPTIONS.get(entry.action, "")
