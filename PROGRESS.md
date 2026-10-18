# koha.nexus: Project Progress

_Last updated: 2026-10-17. Panel version on `main`: **1.5.66** (1.5.67: BN authority target seeded, PR)._

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
  `pergamum_bridge_register` upserts Koha's row through `z3950_upsert_sql` (z3950servers has no
  unique key but `id`, so ON DUPLICATE KEY never matches). Not yet tried against the live Pergamum site.
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
- **1.5.59 (SRU gateway: 72 catalogues in four groups at sru.koha.nexus)**: Paulo's list of 2026-10-15.
  `sru-bridge/sru_gateway/targets.json` has 72 ids in his order, each with a `group` (`national`,
  `br_universities`, `intl_universities`, `specialized`; `targets.GROUPS` has his Portuguese names);
  21 old ids renamed (uw_madison→wisconsin, pergamum→all, ...: `koha_sql.RENAMED`), umich, manchester
  and kcl dropped (not in his list), new ids without a known address are kind `missing`.
  `python -m sru_gateway.koha_sql --write` generates `deploy/koha-z3950servers.sql` (Koha's rows:
  https://sru.koha.nexus, 443, sru/<id>, MARC21, utf8; moves rows from 137.131.205.31/10.0.0.60,
  follows renames, removes retired ids, keeps checked/rank, re-runnable) and the panel's curated list
  (`panel/kei_panel/data/z3950_targets.json`, now only gateway rows). Panel Z39.50 screen: the four
  groups as `[1]`..`[4]` headings (`z3950.REGIONS`, translated in pt/es/fr/it/de). `z3950-add` writes
  `https://` before the host of an SRU row on port 443 (Koha speaks HTTPS only then). Syntax stays
  MARC21 and encoding utf8 although Paulo wrote USMARC/utf-8 (PR #62: USMARC shows no record).
- **1.5.58 (Paulo's four Windows fixes)**: (1) the panel's bottom bar shows Dashboard and **Open the
  terminal** (key `c`, also a General tools card `terminal` in `PANEL_ONLY`: `runuser -l <real_user>`
  in the same window via `bridge.run_command_interactive`, "Type exit..." printed first); `b` still
  opens the Backup center but is no longer in the bar. Tray: Open the terminal (`KohaEasy.ps1 Terminal`)
  next to Open User Folder. (2) The WinForms Koha status window (`KohaEasy.Window.ps1`) is removed:
  Launch (the Koha icon) and Window (old shortcuts) open the panel; "Koha - Status" shortcut and the
  tray's "Service status" are gone; install.ps1 deletes the old file and ends a still running
  `bin\python` pythonw; Restart-KohaTray ends an open old window; tray checks every 60 s again.
  (3) Drag and drop: the elevated installer started the tray elevated, so every panel window it opened
  was elevated and Windows (UIPI) refused drops from Explorer. Start-KohaTray now starts it through
  Explorer (`bin\koha-tray.lnk`) when elevated, direct start as fallback. Drop/pick texts name
  .sql, .sql.gz, .sql.xz, .sql.zst (the checks already read the codec from the content). (4) Open link:
  WSL uses explorer.exe (absolute path; wslview only without it), started in C:\Windows after
  `opener._interop_ready()` re-registers a lost WSLInterop binfmt handler (systemd), and the address
  is copied too. Not tried on a real PC.
- **1.5.60 (Paulo: dropped backups, Open Debian terminal)**: a file dropped on the panel's main
  screen did nothing: Windows Terminal pastes the path, and only PathPickerScreen read pastes.
  `MainScreen.on_paste` sends anything `transfer.looks_like_path` accepts to `app.drop_file`: a backup
  (.sql, .sql.gz, .sql.xz, .sql.zst, .sql.bz2) opens `backup.restore(app, file=path)`; another file,
  a missing one, an unreadable one or one on the SSH client gets a message, never silence.
  check_dump_file names a missing xz/bzip2 program instead of calling the file corrupt. "Open the
  terminal" is now **Open Debian terminal** (tray item always clickable; panel footer `c` and the
  General tools card): under WSL the panel opens its own window through powershell.exe
  -EncodedCommand: `wt.exe -w new ... wsl.exe -d <WSL_DISTRO_NAME> --cd ~ -- koha-window --shell`,
  else `wsl.exe -d <distro>`; elsewhere the in-window shell. Not `wt -p "Debian"`: the distro is
  `koha`, so a "Debian" profile may not exist.
- **1.5.61 (Paulo: restore screen drops, Open file manager)**: a terminal hands over a dropped file
  as a bracketed paste or as plain keystrokes (classic console, some Windows Terminal versions);
  keystrokes go to the focused widget, and PathPickerScreen focused the folder tree, which swallowed
  them. In file mode the path box (PathInput) now has the focus; it times printable keys: a burst
  (keys <= 25 ms apart, >= 6 of them) that reads as a path when it ends (120 ms idle) is undone and
  handed to `dropped()`, Enter right after a burst takes the drop; typing by hand is untouched.
  `📂 Open file manager` (WSL or a Linux desktop only) opens the tree's folder via
  `opener.open_user_folder` in a thread worker, ignoring clicks within 2 s.
  `panel/tests/test_picker_drops.py`.
- **1.5.63 (Paulo: carousel from a Koha list)**: the nightly job `koha-kei-new-arrivals` also writes
  `/images/custom/kei-list-<shelfnumber>.json` for every public list (`virtualshelves.public = 1`, or
  `category = 2` before 21.05; max 50 lists, in the list's `sortfield` order; a list made private loses
  its file). Covers for both feeds: Koha's uploaded one (`cover_images`/`biblioimages`, only with
  `OPACLocalCoverImages` = 1) as `/cgi-bin/koha/opac-image.pl?thumbnail=1&biblionumber=N`, else
  OpenLibrary (`?default=false`, 404 when missing), else Amazon. Server-side, not the REST API: Koha's
  public list API differs by version and the OPAC page has no ISBN/availability. Carousel settings
  `source` (new|list), `shelf`, `lists` (keep the job with the home carousel off). OPAC script:
  `KEI.listCarousel(shelfId, selectorOrElement, {title, mode, count, ...})` returns a Promise of the
  element; `<div data-kei-list="7" data-title=".." data-mode="coverflow">` mounts one from news/HTML
  customizations. CSS selector is now `.kei-carousel` (home one keeps `#kei-carousel`).
