"""The Backup center (Paulo, 2026-11-06): one screen in the main menu for
every backup of the server, on four servers (demo mode, simulated
installer answers): no platform, Koha only, Tainacan only, both.

It offers only the installed platforms (Koha first, a choice only when
both are there); the platform groups open it already filtered; each
automatic backup is a row with its own destination, frequency, retention,
what is encrypted and its last run ("No run recorded" without a reliable
record); the cloud connections are shared and need no Koha. Opening it
only reads.
"""

import asyncio

import pytest

from kei_panel import backup_center, cloud, cron, platforms
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv

SERVERS = {"none": ("0", "0"), "koha": ("1", "0"), "tainacan": ("0", "1"), "both": ("1", "1")}
# What the center may call while it is drawn: reads only.
READS = {"platform-backup-status", "info", "cloud-status", "cloud-list"}
KOHA_CARDS = ["backup-download", "backup-manual", "backup-marc", "restore", "backup-cloud", "backup-test"]
TAINACAN_CARDS = ["tainacan-backup", "tainacan-restore-test", "tainacan-restore", "pbackup-schedule",
                  "pbackup-configure", "pbackup-verify", "pbackup-incomplete", "pbackup-kit"]


# ----------------------------------------------------------------------
# The rows, as data
# ----------------------------------------------------------------------
def test_only_the_installed_platforms_are_offered_koha_first():
    assert backup_center.scopes(False, False) == []
    assert backup_center.scopes(True, False) == ["koha"]
    assert backup_center.scopes(False, True) == ["tainacan"]
    assert backup_center.scopes(True, True) == ["koha", "tainacan"]
    assert backup_center.pick_scope("tainacan", ["koha", "tainacan"]) == "tainacan"
    assert backup_center.pick_scope("tainacan", ["koha"]) == "koha"         # asked for, not installed
    assert backup_center.pick_scope("", []) == ""


def _history(*lines):
    return cloud.parse_history([f"sql\t{line}" for line in lines])


def test_each_koha_cloud_backup_has_its_own_destination_retention_and_last_run():
    cron_file = cron.defaults("library")
    cron_file.jobs.append(cron.cloud_job("gdrive", "sql+marc", hour=23, minute=30))
    plans = cloud.parse_plans(["gdrive\tgdrive\t\t30", "weekly\twasabi\tkoha-library\t0"])
    remotes = [cloud.Remote("gdrive", "drive"), cloud.Remote("wasabi", "crypt")]
    history = _history(
        "2026-11-01 23:31:00 | Cloud OK: gdrive:Backup_SQL_Koha/ (a.sql.gz) [gdrive]",
        "2026-11-02 23:31:00 | WARN: cloud upload failed on gdrive [gdrive] (local copy preserved)",
        "2026-11-02 23:32:00 | Cloud cleanup: copies older than 30 days removed from gdrive:Backup_SQL_Koha/",
        "2026-11-03 02:00:00 | Cloud OK: wasabi:koha-library/Backup_SQL_Koha/ (a.sql.gz) [other-plan]")
    backup = {"last_result": "ok", "log_epoch": "1762210800"}
    rows = backup_center.koha_plans(cron_file, {"keep_days": "7", "dir_sql": "/var/backups/koha_sql"}, plans,
                                    remotes, history, backup)
    sql, marc, gdrive, weekly = rows
    assert sql.destination == "This server (/var/backups/koha_sql)" and sql.keep == "7 days on this server"
    assert sql.encrypted == "Not encrypted" and sql.last.endswith("· OK") and sql.state == "ok"
    assert marc.last == "No run recorded" and marc.state == ""
    # Each plan: its own folder and days kept; the cleanup line is not a run.
    assert gdrive.destination == "gdrive:" and gdrive.keep == "30 days in the cloud"
    assert gdrive.last == "2026-11-02 23:31:00 · FAILED" and gdrive.state == "bad"
    assert gdrive.when.startswith("Daily at 23:30")
    # The other plan's line ([other-plan]) is not this plan's run, even on the same connection.
    assert weekly.destination == "wasabi:koha-library/" and weekly.keep == "Everything kept"
    assert weekly.last == "No run recorded" and weekly.when == "Not scheduled"
    # Only a connection that encrypts (rclone crypt) says so; never "encrypted" for a plain one.
    assert weekly.encrypted == "Encrypted by the connection (rclone crypt)"
    assert gdrive.encrypted == "Not encrypted"


