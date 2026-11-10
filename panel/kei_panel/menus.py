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
    # The platform this entry works on ("koha"), when its section is shared
    # by every platform (the Server area). "" = it works on any server.
    requires: str = ""
    # Where the card is drawn in its screen (views/base.py): "" with the
    # day-to-day tools; "setup" (installing), "recovery" (diagnosis and
    # recovery, drawn first when something is wrong) and "removal"
    # (removing, kept apart from the rest). A platform's home shows each
    # zone by the platform's state (platforms.home_zones).
    zone: str = ""
    # A "view" entry can open its screen already filtered: the Backup center
    # opened from Koha's group shows Koha's backups ("koha"), from
    # Tainacan's group Tainacan's ("tainacan"). "" = as the screen was left.
    # On a card of the Backup center itself, the platform view it is shown
    # in ("both": the joint backup, only with Koha and Tainacan as a set).
    scope: str = ""


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
    requires: str = ""    # platform the whole section works on ("koha"); "" = any server
    # The platform group of the sidebar it belongs to ("koha", "tainacan"):
    # drawn under that group's row, only while the group is expanded. The
    # group's own row is the section whose id is the group (its home).
    group: str = ""


# The platform groups of the sidebar, in order: the id of the platform's
# home section, which is also the group's name.
GROUPS = ("koha", "tainacan", "dspace")
# UI orchestration uses existing drivers and has no standalone Bash mutation.
PANEL_ONLY_ACTIONS = frozenset({"instance-add", "instance-remove"})

