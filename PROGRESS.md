# koha.nexus: Project Progress

_Last updated: 2026-10-08. Panel version on `main`: **1.5.10**._

This file is the hand-off context for a fresh chat session. It replaces the older
PROGRESS.md (which described a WinForms "Management Panel" and a PR #62 that never
existed in this repository).

**koha.nexus : A smart, free and easy-to-use assistant for library management**
(PT: *Assistente inteligente e gratuito para facilitar a gestão de bibliotecas*).
Repository: `PauloFBaldiFH/koha.nexus` (renamed from Koha-Easy-Installer). Website:
`index.html` served at https://koha.nexus (GitHub Pages, `CNAME`).

---

## 1. Current architecture and decisions

### Components

| Part | Path | Stack | Role |
|---|---|---|---|
| Installer / engine | `installer` (installed as `/usr/local/bin/config.sh`) | Bash | Installs and maintains Koha on Debian/Ubuntu/WSL2. Holds every routine. Classic whiptail/dialog panel lives here too. |
| Translations | `lang/*.cache` (22 languages) | key=value dictionaries | English keys byte-for-byte; `pt.cache` must get every new string. Headers carry the panel version. |
| Integrity hash | `installer.sha256` | sha256 | Windows installer verifies it. **Regenerate after every change to `installer`.** |
| Textual panel (default UI) | `panel/kei_panel/` | Python 3, Textual 8.2 (own venv `panel-venv`) | Full-screen TUI. All 9 sections are native screens; no whiptail boxes. |
| Windows installer | `windows/` | PowerShell + C# launcher + .cmd | Installs Debian on WSL2 and Koha inside it. Install root `C:\Koha` (old `C:\KohaEasy` kept). |
| Free-address broker | `broker/` | Cloudflare Worker (TypeScript), D1, Queues | Gives each library `<name>.koha.nexus` and `<name>-admin.koha.nexus` through Cloudflare Tunnels. Live at `https://broker.koha.nexus`. |
| AI assistant (Module 2) | installed by installer section 38 | Perl (`tools/ai_assistant.pl`, `KohaEasy::Assistant`) + JS/CSS via `IntranetUserJS` | Chat on the Koha **web** staff home page, replacing the news block. |
| AI cataloguing / MARC replace | installer + `marc_replace.pl` + `panel/kei_panel/marcreplace.py` | Perl + JS | AI-generated MARC record preview, add as new or replace an existing biblio. |
| Tests | `tests/*.bats`, `panel/tests` | bats, pytest | Most bats suites need a real Koha; `tests/ai_assistant.bats` and `tests/z3950.bats` (MariaDB only) run in the cloud. Panel: `cd panel && python3 -m pytest -q tests`. |

### Key decisions (with dates)

- **Textual panel is the default UI** (2026-10-03). After Paulo called the first version
  "superficial" (routines still dropped into whiptail), the decision was a **full Python
  port**: every routine is a native Textual screen. Done in PR #21 to #27 (v1.5.0).
  - `sudo config.sh` opens Textual; on failure (or a 60 s start-up watchdog) it falls back to
    the classic panel with a reason. `KEI_UI=whiptail` forces classic.
  - Bridge to bash only through `config.sh --task NAME ARGS` (whitelisted in the installer's
    "PANEL TASKS" section) and `--run <action>`. Tasks talk back with `@@step/@@done/@@note/
    @@msg/@@result/@@ask/@@preview/...` lines on **stderr**, parsed by `bridge.TaskOutcome`.
  - **Pac-Man loader is mandatory for every heavy task** (`run_with_loader`), one-line style.
  - Textual draws on stderr, so never redirect the panel's stderr. Tracebacks go to
    `/var/log/koha-easy-install/new-panel.log`.
  - The Textual app must not take `PANEL_LOCK_FILE`; lock fd 9 is passed to children via
    `KEI_PANEL_LOCK_FD`.
  - Panel `t()` keys must match installer English keys byte for byte.
- **Version discipline**: bump `PANEL_VERSION` in `installer` + the 22 lang headers whenever the
  panel or installer changes, or "Update this panel via GitHub" says "up to date" and servers
  keep stale copies. Parallel PRs touching `installer` always conflict on `installer.sha256`
  and the version: whichever merges second merges `main`, takes the next version, and
  regenerates the hash.
