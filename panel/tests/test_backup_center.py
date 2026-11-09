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
READS = {"platform-backup-status", "info", "cloud-status", "cloud-list", "set-schedule-status"}
KOHA_CARDS = ["backup-download", "backup-manual", "backup-marc", "restore", "backup-cloud", "backup-test"]
SHARED = ["restore-assisted", "cloud-connections"]
TAINACAN_CARDS = ["tainacan-backup", "tainacan-restore-test", "tainacan-restore", "pbackup-schedule",
                  "pbackup-configure", "pbackup-verify", "pbackup-incomplete", "pbackup-kit"]


# ----------------------------------------------------------------------
# The rows, as data
# ----------------------------------------------------------------------
def test_only_the_installed_platforms_are_offered_koha_first():
    assert backup_center.scopes(False, False) == []
    assert backup_center.scopes(True, False) == ["koha"]
    assert backup_center.scopes(False, True) == ["tainacan"]
    assert backup_center.scopes(True, True) == ["koha", "tainacan", "both"]     # the set only with both
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


ERRORS: list = []


def _traced(fn):
    # A routine runs in a worker that swallows its errors (exit_on_error=False):
    # keep them, so a test that waits for a screen can say why it never came.
    async def run(app):
        try:
            return await fn(app)
        except Exception:
            import traceback
            ERRORS.append(traceback.format_exc())
            raise
    run.traced = True
    return run


def make_app(ran):
    from kei_panel import routines
    for name, fn in list(routines.ROUTINES.items()):
        if not getattr(fn, "traced", False):
            routines.ROUTINES[name] = _traced(fn)
    ERRORS.clear()
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


async def until(pilot, ready, seconds=30.0):
    # A loaded CI runner can take several seconds to push a screen: wait
    # long enough, and say what never came instead of failing later on the
    # wrong screen.
    waited = 0.0
    while not ready() and waited < seconds:
        await pilot.pause(0.25)
        waited += 0.25
    if not ready():
        raise AssertionError(f"still on {type(pilot.app.screen).__name__} after {seconds:.0f} s; "
                             f"routine errors: {' | '.join(ERRORS) or 'none'}")
    return True


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
    assert st["buttons"] == (["koha", "tainacan", "both"] if koha and tainacan else [])
    if koha:            # Koha first
        assert st["scope"] == "koha" and st["koha"] and not st["tainacan"]
        assert st["cards"] == KOHA_CARDS + SHARED
        names = [r[0] for r in st["rows"]]
        assert names[:2] == ["Database backup (SQL)", "MARC21 package"]
        assert names[2:] == ["Cloud backup gdrive (SQL + MARC21)", "Cloud backup wasabi-weekly (SQL)"]
    elif tainacan:
        assert st["scope"] == "tainacan" and st["tainacan"] and not st["koha"]
        assert st["cards"] == TAINACAN_CARDS + SHARED
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
    assert from_tainacan["scope"] == "tainacan" and from_tainacan["buttons"] == ["koha", "tainacan", "both"]
    assert from_tainacan["cards"] == TAINACAN_CARDS + SHARED
    assert from_koha["scope"] == "koha" and from_koha["cards"] == KOHA_CARDS + SHARED
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


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_koha_and_tainacan_as_a_set_offer_the_joint_backup_and_both_plans(server):
    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            app.screen.action_show("backups", scope="both")
            await pilot.pause(0.3)
            await until(pilot, loaded(app))
            view = current_view(app)
            return state(view), bool(view.query_one("#bk-both").display), ran

    st, note, ran = asyncio.run(main())
    assert st["scope"] == "both" and note and not st["koha"] and not st["tainacan"]
    # The platform cards stay in each platform's view; the set has its own.
    assert st["cards"] == ["set-backup", "set-schedule", "restore-assisted", "cloud-connections"]
    assert [r[0] for r in st["rows"]] == ["Database backup (SQL)", "MARC21 package",
                                          "Cloud backup gdrive (SQL + MARC21)", "Cloud backup wasabi-weekly (SQL)",
                                          "Tainacan backup", "Joint backup (Koha + Tainacan)"]
    joint = st["rows"][-1]
    assert joint[1] == "This server (/root/backups) + copy to gdrive:koha-nexus-sets"
    assert joint[2] == "Daily at 01:15" and joint[3] == "the newest 7 sets" and joint[5] == "2026-11-06 01:16 · OK"
    assert "the cloud copy is the whole set encrypted with the backup key" in joint[4]
    assert {name for name, _a in ran} <= READS