- **1.5.62 (Paulo: staff washed-out look, empty OPAC Normal view)**: the staff wrappers (`#container-main`,
  `.main`, `main`, `.container-fluid`, `#sub-header`, `#sidebar-container`, the rows and columns
  between them) are `background-color: transparent !important`; the old wallpaper rule painted `.main`
  (the whole content area) with the solid card colour. Over a staff wallpaper the cards (`.page-section`,
  `.sidebar_menu`, `.dataTables_wrapper`, `fieldset.rows`, `form .action`) take the staff surface at the
  opacity slider, one layer only (nested ones and their tables clear). STAFF_FILM is now the OPAC's
  0-90 range, staff default 55 (was 40-95, default 75: a 75 % page-colour film was the whitish wash).
  Catalogue card: Koha has no fallback for a custom XSLT path, so a missing `{langcode}` file empties the
  Normal view silently (C4::XSLT returns undef). `ficha_refresh` now also runs when the preferences point
  at kei-xslt without a state file (restore from another server), after a language pack and in
  `staff_authlinks_fix` (install, update, restore); files are written as `.part` then moved; when they
  cannot be written the preferences go back to `default`. tests BR13b.
- **1.5.65 (Paulo: configurable staff content card backdrop)**: Staff interface gets `card`
  (`sections` default, as before / `page`: Koha's `.main`, content plus sidebar, is the one card) and
  `card_padding` (0-40 px, default 16 = Koha's 1rem). Its transparency is the staff Opacity slider and its
  corners the Blocks slider, so no second opacity. In `page` mode `.main` leaves the transparent-wrapper
  list and joins the textured/wallpaper blocks; `.page-section`, `fieldset.rows`, `.sidebar_menu`,
  `.dataTables_wrapper`, `form .action`, `.tab-content` inside it go clear by specificity
  (`_staff_inner_css`), never a card inside a card. Frosted: `.main` drops `isolation` (body becomes the
  stacking context), otherwise Koha's modals inside `.main` sit under Bootstrap's backdrop. Paulo's pasted
  rule was not copied as is: its `!important`s fight the transparent wrapper rule and the textures,
  `#intranetmainuserblock` is already a `.page-section` on the home page (no `.main` there) and
  `.main-content` is not in Koha's staff templates.
- **1.5.71 (Paulo: enrichment step 5, worker and job flow)**: `enrichment/nexus_jobs` (jobs.db, worker,
  report, Apply/Revert bookkeeping). Tasks `enrich-job-add SCOPE` (export_records.pl xml, no items, throttled),
  `enrich-jobs`, `enrich-job-show/diff`, `enrich-job-apply` (PRE-ENRICH backup, ≤500 per Koha batch:
  stage_file.pl --match NEXUSBIB [local-number = 999$c] --no-create --item-action ignore, wrong matches set to
  error, commit_file.pl, index-queue wait; 005 changed since report = left out), `enrich-job-revert [--all]`
  (commit_file.pl --revert, records edited after Apply kept by marking them reverted), `enrich-job-cancel`,
  `enrich-pause`. Unit `koha-nexus-enrich` (CPUQuota 25%, MemoryMax 256M, PrivateNetwork, no Koha access).
  Report: jobs/ID/report.html/.json/.tsv with M0/M1/W/R and before/after diffs. Tests: enrichment/tests/test_jobs.py,
  tests/enrichment_jobs.bats (Koha stand-in tests/data/koha_import_mock.py). Not run on a real Koha yet; no panel
  screen yet (tasks only); pointer-only matches not fetched.
- **1.5.72 (Paulo: enrichment step 6, bibliographic panel screen)**: Library tools > **Enrich bibliographic
  catalog** (key e, `views/enrich.py`). Scope box (all, or 101, 102, 500-550) → `enrich-job-add`; worker box with
  progress bar, paused/busy state, Pause/Resume; jobs table refreshed every 4 s while a job moves; staged report
  summary (records, enriched, review, M0/M1/W/R, fields by source), changed records list (`show` now carries
  `changes`, ≤200 enriched + ≤200 review) and the picked record's before/after (`enrich-job-diff` emits
  `kei_result line`, added lines in green). Open report copies report.html to Downloads and opens it. Apply and
  Revert ask first (danger) and run uncancellable; Cancel job for jobs not applied. Manual page `sec-enrich`
  (en, pt-BR). Fix: dashboard `age()` took real time instead of `now` (test broke once the date passed).
- **1.5.73 (Paulo: enrichment step 6b, Enrich & standardize authorities)**: `nexus_enrich/authority.py` matches
  each 1XX/6XX/7XX heading with the library's Koha authorities (heading, then 4XX variants), then static.db
  `auth_headings` ranked BN > Brazilian sources > LoC > rest (authority records before gathered headings);
  subjects never take LCSH/LoC forms; several people with the name and no dates, or two Koha authorities → review;
  mode fuzzy (≥ 0.92) applies close forms (preliminary), exact mode only proposes them. Fields with $9, name/title
  ($t) and subdivided subjects are skipped. Jobs gain `kind`/`mode`; `auth_new` keeps one new authority per heading
  (MARC21 authority: 1XX, 4XX, 010/024, 670, 008/33 d + 667 when preliminary); records get `$9 nexus-new:ID`,
  replaced by the real authid at Apply. Apply: re-export Koha authorities (`auth-resolve`), stage_file.pl
  --authorities + commit_file.pl per batch, then the records as in step 5. Revert: records first, then the
  authority batches; an authority a record still links to is kept. Task `enrich-auth-add SCOPE MODE`, panel
  screen Library tools > Enrich & standardize authorities (key h, `AuthEnrichView`), report.html with new
  authorities and heading diffs (diff now shows replaced lines). Manual `sec-enrich-auth`. Not run on a real Koha.
- **1.5.81 (Paulo: export still empty on WSL2 after 1.5.79)**: when the `koha_tool` export leaves the file empty, `enrich_export` now runs the second try straight through `koha-shell` (`koha-shell INSTANCE -c "export_records.pl ..." > FILE 2>> LOG`), skipping the `koha_exec` subshell, the same way the MARC21 backup runs it. Paulo verified this form on WSL2: 11,488 records exported, and the worker processed the job.
- **1.5.82 (Paulo: Edit & Map Fields proposal, engine side)**: `kei_import/fieldmap.py` applies an operator's field mapping (`{"mappings": [{"from": "500$a", "to": "100$a"}]}`; whole fields, control fields, spreadsheet columns, `ignore`) streamingly to every biblio stream before `stage_file.pl` (`build --fieldmap`, output `out/mapped-N.xml`); `fields` samples the direct import's streams (`out/manifest-direct.tsv`) and table columns into `work/fields.json`. No mapping = the direct import unchanged. Panel (Paulo approved the outline): after the build preview the task asks "Edit the field mapping before importing?" (default No, panel only), runs `fields`, opens `screens/fieldmap.py` via `@@fieldmap TITLE<TAB>FIELDS<TAB>OUT<TAB>ENGINE` (table, destination picker, custom TAG$sub, ignore, live preview with the engine's own module), then rebuilds with `--fieldmap`; a failed mapped build falls back to the direct build. Spec: `docs/field-mapping.md`. Tests: `panel/tests/test_fieldmap.py`, `test_fieldmap_screen.py`. Panel `t()` keys with `$a` get expanded as variables: pass `TAG$subfield` as a `${ref}` value.
- **1.5.83 (Paulo: Editar Campos as a MarcEdit-style data grid, steps 1 and 2 of `redesign-grid-proposal.md`)**: `screens/fieldmap.py` is a grid: rows are the sample records, columns the fields (MARC `TAG$c`) or spreadsheet columns, with each column's destination in a two-line header (`= kept`, `→ changed`, `✕ left out`). The row under the cursor is the example ("Example N of 10", `[`/`]`, ◀ ▶) for the inspector and the Koha preview; the column is the field the mapping card edits. Cell inspector: full value, length, warnings (edge spaces, all capitals, mojibake, ISBN-like, control characters). Filter Show: all / changed / with problems. Wide terminals (>=140 cols) put mapping+inspector and preview side by side; narrower ones use Mapping/Preview tabs (`p`), with grid and bottom heights set by hand (fr heights overflowed a full-screen dialog). Engine: `fields.json` gains `tables` (`fieldmap.table_entry`: first 10 rows per biblio table, cells under headers); older engines' 3 samples per column still fill a 3-row grid. Step 3 (indicators, split on `;`, fixed fields) is the next PR.
- **1.5.84 (Paulo: Editar Campos after the librarians' sketch `exemplo ferramenta de importação.xlsx`)**: screen rebuilt as grid + drag splitter (Ctrl+Up/Down) + one-line cell view, then "Selecionar campo" / "Função" (keep, custom TAG$sub, fixed text for every record, leave out, targets, other columns' fields) and "Mais opções" (LoC MARC 21 link + per-tag bdXXX.html, three options); record preview moved to a modal (`p`). Headers "campo N · source"; field names in `kei_panel/marc21.py`. Engine: fixed texts `{"from": "=BK", "to": "942$c"}` (fill, never overwrite; 952 into every copy, never creates one) and `"options"` clean/case/group in new `kei_import/tidy.py` (safe repair: mojibake, spaces, one OCR 0/1 between letters; recasing via rules.smart_case, sentence case for titles plus the record's own name words; grouping: surname + title Levenshtein >= 0.9 + publisher >= 0.8 + year/edition/volume/ISBN guards, three streaming passes, 952 + ISBNs moved). `marc_rules` now includes fixed texts and options. Textual 8 Select posts `Select.NULL` on set_options: handlers ignore non-str values.
- **1.5.85 (Paulo: direct Z39.50 servers first, SRU gateway as fallback)**: new `panel/kei_panel/data/z3950_direct.json` = Paulo's validated direct list of 2026-10-18 (171 servers: Brazil 24, North America 41, Europe 53, Latin America 17, Asia/Oceania 20, Authorities 16), each with flag, country, syntax (MARC21/UNIMARC), yaz-client command, `alternates` (other addresses the list gave), `unconfirmed` (host/db the list left as "x ou y"), `sru_fallback` (gateway id it covers) and `excluded` (Index Data directory/test servers, BNE10, LCNAMES/LCSH kept as NAF/SAF). `panel-list` puts them first (regions brazil … asia_oceania, authorities), then the gateway rows as `sru_*` regions, rank 500+, never preselected. Preselected: UTFPR, UFSC, UNIFESP, LoC LCDB. Logins only via `login_env` (KEI_Z3950_SENADO_FOLIO, KEI_Z3950_BNF). "Update server settings" leaves out direct authority files Koha lacks (`sync_targets`). Gateway targets.json gains `country`; utfpr db Default -> biblioteca. Installer's gateway koha-sql still ticks sru/_union at install.
- **1.5.86 (Paulo: flags showed as broken glyphs on Windows)**: Windows Terminal cannot draw flag emoji (regional indicator pairs), so the Z39.50 screen shows the country code (`z3950.badge`: BR, US...) before each name and 🌐 only for multi-country rows; the JSON keeps the flag emoji for other uses.
- **1.5.87 (Paulo: gateway rows back on the Cloudflare tunnel)**: the koha.nexus SRU gateway rows (sru/_union, sru/<id>, sru/_union-aut) point at https://sru.koha.nexus:443 again, in the panel list (`panel_list` host sru.koha.nexus 443; Koha gets the https:// prefix from z3950_add) and in `koha-sql` (installer enrich_register): rows on 127.0.0.1:5000 and the VPS IPs move to the tunnel; the retired bridges' 127.0.0.1 rows are still deleted; the Catalog Network (127.0.0.1:8088) is left alone. Direct Z39.50 servers unchanged. z3950.bats: the z3950-sync test now counts the gateway authority row and LCDB (it failed since before 1.5.85; bats is not in CI).
- **1.5.88 (Paulo: shared catalogue and Rede Pergamum back)**: a new first heading of the panel list, "koha.nexus servers" (region `koha_nexus`), preselected: the Catalog Network (https://catalog.koha.nexus:443/sru, the same row as the Community network switch) and Rede Pergamum (sru.koha.nexus:443/sru/all, out of the fallback; `koha_sql.PRIMARY_IDS`). `koha-sql` ticks sru/all next to sru/_union. enrich_register adds the Catalog Network row when Koha lacks it (`catalog_network_auto`), unless the switch was turned off (`/etc/koha-easy-install/catalog-network.off`). KEI_CATALOG_NETWORK_URL is read by the installer too.
- **On-demand enrichment step 1 (Paulo, plan `/mnt/project-files/on-demand-enrichment/plan.md`; no version bump, installer unchanged)**: `nexus_gateway/z3950.py` gains `Session` (one Init for several Search/Present, then Close), Type-1 queries `Term`/`Op`/`and_` (RPN AND/OR/AND-NOT, any Bib-1 attribute), `Timeouts` per phase (connect 4, init 6, search 8, present 10, close 2, session 25 s), `Diagnostic` (Bib-1 code, addinfo, category query/config/temporary/record) from non-surrogate and surrogate records, and `Z3950Error.phase`/`.kind` (dns, refused, unreachable, timeout, reset, init-refused, closed + close_reason, protocol). `search()` is now a wrapper over Session with `Timeouts.single` (no wait on Close), same results for the gateway. Tests: `enrichment/tests/test_z3950_session.py` (scripted fake server, hand-written BER). Not run against a live server (ports 210/1921 unreachable from the cloud).
- **On-demand enrichment step 2 (Paulo; no version bump, installer unchanged)**: new package `enrichment/nexus_ondemand/`: `targets` loads only `servers` of `z3950_direct.json` (171 load; 7 UNIMARC and senado-folio without its login are "unusable", logins from `<login_env>_USER/_PASSWORD`), `policy` refuses *.koha.nexus, localhost, non-public IPs, the VPS, Cloudflare ranges, ports 443/5000/5006/8088 and sru/ databases by name and again after the lookup (connects to the checked IP), `connect.open_session` is the only door to the network, `limits` (1 session/host, 0.5/s burst 2, 500/day; Alma provider 4 at once 2/s 3000/day; LoC 1 per 6 s 300/day; 8 for the service), `health` = health.db (breaker 3 consecutive or 5 in 10 min, 5 min x 2^level up to 24 h, one half-open probe; misconfigured until the list changes or reset; ban-like signals open 24 h and halve the rate; capabilities, preferred alternate, daily counts). CLI `python -m nexus_ondemand targets|health|health-reset|check`. Step 4 must point NEXUS_ONDEMAND_DIRECT_LIST at an installed copy (the installer extracts only enrichment/).
- **On-demand enrichment step 3 (Paulo; no version bump, installer unchanged)**: `nexus_ondemand/plan.py` (searches per record: ISBN 13+10 forms OR'ed, ISSN, LCCN, title AND author surname or year; ISBN/ISSN fall back to use 1007, title-author to title alone), `select.py` (eligible direct servers ordered by the record's language/place country, region, national/preselected, 7-day success ratio, latency; `waves()` keeps at most 2 sessions of one provider per wave of 6), `dispatch.py` (`Dispatcher.run`: waves with a 12 s budget, early stop on a complete M0 or two M0 agreeing on 082, max 20 servers, `exclude` for "Search more servers"; preferred address then alternates; one session per server under the limiter; learned.db cache `direct:<id>`; identical searches joined; diagnostic 114 -> fallback form remembered in health.db; Present capped at 10, diagnostic 13 retried with half; sessions 15 s, LoC 12 s; static.db after the servers when no M0). Paulo's live findings: a name that does not exist (getaddrinfo EAI_NONAME/-5/no address, kind `dns-missing`) opens the breaker for 24 h at once (`gone`); when 5+ servers of one request fail DNS, or every port-1921 connect times out, with none of that kind succeeding, the failures are not recorded and `Result.network` says what this machine blocks. Tests: `test_ondemand_dispatch.py` (scripted fake network), `test_ondemand_plan_select.py`.
- **On-demand enrichment step 4 (Paulo; 1.5.89)**: jobs integration. `jobs.db` gains `jobs.origin` (batch/ondemand: the batch worker and the new service each take only their own), `jobs.query` (a typed query), `jobs.rounds`, `od_attempts` (per record, round, server: outcome, diagnostic, hits, ms) and `od_choices` (the librarian's donor per field group; `merge.Policy.donors` puts it first, class rules unchanged). `nexus_ondemand/service.py` + `python -m nexus_ondemand serve | once ID | status`: at most 50 exported records or one typed query, dispatcher per record, records kept in `jobs/ID/candidates/SEQ/`, each server's best record merged (plan 8.2), same report/chunks as a batch job, `ondemand-status.json` per server event, exits after 5 idle minutes. `nexus_jobs add --origin ondemand --scope | --isbn/--title/--author/--year`, `more ID` (new round, servers already asked passed over), `donor ID BIB GROUP [SOURCE]` (re-merge, no network), `origin ID`; `show` lists attempts. Installer: ships `nexus_ondemand` and `z3950_direct.json` into `$ENRICH_DIR`, unit `koha-nexus-ondemand` (network, no port, Nice 10, CPUQuota 25%, MemoryMax 160M, panel .env for KEI_Z3950_* logins), `enrich_od_ready`, `ondemand_py`, tasks `enrich-od-add/-status/-more/-donor`, `z3950-health`, `z3950-health-reset`; Apply and Revert of an on-demand job save a copy of its records (`jobs/ID/snapshot-apply|revert-*.xml`) instead of a full database backup (Paulo's decision 5). Tests: `test_ondemand_service.py`, `tests/enrichment_ondemand.bats` (real service on a scripted fake network, MariaDB, Koha stand-ins). The panel (step 5) does not call these tasks yet; importing a typed query's record as new comes with it.
- **1.5.80 (Paulo: gateway_py outside its folder, jobs blocked on an empty static.db)**: `gateway_py` runs from `ENRICH_DIR` like `jobs_py`, and `enrich_install` writes `koha-nexus.pth` into the venv, so `python -m nexus_gateway` works from any folder. Before this, `enrich_empty_db` and `enrich_records` failed silently from other folders, and the count always read 0, even with a real static.db. A job on an empty (or missing, now created) static.db no longer stops: the download starts in the background, the job runs, and its message says the report finds little until the download is done.
- **1.5.79 (Paulo: export.xml still empty)**: the three enrichment exports (records, authorities, Koha's authorities at Apply) go through `enrich_export`. When the low-priority run leaves the file empty, it runs once more plainly, as the MARC21 backup does (koha-shell, no priority prefix, from /tmp). The failure dialog and the job's error quote the last message line of the log. No `chmod 666`: the file is opened by the root shell (`koha_exec`), so its mode never limited the instance user.
- **1.5.78 (Paulo: WSL2 export still refused)**: the 1.5.76 probe passed as root but the export's scope was still
  refused under WSL2; `throttle_cmd` now never uses `systemd-run --scope` when `is_wsl` (nice + ionice only).
- **1.5.77 (Paulo: WSL2 credentials showed http://0:80, drops right after install did nothing)**: `get_server_ip`
  reads the word after `src` in `ip -4 route get 1.1.1.1`, not the 7th word (WSL2 mirrored mode prints
  `1.1.1.1 dev eth0 src X uid 0`, so the 7th word was the uid `0`), then falls back to WIN_LAN_IP, the first usable
  address of `hostname -I` / `ip -4 addr` (`lan_ip_usable`: no 0.x, 127.x, 169.254.x, multicast) and 127.0.0.1.
  Drops: the panel the Windows installer opens runs in the elevated installer window, and Windows refuses drags
  from Explorer into an elevated window; `Invoke-KohaPanel` passes `KEI_WIN_ELEVATED` (WSLENV) and the file picker
  then says to paste the path (Copy as path) or open Koha from its icon. Drive paths go through `wslpath -u` when
  it works (wsl.conf may mount drives outside /mnt), panel and `clean_path` alike; `flush_tty_input` drops keys
  left waiting before the classic pickers and Enter prompts. Elevation and the real drop not tested on Windows.
- **1.5.76 (Paulo: enrichment export never ran under WSL2)**: `throttle_cmd` tries `systemd-run --scope
  --no-ask-password -p CPUQuota=25% true` first and uses the scope only when systemd grants it; under WSL2 polkit
  refused it ("Failed to start transient scope unit: Access denied", no pkttyagent), so export_records.pl never
  ran and the job said "No record in this scope". Without it: `nice -n 19 ionice -c 3`. The dir check now uses
  `systemd_is_pid1` (KEI_SYSTEMD_RUNDIR). An export file left empty (not even `<collection>`) is a failed export
  (bib, authorities, Apply's authority re-export), not an empty scope.
- **1.5.75 (Paulo: fresh WSL install findings)**: `enrich_install` creates an empty static.db (`python -m
  nexus_gateway init-db`: schema, meta schema + empty, 0644, never over an existing file) before the gateway starts,
  so the gateway, Koha's rows and the panel work before the first download; the first download now starts when
  `static.release` is missing (the empty file is no release). Starting a job on an empty database says the download
  has started (and starts the update unit) instead of the old error. `releases_api` defaults to the repository's
  GitHub Releases (`config.RELEASES_API`, also `update.API`); "no release found" now names the URL and that drafts and
  pre-releases are not read. update chmods static.db and static.release 0644. Cause of Paulo's "no release found":
  the uploaded enrichment release was still a **draft** (untagged), invisible to the API; publish it as tag
  `enrich-2026.10` with `nexus-enrich-2026.10.db.zst` + `.sha256`.
- **1.5.74 (Paulo: authority search row for cataloguing)**: the local gateway answers `/sru/_union-aut` from
  static.db `auth_headings` (`nexus_gateway/authorities.py`): Koha's authority search fields reach it through the
  row's SRU fields (authorpersonal=bath.personalName, authorcorp=bath.corporateName,
  authormeetingcon=bath.conferenceName, subject/subjectsubdiv=dc.subject, title/uniformtitle=bath.uniformTitle,
  nameany/authorany=bath.name, srchany=cql.serverChoice); each clause matches heading and 4XX words of those kinds,
  and/or/not combine. Ranked like the authority jobs (exact heading, BN > Brazilian > LoC > rest, established before
  preliminary, most used); subjects never LCSH. Records are MARC21 authorities built by
  `authority.authority_record` (670 source + release, 008/33 d + 667 when preliminary). `koha-sql` step 6 upserts
  one row KOHA.NEXUS (AUTORIDADES), recordtype authority, 127.0.0.1:5000 `sru/_union-aut`, ticked when added, tick
  and rank left to the librarian; the panel list carries it first among the authority files. Koha's own authorities
  are searched by Koha itself; LoC and BN rows untouched. Not tried against a live Koha authority search yet.
- **1.5.70 (Paulo: enrichment step 4, installer and monthly updates)**: `python -m nexus_gateway update`
  finds the newest `nexus-enrich-YYYY.MM.db.zst` (GitHub releases `enrich-YYYY.MM`, mirror `latest.txt`
  via `NEXUS_GATEWAY_MIRROR`), checks size and SHA-256, decompresses, checks the DB and swaps it over
  `static.db` with `os.replace` (gateway reopens it). `enrich_build publish` uploads a month (GITHUB_TOKEN).
  Installer `enrich_install` (task `enrich-install`, end of Koha install): venv in
  `/usr/local/lib/koha-easy-installer/enrichment`, units `koha-nexus-sru`, `koha-nexus-enrich-update`
  (+ weekly timer, low priority), retires the Zeus/Pergamum bridges, runs `koha-sql`. Panel list
  `z3950_targets.json` is generated by `nexus_gateway panel-list` (127.0.0.1:5000, `_union` only ticked).
  `.wslconfig` gets `autoMemoryReclaim=gradual`. No release published yet; mirror URL unknown.
- **1.5.69 (Paulo: Windows shutdown watcher)**: `KohaEasy.ps1 Watcher` (`windows/KohaEasy.Watcher.ps1` +
  `KohaEasy.Watcher.cs`), its own HKCU Run entry `KohaEasyShutdownWatcher`, so the clean stop at the end of
  a Windows session no longer depends on the tray being open. A hidden top-level window (not HWND_MESSAGE:
  no broadcasts there) holds the block reason while Koha runs, answers WM_QUERYENDSESSION TRUE, and on
  WM_ENDSESSION runs `/usr/local/bin/koha-graceful-shutdown.sh` (was `/usr/local/sbin/koha-easy-stop`, now a
  file in `windows/`, read by Core) through a console-less wsl.exe, 20 s (`SessionStopS`), then
  `wsl --shutdown`, then releases the reason (37 s at most). The tray stands in only when the watcher is not
  running. Installer registers and starts it after the tray on every run; keep-alive restarts it; Koha icon
  puts back the entry; `EnableShutdownWatcher` / `DisableShutdownWatcher`; uninstall removes it. Script
  also stops the long_tasks worker queue and, without systemd, MariaDB via `mariadb-admin shutdown`.
  Docs: `docs/windows-shutdown-watcher.md`. Not run on a real Windows shutdown.
- **1.5.68 (Paulo: authority servers in the panel, true upsert, sync button)**: the panel's catalogue
  (`panel/kei_panel/data/z3950_targets.json`) carries the three authority files under a fifth heading
  "Authority files" (`recordtype: authority`, a fixed `rank` and `timeout`): LoC NAF and SAF
  (lx2.loc.gov:210, USMARC, timeout 10, ranks 1 and 2) and BIBLIOTECA NACIONAL (AUTORIDADES)
  (sru.koha.nexus:443/sru/bn-aut, SRU, MARC21, timeout 30, rank 3, Koha's authority SRU fields). `Target`
  gains `recordtype`, `timeout` and `rank`; the z3950-add file a 14th column (recordtype); the SQL export
  matches rows of the target's own record type and writes `https://` for SRU on 443; a Koha SQL dump's
  authority rows are read. `z3950_upsert_sql` counts `@kei_added` and `@kei_updated` (rows whose settings
  changed), and gains mode `sync`. New button "Update server settings" ("Atualizar dados dos servidores")
  sends the whole catalogue to `--task z3950-sync`: every row Koha has is refreshed (by address, else by
  name, within its record type; tick and rank kept), only the missing authority files are inserted, and
  rows on the BN's dead Z39.50 hosts (`Z3950_DEAD_HOSTS`: 200.20.12.18, 162.214.168.248) are unticked,
  never deleted (also by `z3950_seed_authorities`). The result says how many were added and updated.
  `z3950-list` now returns authority rows too (5th column recordtype).
- **1.5.67 (Paulo: BN authority database)**: `z3950_seed_authorities` also upserts
  `BIBLIOTECA NACIONAL (AUTORIDADES)`: https://sru.koha.nexus:443, db `sru/bn-aut`, SRU, MARC21, utf8,
  timeout 30, rank 3, recordtype authority, SRU fields mapped from Koha's authority search form
  (`authorpersonal=bath.personalName`, `authorcorp=bath.corporateName`, `nameany`/`authorany=dc.creator`,
  ...). The `/sru/bn-aut` endpoint itself is in the SRU gateway (`sru-bridge/`, off `main`): it searches
  `/sru/bn` by author and answers MARC21 authority records (leader `00000nz  a2200000n  4500`, 040
  `$a BR-RjBN $b por`, the 100/110 heading `$a $d`, 670 `$a Acervo Fundação Biblioteca Nacional
  (Pergamum)`); records with no 100/110 answer SRU diagnostic 1.
- **1.5.66 (Paulo: idempotent Z39.50 / SRU upsert)**: every write to `z3950servers` goes through
  `z3950_upsert_sql` (installer): each target finds its row by host, port and database, else by name
  (never a row another target of the same list took), gets the connection settings (host, port, db,
  syntax, encoding, timeout, servertype, sru_fields, sru_options; the login only when one is given) and
  keeps the librarian's `checked` and `rank`; no row means an INSERT. Mode `add` (z3950-add) keeps the
  row's name; mode `named` (Zeus and Pergamum bridges, Catalog Network) matches host and port, sets the
  name and removes other rows with that name or address. The panel's SQL export (`to_koha_sql`) and
  `catalog-network/deploy/koha-z3950servers.sql` follow the same rule. Re-registering a bridge no
  longer re-ticks it. `z3950_seed_authorities` (`--task z3950-seed`, and at install) upserts Paulo's
  two Library of Congress authority targets (lx2.loc.gov:210 NAF rank 1 and SAF rank 2, USMARC, utf8,
  timeout 10, recordtype authority). `sru-bridge/` now lives on a backup branch, so its CI job
  (sru-services matrix) and the two gateway SQL tests in tests/z3950.bats were removed.
- **1.5.64 (Paulo: translucent staff header)**: `cfg["staff"]` gains `header_glass` (off by default),
  `header_opacity` (0-100, default 85) and `header_blur` (0-30 px, default 8); switch and two sliders in
  the Staff interface box. `_staff_header_css` (after the texture, so it also beats the metal bar) paints
  `nav.navbar.bg-dark` and `#header_search` with the bar colours as `rgba(..., var(--nexus-staff-header-a))`,
  blur on a `::before` layer (never on the bar), the search bar's inner tabs/labels clear (one layer),
  bars `isolation: isolate; z-index: 1030/1029` so the nav dropdowns stay above the search bar and the
  page. Only backgrounds go translucent (no `opacity`): links get a soft text-shadow, the search field,
  `.form-extra-content` and light dropdowns stay on the solid staff card colour. Solid again under
  `prefers-reduced-transparency` or without `backdrop-filter`.
- **1.5.57 (Windows: terminal panel + tray, web window dropped)**: Paulo chose to drop the
  pywebview Control Center (PRs #98-#104): `windows/client/`, `windows/KohaEasy.Python.psm1`,
  `nexus_core/taskproto.py` + `menucatalog.py` and the windows-client CI are gone; install.ps1 deletes
  `bin\client`, `bin\python`, `bin\nexus_core` and `downloads\python` of test builds (nexus_core stays,
  unused). The Textual panel is the only interface. It opens in Windows Terminal with a "Koha Nexus"
  profile (a fragment in `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\KohaEasy\koha-nexus.json`, removed by the uninstaller: title,
  padding, Cascadia Mono, icon), else `cmd.exe /c` with chcp 65001. `koha-window` (version line
  `# koha-window 2`, rewritten when older) cleans up also when the window is closed: a watcher waits
  on the WSL parent (`tail --pid`), then stops tty holders and the window's session; setsid jobs keep
  running. Tray: dot green running / yellow starting / red otherwise, check every 30 s, menu Open
  Dashboard (panel, also double-click) / Open User Folder (`KohaEasy.ps1 UserFolder`, wslpath -w of the
  default user's ~) / Restart Services / More options (the old items) / Exit. Toasts at the end of long
  panel jobs: `kei_event` writes `$STOP_GUARD_STATE_DIR/events.log`, `--status-json` has `events`
  (last 10), Get-KohaNotifications shows each new one once (`lastEventId`). Panel: card "Open user
  folder" (General tools, `opener.folder_command`); manual backup starts on the Windows Downloads
  folder under WSL and a backup on the Windows disk or a download is shown selected in Explorer
  (`opener.reveal_command`, `explorer.exe /select,`). New CI `windows-tools.yml`: PowerShell 5.1
  checks (`tests/windows_checks.ps1`) and `tests/koha_window_test.sh`. Not tried on a real PC.
- **1.5.56 (panel clean-ups from Paulo)**: Backup center has no button row any more: its cards are
  the only actions (Download latest backup is now a card, `backup-download` in `menus.PANEL_ONLY`, so it
  is not an installer action); the codec box is "Backup compression type"; the cloud card is
  "Configure cloud backup" (installer menu key re-keyed in all 22 caches, Google Drive stays inside
  the provider choice). The MARC21 result box has "Download to computer" on WSL/desktop
  (`routines/backup.download_file` copies the `.tar.gz` to Downloads; over SSH only the scp command).
  Database tables left the sidebar: a `kind="view"` card of Diagnostics (`sidebar=False`,
  `parent="diagnostics"`, no cards of its own). OPAC: the "News action buttons" box is gone and
  `news_buttons` is always saved on. AI screen: a warning that local models can slow the whole
  server. Magic Import: a subtitle naming patron data. Manual (en + pt-BR) and preview.json updated.
  Not tried on a live Koha.
- **1.5.55 (MARC21 export output)**: Paulo saw raw records (leader, tags, $a) in the export's error
  box. `/root/backup_marc.sh` no longer passes `--filename` to export_records.pl: its stdout is
  redirected by the root shell into `biblios_/authorities_<date>.mrc` and its stderr into
  `backup_marc_export_errors.log`; the bib file must start with 5 digits (ISO 2709); log_backup starts
  a fresh line after a partial one. function_marc_backup rewrites a script without `EXPORT_ERR=`,
  reads only this run's `date | ...` lines by byte offset, quotes only the last stderr message (record
  dumps skipped) and reports `contents` (the .mrc names) in the success box. Not tried on a live Koha.
- **SRU gateway (sru-bridge/sru_gateway, bridge-only, no panel version)**: the central VPS serves
  one SRU database per catalogue, `/sru/{id}` on port 5000, from `sru_gateway/targets.json` (the 48
  ids of Paulo's 2026-10-11 list; Koha rows from `/mnt/project-files/sru-servers/insert_z3950servers.sql`,
  database `sru/<id>`). Kinds zeus, pergamum, z3950 (the panel's BER client with a paged Present), sru,
  missing (diagnostic 1). Only ufsc, pergamum, bl, sbn_it, swb_de have addresses; the other 43 wait
  for real addresses. `//sru/bn` is read as `/sru/bn`. Unit `deploy/sru-gateway.service` (0.0.0.0:5000).
- **SRU clean-up, Phase 0 of the SRU/enrichment study (bridge-only, no panel version)**: the
  Pergamum fixes from the orphan root `pergamum_sru/` (PHPSESSID handshake, HTTP 500 with a `+:`
  Sajax body read as no hits, ISBN reduced to digits/X, timeout 30 s) are in
  `sru-bridge/pergamum_sru` (1.1.0) and the root copy is gone. Removed: `sql/z3950servers_seeds.sql`
  (pasted mysql output, not SQL), `sru-services-systemd/`, `SRU_BRIDGES_SPECS.md` (ports 5001/5002,
  used by nothing), `STATUS_ALVOS.md` (folded into a `status` per entry of `targets.json`, 53 ids,
  and a README table generated by `python -m sru_gateway.status_table --write`). Ports: 5000
  gateway (VPS) / Zeus (Koha server), 5006 Pergamum, 8088 catalog network. Gateway 1.1.0: zeus
  entries share one Zeus HTTP client (Zeus's Referer); `python -m sru_gateway.zeus_labels` reads
  Zeus's search page to check each `target_index`. CI: `.github/workflows/sru-services.yml`.
- **Enrichment, step 3 (no panel version)**: `enrichment/nexus_gateway`, the local SRU server on
  127.0.0.1:5000 that replaces the VPS gateway for Koha: `/sru/_union` and `/sru/<id>` (the 72 ids of
  the VPS gateway's `targets.json`, plus `unb`) answer from `static.db`, and on a miss from the native
  Z39.50/SRU targets live within 6 s; late answers go to `learned.db`. `python -m nexus_gateway
  koha-sql` repoints the rows with `sru/_union` the only ticked one. Not installed by the installer
  yet (step 4), so no row points at it yet. Unit: `enrichment/deploy/koha-nexus-sru.service`.
- **Enrichment, steps 1-2 (no panel version)**: the offline-first design (`design.md` revision 3,
  approved 2026-10-17 in `/mnt/project-files/enrichment-design/`): no search or enrichment backend on
  the VPS, a monthly `nexus-enrich-YYYY.MM.db.zst` on GitHub Releases, no HTML scraping on libraries'
  machines. `enrichment/enrich_build` builds `static.db` from the harvest dumps (JSONL / MARCXML /
  ISO 2709 / the catalog pool, streamed; per-source `full` or `pointer` mode; ISBN clusters with a
  title check; authority records and bib headings into `auth_headings`; zstd dictionary bodies;
  `release` / `verify`). `enrichment/nexus_enrich` classifies candidates M0 / M1 / W / R and only adds
  missing fields (one donor per group, `883` + `$8 N\p`). Not yet tried on Paulo's real dumps
  (their layout is unknown to the repo). CI: `.github/workflows/enrichment.yml`.
- **1.5.54 (follow-up from Paulo)**: News items (OPAC and staff) take a list of buttons
  (`news.<side>.buttons` = `[{text, url}]`, at most 6, "Adicionar botão" + ✕ rows like the staff home
  buttons; a 1.5.53 `button_text`/`button_url` pair is read as the first button). The main menu (panel
  and classic, now 16 options) has no "Restore database" of its own: restore lives only in the Backup
  center. bridge.stream reads output in 64 KiB chunks (`read_lines`): "\n", else after 1 MiB the last
  \r / 0x1D / 0x1E, else a hard cut, so a routine printing MARC records no longer raises "Separator is
  not found, and chunk exceed the limit"; function_marc_backup also sends the script's output to its
  log. Not tried on a live Koha.
- **1.5.53 (eight panel fixes from Paulo)**: Cloudflare and free-address examples say `example-library`
  (no TLD, no town names). Corner sliders (Blocos/Campos/Botões) explain border-radius in a note and
  tooltips. Reader alerts job runs daily, weekly or monthly: cron.py writes `--every weekly|monthly`
  after the instance and notify.py covers the whole period (dedupe by the sent log). Backup screen
  (pt: "Central de backups e restauração") has Restore database and Export MARC21 now
  (`--task backup-marc` runs `/root/backup_marc.sh` and reads its log). OPAC and staff news item of
  our own (`news-opac`/`news-staff` in contents.list, Koha news `kei-news-*`, opac_only/staff_only,
  title on the file's first line as `<!-- kei-news-title: ... -->`). Footer credits are one text box
  of `Field: value` lines. widgets/linkrow.py (Open + Copy) for Postimages and the Evolution API guide;
  AI screen has Get an API key + Copy (Gemini: aistudio.google.com/api-keys). Not tried on a live Koha.
- **1.5.52 (one glass surface)**: Paulo found the header, content, sidebar and breadcrumbs
  each a different surface. Now every surface reads shared variables (`--koha-card-bg` =
  rgba(`--koha-card-rgb`, `--koha-card-alpha`), `--koha-glass-blur`, `--koha-card-border`,
  `--koha-card-radius`, `--koha-card-sheen/-shadow` from the texture), set in css_body's :root; the old
  `--kei-*` names are aliases. One opacity slider, free 0-100 (`panel_opacity` removed). `_cards_css`:
  header, search and `.main` are the card; Koha's boxes (`_OWN_CARDS`) are the same card only outside
  .main (`:not(.main *)`, outermost only). `_panels_css`: inside .main every box (`_PANES`, `_FILLS` from
  Koha's opac.scss) is transparent with `--koha-pane-border`, so nothing stacks.
- **1.5.51 (frosted glass follow-up to 1.5.50)**: Paulo asked to keep the glass look. The
  content panels are translucent again (`panel_opacity` 50-100, default 76) with
  `backdrop-filter: blur(12px)` (and `-webkit-`), Koha's inner panels a second translucent layer
  (`INNER_ALPHA` .55); `panel_colors` checks text against the panel over a black and a white
  wallpaper (7:1 from 76% up), plus a soft text shadow and bold labels. `#opaccredits` has no box:
  only a halo around the letters. The credits form placeholders are generic (no real library data).
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