SECTIONS: tuple[Section, ...] = (
    # State, addresses and indicators of the server and of each platform
    # live here only, in tabs (views/dashboard.py).
    Section("dashboard", "Control Dashboard", view="dashboard", key="d", icon="📊"),

    Section("instances", "➕  Add or remove instance", "Instances", entries=(
        Entry("➕  Add instance", "instance-add", kind="native"),
        Entry("🗑  Remove instance", "instance-remove", kind="native", zone="removal"),
    )),

    # ---------------- Koha (library) ----------------
    # Its home: installing while Koha is absent; its tools once installed;
    # diagnosis and recovery first when its services are stopped.
    Section("koha", "📚  Koha (library)", "📚  Koha (library)", entries=(
        Entry("📦  Install Koha server", "install", kind="native", zone="setup"),
        Entry("📡  Detailed server & Koha status", "status", kind="native", zone="recovery"),
        Entry("🏥  Full system health check", "health", kind="native", zone="recovery", requires="koha"),
        Entry("🔁  Restart / repair Koha services (Memcached, Plack)", "repair-services", kind="native",
              zone="recovery", requires="koha"),
        Entry("📜  Real-time Apache log auditing", "apache-log", kind="native", zone="recovery", requires="koha"),
        Entry("🧭  Continue the setup", "setup-koha", kind="native", requires="koha"),
        Entry("🔑  View first-access credentials", "credentials", kind="native", requires="koha"),
        Entry("🔐  Administrative access", "admin-koha", kind="native", requires="koha"),
        Entry("💾  Koha backups", "backups", kind="view", scope="koha"),
        Entry("🪄  Magic Import Tool", "import", kind="view"),
        Entry("📚  Library tools", "library", kind="view"),
        Entry("📡  Z39.50 / SRU servers", "z3950", kind="view"),
        Entry("🤖  AI", "ai", kind="view"),
        Entry("🎨  OPAC and Staff Appearance", "opac", kind="view"),
        Entry("📨  Messaging & interoperability", "hub", kind="view"),
        Entry("🔍  Search engine & indexing", "search", kind="view"),
        Entry("⏰  Koha schedules", "schedules", kind="view", scope="koha"),
        Entry("🔧  Koha settings & parameters", "settings", kind="view"),
        Entry("🩺  Koha diagnostics & maintenance", "diagnostics", kind="view"),
        Entry("🛡  Koha security", "koha-security", kind="view"),
    ), view="platform-home", key="k", group="koha"),
    Section("credentials", "🔑  View first-access credentials", requires="koha", entries=(
        Entry("🔑  View first-access credentials", "credentials", kind="native"),), sidebar=False, parent="koha",
        group="koha"),
    # Every import in one place, right under the backups (Paulo, 2026-10-09).
    Section("import", "🪄  Magic Import Tool",
            prompt="Imports bibliographic records, authority records and patron (reader) data from other systems: "
                   "MARC, ISIS, CSV and spreadsheets, and old-system backups.", entries=(
        Entry("🪄  Magic Import Tool (drop anything here)", "magic-import", kind="native"),), key="i", requires="koha",
        group="koha"),
    # Enrichment jobs (views/enrich.py), opened from Library tools (or its key).
    # The batch "Enrich bibliographic catalog" screen is retired (Paulo, 1.5.94):
    # "Enrich from world catalogues" (on-demand enrichment) replaces it. Its view and installer tasks stay in the
    # code, but no key, card or sidebar row opens it.
    Section("enrich", "✨  Enrich bibliographic catalog", "✨  Enrich bibliographic catalog", view="enrich",
            sidebar=False, parent="library", requires="koha", group="koha"),
    Section("enrich-auth", "📇  Enrich & standardize authorities", "📇  Enrich & standardize authorities",
            view="enrich-auth", key="h", sidebar=False, parent="library", requires="koha", group="koha"),
    Section("ondemand", "🌐  Enrich from world catalogues", "🌐  Enrich from world catalogues", view="ondemand",
            key="n", sidebar=False, parent="library", requires="koha", group="koha"),
    Section("library", "📚  Library tools", "📚  Library tools",
            "Changes are always previewed first and protected by a verified backup.", (
        Entry("✨  Enrich bibliographic catalog", "enrich", kind="view", hidden=True),
        Entry("📇  Enrich & standardize authorities", "enrich-auth", kind="view"),
        Entry("🌐  Enrich from world catalogues", "ondemand", kind="view"),
        Entry("🔙  Undo a MARC import", "marc-undo", kind="native"),
        Entry("🔗  Sync & link authorities", "authority-sync", kind="native"),
        Entry("👥  Find duplicate authors (authorities)", "authority-match", kind="native"),
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
        Entry("📂  Staff access to server files", "access-files", kind="native"),
        Entry("🧮  Cutter Calculator", "cutter", kind="native", hidden=True),
    ), key="l", requires="koha", group="koha"),
    # New screen: this Koha's Z39.50/SRU server (on/off), the koha.nexus
    # Catalog Network, and public catalogues for copy cataloguing (Z39.50 and
    # SRU), scanned and ranked, added to Koha's z3950servers (no bash menu).
    Section("z3950", "📡  Z39.50 / SRU servers", "📡  Z39.50 / SRU servers", view="z3950", key="z", requires="koha",
            group="koha"),
    # New screen: both AI tools on one page (views/ai.py). AI cataloguing
    # (Module 1: MARC Replace, which opens the routine below) and the AI
    # assistant (Module 2: the chat on the Koha staff home page) share the
    # provider, each with its own model; Ollama models download from there.
    Section("ai", "🤖  AI", "🤖  AI", entries=(
        Entry("🔀  Replace a MARC record (staff tool)", "marc-replace", kind="native"),
        Entry("💬  AI assistant on the staff home page", "ai-assistant", kind="native"),
    ), view="ai", key="a", requires="koha", group="koha"),
    # New screen: the look of the public catalogue and the staff interface (textures, wallpaper, dark mode,
    # New arrivals carousel), written into OpacUserCSS / OpacUserJS (no bash menu).
    Section("opac", "🎨  OPAC and Staff Appearance", "🎨  OPAC and Staff Appearance", view="opac", key="o",
            requires="koha", group="koha"),
    # Messaging & interoperability: e-mail, WhatsApp/Telegram, SMS, SIP2 and
    # Z39.50 on one screen (views/hub.py); its buttons run these routines.
    # This Koha's Z39.50/SRU server is turned on and off on the z3950 screen:
    # the classic "SIP2 and Z39.50" routine stays reachable, but no button runs it.
    Section("hub", "📨  Messaging & interoperability", "📨  Messaging & interoperability", entries=(
        Entry("📧  Configure email and circulation notices", "email", kind="native"),
        Entry("💬  Messaging: WhatsApp and Telegram", "messaging", kind="native"),
        Entry("🔌  Enable interoperability (SIP2 and Z39.50)", "interoperability", kind="native", hidden=True),
    ), view="hub", key="m", requires="koha", group="koha"),
    Section("search", "🔍  Search engine & indexing", "🔍 Search Engine & Indexing", "Choose an action:", (
        Entry("🔃  Toggle search engine (Zebra ⇄ Elasticsearch)", "search-toggle", kind="native"),
        Entry("🔨  Repair / rebuild indexing", "search-repair", kind="native"),
    ), requires="koha", group="koha"),
    # The visual cron manager of koha_tasks (views/crons.py); the entry is the
    # classic routine. Reached from the Schedules center (Paulo, 2026-11-06).
    Section("crons", "⏰  Schedules & cron tasks", entries=(
        Entry("⏰  Schedules & cron tasks", "crons", kind="native"),), view="crons", requires="koha",
        sidebar=False, parent="schedules"),
    # Koha's own parameters (the clock and timezone are the server's: General tools).
    Section("settings", "🔧  Koha settings & parameters", "🔧 Koha Settings & Parameters", "Choose a parameter:", (
        Entry("📏  Server sizing (memory / workers)", "sizing", kind="native"),
        Entry("👑  Create super librarian", "superlibrarian", kind="native"),
    ), requires="koha", group="koha"),
    # Koha's diagnosis and maintenance (the server's own: Server diagnostics).
    Section("diagnostics", "🩺  Koha diagnostics & maintenance", "🩺  Koha diagnostics & maintenance",
            "Choose a tool:", (
        Entry("🏥  Full system health check", "health", kind="native"),
        Entry("📜  Real-time Apache log auditing", "apache-log", kind="native"),
        Entry("🧹  Deep database optimization & log cleanup", "db-maintenance", kind="native"),
        Entry("📑  Database tables", "database", kind="view"),
        Entry("🔁  Restart / repair Koha services (Memcached, Plack)", "repair-services", kind="native"),
    ), requires="koha", group="koha"),
    # New screen: Koha's tables at a glance (no bash menu of its own), opened
    # from Koha diagnostics & maintenance (Paulo, 2026-10-15: not on the sidebar;
    # maintenance and the reports pack have their own cards elsewhere).
    Section("database", "📑  Database tables", "📑  Database tables", view="database", key="t",
            sidebar=False, parent="diagnostics", requires="koha", group="koha"),
    # Koha's own protections (the server's are in Security & access).
    Section("koha-security", "🛡  Koha security", "🛡  Koha security", "Choose a tool:", (
        Entry("🚧  Staff firewall (restrict port 8080)", "staff-firewall", kind="native"),
        Entry("🔐  Rotate database password", "rotate-db-password", kind="native"),
        Entry("🔎  Google Search Console Assistant", "search-console", kind="native"),
    ), requires="koha", group="koha"),

    # ---------------- Tainacan (collections and museums) ----------------
    # Its home: installing while it is absent (Docker is prepared on the
    # way, after its own plan and Yes); its tools once installed; the
    # problem and the right diagnosis first when the installation is
    # incomplete or its containers or Docker are stopped. Never a restore
    # by itself: restoring lives in its Backups.
    Section("tainacan", "🏺  Tainacan (collections and museums)", "🏺  Tainacan (collections and museums)", entries=(
        Entry("📦  Install Tainacan", "tainacan-install", kind="native", zone="setup"),
        Entry("▶  Start Tainacan", "tainacan-start", kind="native", zone="recovery", requires="tainacan"),
        Entry("🩺  Tainacan diagnosis", "tainacan-status", kind="native", zone="recovery", requires="tainacan"),
        Entry("📜  Tainacan logs", "tainacan-logs", kind="native", zone="recovery", requires="tainacan"),
        Entry("🧱  Shared infrastructure", "infra", kind="view", zone="recovery"),
        Entry("🧭  Continue the setup", "setup-tainacan", kind="native", requires="tainacan"),
        Entry("🔐  Administrative access", "admin-tainacan", kind="native", requires="tainacan"),
        Entry("🌐  Tainacan address", "tainacan-address", kind="native", requires="tainacan"),
        Entry("🏠  Prepare the home page", "tainacan-site", kind="native", requires="tainacan"),
        Entry("🩺  Tainacan diagnosis & maintenance", "tainacan-maintenance", kind="view"),
        Entry("🎟  Tainacan events", "tainacan-events", kind="view"),
        Entry("💾  Tainacan backups", "backups", kind="view", scope="tainacan"),
        Entry("🗑  Uninstall Tainacan", "tainacan-uninstall", kind="native", zone="removal", requires="tainacan"),
    ), view="platform-home", key="g", group="tainacan"),
    Section("tainacan-maintenance", "🩺  Tainacan diagnosis & maintenance", "🩺  Tainacan diagnosis & maintenance",
            "The diagnosis runs only when you ask for it; its result is kept with the time it was read and shown "
            "in the Control Dashboard, Tainacan tab.", (
        Entry("🩺  Tainacan diagnosis", "tainacan-status", kind="native"),
        Entry("📜  Tainacan logs", "tainacan-logs", kind="native"),
        Entry("👤  WordPress administrator", "tainacan-credentials", kind="native"),
        Entry("🏠  Prepare the home page", "tainacan-site", kind="native"),
        Entry("↩  Undo the home page", "tainacan-site-undo", kind="native"),
    ), view="platform-section", requires="tainacan", group="tainacan"),
    Section("tainacan-events", "🎟  Tainacan events", "🎟  Tainacan events",
            "Optional and off until you turn them on, after the plan and a Yes. Turning them off keeps "
            "their data.", (
        Entry("🎟  Turn events on", "events-on", kind="native"),
        Entry("⏸  Turn events off", "events-off", kind="native"),
        Entry("📋  Events state", "events-status", kind="native"),
    ), view="platform-section", requires="tainacan", group="tainacan"),
    Section("dspace", "🏛  DSpace (repository)", "🏛  DSpace (repository)", entries=(
        Entry("📦  Install or resume DSpace", "dspace-install", kind="native", zone="setup"),
        Entry("▶  Start DSpace", "dspace-start", kind="native", zone="recovery", requires="dspace"),
        Entry("🩺  DSpace diagnosis", "dspace-diagnose", kind="native", zone="recovery", requires="dspace"),
        Entry("📜  DSpace logs", "dspace-logs", kind="native", zone="recovery", requires="dspace"),
        Entry("🧭  Continue the setup", "setup-dspace", kind="native", requires="dspace"),
        Entry("🔐  Administrative access", "dspace-admin", kind="native", requires="dspace"),
        Entry("🩺  DSpace diagnosis & maintenance", "dspace-maintenance", kind="view"),
        Entry("💾  DSpace backups", "backups", kind="view", scope="dspace"),
        Entry("🌐  DSpace address and HTTPS", "dspace-address", kind="native", requires="dspace"),
        Entry("🔄  Reviewed DSpace update", "dspace-upgrade", kind="native", requires="dspace"),
        Entry("📖  DSpace first steps", "dspace-help", kind="native", requires="dspace"),
        Entry("🗑  Remove DSpace", "dspace-remove", kind="native", zone="removal", requires="dspace"),
    ), view="platform-home", key="j", group="dspace"),
    Section("dspace-maintenance", "🩺  DSpace diagnosis & maintenance", "🩺  DSpace diagnosis & maintenance", entries=(
        Entry("🩺  DSpace diagnosis", "dspace-diagnose", kind="native"),
        Entry("📜  DSpace logs", "dspace-logs", kind="native"),
        Entry("🔧  Repair DSpace web access", "dspace-repair-web", kind="native"),
        Entry("▶  Start DSpace", "dspace-start", kind="native"),
        Entry("⏹  Stop DSpace", "dspace-stop", kind="native"),
        Entry("📖  DSpace first steps", "dspace-help", kind="native"),
    ), view="platform-section", requires="dspace", group="dspace"),

    # ---------------- Server: shared by every platform ----------------
    # Every backup in one place (Paulo, 2026-11-06): the platform is chosen
    # at the top (Koha, Tainacan; only the installed ones), each card shows
    # only for the platform it works on, and the platform groups open it
    # already filtered. Cloud connections are the server's: any platform
    # (or none yet) can add one; what each platform sends, where, when and
    # for how long is its own plan.
    Section("backups", "💾  Backup center", "💾 Backup Center", "Choose a backup routine:", (
        Entry("⏰  DSpace and platform-set plans", "dspace-plan", kind="native", requires="dspace"),
        Entry("▶  Run an encrypted backup plan", "dspace-plan-run", kind="native", requires="dspace"),
        Entry("🔐  Set up the DSpace backup key", "dspace-backup-key", kind="native", requires="dspace"),
        Entry("💾  Create encrypted DSpace backup", "dspace-backup-create", kind="native", requires="dspace"),
        Entry("🧪  Test DSpace recovery", "dspace-backup-test", kind="native", requires="dspace"),
        Entry("📥  Restore DSpace", "dspace-backup-restore", kind="native", requires="dspace"),
        Entry("📥 Download latest backup", "backup-download", kind="native", requires="koha"),
        Entry("💾  Generate manual backup and download to PC", "backup-manual", kind="native", requires="koha"),
        Entry("📚  Export MARC21 records now", "backup-marc", kind="native", requires="koha"),
        Entry("📥  Restore database", "restore", kind="native", requires="koha"),
        Entry("📤  Configure cloud backup", "backup-cloud", kind="native", requires="koha"),
        Entry("🧾  Test integrity of latest backup", "backup-test", kind="native", requires="koha"),
        Entry("💾  Back up Tainacan now", "tainacan-backup", kind="native", requires="tainacan"),
        Entry("🧪  Test a restore", "tainacan-restore-test", kind="native", requires="tainacan"),
        Entry("📥  Restore Tainacan", "tainacan-restore", kind="native", requires="tainacan"),
        Entry("⏰  Schedule backups", "pbackup-schedule", kind="native", requires="tainacan"),
        Entry("☁  Repository and cloud copy", "pbackup-configure", kind="native", requires="tainacan"),
        Entry("🧾  Verify backups", "pbackup-verify", kind="native", requires="tainacan"),
        Entry("⏯  Incomplete backup", "pbackup-incomplete", kind="native", requires="tainacan"),
        Entry("🔐  Set up encrypted backups", "pbackup-setup", kind="native", requires="tainacan"),
        Entry("🧰  Recovery kit", "pbackup-kit", kind="native", requires="tainacan"),
        Entry("📦  Joint backup (Koha + Tainacan)", "set-backup", kind="native", scope="both"),
        Entry("⏰  Schedule the joint backup", "set-schedule", kind="native", scope="both"),
        Entry("♻  Assisted restore", "restore-assisted", kind="native"),
        Entry("🔌  Cloud connections", "cloud-connections", kind="native"),
        Entry("📦  Create full Nexus backup", "nexus-backup-create", kind="native", scope="nexus"),
        Entry("🧾  Verify full Nexus package", "nexus-backup-verify", kind="native", scope="nexus"),
        Entry("♻  Recover full Nexus backup", "nexus-backup-restore", kind="native", scope="nexus"),
        Entry("⏯  Recovery sessions", "nexus-backup-sessions", kind="native", scope="nexus"),
        Entry("🔐  Shared recovery key", "nexus-backup-key", kind="native", scope="nexus"),
        Entry("🧰  Save recovery kit", "nexus-backup-kit", kind="native", scope="nexus"),
    ), view="backups", key="b"),
    # Unified inventory and confirmed edits through the original schedule writers.
    # Manual/package jobs remain read-only; the original editors stay available.
    Section("schedules", "⏰  Schedules", "⏰ Schedules", entries=(
        Entry("⏰  DSpace and platform-set plans", "dspace-plan", kind="native", requires="dspace"),
        Entry("✏  Koha's scheduled jobs", "crons", kind="view", requires="koha"),
        Entry("⏰  Schedule backups", "pbackup-schedule", kind="native", requires="tainacan"),
        Entry("⏰  Schedule the joint backup", "set-schedule", kind="native", requires="koha+tainacan"),
    ), view="schedules", key="s"),
    # Security, remote access and the firewall in one hub: VPN, Cloudflare
    # Tunnel, UFW, HTTPS and Fail2ban (it replaces "Publish system to
    # internet" and "Security center"). The Tunnel and HTTPS only serve
    # Koha for now: their cards say so and show only with Koha installed.
    Section("security", "🔒  Security & access hub", "🔒 Security & Access Hub",
            "Choose a security or remote-access tool:", (
        Entry("🔐  WireGuard VPN", "vpn", kind="view"),
        Entry("🌉  Cloudflare Tunnel Manager (Recommended)", "cloudflare", kind="native", requires="koha"),
        Entry("🧱  Show active UFW rules", "ufw", kind="native"),
        Entry("🔏  Free SSL certificate (Certbot / Apache)", "ssl", kind="native", requires="koha"),
        Entry("🚨  Fail2ban status (intrusion attempts)", "fail2ban", kind="native"),
    ), key="x"),
    # WireGuard VPN for the staff interface and SSH (views/vpn.py), opened
    # from the Security & access hub (or its key).
    Section("vpn", "🔐  WireGuard VPN", "🔐  WireGuard VPN", view="vpn", key="v", sidebar=False,
            parent="security"),
    # What the platforms in containers share: the web proxy and Docker (the
    # key and the recovery kit of their backups live in the Backup center).
    Section("infra", "🧱  Shared infrastructure", "🧱  Shared infrastructure",
            "What the platforms in containers use together: the web server in front of them and Docker.", (
        Entry("🐳  Install Docker", "docker-install", kind="native"),
        Entry("🗑  Remove Docker", "docker-remove", kind="native", zone="removal"),
    ), view="platform-section", key="p"),
    Section("server-diagnostics", "🩺  Server diagnostics", "🩺  Server diagnostics", "Choose a tool:", (
        Entry("📡  Detailed server & Koha status", "status", kind="native"),
        Entry("📄  View latest validation report", "validation-report", kind="native"),
        Entry("📦  Export diagnostics", "export-diagnostics", kind="native"),
        Entry("🗂  Open diagnostics", "open-diagnostics", kind="native"),
    )),
    Section("languages", "🌍  Languages", "🌍 Panel & application languages", "Choose an action:", (
        Entry("🏛  DSpace interface languages", "dspace-languages", kind="native", requires="dspace"),
        Entry("🌍  Download & activate a language", "languages", kind="native"),
        Entry("📥  Download a language pack only", "lang-download", kind="native", requires="koha"),
        Entry("✅  Set an installed language as active", "lang-activate", kind="native", requires="koha"),
        Entry("📋  Installed languages & active one", "lang-list", kind="native", requires="koha"),
    )),
    Section("update", "🔄  Update center", "🔄 Update Center", "Choose what to update:", (
        Entry("🆙  Update OS packages & Koha schemas", "update-system", kind="native"),
        Entry("🆕  Update this panel via GitHub", "update-panel", kind="native"),
    )),
    Section("tools", "🧰  General tools", "🧰 General Tools", "Choose a tool:", (
        Entry("📂  Open user folder", "user-folder", kind="native"),
        Entry("💻  Open Debian terminal", "terminal", kind="native"),
        Entry("📊  Resource monitoring (Htop / Nethogs)", "monitor", kind="native"),
        Entry("📂  File explorer (Midnight Commander)", "mc", kind="native"),
        Entry("🕒  Clock and timezone (NTP)", "clock", kind="native"),
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


# The platform routines of the panel (routines/platforms.py): each runs
# installer tasks (--task), none is a classic --run routine. The task a card
# needs from the installer in use, or its card is not drawn.
PLATFORM_TASKS: dict[str, str] = {
    **{name: "dspace-panel" for name in ("dspace-install", "dspace-start", "dspace-stop", "dspace-diagnose", "dspace-logs", "dspace-admin", "dspace-help", "setup-dspace", "dspace-backup-create", "dspace-backup-test", "dspace-backup-restore", "dspace-backup-key", "dspace-plan", "dspace-plan-run", "dspace-address", "dspace-upgrade", "dspace-remove", "dspace-repair-web", "dspace-languages")},
    "docker-install": "docker-plan", "docker-remove": "docker-remove",
    "tainacan-install": "tainacan-plan", "tainacan-status": "tainacan-status", "tainacan-logs": "tainacan-logs",
    "tainacan-credentials": "tainacan-credentials", "tainacan-uninstall": "tainacan-uninstall",
    "tainacan-start": "tainacan-start", "tainacan-site": "tainacan-site", "tainacan-site-undo": "tainacan-site",
    "tainacan-backup": "tainacan-backup", "tainacan-restore-test": "tainacan-restore-test",
    "tainacan-restore": "tainacan-restore", "events-on": "tainacan-events", "events-off": "tainacan-events",
    "events-status": "tainacan-events", "pbackup-setup": "platform-backup-setup",
    "pbackup-kit": "platform-backup-kit", "pbackup-configure": "platform-backup-repo",
    "pbackup-schedule": "platform-backup-schedule", "pbackup-verify": "platform-backup-verify",
    "pbackup-incomplete": "platform-backup-incomplete", "cloud-connections": "cloud-list",
    **{action: "nexus-full" for action in ("nexus-backup-create", "nexus-backup-verify", "nexus-backup-restore", "nexus-backup-sessions")},
    "nexus-backup-key": "platform-backup-setup", "nexus-backup-kit": "platform-backup-kit",
    "set-backup": "set-backup", "restore-assisted": "set-inspect", "set-schedule": "set-schedule",
    "tainacan-address": "tainacan-address", "admin-koha": "admin-status", "admin-tainacan": "admin-status",
    "setup-koha": "setup-status", "setup-tainacan": "setup-status",
}

# Panel routines with no installer routine of their own (routines/).
PANEL_ONLY = frozenset({"backup-download", "user-folder", "terminal", "export-diagnostics",
                        "open-diagnostics"} | set(PLATFORM_TASKS))

# Routines started from a button rather than a menu card, with the
# platform they work on (the dashboard's "Restart Koha").
BUTTON_REQUIRES: dict[str, str] = {"restart-koha": "koha"}


def children(group: str) -> list[Section]:
    """The sections drawn under a platform group of the sidebar."""
    return [s for s in SECTIONS if s.group == group and s.id != group and s.sidebar]


def group_of(section_id: str) -> str:
    """The platform group a section belongs to ("" = the Server area)."""
    sec = section(section_id)
    return sec.group or (section(sec.parent).group if sec.parent else "")


def requires_of(action: str) -> str:
    """The platform a routine or a view works on ("" = any server): the
    entry's own `requires`, else its section's. A "view" entry names a
    section: that section's requirement."""
    if action in BUTTON_REQUIRES:
        return BUTTON_REQUIRES[action]
    for s in SECTIONS:
        if s.id == action and s.requires:
            return s.requires
        for e in s.entries:
            if e.action == action and (e.requires or s.requires):
                return e.requires or s.requires
    return ""


def platform_actions(platform: str) -> set[str]:
    """Installer actions (--run) that need `platform`: the list the
    installer keeps too (KEI_KOHA_ACTIONS), checked by tests/test_menus.py."""
    return {a for a in all_actions() if requires_of(a) == platform}


def all_actions() -> set[str]:
    """Installer actions (a view entry opens a screen, not a routine)."""
    return {e.action for s in SECTIONS for e in s.entries if e.kind != "view" and e.action not in PANEL_ONLY}


# The line under each card (widgets/cards.py): what the routine does, in a
# few words. English keys like the labels; pt.cache holds the PT-BR texts.
# tests/test_menus.py checks every entry has one.
DESCRIPTIONS: dict[str, str] = {
    "instance-add": "Choose an available application driver and review its installation plan.",
    "instance-remove": "Choose an installation and review whether to preserve or erase its data.",
    "dspace-address": "Plan a canonical local, institutional HTTPS or free repository address without modifying another platform. Existing certificate/key files or an external TLS proxy are required for HTTPS. A verified encrypted safety backup precedes URL changes.",
    "dspace-upgrade": "Updates only the reviewed recipe 3 to 4 of DSpace 10.1 using an immutable image catalog. It tests a safety backup, preserves the database schema and volumes, and rolls back configuration if validation fails.",
    "dspace-remove": "Keeps repository data by default. Erasing active owned volumes needs an additional typed confirmation and a verified safety backup. Other platforms and shared infrastructure remain.",
    "dspace-plan": "Creates or edits a backup plan with fixed participants, daily time, retention and an optional existing cloud connection. Old Koha/Tainacan plans never silently include DSpace.",
    "dspace-plan-run": "Runs an explicit plan immediately. The entire output is encrypted, cloud upload is checked and partial captures or failed uploads do not prune good backups.",
    "dspace-backup-key": "Configures the existing shared backup key and recovery kit for encrypted DSpace packages.",
    "dspace-backup-create": "Pauses the repository and encrypts PostgreSQL, private configuration, files and every cold Solr core.",
    "dspace-backup-test": "Recovers into independent volumes with no external network or public ports and checks records and file hashes.",
    "dspace-backup-restore": "Makes a safety backup, verifies a recovery copy, then replaces active volume references while preserving previous data.",
    "backups:dspace": "Encrypted DSpace backup, isolated recovery verification and guarded restoration",
    "dspace-install": "Checks the reviewed images first, prepares Docker/Apache only with consent, then shows the repository installation plan. An incomplete migration requires explicit investigation before retry.",
    "dspace-start": "Starts the existing DSpace services without reinstalling, restoring or changing the approved migration history.",
    "dspace-stop": "Stops the repository gracefully, retaining configuration and every data volume.",
    "dspace-diagnose": "Explicitly checks PostgreSQL, all seven Solr cores, API, interface and isolation; process state alone does not establish health.",
    "dspace-languages": "Selects bundled interface translations and the fallback language. Existing account, browser and panel preferences remain independent.",
    "dspace-repair-web": "Repairs the UI/API address and managed proxy with a private configuration rollback copy. No database migration, image replacement or data deletion.",
    "dspace-logs": "Shows bounded container logs with sensitive fields redacted. It never exports private configuration or the database password.",
    "dspace-admin": "Creates an administrator with an e-mail, chosen password and language, or resets an existing administrator. Creating refuses an e-mail already used by any account.",
    "setup-dspace": "Offers administrator setup now or later and keeps a reminder for subsequent stages. The permanent menus remain available.",
    "dspace-help": "Explains communities, collections, deposits and access policies, with the repository login address.",
    "dspace-maintenance": "Diagnosis, logs, safe start/stop and first steps of the DSpace repository.",

    "install": "Installs Koha with MariaDB and Apache on this server",
    "credentials": "Shows the logins and passwords of the first access",
    "admin-koha": "Superlibrarians: the web installer, a new one, a new password",
    "admin-tainacan": "Administrators: your own password, a new password, another administrator",
    "setup-koha": "The steps left after the installation: access, address, backup",
    "setup-tainacan": "The steps left after the installation: access, address, backup",
    "tainacan-address": "The address of the collection: local network, your own domain or a free koha.nexus address",
    "restore": "Replaces Koha's database with a backup, tested first",
    "backup-manual": "Makes a full backup and shows how to copy it to a PC",
    "backup-marc": "Exports the catalogue and the authorities in MARC21 now",
    "backup-download": "Copies the newest backup to this computer's Downloads folder",
    "backup-cloud": "Automates backups uploaded to cloud storage services",
    "backup-test": "Imports a backup into a test database to check it",
    "magic-import": "Imports bibliographic and authority records and patron data: MARC, ISIS, CSV, backups",
    "database": "Koha's tables, largest first, with rows and size",
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
    "ssl": "Free HTTPS certificate, only for your own domain without the tunnel",
    "fail2ban": "Shows the banned IPs and the intrusion attempts",
    "rotate-db-password": "Makes a new MariaDB password for Koha",
    "search-console": "Checks the OPAC and keeps its sitemap for Google up to date",
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
    "enrich": "Adds subjects, classification and notes from open catalogues, with a report before Apply",
    "enrich-auth": "Links names and subjects to authorities (BN first) and creates the missing ones, with a report",
    "ondemand": "Completes your records with data from library catalogues around the world, or finds a new book to import",
    "marc-undo": "Removes the records of an imported MARC batch",
    "authority-sync": "Links the catalog headings to their authorities",
    "authority-match": "Finds variant forms of one author and merges the ones you confirm",
    "patron-category": "Moves patrons from one category to another",
    "data-quality": "Finds records with missing or broken data",
    "privacy-anonymise": "Anonymises loans and holds that ended long ago",
    "privacy-delete": "Deletes expired patrons with no loans, after a backup",
    "tool-logs": "Shows what the library tools did and when",
    "brazil": "CPF check, Pimaco labels, holidays, ABNT and census",
    "cataloguing": "PHA, Cutter and CDD helpers for cataloguers",
    "cdd": "Adds a CDD lookup to the cataloguing editor",
    "plugins": "Turns Koha plugins on or off and sets their sources",
    "access-files": "Fixes the access_dir error of Tools > Access files in Koha",
    "cutter": "Finds the Cutter number of an author",
    "monitor": "Watches CPU, memory and network live",
    "mc": "Browses the server's files in Midnight Commander",
    "user-folder": "Opens your home folder in Windows Explorer or the file manager",
    "terminal": "A Debian command line: its own window on Windows, this window elsewhere",
    "crons": "Turns Koha's scheduled jobs on or off",
    "schedules": "Every scheduled job of this server, its last and next run",
    "schedules:koha": "Koha's scheduled jobs: when they run, the last and the next run",
    "languages": "Downloads a language and makes it the OPAC, staff and panel one",
    "lang-download": "Downloads a Koha language pack and changes nothing else",
    "lang-activate": "Makes an installed language the active one, no download",
    "lang-list": "Lists the installed languages and the active ones",
    "update-system": "Updates the system packages and Koha's database",
    "update-panel": "Downloads the newest version of this panel",
    "about": "Version, license and where to get help",
    "reboot": "Restarts the whole server",
    # The cards of the platform homes that open a screen of the group (or,
    # for a card with a scope, the shared screen filtered: "ACTION:SCOPE").
    "backups": "Every backup of this server: Koha, Tainacan, cloud connections and plans",
    "backups:koha": "Backups of Koha's database, MARC21 exports, restore and cloud copies",
    "backups:tainacan": "Back up, test a restore, restore, schedule and cloud copy",
    "import": "Imports records and patrons from other systems, with checks first",
    "library": "Enrichment, authorities, reports, privacy and other catalogue tools",
    "z3950": "Koha's Z39.50/SRU server and the catalogues for copy cataloguing",
    "ai": "AI cataloguing and the AI assistant of the staff interface",
    "opac": "The look of the public catalogue and of the staff interface",
    "hub": "E-mail, WhatsApp, Telegram and SMS notices",
    "search": "Zebra or Elasticsearch, and rebuilding the index",
    "settings": "Server sizing and the super librarian account",
    "diagnostics": "Health check, Apache log, database upkeep and Koha's services",
    "koha-security": "Staff port, database password and Google Search Console",
    "infra": "Docker and the web proxy in front of the platforms",
    "tainacan-maintenance": "Diagnosis, logs and the WordPress administrator",
    "tainacan-events": "Events, bookings and certificates in Tainacan: optional",
    # Tainacan, Docker and the platform backups (routines/platforms.py).
    "tainacan-install": "Installs WordPress and Tainacan in containers, after its plan and a Yes",
    "tainacan-status": "Checks the containers, WordPress, the plugin and the collections",
    "tainacan-logs": "The latest lines of the containers' logs, secrets blanked",
    "tainacan-credentials": "The WordPress account of Tainacan's administrators",
    "tainacan-start": "Starts Docker and Tainacan's containers again, with the data as it is; nothing is restored",
    "tainacan-site": "A home page with the search of the collection and links to the collections and items",
    "tainacan-site-undo": "Puts back the home page and settings that were there before",
    "tainacan-uninstall": "Removes Tainacan; you choose whether its data is kept",
    "events-on": "Shows the plan, then turns on Nexus Eventos over Events Manager",
    "events-off": "Turns events off and keeps their data",
    "events-status": "Whether events are on, both plugins and the data kept",
    "tainacan-backup": "A full backup of Tainacan now: database, files and configuration",
    "tainacan-restore-test": "Restores a backup in an isolated copy and compares it, nothing else changes",
    "tainacan-restore": "Replaces the Tainacan in use with a backup, tested first",
    "pbackup-schedule": "A daily backup, weekly upkeep and a monthly restore test",
    "pbackup-configure": "Where the files go (restic repository) and the copy in the cloud",
    "pbackup-verify": "Checks the backups and the repository now",
    "pbackup-incomplete": "Resumes or discards a backup that stopped before the end",
    "docker-install": "Installs Docker after its plan and a Yes; nothing else changes",
    "docker-remove": "Removes the Docker Koha.Nexus installed, only when nothing is left in it",
    "pbackup-setup": "Makes the server key that encrypts the configuration in the backups",
    "pbackup-kit": "Saves the recovery kit to copy away from this server",
    "cloud-connections": "The cloud accounts this server can send backups to, for any platform",
    "nexus-backup-create": "All installed applications, Nexus settings and immutable container images in one encrypted portable package",
    "nexus-backup-verify": "Verify the recovery phrase and every archived checksum without using the original server keyring",
    "nexus-backup-restore": "Review compatible application recovery and preserve destination addresses and publication identities",
    "nexus-backup-sessions": "Review or resume interrupted recoveries; remove completed private staging explicitly",
    "nexus-backup-key": "Configure the existing shared OpenPGP recovery key",
    "nexus-backup-kit": "Save the current protected key and recovery instructions separately",
    "set-backup": "One file with the data of Koha and of Tainacan, each captured in turn, with its checksums",
    "set-schedule": "The joint backup every day: its folder, how many sets are kept and an encrypted cloud copy",
    "restore-assisted": "Recognises any backup by its content, shows where it came from and restores what you choose",
    "export-diagnostics": "Saves a report of this server to send to whoever helps you",
    "open-diagnostics": "Reads a diagnostics report saved here or sent to you",
}


def description(entry: Entry) -> str:
    if entry.scope:
        return DESCRIPTIONS.get(f"{entry.action}:{entry.scope}") or DESCRIPTIONS.get(entry.action, "")
    return DESCRIPTIONS.get(entry.action, "")