# ----------------------------------------------------------------------
# The joint backup and the assisted restore (routines/backup_set.py)
# ----------------------------------------------------------------------
def _outcome(lines):
    from kei_panel.bridge import TaskOutcome
    out = TaskOutcome()
    for line in lines:
        out.feed(line)
    return out


def test_the_inspection_is_read_as_data():
    from kei_panel.routines import backup_set
    out = _outcome(["@@result kind=koha-nexus-set", "@@result created=2026-11-06 10:01:31", "@@result host=bib",
                    "@@result complete=no", "@@result integrity=ok", "@@result platforms=koha",
                    "@@result recoverability=partial", "@@result koha_files=yes",
                    "@@result part=koha\tok\t10:00\t10:01\tgpg\t\tfull",
                    "@@result part=tainacan\tfailed\t10:01\t10:02\t\tThe Tainacan database is not running.",
                    "@@result conflict=koha\tKoha is not installed here: install it first, then restore."])
    info = backup_set.parse_inspect(out)
    assert info.kind == "koha-nexus-set" and not info.complete and info.platforms == ["koha"]
    assert [(p.id, p.ok, p.recov) for p in info.parts] == [("koha", True, "full"), ("tainacan", False, "")]
    assert info.recoverability == "partial" and info.koha_files
    text = backup_set.summary(info)
    assert "Made on: bib" in text and "Incomplete set" in text and "not at the same instant" in text
    assert "its secrets (encryption key, SIP2 and panel logins) encrypted with the backup key" in text
    # Never "complete" when a part is missing or has no secrets; the outside dependencies are said.
    assert "NOT recoverable in full" in text and "koha-common" in text and "Cloudflare" in text
    # A Koha part without its secrets says what that means.
    data_only = backup_set.Part("koha", True, secrets="none", recov="data-only")
    assert "WITHOUT its secrets" in backup_set.secrets_text(data_only)
    assert "Tainacan: not in the set (The Tainacan database is not running.)" in text
    assert "Koha is not installed here" in text


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_joint_backup_asks_the_folder_says_it_is_not_simultaneous_and_reports_each_platform(server, tmp_path):
    from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen
    from kei_panel.screens.files import PathPickerScreen

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.run_native("set-backup")
            await until(pilot, lambda: isinstance(app.screen, PathPickerScreen))
            app.screen.dismiss(tmp_path)
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            question = app.screen._question
            await pilot.click("#yes")
            await until(pilot, lambda: isinstance(app.screen, MessageScreen), 15)
            return question, app.screen._body, ran

    question, body, ran = asyncio.run(main())
    assert "not taken at the same instant" in question
    assert "Joint backup done" in body and "Koha: 2026-11-06 10:00:02" in body and "Tainacan: 2026-11-06" in body
    assert ("set-backup", (str(tmp_path),)) in ran


