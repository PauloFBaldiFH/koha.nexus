"""Simulated `--task` answers for demo mode and the tests: the same @@
lines the installer prints, fed through the real parser."""

from __future__ import annotations

import asyncio
import json
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

# The enrichment jobs screens (views/enrich.py): one bibliographic job with
# its report, one still being compared, and an authority job (3).
_ENRICH_JOBS = [
    {"id": 6, "created": "2026-10-18 10:05:00", "updated": "2026-10-18 10:05:21", "scope": "query", "state": "ready",
     "total": 1, "done": 1, "release": "", "error": "", "kind": "bib", "mode": "", "origin": "ondemand",
     "query": '{"isbn": "9788535911664", "title": "O evangelho segundo Jesus Cristo"}', "rounds": 1},
    {"id": 5, "created": "2026-10-18 09:58:00", "updated": "2026-10-18 09:58:40", "scope": "101, 117",
     "state": "ready", "total": 2, "done": 2, "release": "", "error": "", "kind": "bib", "mode": "",
     "origin": "ondemand", "query": "", "rounds": 1},
    {"id": 3, "created": "2026-10-17 16:20:00", "updated": "2026-10-17 16:41:02", "scope": "all", "state": "ready",
     "total": 1240, "done": 1240, "release": "nexus-enrich-2026.10", "error": "", "kind": "auth", "mode": "exact"},
    {"id": 2, "created": "2026-10-17 14:02:11", "updated": "2026-10-17 14:05:40", "scope": "500-550",
     "state": "matching", "total": 51, "done": 20, "release": "nexus-enrich-2026.10", "error": "", "kind": "bib",
     "mode": ""},
    {"id": 1, "created": "2026-10-17 09:12:03", "updated": "2026-10-17 09:40:55", "scope": "all", "state": "ready",
     "total": 1240, "done": 1240, "release": "nexus-enrich-2026.10", "error": "", "kind": "bib", "mode": ""},
]
_ENRICH_REPORT = {"job": 1, "scope": "all", "release": "nexus-enrich-2026.10", "records": 1240, "enriched": 412,
                  "unchanged": 301, "review": 37, "no_match": 488, "errors": 2,
                  "records_with": {"M0": 356, "M1": 41, "W": 77, "R": 37}, "pointer_only": 12,
                  "fields_added": 1288, "fields_by_class": {"M0": 1104, "M1": 96, "W": 88},
                  "fields_by_group": {"subjects": 702, "082": 318, "300": 140, "520": 128},
                  "fields_by_source": {"unesp": 540, "ufpr": 401, "unb": 221, "loc": 126}, "koha_batches": 1}
_ENRICH_SHOW = dict(_ENRICH_JOBS[4], dir="/var/lib/koha-nexus-enrich/jobs/1", report=_ENRICH_REPORT,
                    report_html="/var/lib/koha-nexus-enrich/jobs/1/report.html",
                    chunks=[{"job_id": 1, "chunk": 1, "records": 412, "state": "pending"}],
                    changes=[{"biblionumber": 101, "status": "enriched", "title": "Ensaio sobre a cegueira",
                              "m0": 3, "m1": 0, "w": 0, "r": 0, "added": 3},
                             {"biblionumber": 117, "status": "enriched", "title": "Vidas secas",
                              "m0": 0, "m1": 0, "w": 2, "r": 0, "added": 2},
                             {"biblionumber": 230, "status": "review", "title": "Memórias póstumas de Brás Cubas",
                              "m0": 0, "m1": 0, "w": 0, "r": 2, "added": 0}])
_ENRICH_DIFF = ["# job 1, biblionumber 101: enriched", "  LDR    00000nam a2200000 a 4500",
                "  020 __ $a 9788535902778", "  100 1_ $a Saramago, José",
                "  245 10 $a Ensaio sobre a cegueira", "+ 082 04 $8 2\\p $a 869.3",
                "+ 650 _4 $8 1\\p $a Cegueira", "+ 650 _4 $8 1\\p $a Romance português",
                "+ 883 0_ $8 1\\p $a nexus_enrich M0 $c 0.97 $d 20261017 $q unesp $w 33012"]

_AUTH_REPORT = {"kind": "auth", "mode": "exact", "job": 3, "scope": "all", "release": "nexus-enrich-2026.10",
                "records": 1240, "changed": 655, "unchanged": 540, "review": 45, "errors": 0,
                "headings": {"read": 2310, "linked_before": 120, "koha": 806, "new": 512, "review": 61,
                             "no_match": 650, "skipped": 161, "standardized": 388, "fuzzy": 0},
                "new_authorities": 214, "preliminary": 170, "new_by_source": {"bn": 96, "ufpr": 51, "loc": 44,
                                                                              "unesp": 23},
                "koha_batches": 3}
_AUTH_SHOW = dict(_ENRICH_JOBS[2], dir="/var/lib/koha-nexus-enrich/jobs/3", report=_AUTH_REPORT,
                  report_html="/var/lib/koha-nexus-enrich/jobs/3/report.html",
                  changes=[{"biblionumber": 101, "status": "enriched", "title": "Ensaio sobre a cegueira",
                            "m0": 0, "m1": 2, "w": 1, "r": 0, "added": 2},
                           {"biblionumber": 117, "status": "enriched", "title": "Vidas secas",
                            "m0": 1, "m1": 0, "w": 1, "r": 0, "added": 1},
                           {"biblionumber": 230, "status": "review", "title": "Memórias póstumas de Brás Cubas",
                            "m0": 0, "m1": 0, "w": 0, "r": 1, "added": 0}],
                  new_authorities=[{"id": 1, "heading": "Saramago, José, 1922-2010", "source": "bn",
                                    "preliminary": 1, "state": "pending", "authid": None}])
_AUTH_DIFF = ["# job 3, biblionumber 101: enriched", "  LDR    00000nam a2200000 a 4500",
              "- 100 1_ $a Saramago, José", "+ 100 1_ $a Saramago, José, $d 1922-2010 $9 nexus-new:1",
              "  245 10 $a Ensaio sobre a cegueira", "- 650 _4 $a Cegueira", "+ 650 _4 $a Cegueira $9 nexus-new:2"]
# The on-demand screen (views/ondemand.py): job 5 (two records, enriched by
# direct Z39.50 servers) and job 6 (a typed book, two records found).
_OD_ATTEMPTS = [
    {"seq": 1, "round": 1, "wave": 1, "target": "ufpr", "address": "z3950.ufpr.br:210/biblios", "outcome": "found",
     "category": "", "detail": "", "step": "isbn", "hits": 1, "records": 1, "ms": 412},
    {"seq": 1, "round": 1, "wave": 1, "target": "usp", "address": "dedalus.usp.br:9991/usp01", "outcome": "none",
     "category": "", "detail": "", "step": "isbn", "hits": 0, "records": 0, "ms": 690},
    {"seq": 1, "round": 1, "wave": 1, "target": "bne", "address": "catalogo.bne.es:2200/unicorn",
     "outcome": "error", "category": "timeout", "detail": "no answer in 15 s", "step": "isbn", "hits": 0,
     "records": 0, "ms": 15000},
]
_OD_SHOW = dict(_ENRICH_JOBS[1], dir="/var/lib/koha-nexus-enrich/jobs/5",
                report={"job": 5, "scope": "101, 117", "records": 2, "enriched": 2, "unchanged": 0, "review": 0,
                        "no_match": 0, "errors": 0, "records_with": {"M0": 2, "M1": 0, "W": 0, "R": 0},
                        "fields_added": 5, "fields_by_source": {"z3950:ufpr": 3, "z3950:unb": 2}, "koha_batches": 1},
                report_html="/var/lib/koha-nexus-enrich/jobs/5/report.html", chunks=[], attempts=_OD_ATTEMPTS,
                found=[], choices={"101": {"subjects": "z3950:ufpr"}},
                donors={"101": [{"source": "z3950:ufpr", "remote_id": "88213", "cls": "M0", "score": 0.97,
                                 "reasons": []},
                                {"source": "z3950:unb", "remote_id": "5521", "cls": "M0", "score": 0.93,
                                 "reasons": []}],
                        "117": [{"source": "z3950:unb", "remote_id": "7710", "cls": "M0", "score": 0.95,
                                 "reasons": []}]},
                changes=[{"biblionumber": 101, "status": "enriched", "title": "Ensaio sobre a cegueira",
                          "m0": 3, "m1": 0, "w": 0, "r": 0, "added": 3},
                         {"biblionumber": 117, "status": "enriched", "title": "Vidas secas",
                          "m0": 2, "m1": 0, "w": 0, "r": 0, "added": 2}])
