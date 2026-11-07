"""Routines ported to the panel: their questions are Textual screens, their
work runs as `config.sh --task` behind the Pac-Man loader, their answers
come back as a result screen. No whiptail box is opened.

Each routine is an async function (app) run in a worker, so a flow reads
top to bottom with `await app.push_screen_wait(...)`. ROUTINES maps the
menu's --run action to it; menus.Entry(kind="native") marks the entries.
An installer without `--task` (older than the panel) keeps the classic
routine (app.run_entry falls back to it).
"""

from __future__ import annotations

from typing import Awaitable, Callable

from . import (dspace, admin_access, backup, backup_set, database, diagnostics, install, platforms, search, security, setup,
               settings, tools)

Routine = Callable[[object], Awaitable[None]]

ROUTINES: dict[str, Routine] = {
    **{"dspace-" + name: getattr(dspace, name) for name in ("install", "start", "stop", "diagnose", "logs", "admin", "help")},
    "setup-dspace": dspace.assistant,
    "backup-manual": backup.manual_backup,
    "backup-test": backup.test_backup,
    "backup-marc": backup.marc_backup,
    "backup-cloud": backup.cloud_backup,
    "cloud-connections": backup.cloud_connections,      # Backup center, any platform
    "set-backup": backup_set.set_backup,                # Backup center, Koha and Tainacan
    "set-schedule": backup_set.set_schedule,            # Backup center and Schedules, Koha and Tainacan
    "restore-assisted": backup_set.restore_assisted,    # Backup center, any backup
    "restore": backup.restore,
    "backup-download": backup.download_latest,           # backup view
    "db-maintenance": database.deep_maintenance,
    "reports": database.reports_pack,
    "install": install.install_koha,
    "credentials": install.credentials,
    "status": diagnostics.status,
    "health": diagnostics.health,
    "validation-report": diagnostics.validation_report,
    "apache-log": diagnostics.apache_log,
    "repair-services": diagnostics.repair_services,
    "restart-koha": diagnostics.restart_koha,               # dashboard
    "export-diagnostics": diagnostics.export_diagnostics,   # dashboard
    "open-diagnostics": diagnostics.open_diagnostics,       # dashboard
    "search-toggle": search.toggle,
    "search-repair": search.repair,
    "fail2ban": security.fail2ban,
    "ufw": security.ufw,
    "staff-firewall": security.staff_firewall,
    "rotate-db-password": security.rotate_password,
    "cloudflare": security.cloudflare,
    "sizing": settings.sizing,
    "email": settings.email,
    "superlibrarian": settings.superlibrarian,
    "interoperability": settings.interoperability,
    "clock": settings.clock,
    "languages": tools.languages,
    "lang-activate": tools.language_activate,
    "update-panel": tools.update_panel,
    "monitor": tools.monitor,
    "mc": tools.mc,
    "user-folder": tools.user_folder,
    "terminal": tools.terminal,
    # Docker, Tainacan and the platform backups (menus.PLATFORM_TASKS).
    "docker-install": platforms.install_docker,
    "docker-remove": platforms.remove_docker,
    "tainacan-install": platforms.tainacan_install,
    "tainacan-status": platforms.tainacan_status,
    "tainacan-logs": platforms.tainacan_logs,
    "tainacan-credentials": platforms.tainacan_credentials,
    "tainacan-start": platforms.tainacan_start,
    "tainacan-site": platforms.tainacan_site,
    "tainacan-site-undo": platforms.tainacan_site_undo,
    "tainacan-uninstall": platforms.tainacan_uninstall,
    "tainacan-backup": platforms.tainacan_backup,
    "tainacan-restore-test": platforms.tainacan_restore_test,
    "tainacan-restore": platforms.tainacan_restore,
    "events-on": platforms.events_on,
    "events-off": platforms.events_off,
    "events-status": platforms.events_status,
    "pbackup-setup": platforms.backup_setup,
    "pbackup-kit": platforms.backup_kit,
    "pbackup-configure": platforms.backup_configure,
    "pbackup-schedule": platforms.backup_schedule,
    "pbackup-verify": platforms.backup_verify,
    "pbackup-incomplete": platforms.backup_incomplete,
    "tainacan-address": platforms.tainacan_address,
    # Administrative access and the steps after a new installation.
    "admin-koha": admin_access.koha_admin,
    "admin-tainacan": admin_access.tainacan_admin,
    "setup-koha": setup.koha_setup,
    "setup-tainacan": setup.tainacan_setup,
}

# The rest run their classic routine with `--task run ACTION`; the title is
# the menu label's (an installer text).
GENERIC: dict[str, str] = {
    "ssl": "🔏  Free SSL certificate (Certbot / Apache)",
    "search-console": "🔎  Google Search Console Assistant",
    "library-tools": "📚  Library tools",
    "magic-import": "🪄  Magic Import Tool (drop anything here)",
    "marc-undo": "🔙  Undo a MARC import",
    "authority-sync": "🔗  Sync & link authorities",
    "authority-match": "👥  Find duplicate authors (authorities)",
    "patron-category": "🎓  School-year turnover (patron categories)",
    "data-quality": "🧪  Catalog data-quality check",
    "privacy-anonymise": "🎭  Privacy (LGPD): anonymise old history",
    "privacy-delete": "🚮  Privacy (LGPD): delete old patrons",
    "tool-logs": "📜  View tool logs",
    "brazil": "🌎  Brazil: localization",
    "messaging": "💬  Messaging: WhatsApp and Telegram",
    "cataloguing": "📝  Cataloguing aids: PHA, Cutter, CDD",
    "marc-replace": "🔀  Replace a MARC record (staff tool)",
    "cdd": "🔎  CDD lookup in the cataloguing (staff tool)",
    "plugins": "🧩  Koha plugins (turn on or off)",
    "access-files": "📂  Staff access to server files",
    "cutter": "🧮  Cutter Calculator",
    "ai-assistant": "💬  AI assistant on the staff home page",
    "crons": "⏰  Schedules & cron tasks",
    "lang-download": "📥  Download a language pack only",
    "lang-list": "📋  Installed languages & active one",
    "update-system": "🆙  Update OS packages & Koha schemas",
    "about": "💡  About the program & support",
    "reboot": "🔁  Reboot server",
}
for _action, _title in GENERIC.items():
    ROUTINES.setdefault(_action, tools.generic(_action, _title))


def has(action: str) -> bool:
    return action in ROUTINES


def task_of(action: str) -> str:
    """The `--task` the routine needs from the installer ("" = its own)."""
    from ..menus import PLATFORM_TASKS
    if action in PLATFORM_TASKS:
        return PLATFORM_TASKS[action]
    if action in GENERIC or action in ("languages", "lang-activate", "update-panel"):
        return "run"
    if action in ("monitor", "mc"):
        return "tool-install"
    return ""