@pytest.mark.parametrize("server", ["both"], indirect=True)
@pytest.mark.parametrize("kind,choice,restored", [
    ("koha-nexus-set", "tainacan", "tainacan"),
    ("koha-nexus-set", "both", "koha tainacan"),
    ("koha-sql", None, "koha"),
    ("unsafe", None, ""),
])
def test_the_assisted_restore_recognises_the_backup_and_uses_the_existing_restores(
        server, monkeypatch, kind, choice, restored):
    from kei_panel.routines import backup, platforms as tn
    from kei_panel.screens.dialogs import ChoiceScreen, MessageScreen
    from kei_panel.screens.files import PathPickerScreen

    calls: list = []

    async def koha_restore(app, file=None):
        calls.append(("koha", file))

    async def tainacan_restore(app, name=None):
        calls.append(("tainacan", name))
    monkeypatch.setattr(backup, "restore", koha_restore)
    monkeypatch.setattr(tn, "tainacan_restore", tainacan_restore)

    async def main():
        ran: list = []
        app = make_app(ran)
        real = app.bridge.task

        async def task(name, *args, **kwargs):
            out = await real(name, *args, **kwargs)
            if name == "set-inspect" and kind != "koha-nexus-set":
                out.results.clear(); out.lists.clear()
                out.feed(f"@@result kind={kind}")
                if kind == "unsafe":
                    out.feed("@@result why=entry ../../etc/cron.d/x")
            return out
        app.bridge.task = task
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.run_native("restore-assisted")
            await until(pilot, lambda: isinstance(app.screen, ChoiceScreen))
            app.screen.dismiss("file")
            await until(pilot, lambda: isinstance(app.screen, PathPickerScreen))
            app.screen.dismiss("/root/backups/knx-set-20261106-100000.tar")
            shown = ""
            if choice:
                await until(pilot, lambda: isinstance(app.screen, ChoiceScreen) and "Made on" in app.screen._prompt)
                shown = app.screen._prompt
                app.screen.dismiss(choice)
            elif kind == "unsafe":
                await until(pilot, lambda: isinstance(app.screen, MessageScreen))
                shown = app.screen._body
            if restored:
                await until(pilot, lambda: len(calls) == len(restored.split()))
            if kind == "koha-nexus-set":
                await until(pilot, lambda: any(n == "set-cleanup" for n, _a in ran))
            return shown, [n for n, _a in ran]

    shown, names = asyncio.run(main())
    assert " ".join(c[0] for c in calls) == restored
    if kind == "koha-nexus-set":
        assert "Made on: biblioteca" in shown and "not at the same instant" in shown
        assert "The Tainacan in use" in shown
        assert names.count("set-unpack") == 1 and names.count("set-cleanup") == 1
        assert all(c[1].startswith("/var/backups/koha-nexus/.set-restore.demo/") for c in calls)
    else:
        assert "set-unpack" not in names
    if kind == "koha-sql":
        assert calls == [("koha", "/root/backups/knx-set-20261106-100000.tar")]
    if kind == "unsafe":
        assert "refused before anything was extracted" in shown and "../../etc/cron.d/x" in shown


# ----------------------------------------------------------------------
# Koha's secrets (document V): asked before, never in clear, recovered with a plan
# ----------------------------------------------------------------------
@pytest.mark.parametrize("server", ["both"], indirect=True)
@pytest.mark.parametrize("answer", ["data", "key", None])
def test_without_a_backup_key_the_person_chooses_before_the_joint_backup(server, tmp_path, monkeypatch, answer):
    from kei_panel.routines import platforms as tn
    from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen
    from kei_panel.screens.files import PathPickerScreen

    keys = {"key": ""}
    setups: list = []

    async def state(app):
        return platforms.BackupState(known=True, key=keys["key"])

    async def setup(app):
        setups.append(1)
        keys["key"] = "3F2A"
    monkeypatch.setattr(tn, "backup_state", state)
    monkeypatch.setattr(tn, "backup_setup", setup)

    async def main():
        ran: list = []
        app = make_app(ran)
        real = app.bridge.task

        async def task(name, *args, **kwargs):
            out = await real(name, *args, **kwargs)
            if name == "set-backup" and "no-secrets" in args:     # what the installer says for data only
                out.results["recoverability"] = "partial"
                out.lists["platform"][0] = out.lists["platform"][0].replace("\tfull", "\tdata-only")
            return out
        app.bridge.task = task
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.run_native("set-backup")
            await until(pilot, lambda: isinstance(app.screen, PathPickerScreen))
            app.screen.dismiss(tmp_path)
            await until(pilot, lambda: isinstance(app.screen, ChoiceScreen))
            prompt = app.screen._prompt
            app.screen.dismiss(answer)
            body = ""
            if answer:
                await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
                await pilot.click("#yes")
                await until(pilot, lambda: isinstance(app.screen, MessageScreen), 15)
                body = app.screen._body
            await pilot.pause(0.3)
            return prompt, body, [(n, a) for n, a in ran if n == "set-backup"]

    prompt, body, ran = asyncio.run(main())
    assert "never go in clear" in prompt and "two-factor" in prompt and "not complete" in prompt
    if answer is None:
        assert ran == [] and setups == []
    elif answer == "data":
        assert ran == [("set-backup", (str(tmp_path), "", "no-secrets"))]
        assert "data only for the platform marked" in body and "data without its secrets" in body
        assert "NOT recoverable in full" in body and "Joint backup done." not in body
    else:
        assert setups == [1] and ran == [("set-backup", (str(tmp_path),))]
        assert "✅ Joint backup done." in body and "Recoverable in full" in body


