# koha.nexus: Project Progress

_Last updated: 2026-10-09. Panel version on `main`: **1.5.32** (1.5.33: card hint ticker PR)._

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
| Windows installer | `windows/` | PowerShell + C# launcher | Installs Debian on WSL2 and Koha inside it. Install root `C:\Koha` (old `C:\KohaEasy` kept). |
| Catalog Network | `catalog-network/` | Python (FastAPI + SQLite FTS5) | The shared catalogue on the project's Oracle VPS: SRU 1.1/1.2 for Koha, `POST /api/records/sync` (bearer tokens), systemd unit `koha-nexus-catalog` on 127.0.0.1:8088 behind the Cloudflare Tunnel. |
| Free-address broker | `broker/` | Cloudflare Worker (TypeScript), D1, Queues | Gives each library `<name>.koha.nexus` and `<name>-admin.koha.nexus` through Cloudflare Tunnels. Live at `https://broker.koha.nexus`. |
| AI assistant (Module 2) | installed by installer section 38 | Perl (`tools/ai_assistant.pl`, `KohaEasy::Assistant`) + JS/CSS via `IntranetUserJS` | Chat on the Koha **web** staff home page, replacing the news block. |
| AI cataloguing / MARC replace | installer + `marc_replace.pl` + `panel/kei_panel/marcreplace.py` | Perl + JS | AI-generated MARC record preview, add as new or replace an existing biblio. |
| Tests | `tests/*.bats`, `panel/tests` | bats, pytest | Most bats suites need a real Koha; `tests/ai_assistant.bats`, `tests/z3950.bats` and `tests/opac_theme.bats` (MariaDB only) run in the cloud. Panel: `cd panel && python3 -m pytest -q tests`. |

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
  Since 1.5.21 the Brazil list is the local Zeus SRU bridge (`sru-bridge/`, 127.0.0.1:5000/sru,
  ticked when the screen opens via `"preselect": true`) plus UFSC, UTFPR and UNIFESP on port 210;
  Biblioteca Nacional and UNESP (Alma) were dropped as permanently dead. A target's `sru_fields`
  and `sru_options` go to Koha through the 12th and 13th columns of the z3950-add file.
  Since 1.5.26 the bridge is installed by the installer (`--task sru-bridge`, and automatically when
  z3950-add gets the Zeus row): `/usr/local/lib/koha-easy-installer/sru-bridge` with its own venv,
  systemd unit `koha-zeus-sru` (enabled at boot, Restart=always, DynamicUser).
  Since 1.5.27 (from Paulo's live tests): the bridge queries `catalogo.bu.ufsc.br/zeus/` with only
  `targets[0]` (BU/UFSC; the other targets hang) and reads the MARCXML Zeus embeds; Koha's row is
  syntax MARC21 (USMARC shows 0 results), `sru=get,sru_version=1.1`, timeout 15, written by
  `sru_bridge_register`, which also unticks `z3950.ufsc.br` (dropped from the curated list).
  Since 1.5.22 a server is working once it answers the protocol (Z39.50 Init accepted, or any SRU
  response), even with 0 hits, a slow search or a refused Present; BER indefinite lengths are read.
  `History` resets automatic hides when `HISTORY_RULES` changes. Confirmed dead and left out:
  raw IPs (Biblioteca Nacional), `*.alma.exlibrisgroup.com` (UNESP, BNE, CSIC), Portugal's BN
  and `z3950.loc.gov:7090` (use `lx2.loc.gov:210/LCDB`). LIBRIS is MARC-8.
  Since 1.5.25 no login is in the repository (GitGuardian flagged BnF's public one): a curated
  target names `"login_env": "KEI_Z3950_X"` and `credentials.py` reads `KEI_Z3950_X_USER` /
  `_PASSWORD` from the environment or `/etc/koha-easy-install/.env` (`KEI_ENV_FILE`; see
  `.env.example`; `.env` is git-ignored). Such a login is not copied into `z3950-targets.json`.
- **OPAC appearance** (1.5.16, Subject 4): panel screen `views/opac.py` over `opac_theme.py`
  (textures, radius sliders in `widgets/slider.py`, wallpaper with a legibility film, logo,
  favicon via `OpacFavicon`, a 🌓 switch saved in `localStorage` key `kei_theme`, clean-up
  rules, `[kei-button ...]` markers in news, the New arrivals carousel). It writes one marked
  block into `OpacUserCSS` (first line `/* KEI-THEME-DATA: {...} */`, read back to fill the
  screen) and one into `OpacUserJS`; the rest of both preferences is kept. Koha's side is
  installer section 40: `--task opac-theme-get | opac-theme-apply DIR | opac-theme-remove |
  opac-carousel-refresh`, backup first, under the backup lock. Pictures go to
  `/usr/share/koha/opac/htdocs/images/custom/kei-*`, ImgBB (API key) or Cloudinary (unsigned
  preset); the keys stay in `/etc/koha-easy-install/opac-theme.conf` (0600), never in the
  public CSS. The carousel reads `images/custom/kei-new-arrivals.json`, written nightly by
  `/usr/local/bin/koha-kei-new-arrivals` (cron `/etc/cron.d/koha_kei_opac`): newest titles
  with a copy that is not lost or withdrawn and a real Amazon cover (the 43-byte "no cover"
  GIF is skipped). Not yet tried on a live OPAC.
- **Administration hub** (1.5.17, Subject 5), installer section 41:
  - *Messaging & interoperability* (`views/hub.py`, key `m`): tabs E-mail, WhatsApp &
    Telegram, SMS, SIP2, Z39.50 over `--task hub-status` (no SMTP passwords). Buttons run the
    `email`, `messaging` and `interoperability` routines (their entries moved into this
    section); links open the exact staff page (`smtp_servers.pl`, `?op=add_form`,
    `KohaAdminEmailAddress`, `letter.pl`, `overduerules.pl`, `SMSSendDriver`,
    `memberentry.pl`, `z3950servers.pl`) from `staffClientBaseURL`, else `http://IP:8080`.
    Gmail cheat sheet (smtp.gmail.com, 587, STARTTLS, app password).
  - *SIP2 wizard*: `sip.py` reads and writes `SIPconfig.xml` (RAW listener 127.0.0.1 or
    0.0.0.0, the login, its institution policy; Koha's example logins with public passwords
    removed by default; comments and other listeners kept). `--task sip-apply FILE PORT
    PUBLIC` checks the XML, keeps `SIPconfig.xml.kei-DATE` (0600), opens the port when public
    and restarts `koha-sip`.
  - *Schedules & cron tasks* (`views/crons.py` over `cron.py`, key `s`): switches, frequency,
    day and time per job of `/etc/cron.d/koha_tasks`; presets for backups, a full index
    rebuild (`/usr/local/bin/koha-kei-reindex`, Zebra or Elasticsearch at run time), fines,
    authority linking (daily/weekly), sessions, Plack, journal, mysqlcheck. A job switched
    off stays in the file as `#off# ...`; hand-written lines and `# BEGIN/# END` blocks are
    kept. `--task cron-apply FILE` validates every line and keeps `koha_tasks.bak`. No nano.
  - *Cloud backup, other services* (`cloud.py`, `screens/oauth.py`): OneDrive, MEGA, S3
    (AWS, R2, Wasabi, MinIO) without the rclone CLI. OneDrive runs `rclone authorize
    onedrive --auth-no-open-browser` on the server, follows its first redirect to get
    Microsoft's own sign-in URL (📋 Copy link works from any computer), and the person pastes
    back the `http://localhost:53682/?code=...` address, which the panel replays to rclone on
    127.0.0.1 (or pastes a token). `--task cloud-provider FILE` (0600 TSV, deleted at once)
    runs `rclone config create ... --obscure`; S3 gets `NAME-s3` plus an alias `NAME` →
    `NAME-s3:bucket`. Google Drive flows untouched. None of this tried on a live Koha yet.
  - *Cloud set-up test* (1.5.23, every service): `validate_and_register_rclone` no longer runs the
    full backup in the foreground. Each rclone call goes through `rclone_probe` (`timeout 30s` plus
    `--contimeout 15s --timeout 20s --retries 1 --low-level-retries 1`): mkdir, then a small
    `kei-upload-test.txt` sent, listed back and deleted. Only then is `RCLONE_REMOTE` saved and the
    first full backup started in the background. A failure or timeout shows rclone's own output;
    the panel and the classic menu offer *Try the test again* / *Edit the token* / *Back*. The
    pasted Google Drive token goes through `rclone_token_clean` (control characters, BOM, outer
    quotes, typographic quotes and PowerShell `\"` removed, JSON re-written compact) and is read
    back from rclone.conf. Tests: `tests/cloud_test.bats` (stand-in rclone; the real one when present).
- **WireGuard VPN** (1.5.18, Subject 6): panel screen `views/vpn.py` (key `v`) over `vpn.py`
  and `screens/vpn.py`; installer section 42, `--task vpn-status | vpn-setup ENDPOINT PORT |
  vpn-peer-add NAME | vpn-peer-revoke NAME | vpn-stop`. Server 10.66.0.1/24 on wg0, UDP port
  51820 by default, `wg-quick@wg0`, `net.ipv4.ip_forward` in `/etc/sysctl.d/99-kei-wireguard.conf`,
  iptables FORWARD + MASQUERADE in PostUp/PostDown, UFW: the UDP port plus 8080 and the SSH port
  on wg0. Keys: `/etc/wireguard/kei-server.key`; each device is `kei-peers/NAME.peer` (server
  block, PSK) + `NAME.conf` (its profile, 0600); wg0.conf is rebuilt from them and applied with
  `wg syncconf`. Profiles are split tunnel only (`AllowedIPs = 10.66.0.0/24`, MTU 1360,
  PersistentKeepalive 25, no DNS line); the panel refuses to show one that is not
  (`vpn.profile_problem`). QR via `qrencode -t ansiutf8` (comments stripped to keep it small),
  Copy profile via OSC 52. WSL needs mirrored networking (`host_can lan_direct`). Not yet tried
  on a live server.
- **AI providers**: Ollama (default `http://127.0.0.1:11434`, always send `num_ctx`, 16384),
  OpenAI, Anthropic, Google Gemini. Active key in `vision.conf` (owned by the Koha instance
  user, else the web says "provider not configured"); all keys in `ai-keys.conf` (0600).
  Saved keys are never shown back, only the last 4 characters.
  Since 1.5.24 the panel's 🤖 AI screen has both tools on one page (no tabs), an Ollama box
  that downloads models with only Ollama answering, CPU-friendly presets (`llama3.2:1b/3b`,
  `qwen2.5:1.5b/3b`, `qwen2.5vl:7b` marked High CPU / Slow on ARM) and a separate
  `chat_model` in `vision.conf` for the assistant (empty = `model`, the vision one;
  `KohaEasy::Assistant::load_conf` uses it, the web AI settings form keeps it).
- **Free addresses**: Paulo bought the `koha.nexus` domain; broker deployed by Paulo on the
  **Cloudflare Workers Free plan** (so `PBKDF2_ITERATIONS=20000`). One broker per Cloudflare
  account. His local `wrangler.toml` holds real IDs; the repo keeps placeholders. The Worker
  he deploys is `kei-broker`; a stray Cloudflare auto-deploy for a Worker named `koha-nexus`
  shows a red check on PRs and can be disconnected in Cloudflare.
- **Website** (`index.html`, served at https://koha.nexus by GitHub Pages; 1.5.19, Subject 7):
  23 languages in one `translations` object, missing keys fall back to English. A "Panel"
  showcase (`#panel`) shows real screenshots of the panel's demo mode in
  `docs/images/panel/*.webp` (Textual `save_screenshot` SVG, rasterised with Playwright, WebP
  via Pillow). The motion script is a second `<script>` block; it never touches
  `loadLibraries()` (the `broker.koha.nexus/api/public-libraries` fetch into `#libraries-grid`)
  nor `broker/`. New site strings are translated into pt/es/fr/it/de only.
- **Emoji widths** (1.5.20): a symbol Textual counts one cell wide followed by U+FE0F (⬇️, 🛡️,
  🎛️, ⚠️) is drawn two cells wide by Windows Terminal, which slides the rest of that terminal row
  (boxes, highlights, scroll bars, even a dialog over it). `glyphs.steady()` (run by `t()`) drops
  the selector after such symbols; menu icons use emoji that are two cells everywhere (📊, 🔐, 📥).
  Hindi and Bengali names in the language list are written in Latin letters for the same reason.
- **Dormant menu entries**: `Entry(hidden=True)` keeps a routine but draws no card (cataloguing
  aids, CDD lookup, Cutter Calculator, hidden at Paulo's request on 2026-10-08).
- **Links from the panel** open through `panel/kei_panel/opener.py` (wslview/explorer.exe on
  WSL, xdg-open as SUDO_USER on a desktop, else copy via OSC 52). Never Python `webbrowser`.
- **Windows**: new installs go to `C:\Koha`; scheduled tasks live in the Task Scheduler root as
  "Koha - <task> (<USERNAME>)". The only install path is the PowerShell one-liner
  `irm .../windows/install.ps1 | iex`, documented as "open PowerShell **as Administrator**" from
  the person's own administrator account (Paulo, 2026-10-08); the docs warn not to approve with
  another person's password. `Install-Koha.cmd` was removed in 1.5.31 (Paulo, 2026-10-09): do not
  bring back a .cmd or batch installer. `Uninstall-Koha.cmd` (the uninstaller in `C:\Koha`) stays. Use `Get-KohaPath`, not
  literal paths.
- **Naming**: product name koha.nexus everywhere visible; internal ids/paths such as
  `koha-easy-installer` and `/etc/koha-easy-install` are intentionally kept.
  Since 1.5.28 the Windows launcher is `koha.nexus.exe`, banners say KOHA.NEXUS, and the
  installer adds `/etc/koha-nexus`, `/usr/local/lib/koha-nexus` and `/usr/local/bin/koha-nexus`
  as links to the old paths (uninstall removes them).
- **1.5.28 (koha.nexus rebrand PR)**: the panel lock (`/var/run/koha_panel.lock`) is taken
  over when its holder is gone or lost its terminal (SSH drop); 🔒 Security & access hub
  (WireGuard, Cloudflare Tunnel, UFW, staff firewall, SSL, Fail2ban...) replaces the sidebar
  VPN/publish items; Magic Import sits right under Backups; dumps may be `.sql.bz2/.xz/.zst`
  (zstd added to the dependencies); cloud servers show the public IP next to the private one;
  OPAC look has a 2D/3D carousel, block colours (`--nexus-*`), quick access buttons and an
  optional staff theme (IntranetUserCSS); each apply saves `theme-settings.json` in CONF_DIR
  and Restore database writes it back (`theme_state_reapply`).
- **1.5.29 (panel lock fix)**: a panel's bash runs its TERM trap only after the Textual panel
  it waits for ends, so `kill PID` left it running and the lock loop went on (Paulo,
  2026-10-09). `panel_lock_end` ends the whole tree (TERM, 3 s, KILL); `sudo config.sh --unlock`
  and the "close it and open here? [s/N]" question use it. A running backup is named instead of
  a dead PID. The lock file is removed on exit; `panel_lock_open` re-opens it if the path changed.

- **1.5.30 (Z39.50 screen + Catalog Network)**: the Z39.50 / SRU servers screen has three
  boxes. Top: this Koha's Z39.50/SRU server (`koha-z3950-responder`) with an on/off switch
  (`--task z3950-daemon on|off`: firewall port opened/closed, off also at boot; its
  `/etc/koha/sites/<instance>/z3950` settings are kept aside as `z3950.kei-off` in case
  `--disable` drops them). Middle: the "Rede koha.nexus (Catalogação Compartilhada)" switch
  (`--task catalog-network on URL|off`: an SRU row, host `https://HOST`, port 443, db `sru`,
  MARC21, utf8). Both read `--task z3950-server-status`. Bottom: the outbound list as before.
  The hub's Z39.50 tab only shows the state and links here (its "Enable SIP2 and Z39.50"
  buttons are gone; the classic routine stays as a hidden entry). The network's address is
  `KEI_CATALOG_NETWORK_URL` (environment or `.env`), default `https://catalog.koha.nexus/sru`:
  **a placeholder until the tunnel hostname is chosen**. The service itself is
  `catalog-network/` (see its README for the VPS install, the cloudflared rule and the SQL).

- **1.5.31 (PowerShell-only Windows install)**: `windows/Install-Koha.cmd` is gone. The READMEs
  and `index.html` show only `irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex`
  (without the old `Tls12` prefix, as Paulo wrote it), and the site's download button is now a
  code box with a Copy button, translated into all 22 languages.

- **1.5.32 (Magic Import file checks)**: Paulo's "BKP_BIBLIOTECA (2).backup" report. The file
  picker takes any file when the routine asks for any (`.backup`, `.bkp`, `.dump`, `.tar`...),
  and a typed, pasted or dropped path is cleaned the same way (`transfer.dropped_path`: quotes,
  `& '...'` from PowerShell, `C:\...`, `C:/...`, `file://`, `\\wsl.localhost\...`, backslash
  escapes, `~`). Dialog titles, options and the loader status are plain text now (`markup=False`,
  `Content(...)`): a `[/path]` in a text used to raise Rich's MarkupError and close the panel.
  Before copying anything, `magic_preflight` says each step under Pac-Man (checking, testing the
  compression, reading the format), and `dump_kind` reads the kind from the content: a pg_dump
  custom or tar backup stops with a plain "Koha's database is MariaDB" message; a plain-SQL
  PostgreSQL dump still goes to the engine (the ISIS reader). Restore database refuses
  PostgreSQL backups, tar/zip archives and SQLite files in `check_dump_file`, and its pickers
  also list `.backup`, `.bkp` and `.dump` (the content decides). An engine exception is one
  readable line (exit 4), with the traceback in the log.

- **1.5.33 (card hint ticker)**: the grey hint line under each action card ("Runs in the
  background", "Passo a passo, neste painel"...) is one line now (`widgets/marquee.py`). Text that
  fits is drawn as it is; text that does not is cut with "…", and while the card is hovered or
  focused it slides one cell every 0.15 s, resting about 1.5 s at the start and at the end. Only a
  running ticker has a timer, the window is always exactly the box width (wide characters cut by
  an edge become a space), so nothing bleeds past the border. Gotcha: a Textual widget must not
  use `self._running` (MessagePump's own flag), like `remove()` and `_task()`.

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
