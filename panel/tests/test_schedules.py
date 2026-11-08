"""The Schedules center (Paulo, 2026-11-06): every scheduled job of the
server in one list, from every file that holds one, read only.

The rows (schedules.py): one per cron line, never twice; the presets the
editor offers but that are not written are not schedules; lines written by
hand are kept and shown (a password in them hidden); a command scheduled
twice says so; the next run follows cron's rules; the last run comes only
from a reliable record ("No run recorded" otherwise); WP-Cron is
WordPress's own scheduler, not a server schedule. The screen, on four
servers (demo mode): what is installed decides the filters and the cards;
the Koha group opens it filtered; opening it only reads.
"""

import asyncio
import datetime as dt

import pytest

from kei_panel import cloud, cron, platforms, schedules
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv

NOW = dt.datetime(2026, 11, 6, 10, 30)        # a Friday

TASKS = """PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
# Database backup (compressed SQL) - Daily at 23:00
0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1
#off# 0 2 * * 6 root /usr/local/bin/koha-kei-reindex library >/dev/null 2>&1
30 23 * * * root /bin/bash /root/cloud_plan.sh gdrive sql+marc >/dev/null 2>&1
# my own copy
10 6 * * * root mysqldump -pS3cretPass koha_library > /root/extra.sql
# BEGIN KOHA EMAIL NOTICES
0 8 * * * root /usr/sbin/koha-shell library -c "process_message_queue.pl"
# END KOHA EMAIL NOTICES
"""
PLATFORMS = ("30 2 * * * root /usr/local/bin/config.sh --task platform-backup-run tainacan scheduled >/dev/null 2>&1\n"
             "30 3 * * 0 root /usr/local/bin/config.sh --task platform-backup-maintain tainacan >/dev/null 2>&1\n"
             "30 4 1 * * root /usr/local/bin/config.sh --task platform-backup-verify tainacan 30 >/dev/null 2>&1\n")


# ----------------------------------------------------------------------
# Cron expressions
# ----------------------------------------------------------------------
@pytest.mark.parametrize("sched,expected", [
    ("0 23 * * *", dt.datetime(2026, 11, 6, 23, 0)),
    ("15 9 * * *", dt.datetime(2026, 11, 7, 9, 15)),          # already past today
    ("*/5 * * * *", dt.datetime(2026, 11, 6, 10, 35)),
    ("0 3 * * 0", dt.datetime(2026, 11, 8, 3, 0)),            # Sunday
    ("0 3 * * 7", dt.datetime(2026, 11, 8, 3, 0)),            # 7 is Sunday too
    ("0 8 * * mon-fri", dt.datetime(2026, 11, 9, 8, 0)),
    ("45 0 5 * *", dt.datetime(2026, 12, 5, 0, 45)),
    ("0 0 1 jan *", dt.datetime(2027, 1, 1, 0, 0)),
    ("5 4 1,15 * 0", dt.datetime(2026, 11, 8, 4, 5)),          # day 1 or 15, OR Sunday (cron's rule)
    ("0 */6 * * *", dt.datetime(2026, 11, 6, 12, 0)),
    ("10-50/20 11 * * *", dt.datetime(2026, 11, 6, 11, 10)),
    ("@daily", dt.datetime(2026, 11, 7, 0, 0)),
    ("@reboot", None),
    ("0 25 * * *", None),
    ("0 3 31 2 *", None),                                     # never
    ("nonsense", None),
])
def test_the_next_run_follows_cron(sched, expected):
    assert schedules.next_run(sched, NOW) == expected


def test_a_schedule_in_words():
    d = schedules.describe
    assert d("0 23 * * *") == "Daily at 23:00"
    assert d("0 3 * * 0") == "Weekly, Sunday at 03:00"
    assert d("0 1 5 * *") == "Monthly, day 5 at 01:00"
    assert d("*/5 * * * *") == "Every 5 minutes"
    assert d("30 * * * *") == "Every hour at :30"
    assert d("15 6 * * 1-5") == "Monday to Friday at 06:15"
    assert d("@reboot") == "At startup"
    assert d("0 8 1-7 * 1") == "0 8 1-7 * 1"             # as written when there are no words for it