@pytest.mark.parametrize("server", ["both"], indirect=True)
@pytest.mark.parametrize("confirm", [True, False])
def test_koha_secrets_come_back_with_a_plan_after_its_database_and_no_value_is_shown(server, monkeypatch, confirm):
    from kei_panel.routines import backup, platforms as tn
    from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
    from kei_panel.screens.files import PathPickerScreen

    async def koha_restore(app, file=None):
        return True

    async def tainacan_restore(app, name=None):
        return None
    monkeypatch.setattr(backup, "restore", koha_restore)
    monkeypatch.setattr(tn, "tainacan_restore", tainacan_restore)
    envs: list = []

    async def main():
        ran: list = []
        app = make_app(ran)
        real = app.bridge.task

        async def task(name, *args, **kwargs):
            if name == "set-koha-extras":
                envs.append((args, kwargs.get("env")))
            return await real(name, *args, **kwargs)
        app.bridge.task = task
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.run_native("restore-assisted")
            await until(pilot, lambda: isinstance(app.screen, ChoiceScreen))
            app.screen.dismiss("file")
            await until(pilot, lambda: isinstance(app.screen, PathPickerScreen))
            app.screen.dismiss("/root/backups/knx-set-20261106-100000.tar")
            await until(pilot, lambda: isinstance(app.screen, ChoiceScreen) and "Made on" in app.screen._prompt)
            app.screen.dismiss("koha")
            await until(pilot, lambda: isinstance(app.screen, InputScreen))
            app.screen.dismiss("RECO-VERY-PHRA-SE01")
            # Wait until on_mount has focused "#no": dismissing before that
            # removes the buttons under on_mount (NoMatches on CI 42411175197).
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen)
                        and app.screen.is_mounted and app.focused is not None
                        and app.focused.id == "no")
            plan = app.screen._question
            # The plan is long: on a small CI runner the buttons can lie below
            # the fold, where a click lands on nothing. The answer is what matters.
            app.screen.dismiss(bool(confirm))
            done = ""
            if confirm:
                await until(pilot, lambda: isinstance(app.screen, MessageScreen), 15)
                done = app.screen._body
                app.screen.dismiss(None)
            await pilot.pause(0.5)
            return plan, done, [n for n, _a in ran]

    plan, done, names = asyncio.run(main())
    assert "the rest of koha-conf.xml (database password, paths, Zebra, memcached) stays as it is" in plan
    assert "SIPconfig.xml: this server keeps its own" in plan and "SIPconfig.xml.from-backup" in plan
    assert "kei-messaging.conf: added (this server has none)" in plan
    assert "uploads: back to /var/lib/koha/library/uploads" in plan
    # The phrase only in the environment, never on the command line.
    assert all("RECO-VERY-PHRA-SE01" not in " ".join(a) for a, _e in envs)
    assert all(e == {"KEI_BACKUP_PHRASE": "RECO-VERY-PHRA-SE01"} for _a, e in envs)
    actions = [a[0] for a, _e in envs]
    if confirm:
        assert actions == ["plan", "apply"] and envs[1][0][2] == "confirm"
        assert "koha-before-files-20261106-101500.tar.gz" in done
    else:
        assert actions == ["plan"]
    assert names.count("set-cleanup") == 1