def test_an_old_log_line_without_an_id_counts_for_the_plan_of_that_connection():
    plan = cloud.parse_plans(["gdrive\tgdrive\t\t0"])[0]
    old = _history("2026-10-30 23:01:00 | Cloud OK: gdrive:Backup_SQL_Koha/ (a.sql.gz)",
                   "2026-10-31 23:01:00 | WARN: cloud upload failed on gdrive (local copy preserved)")
    assert backup_center.plan_last_run(plan, old).when == "2026-10-31 23:01:00"
    assert backup_center.plan_last_run(plan, _history("2026-10-30 | Cloud OK: nas:x/ (a)")) is None


def test_no_nightly_record_says_so_instead_of_inventing_a_run():
    rows = backup_center.koha_plans(None, {}, [], [], [], {})
    assert [r.last for r in rows] == ["No run recorded", "No run recorded"]
    assert rows[0].when == "Not scheduled"


def test_the_tainacan_row_says_part_by_part_what_is_encrypted():
    known = platforms.BackupState(known=True, key="3F2A", repo="/var/backups/koha-nexus/restic/tainacan",
                                  copy="gdrive:koha-nexus", schedule="02:30",
                                  last="knx-tainacan-20261105-023000|2026-11-05 02:30:00|ref")
    row, = backup_center.tainacan_plans(known, "7 7 4 6", [cloud.Remote("gdrive", "drive")])
    assert row.destination == ("This server + restic repository /var/backups/koha-nexus/restic/tainacan"
                               " + copy to gdrive:koha-nexus")
    assert row.when == "Daily at 02:30"
    assert row.keep == "last 7, 7 daily, 4 weekly, 6 monthly"
    assert row.encrypted == ("configuration encrypted with this server's key; files encrypted in the restic "
                             "repository; database not encrypted")
    assert row.last == "2026-11-05 02:30:00 · OK"
    plain = platforms.BackupState(known=True)
    row, = backup_center.tainacan_plans(plain, "", [])
    assert row.when == "Not scheduled" and row.last == "No run recorded"
    assert row.encrypted == ("configuration not encrypted (readable by root only); files not encrypted; "
                             "database not encrypted")
    # A copy through an rclone crypt connection is said as such, only for the copy.
    crypt = platforms.BackupState(known=True, copy="vault:tainacan")
    row, = backup_center.tainacan_plans(crypt, "", [cloud.Remote("vault", "crypt")])
    assert row.encrypted.endswith("the cloud copy is encrypted by the connection (rclone crypt)")
    assert backup_center.tainacan_plans(platforms.BackupState(), "", []) == []     # not read: no row


# ----------------------------------------------------------------------
# The screen, on four servers
# ----------------------------------------------------------------------
@pytest.fixture
def server(monkeypatch, request):
    koha, tainacan = SERVERS[request.param]
    monkeypatch.setenv("KEI_PANEL_DEMO_KOHA", koha)
    monkeypatch.setenv("KEI_PANEL_DEMO_TAINACAN", tainacan)
    return request.param


def make_app(ran):
    app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
    real_task = app.bridge.task

    async def task(name, *args, **kwargs):
        ran.append((name, args))
        return await real_task(name, *args, **kwargs)
    app.bridge.task = task
    return app


def current_view(app):
    from textual.widgets import ContentSwitcher
    switcher = app.screen.query_one("#views", ContentSwitcher)
    return switcher.query_one(f"#{switcher.current}")


def shown_cards(view) -> list[str]:
    from kei_panel.widgets.cards import ActionCard
    return [c.entry.action for c in view.query(ActionCard) if c.display]


async def until(pilot, ready, seconds=10.0):
    waited = 0.0
    while not ready() and waited < seconds:
        await pilot.pause(0.25)
        waited += 0.25
    return ready()


def loaded(app):
    view = current_view(app)
    return lambda: bool(view.query("#platform-loader")) and not view.query_one("#platform-loader").display


def state(view):
    rows = [[r.name, r.destination, r.when, r.keep, r.encrypted, r.last] for r in view.plans]
    # Each row is drawn as its own block, with every field.
    blocks = [str(w.render()) for w in view.query("#bk-plans Static")]
    assert all(r[0] in b and r[1] in b and r[5] in b for r, b in zip(rows, blocks))
    buttons = [s for s in backup_center.SCOPES if view.query_one(f"#scope-{s}").display]
    return {"scope": view.scope, "buttons": buttons if view.query_one("#bk-scopes").display else [],
            "none": bool(view.query_one("#bk-none").display), "koha": bool(view.query_one("#bk-koha").display),
            "tainacan": bool(view.query_one("#bk-tainacan").display), "cards": shown_cards(view), "rows": rows}