# ----------------------------------------------------------------------
# The rows
# ----------------------------------------------------------------------
def test_one_row_per_line_and_the_presets_not_written_are_not_schedules():
    rows = schedules.koha_task_rows(TASKS, "library")
    names = [r.name for r in rows]
    # Four job lines and one block line: five rows; fines, Plack... are not in the file.
    assert len(rows) == 5
    assert names[:3] == ["Database backup (compressed SQL)", "Full search index rebuild",
                         "Cloud backup gdrive (SQL + MARC21)"]
    assert not any("Fine" in n or "Plack" in n for n in names)
    off = rows[1]
    assert off.state == "off" and off.when == "Weekly, Saturday at 02:00"
    hand = rows[3]
    assert hand.name.startswith("Written by hand: mysqldump -p***") and "S3cret" not in hand.name + hand.command
    assert hand.platform == "server" and hand.editor == "Schedules & cron tasks"
    block = rows[4]
    assert block.name.startswith("Koha email notices:") and block.editor == "Messaging & interoperability"
    assert {r.kind for r in rows[:1]} == {"backup"} and rows[2].kind == "backup" and rows[1].kind == "maintenance"
    assert rows[0].key == "koha:backup_sql" and rows[2].key == "koha:cloud:gdrive"


def test_the_platforms_backups_and_the_installers_own_files():
    rows = schedules.platform_rows(PLATFORMS)
    assert [(r.platform, r.name, r.when, r.key) for r in rows] == [
        ("tainacan", "Backup", "Daily at 02:30", "tainacan:run"),
        ("tainacan", "Backup upkeep (old packages and repository)", "Weekly, Sunday at 03:30", "tainacan:maintain"),
        ("tainacan", "Restore test of an older backup", "Monthly, day 1 at 04:30", "tainacan:verify")]
    assert rows[0].editor == "Backup center > Schedule backups"
    es = schedules.system_rows("koha_es_watchdog", "*/5 * * * * root /usr/local/bin/koha-es-watchdog.sh\n")
    assert [(r.name, r.when, r.editor) for r in es] == [
        ("Elasticsearch indexer watchdog", "Every 5 minutes", "Search engine & indexing")]
    ollama = schedules.system_rows("koha-easy-ollama", "@reboot root OLLAMA_HOST=127.0.0.1:11434 ollama serve\n")
    assert ollama[0].when == "At startup" and ollama[0].platform == "server"


def test_wp_cron_is_wordpress_s_own_scheduler_never_a_server_schedule():
    with_tn = schedules.collect({"koha-nexus-platform-backups": PLATFORMS}, "library", tainacan=True)
    wp = [r for r in with_tn if r.source == "wp-cron"]
    assert len(wp) == 1 and wp[0].state == "internal" and not wp[0].sched
    assert "not a server schedule" in wp[0].when
    schedules.fill_times(with_tn, NOW, {})
    assert wp[0].next == "—" and wp[0].last == "No run recorded"
    assert not [r for r in schedules.collect({"koha_tasks": TASKS}, "library", tainacan=False)
                if r.source == "wp-cron"]


def test_a_command_scheduled_twice_says_so_and_an_off_line_does_not_count():
    twice = TASKS + "0 22 * * * root /bin/bash /root/backup_sql.sh\n"
    rows = schedules.collect({"koha_tasks": twice}, "library", tainacan=False)
    sql = [r for r in rows if "backup_sql.sh" in r.command]
    assert len(sql) == 2 and all(r.also for r in sql)
    assert "Daily at 22:00" in sql[0].also[0] and "Daily at 23:00" in sql[1].also[0]
    off = TASKS + "#off# 0 4 * * 6 root /usr/local/bin/koha-kei-reindex library >/dev/null 2>&1\n"
    assert not any(r.also for r in schedules.collect({"koha_tasks": off}, "library", tainacan=False))