_OD_QUERY_SHOW = dict(_ENRICH_JOBS[0], dir="/var/lib/koha-nexus-enrich/jobs/6",
                      report={"job": 6, "scope": "query", "records": 1, "enriched": 0, "no_match": 0},
                      report_html="/var/lib/koha-nexus-enrich/jobs/6/report.html", chunks=[], changes=[],
                      attempts=_OD_ATTEMPTS, donors={}, choices={},
                      found=[{"seq": 1, "query": {"isbn": "9788535911664"}, "found": [
                          {"source": "z3950:ufpr", "remote_id": "90311", "title": "O evangelho segundo Jesus Cristo",
                           "isbn": "9788535911664"},
                          {"source": "z3950:unb", "remote_id": "6620", "title": "O evangelho segundo Jesus Cristo : "
                           "romance", "isbn": "9788535911664", "imported": 1302}]}])
_OD_STATUS = {"job": 5, "state": "matching", "round": 1, "total": 2, "done": 1,
              "record": {"seq": 2, "biblionumber": 117, "title": "Vidas secas"}, "found": 1, "network": [],
              "inflight": 2, "per_hour": 240, "eta_s": 4500, "capped": 14, "cooling": 3,
              "servers": {"ufpr": {"name": "Universidade Federal do Paraná", "country": "BR", "state": "1 record(s)",
                                   "ms": 412, "hits": 1},
                          "usp": {"name": "Universidade de São Paulo (Dedalus)", "country": "BR",
                                  "state": "no record", "ms": 690, "hits": 0},
                          "bne": {"name": "Biblioteca Nacional de España", "country": "ES",
                                  "state": "down: timeout: no answer in 15 s", "ms": 15000, "hits": 0},
                          "unb": {"name": "Universidade de Brasília", "country": "BR", "state": "searching",
                                  "ms": 0, "hits": 0}}}
_Z_HEALTH = [
    {"id": "bne", "key": "catalogo.bne.es:2200/unicorn", "state": "down", "level": 2, "open_until": 0,
     "last_error": "timeout: no answer in 15 s", "last_error_at": 0, "last_ok_at": 0, "latency_ms": 0,
     "ok_7d": 0, "fail_7d": 4},
    {"id": "ufpr", "key": "z3950.ufpr.br:210/biblios", "state": "ok", "level": 0, "open_until": 0,
     "last_error": "", "last_error_at": 0, "last_ok_at": 0, "latency_ms": 410, "ok_7d": 12, "fail_7d": 0},
    {"id": "old", "key": "z3950.old.example:210/db", "state": "down", "level": 0, "open_until": 0,
     "last_error": "dns: name not found", "last_error_at": 0, "last_ok_at": 0, "latency_ms": 0,
     "ok_7d": 0, "fail_7d": 1},
]

# Answers that depend on the first argument (the job): the authority job.
_BY_ARG: dict[tuple[str, str], list[str]] = {
    ("set-koha-extras", "apply"): ["@@result secrets=open",
                                   "@@result safety=/var/backups/koha-nexus/koha-before-files-20261106-101500.tar.gz",
                                   "@@result item=uploads\trestore\t/var/lib/koha/library/uploads",
                                   "@@result item=encryption_key\tapply\t/etc/koha/sites/library/koha-conf.xml"],
    # The home page of the collection (installer: --task tainacan-site).
    ("tainacan-site", "plan"): [
        "@@result plan=apply",
        "@@result page=A new page with the search of the collection and links to the collections and to all the "
        "items.",
        "@@result front=Home page: from the list of blog posts to that page.",
        "@@result facets=Tainacan's faceted search in its collection and items pages (Tainacan, Settings, Theme "
        "default templates).",
        "@@result kept=Not changed: the theme (Twenty Twenty-Five 1.5), the menus, the posts, the pages and the "
        "rest of the settings. Nothing is deleted.",
        "@@result undo=Undo puts the previous home page and settings back.", "@@result rc=0"],
    ("tainacan-site", "status"): ["@@result site=blog", "@@result facets=off", "@@result plugin=active"],
    ("tainacan-site", "apply"): ["@@msg ok OK\tThe home page of the collection is ready at "
                                 "http://192.168.0.20:8090: search, collections and all the items."],
    ("tainacan-site", "undo"): ["@@msg ok OK\tThe previous home page and settings are back."],
    ("tainacan-start", ""): [
        "@@result plan=start",
        "@@result containers=Containers: database exited, WordPress exited.",
        "@@result start=The database and WordPress containers start again with their data as they are; nothing "
        "is restored or deleted.",
        "@@result check=Then the functional check runs again.", "@@result rc=0"],
    ("tainacan-start", "confirm"): ["@@msg ok OK\tTainacan is running again, with its data as it was."],
    # Events in Tainacan (installer: --task tainacan-events, tainacan-restore-notes).
    ("tainacan-events", "plan"): [
        "@@result plan=enable", "@@result em_action=install", "@@result em_origin=ours",
        "@@result em_file=events-manager/events-manager.php",
        "@@result dependency=Events Manager 7.4.13 (downloaded from wordpress.org, checked against the published "
        "checksums)", "@@result nx_action=install",
        "@@result plugin=Nexus Eventos 0.1.1 (production package, each file checked)",
        "@@result data=Tables wp_em_* and wp_nxev_* in the WordPress database: in the Tainacan backups, also with "
        "events off.",
        "@@result undo=Turning events off keeps their data; it never deletes events, bookings or certificates.",
        "@@result rc=0"],
    ("tainacan-events", "enable"): [
        "@@note Downloading Events Manager 7.4.13 from wordpress.org...", "@@note Checking every file...",
        "@@note Installing Nexus Eventos 0.1.1...",
        "@@msg ok OK\tEvents are on: Nexus Eventos 0.1.1 and Events Manager (Plugins, Events)."],
    ("tainacan-events", "disable"): ["@@msg ok OK\tEvents are off. Their data was kept. Events Manager was turned "
                                     "off too."],
    ("tainacan-events", "status"): [
        "@@result events=on", "@@result dependency_origin=ours", "@@result dependency=7.4.13|active",
        "@@result plugin=0.1.1|active", "@@result count_events=3", "@@result count_bookings=12",
        "@@result count_passes=9", "@@result count_attendance=7", "@@result count_certificates=5"],
    ("tainacan-restore-notes", "knx-tainacan-20261105-020000"): [
        "@@result note=Without the recovery phrase, the 9 event pass links already sent stop working (they were "
        "signed with the keys of the backup). Restore with the phrase to keep them, or send the passes again "
        "from Events Manager."],
    ("tainacan-restore-notes", "knx-tainacan-20261104-020000"): [],
    ("enrich-job-show", "5"): ["@@result job=" + json.dumps(_OD_SHOW, ensure_ascii=False)],
    ("enrich-job-show", "6"): ["@@result job=" + json.dumps(_OD_QUERY_SHOW, ensure_ascii=False)],
    ("enrich-job-apply", "5"): ["@@result backup=/var/lib/koha-nexus-enrich/jobs/5/snapshot-apply-2026-10-18.xml",
                                "@@result applied=2", "@@result apply=done",
                                "@@msg ok OK\t✅ Job 5 applied: 2 record(s) enriched."],
    ("enrich-job-show", "3"): ["@@result job=" + json.dumps(_AUTH_SHOW, ensure_ascii=False)],
    ("enrich-job-diff", "3"): ["@@result line=" + line for line in _AUTH_DIFF],
    ("enrich-job-apply", "3"): ["@@result backup=/var/backups/koha_sql/PRE-ENRICH_2026-10-17_17h00.sql.gz",
                                "@@result authorities=214", "@@result applied=655", "@@result apply=done",
                                "@@msg ok OK\t✅ Job 3 applied: 214 new authority record(s), 655 record(s) "
                                "linked and standardised."],
    ("cf-service", "restart"): ["@@note Restarting Cloudflare Tunnel...", "@@msg ok OK\tThe tunnel is running."],
    ("cf-service", "resume"): ["@@note Resuming the tunnel...", "@@msg ok OK\tThe tunnel is running."],
    ("cf-service", "pause"): ["@@note Pausing the tunnel...",
                              "@@msg ok OK\tThe tunnel is paused: the catalog is off the internet until you resume "
                              "it (also after a restart of the server). Its settings are kept."],
    ("cf-run", "staff"): [
        "@@choose Remote staff access\tStaff interface from outside the library: https://biblioteca-admin.koha.nexus"
        "\t\ton\tTurn on or change the password\toff\tTurn off (staff interface only on the local network)",
        "@@msg ok OK\tRemote staff access is off."],
    ("cf-run", "recovery"): ["@@msg ok OK\tRecovery file saved:\n\n  /home/biblioteca/koha-address-biblioteca.key"],
    # The free koha.nexus address of the collection (routines/platforms.py).
    ("tainacan-free", "on"): [
        "@@ask Free address\tThe collection gets the address https://biblioteca-acervo.koha.nexus, in the same "
        "tunnel as the catalog (https://biblioteca.koha.nexus). WordPress's links change to it; the collections, "
        "items and accounts do not change.\n\nContinue?",
        "@@note Adding the collection to the free address...",
        "@@msg ok OK\tYour collection is online:\n\n  https://biblioteca-acervo.koha.nexus"],
    ("tainacan-free", "off"): [
        "@@ask Free address\tThe address https://biblioteca-acervo.koha.nexus is released and Tainacan goes back to "
        "this server on the local network. The catalog keeps its address (https://biblioteca.koha.nexus)."
        "\n\nContinue?",
        "@@note Releasing the address...",
        "@@msg ok OK\tThe free address was released.\n\nTainacan now answers at http://192.168.0.10:8090."],
}