@pytest.mark.parametrize("server", list(SERVERS), indirect=True)
def test_the_center_follows_what_is_installed_and_only_reads(server):
    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            await pilot.press("b")
            await pilot.pause(0.3)
            await until(pilot, loaded(app))
            return current_view(app).id, state(current_view(app)), ran

    vid, st, ran = asyncio.run(main())
    assert vid == "view-backups"
    koha, tainacan = server in ("koha", "both"), server in ("tainacan", "both")
    assert st["none"] is (not koha and not tainacan)
    assert st["buttons"] == (["koha", "tainacan"] if koha and tainacan else [])
    if koha:            # Koha first
        assert st["scope"] == "koha" and st["koha"] and not st["tainacan"]
        assert st["cards"] == KOHA_CARDS + ["cloud-connections"]
        names = [r[0] for r in st["rows"]]
        assert names[:2] == ["Database backup (SQL)", "MARC21 package"]
        assert names[2:] == ["Cloud backup gdrive (SQL + MARC21)", "Cloud backup wasabi-weekly (SQL)"]
    elif tainacan:
        assert st["scope"] == "tainacan" and st["tainacan"] and not st["koha"]
        assert st["cards"] == TAINACAN_CARDS + ["cloud-connections"]
        assert [r[0] for r in st["rows"]] == ["Tainacan backup"]
    else:
        assert st["scope"] == "" and st["cards"] == ["cloud-connections"] and st["rows"] == []
    assert {name for name, _a in ran} <= READS
    # The engine's state is read only where Tainacan is (the dashboard reads it too).
    assert ("platform-backup-status" in {n for n, _a in ran}) is tainacan


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_platform_groups_open_the_center_already_filtered(server):
    from kei_panel.widgets.cards import ActionCard

    async def open_from(app, pilot, key, scope):
        await pilot.press(key)
        await pilot.pause(2.0)
        home = current_view(app)
        next(c for c in home.query(ActionCard) if c.entry.action == "backups" and c.entry.scope == scope) \
            .action_choose()
        await pilot.pause(0.3)
        await until(pilot, loaded(app))
        return state(current_view(app))

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            from_tainacan = await open_from(app, pilot, "g", "tainacan")
            from_koha = await open_from(app, pilot, "k", "koha")
            await pilot.click("#scope-tainacan")          # the choice on the center itself
            await pilot.pause(0.3)
            await until(pilot, loaded(app))
            chosen = state(current_view(app))
            return from_tainacan, from_koha, chosen

    from_tainacan, from_koha, chosen = asyncio.run(main())
    assert from_tainacan["scope"] == "tainacan" and from_tainacan["buttons"] == ["koha", "tainacan"]
    assert from_tainacan["cards"] == TAINACAN_CARDS + ["cloud-connections"]
    assert from_koha["scope"] == "koha" and from_koha["cards"] == KOHA_CARDS + ["cloud-connections"]
    assert chosen["scope"] == "tainacan" and chosen["rows"][0][0] == "Tainacan backup"


@pytest.mark.parametrize("server", ["tainacan"], indirect=True)
def test_cloud_connections_work_without_koha_and_keep_the_one_tainacan_uses(server):
    from textual.widgets import DataTable, TabbedContent

    from kei_panel.screens.cloud_backup import CloudBackupScreen

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.run_native("cloud-connections")
            await until(pilot, lambda: isinstance(app.screen, CloudBackupScreen))
            screen = app.screen
            await until(pilot, lambda: screen.remotes != [])
            await pilot.pause(0.3)
            tabs = screen.query_one("#cb-tabs", TabbedContent)
            hidden = [p for p in ("cb-tab-conn", "cb-tab-plan", "cb-tab-files", "cb-tab-hist")
                      if not tabs.get_tab(p).display]
            table = screen.query_one("#cb-remotes", DataTable)
            uses = {str(table.get_row_at(i)[1]): str(table.get_row_at(i)[3]) for i in range(table.row_count)}
            return hidden, bool(screen.query_one("#cb-use").display), uses, ran

    hidden, use_button, uses, ran = asyncio.run(main())
    # Only the connections: no Koha cloud backup can be made from here.
    assert hidden == ["cb-tab-plan", "cb-tab-files", "cb-tab-hist"] and not use_button
    assert "Tainacan copy" in uses["gdrive"]
    assert not {n for n, _a in ran} & {"cloud-remote", "cloud-plan-save", "cloud-token", "cloud-authorize"}
