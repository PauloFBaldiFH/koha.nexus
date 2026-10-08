"""cron.py: Koha's koha_tasks file read into jobs and written back."""

from kei_panel import cron

INSTALLER_FILE = """# ======================================================================
# koha.nexus schedules
# ======================================================================
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=root

# Database backup
0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1
0 3 * * 0 root /bin/bash /root/backup_marc.sh >/dev/null 2>&1
30 1 * * * root /usr/sbin/koha-shell library -c "/usr/share/koha/bin/cronjobs/cleanup_database.pl --confirm --sessions --sessdays 2 --zebraqueue 10" >/dev/null 2>&1
#off# 45 0 * * * root /usr/sbin/koha-shell library -c "/usr/share/koha/bin/cronjobs/fines.pl" >/dev/null 2>&1

# my hourly sync
*/15 * * * 1-5 root /usr/local/bin/sync.sh
# BEGIN AI assistant
0 4 * * * root /usr/local/bin/kei-ai-refresh
# END AI assistant
"""


def test_parse_reads_presets_off_lines_own_lines_and_blocks():
    cf = cron.parse(INSTALLER_FILE, "library")
    sql = cf.job("backup_sql")
    assert (sql.enabled, sql.freq, sql.time()) == (True, "daily", "23:00")
    marc = cf.job("backup_marc")
    assert (marc.freq, marc.day, marc.time()) == ("weekly", 0, "03:00")
    fines = cf.job("fines")
    assert not fines.enabled and fines.time() == "00:45"
    # Presets missing from a file with jobs come in switched off.
    assert not cf.job("authorities").enabled and not cf.job("reindex").enabled
    own = [j for j in cf.jobs if not j.key]
    assert len(own) == 1 and own[0].freq == "custom" and own[0].raw == "*/15 * * * 1-5"
    assert own[0].note == ["# my hourly sync"]
    assert cf.env == ["MAILTO=root"]
    assert cf.blocks == ["# BEGIN AI assistant\n0 4 * * * root /usr/local/bin/kei-ai-refresh\n# END AI assistant"]


def test_render_round_trip_keeps_everything():
    cf = cron.parse(INSTALLER_FILE, "library")
    text = cron.render(cf)
    assert cron.file_problem(text) == ""
    assert text.startswith(cron.HEADER) and cron.CRON_PATH in text and "MAILTO=root" in text
    assert "# my hourly sync\n*/15 * * * 1-5 root /usr/local/bin/sync.sh" in text
    assert "# BEGIN AI assistant" in text and "# END AI assistant" in text
    assert "#off# 45 0 * * * root" in text
    again = cron.parse(text, "library")
    assert [(j.key, j.enabled, j.schedule(), j.command) for j in again.jobs] == \
           [(j.key, j.enabled, j.schedule(), j.command) for j in cron.parse(text, "library").jobs]
    assert cron.render(again) == text


def test_empty_file_gets_the_defaults():
    cf = cron.defaults("lib2")
    on = {j.key for j in cf.jobs if j.enabled}
    assert on == {p.key for p in cron.PRESETS if p.enabled}
    assert "reindex" not in on and "authorities" not in on and "fines" not in on
    assert 'MAILTO=""' in cf.env
    text = cron.render(cf)
    assert "koha_lib2" in text and cron.file_problem(text) == ""


def test_authority_linking_daily_or_weekly():
    p = cron.BY_KEY["authorities"]
    assert p.freqs == ("daily", "weekly") and "link_bibs_to_authorities.pl" in p.command
    job = cron.preset_job(p, "library")
    job.enabled = True
    assert job.line() == ('0 4 * * 0 root /usr/sbin/koha-shell library -c '
                          '"/usr/share/koha/bin/link_bibs_to_authorities.pl" >/dev/null 2>&1')
    daily = cron.with_freq(job, "daily")
    assert daily.schedule() == "0 4 * * *"


def test_reindex_preset_uses_the_helper():
    job = cron.preset_job(cron.BY_KEY["reindex"], "library")
    assert job.command.startswith(cron.REINDEX_BIN + " library")


def test_schedule_problem():
    for good in ("0 23 * * *", "*/15 * * * 1-5", "0 3 1,15 * *", "@daily", "0 3 * * sun", "0 3 * jan-mar *"):
        assert cron.schedule_problem(good) == "", good
    assert "five fields" in cron.schedule_problem("0 23 * *")
    assert "out of range" in cron.schedule_problem("0 24 * * *")
    assert "out of range" in cron.schedule_problem("*/0 * * * *")
    assert cron.schedule_problem("0 3 * * ; rm") != ""


def test_parse_time_and_describe():
    assert cron.parse_time("2:30") == (2, 30) and cron.parse_time("23h05") == (23, 5)
    assert cron.parse_time("24:00") is None and cron.parse_time("ab") is None
    job = cron.Job("x", "X", "true", freq="monthly", day=5, hour=1)
    assert cron.describe(job) == "Monthly, day 5 at 01:00"
    assert cron.describe(cron.with_freq(job, "weekly")) == "Weekly, Friday at 01:00"
    assert cron.with_freq(cron.Job("", "", "true", freq="weekly", day=0), "monthly").day == 1


def test_file_problem_catches_bad_lines():
    assert "PATH" in cron.file_problem("0 1 * * * root true\n")
    assert "not a cron line" in cron.file_problem(cron.CRON_PATH + "\nrm -rf /\n")
    assert "out of range" in cron.file_problem(cron.CRON_PATH + "\n0 99 * * * root true\n")


def test_write_temp_and_read(tmp_path, monkeypatch):
    path = cron.write_temp("x\n")
    try:
        assert path.stat().st_mode & 0o777 == 0o600 and path.read_text() == "x\n"
    finally:
        path.unlink()
    monkeypatch.setenv("KEI_CRON_FILE", str(tmp_path / "nope"))
    assert cron.read() == ""
