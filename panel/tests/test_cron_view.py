"""The scheduled tasks screen (views/crons.py), driven headless in demo mode."""

import asyncio
import time

from conftest import INSTALLER
from textual.widgets import Input, Select, Switch

from kei_panel import cron
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen, TextScreen

FILE = """# koha.nexus schedules
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1
0 3 * * 0 root /bin/bash /root/backup_marc.sh >/dev/null 2>&1
# my own report
15 6 * * 1-5 root /usr/local/bin/report.sh
"""


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def _index(view, key):
    return next(i for i, j in enumerate(view.cf.jobs) if j.key == key)


def test_switch_schedule_preview_and_save(tmp_path, monkeypatch):
    path = tmp_path / "koha_tasks"
    path.write_text(FILE)
    monkeypatch.setenv("KEI_CRON_FILE", str(path))
    sent = {}
    real = cron.write_temp

    def spy(text):
        sent["text"] = text
        sent["path"] = real(text)
        return sent["path"]
    monkeypatch.setattr(cron, "write_temp", spy)
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("s")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-crons")
            await _until(pilot, lambda: view.drawn)
            own = next(i for i, j in enumerate(view.cf.jobs) if not j.key)
            assert view.query_one(f"#cr-freq-{own}", Select).value == "custom"
            assert view.query_one(f"#cr-raw-{own}", Input).value == "15 6 * * 1-5"

            # Authority linking: off, switched on, daily at 02:30.
            a = _index(view, "authorities")
            assert view.query_one(f"#cr-on-{a}", Switch).value is False
            view.query_one(f"#cr-on-{a}", Switch).value = True
            view.query_one(f"#cr-freq-{a}", Select).value = "daily"
            await pilot.pause(0.1)
            assert not view.query_one(f"#cr-day-{a}").display
            view.query_one(f"#cr-time-{a}", Input).value = "2:30"
            # The full index rebuild, weekly on Wednesday at 01:00.
            r = _index(view, "reindex")
            view.query_one(f"#cr-on-{r}", Switch).value = True
            view.query_one(f"#cr-day-{r}", Select).value = 3
            view.query_one(f"#cr-time-{r}", Input).value = "01:00"

            # A wrong time is caught before anything is written.
            view.query_one(f"#cr-time-{_index(view, 'fines')}", Input).value = "25:00"
            assert "HH:MM" in view.new_text()[1]
            view.query_one(f"#cr-time-{_index(view, 'fines')}", Input).value = "00:45"

            view.preview()
            await _until(pilot, lambda: isinstance(app.screen, TextScreen))
            assert "30 2 * * * root /usr/sbin/koha-shell" in app.screen._text
            await pilot.press("escape")

            view.save()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "Authority linking: on" in app.screen._preview
            assert "Full search index rebuild: on" in app.screen._preview
            await pilot.pause(0.1)
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert "Schedules updated" in app.screen._body
            assert not sent["path"].exists()               # the file handed to the task is gone
            text = sent["text"]
            assert "30 2 * * * root /usr/sbin/koha-shell library -c \"/usr/share/koha/bin/link_bibs_to_authorities.pl\"" in text
            assert "0 1 * * 3 root /usr/local/bin/koha-kei-reindex library" in text
            assert "#off# 45 0 * * * root" in text            # fines stays off
            assert "# my own report\n15 6 * * 1-5 root /usr/local/bin/report.sh" in text
            assert cron.file_problem(text) == ""

    asyncio.run(main())


def test_custom_schedule_is_checked_and_nothing_changed(tmp_path, monkeypatch):
    path = tmp_path / "koha_tasks"
    path.write_text(FILE)
    monkeypatch.setenv("KEI_CRON_FILE", str(path))
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("s")
            view = app.screen.query_one("#view-crons")
            await _until(pilot, lambda: view.drawn)
            # Nothing changed: no confirmation, no task.
            view.save()
            await pilot.pause(0.2)
            assert not isinstance(app.screen, ConfirmScreen)

            b = _index(view, "backup_sql")
            view.query_one(f"#cr-freq-{b}", Select).value = "custom"
            await pilot.pause(0.1)
            assert view.query_one(f"#cr-raw-{b}").display and not view.query_one(f"#cr-time-{b}").display
            view.query_one(f"#cr-raw-{b}", Input).value = "0 25 * * *"
            assert view.new_text()[1]
            view.query_one(f"#cr-raw-{b}", Input).value = "0 */6 * * *"
            text, problem = view.new_text()
            assert problem == "" and "0 */6 * * * root /bin/bash /root/backup_sql.sh" in text

            # Defaults bring the presets back, the hand-written line stays.
            view.defaults()
            await _until(pilot, lambda: view.drawn)
            assert any(not j.key for j in view.cf.jobs)
            assert view.query_one(f"#cr-freq-{_index(view, 'backup_sql')}", Select).value == "daily"

    asyncio.run(main())