def test_the_last_run_only_from_a_record_and_the_next_from_the_line():
    rows = schedules.collect({"koha_tasks": TASKS, "koha-nexus-platform-backups": PLATFORMS}, "library", True)
    plans = [cloud.Plan("gdrive", "gdrive", "Koha", 30)]
    history = [cloud.History("sql", "2026-11-05 23:31:02", "Cloud OK [gdrive] koha.sql.gz", True)]
    tn = platforms.BackupState(known=True, last="knx-tainacan-20261106-023000|2026-11-06 02:30:00|self",
                               verified="2026-11-01 04:30:12 knx-tainacan-20261002-023000 failed")
    last = schedules.last_runs({"last_result": "ok", "log_epoch": "1762392000"}, plans, history, tn)
    schedules.fill_times(rows, NOW, last)
    by = {r.key: r for r in rows if r.key}
    assert by["koha:backup_sql"].last.endswith("· OK") and by["koha:backup_sql"].last_state == "ok"
    assert by["koha:cloud:gdrive"].last == "2026-11-05 23:31:02 · OK"
    assert by["tainacan:run"].last == "2026-11-06 02:30:00 · OK"
    assert by["tainacan:verify"].last == "2026-11-01 04:30 · FAILED" and by["tainacan:verify"].last_state == "bad"
    assert by["tainacan:maintain"].last == "No run recorded"
    assert by["koha:reindex"].next == "Switched off" and by["koha:reindex"].last == "No run recorded"
    assert by["koha:backup_sql"].next == "2026-11-06 23:00"
    assert by["tainacan:verify"].next == "2026-12-01 04:30"


def test_the_files_are_read_from_the_cron_folder_and_a_missing_one_is_left_out(tmp_path, monkeypatch):
    (tmp_path / "koha_tasks").write_text(TASKS)
    (tmp_path / "koha_sitemap").write_text("SHELL=/bin/bash\n17 3 * * * root /usr/local/bin/config.sh --opac-sitemap\n")
    (tmp_path / "someone-else").write_text("* * * * * root /usr/bin/true\n")
    monkeypatch.delenv("KEI_CRON_FILE", raising=False)
    monkeypatch.setenv("KEI_CRON_DIR", str(tmp_path))
    files = schedules.read_files()
    assert set(files) == {"koha_tasks", "koha_sitemap"}          # only the files it knows
    rows = schedules.collect(files, "library", tainacan=False)
    assert rows[-1].name == "OPAC sitemap refresh" and rows[-1].when == "Daily at 03:17"


def test_the_filters():
    rows = schedules.collect({"koha_tasks": TASKS, "koha-nexus-platform-backups": PLATFORMS}, "library", True)
    assert {r.platform for r in schedules.shown(rows, "tainacan")} == {"tainacan"}
    assert {r.kind for r in schedules.shown(rows, "", "backup")} == {"backup"}
    assert [r.name for r in schedules.shown(rows, "tainacan", "backup")] == [
        "Backup", "Backup upkeep (old packages and repository)", "Restore test of an older backup"]
    assert schedules.platforms_offered(False, True) == ["tainacan", "server"]


# ----------------------------------------------------------------------
# The screen, on four servers
# ----------------------------------------------------------------------
SERVERS = {"none": ("0", "0"), "koha": ("1", "0"), "tainacan": ("0", "1"), "both": ("1", "1")}
READS = {"platform-backup-status", "cloud-status", "set-schedule-status"}


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
        ran.append(name)
        return await real_task(name, *args, **kwargs)
    app.bridge.task = task
    return app