_SCRIPTS: dict[str, list[str]] = {
    "ollama-install": ["@@step Installing Ollama", "@@done 0 Installing Ollama",
                       "@@msg ok OK\tOllama is already installed and running."],
    "tool-install": ["@@result iface=eth0"],
    "info": [
        "@@result real_user=root", "@@result timezone=America/Sao_Paulo", f"@@result real_home={_HOME}", "@@result server_ip=192.0.2.10",
        "@@result dir_sql=/var/backups/koha_sql", "@@result compression=gz", "@@result compression_used=gz",
        "@@result db_name=koha_library",
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
    "backup-marc": [
        "@@note Exporting the MARC21 records...",
        "@@result file={0}/koha_marc_2026-10-03_1200.tar.gz", "@@result size=21M",
        "@@result kept=/var/backups/koha_marc/koha_marc_2026-10-03_1200.tar.gz",
        "@@result contents=biblios_2026-10-03_1200.mrc authorities_2026-10-03_1200.mrc",
        "@@result scp=scp root@192.0.2.10:{0}/koha_marc_2026-10-03_1200.tar.gz Downloads/",
        "@@result user=root", "@@result cloud=no",
    ],
    "marc-info": [
        "@@result dir_marc=/var/backups/koha_marc", "@@result biblios=12840", "@@result authorities=3175",
        "@@result newest=/var/backups/koha_marc/koha_marc_2026-10-26_0300.tar.gz",
        "@@result newest_size=21M", "@@result newest_date=2026-10-26 03:00",
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
        "\t3\t8-16 GB  - 4 Plack, 128MB cache, 1G InnoDB\t4\t16-24 GB - 6 Plack, 256MB cache, 2G InnoDB"
        "\t5\t24-48 GB - 8 Plack, 512MB cache, 4G InnoDB, ES 6G\t6\t48 GB+   - 12 Plack, 1GB cache, 8G InnoDB, ES 8G",
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
    "z3950-list": ["@@result row=https://catalog.koha.nexus\t443\tsru\tRede koha.nexus (Catalogação Compartilhada)"
                   "\tbiblio\t1",
                   "@@result row=utoronto.alma.exlibrisgroup.com\t1921\t01UTON_INST\tUniversity of Toronto\tbiblio\t1",
                   "@@result row=z3950.ufsc.br\t210\tDefault\tUFSC\tbiblio\t0",
                   "@@result row=https://sru.koha.nexus\t443\tsru/toronto\tUniversity of Toronto, Canadá\tbiblio\t0"],
    "z3950-check": ["@@result ticked=1", "@@result unticked=1", "@@result missing=0",
                    "@@msg ok OK\tKoha's cataloguing search: 1 server(s) ticked, 1 unticked."],
    "enrich-jobs": ["@@result jobs=" + json.dumps(_ENRICH_JOBS, ensure_ascii=False),
                    "@@result worker=" + json.dumps({"job": 2, "state": "matching", "total": 51, "done": 20,
                                                      "paused": False, "pause_file": False})],
    "enrich-job-show": ["@@result job=" + json.dumps(_ENRICH_SHOW, ensure_ascii=False).replace('"id": 1,', '"id": {0},')],
    "enrich-job-diff": ["@@result line=" + line for line in _ENRICH_DIFF],
    "enrich-job-add": ["@@result job=3", "@@result records=1240",
                       "@@msg info Enrich bibliographic data\tJob 3: 1240 record(s) are being compared with the "
                       "enrichment database, slowly and in the background.\n\nNothing is written to the "
                       "catalogue until you review the report and choose Apply."],
    "enrich-job-apply": ["@@result backup=/var/backups/koha_sql/PRE-ENRICH_2026-10-17_15h00.sql.gz",
                         "@@result applied=412", "@@result apply=done",
                         "@@msg ok OK\t✅ Job {0} applied: 412 record(s) enriched."],
    "enrich-job-revert": ["@@result reverted=412", "@@result kept=0", "@@result revert=done",
                          "@@msg ok OK\t✅ Job {0} reverted: 412 record(s) have their previous version back."],
    "enrich-auth-add": ["@@result job=4", "@@result records=1240",
                        "@@msg info Enrich & standardize authorities\tJob 4: the headings of 1240 record(s) are "
                        "being compared with your authorities and the enrichment database, and the ones still "
                        "missing are searched on the authority servers, in the background.\n\nNothing is written "
                        "to the catalogue until you review the report and choose Apply."],
    "enrich-job-cancel": [],
    "enrich-od-status": ["@@result status=" + json.dumps(_OD_STATUS, ensure_ascii=False)],
    "enrich-od-add": ["@@result job=7"],
    "enrich-od-more": ["@@result job={0}", "@@result round=2"],
    "enrich-od-donor": ["@@result job={0}", "@@result round=1"],
    "enrich-od-import": ["@@result batch=88", "@@result import=done", "@@result biblionumber=1303",
                         "@@msg ok OK\t✅ Imported as a new record (biblionumber 1303, batch 88).\n\nO evangelho "
                         "segundo Jesus Cristo\n\nIt is indexed automatically in a few minutes. To take it out "
                         "again: Library tools > Undo a MARC import."],
    "z3950-health": ["@@result health=" + json.dumps(_Z_HEALTH, ensure_ascii=False)],
    "z3950-health-reset": ["@@result reset=1"],
    "enrich-pause": [],
    "z3950-server-status": ["@@result daemon=running", "@@result port=2100", "@@result network=off"],
    "z3950-daemon": ["@@msg ok OK\tThis catalogue's Z39.50/SRU server: {0}."],
    "catalog-network": ["@@msg ok OK\tThe koha.nexus network: {0}."],
    "z3950-add": ["@@result added=2", "@@result existing=1", "@@result invalid=0",
                  "@@msg ok OK\tZ39.50/SRU servers added to Koha: 2\\nAlready in Koha: 1\\n\\nThey are in "
                  "Administration > Z39.50/SRU servers, checked for the cataloguing searches."],
    "z3950-sync": ["@@result added=3", "@@result updated=5", "@@result unchecked=1", "@@result invalid=0",
                   "@@msg ok OK\tZ39.50/SRU server settings updated.\\nAdded: 3\\nUpdated: 5\\n\\n"
                   "Old Biblioteca Nacional addresses unticked: 1"],
    "opac-theme-get": ["@@result amazon=0"],
    "opac-theme-sync": ["@@result instance=library", "@@result database=koha_library",
                        "@@result installer_version=demo", "@@result amazon=0", "@@result block_OpacUserCSS=no", "@@result block_OpacUserJS=no",
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
    "docker-plan": ["@@result plan=install",
                    "@@result repository=https://download.docker.com/linux/debian bookworm stable (amd64)",
                    "@@result key=/etc/apt/keyrings/docker.asc (new)",
                    "@@result source=/etc/apt/sources.list.d/docker.list (new)",
                    "@@result packages=docker-ce docker-ce-cli containerd.io docker-buildx-plugin "
                    "docker-compose-plugin",
                    "@@result service=docker started and enabled at boot",
                    "@@result kept=Not changed: /etc/docker/daemon.json, the docker group (nobody is added) and "
                    "Docker's address pools.",
                    "@@result undo=Docker installed here can be removed from the panel while no container, volume "
                    "or network exists.", "@@result rc=0"],
    "docker-install": ["@@note Installing Docker...", "@@msg ok OK\tDocker is installed."],
    "tainacan-plan": ["@@result plan=install", "@@result address=http://192.168.0.10:8090",
                      "@@result web=Apache site on its own port 8090, opened in the firewall; the other sites stay "
                      "as they are.",
                      "@@result images=WordPress 7.1.4 (PHP 8.3), MariaDB 11.8, WP-CLI 2.12 (fixed by digest)",
                      "@@result plugin=Tainacan 1.4.1 (checked against the checksums published by wordpress.org)",
                      "@@result network=Docker network kn-tainacan, isolated from the host, the VPN and the other "
                      "platforms",
                      "@@result data=Docker volumes kn-tainacan-db and kn-tainacan-wp",
                      "@@result kept=Not changed: Koha, its database and its sites, Docker's configuration and "
                      "anything of other programs.", "@@result rc=0"],
    "tainacan-install": ["@@note Downloading the images (this can take a few minutes)...",
                         "@@msg ok OK\tTainacan is installed at http://192.168.0.10:8090. Administrator: knadmin "
                         "(password: Platforms, Tainacan, Administrator)."],
    "tainacan-status": ["@@result status=installed", "@@result url=http://192.168.0.10:8090",
                        "@@result db=running", "@@result wordpress=running", "@@result health=healthy",
                        "@@result collections=3", "@@result items=128", "@@result attachments=117",
                        "@@result attachments_missing=0", "@@result wordpress_version=7.1.4",
                        "@@result tainacan_version=1.4.1", "@@result images_pinned=yes", "@@result audit=ok",
                        "@@result last_backup=knx-tainacan-20261105-020000", "@@result backups=3",
                        "@@result disk_db=84.2MB", "@@result disk_wp=2.1GB", "@@result checked_at=1793872800",
                        "@@result result=ok"],
    "tainacan-logs": ["@@msg ok OK\twordpress-1  | AH00094: Command line: 'apache2 -D FOREGROUND'"],
    "tainacan-backup": ["@@msg ok OK\t/var/backups/koha-nexus/tainacan/knx-tainacan-20261105-143000"],
    "tainacan-backups": ["@@result backup=knx-tainacan-20261105-020000|2026-11-05 02:00:00|manual",
                         "@@result backup=knx-tainacan-20261104-020000|2026-11-04 02:00:00|manual"],
    "tainacan-restore-test": ["@@msg ok OK\tRestore test passed for knx-tainacan-20261105-020000: the isolated copy "
                              "had the same collections, items and attachments, and answered through the API. "
                              "(ok 3 128 117)"],
    "tainacan-restore": ["@@msg ok OK\tRestored knx-tainacan-20261105-020000. The state before is in the safety "
                         "backup knx-tainacan-20261105-143500. (ok 3 128 117)"],
    "tainacan-credentials": ["@@msg ok OK\tTainacan administrator\nAddress: http://192.168.0.10:8090/wp-admin/\n"
                             "User: knadmin\nPassword: demo-password-123"],
    # The common backup engine of the platforms (views/platforms.py, "Platform backups").
    "platform-backup-status": ["@@result key=3F2A9C0E5B7D1A4C8E6F0B2D4A6C8E0F1A3B5C7D",
                               "@@result gpg=yes", "@@result restic=0.16.4",
                               "@@result kit=/var/lib/koha-nexus/backup/recovery-kit.txt",
                               "@@result tainacan.repo=/var/backups/koha-nexus/restic/tainacan",
                               "@@result tainacan.copy=gdrive:koha-nexus", "@@result tainacan.schedule=02:30",
                               "@@result tainacan.keep=7 7 4 6",
                               "@@result tainacan.last=knx-tainacan-20261105-023000|2026-11-05 02:30:00|ref",
                               "@@result tainacan.count=9", "@@result tainacan.incomplete=1",
                               "@@result tainacan.verified=2026-11-01 04:30:12 knx-tainacan-20261002-023000 ok",
                               "@@result tainacan.maintained=2026-11-02 03:30:40 ok"],
    "platform-backup-plan": ["@@result plan=setup", "@@result key=", "@@result package=restic",
                             "@@result phrase=A recovery phrase is shown once: write it down and keep it away from "
                             "this server. Without it, the encrypted configuration of a backup cannot be read."],
    "platform-backup-setup": ["@@note Installing restic...",
                              "@@msg ok OK\tRecovery phrase (write it down now; it is not saved on this server): "
                              "K7QD-M2XP-9WRT-4HNC-V8BZ-3LFA\nEncrypted backups are set up."],
    "platform-backup-repo": ["@@msg ok OK\tFiles of this platform now go to the restic repository "
                             "/var/backups/koha-nexus/restic/tainacan. Save the recovery kit again."],
    "platform-backup-copy": ["@@msg ok OK\tEach new package will also be copied to gdrive:koha-nexus."],
    "platform-backup-kit": ["@@msg ok OK\t/var/lib/koha-nexus/backup/recovery-kit.txt"],
    "tainacan-address": ["@@msg ok OK\tTainacan now answers at {0}."],
    "tainacan-free-status": ["@@result host=", "@@result library=koha", "@@result available=yes",
                             "@@result preview=biblioteca-acervo.koha.nexus"],
    "platform-backup-schedule": ["@@msg ok OK\tDaily backup at 02:30; maintenance on Sundays and a restore test of "
                                 "an older backup on the 1st of each month."],
    "platform-backup-verify": ["@@note Checking the restic repository...", "@@note Restoring in an isolated copy...",
                               "@@msg ok OK\tVerified: the backup knx-tainacan-20261006-023000 was restored in "
                               "isolation and matched its manifest. Restore test passed. (ok 3 128 117)"],
    "platform-backup-incomplete": ["@@result incomplete=knx-tainacan-20261105-143000|db|no"],
    "platform-backup-resume": ["@@note Doing the capture again...",
                               "@@msg ok OK\t/var/backups/koha-nexus/tainacan/knx-tainacan-20261105-143000"],
    "platform-backup-discard": ["@@msg ok OK\tThe incomplete backup knx-tainacan-20261105-143000 was discarded."],
    "tainacan-uninstall": ["@@msg ok OK\tTainacan was uninstalled. Its data was kept: installing it again uses it."],
    "docker-remove": ["@@msg ok OK\tDocker was removed. /var/lib/docker (images) was kept: delete it yourself if "
                      "you do not need it."],
    "vpn-stop": ["@@msg ok OK\tThe VPN is off. The devices and keys are kept: Set up turns it on again."],
    "cloud-provider": ["@@note Registering the connection in rclone...", "@@note Testing the real cloud upload...",
                       "@@msg ok OK\tCloud enabled and tested successfully."],
    # The joint package and the assisted restore (routines/backup_set.py).
    "set-backup": ["@@note Backing up koha...",
                   "@@result platform=koha\tok\t2026-11-06 10:00:02\t2026-11-06 10:00:41\tkoha/koha_library_set_2026-11-06_10h00.sql.gz\tfull",
                   "@@note Backing up tainacan...",
                   "@@result platform=tainacan\tok\t2026-11-06 10:00:41\t2026-11-06 10:01:30\ttainacan/knx-tainacan-20261106-100041/\tfull",
                   "@@result size=212M", "@@result complete=yes", "@@result recoverability=full", "@@result file={0}/knx-set-20261106-100000.tar"],
    "set-inspect": ["@@result kind=koha-nexus-set", "@@result id=4b1f0c9e-2d55-4f0a-9a43-6c1d1f0e9a10",
                    "@@result created=2026-11-06 10:01:31", "@@result host=biblioteca",
                    "@@result panel_version=1.5.176", "@@result complete=yes", "@@result integrity=ok",
                    "@@result platforms=koha tainacan", "@@result recoverability=full", "@@result koha_files=yes",
                    "@@result part=koha\tok\t2026-11-06 10:00:02\t2026-11-06 10:00:41\tgpg\t\tfull",
                    "@@result part=tainacan\tok\t2026-11-06 10:00:41\t2026-11-06 10:01:30\tgpg\t\tfull"],
    "set-unpack": ["@@result stage=/var/backups/koha-nexus/.set-restore.demo",
                   "@@result koha=/var/backups/koha-nexus/.set-restore.demo/koha/koha_library_set_2026-11-06_10h00.sql.gz",
                   "@@result tainacan=/var/backups/koha-nexus/.set-restore.demo/tainacan/knx-tainacan-20261106-100041"],
    "set-cleanup": [],
    # The scheduled joint package (U6).
    "set-schedule-status": ["@@result schedule=01:15", "@@result dest=/root/backups", "@@result keep=7",
                            "@@result copy=gdrive:koha-nexus-sets", "@@result secrets=yes", "@@result cron=yes",
                            "@@result last=2026-11-06 01:16:52|ok|full|ok|", "@@result runs=12"],
    "set-schedule": ["@@msg ok OK\tJoint backup every day at 01:15 in /root/backups, the newest 7 kept."],
    "set-run": ["@@result platform=koha\tok\t2026-11-06 01:15:02\t2026-11-06 01:15:41\tkoha/x.sql.gz\tfull",
                "@@result platform=tainacan\tok\t2026-11-06 01:15:41\t2026-11-06 01:16:30\ttainacan/knx-tainacan-1/\tfull",
                "@@result complete=yes", "@@result recoverability=full", "@@result copy=ok", "@@result removed=1"],
    # Koha's files and secrets after its database: paths and states, never a value.
    "set-koha-extras": ["@@result secrets=open",
                        "@@result item=uploads\trestore\t/var/lib/koha/library/uploads",
                        "@@result item=plugins\trestore\t/var/lib/koha/library/plugins",
                        "@@result item=opac-custom\trestore\t/usr/share/koha/opac/htdocs/images/custom",
                        "@@result item=encryption_key\tapply\t/etc/koha/sites/library/koha-conf.xml",
                        "@@result item=SIPconfig.xml\tbeside\t/etc/koha/sites/library/SIPconfig.xml.from-backup",
                        "@@result item=kei-messaging.conf\tadd\t/etc/koha/sites/library/kei-messaging.conf"],
    # The automatic cloud backup screen (screens/cloud_backup.py).
    "cloud-status": [
        "@@result plan=gdrive\tgdrive\t\t30", "@@result plan=wasabi-weekly\twasabi\tkoha-library\t90",
        "@@result remote=gdrive", "@@result remote2=", "@@result sql_folder=Backup_SQL_Koha",
        "@@result marc_folder=Backup_MARC_Koha", "@@result keep_days=7", "@@result cloud_keep_days=30",
        "@@result bwlimit=", "@@result cloud_marc=yes", "@@result dir_sql=/var/backups/koha_sql",
        "@@result rclone=v1.60.1-DEV", "@@result rclone_backends=46", "@@result rclone_source=debian",
        "@@result history=sql\t2026-10-31 23:00:41 | OK: /var/backups/koha_sql/koha_library_2026-10-31_23h00.sql.gz"
        " (48213412 bytes)",
        "@@result history=sql\t2026-10-31 23:01:30 | Cloud OK: gdrive:Backup_SQL_Koha/"
        " (koha_library_2026-10-31_23h00.sql.gz)",
        "@@result history=sql\t2026-11-01 23:01:12 | WARN: cloud upload failed on gdrive (local copy preserved)",
        "@@result history=sql\t2026-11-02 23:31:20 | Cloud OK: gdrive:Backup_SQL_Koha/"
        " (koha_library_2026-11-02_23h00.sql.gz) [gdrive]",
        "@@result history=sql\t2026-11-01 02:12:40 | Cloud OK: wasabi:koha-library/Backup_SQL_Koha/"
        " (koha_library_2026-10-31_23h00.sql.gz) [wasabi-weekly]",
        "@@result history=marc\t2026-11-01 03:02:10 | Cloud OK: gdrive:Backup_MARC_Koha/"
        " (koha_marc_2026-11-01_0300.tar.gz)",
    ],
    "cloud-list": ["@@result remote=gdrive\tdrive", "@@result remote=wasabi\ts3",
                   "@@result remote=nas\tsftp"],
    "cloud-show": ["@@result opt=provider\tWasabi", "@@result opt=endpoint\ts3.wasabisys.com",
                   "@@result opt=access_key_id\tAKIADEMO", "@@result secret=secret_access_key"],
    "cloud-save": ["@@note Registering the connection in rclone...", "@@result remote=newcloud"],
    "cloud-test": ["@@note Testing the real cloud upload...", "@@result test=ok", "@@result seconds=3",
                   "@@msg ok OK\t✅ The cloud answered: a test file was sent to {0}:Backup_SQL_Koha, read back "
                   "and removed."],
    "cloud-delete": ["@@msg ok OK\tThe connection '{0}' was removed. The files already in the cloud were not "
                     "touched."],
    "cloud-settings": ["@@msg ok OK\tCloud backup settings saved. They apply from the next backup."],
    "cloud-ls": ["@@result entry=D\tBackup_SQL_Koha\t0\t2026-10-01T10:00:00",
                 "@@result entry=D\tBackup_MARC_Koha\t0\t2026-10-01T10:00:00",
                 "@@result entry=D\tDocuments\t0\t2026-09-12T08:00:00",
                 "@@result entry=F\tkoha_library_2026-11-02_23h00.sql.gz\t48322112\t2026-11-02T23:01:20",
                 "@@result entry=F\tkoha_library_2026-11-01_23h00.sql.gz\t48297001\t2026-11-01T23:01:00",
                 "@@result entry=F\tkoha_library_2026-10-31_23h00.sql.gz\t48213412\t2026-10-31T23:01:30"],
    "cloud-about": ["@@result total=16106127360", "@@result used=5153960755", "@@result free=10952166605"],
    "cloud-get": ["@@note Downloading from the cloud...",
                  "@@result file=/home/demo/backups/from_cloud/koha_library_2026-11-02_23h00.sql.gz",
                  "@@result size=47M", "@@msg ok OK\tDownloaded"],
    "cloud-rm": ["@@msg ok OK\tDeleted from the cloud"],
    "cloud-plan-save": ["@@result plan={0}", "@@msg ok OK\tCloud backup {0} saved."],
    "cloud-plan-delete": ["@@msg ok OK\tCloud backup {0} removed. The files already in the cloud were not "
                          "touched."],
    "cloud-send-now": ["@@note Sending to the cloud: {0}...",
                       "@@result line=2026-11-02 14:40:02 | OK: /var/backups/koha_sql/koha_library_2026-11-02_14h40"
                       ".sql.gz (48322112 bytes)",
                       "@@result line=2026-11-02 14:40:31 | Cloud OK: {0}:Backup_SQL_Koha/"
                       " (koha_library_2026-11-02_14h40.sql.gz) [{0}]",
                       "@@msg ok OK\t✅ Backup made and sent to the cloud."],
    # The Cloudflare Tunnel screen (screens/cloudflare.py): a free address.
    "cf-status": [
        "@@result mode=broker", "@@result opac=biblioteca.koha.nexus", "@@result staff=",
        "@@result local_ip=192.168.0.10", "@@result version=2026.9.1", "@@result package=yes", "@@result unit=yes",
        "@@result service=active", "@@result enabled=enabled", "@@result since=Mon 2026-11-02 08:14:03 -03",
        "@@result restarts=0", "@@result staff_host=biblioteca-admin.koha.nexus", "@@result staff_remote=no",
        "@@result listing=yes", "@@result broker=https://broker.koha.nexus",
        "@@result opac_base=http://192.168.0.10", "@@result staff_base=http://192.168.0.10:8080",
        "@@result connections=4", "@@result edge=gru01", "@@result edge=gru02",
        "@@result log=2026-11-02T08:14:03-0300 INF Starting tunnel tunnelID=5f2c…",
        "@@result log=2026-11-02T08:14:04-0300 INF Registered tunnel connection connIndex=0 location=gru01 "
        "protocol=quic",
        "@@result log=2026-11-02T08:14:04-0300 INF Registered tunnel connection connIndex=1 location=gru02 "
        "protocol=quic",
        "@@result log=2026-11-02T08:14:05-0300 INF Registered tunnel connection connIndex=2 location=gru01 "
        "protocol=quic",
        "@@result log=2026-11-02T08:14:05-0300 INF Registered tunnel connection connIndex=3 location=gru02 "
        "protocol=quic"],
    "cf-check": [
        "@@result check=service\tok\t", "@@result check=origin-opac\tok\tHTTP 200",
        "@@result check=dns-opac\tok\tbiblioteca.koha.nexus",
        "@@result check=public-opac\tok\tHTTP 200 · 0.412 s", "@@result check=koha-url\twarn\thttp://192.168.0.10"],
    "cf-urls": ["@@note Setting Koha URL system preferences...",
                "@@msg ok OK\tKoha now uses the tunnel's addresses:\n\n  OPACBaseURL: https://biblioteca.koha.nexus"
                "\n  staffClientBaseURL: http://192.168.0.10:8080"],
    "cf-qr": [*("@@result qr=" + line for line in ['█▀▀▀▀▀█ ▄▀▄ █▀▀▀▀▀█', '█ ███ █ ▀█▀ █ ███ █', '█ ▀▀▀ █ ▄ ▄ █ ▀▀▀ █', '▀▀▀▀▀▀▀ █▄▀ ▀▀▀▀▀▀▀', '▀█▄ ▀▀▀▄▀█▄▀▀▄█▀ ▄▀', '█▀▀▀▀▀█ ▄█▀ ▀▄█▄ █▀', '█ ███ █ ▀▄▄▀█▀ ▀▄▄█', '▀▀▀▀▀▀▀ ▀ ▀▀  ▀ ▀▀']), "@@result png=/home/biblioteca/koha-catalog-qr.png",
              "@@result url=https://biblioteca.koha.nexus"],
    "cf-update": ["@@note Updating cloudflared", "@@result version=2026.10.0",
                  "@@msg ok OK\tcloudflared updated: 2026.9.1 → 2026.10.0"],
    "cf-run": ["@@msg ok OK\tDone."],
    "cloud-rclone-official": ["@@note Downloading the official rclone...", "@@result rclone=v1.71.2",
                              "@@result rclone_backends=72",
                              "@@msg ok OK\tThe official rclone v1.71.2 is installed: every service it "
                              "supports can be chosen now."],
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
        "~@@ask 🪄  Magic Import Tool\tEdit the field mapping before importing?\\n\\nYou can send a field or column to "
        "another MARC field, or leave it out, and see the records change as you go.\\nNo = import as it is.",
        "~@@fieldmap Edit field mapping\t{tmp}/fields.json\t{tmp}/fieldmap.json\t{tmp}/kei",
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


# The cron files of the demo server, for the Schedules center
# (schedules.read_files reads /etc/cron.d on a real one).
_DEMO_KOHA_TASKS = """# ======================================================================
# Koha.Nexus scheduled jobs (Schedules & cron tasks)
# ======================================================================
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# Database backup (compressed SQL) - Daily at 23:00
0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1

# MARC21 records backup - Weekly, Sunday at 03:00
0 3 * * 0 root /bin/bash /root/backup_marc.sh >/dev/null 2>&1

# Cloud backup gdrive: sql+marc - Daily at 23:30
30 23 * * * root /bin/bash /root/cloud_plan.sh gdrive sql+marc >/dev/null 2>&1

# Cloud backup wasabi-weekly: sql - Weekly, Sunday at 02:00
0 2 * * 0 root /bin/bash /root/cloud_plan.sh wasabi-weekly sql >/dev/null 2>&1

# Full search index rebuild - Weekly, Saturday at 02:00
#off# 0 2 * * 6 root /usr/local/bin/koha-kei-reindex library >/dev/null 2>&1

# Clear old sessions and the Zebra queue - Daily at 01:30
30 1 * * * root /usr/sbin/koha-shell library -c "/usr/share/koha/bin/cronjobs/cleanup_database.pl --confirm --sessions --sessdays 2 --zebraqueue 10" >/dev/null 2>&1

# Plack restart (frees memory) - Daily at 05:00
0 5 * * * root /usr/sbin/koha-plack --restart library >/dev/null 2>&1

# System log cleanup (keeps 14 days) - Daily at 00:30
30 0 * * * root /usr/bin/journalctl --vacuum-time=14d >/dev/null 2>&1

# Database table check - Monthly, day 5 at 01:00
0 1 5 * * root /usr/bin/mysqlcheck --check --databases koha_library >/dev/null 2>&1

# Copy of the reports folder (written by hand)
15 6 * * 1-5 root rsync -a /var/lib/koha/library/reports/ /srv/reports/ >/dev/null 2>&1
"""
_DEMO_CRON = {
    "koha_es_watchdog": "# Elasticsearch indexer watchdog (every 5 minutes)\n"
                        "*/5 * * * * root /usr/local/bin/koha-es-watchdog.sh >/dev/null 2>&1\n",
    "koha_sitemap": "SHELL=/bin/bash\n17 3 * * * root /usr/local/bin/config.sh --opac-sitemap >/dev/null 2>&1\n",
    "koha-common": "*/15 * * * * root koha-foreach --chdir --enabled --email "
                   "/usr/share/koha/bin/cronjobs/process_message_queue.pl\n"
                   "0 1 * * * root koha-foreach --chdir --enabled /usr/share/koha/bin/cronjobs/cleanup_database.pl "
                   "--sessions --zebraqueue 10\n",
}
_DEMO_PLATFORM_BACKUPS = (
    "# koha.nexus: backups of the platforms (kei_backup_schedule)\n"
    "30 2 * * * root /usr/local/bin/config.sh --task platform-backup-run tainacan scheduled >/dev/null 2>&1\n"
    "30 3 * * 0 root /usr/local/bin/config.sh --task platform-backup-maintain tainacan >/dev/null 2>&1\n"
    "30 4 1 * * root /usr/local/bin/config.sh --task platform-backup-verify tainacan 30 >/dev/null 2>&1\n")


_DEMO_SETS = (
    "# Managed by Koha.Nexus: the scheduled joint backup (Koha + Tainacan). config.sh writes it again.\n"
    "SHELL=/bin/bash\n"
    "15 1 * * * root /usr/local/bin/config.sh --task set-run scheduled >/dev/null 2>&1\n")


def demo_cron_files(koha: bool, tainacan: bool) -> dict[str, str]:
    """The demo server's cron files, by name (schedules.read_files)."""
    files: dict[str, str] = {}
    if koha:
        files["koha_tasks"] = _DEMO_KOHA_TASKS
        files.update(_DEMO_CRON)
    if tainacan:
        files["koha-nexus-platform-backups"] = _DEMO_PLATFORM_BACKUPS
    if koha and tainacan:
        files["koha-nexus-backup-sets"] = _DEMO_SETS
    return files


def _set_conflicts() -> list[str]:
    """What kei_set_conflicts says, in the panel's language as the installer would."""
    from .i18n import t
    return ["@@result conflict=koha\t" + t(
                "The Koha in use (database ${d}) is replaced; a safety backup is made first.", d="koha_library"),
            "@@result conflict=tainacan\t" + t(
                "The Tainacan in use (${u}) is replaced after a test in an isolated copy; its address and ports "
                "stay those of this server.", u="http://192.0.2.10:8090")]


# The steps after a new installation in the demo: none unless
# KEI_PANEL_DEMO_SETUP=1 (then both platforms have every step to do). Kept
# for the session, as the installer keeps its file.
_DEMO_SETUP: dict[str, dict[str, str]] = {}
_DEMO_ADMINS = {"koha": ["admin", "bibliotecaria"], "tainacan": ["kn_7f3a"]}


def _demo_setup(platform: str) -> dict[str, str] | None:
    import os
    if platform not in _DEMO_SETUP and os.environ.get("KEI_PANEL_DEMO_SETUP") == "1":
        _DEMO_SETUP[platform] = {"admin": "pending", "public": "pending", "backup": "pending"}
    return _DEMO_SETUP.get(platform)


def _admin_lines(name: str, args: tuple[str, ...]) -> list[str] | None:
    """Administrative access and the setup steps (never a password)."""
    from .i18n import t
    platform = args[0] if args else ""
    if platform not in ("koha", "tainacan"):
        return None
    if name == "admin-status":
        state = "ready" if platform == "koha" else "initial"
        return [f"@@result state={state}", "@@result initial=" + ("kn_7f3a" if platform == "tainacan" else "")] \
            + [f"@@result admin={a}" for a in _DEMO_ADMINS[platform]]
    if name == "admin-password":
        user = args[1] if len(args) > 1 else ""
        if platform in _DEMO_SETUP:
            _DEMO_SETUP[platform]["admin"] = "done"
        return ["@@msg ok OK\t" + t("The password of ${u} was changed. The other accounts and the site's keys were "
                                    "not touched.", u=user)]
    if name == "admin-create":
        return ["@@msg ok OK\t" + t("Administrator ${u} created.", u=args[1] if len(args) > 1 else "")]
    steps = _demo_setup(platform)
    if name == "setup-mark":
        if steps is None:
            return []
        if len(args) > 2:
            steps[args[1]] = args[2]
        return []
    if name == "setup-close":
        _DEMO_SETUP.pop(platform, None)
        import os
        os.environ.pop("KEI_PANEL_DEMO_SETUP", None)
        return []
    if steps is None:
        return ["@@result setup=none"]
    return ["@@result setup=open"] + [f"@@result step={k}|{v}|" for k, v in steps.items()] \
        + [f"@@result pending={sum(1 for v in steps.values() if v != 'done')}"]


async def demo_task(out: "TaskOutcome", name: str, args: tuple[str, ...], reporter: "Reporter | None",
                    on_result: Callable[[str, str], None] | None, env: dict[str, str],
                    ask=None) -> "TaskOutcome":
    if name == "dspace-panel":
        import base64
        import os
        command = args[0] if args else "status"
        data = {"status": "installed" if os.environ.get("KEI_PANEL_DEMO_DSPACE") == "1" else "absent",
                "phase": "ready", "url": "http://192.168.1.20:8100"}
        if command == "availability":
            data = {"available": False, "reason": "Demo: no reviewed production image catalog."}
        elif command == "setup-status":
            data = {"setup": "none"}
        elif command == "admin-status":
            data = {"state": "own", "admins": ["admin@example.org"]}
        elif command == "logs":
            data = {"logs": "Demo: no real logs."}
        elif command in ("admin-create", "admin-password"):
            data = {"changed": True}
        out.feed("@@result payload=" + base64.b64encode(json.dumps(data).encode()).decode(), reporter, on_result)
        return out
    if name == "run":
        lines = [ln.replace("{tmp}", _demo_tmp()) for ln in _RUN.get(args[0] if args else "", _RUN_DEFAULT)]
        args = ()
    else:
        lines = _BY_ARG.get((name, args[0] if args else ""), _SCRIPTS.get(name))
        if name in ("admin-status", "admin-password", "admin-create", "setup-status", "setup-mark",
                    "setup-close"):
            lines = _admin_lines(name, args)
        if name == "set-inspect":
            lines = lines + _set_conflicts()
    if lines is None:
        out.feed(f"@@msg error Error\tUnknown panel action: {name}", reporter)
        out.rc = 2
        return out
    pause = 0.0 if name in ("tool-install", "info", "marc-info", "cloud-remotes", "cloud-status", "cloud-list",
                            "cloud-about", "cloud-ls", "timezones", "credentials", "cf-status", "cf-check",
                            "docker-plan", "tainacan-plan", "tainacan-status", "tainacan-backups",
                            "tainacan-restore-notes",
                            "platform-backup-status", "platform-backup-plan", "platform-backup-incomplete",
                            "set-inspect", "set-cleanup", "set-schedule-status", "admin-status", "setup-status", "setup-mark",
                            "setup-close") \
        else 0.05 if name == "install" else 0.15
    if name in ("tainacan-events", "tainacan-site") and args[:1] in (("plan",), ("status",)) \
            or (name == "tainacan-start" and not args):
        pause = 0.0
    for line in lines:
        # "~": an optional step, whose "no" or cancel goes on (the field mapping).
        optional = line.startswith("~")
        line = line.lstrip("~")
        # KEI_TASK_ANSWER=no: the routine stops at its question, as in bash.
        if env.get("KEI_TASK_ANSWER") == "no" and out.asks:
            break
        out.feed(line.replace("{0}", args[0] if args else _HOME), reporter, on_result)
        # Interactive: a "no" or a cancel ends the routine (its usual `|| return 0`).
        from .bridge import _PROMPTS, answer_prompt
        if ask and line.startswith(_PROMPTS):
            if await answer_prompt(out, line, ask) in ("no", "cancel") and not optional:
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
    _demo_fields(folder)
    return str(folder)


def demo_diagnostics() -> "Path":
    """The demo's diagnostics folder (like KEI_DIAG_DIR), with one export."""
    import json
    from pathlib import Path
    base = Path(_demo_tmp()) / "diagnostics"
    out = base / "koha-diagnostics-koha-20261004-0130"
    if not out.exists():
        (out / "logs").mkdir(parents=True)
        from .bridge import _DEMO_STATUS
        (out / "status.json").write_text(json.dumps(_DEMO_STATUS | {"generated_at": 1791077400}))
        (out / "README.txt").write_text("Koha diagnostics for support.\nstatus.json   services, web pages, "
                                        "last backup, disk and memory\n")
        (out / "system.txt").write_text("koha.nexus 1.4.0  |  2026-10-04 01:30:00 -0300\n$ uptime\n"
                                        " 01:30:00 up 3 days,  2:11,  load average: 0.42, 0.40, 0.38\n")
        (out / "services.txt").write_text("$ systemctl status apache2 --no-pager -n 30\n"
                                          "● apache2.service - The Apache HTTP Server\n     Active: active (running)\n")
        (out / "logs" / "apache2_error.log").write_text(
            "[Sat Oct 04 01:10:02.123456 2026] [cgi:error] [pid 812] AH01215: DBI connect failed\n"
            "[Sat Oct 04 01:12:40.000000 2026] [mpm_prefork:notice] [pid 1] resuming normal operations\n")
        (out / "logs" / "koha_library_plack-error.log").write_text("[2026/10/04 01:20:00] [WARN] slow search\n")
    return base


def _demo_fields(folder) -> None:
    """The Magic Import's field mapping in the demo: a fields.json like the
    engine's, and the engine's fieldmap module (from the installer next to
    this panel, when there is one) for the live preview."""
    import json
    import re
    from pathlib import Path
    fields = folder / "fields.json"
    if not fields.exists():
        def rec(n, author, klass, tombo, subject):
            fields = [["001", f"ISIS-{n}"], ["090", "  ", [["a", klass]]], ["245", "10", [["a", f"Livro {n}"]]]]
            if author:
                fields.append(["500", "  ", [["a", author]]])
            fields += [["595", "  ", [["a", tombo], ["b", "LIV"]]], ["690", "  ", [["a", subject]]]]
            return {"leader": "00000nam a22000007a 4500", "fields": fields}
        rows = [("AUSTEN, JANE", "823.91", "Romance inglês"), ("ASSIS, MACHADO DE", "869.3", "Literatura brasileira"),
                ("ALENCAR, JOSE DE", "869.3", "Indianismo"), ("", "028.5", "Literatura infantil"),
                ("Rosa, João Guimarães ", "869.3", "Sertão"), ("LISPECTOR, CLARICE", "869.3", "Ficção"),
                ("Queiroz, Rachel de", "869.3", "Seca"), ("", "981", "HistÃ³ria do Brasil"),
                ("AMADO, JORGE", "869.3", "Bahia"), ("Meireles, Cecília", "869.1", "Poesia")]
        records = [rec(n, a, k, f"T-{41 + n:04d}", sub) for n, (a, k, sub) in enumerate(rows, 1)]
        samples: dict = {}
        for r in records:
            for f in r["fields"]:
                if len(f) == 2:
                    samples.setdefault(f[0], []).append(f[1])
                else:
                    for code, value in f[2]:
                        samples.setdefault(f"{f[0]}${code}", []).append(value)
        targets = [["100$a", "Personal name (author)"], ["245$a", "Title"], ["245$b", "Remainder of title (subtitle)"],
                   ["260$b", "Publisher (260)"], ["264$b", "Publisher (264)"], ["260$c", "Date of publication (260)"],
                   ["264$c", "Date of publication (264)"], ["082$a", "Dewey class (DDC)"], ["650$a", "Topical subject"],
                   ["952$p", "Barcode / accession number of the item"], ["952$y", "Koha item type"]]
        fields.write_text(json.dumps({
            "version": 1, "sample": 10, "targets": [{"to": a, "label": b} for a, b in targets],
            "streams": [{"name": "acervo-isis.iso", "kind": "marc", "format": "ISO2709", "encoding": "UTF-8",
                         "records_total": 11488, "records": records,
                         "fields": [{"from": k, "kind": "marc", "count": len(v), "samples": list(dict.fromkeys(v))[:3], "to": k}
                                    for k, v in sorted(samples.items())]}],
            "columns": [], "tables": [], "mapping": {"version": 1, "mappings": []}}, ensure_ascii=False), encoding="utf-8")
    engine = folder / "kei" / "kei_import"
    installer = Path(__file__).resolve().parents[2] / "installer"
    if not (engine / "tidy.py").exists() and installer.exists():
        text = installer.read_text(encoding="utf-8")
        engine.mkdir(parents=True, exist_ok=True)
        for m in re.finditer(r'cat > "\$d/kei_import/(__init__|marc|rules|tidy|fieldmap)\.py" <<\'KEIPY\'\n(.*?)\nKEIPY\n', text, re.S):
            (engine / f"{m.group(1)}.py").write_text(m.group(2) + "\n", encoding="utf-8")
