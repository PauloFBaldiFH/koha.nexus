# koha.nexus: Project Progress

_Last updated: 2026-10-08. Panel version on `main`: **1.5.19**._

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
- **Links from the panel** open through `panel/kei_panel/opener.py` (wslview/explorer.exe on
  WSL, xdg-open as SUDO_USER on a desktop, else copy via OSC 52). Never Python `webbrowser`.
- **Windows**: new installs go to `C:\Koha`; scheduled tasks live in the Task Scheduler root as
  "Koha - <task> (<USERNAME>)"; the `.cmd` no longer runs as admin.
  The manual PowerShell line is documented as "open PowerShell **as Administrator**" from the
  person's own administrator account (Paulo, 2026-10-08); the `.cmd` itself still runs as the
  signed-in user (5c1fa82), and the docs warn not to approve with another person's password. Use `Get-KohaPath`, not
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