def current_view(app):
    from textual.widgets import ContentSwitcher
    switcher = app.screen.query_one("#views", ContentSwitcher)
    return switcher.query_one(f"#{switcher.current}")


async def until(pilot, ready, seconds=10.0):
    waited = 0.0
    while not ready() and waited < seconds:
        await pilot.pause(0.25)
        waited += 0.25
    return ready()


def state(view):
    from textual.widgets import Select
    from kei_panel.widgets.cards import ActionCard
    shown = schedules.shown(view.rows, view.platform, view.kind)
    blocks = [str(w.render()) for w in view.query("#sc-rows Static")]
    if shown:
        assert len(blocks) == len(shown) and all(r.name in b and r.editor in b for r, b in zip(shown, blocks))
    options = [v for _label, v in view.query_one("#sc-platform", Select)._options]
    return {"platforms": options, "cards": [c.entry.action for c in view.query(ActionCard) if c.display],
            "rows": [(r.platform, r.name) for r in shown], "blocks": blocks}


@pytest.mark.parametrize("server", list(SERVERS), indirect=True)
def test_the_center_on_four_servers_only_reads(server):
    async def main():
        ran: list = []
        app = make_app(ran)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.screen.query_one("#sidebar").blur()
            await pilot.press("s")
            await pilot.pause(0.3)
            await until(pilot, lambda: getattr(current_view(app), "ready", False))
            return current_view(app).id, state(current_view(app)), ran

    vid, st, ran = asyncio.run(main())
    assert vid == "view-schedules"
    assert set(ran) <= READS
    koha, tainacan = server in ("koha", "both"), server in ("tainacan", "both")
    assert st["platforms"] == [""] + [p for p, on in (("koha", koha), ("tainacan", tainacan), ("server", True)) if on]
    assert st["cards"] == ["crons"] * koha + ["pbackup-schedule"] * tainacan + ["set-schedule"] * (koha and tainacan)
    # The scheduled joint backup: one row, only with both platforms, with its last run from its history.
    joint = [n for p, n in st["rows"] if p == "koha+tainacan"]
    assert joint == (["Joint backup (Koha + Tainacan)"] if koha and tainacan else [])
    platforms_shown = {p for p, _n in st["rows"]}
    assert ("koha" in platforms_shown) is koha
    assert ("tainacan" in platforms_shown) is tainacan
    assert any("WP-Cron" in n for _p, n in st["rows"]) is tainacan
    if not koha and not tainacan:
        assert st["rows"] == [] and st["blocks"] == ["Nothing is scheduled here."]
    # One row per line of the files: never the same job twice.
    assert len(st["rows"]) == len(set(st["rows"]))


@pytest.mark.parametrize("server", ["both"], indirect=True)
def test_the_koha_group_opens_it_filtered_and_its_card_opens_the_editor(server):
    from textual.widgets import Select

    async def main():
        app = make_app([])
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.3)
            app.screen.action_show("schedules", scope="koha")
            await until(pilot, lambda: getattr(current_view(app), "ready", False))
            view = current_view(app)
            filtered = {p for p, _n in state(view)["rows"]}
            chosen = view.query_one("#sc-platform", Select).value
            view.query_one("#sc-kind", Select).value = "backup"
            await until(pilot, lambda: view.kind == "backup" and len(view.query("#sc-rows Static")) == 5)
            backups = state(view)["rows"]
            from kei_panel.widgets.cards import ActionCard
            card = next(c for c in view.query(ActionCard) if c.entry.action == "crons")
            card.post_message(ActionCard.Chosen(card.entry))
            await until(pilot, lambda: current_view(app).id == "view-crons"
                        and getattr(current_view(app), "drawn", False))
            return filtered, chosen, backups, current_view(app).id, getattr(app, "backup_scope", "")

    filtered, chosen, backups, editor, backup_scope = asyncio.run(main())
    # Koha's rows, and the joint backup (of both platforms) under the Koha filter too.
    assert filtered == {"koha", "koha+tainacan"} and chosen == "koha"
    assert [n for _p, n in backups] == ["Database backup (compressed SQL)", "MARC21 records backup",
                                       "Cloud backup gdrive (SQL + MARC21)", "Cloud backup wasabi-weekly (SQL)",
                                       "Joint backup (Koha + Tainacan)"]
    assert editor == "view-crons"
    assert backup_scope != "koha"          # the Backup center's own choice is left alone