def test_the_joint_backup_row_says_data_only_and_no_record():
    row, = backup_center.set_plans({"schedule": "", "secrets": "no"})
    assert row.when == "Not scheduled" and row.last == "No run recorded" and row.state == ""
    assert row.encrypted.startswith("Koha without its secrets (data only, chosen by you)")
    assert backup_center.set_plans({}) == []


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_scheduling_the_joint_backup_asks_everything_then_writes_one_schedule(server, tmp_path):
    from kei_panel.screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen
    from kei_panel.screens.files import PathPickerScreen

    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.run_native("set-schedule")
            await until(pilot, lambda: isinstance(app.screen, ChoiceScreen))
            current = app.screen._prompt
            app.screen.dismiss("change")
            await until(pilot, lambda: isinstance(app.screen, PathPickerScreen))
            app.screen.dismiss(tmp_path)
            answers = ["02:40", "5", "gdrive:sets"]
            asked = []
            for value in answers:
                await until(pilot, lambda: isinstance(app.screen, InputScreen) and app.screen._prompt not in asked)
                asked.append(app.screen._prompt)
                app.screen.dismiss(value)
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            question = app.screen._question
            await pilot.click("#yes")
            await pilot.pause(1.0)
            return current, question, [(n, a) for n, a in ran if n == "set-schedule"]

    current, question, ran = asyncio.run(main())
    assert "every day at 01:15 in /root/backups" in current
    assert "never two at the same time" in question and "Cloud copy: gdrive:sets" in question
    assert ran == [("set-schedule", ("time=02:40", f"dest={tmp_path}", "keep=5", "copy=gdrive:sets", "secrets=yes"))]


@pytest.mark.parametrize('size', [(80, 24), (160, 48)])
def test_dspace_inventory_and_persisted_compression_are_available_without_capturing(monkeypatch, size):
    import json
    from textual.widgets import Select
    from kei_panel.bridge import TaskOutcome
    from kei_panel.widgets.cards import StatusCard
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA', '0')
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN', '0')
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE', '1')
    async def exercise():
        app = KohaPanelApp(PanelEnv(installer=None, lang='en', plain=True, demo=True))
        original = app.bridge.task
        calls = []; preference = {'compression': 'gz'}
        async def task(name, *args, **kwargs):
            calls.append((name,args))
            if name == 'dspace-panel' and args[0] == 'backup-list':
                data = dict(preference, packages=['/backups/new.tar.gz.gpg'], directory='/backups',
                            details=[dict(path='/backups/new.tar.gz.gpg',bytes=2048,modified_at=1730000000)])
                return TaskOutcome(results={'json':json.dumps(data)})
            if name == 'dspace-panel' and args[0] == 'backup-settings':
                assert args == ('backup-settings', '--compression', 'xz', '--confirm')
                preference['compression'] = 'xz'
                return TaskOutcome(results={'json':json.dumps(preference)})
            return await original(name,*args,**kwargs)
        app.bridge.task = task
        async with app.run_test(size=size) as pilot:
            await pilot.pause(1.5)
            app.backup_scope='dspace'; app.screen.action_show('backups')
            await until(pilot, loaded(app))
            view = current_view(app)
            select = view.query_one('#bk-ds-codec', Select)
            assert not select.disabled and select.value == 'gz'
            assert '2 KB' in str(view.query_one('#bk-ds-size', StatusCard).query_one('.card-value').render())
            assert not any(args and args[0]=='backup-settings' for name,args in calls)
            select.value='xz'
            await until(pilot, lambda: preference['compression']=='xz')
            await until(pilot, lambda: not select.disabled)
            view.refresh_data()
            await until(pilot, loaded(app))
            assert select.value == 'xz'
            assert not any(args and args[0] in ('backup-create','backup-restore','backup-test') for name,args in calls)
    asyncio.run(exercise())
