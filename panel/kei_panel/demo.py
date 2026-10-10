"""Simulated `--task` answers for demo mode and the tests: the same @@
lines the installer prints, fed through the real parser."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .bridge import TaskOutcome
    from .tasks import Reporter

_HOME = "/root"
_NEWEST = "/var/backups/koha_sql/koha_library_2026-10-02_03h00.sql.gz"

_CREDS = [
    "@@result cred=ON THIS MACHINE (localhost):\tOPAC  (catalog)\thttp://localhost:80",
    "@@result cred=ON THIS MACHINE (localhost):\tStaff (administration)\thttp://localhost:8080",
    "@@result cred=FROM OTHER COMPUTERS ON THE NETWORK:\tOPAC  (catalog)\thttp://192.0.2.10:80",
    "@@result cred=FROM OTHER COMPUTERS ON THE NETWORK:\tStaff (administration)\thttp://192.0.2.10:8080",
    "@@result cred=SSH ACCESS (remote terminal):\tSSH\tssh root@192.0.2.10",
    "@@result cred=DATABASE CREDENTIALS (1st Access / Web Installer):\tUser\tkoha_library",
    "@@result cred=DATABASE CREDENTIALS (1st Access / Web Installer):\tPass\tdemo-Pa55word",
    "@@result cred=DATABASE CREDENTIALS (1st Access / Web Installer):\tFull file\t/root/koha_credentials.txt",
]
_REPORT = ("@@preview Diagnostic Report\t=====\\nKOHA.NEXUS - VALIDATION REPORT\\n"
           "✅ Root OK.\\n✅ HTTPS: Koha repository responded.\\n✅ Disk: 41000 MB free.\\n"
           "❗ TCP 80 already in use by 'apache2'.")
_STAGES = [("1/7", "Preparing the system", ["Checking the package manager", "Setting up language and UTF-8",
                                            "Updating the system"]),
           ("2/7", "Essential tools", ["Installing essential packages", "Adding the Koha repositories"]),
           ("3/7", "Database and Koha", ["Downloading and installing Koha", "Starting the database"]),
           ("4/7", "Web server", ["Configuring Apache and Koha"]),
           ("5/7", "Your library", ["Creating the Koha instance", "Starting Koha (Plack)"]),
           ("6/7", "Search and safety", ["Turning on the search index", "Setting up backups and credentials"]),
           ("7/7", "Services", ["Restarting Koha services", "Cleaning temporary files",
                                "Checking that everything works"])]
_INSTALL = [line for n, stage, steps in _STAGES
            for line in [f"@@stage [{n}] {stage}\tThis might take a few minutes. Please keep this window open."]
            + [x for step in steps for x in (f"@@step {step}", f"@@done 0 {step}")]]

_SCRIPTS: dict[str, list[str]] = {
    "ollama-install": ["@@step Installing Ollama", "@@done 0 Installing Ollama",
                       "@@msg ok OK\tOllama is already installed and running."],
    "tool-install": ["@@result iface=eth0"],
    "info": [
        "@@result real_user=root", "@@result timezone=America/Sao_Paulo", f"@@result real_home={_HOME}", "@@result server_ip=192.0.2.10",
        "@@result dir_sql=/var/backups/koha_sql", "@@result compression=gz", "@@result compression_used=gz",
        "@@result koha_installed=yes",
        f"@@result newest={_NEWEST}", "@@result newest_date=2026-10-02 03:00",
        "@@result newest_size=46M", "@@result rclone=yes", "@@result rclone_remote=gdrive",
    ],
    "backup-compression": ["@@result compression={0}"],
    "backup-manual": [
        "@@note Generating the backup...",
        "@@result file={0}/koha_library_manual_2026-10-03_12h00.sql.gz", "@@result size=46M",
        "@@result scp=scp root@192.0.2.10:{0}/koha_library_manual_2026-10-03_12h00.sql.gz Downloads/",
        "@@result user=root",
    ],
    "backup-test": [
        "@@ask Test Backup\tRun the test now?", "@@note Importing into a temporary database...",
        f"@@result file={_NEWEST}", "@@result tables=312", "@@result biblios=48210",
        "@@result patrons=3921", "@@msg ok OK\tBACKUP IS INTACT AND RESTORABLE.",
    ],
    "restore-check": [
        "@@note Checking the backup file...", "@@result size_mb=180", "@@result need_mb=526",
        "@@result free_mb=41000", "@@result has_sql=yes", "@@result complete=yes",
    ],
    "restore": [
        "@@title Restoring the catalog",
        "@@step Testing the backup in a temporary database", "@@done 0 Testing the backup in a temporary database",
        "@@step Saving a safety backup of the current database",
        "@@done 0 Saving a safety backup of the current database",
        "@@note Safety backup: /var/backups/koha_sql/pre_restore_safety_backup_2026-10-03_12h00m00.sql.gz",
        "@@step Stopping Koha services", "@@done 0 Stopping Koha services",
        "@@step Recreating the database", "@@done 0 Recreating the database",
        "@@step Importing the catalog", "@@done 0 Importing the catalog",
        "@@step Upgrading the database schema", "@@done 0 Upgrading the database schema",
        "@@step Synchronizing the search engine", "@@done 0 Synchronizing the search engine",
        "@@step Reindexing the catalog", "@@done 0 Reindexing the catalog",
        "@@step Restarting Koha services", "@@done 0 Restarting Koha services",
        "@@step Checking that everything works", "@@done 0 Checking that everything works",
        "@@result engine=Zebra", "@@result tables=312",
        "@@result safety_backup=/var/backups/koha_sql/pre_restore_safety_backup_2026-10-03_12h00m00.sql.gz",
        "@@msg ok OK\tCatalog restored and indexed successfully!",
    ],
    "cloud-prepare": ["@@step Installing rclone", "@@done 0 Installing rclone"],
    "cloud-token": [
        "@@step Registering 'gdrive' remote in Rclone...", "@@done 0 Registering 'gdrive' remote in Rclone...",
        "@@note Testing the real cloud upload...",
        "@@msg ok OK\tCloud enabled and tested successfully.",
    ],
    "cloud-authorize": [
        "@@result auth_url=http://127.0.0.1:53682/auth?state=demo",
        "@@result auth_tunnel=ssh -L 53682:127.0.0.1:53682 root@192.0.2.10",
        "@@note Waiting for the authorization...",
        "@@step Registering 'gdrive' remote in Rclone...", "@@done 0 Registering 'gdrive' remote in Rclone...",
        "@@msg ok OK\tCloud enabled and tested successfully.",
    ],
    "cloud-remotes": ["@@result remote=gdrive", "@@result remote=onedrive"],
    "install-check": [
        _REPORT, "@@result v_ok=12", "@@result v_warn=1", "@@result v_fail=0", "@@result busy_ports=80",
        "@@result port_info=- Port 80: apache2\\n", "@@result tz=America/Sao_Paulo", "@@result exists=yes",
        "@@result db_name=koha_library", "@@result can_reboot=yes",
    ],
    "install-free-ports": ["@@note Stopping web services to free ports 80 and 8080..."],
    "timezones": ["@@result tz=America/Sao_Paulo", "@@result tz=Europe/Lisbon", "@@result tz=UTC"],
    "install": _INSTALL + ["@@result v_ok=40", "@@result v_warn=1", "@@result v_fail=0",
                           "@@result can_reboot=yes"] + _CREDS,
    "credentials": _CREDS,
    "validation-report": [_REPORT],
    "reboot": ["@@msg ok OK\tRebooting in 5 seconds to consolidate services..."],
    "status": [f"@@result row={g}\t{k}\t{v}" for g, k, v in [
        ("SERVICES", "Apache", "🟢 active"), ("SERVICES", "MariaDB", "🟢 active"),
        ("SERVICES", "Memcached", "🟢 active"), ("SERVICES", "Plack", "🟢 running"),
        ("SERVICES", "Zebra", "⚪ inactive"), ("SERVICES", "Elasticsearch", "🟢 active"),
        ("SEARCH", "Engine", "Elasticsearch"), ("SEARCH", "Pending jobs", "0"),
        ("SEARCH", "Index/database", "48210 / 48210"), ("MACHINE", "Memory", "3.1Gi / 7.7Gi"),
        ("MACHINE", "Disk (/)", "41G free of 80G"), ("BACKUP", "Latest SQL", "2026-10-02 03:00")]],
    "health": ["@@title Full system validation", "@@step Checking that everything works",
               "@@done 0 Checking that everything works", "@@msg ok OK\tNo critical failures.\\n\\nOK: 40   Warnings: 1",
               _REPORT],
    "apache-log": ["@@result file=/var/log/koha/library/intranet-error.log"],
    "repair-services": ["@@title Restarting Koha services", "@@step Restarting Koha services",
                        "@@done 0 Restarting Koha services",
                        "@@msg ok OK\tKoha services restarted.\\n\\nMemcached: active\\nPlack: running"],
    "export-diagnostics": ["@@step Collecting logs and system status", "@@done 0 Collecting logs and system status",
                           "@@result path=/var/log/koha-easy-install/diagnostics/koha-diagnostics-koha-20261004-0130"],
    "search-toggle": [
        "@@ask Search Engine\tCurrent engine: ZEBRA.\\n\\nEnable ELASTICSEARCH? It brings advanced search and dynamic"
        "\\nfacets, but needs about 1.5 GB more RAM and more disk.",
        "@@title Switching the search engine to Elasticsearch",
        *[x for step in ["Stopping Zebra", "Installing Elasticsearch 7", "Configuring Elasticsearch",
                         "Starting Elasticsearch", "Declaring Elasticsearch in Koha", "Restarting Koha services",
                         "Starting the indexer", "Reindexing the catalog", "Starting Koha (Plack)",
                         "Checking that everything works"]
          for x in (f"@@step {step}", f"@@done 0 {step}")],
        "@@msg ok OK\tSystem now running on ELASTICSEARCH.\\n\\nThe indexer has automatic recovery and the "
        "watchdog checks the queue every 5 minutes.",
        "@@ask View Report\tDo you want to see the detailed system validation report now?",
        _REPORT,
    ],
    "search-repair": [
        "@@msg info Diagnostics\tElasticsearch (9200) : OK\\nIndexer              : STOPPED\\n"
        "Pending jobs         : 412\\nGrowing queue + smaller index = indexer is down.",
        "@@ask Repair\tReinstall the indexer service, flush the cache and restart everything?",
        "@@title Repairing the search index",
        "@@step Repairing the indexing services", "@@done 0 Repairing the indexing services",
        "@@ask Reindex\tRebuild the whole index from scratch?\\nOn large catalogs this can take several minutes.",
        "@@step Reindexing the catalog", "@@done 0 Reindexing the catalog",
        "@@step Checking that everything works", "@@done 0 Checking that everything works",
        "@@msg ok OK\tIndexer is running and catalog synchronized.\\nAdd a test record and search for it after ~10 seconds.",
        "@@ask View Report\tDo you want to see the detailed system validation report now?",
        _REPORT,
    ],
    "fail2ban": ["@@preview 🚨 Fail2ban\t=== sshd ===\\nStatus for the jail: sshd\\n|- Currently failed: 2\\n"
                 "`- Currently banned: 1\\n   `- Banned IP list: 203.0.113.7"],
    "ufw": ["@@preview 🧱 UFW\tStatus: active\\n\\nTo                         Action      From\\n"
            "80/tcp                     ALLOW IN    Anywhere\\n8080/tcp                   DENY IN     Anywhere"],
    "staff-firewall": ["@@ask Staff firewall\tBLOCK direct external access to 8080?",
                       "@@msg ok OK\tPort 8080 now allowed only from 127.0.0.1 and the local network."],
    "rotate-db-password": [
        "@@ask Rotate Password\tA new strong password will be generated for the database user,\\nkoha-conf.xml "
        "updated and services restarted.\\n\\nContinue?",
        "@@result password=Xq7demoNewPassw0rd24ch", "@@result file=/root/koha_credentials.txt",
        "@@msg ok OK\tPassword rotated and Koha still responds.\\n\\nNew password: Xq7demoNewPassw0rd24ch"
        "\\n(/root/koha_credentials.txt)"],
    "sizing": [
        "@@choose Sizing\tDetected RAM: 7.7 GB\\nRecommended profile: 2\t2"
        "\t1\t< 4 GB   - 2 Plack, 64MB cache, 512M InnoDB\t2\t4-8 GB   - 3 Plack, 128MB cache, 768M InnoDB"
        "\t3\t8-16 GB  - 4 Plack, 128MB cache, 1G InnoDB\t4\t16 GB+   - 6 Plack, 256MB cache, 2G InnoDB",
        "@@note Applying profile 2...",
        "@@msg ok OK\tProfile 2 applied.\\n\\nPlack: 3 workers\\nMemcached: 128 MB\\nMariaDB InnoDB: 768M"],
    "email": ["@@msg info Email Setup\tE-mail is enabled for the instance (koha-email-enable)."],
    "superlibrarian": [
        "@@input Username\tUsername (login):\t\t", "@@input Card Number\tCard number:\t\t",
        "@@input Password\tPassword (at least 8 characters):\t\tpassword",
        "@@input Confirm Password\tType the password again:\t\tpassword",
        "@@input First name\tFirst name:\tSuper\t", "@@input Surname\tSurname:\tAdmin\t",
        "@@note Hashing the password...",
        "@@msg ok OK\tSuper Librarian created successfully."],
    "interoperability": [
        "@@ask SIP2 & Z39.50\tEnable both and open the firewall ports?",
        "@@msg ok OK\tZ39.50 and SIP2 were enabled successfully!"],
    "clock": ["@@msg ok OK\tTimezone set to: Europe/Lisbon\\nCurrent time: 2026-10-03 17:00"],
    "db-maintenance": [
        "@@ask Deep Maintenance\tThis routine will:\\n\\n• Repair and optimize MariaDB tables\\n\\nContinue?",
        "@@title Deep maintenance",
        "@@step Optimizing the database", "@@done 0 Optimizing the database",
        "@@step Cleaning system logs", "@@done 0 Cleaning system logs",
        "@@step Restarting Koha services", "@@done 0 Restarting Koha services",
        "@@msg ok OK\tMaintenance completed successfully!",
    ],
    "reports-install": [
        "@@preview Preview (dry run)\t● Overdue loans with patron contacts — new\\n● Lost items — update",
        "@@ask Essential reports pack\tNew reports: 1\\nReports to update: 1\\n\\nInstall them now?",
        "@@note Generating the backup...",
        "@@msg ok OK\t✅ Reports installed: 2",
    ],
    "reports-remove": [
        "@@preview Preview (dry run)\t● Overdue loans with patron contacts\\n● Lost items",
        "@@ask Essential reports pack\tRemove the 2 report(s) of the pack?",
        "@@note Generating the backup...",
        "@@msg ok OK\t✅ Reports removed: 2",
    ],
    "cloud-remote": ["@@note Testing the real cloud upload...",
                     "@@msg ok OK\tCloud enabled and tested successfully."],
    "z3950-list": ["@@result row=lx2.loc.gov\t210\tLCDB\tLIBRARY OF CONGRESS"],
    "z3950-server-status": ["@@result daemon=running", "@@result port=2100", "@@result network=off"],
    "z3950-daemon": ["@@msg ok OK\tThis catalogue's Z39.50/SRU server: {0}."],
    "catalog-network": ["@@msg ok OK\tThe koha.nexus network: {0}."],
    "z3950-add": ["@@result added=2", "@@result existing=1", "@@result invalid=0",
                  "@@msg ok OK\tZ39.50/SRU servers added to Koha: 2\\nAlready in Koha: 1\\n\\nThey are in "
                  "Administration > Z39.50/SRU servers, checked for the cataloguing searches."],
    "opac-theme-get": ["@@result amazon=0"],
    "opac-theme-sync": ["@@result amazon=0", "@@result block_OpacUserCSS=no", "@@result block_OpacUserJS=no",
                        "@@result block_IntranetUserCSS=no", "@@result block_IntranetUserJS=no",
                        "@@result own_OpacUserCSS=12", "@@result own_OpacUserJS=0", "@@result own_IntranetUserCSS=3",
                        "@@result own_IntranetUserJS=40", "@@result mainblock=yes", "@@result mainblock_buttons=2"],
    "opac-theme-apply": ["@@note Generating the backup...", "@@note Writing the OPAC preferences...",
                         "@@note Looking for the covers of the newest titles...",
                         "@@result feed=9 of 14 titles with an ISBN have an Amazon cover", "@@result applied=yes",
                         "@@msg ok OK\t✅ The new look is in the OPAC. Reload the catalogue page in the browser to "
                         "see it.\n\nSafety backup: /var/backups/koha_sql/PRE-OPAC-THEME_demo.sql.gz"],
    "opac-theme-remove": ["@@note Generating the backup...",
                          "@@msg ok OK\t✅ The OPAC is back to Koha's own look. The rest of OpacUserCSS and "
                          "OpacUserJS was kept.\n\nSafety backup: /var/backups/koha_sql/PRE-OPAC-THEME_demo.sql.gz"],
    "opac-carousel-refresh": ["@@result feed=9 of 14 titles with an ISBN have an Amazon cover",
                              "@@msg ok OK\tThe New arrivals feed was rebuilt."],    "hub-status": ["@@result staff_url=http://192.0.2.10:8080", "@@result email=on",
                   "@@result admin_email=library@example.org", "@@result sms_driver=", "@@result messaging=no",
                   "@@result smtp=Gmail\tsmtp.gmail.com\t587\tstarttls\tlibrary@example.org\t1",
                   "@@result branch=CPL\tCentral Library", "@@result branch=MPL\tMidway Library",
                   "@@result sip_conf=/etc/koha/sites/library/SIPconfig.xml", "@@result sip=stopped",
                   "@@result z3950=running"],
    "cron-apply": ["@@msg ok OK\tSchedules updated successfully.\nPrevious copy saved at: "
                   "/etc/cron.d/koha_tasks.bak"],
    "sip-apply": ["@@note Restarting Koha's SIP2 server...", "@@result sip=yes",
                  "@@result backup=/etc/koha/sites/library/SIPconfig.xml.kei-demo",
                  "@@msg ok OK\t✅ SIP2 is set up. The self-check machine connects to 192.0.2.10 port 6001 with "
                  "the SIP login.\n\nThe login must also be a Koha patron with the same user name and password."],
    "vpn-status": ["@@result installed=yes", "@@result configured=yes", "@@result running=yes",
                   "@@result supported=yes", "@@result address=10.66.0.1", "@@result port=51820",
                   "@@result endpoint=vpn.example.org", "@@result server_ip=192.0.2.10", "@@result ssh_port=22",
                   "@@result peer=front-desk\t10.66.0.2\t1760000000\t1048576\t5242880",
                   "@@result peer=maria-phone\t10.66.0.3\t0\t0\t0"],
    "vpn-setup": ["@@note Installing WireGuard...", "@@note Starting the VPN...", "@@result running=yes",
                  "@@msg ok OK\t✅ The VPN is on: this server is 10.66.0.1 inside it, UDP port 51820.\n\n"
                  "Add a device for each computer or phone of the staff."],
    "vpn-peer-add": ["@@result address=10.66.0.4",
                     "@@msg ok OK\t✅ Device added with the address 10.66.0.4. Scan its QR code with the "
                     "WireGuard app, or copy its profile to a computer."],
    "vpn-peer-revoke": ["@@msg ok OK\tDevice revoked: it can no longer connect."],
    "vpn-stop": ["@@msg ok OK\tThe VPN is off. The devices and keys are kept: Set up turns it on again."],
    "cloud-provider": ["@@note Registering the connection in rclone...", "@@note Testing the real cloud upload...",
                       "@@msg ok OK\tCloud enabled and tested successfully."],
}


# `--task run ACTION`: the classic routines, their boxes asked by the panel.
_RUN: dict[str, list[str]] = {
    "cloudflare": [
        "@@choose Cloudflare Tunnel Manager\tTunnel Status: ACTIVE\\n\\nWhat do you want to do?\t"
        "\t1\t🆓  Free Address (no domain needed)\t5\t🔁  Restart Tunnel Service",
        "@@note Restarting Cloudflare Tunnel...",
        "@@say ok OK\tService restarted successfully.",
        "@@choose Cloudflare Tunnel Manager\tTunnel Status: ACTIVE\\n\\nWhat do you want to do?\t"
        "\t1\t🆓  Free Address (no domain needed)\t5\t🔁  Restart Tunnel Service"],
    "crons": [
        "@@choose Schedules & Scheduled Tasks\tThe Cron service runs routine maintenance and backup jobs.\t"
        "\t2\t📋 View active tasks and schedules\t4\t📝 Edit schedules manually (Advanced - nano)",
        "@@edit Active Tasks in /etc/cron.d/koha_tasks\t{tmp}/koha_tasks\tChange only the NUMBERS.",
        "@@say ok OK\tSchedules updated successfully."],
    "brazil": [
        "@@check Pimaco label templates\tChoose the templates:\t6180\tPimaco 6180\tON\t6181\tPimaco 6181\tOFF",
        "@@say ok OK\tTemplates installed."],
    "magic-import": [
        "@@file file\tFile Explorer\tPick the file to import:\t{0}\t*",
        "@@step Reading the file", "@@done 0 Reading the file",
        "@@preview Preview (dry run)\t== Summary\\nRows read from tables: 124\\nBooks: 120 record(s), 131 item(s)"
        "\\nPatrons: 0\\nCasing fixed (text typed in capitals): 37\\nAnomalies to check: 2",
        "@@ask 🪄  Magic Import Tool\tCasing fixed: 37  ·  Encoding fixed: 1  ·  Anomalies to check: 2"
        "\\n\\nReady to import:\\n  Records: 120\\n  Items: 131\\n\\nGo on?",
        "@@say ok OK\t120 records imported."],
    "authority-sync": [
        "@@choose Sync & link authorities\tWhich records should be linked to the authorities?\t"
        "\tall\tThe whole catalog\trange\tA range of record numbers (biblionumber)",
        "@@choose Sync & link authorities\tHow should a heading be matched to an authority?\t"
        "\tDefault\tDefault (exact, safe): only when a single authority matches"
        "\tFirstMatch\tFuzzy: when several authorities match, take the first",
        "@@choose Sync & link authorities\tWhat should be done?\t"
        "\tpreview\tSimulation / preview (dry run): nothing is written\tapply\tApply the changes permanently",
        "@@step Simulation (dry run): nothing is written...", "@@done 0 Simulation (dry run): nothing is written...",
        "@@ask Simulation (dry run)\tNothing was written (simulation).\\n\\nLinker: Default\\nRecords checked: 120"
        "\\nRecords that would be updated: 37\\nHeadings that would be linked: 52 (fuzzily: 0)"
        "\\nHeadings without a matching authority: 18\\n\\nApply these changes permanently now?",
        "@@say ok OK\tChanges saved permanently. Records updated: 37. The search index is being rebuilt in the background."],
    "authority-match": [
        "@@step Comparing the names...", "@@done 0 Comparing the names...",
        "@@view Preview (nothing is changed yet)\t== Smart authority matching\nPersonal names checked: 412"
        "\nGroups of variant forms: 2\nVariant forms to merge: 3\n\n1. Keep: Assis, Machado de, 1839-1908"
        "\n   1.00  Machado de Assis (inverted, dates missing)\n   0.93  Assis, M. de (abbreviated, dates missing)"
        "\n\n2. Keep: Sousa, Ana Maria de\n   0.98  Souza, Ana Maria de (sounds alike)",
        "@@choose Group 1 of 2\tThese forms look like the same person (score and why):"
        "\n  1.00  Machado de Assis (inverted, dates missing)\n  0.93  Assis, M. de (abbreviated, dates missing)"
        "\n\nWhich form should stay? The others are merged into it.\t1\t1\tAssis, Machado de, 1839-1908 · suggested"
        "\tskip\tNot the same person: leave this group as it is",
        "@@ask Find duplicate authors\tAuthorities to merge into the form kept: 3\n\nMerge them now?",
        "@@say ok OK\tAuthorities merged: 3"],
    "about": ["@@view About\tkoha.nexus\\n\\nBorn from real-life experience facing technical barriers in collection "
              "management, designed for libraries without budget for expensive commercial systems or dedicated "
              "technical support.\\n\\nSupport this open-source initiative:\\n  * Pix (Brazil)  : 076.650.449.21\\n"
              "  * Bitcoin (BTC) : bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx\\n\\nOfficial Repository:\\n"
              "  https://github.com/PauloFBaldiFH/koha.nexus\\nWebsite:\\n  https://koha.nexus\\n\\n"
              "Created with dedication by Paulo F. Baldi FH."],
    "reboot": ["@@ask Reboot\tReboot the server now?", "@@say info Reboot\tRebooting in 5 seconds..."],
    "languages": [
        "@@choose Koha & Panel Languages\tChoose the language:\tpt-BR\ten\tEnglish\tpt-BR\tPortuguês (Brasil)",
        "@@result panel_lang=en", "@@say ok OK\tLanguage 'en' enabled successfully."],
    "lang-list": ["@@view Installed languages & active one\tKoha languages installed on this server:\n\n"
                  "  en           English                OPAC: enabled    Staff: enabled\n"
                  "  pt-BR        Português (Brasil)     OPAC: ACTIVE     Staff: ACTIVE\n\n"
                  "Active in the OPAC: pt-BR\nActive in the staff interface: pt-BR"],
}
_RUN_DEFAULT = ["@@step Working", "@@done 0 Working", "@@say ok OK\tDone (demo)."]


async def demo_task(out: "TaskOutcome", name: str, args: tuple[str, ...], reporter: "Reporter | None",
                    on_result: Callable[[str, str], None] | None, env: dict[str, str],
                    ask=None) -> "TaskOutcome":
    if name == "run":
        lines = [ln.replace("{tmp}", _demo_tmp()) for ln in _RUN.get(args[0] if args else "", _RUN_DEFAULT)]
        args = ()
    else:
        lines = _SCRIPTS.get(name)
    if lines is None:
        out.feed(f"@@msg error Error\tUnknown panel action: {name}", reporter)
        out.rc = 2
        return out
    pause = 0.0 if name in ("tool-install", "info", "cloud-remotes", "timezones", "credentials") else 0.05 if name == "install" else 0.15
    for line in lines:
        # KEI_TASK_ANSWER=no: the routine stops at its question, as in bash.
        if env.get("KEI_TASK_ANSWER") == "no" and out.asks:
            break
        out.feed(line.replace("{0}", args[0] if args else _HOME), reporter, on_result)
        # Interactive: a "no" or a cancel ends the routine (its usual `|| return 0`).
        from .bridge import _PROMPTS, answer_prompt
        if ask and line.startswith(_PROMPTS):
            if await answer_prompt(out, line, ask) in ("no", "cancel"):
                break
        if pause:
            await asyncio.sleep(pause)
    return out


def _demo_tmp() -> str:
    """A scratch folder for the demo's editable file (the schedules)."""
    import tempfile
    from pathlib import Path
    folder = Path(tempfile.gettempdir()) / "kei-panel-demo"
    folder.mkdir(exist_ok=True)
    tasks = folder / "koha_tasks"
    if not tasks.exists():
        tasks.write_text("PATH=/usr/sbin:/usr/bin:/sbin:/bin\n0 23 * * * root /root/backup_sql.sh\n")
    return str(folder)
