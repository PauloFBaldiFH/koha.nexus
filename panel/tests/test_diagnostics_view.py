import json
import os

from kei_panel.screens.diagnostics import error_count, export_files, list_exports, read_text, summary


def _export(base, name="koha-diagnostics-srv-20261029-170834", mtime=None):
    out = base / name
    (out / "logs").mkdir(parents=True)
    (out / "README.txt").write_text("Koha diagnostics for support.\n")
    (out / "status.json").write_text(json.dumps({
        "generated_at": 1_791_000_000, "panel_version": "1.5.126", "platform": "wsl", "state": "degraded",
        "services": {"apache2": "active", "mariadb": "failed"}, "http": {"staff": 500, "opac": 200},
        "backup": {"last_file": "koha_library.sql.xz", "last_result": "ok"},
        "disk": {"total": 100 * 1024**3, "free": 40 * 1024**3}, "memory": {"total": 8 * 1024**3, "available": 1024**3}}))
    (out / "system.txt").write_text("$ uptime\n up 3 days\n")
    (out / "services.txt").write_text("mariadb.service: Failed with result 'exit-code'.\nok\n")
    (out / "logs" / "apache2_error.log").write_text("[cgi:error] DBI connect failed\n[notice] fine\n[x] fatal\n")
    if mtime:
        os.utime(out, (mtime, mtime))
    return out


def test_exports_are_listed_newest_first(tmp_path):
    old = _export(tmp_path, "koha-diagnostics-a", mtime=1_000)
    new = _export(tmp_path, "koha-diagnostics-b", mtime=2_000)
    (tmp_path / "something-else").mkdir()
    assert list_exports(tmp_path) == [new, old]
    assert list_exports(tmp_path / "missing") == []


def test_files_in_reading_order(tmp_path):
    out = _export(tmp_path)
    names = [str(p.relative_to(out)) for p in export_files(out)]
    assert names == ["README.txt", "status.json", "system.txt", "services.txt", "logs/apache2_error.log"]


def test_summary_shows_the_state_and_error_counts(tmp_path):
    out = _export(tmp_path)
    text = "\n".join(summary(out))
    assert "koha.nexus 1.5.126 · wsl · State: degraded" in text
    assert "HTTP 500 / 200" in text
    assert "Services: mariadb (failed)" in text
    assert "Disk free: 40.0 GB / 100.0 GB" in text
    assert "      2  logs/apache2_error.log" in text
    assert "      1  services.txt" in text
    assert error_count("ok\nError here\nwarn") == 1


def test_a_big_file_shows_its_end(tmp_path):
    f = tmp_path / "big.log"
    f.write_text("".join(f"line {i}\n" for i in range(1000)))
    text = read_text(f, limit=100)
    assert text.splitlines()[-1] == "line 999" and not text.startswith("ine")
    assert "missing.log" in read_text(tmp_path / "missing.log")


def test_viewer_opens_on_the_summary_and_shows_a_file(tmp_path, widget_event_loop):
    import asyncio

    from textual.app import App
    from textual.widgets import OptionList, RichLog

    from kei_panel.screens.diagnostics import DiagnosticsScreen
    out = _export(tmp_path)

    class Host(App):
        def on_mount(self):
            self.push_screen(DiagnosticsScreen(out, can_open=False))

    async def run():
        app = Host()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            log = screen.query_one("#diag-text", RichLog)
            assert any("State: degraded" in str(line.text) for line in log.lines)
            assert not screen.query("#open-folder")
            files = screen.query_one("#diag-files", OptionList)
            files.highlighted = files.option_count - 1      # logs/apache2_error.log
            await pilot.pause()
            assert any("DBI connect failed" in str(line.text) for line in log.lines)
    asyncio.run(run())
