# koha.nexus panel (Textual)

The Textual front end of the bash panel (`../installer`). `sudo config.sh`
opens it; the classic whiptail panel is the fallback when it cannot start,
and `sudo KEI_UI=whiptail config.sh` always opens the classic one. Every
routine of the menu is a panel screen: no whiptail box is opened from it.

## How config.sh starts it

1. The sources are installed under `/usr/local/lib/koha-easy-installer/panel`:
   copied from `panel/` next to the installer (a git clone, or the copy the
   Windows installer puts in Debian), or downloaded from GitHub when only the
   installer reached the server.
2. The first start builds a venv at `/usr/local/lib/koha-easy-installer/panel-venv`
   with `requirements.txt` (installing `python3-venv` if needed), behind the
   bash Pac-Man line "Preparing the new panel". Later starts skip this step.
3. config.sh keeps the panel lock and runs `python -m kei_panel`; routines
   started from the new panel run as `config.sh --run <action>` with that
   lock descriptor handed down (`KEI_PANEL_LOCK_FD`).
4. On a new installation the new panel's first screen asks the panel language
   (config.sh skips its whiptail box) and starts again in it.
5. If the set-up fails (offline server, Python older than 3.9), the panel
   crashes, or it draws nothing within 60 s (`KEI_PANEL_START_TIMEOUT`), a box
   says why and the classic panel opens; it is tried again at the next
   start.
   Textual draws on stderr, so config.sh never redirects it: the app writes
   its own tracebacks to `/var/log/koha-easy-install/new-panel.log`.

`KEI_UI=whiptail` (or `dialog`) opens the classic panel directly.

## Try it without Koha

```sh
cd panel
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m kei_panel --demo        # simulated installer: no root, no Koha
```

Keys: arrows / Tab / Enter everywhere, `d` dashboard, `b` backup, `t` database
tables, `a` AI cataloguing, `l` library tools, `q` exit, `ctrl+p` command palette. Every card
and button also takes mouse clicks, and lists scroll with the wheel.

## How it talks to bash

`bridge.py` is the only door:

| Menu entry kind | What happens |
| --- | --- |
| native (every entry) | the routine runs as `config.sh --task NAME ARGS` behind the Pac-Man loader; its questions are the panel's own screens (see below) |
| interactive (only with an installer older than the panel) | Textual suspends; `config.sh --run <action>` gets the real terminal and asks its whiptail questions; Textual comes back when it ends |
| background (an installer verb exists: `--rebuild-search-index`, `--status-json`...) | the verb runs as an async subprocess in a worker, behind the Pac-Man loader, its output streamed to the loader's log |

The installer's own `KEI_CLI_MODE` line says which verbs exist, so when a
routine gains a non-interactive verb (e.g. `--backup-now`) its card moves to
the background path by itself.

## The worker + Pac-Man pattern

```python
from kei_panel.tasks import run_with_loader

async def job(reporter):                 # or a plain def: runs in a thread
    reporter.status("Dumping the database")
    rc = await app.bridge.run_verb(("--backup-now",), reporter)
    reporter.progress(1, 1)
    return rc

run_with_loader(app, t("Saving a safety backup"), job, on_done=show_result)
```

`run_with_loader` pushes `LoadingScreen` first, then starts the job in a
worker; `PacmanLoader` animates on a timer while the job runs, Esc cancels
it (a subprocess is terminated), and `on_done` gets a `TaskResult`.
`PacmanLoader` is a normal widget too: the dashboard uses the one-line form
inline while it reads the status.

## Ported routines (no whiptail)

A ported routine asks its questions in the panel's own screens (folder and
file pickers, choices, confirmations), then runs in the installer as
`config.sh --task NAME ARGS` behind Pac-Man. The installer answers in a
line protocol (`@@step`, `@@done`, `@@note`, `@@msg`, `@@result`, see
"PANEL TASKS" in `installer`), so its own texts and translations are shown
and its checks (locks, safety copy, rollback) stay in one place. Menu
entries with `kind="native"` use `routines/`; an installer without `--task`
keeps the classic routine.

Questions a routine asks halfway (`@@ask`) are answered in one of two ways:
`KEI_TASK_ANSWER=no|yes` answers all of them (the preview-then-run pattern:
a dry run stops at its question), or `KEI_TASK_INTERACTIVE=1` makes the
routine wait for each answer, which the panel asks in a confirm screen over
the loader and writes to the routine's stdin (`ask=asker(app)` in
`run_task`). Menus and text boxes work the same way: routines call
`ask_menu` / `ask_input` (answer in `REPLY`) or the tools' `ui_menu` /
`ui_input` (answer printed), whiptail in the classic panel, which become
`@@choose` / `@@input` lines answered with `ok VALUE` or `cancel`. Long
installs announce their stages with `@@stage`.

