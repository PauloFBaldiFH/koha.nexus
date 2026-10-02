# koha.nexus panel: Textual prototype

A Textual front end for the bash panel (`../installer`). It is a
prototype that runs **next to** the whiptail/dialog panel: nothing in
`installer` changes, and `sudo config.sh` still opens the classic panel.

## Try it

```sh
cd panel
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m kei_panel --demo        # simulated installer: no root, no Koha
sudo KEI_INSTALLER=/usr/local/bin/config.sh .venv/bin/python -m kei_panel   # a real server
```

Keys: arrows / Tab / Enter everywhere, `d` dashboard, `b` backup, `t` database
tables, `a` AI cataloguing, `q` exit, `ctrl+p` command palette. Every card
and button also takes mouse clicks, and lists scroll with the wheel.

## How it talks to bash

`bridge.py` is the only door:

| Menu entry kind | What happens |
| --- | --- |
| interactive (most routines today) | Textual suspends; `config.sh --run <action>` gets the real terminal and asks its whiptail questions as it does now; Textual comes back when it ends |
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
  installer's MARC Replace routine (`config.sh --run marc-replace`, or
  `library-tools` with an older installer) to install or manage the page
  whose "AI cataloguing" tab uses this provider.

Every network call above is a thread job behind the Pac-Man loader.

## Module 2: AI assistant (dashboard)

`widgets/assistant.py` puts a chat under the dashboard's status cards. It
uses the provider saved in Module 1 and answers questions about the
catalogue, patrons, saved reports, system preferences and panel screens.

* **Read-only below the prompt.** Queries run as `kei_ai_ro`, a MariaDB
  account with `SELECT` only (no `sessions`/`api_keys`, no password
  columns), created once by **Set up read-only access**; its option file is
  `/etc/koha-easy-install/ai-readonly.cnf` (0600). Free SQL also passes
  `assistant/sqlguard.py` (one `SELECT`, no `INTO`/locks/`SLEEP`, `LIMIT 50`).
* **Changes are proposals.** The model can only call `propose_change`; the
  panel shows the exact SQL or panel routine with **Confirm** / **Cancel**.
  SQL is one single-table `UPDATE`/`INSERT`/`DELETE` with a real `WHERE`,
  run through `koha-mysql` in a transaction with `LIMIT` = the previewed
  row count, after `--backup-now` when the installer has it.
* **Blue links.** `[[biblio:12|Title]]` in an answer is a clickable blue
  link and a chip under it (Tab / Enter, ctrl+o for the first). Only ids a
  tool really returned become links; they open a record card (or switch
  panel screen for `page:` links).
* Each question is one thread job behind the Pac-Man loader; `--demo` uses
  a scripted model and an SQLite copy of a few Koha tables.

The system prompt is `assistant/prompt.py`.

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
  assistant/        Module 2: prompt, provider chat, agent loop, tools, SQL guard,
                    read-only DB account, links, running confirmed changes
  widgets/          PacmanLoader, StatusCard, ActionCard, AssistantPanel
  screens/          MainScreen, LoadingScreen, ConfirmScreen, ResultScreen, RecordScreen
  views/            dashboard, section (generic), backup, database, ai
  panel.tcss        all styling
tests/              pytest, headless (no Koha needed)
```

Run the tests with `python3 -m pytest -q tests` from this folder.