- **AI assistant lives in the Koha web staff UI, not the TUI** (2026-10-02). Injected through a
  marked `IntranetUserJS` block (survives koha-common upgrades). Read-only MariaDB user
  `kei_ai_ro_<instance>` (sensitive tables/columns excluded). Since 1.5.15 (Subject 3) the model
  never writes SQL: catalogue search goes through Koha's search engine (database fallback), the
  other reads are fixed queries, small talk skips the tools, and each answer keeps the records
  it found for follow-up questions. Changes are action proposals (hold, patron fields, record
  fields, write-off) with a field diff and Approve & Execute / Reject; on approval the values
  are re-read and Koha's own Perl objects make the change with the librarian's permissions
  (not /api/v1, which needs OAuth), with undo JSON and a log.
- **Z39.50 / SRU servers** (1.5.15): panel screen `views/z3950.py` over `z3950.py` (curated
  `data/z3950_targets.json`, community sync from that file on `main`, imports, BER Z39.50 and
  SRU probes that must return valid MARC, blacklist history in `/etc/koha-easy-install`).
  Koha's side is `--task z3950-list` / `z3950-add FILE` (installer section 39).
- **AI providers**: Ollama (default `http://127.0.0.1:11434`, always send `num_ctx`, 16384),
  OpenAI, Anthropic, Google Gemini. Active key in `vision.conf` (owned by the Koha instance
  user, else the web says "provider not configured"); all keys in `ai-keys.conf` (0600).
  Saved keys are never shown back, only the last 4 characters.
- **Free addresses**: Paulo bought the `koha.nexus` domain; broker deployed by Paulo on the
  **Cloudflare Workers Free plan** (so `PBKDF2_ITERATIONS=20000`). One broker per Cloudflare
  account. His local `wrangler.toml` holds real IDs; the repo keeps placeholders. The Worker
  he deploys is `kei-broker`; a stray Cloudflare auto-deploy for a Worker named `koha-nexus`
  shows a red check on PRs and can be disconnected in Cloudflare.
- **Links from the panel** open through `panel/kei_panel/opener.py` (wslview/explorer.exe on
  WSL, xdg-open as SUDO_USER on a desktop, else copy via OSC 52). Never Python `webbrowser`.
- **Windows**: new installs go to `C:\Koha`; scheduled tasks live in the Task Scheduler root as
  "Koha - <task> (<USERNAME>)"; the `.cmd` no longer runs as admin. Use `Get-KohaPath`, not
  literal paths.
- **Naming**: product name koha.nexus everywhere visible; internal ids/paths such as
  `koha-easy-installer` and `/etc/koha-easy-install` are intentionally kept.

---

## 2. Completed and in-progress work

### Merged (newest first)

| PR | Version | What it did |
|---|---|---|
| #40 | 1.5.10 | MARC replace page: empty biblionumber now previews and adds the record as a **new** biblio ("Incluir no catálogo"); a resubmit does not duplicate. |
| #39 | 1.5.9 | Elasticsearch: validation and "Repair / rebuild indexing" run a real Koha search and show Koha's error; optional reset of search mappings, then re-test. |
| #35 to #38 | site | `index.html`: all 22 languages, per-language URLs (`?lang=xx` / `#xx`, Portuguese is `br`), copy buttons, public library network list (broker endpoint). |
| #34 | 1.5.8 | Dashboard "Addresses" grid with Open/Copy, Restart Koha, Export diagnostics. |
| #33 | 1.5.6 | Copy toast, `c` key, automatic Copy buttons for URLs and recovery codes. |
| #31 | 1.5.4 | Broker Worker completed for zone koha.nexus; installer `KEI_BROKER_URL=https://broker.koha.nexus`; clear offline message. |
| #30 | 1.5.3 | AI assistant reads the DB reliably (Ollama `num_ctx`, refusal guard, better author/subject search); AI cataloguing can replace a record. |
| #29 | 1.5.2 | Ollama on WSL2 (127.0.0.1, zstd), green dashboard, dialogs never clip buttons, compact web chat. |
| #28 | 1.5.1 | One "🤖 AI" menu (cataloguing + assistant tabs), vision.conf ownership fix, Install Ollama task. |
| #21 to #27 | 1.5.0 | Full Textual port, phases 1 to 9 (backups, database, install + credentials, diagnostics, search, security, settings, publishing, everything else) and default switch. |
| #18 to #20 | | Textual opened from config.sh with fallback, language screen, blank-window fix, watchdog. |
| #16, #17 | | Windows: `C:\Koha`, uninstaller `Uninstall-Koha.cmd`, "Acesso negado" fix for scheduled tasks. |
| #15 | | Module 2: AI assistant on the Koha staff home page. |
| #14 | | Module 1: AI setup screen in the Textual panel (providers, keys, connection test, Ollama pull). |
| #13 | | Textual panel prototype in `panel/`. |
| #1 to #11 | | Repo URL update, removed "Painel de Gestão" block, koha.nexus rename/tagline, home-folder file pickers, new logo, copyable credentials, WSL home in file explorer, AI cataloguing prompt + Gemini, native emoji, Cataloguing aids freeze fix. |