The rest of the menu (publishing, library tools, schedules, languages,
updates, about, reboot) runs its classic routine unchanged with
`config.sh --task run ACTION`: in a task every dialog helper becomes a
protocol line the panel answers, so each box is a panel screen:

| Line | Classic dialog | Panel screen | Answer |
| --- | --- | --- | --- |
| `@@say KIND TITLE<TAB>TEXT` | `msg_ok` / `msg_info` / `msg_error` | message box | `ok` once closed |
| `@@view TITLE<TAB>TEXT` | `ui_textbox` | long text | `ok` |
| `@@check TITLE<TAB>PROMPT<TAB>KEY<TAB>LABEL<TAB>ON...` | `ui_checklist` | check list | `ok K1<TAB>K2` or `cancel` |
| `@@file file\|dir<TAB>TITLE<TAB>PROMPT<TAB>START<TAB>EXTS` | `select_file` / `select_directory` | file or folder picker | `ok PATH` or `cancel` |
| `@@edit TITLE<TAB>PATH<TAB>NOTE` | `nano` (schedules) | text editor (Save / Cancel) | `ok` or `cancel` |
| `@@cancel on\|off` | | the loader's Cancel button (while an authorization link waits) | |

The protocol goes to stderr, which the panel reads with stdout, so a menu
whose answer is captured with `$(...)` still reaches it. A routine step run
by `tui_run` (output to its log) never waits for an answer.

| Phase | Section | State |
| --- | --- | --- |

| 1 | Backup center (manual backup, integrity test, cloud backup) and Restore | done |
| 2 | Database tables and maintenance (optimization, SQL reports pack) | done |
| 3 | Install Koha server, first-access credentials | done |
| 4 | Diagnostics (status, health check, validation report, services, Apache log) | done |
| 5 | Search engine and indexing | done |
| 6 | Security center | done |
| 7 | Koha settings and parameters | done |
| 8 | Publishing (Cloudflare tunnel, SSL, Search Console) | done |
| 9 | Schedules, languages, updates, library tools, general tools, about, reboot | done |

Full-screen programs of their own (htop, nethogs, links, Midnight Commander)
get the terminal after their choice and installation are made in the
panel, as they would in any panel.

## Module 1: AI setup (`a`)

`views/ai.py` sets up the AI the cataloguing tools use:

* **Provider selector** (radio list, mouse or arrows): Local Ollama, Google
  Gemini, OpenAI, Anthropic Claude, or any OpenAI-compatible server.
* **API key** in a password field. Saved to `vision.conf` (the file the
  staff interface reads) and, per provider, to `ai-keys.conf` next to it,
  both mode 0600; switching provider brings the saved key back. A saved key
  is never put back in a widget: the field stays empty (empty = keep it) and
  shows `••••` plus the last four characters.
* **Local Ollama box**: checks that Ollama answers and whether the model is
  downloaded, downloads it (`/api/pull`, with a real progress bar), and shows
  the install command when nothing answers.
* **Test connection** (F5) lists the provider's models with the same
  endpoints as the staff interface's own test; **Save** (ctrl+s) refuses the
  same problems the Perl side does (bad URL, key over plain http, missing key).
* **Next step: MARC Replace**: once a provider is saved, opens the
  installer's MARC Replace routine (`config.sh --task run marc-replace`, its
  menus as panel screens; `library-tools` with an older installer) to install or manage the page
  whose "AI cataloguing" tab uses this provider.

Every network call above is a thread job behind the Pac-Man loader.

## Layout

```
kei_panel/
  app.py            KohaPanelApp: decides how a menu entry runs
  bridge.py         installer calls (--run, verbs, --status-json, koha-mysql)
  tasks.py          run_with_loader, Reporter, TaskResult
  menus.py          the menu tree as data (labels = installer translation keys)
  i18n.py           t() over the same lang/*.cache files and _MENU_PT
  glyphs.py         plain symbols for the classic Windows console
  env.py            installer path, language, KEI_PLAIN_GLYPHS rule
  aiconf.py         vision.conf of the AI cataloguing tabs, ai-keys.conf, key masking
  aiclient.py       connection test and local Ollama (version, models, pull), blocking
  marcreplace.py    is the MARC Replace page installed, which --run action opens it
  demo.py           simulated --task answers (demo mode, tests)
  routines/         every routine: backup, database, install, diagnostics,
                    search, security, settings, tools (the generic runner)
  widgets/          PacmanLoader, StatusCard, ActionCard
  screens/          MainScreen, LoadingScreen, dialogs (confirm, choice, input,
                    message, check list, editor, text), PathPickerScreen,
                    LogTailScreen
  views/            dashboard, section (generic), backup, database, ai
  panel.tcss        all styling
tests/              pytest, headless (no Koha needed)
```

Run the tests with `python3 -m pytest -q tests` from this folder.