def test_the_joint_backup_row_and_its_last_run():
    text = "SHELL=/bin/bash\n15 1 * * * root /usr/local/bin/config.sh --task set-run scheduled >/dev/null 2>&1\n"
    rows = schedules.collect({schedules.SET_FILE: text}, "library", True)
    joint = [r for r in rows if r.source == schedules.SET_FILE]
    assert [(r.platform, r.name, r.key) for r in joint] == [("koha+tainacan", "Joint backup (Koha + Tainacan)", "set:run")]
    assert joint[0].when.startswith("Daily at 01:15")
    assert schedules.shown(rows, "tainacan") and joint[0] in schedules.shown(rows, "koha")
    assert joint[0] not in schedules.shown(rows, "server")
    assert schedules.set_last_run("2026-11-06 01:16:52|ok|full|none|") == ("2026-11-06 01:16 · OK", "ok")
    assert schedules.set_last_run("2026-11-06 01:16:52|partial|partial|none|tainacan: x")[1] == "bad"
    assert schedules.set_last_run("2026-11-06 01:16:52|ok|full|failed|") == ("2026-11-06 01:16 · OK, cloud copy FAILED", "bad")
    assert schedules.set_last_run("2026-11-06 01:16:52|busy|||")[1] == "warn"
    assert schedules.set_last_run("") is None


def test_dspace_plan_cron_is_read_only_and_filters_under_each_explicit_member():
    files={'koha-nexus-plan-all':'# Managed by Koha.Nexus: backup plan all\n# Members=koha,tainacan,dspace\n30 2 * * * root KEI_DSPACE_OPERATIONS_DATA=\'{"id":"all"}\' /usr/local/bin/config.sh --task dspace operations plan-run --confirm >/dev/null 2>&1\n'}
    rows=schedules.collect(files,'library',False)
    assert len(rows)==1 and rows[0].platform=='koha+tainacan+dspace'
    assert schedules.shown(rows,'dspace')==rows
    assert schedules.shown(rows,'koha')==rows
    assert schedules.platforms_offered(False,False,True)==['dspace','server']


def test_dspace_plan_rows_show_their_last_run_and_never_call_a_failure_ok():
    # The agreed pattern: each schedule shows system, short text, last run and status.
    files={'koha-nexus-plan-all':'# Managed by Koha.Nexus: backup plan all\n# Members=koha,tainacan,dspace\n30 2 * * * root KEI_DSPACE_OPERATIONS_DATA=\'{"id":"all"}\' /usr/local/bin/config.sh --task dspace operations plan-run --confirm >/dev/null 2>&1\n'}
    rows=schedules.collect(files,'library',False)
    stamp=dt.datetime(2026,11,8,2,31).timestamp()
    good=dict(started=stamp-60,finished=stamp,capture='ok',copy='ok',retention='ok')
    last=schedules.operation_last_runs({'plans':[{'id':'all','last':good}]})
    schedules.fill_times(rows,dt.datetime(2026,11,8,12,0),last)
    assert rows[0].last=='2026-11-08 02:31 · OK' and rows[0].last_state=='ok'
    for bad in (dict(good,capture='partial'),dict(good,copy='failed'),dict(good,retention='not-run')):
        assert schedules.operation_last_runs({'plans':[{'id':'all','last':bad}]})['operations:koha-nexus-plan-all'][1]=='bad'
    assert schedules.operation_last_runs({'plans':[{'id':'all','last':None}]})=={}
