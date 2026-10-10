# koha.nexus: Project Progress

_Last updated: 2026-10-10. Panel version on `main`: **1.5.49** (1.5.50: OPAC and Staff Appearance PR)._

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
- **Self-update reads one commit** (1.5.34): "Update this panel via GitHub" asks
  `api.github.com/repos/<repo>/commits/main` for the commit and downloads `installer` and
  `installer.sha256` from `raw.githubusercontent.com/<repo>/<sha>/`. The branch URLs are cached
  up to 5 minutes per file, so right after a merge they paired a new installer with the old hash
  and the panel showed the SHA-256 security alert. A mismatch at a pinned commit is still the
  security alert; only when the API is unreachable (branch fallback) does the panel say to try
  again in a few minutes. `tests/updater.bats` runs in the cloud (fake curl).
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
  Since 1.5.41 a second bridge, Rede Pergamum (PUCPR, site CRP), lives in the same directory as
  package `pergamum_sru` on 127.0.0.1:5006/sru, unit `koha-pergamum-sru`, `--task pergamum-bridge`
  (and automatically when z3950-add gets the 127.0.0.1:5006 row, offered unticked in the Brazil
  list). Both bridges share one venv and the SRU endpoint code (`zeus_sru.app.sru_app`).
  `pergamum_bridge_register` deletes then inserts Koha's row (z3950servers has no unique key but
  `id`, so ON DUPLICATE KEY never matches). Not yet tried against the live Pergamum site.
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
  background"...) is one line now (`widgets/marquee.py`). Text that
  fits is drawn as it is; text that does not is cut with "…", and while the card is hovered or
  focused it slides one cell every 0.15 s, resting about 1.5 s at the start and at the end. Only a
  running ticker has a timer, the window is always exactly the box width (wide characters cut by
  an edge become a space), so nothing bleeds past the border. Gotcha: a Textual widget must not
  use `self._running` (MessagePump's own flag), like `remove()` and `_task()`.

- **1.5.35 (card descriptions)**: Paulo asked for a real one-line description under every menu
  card instead of the generic hint ("Step by step, in this panel" / "Runs in the background" /
  "Opens the classic screens", now removed from the panel and pt.cache). `menus.DESCRIPTIONS`
  maps each action to an English key (like the labels), with the PT-BR text added by hand to
  `lang/pt.cache`; the other languages show the English text until gen_lang.py runs where Google
  Translate can be reached. tests/test_menus.py checks every entry has one with a PT-BR text.

- **1.5.36 (Magic Import restore)**: Paulo still saw the panel close before the restore of
  "BKP_BIBLIOTECA (2).backup". Found: `magic_is_koha_dump` always failed on a compressed backup
  (awk exits early, zcat dies of SIGPIPE, pipefail), so every real Koha backup went through the
  import engine and was copied twice before Restore database; it now runs without pipefail.
  The panel no longer exits on an error in a dialog: `KohaPanelApp._recover` closes that dialog
  (the routine gets "cancelled") and shows the error, with the traceback in
  `/var/log/koha-easy-install/new-panel.log`; errors on the main screen still end the app.
  Restore database unpacks a .tar/.tar.gz/.tgz/.zip in /var/tmp/kei-unpack.* (`restore_unpack`,
  the largest MariaDB dump inside; a pg_dump tar is refused) and its errors are titled
  "Incompatible file format" / "SQL restore error". Tested end to end here: the real panel and
  installer, mock Koha, a gzip and a tar.gz named "BKP_BIBLIOTECA (2).backup".

- **1.5.37 (OPAC depth and buttons)**: from Paulo's production "Glass & Metal" stylesheet.
  Without a wallpaper the page gets a canvas (the library's page colour, or #e8ecf2, under two
  faint accent glows; dark mode its own) and the blocks a layered shadow, so white blocks and
  glass no longer sit flat on Koha's white page (`_canvas_css`). `_buttons_css` styles every
  button kind: main ones (.btn-primary, #searchsubmit, bare submit inputs) in the accent,
  secondary ones (.btn-default/.btn-secondary/#backtotop...) on the surface; with the metal
  texture they take his brushed/silver gradients. Buttons inside news and #opacmainuserblock
  are full-width, 44px+ touch targets. Paulo then reported the blocks stayed white whatever
  accent he chose: the surface is now tinted 12% with the accent (`mix`), every block gets a
  wash of both accents (content blocks .22/.16, with an accent border) and headings use
  `--kei-ink` (the accent, darkened or lightened). No new settings: KEI-THEME-DATA unchanged. His
  site-specific bits (image URLs, link hiding, mobile results layout) were not made defaults.

- **1.5.38 (OPAC header menu, staff theme)**: from Paulo's rendered opac.html/staff.html (Koha
  26.05). OPAC: the user menu opened behind the search bar (each glass block is its own stacking
  context), so #header-region gets z-index 1030 and its menus 1060; the quick access buttons
  (#kei-links) were a 230px auto-fill grid, now one full-width button per line; .btn-acesso
  joins the full-width news buttons. Staff: `staff` has its own accent/accent2/surface (old
  settings start from the OPAC's), pickers in the Staff box. `staff_css_body` targets Koha 26's
  real markup: `nav.navbar.bg-dark` (#header is only the collapse div inside it), #header_search
  in a darker shade of the same hue (no more blue/green clash), the .biglinks-list modules as
  cards with icon tiles, #area-news as a tinted card (his .btn-acesso links included). Koha
  rules beaten by specificity; !important only against .bg-dark and his inline news styles.

- **1.5.39 (staff icons, staff pictures)**: Koha draws Pesquisa avançada / de exemplares with
  two stacked icons (.fa-stack-1x under .fa-stack-2x); in the 2.4rem tile they collided, so the
  small one is hidden and the magnifier centred. cfg["staff"] gains its own logo, favicon and
  background (same sources as the OPAC's pictures) and a film (40-95 %, default 75) over the
  wallpaper; the content boxes stay opaque. Local staff files are kei-staff-*.* in
  /usr/share/koha/intranet/htdocs/intranet-tmpl/kei-custom (served as /intranet-tmpl/kei-custom,
  the OPAC's folder is not served on the staff side); the favicon is the IntranetFavicon
  preference (allowed values: https or that folder), cleared by Remove like OpacFavicon.

- **1.5.40 (backup compression, AI model lists, reports)**: BACKUP_COMPRESSION in backup.conf
  (gz default, zst, xz; installer backup_codec / backup_set_codec, task `backup-compression`,
  Backup center Select) drives the nightly script (it reads the setting at run time and falls
  back to gzip when zstd/xz is missing), manual backups and every PRE-* safety copy; restores
  were already codec-blind (dump_codec reads the magic bytes). panel/kei_panel/aimodels.py
  reads each provider's /models with the key (aiclient.check_connection), drops non-chat
  models and splits Free / Accessible from Advanced (Gemini Pro, OpenAI non-mini/nano, Claude
  non-Haiku: a label, not a billing fact; BILLING_NOTE says so); FALLBACK lists "latest"
  aliases when the live list cannot be read. Defaults: gemini-flash-latest, gpt-5-mini,
  claude-sonnet-5-5 (aiconf and both Perl DEFAULTS). Reports pack 8 -> 22 (tests/library_tools
  L08 builds the extra Koha columns and runs each new report on a row made for it).

- **1.5.41 (Rede Pergamum SRU bridge)**: `sru-bridge/pergamum_sru` turns Koha's SRU searches
  into Pergamum's Sajax calls (ajax_resultados for the acervo ids of the first 50 hits,
  ajax_conteudo_pastas for each record's MARC text between <inicio> and <fim>) and the MARC text
  into MARCXML: bare \r line ends, \u001e and XML-invalid controls removed, entities decoded
  without unicode_escape, datafields without a subfield dropped (Koha refuses them). Koha's
  maximumRecords=0 count call fetches no records; the result list is cached 10 minutes.
  recordSchema is the full info:srw URI as in Paulo's spec (PERGAMUM_SRU_RECORD_SCHEMA=marcxml
  switches it; yaz-client 5.34 reads both).

- **1.5.42 (language menu)**: section "Koha languages" (classic option 13, panel cards) has four
  actions: download a pack only (koha-translate --install, no preference changed; a pack already
  there is skipped), download & activate (the old routine, now without its yes/no), set an
  installed language as active (no download), and list the installed packs with the active and
  enabled ones. "Active" = first in OPACLanguages and StaffInterfaceLanguages (or `language` on
  Koha before 22.11), the other enabled languages kept after it; Koha shows the first one when
  the browser asks for none of the enabled ones. Sessions are no longer deleted. The first install
  is unchanged: it downloads the pack of the server's language and the Web Installer activates it.
  `tests/languages.bats` (MariaDB only) runs in the cloud.
- **1.5.50 (OPAC and Staff Appearance)**: the "OPAC appearance" screen is now **OPAC and Staff
  Appearance** (pt: *Aparência do OPAC e STAFF*). Readability fixes from Paulo's screenshots: `.main`
  and `#opaccredits` are content panels (new slider `panel_opacity`, 80-100, default 94, blur on a
  `::before` layer), Koha's inner panels (breadcrumbs, tab panes, `#menu`/`#usermenu`, facets,
  toolbars, `#action`, `.nav_results`, tables, pagination) share one solid inner colour, edge and
  radius; text/labels/links/headings get colours checked to WCAG AA (`panel_colors`, `readable`)
  in light (#1a1a1a on near-white) and dark (#e6edf3 on #161b22/#0d1117) mode, dark alerts and
  status colours. `.main` left `_BLOCKS` (the header/search keep the glass). Staff: breadcrumb
  card, `.page-section` on the card colour, and with a dark staff surface Koha's white tables,
  forms and dialogs follow it. New boxes: OPAC login page / Staff login page (allow-listed HTML via
  `sanitize_html`, banner picture `kei-login.*` / `kei-staff-login.*`) and Footer credits (a form ->
  fixed markup). They are Koha 23.11+ HTML customizations (`additional_contents` +
  `_localizations`, code `kei-<location>`, lang `default`), not sysprefs; the library's own entries
  at the same location are set to expired and listed in `theme-retired.tsv`, given back when ours is
  turned off or on Remove. Their settings are kept out of the public CSS data line and live in
  theme-settings.json (`contents_settings`, `contents`), re-applied after a restore. Apply and
  Remove restart memcached and Plack. Not checked on a live Koha.
- **1.5.49 (staff authority links)**: the magnifying glass next to a heading on the staff record
  page opened `opac-authoritiesdetail.pl` (404 on the staff port). Koha's staff stylesheet
  (25.05 to 26.05) links to `authorities/detail.pl`; only the OPAC one makes that link, so the staff
  page was being drawn by an OPAC stylesheet. `staff_authlinks_fix` (after install, Koha update,
  restore, and at the start of Sync & link authorities): any of `XSLTDetailsDisplay`,
  `XSLTResultsDisplay`, `XSLTListsDisplay` whose file (or a file it imports) links to the OPAC page
  goes back to `default` (the catalogue card files are written again instead when the preference is
  the card's), then a jQuery rewrite is appended to `IntranetUserJS` when the text there does not
  mention `opac-authoritiesdetail.pl` yet, written through `C4::Context->set_preference` by
  `koha-shell -c "perl -"` (script from a quoted heredoc), then memcached and Plack restart, only
  when something changed. Log: `tools/staff-authority-links-*.log`. Not run on a live Koha.
- **1.5.48 (Sync & link authorities: simulation or apply, linker choice)**: the old flow always
  ran `link_bibs_to_authorities.pl --test` first and decided on its "Number of bibs modified",
  which Koha only counts outside `--test`, so it always said "nothing to change". Now the menu
  asks for the linker (Default, FirstMatch, LastMatch) and the mode: **Simulation**
  (`--test -v --link-report`; records that would change counted from the `-v` lines
  "Bib N (...): K headings changed"; can go straight on to apply) or **Apply permanently**
  (PRE-AUTHORITIES backup, run without `--test`, then `koha-rebuild-zebra -v -b` or
  `koha-elasticsearch --rebuild -b` in the background, log `authority-sync-*-reindex.log`).
  Koha's script has no `--linker` option (GetOptions would refuse it) and no Fuzzy module, so the
  linker goes to that run only as `OVERRIDE_SYSPREF_LinkerModule=<X>` (read by
  `C4::Context->preference` before the database); the saved preference is untouched.
  `koha_exec` takes `KOHA_EXEC_OUT`: stdout to that file (`authority-sync-*-simulation.txt` /
  `-applied.txt`, parsed), stderr (per-record warnings) to the tool log. Tests:
  `tests/authority_sync.bats` (double in `tests/mocks/koha-script`), not run on a live Koha.
- **1.5.47 (Find duplicate authors, Library tools > 18, panel action `authority-match`)**: the
  personal names of the authority file (100 $a/$q/$d) are compared by the Magic Import engine,
  new module `kei_import/authorities.py` (`kei_import_run.py authorities --in TSV|MARCXML --work DIR
  [--uses FILE] [--threshold 0.85]`, exit 3 = nothing alike). Names are compared word by word in
  direct order (inverted and direct forms line up; particles dropped; surname split reuses the
  rules of `rules.py`); a word matches by the mean of Jaro-Winkler and Levenshtein, by its sound in
  Portuguese/Spanish (`sound()`: Souza/Sousa, Luiz/Luís, Thereza/Teresa, Mattos/Matos) or by its
  initial; masculine/feminine of one name (Mário/Maria), other dates or another agnomen (Filho,
  Neto, Júnior) never match, and two forms below 0.75 never end up in one group through a third
  (`Silva, J.` is flagged "also like"). Blocking by the sound and the first 4 letters of the last
  surname (5,000 names in 20 surnames: about 7 s). The form kept by default is the most complete
  (whole words, dates, inverted, accents, not capitals), then the most used ($9 counts from
  biblio_metadata, tags below 900 so not 952), then the oldest authid. Nothing is merged on a
  guess: each group is a menu (pick the form to keep, "not the same person", or "suggested form
  for every group left"); then a confirmation, a verified PRE-AUTHORITIES backup, and a Perl script
  run through koha-shell does what the staff interface's Merge does: the variant's $a added as a
  400 to the record kept, `C4::AuthoritiesMarc::merge` (override_limit) and `DelAuthority
  (skip_merge)`; one failed pair does not stop the others. Not tried on a live Koha yet.
  `tests/authority_match.bats` (MariaDB + perl MARC::File::XML; doubles C4/AuthoritiesMarc.pm and
  Koha/Authorities.pm in tests/mocks/perl5) and pytest cases in `panel/tests/test_magic_engine.py`;
  sample data `tests/data/authorities_sample.xml`. pt and es translations added by hand.
- **1.5.46 (staff material, AI chat input, Ollama memory, local-model tool calls)**:
  - Staff interface: `cfg["staff"]` gets the OPAC's material (`texture`, `blur`, `opacity`,
    `radius_block`, `radius_input`, `radius_button`, `STAFF_MATERIAL`, same `RANGES`) and an optional
    `page` colour. Settings saved before default to `flat` with the old 12px blocks, so their look does
    not change. `_staff_material_css` puts the texture on `.page-section, #area-news, fieldset.rows`
    (cards: module tiles and news items); frosted glass blurs a `::before` layer, never the block, so
    Koha's `position: fixed` modals are not trapped; metal also brushes the top bar and buttons; glass
    without a staff wallpaper gets the OPAC's accent-glow canvas. "Copy OPAC preset" (staff box) =
    `copy_opac_to_staff()`: material, colours, page colour and https pictures (OPAC files on this
    server are skipped, the staff side does not serve /images/custom); the staff's text size,
    contrast and density are kept. Nothing reaches Koha before Apply.
  - AI assistant input: auto-grow measured from scratch (height auto, then scrollHeight) whatever box
    model a theme gives textareas; three lines to start, max `min(176px, 33vh)` (wide view
    `min(240px, 30vh)`), then an inner scrollbar; shrinks when text is deleted and after sending; a
    click no longer pins the grown height (only a grip drag sets the start height). Before: up to half
    the window (450px at 900px) plus a 60vh log.
  - Ollama memory: "Connected: N models" counted the downloaded models (/api/tags), not the loaded
    ones. Now the assistant (`ollama_unload_others` in KohaEasy::Assistant::chat) and MARC Replace
    (KohaEasy::Cataloguing::Vision::extract) unload every other model (`keep_alive: 0`) before each
    request, and Ollama loads the asked one on demand. Panel: the Ollama box shows installed and in
    memory (/api/ps), Save unloads models not in the fields, "Free memory" unloads all
    (`aiclient.ollama_loaded/ollama_unload/ollama_keep_only`).
  - Tool calls of local models: `normalize_envelope` reads Llama 3 `{"name","parameters"}`, Qwen
    `<tool_call>` with string arguments, OpenAI `tool_calls`/`function`, ReAct `action_input`, a nested
    `{"tool":{...}}`, arguments next to the name, `functions.` prefixes and `search_catalog`. A first
    reply that only announces a search ("Vou usar o termo 'Bandeira'...", `$ANNOUNCE`) or names
    records before any tool ran gets one reminder, then the catalogue is searched with the quoted
    words (else the question's); any other plain answer is kept. The prompt has a worked example and
    forbids announcing. Not tried against a live Koha or a real local model.

- **1.5.45 (reader alerts and daily digest)**: `panel/kei_panel/notify.py` (standard library only)
  sends due-date reminders and overdue alerts to readers (one message per reader, by e-mail and/or
  WhatsApp/Telegram through `KohaEasy::Messaging`) and a daily summary to the library (loans plus
  `config.sh --status-json`). Each alert is off until switched on in Messaging > Alerts (new hub
  tab, `/etc/koha-easy-install/notifications.conf`); its dry run shows what would go out today.
  Runs from Schedules & cron tasks: preset `notify`, daily at 07:00, off; the Alerts tab's Save
  switches it on; `cron-apply` writes `/usr/local/bin/koha-kei-notify` (panel venv Python, else
  python3). Koha is only read (koha-mysql); e-mail goes through Koha's default SMTP server
  (`smtp_servers`, else localhost:25, as Koha does) from KohaAdminEmailAddress and only when
  Koha's e-mail is on. What was sent: `/var/lib/koha/<instance>/kei-notify/sent.tsv` (written after
  each message, under a lock), so repeated runs never send twice on the same day; due keys carry the
  due date (a renewal brings a new reminder); overdue repeats every N days (0: once), loans overdue
  over 90 days only in the summary. Log: `/var/log/koha-easy-install/notify.log`. Not tried live.

- **1.5.44 (last-backup indicator, pre-restore safety backup)**: one source of truth for "the
  newest backup", `latest_sql_backup` (EPOCH MTIME SIZE PATH): top-level, non-empty `*.sql.{gz,zst,xz}`
  in $DIR_SQL, dated by the timestamp in the name (`backup_name_epoch`: `_23h00`, `_14h0733`,
  `_14h07m33`, `20261002-0300`), else the mtime, so a copied-back old backup no longer looks new;
  a manual backup saved elsewhere counts while its file exists (`/var/lib/koha-easy-install/last-manual-backup`).
  The dashboard, Backup center, Download latest backup, Test the latest backup, the validation report
  and the detailed status all read it (before, four separate `find`s disagreed on depth and order).
  Nightly script and `create_safety_backup` write `FILE.part` and rename once verified (a dump in
  progress was the "newest"); an old nightly script is rewritten by `--task info`. Status JSON adds
  `backup.last_kind` (nightly|safety|manual|other|none). The Last backup card shows the date and time,
  "N h ago · file", green under two days unless the last nightly run failed; "None yet" when empty.
  Restore's safety copy is now `pre_restore_safety_backup_<YYYY-MM-DD_HHhMMmSS>.sql.<codec>` (codec
  from Backup center); older `PRE-RESTORE_*` copies are still found by require_koha_tables. A failed
  safety copy still aborts before the live database is touched, now logged.

- **1.5.43 (OPAC and staff quick access buttons)**: each quick access button has a `sort_order`
  (settings saved before it get 1..n as listed, so nothing moves) and the buttons are shown by it;
  a layout per set (`list` or `grid2`: two columns, icon over text below 576px, one column below
  340px); a `metal` style next to solid, gradient and glass (silver gradient with a fine grain,
  bevel, a specular band sweeping across on hover, gunmetal in the OPAC's dark mode; glass stays
  the default). `cfg["staff_links"]` puts the same buttons on the staff home page (above the
  module tiles of mainpage.pl) through a marked block in IntranetUserJS (staff.js) and its CSS in
  IntranetUserCSS, in the staff colours whether or not the staff colour theme is on. "Sync current
  OPAC settings" (replaces Reload) runs `--task opac-theme-sync`: the settings line of OpacUserCSS,
  else theme-settings.json, else the config of our scripts; which of our blocks are present, the
  library's own lines, and [kei-button] markers in OpacMainUserBlock (additional_contents), which
  turn the news buttons on. Nothing is written until Apply.

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