### Open

- **PR #32: recovery codes for free addresses** (branch `claude/textual-panel-prototype-ykcbvo`).
  Each enrollment returns a code `XXXX-XXXX-XXXX-XXXX`; broker stores only its sha256
  (migration `0002_recovery.sql`). Endpoints `POST /v1/recover` and signed
  `POST /v1/recovery-code`. Panel saves the code in
  `/etc/koha-easy-install/broker-recovery.txt` (0600); Free address asks "new or recover";
  manage menu entry "Recovery code".
  **Version clash:** the PR says 1.5.9, but `main` is already 1.5.10. It must merge `main`,
  become **1.5.11** (installer + 22 lang headers) and regenerate `installer.sha256` before
  merging. After merge Paulo runs `npm run db:migrate` and `npm run deploy` from `broker/`.

### Not yet verified on real hardware

- **Textual panel (1.5.x) on Paulo's real server**: no confirmation yet that it starts and that
  the routines work outside the cloud harness.
- **Free-address provisioning end to end**: broker is live and answers `ok`, but creating a
  tunnel from the panel has not been confirmed.
- **Elasticsearch repair (PR #39)**: not tested against a real Elasticsearch.
- **Full Koha install from the Textual panel** (phase 3) was not run in the cloud.

---

## 3. Pending implementation and roadmap

1. Finish PR #32 (rebase onto 1.5.10 as 1.5.11, hash, panel tests), merge, then migrate and
   deploy the broker.
2. Field test on Paulo's server, after updating the panel through the Update center or
   `sudo wget -O /usr/local/bin/config.sh https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer`:
   - panel start-up and each of the 9 sections;
   - Search → Repair / rebuild indexing on Elasticsearch (send the error or the tail of
     `/var/log/koha/<instance>/plack-error.log` if it still fails);
   - AI assistant on the staff home page (e.g. "find books by Machado de Assis");
   - MARC replace: new record with blank biblionumber, replace with a biblionumber.
3. Free address end to end: enroll, open `<name>.koha.nexus`, recover on a second server.
4. Windows: check DPI/layout and the full install on a physical Windows machine.
5. Robustness: more bats coverage that runs without a full Koha (only `ai_assistant.bats` does
   today); keep the Pac-Man loader and error screens consistent for any new task.
6. Optional: Paulo's older note about the Python import module (patron fields `firstname`,
   `surname`, `cardnumber`, `categorycode`, `branchcode`) was never picked up here.

---

## 4. Immediate next step

**Bring PR #32 up to date and merge it:**

```bash
git fetch origin
git checkout claude/textual-panel-prototype-ykcbvo
git merge origin/main            # resolve installer / lang header / installer.sha256 conflicts
# set PANEL_VERSION=" 1.5.11" in installer and in the 22 lang/*.cache headers
sha256sum installer > installer.sha256   # same format as the existing file
cd panel && python3 -m pytest -q tests
cd ../broker && npm test
git push
```

Then merge PR #32 and, from Paulo's local `broker/` folder (real IDs in `wrangler.toml`):
`npm run db:migrate && npm run deploy`. After that, update the panel on the real server and
run the field test list in section 3.

---

## Working rules

- Any change to `installer` → bump `PANEL_VERSION` + 22 lang headers, regenerate
  `installer.sha256`.
- New user-facing strings → English key in installer/panel, entry in `lang/pt.cache`.
- Keep changes modular; don't rewrite whole scripts.
- Paulo writes in Portuguese or English; answer in the language of his message.
