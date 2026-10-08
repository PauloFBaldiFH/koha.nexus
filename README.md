<p align="right">
  🇺🇸 English &nbsp;|&nbsp; <a href="README.pt-BR.md">🇧🇷 Português</a>
</p>

<p align="center">
  <img src="docs/images/koha-logo-green.png" alt="koha.nexus logo" width="400">
</p>

# koha.nexus : A smart, free and easy-to-use assistant for library management

A single Bash script that installs, tunes and maintains the **[Koha](https://koha-community.org/) Integrated Library System** on Debian/Ubuntu, through a friendly menu-driven control panel (whiptail, dark theme) available in **22 languages**.

It was born from real-life experience facing technical barriers in collection management, and is designed for libraries without budget for expensive commercial systems or dedicated technical support.

---

## Features

- **One-step installation** of Koha, MariaDB, Apache, Memcached and Plack, with pre-validation of the server (OS, disk, network, busy ports), 4 GB SWAP, NTP and timezone selection.
- **Backup center**: daily compressed SQL backups, weekly MARC21 export, manual backup with download instructions, restore test in a temporary database and cloud copies to Google Drive (rclone).
- **Safe restore** of `.sql` / `.sql.gz` backups: the file is checked (gzip test, complete mysqldump, Koha tables) and imported into a temporary database first; the current catalog is only replaced after a verified safety copy exists, is put back automatically if anything fails, and a restore cannot be left half-done by CTRL+C or a lost SSH connection.
- **Search engine**: switch between Zebra and Elasticsearch 7, indexer watchdog and repair/rebuild tools.
- **Publishing to the internet**: Cloudflare Tunnel (no open ports), free SSL certificate (Certbot) and a Google Search Console assistant.
- **Free address (in testing)**: a public catalog address without buying a domain or opening a Cloudflare account. The library types its name and the address it wants in the panel, and the address is created right away. The link can be shared as a QR code on screen, a printable QR image or a link. Remote staff access adds a password checked at Cloudflare before Koha's own login. The address service is still being tested and is not open to libraries yet.
- **QR code sign-in**: when Cloudflare or Google Drive asks you to authorize the server, the panel lets you choose how to open the page. Cloudflare offers a QR code to scan with your phone, the browser of this computer (the Windows browser under WSL) or a link to copy. Google Drive offers the browser or the link: Google only returns to the computer running rclone, so a phone cannot finish that login, and on a server with no screen the panel explains the SSH tunnel. The Google token is never shown on screen.
- **Diagnostics**: full health check with a detailed report, server status, real-time Apache log viewer and deep database maintenance.
- **Security**: Fail2ban, UFW firewall (with option to restrict the staff port 8080) and database password rotation.
- **Koha settings**: server sizing profiles, e-mail notices (Koha's own schedule, enabled with `koha-email-enable`), super librarian creation, SIP2 and Z39.50, clock and timezone.
- **Library tools**: the 🪄 Magic Import Tool, one entry for every import (spreadsheets, MARC, the backup of the old system, archives of them: books and patrons found and split on their own), undo of a MARC import, essential SQL reports pack, school-year category turnover, catalog data-quality check, and privacy (LGPD) housekeeping. Every change is previewed first with Koha's own dry run and protected by a verified backup (see [Library tools](#library-tools)).
- **Brazil: localization** (opt-in, never applied by the installation or by a schedule): CPF audit (modulo 11), Pimaco label templates, the Brazilian cataloguing card (ficha catalográfica) with the ABNT reference of the record, Brazilian holidays in the Koha calendar, government census reports (MEC/INEP/IBGE/SNBP) and bibliographies and collection listings by ABNT NBR 6023 (see [Brazil: localization](#brazil-localization)). The migrations from Biblivre, SophiA, Pergamum, Biblioteca Fácil and ISIS are done by the [Magic Import Tool](#-magic-import-tool).
- **Messaging: WhatsApp and Telegram** (opt-in): Koha's own notices (checkout, check-in, overdue, due, hold) delivered through a self-hosted WhatsApp gateway (Evolution API or similar) or a Telegram bot, with the patrons' numbers completed and corrected on the way (see [Messaging](#messaging-whatsapp-and-telegram)).
- **Cataloguing aids**: author notation with the PHA or Cutter-Sanborn table loaded by the library, Dewey (CDD) lookup, a Cutter Calculator (Cutter-Sanborn or PHA, with the PHA table read even from a scanned PDF) with a Cutter button in Koha's cataloguing, and a staff-interface page that replaces a record by its biblionumber without touching its items (see [Cataloguing aids](#cataloguing-aids-pha-cutter-sanborn-cdd), [Cutter Calculator](#cutter-calculator) and [Replace a MARC record](#replace-a-marc-record-staff-interface)).
- **Windows 10/11 (WSL 2)**: Koha on a single Windows PC, with Start/Stop shortcuts that use the official Koha icon, a status icon, Windows notifications, one-click diagnostics and a disk watchdog (see [Windows (WSL 2)](#windows-wsl-2)).
- **Languages**: installs Koha language packs and translates the panel itself (22 languages).
- **Self-update** from GitHub with SHA-256 verification.

## Requirements

| Item | Minimum |
|------|---------|
| Operating system | Debian 11/12/13 or Ubuntu 22.04/24.04, 64-bit (amd64 or arm64, e.g. Oracle Ampere, AWS Graviton, Raspberry Pi 4/5), or Windows 10/11 through WSL 2 (see [Windows](#windows-wsl-2)) |
| RAM | 2 GB (4 GB+ recommended; Elasticsearch needs ~1.5 GB more) |
| Free disk | 5 GB (10 GB+ recommended) |
| Access | `root` or a user with `sudo` |
| Network | Internet access to `debian.koha-community.org` |
| Ports | 80 (OPAC) and 8080 (staff interface) free |

## Installation

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Or clone the repository (this keeps the translation files next to the script and works offline):

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

On the first run you choose the panel language. Then pick **1 – Install Koha server** and follow the wizard (10 to 30 minutes).

After the installation the panel is available anywhere as:

```bash
sudo config.sh
```

### After installing

1. Open the staff interface at `http://SERVER-IP:8080`.
2. Log in with the database user and password shown at the end of the installation (also saved in `/root/koha_credentials.txt`) and complete Koha's **Web Installer**.
3. Back in the panel, create your own super librarian (**9 – Koha settings > Create super librarian**).
4. The public catalog (OPAC) is at `http://SERVER-IP:80`.

## Windows (WSL 2)

Koha can also run on a single Windows 10 or 11 PC. This suits small single-desk libraries, staff training and evaluations. Libraries with several desks should keep a dedicated Linux server.

Koha runs inside a Debian system in **WSL 2** (the Windows Subsystem for Linux), managed by the same panel. Small **PowerShell** tools let the librarian control it from Windows without opening a terminal.

### What works on Windows

- **WSL mode in the panel**: WSL 2 is detected automatically. WSL 1 is refused, with an explanation.
  - The host tasks are left to Windows: no swapfile, NTP, UFW, Fail2ban or avahi.
  - The timezone is chosen inside Debian during the installation, with the Windows zone offered first. A different zone is kept across WSL restarts (`useWindowsTimezone=false` in `/etc/wsl.conf`).
  - "Reboot server" becomes **Restart Koha services**.
  - systemd must be enabled in WSL (the Windows installer does it).
  - Screens are always UTF-8, and the installer and the panel show emoji. When Windows Terminal is installed (it comes with Windows 11), the installer and the control panel open in it. The classic Windows console has no emoji font, so on a PC without Windows Terminal they show plain symbols such as `[OK]` instead of boxes.
  - The Windows side talks to the panel through `/etc/koha-easy-install/windows.conf`. It is read with a whitelist of keys and never executed.
- **Networking**: Apache listens on every address, on ports 80 (catalog) and 8080 (staff interface). The installer opens both ports to the local network only, in the Windows firewall and, on Windows 11, in the Hyper-V firewall that guards WSL, so other PCs of the library reach Koha at this PC's address. Windows 11 uses mirrored networking, with `hostAddressLoopback` so this PC can also reach Koha by its own address. The network mode is read from WSL itself, not from `.wslconfig`: when WSL falls back to NAT (Windows 10, or a Windows 11 where mirrored networking cannot start), the *Koha network* task points `netsh interface portproxy` at Debian's address each time Koha starts, and back in mirrored mode it removes that forwarding. Other PCs can use this PC's name (`http://<pc-name>:8080/`), which stays the same when the router hands out a new address. To publish Koha on the internet, use the panel's built-in **Cloudflare Tunnel**.
- **Library network test**: at the end of the install, with the **Test the library network** button of the Koha window and in the diagnostics, Koha is asked through this PC's own network address, the way the other PCs reach it. The result says whether it answered and what could block the other PCs: a missing firewall rule, missing port forwarding in NAT mode, or another firewall product that needs ports 80 and 8080 opened too.
- **Koha window**: a native Windows window with a dark design, opened by the **Koha** icon on the desktop, *Koha - Status* and the tray. It works even when Koha does not answer, because it asks Debian directly through WSL and never needs Koha's web server. It opens with the green koha.nexus logo (the Koha name and symbol belong to the Koha community). The window, its dialogs and the Koha icon's tooltip carry the title *koha.nexus : A smart, free and easy-to-use assistant for library management* (*koha.nexus : Assistente inteligente e gratuito para facilitar a gestão de bibliotecas* in Portuguese). The Koha icon and the other program shortcuts show the icon built into `KohaEasy.exe`, the program they start, so they keep it after Windows restarts. Below it, a banner speaks up only about problems: it stays green with the time of the last check and the latest backup while every component runs. When one fails, it turns red and says which one (for example "Attention: MariaDB is offline"), with a **Start Koha** button while Koha is off. **Details** on the banner opens the list of components (Debian (WSL), MariaDB, Apache, RabbitMQ, Memcached, koha-common and the staff page's HTTP answer), with a red badge on the one that failed. Below it come **Quick access** (the staff interface first, then the public catalog). Then come four actions: **Management panel** (the full terminal menus), **Restart Koha** (Koha's services, without restarting WSL), **Shut down the PC safely** (below) and **Open the Debian terminal**, which opens a full Debian shell as your Debian user in its own window (Windows Terminal, or the classic console) while Koha runs; sudo, passwords and full-screen programs work there, and closing it or typing `exit` ends everything it ran. **More actions** holds Stop Koha, Restart Debian and Koha, Rebuild search index, Test the library network and the diagnostics exports. While Koha stops, the window shows which step it is on. The window checks again every 30 seconds, or when you press F5. For 45 seconds after Windows starts, a Koha that is still coming up shows as starting, not as failed, and sends no failure notification. It also shows the addresses other PCs use.
- **No console windows**: the shortcuts, the tray, and the tasks that run at sign-in and keep Debian running start through `KohaEasy.exe`, a small launcher the installer compiles on the PC from its C# source (`windows/KohaEasy.Launcher.cs`) with the compiler that comes with Windows, so nothing is downloaded. It is a Windows program that starts PowerShell with no window at all, so Windows Terminal never opens an empty window at sign-in. It also gives the Koha window, the Start menu entry and the notifications Koha's own name and icon on the taskbar. If Windows does not let it run (Smart App Control or an antivirus), everything starts through Windows Script Host (`KohaEasy.Hidden.js`, which starts PowerShell hidden from the start), and after that through a hidden console. Every run of the installer tries them again, best first. Anything started the old way, with a console you can see (a shortcut, sign-in entry or task of an earlier version), starts itself again the hidden way at once, so that console closes. The installer checks that the **Koha** icon really is on your desktop (the one Explorer shows, OneDrive's included) and in the Start menu before it says so. When Windows refuses one, it says where Koha is instead and gives Windows' reason, which also goes in the install log.
- **Control panel window**: the control panel and the Debian terminal open in their own window (Windows Terminal when it is installed), which closes as soon as you leave with **Exit**: anything still holding that window is stopped first, so it never stays open and black. If the panel ends with an error, the window waits for Enter so the message can be read.
- **Koha icon and shortcuts**: one **Koha** icon on the desktop and in the Start menu. Clicking it starts whatever is not running, with no console window: the status icon, and Koha itself (the Koha window then shows it starting). It also puts back the sign-in entry and the scheduled tasks if someone deleted them. Then it opens the Koha window, or brings the one already open to the front, so clicking it again never starts anything twice. Every shortcut, including those in the *Koha* folder of the Start menu, has the official `koha.ico`, and none opens a console window. The folder holds:
  - Staff interface, Public catalog, Control panel and Backups folder
  - **Start**, **Stop** and **Restart**
  - Status, Export diagnostics and Status icon
- **Start and stop**: Koha can start automatically when you sign in to Windows, or only when you click *Koha - Start*. Change this at any time from the tray menu. After **Stop**, Koha stays off until you start it again, and nothing starts it behind your back.
- **Clean stops and repair after a power cut**: Stop, Restart and every other step that stops Debian first stop Koha's services inside it in order (the web server, then the queue and the cache, then MariaDB) and only then let WSL stop Debian, so the database and the search index are never cut off mid-write. A clean stop leaves a mark. When Debian starts without it (a power cut, a forced Windows shutdown, a crash), Koha checks its database, makes a fresh backup and brings the Zebra search index up to date, rebuilding it from scratch when needed, and a Windows notification says how it went. Linux servers get the same check after an unclean reboot.
- **Data-safety settings**: MariaDB's crash-safety settings (doublewrite, a log flush at every commit, one file per table, no binary log) are pinned in `98-koha-durability.cnf`; the system journal is capped at 100 MB and one month, the panel's logs are rotated, and the weekly log rotation and TRIM timers are switched on. On Windows, when Windows shuts down, restarts or signs out while Koha runs, the tray stops Koha cleanly first: Windows asks it before the other programs, and it runs the stop through a `wsl.exe` with no console, because Windows closes console programs when a session ends; a power cut or a forced shutdown still relies on the repair above. The diagnostics warn when Windows' write-cache buffer flushing is turned off for the disk that holds Koha. The Koha window has a **Rebuild search index** button under **More actions**.
- **Shut down the PC safely**: one click at the end of the day, from the Koha window, the tray menu or *Koha - Shut down the PC safely* in the Start menu. A small window ticks off each step as it happens (the web interface and the Zebra search engine, the message queue and the cache, the database, writing everything to disk, closing Debian and its virtual disk), then Windows shuts down or restarts, whichever you chose. Nothing races Windows: Koha is completely stopped before Windows is asked. If Koha does not stop within 60 seconds, Windows shuts down anyway and Koha repairs itself at the next start. Koha starts again at the next sign-in as usual. When Windows is shut down the ordinary way instead, the tray's own stop above still runs, and it now stops all of WSL so Debian's virtual disk is closed before Windows stops it.
- **Status icon (notification area)**: the Koha icon with a coloured dot beside it, ringed in white (green running, yellow starting, red not responding, grey stopped), drawn at the size the screen's scaling asks for. If `koha.ico` cannot be read at sign-in, the icon inside `KohaEasy.exe` is used instead, and the log says why. Double-click it, or pick **Service status**, to open the Koha window. The menu also opens the staff interface, the catalog and the control panel, starts and stops Koha, restarts Koha's services, rebuilds the search index and exports diagnostics. **Close this icon** asks whether Koha keeps running in the background or stops too. If the icon crashes or is ended some other way while Koha runs, it comes back within a minute. The first time it starts, it asks Windows 11 to show it next to the clock instead of among the hidden icons (^), and a notification tells where it is.
- **Windows notifications**:
  - Koha stops responding, stops unexpectedly or recovers
  - Koha was not shut down properly, and what the repair afterwards found
  - the nightly backup succeeds (can be switched off), fails, or has not run for 36 hours
  - disk space runs low
- **Diagnostics in one click**, both ready to send to whoever supports your library, with passwords, tokens and keys removed:
  - `diagnostico_koha.txt` on the desktop: WSL and Windows versions, each service, the latest service errors inside Debian and the Windows logs of the last days. It starts nothing, so it also works while Koha is down.
  - a `.zip` on the desktop with the full WSL, Windows, Apache, MariaDB, Koha and panel logs and the system status. No configuration file is included.
- **Disk watchdog**: warns when the drive that holds Koha's virtual disk (`ext4.vhdx`) has less than 10 GB free, and critically below 5 GB. When the virtual disk holds a lot of unused space, **Compact** gives it back to Windows (needs administrator rights).
- **Languages**: the Windows tools use the panel's 22 languages.

### Installing on Windows

Open **PowerShell** (Start menu, type *PowerShell*; no need to run it as administrator), paste this line and press Enter:

```powershell
[Net.ServicePointManager]::SecurityProtocol='Tls12'; irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

If you prefer double-clicking, download [**Install-Koha.cmd**](https://github.com/PauloFBaldiFH/koha.nexus/blob/main/windows/Install-Koha.cmd) (**Download raw file**, the arrow at the top right of that page) and double-click it. It runs exactly the same line, so the install is identical. The file is not signed: if Windows shows "Windows protected your PC", click **More info > Run anyway**. It is plain text, so you can open it in Notepad and read it first. Double-click it as usual, not **Run as administrator**: Windows asks for permission only for the steps that need it. If Windows blocks it with no **Run anyway** button (Smart App Control on Windows 11, or a company policy), right-click the file > **Properties**, tick **Unblock** and click **OK**, or use the PowerShell line above, which is never blocked this way.

The installer does everything else and shows each step in plain language:

1. It checks the PC: Windows 10 version 2004 or later, or Windows 11; 64-bit; at least 4 GB of memory (8 GB recommended); at least 10 GB free on C:; virtualization turned on in the BIOS.
2. It asks for a user name and password for Debian, before anything is installed. You use them to open Debian and with `sudo`; they are not the Koha staff login. The password is never saved or logged, and it is asked again if Windows restarts before Debian is ready.
3. It installs WSL 2. Windows asks for permission once. If Windows needs a restart, the installer continues by itself after you sign in again.
4. It has WSL install Debian from Microsoft's own WSL list as `koha` in `C:\Koha\wsl`. On an older WSL it downloads the same image itself, checks its SHA-256 and imports it.
5. It creates your Debian user with `sudo` rights and enables systemd. On Windows 11 22H2 or later it also adds mirrored networking and `hostAddressLoopback` to your `.wslconfig`, keeping your own settings and a backup. Then it restarts Debian and waits until systemd is fully running before going on.
6. Before Koha is installed, it builds `KohaEasy.exe` and creates the scheduled tasks, the **Koha** icon (desktop and Start menu) and the status icon, so there is a way into Koha even if the next step stops half-way. It says where the Koha icon is, with Windows' reason when a shortcut could not be made. Then it opens the Koha control panel. The panel's own tools download with a single status line ("Downloading the panel dependencies..."); the package manager's output goes only to `/var/log/koha-easy-install/apt.log`, or to the screen with `--verbose`. Choose your language, then **1 – Install Koha server** (it asks for the timezone), and leave the panel with **Exit** when it finishes. If Koha is not fully installed, the installer says which check failed.
7. It asks whether Koha should start when you sign in to Windows. Then it builds `KohaEasy.exe`, creates the scheduled tasks, the shortcuts and the status icon, gives Debian's own Start menu entry and Windows Terminal profile the Koha icon, opens Koha to the library network (Windows asks for permission once), starts Koha, tests the library network and opens the staff interface. It shows the addresses other PCs use, by this PC's name and by its address. From then on, the **Koha** icon on the desktop starts Koha when it is off and opens the Koha window. Running the one-line command again is safe: it updates `KohaEasy.exe`, the scheduled tasks, the shortcuts and the status icon, brings the library network settings of an earlier version up to date (Windows asks for permission once), finishes a Koha install that stopped half-way (saying which check failed), and if Koha does not start it prints what Debian reports and saves the diagnostics on the desktop. When `.wslconfig` gets new settings, or Koha still runs with an earlier version's window, Koha is stopped cleanly and started again. If the Koha icon or the status icon is still missing, this command checks each part step by step, prints every error in full and saves the result in `C:\Koha\logs\diagnose-<date>.txt`:
   `irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex`

Running it again is safe: it continues from the last step it finished. An install made by an earlier version, whose Debian was called `KohaEasy`, is renamed to `koha` with its data kept. The first-access user and password are in the control panel, option 2. Everything is kept in `C:\Koha`, with the installer's log in `C:\Koha\logs`. An install made before the folder was renamed stays in `C:\KohaEasy`, and running the command again updates it there.

Real-Windows behaviour (the installer, notifications, the tray, Task Scheduler, `KohaEasy.exe`, the library network test and disk compaction) is still being checked on physical machines, so please report anything odd.

## Main menu

| # | Option | What it does |
|---|--------|--------------|
| 1 | Install Koha server | Complete installation and tuning |
| 2 | View first-access credentials | Addresses, user and password |
| 3 | Restore database | Imports a `.sql` / `.sql.gz` backup |
| 4 | Backup center | Manual backup, cloud backup, integrity test |
| 5 | Search engine & indexing | Zebra ⇄ Elasticsearch, repair indexes |
| 6 | Publish system to internet | Cloudflare Tunnel, SSL, Google Search Console |
| 7 | Diagnostics & maintenance | Status, health check, logs, optimization |
| 8 | Security center | Fail2ban, firewall, password rotation |
| 9 | Koha settings & parameters | Sizing, e-mail, super librarian, SIP2/Z39.50, clock |
| 10 | Library tools | Magic Import Tool, undo of a MARC import, SQL reports pack, school-year turnover, data-quality check, privacy (LGPD), Brazil: localization, WhatsApp / Telegram messaging, cataloguing aids, replace a MARC record, CDD lookup, Koha plugins on or off, Cutter Calculator |
| 11 | General tools | htop/nethogs, file manager |
| 12 | Schedules & cron tasks | View, explain, regenerate or edit automated tasks |
| 13 | Koha languages | Koha language packs and panel language |
| 14 | Update center | System/Koha updates and panel self-update |
| 15 | About | Project information and support |
| 16 | Reboot server | |
| 17 | Exit | |

The dialogs use a dark theme, a fixed width and adapt to small terminals. For newt's default colours in a monochrome terminal, start the panel with `NO_COLOR=1`.

## Library tools

Day-to-day tasks for the library staff, run with Koha's own command-line tools as the instance user (`koha-shell library -c ...`). Anything that changes data follows the same steps: the backup/restore lock (no nightly backup or restore can run in the middle), a **preview** (Koha's own dry run), an explicit confirmation, a **verified `PRE-*` backup** in `/var/backups/koha_sql`, and only then the real run. The tools never stop Koha's services, and the `PRE-*` backup undoes any change (**Restore database**).

| Tool | Koha scripts | Preview | Backup |
|------|--------------|---------|--------|
| 🪄 Magic Import Tool: any file, folder or archive with records, copies, patrons, loans or holds ([below](#-magic-import-tool)) | `stage_file.pl`, `commit_file.pl`, `import_patrons.pl` | The tool's own preview, then Koha's staging report and patron dry run | `PRE-IMPORT`, `PRE-PATRONS`, `PRE-CIRCULATION` |
| Undo a MARC import | `commit_file.pl --revert` | Records and items of the batch | `PRE-UNDO-IMPORT` |
| Essential SQL reports pack: 8 read-only reports (most borrowed, overdue with contacts, never borrowed, new acquisitions, expiring accounts, loans per month, items without barcode/call number, lost items), tagged so that updating or removing the pack never touches other reports | — (`saved_sql`) | Each query is checked against this Koha version | `PRE-REPORTS` |
| School-year turnover: move patrons between categories (all, over the age limit, or registered before a date) | `update_patrons_category.pl` | Native dry run with the list of patrons | `PRE-PATRONS` |
| Catalog data-quality check (read-only) | `search_for_data_inconsistencies.pl` | — | — |
| Privacy (LGPD): anonymise old loan and hold history | `batch_anonymise.pl` | Counts computed like Koha does | `PRE-PRIVACY` |
| Privacy (LGPD): delete expired patrons who borrowed nothing since (typed confirmation) | `delete_patrons.pl` | Native dry run | `PRE-PRIVACY` |

Every run is logged in `/var/log/koha-easy-install/tools/` (readable by root only: the logs may contain patron names), also viewable from the menu.

### 🪄 Magic Import Tool

**Library tools > Magic Import Tool** (*Ferramenta de Importação Mágica Maluca* in Portuguese): don't question it, just drop here what you want to import. It is the one entry for every import: the collection, its copies, the patrons, and the loans and holds of the old system, from one file, a folder or an archive holding all of them. Put it in the `importar` folder of the panel user's home (on Windows also `C:\Koha\Importar`, created the first time the tool opens): what waits there is offered first, and **Another file** opens the file explorer.

What it reads, recognised from the bytes of each file, never from its name alone:

| Input | How it is read |
|-------|----------------|
| Spreadsheets: CSV / TSV (any separator; UTF-8, Windows-1252 or Latin-1), Excel `.xlsx` and `.xls`, LibreOffice `.ods`, dBase `.dbf` with its `.dbt` / `.fpt` memo | Every sheet is a table. Each column gets a score for every MARC 21 and patron field from its header (Portuguese or English names, 40 %) and its values (60 %: ISBN and CPF check digits, dates, e-mails, call numbers...). A table is books, patrons, loans, or both; a person's name means the author next to titles and the patron next to CPFs, so authors never become patrons. A row with a book and its reader (a loans sheet) gives the book to the catalog and the reader to the patrons. Spreadsheet dates and Excel serial dates are converted; `.xls` needs `python3-xlrd`, offered when such a file shows up |
| MARC 21: ISO 2709 (`.mrc`, `.iso`) and MARCXML | Characters converted to UTF-8 with `yaz-marcdump` (from Latin-1 or MARC-8; the `yaz` package is offered when missing). Records already in Koha's layout keep their 952. Copies kept in an item field of another system (949, 950, 990, or MARC 21 holdings in 852) become one 952 each, moved with Koha's own MARC::Record: in 852 each subfield is read by its MARC 21 meaning, and in a 9XX by its values (barcode, inventory number, call number, library, item type, shelving location, copy, volume, date acquired, price, status lost/withdrawn/damaged/not for loan, notes), so any system's layout is understood. Library, item type and shelving location are taken only when Koha has them (codes or names); otherwise, and when the field has none, the library and item type chosen for the import are used. The preview lists where each subfield goes and how many values Koha did not have. Another 9XX repeated in most records, or a usual one without a numbering, is asked about, showing what each subfield was read as |
| Biblioteca Fácil database | Collection, patrons, loans and holds (details below) |
| ISIS catalogue | Collection (details below) |
| Archives: `.zip`, `.tar` (also `.tar.gz`, `.tar.bz2`, `.tar.xz`), and `.gz`, `.bz2`, `.xz` files | Unpacked inside the work folder with limits: no path outside it, no links or devices, size and count caps, zip bombs refused, archives inside archives up to three levels |
| A Koha backup (MariaDB dump of a Koha database) | Never imported: it replaces the whole catalog, so it goes to **Restore database**, which tests it in a temporary database first. In an archive with other files, the panel asks whether to restore it or import the other files |

What it cannot read is listed with what to do: MarcEdit `.mrk` text (save it as `.mrc`), a CDS/ISIS master file (export it from WinISIS as ISO 2709), a PostgreSQL custom-format export (export it again as plain SQL) or an SQL dump of another system.

How an import goes:

1. **Questions, only when needed.** A column the tool is not sure about (confidence below 0.85) is asked with its sample values, in the panel's language. So are the character set when the text reads well in more than one, ISBNs shared by different titles, and an item field it does not know. The answers about the columns are remembered (`/etc/koha-easy-install/import-profiles/`), so the next file with the same columns needs no question.
2. **Records and copies.** Rows of the same book become one MARC 21 record with one item in 952 per copy: the work key is the ISBN-13 when its check digit is right, otherwise title, first author's surname, publisher and edition; the volume always takes part, so volumes never merge. The barcode column, or else the tombo, is the barcode (a repeated one becomes `-2`, `-3`... with a note in the item), the tombo is also kept as the inventory number, a number-of-copies column gives that many items, CDD + Cutter make the call number, and the item type is the one of the copy when the file names a Koha item type, otherwise the one you pick.
3. **Patrons.** A row becomes a patron only with a personal identifier: a valid CPF, an e-mail, a card number from a patron table, or a birth date with an address. CPFs are checked (modulo 11) and a CPF or card number used twice is refused with the line; the CPF becomes the card number when there is none and is kept in a patron attribute with code `CPF` when that type exists.
4. **Preview.** Nothing is written to Koha until then: the tool shows what it found in each file, the columns and where they go, the counts, a sample of the records and the rejected lines with the reason.
5. **Commit with Koha's own tools,** as every other tool: the records through the staged MARC import (`stage_file.pl` / `commit_file.pl`; matching records kept, replaced, or always new), the patrons through `import_patrons.pl` with its dry run, the Biblioteca Fácil loans and holds in one transaction. Each part has its own confirmation and verified `PRE-*` backup, and the records can be undone with **Undo a MARC import**.
6. **Summary**: "Successfully imported X bibliographic records, Y items and Z patrons with zero manual mapping required", or how many questions were answered.

The tool is the `kei_import` Python package (standard library and Debian packages only), which the panel writes to its work folder and runs as the instance user through `koha-shell`, like Koha's own tools. The Biblioteca Fácil and ISIS files and the item fields of other systems' MARC are decoded by the panel's Perl readers with Koha's MARC::Record:

| Reader | How it works | Preview | Backup |
|--------|--------------|---------|--------|
| Biblioteca Fácil database (backup `.bkp`, or its data folder with `T09_ACER.dat`) | The panel's reader (Perl) reads the program's own tables (DBISAM 4, `T01_USUA` to `T15_RESE`, format in [docs/biblioteca-facil-format.md](docs/biblioteca-facil-format.md)) with record checksums; rows the program deleted are left out. Three steps: **collection** (copies with the same title, subtitle, edition, year, publisher, ISBN and authors become one MARC 21 record: authors in order from `T10_AUAC`, publisher and city, CDD, CDU, Cutter, keywords, literary classification, contents from `T12_INDC`, language; one item in 952 per copy with the tombo as barcode, `BF<number>` when the tombo is missing or repeated, copy, volume, location, acquisition date, withdrawn, not for loan), then the MARC import; **patrons** (card number = reader code, CPF checked and kept in the `CPF` attribute when that type exists, class and shift in sort1/sort2, RG, parents and notes in the patron notes, deactivated readers restricted), then `import_patrons.pl`; **loans and holds** (open loans to `issues`, returned ones to `old_issues`, holds still valid to `reserves`, linked by card number and barcode, one transaction; what is already in Koha is skipped). Operators and their passwords are not migrated | Tables, counts, checksum errors, the old program's loan rules and a sample of the records; then Koha's staging report, the patron dry run and the loans and holds that can be linked | `PRE-IMPORT`, `PRE-PATRONS`, `PRE-CIRCULATION` |
| ISIS catalogue (PostgreSQL backup: `.backup` / `.sql`, also gzip, bzip2, zip or `INSERT` dumps) | The panel's reader (Perl) reads the `pg_dump` of the ISIS database (format and rules in [docs/isis-format.md](docs/isis-format.md)): noise before and after the dump left out, encoding detected, columns matched by name. One MARC 21 record per MFN (authors, `<article>` nonfiling marks, place / publisher / year split from the imprint, CDD and Cutter, subjects from `<A><B>` or `;` lists) with one item in 952 per tombo of the `registro` field: copies split on hyphens, commas and ISIS carets (`^f`), volumes (`v1`, `I`, `1ª série`) to $h, ranges (`669 a 672`) expanded, stray letters, `$` and call numbers typed in the field left out, `(Baixa)` as withdrawn, `ISIS<mfn>` when there is no tombo and `ISIS<mfn>-<n>` when it repeats, the field as typed kept in the internal note; the occurrences table adds notes and marks lost copies. Text cleaned of `Informação não encontrada` fillers, control characters and `Ẃ` for `ª`. The export has no patrons or loans | Tables, columns and where they go, every cleaning count and the MFNs to check, a sample of the records; then Koha's staging report | `PRE-IMPORT` |

- The Biblivre, SophiA and Pergamum item fields follow their usual export layout; the preview shows the result before anything is written.
- The column scoring was built from the usual column names of Brazilian library programs and spreadsheets, and tested with synthetic files only. The preview lists every column, where it goes and the ones left out, so check it before confirming.
- The Biblioteca Fácil database reader was built from a backup of the program's empty template database. The loan, hold and patron tables were checked with a synthetic backup only, so compare the preview's counts with the old program before confirming.
- The ISIS reader was built from one library's export. Titles with a caret inside may keep an ISIS subfield letter glued to the next word, so the preview lists their MFNs for a check in Koha.

### Brazil: localization

**Library tools > Brazil: localization**. Nothing here is applied during the installation or by a schedule: each option acts only when you choose it, follows the same steps as the other tools (lock, preview, confirmation, verified `PRE-*` backup) and can be undone. The migrations from other systems are in the [Magic Import Tool](#-magic-import-tool).

| Tool | How it works | Preview | Backup |
|------|--------------|---------|--------|
| Check patron CPFs (read-only) | Card number, username, sort1/sort2 or the `CPF` attribute: valid, invalid, shared by two patrons | — | — |
| Pimaco label templates | Sheets 6180, 6181, 6287 (Letter) and A4256, A4251 (A4) plus 3 layouts (spine, barcode, title and barcode) in Koha's label creator; updates or removes only its own templates | Summary before the change | `PRE-LABELS` |
| Cataloguing card (ficha catalográfica) | Stylesheets that wrap Koha's default detail view (OPAC and staff interface, one per installed language) and add the card below the record, with a print button; set in `OPACXSLTDetailsDisplay` / `XSLTDetailsDisplay`. The previous values are kept and **Hide the card** puts them back; the files are rewritten each time the panel starts, so they follow Koha updates | Old and new values | `PRE-FICHA` |
| Brazilian holidays in the calendar | National holidays of a year, Carnival (Monday and Tuesday), Good Friday and Corpus Christi (Easter by the Meeus/Jones/Butcher algorithm) and an optional municipal holiday, for one library or all; days already in the calendar are skipped and **Remove** takes out only the days added by the panel | Dates with the weekday | `PRE-CALENDAR` |
| Government census reports (MEC/INEP/IBGE) | 10 read-only SQL reports in Koha's saved reports with the figures asked by the INEP School and Higher Education censuses, the IBGE surveys, the SNBP registry of public libraries and the MEC course evaluations: summary of the year, active collection by item type and library and by CDD class, volumes added, circulation by month, loans by item type and patron category, readers by category, sex and age group, losses and withdrawals (with the replacement value), age of the collection by CDD class and weeding candidates. Koha asks for the year when a report runs. Installed and removed separately from the essential pack (tag `[koha-easy-installer-censo:...]`) | The reports, new or updated; a report the Koha schema cannot run is skipped | `PRE-CENSO` |
| ABNT references and bibliographies (read-only) | References by ABNT NBR 6023:2018 built from the MARC 21 records (books, chapters and articles through 773, theses through 502, online documents through 856; SURNAME, Forenames; up to three authors, then *et al.*; organizers; entry by title with the first word in capitals; `[S. l.]`, `[s. n.]`; title of the book or journal in bold), in alphabetical order, from a Koha list, the items added in a period, a call number class, a library's whole collection or record numbers. Written as HTML with the NBR 14724 presentation (A4, Times 12, single spacing, a blank line between references; opens in Word or LibreOffice) and as plain text, optionally with the call numbers and copies under each reference (collection listing) | The first references | — |

- The label sizes are the Avery equivalents of each Pimaco sheet: do a test print on plain paper first and adjust the template in Koha if your printer shifts the page.
- The card starts closed on the record page, behind **Show the AACR2 catalogue card**, and opens with a click.
- The card follows the AACR2 layout used by Brazilian libraries (call number column, hanging indent, numbered subjects, roman-numbered added entries). Below it, the reference of the record by ABNT NBR 6023 (essential elements) for readers to copy.
- The census reports count what Koha records: in-library use needs Koha's *local use* check-ins, the sex and age groups need those patron fields, and the CDD class comes from the first three digits of the call number. Check each figure against the form of the census before sending it.
- Carnival and Corpus Christi are *ponto facultativo*, not national holidays: remove them in Tools > Calendar if the library opens. Consciência Negra (20/11) is added from 2024 on.

### Messaging: WhatsApp and Telegram

**Library tools > Messaging: WhatsApp and Telegram**. Koha already writes the notices (checkout, check-in, overdue, due, hold) and hands those of the SMS type to the SMS::Send driver named in the `SMSSendDriver` preference. The panel installs such a driver (`SMS::Send::KohaEasy::Gateway`): each notice goes to Telegram when the patron linked the library's bot, otherwise to WhatsApp. Nothing changes in Koha until **Send Koha notices** is turned on, and turning it off puts the previous `SMSSendDriver` back (verified `PRE-MESSAGING` backup both ways).

| Option | What it does |
|--------|--------------|
| WhatsApp gateway | A gateway of the library's own: Evolution API v2 (`POST /message/sendText/<instance>`, `apikey` header) or another one that accepts `{"number", "to", "text"}` with a Bearer token |
| Telegram bot | The token from @BotFather is checked with Telegram (`getMe`). Patrons open the bot, tap Start and share their own contact; a job every two minutes links the chat to the number (`/stop` undoes it) |
| Country and area code | Numbers are completed and corrected before sending: country code (Brazil by default, or any other), area code (DDD) for numbers without one, trunk and carrier prefixes removed, and the 9th digit of Brazilian mobiles added |
| Send a test message | Through the same SMS::Send path Koha uses, as the instance user |
| What Koha needs | Checks `SMSSendDriver`, the SMS versions of the notices, overdue rules with SMS and patrons with SMS numbers and preferences; offers to create short SMS versions of the notices that have none (`PRE-NOTICES`) |
| Check the patrons' phone numbers | Read-only report with the same rules; the corrected numbers are written only on confirmation (`PRE-PHONES`) |

The settings (with the tokens) are in `/etc/koha/sites/library/kei-messaging.conf`, readable by root and Koha only. When the notices are on, the SMS queue is also sent every two minutes (`/etc/cron.d/koha_messaging`).

### Cataloguing aids: PHA, Cutter-Sanborn, CDD

**Library tools > Cataloguing aids**, read-only for the catalogue.

- **Author notation**: the entry right before the name in the table, the initial of the surname, the number and the initial of the title (the initial article never counts, and a title starting with "l" gets a capital L); prefixes read as one word (La Fonte, O'Donnel) and M' / Mc as Mac; institutions by the first word and anonymous works by the first word of the title, as in the PHA explanation. From a catalogue record it reads 100 / 110 / 111, 245 (with its nonfiling indicator) and 082, and lists the call numbers that already use the same number in that class, with the free numbers right before and after it.
- **The tables are not distributed with the panel**: the PHA table (Heloísa de Almeida Prado, T. A. Queiroz) and the Cutter-Sanborn tables are copyrighted. Each library loads its own copy as a text file (one entry and its number per line; the PHA rows can be typed as printed, entry - number - entry; the PDF of the PHA book is also read, see [Cutter Calculator](#cutter-calculator)). The file is checked before it is kept: entries per letter, numbers out of order (typing mistakes) and repeated entries.
- **CDD**: the ten main classes are built in; the library can load its own schedule (number and caption per line) to search by number or by word, and every lookup also shows how the catalogue already uses the number.

### Replace a MARC record (staff interface)

**Library tools > Replace a MARC record** installs `marc_replace.pl` in Koha's staff interface (`/cgi-bin/koha/tools/marc_replace.pl`). Optionally it also adds shortcuts in the staff interface: **MARC Injection & AI** next to **New record** (and in the New menu of the record pages), which opens the AI cataloguing below to draft a new record; **Replace via MARC / AI** next to **Edit** on each record page, which opens the page with that record (MARC file or text, or photos of the book), always through the preview before anything is replaced; **Replace the record (MARC file)** in the Edit menu of each record; and **Replace a MARC record** and **AI cataloguing** in the tools of the cataloguing home page (`/cgi-bin/koha/cataloguing/cataloging-home.pl`). It replaces a record, found by its biblionumber, with an `.mrc` or `.xml` file or pasted text (Biblioteca Nacional `245 10 |a`, MarcEdit or yaz-marcdump lines):

- login with the `edit_catalogue` permission and a CSRF token (Koha 24.05+ `cud-` operations);
- a preview first; then, in one transaction, the current record is locked and compared with the preview (nothing is replaced if it changed), saved as MARCXML in `/var/lib/koha/library/kei-marc-replace/` (downloadable from the page, and accepted back to undo) and replaced with Koha's `ModBiblio`;
- item fields in the file are always left out: the items are never touched;
- MARC-8 / Latin-1 files are converted by Koha's own `MarcToUTF8Record`.

The page is checked with Koha's Perl modules before it is installed; removing it keeps the saved versions.

#### AI cataloguing (photos of the book)

Two more tabs of the same page catalogue a book from photos of its cover, title page and verso of the title page (with the CIP block):

- **AI settings** (staff allowed to change the system preferences only): the vision model, either a cloud API with a token or key (OpenAI, Anthropic, Google Gemini with a key from Google AI Studio, or any OpenAI-compatible service) or a model on the library's own network (Ollama `http://localhost:11434` or LM Studio `http://localhost:1234/v1` with a vision model such as `qwen2.5vl`, `llama3.2-vision` or `gemma3`). The settings are kept in `kei-marc-replace/vision.conf`, readable by the Koha instance user only; the token is never shown again, and a token is refused over plain `http` to a server outside the local network. **Test the connection** lists the models of the server. No token ships with the panel.
- **Cataloguing instructions for the model** (same tab): the instructions sent with every book, before the fixed answer format. The default ones ask for cataloguing by MARC 21, AACR2 and ISBD in the language of cataloguing, from the chief sources and the context of the book, with a complete example record holding the fields in common use (020, 040, 041, 043, 082, 090, 100, 240, 245, 246, 250, 260, 300, 336-338, 490, 500, 504, 505, 520, 521, 546, 650, 651, 655, 700, 830, 942): the model fills those the photos support, and the library deletes the ones it does not use instead of adding fields by hand. The library can rewrite them (`{language}` becomes the language of cataloguing); they are kept in `kei-marc-replace/vision-prompt.txt`, and **Restore the default instructions** brings the default back.
- **AI cataloguing**: the photos go to the model, with an optional **instructions for this book only** field (for example, "the author is also the illustrator"), which takes precedence over the general instructions, is sent with those photos only and is never saved: the next book starts with an empty field. The model which answers with the bibliographic data as JSON (checked against a fixed schema: nothing invented, placeholders dropped). The national rules are then applied by `KohaEasy::Cataloguing::Rules`: AACR2 and ISBD punctuation (245 `:` `/`, 260 with `[S.l.]` / `[s.n.]`, 300), names inverted as Brazilian cataloguers do (`Assis, Machado de`, `Andrade Filho, José de`), 245 non-filing characters, ISBN check digits (wrong ones go to 020 `$z`), the CDD printed in the CIP block (otherwise the model's suggestion, flagged for checking) in 082 and 090, and the **author notation of the library's own PHA or Cutter-Sanborn table**, computed by a Perl port of the panel's algorithm, so the page and **Cataloguing aids** give the same notation.
- The librarian corrects the draft next to the photos, and a **mandatory preview** follows. Only then is the record added with Koha's `AddBiblio`, in one transaction under a database lock, after the ISBN is checked against the catalogue again (a record with the same ISBN needs an explicit tick), with a copy of the record and of the model's answer saved in `kei-marc-replace/vision/`. A form sent twice adds nothing. With a biblionumber, the draft goes to the replacement above instead (with its lock and saved version).

The two modules are installed with the page in `/usr/local/lib/site_perl/KohaEasy/Cataloguing/` and removed with it (the settings stay with the saved versions).

### CDD lookup in the cataloguing (staff interface)

**Library tools > CDD lookup** puts the whole CDD (Dewey) in Koha's cataloguing, at `/cgi-bin/koha/cataloguing/cdd_lookup.pl`.

- **The CDD is not distributed with the panel**: the DDC is copyrighted by OCLC. **Build the index** asks for the library's own copy (the PDF, or a `.txt` with its text; a PDF is read with `pdftotext`) and builds a SQLite index on the server (`/var/lib/koha/<instance>/kei-cdd/cdd.sqlite`, readable only by root and the instance). The schedules, Tables 1 to 6 and the alphabetical list of subjects are read, with bracketed (not used) and optional numbers marked. A file with fewer than 100 schedule entries is refused and the previous index is kept. A scanned PDF has no text: use the text of an OCR.
- **The page** searches by number (`869.3`, `869,3`, `T1—09`) or by words of the subject (accents and plurals ignored). Each number shows its place in the hierarchy, the notes (with the numbers in them as links), the subdivisions, the subjects of the list, and, for a number not printed in the schedules, **how it was probably built** (base number plus Table 1, Table 2 through —09, Table 3 in 810–899, Table 4 in 420–499), marked as a hint. **Build a number** adds a table notation to the number as you type.
- **In your library**: next to each result, how many titles and items of the catalogue use that class (with and without its subdivisions, from the call numbers of the items), the titles themselves, and how the library classified titles with the searched words.
- **Install the page** optionally adds a **CDD** button next to 082, 083, 090, 092 `$a` and the item call number (952 `$o`) in the cataloguing forms, and **CDD lookup** in the tools of the cataloguing home page (a marked block in `IntranetUserJS`, verified `PRE-CDD` backup first). The button opens the lookup with the number already in the field or with the subjects and title of the record as suggestions; **Use in the record** puts the number in the field (082 and 083 get the number and `$2` the edition when empty; 090, 092 and 952 keep the author notation after it). **Copy** copies it.
- **Remove the page** removes the page, the buttons and the module `KohaEasy/CDD.pm`; the index is kept.

### Cutter Calculator

**Library tools > Cutter Calculator** (Calculadora Cutter) works out the call number of a record: the class and the author number from the library's own Cutter-Sanborn or PHA table, in the panel and in Koha's cataloguing, at `/cgi-bin/koha/cataloguing/cutter_calculator.pl`.

- **The tables are not distributed with the panel**: the editions of the Cutter-Sanborn table and the PHA table (Heloísa de Almeida Prado, T. A. Queiroz) are copyrighted. **Load the Cutter-Sanborn table** asks for the library's own copy as a text file, one number and its entry per line as the three-figure table prints them (`848     Assis`, `  127     Abbot, J.`; the leading spaces may vary). **Load the PHA table** takes a text file or the PDF of the book, even a scanned one: the panel reads its text with `pdftotext` or, when the pages are images, with the Tesseract OCR (Portuguese) on the server, page by page. The rows of the book are put in its order and a number the OCR misread is corrected when one similar digit puts it back in the decimal order of the table; the report lists each correction to check against the book. Each table is checked before it is kept (entries per letter, numbers out of order, repeated entries) and saved in `/etc/koha-easy-install/tables/`, the same tables the AI cataloguing and Cataloguing aids use.
- **The notation** follows the same rules everywhere (`KohaEasy::Cataloguing::Rules`): the entry right before the name in alphabetical order, the initial of the surname, the number and the initial of the title without its article (`Assis, Machado de` + *Dom Casmurro* = `A848d` with Cutter-Sanborn). The main entry is automatic: the author, or the first word of the title (without its article) when the work has no author; it can also be set to a person, an institution (first word) or the title. On the page a name typed in direct order (`Machado de Assis`) is read as `Assis, Machado de`.
- **Options on the page**: the table (PHA or Cutter-Sanborn, when both are loaded), the classification, **Without the letter of the title** (`A848` instead of `A848d`), **Edition** (from the 2nd on: `A848d 2. ed.`; read from 250) and **Copy** (`ex. 2`; the copy number of the item, 952 `$t`, when the button is used there).
- **The gear** (Settings) keeps the defaults of each librarian in the browser: the table, the classification, whether the letter of the title is added and whether the edition and the copy number are added when the record has them. They apply every time the page opens; a field changed by hand on the page wins.
- **The classification** of the call number is CDD, CDU or the library's own codes (`LIT`, `INF J`). It is the one chosen in the settings; otherwise it is read from the class already typed, then from the record (082 CDD, 080 CDU, 084 other), and then from how most of the catalogue's call numbers look. Without a class in the field, the class of the record is used (082, 080 or 084, as the classification says).
- **Suggested classes**: when the record has no class, or only a CDD class without decimals (`869`), the page lists classes from the catalogue: the classes of other titles of the same author, of titles with the same subjects (650), and of titles with the same words in the title, plus, for CDD, the numbers the CDD index of **CDD lookup** gives for the subjects and the title when that index was built. They are hints counted from the catalogue, not a classification: the best one fills a **Suggested call number**, and **Use this class** puts any of them in the form. The panel has no CDU table, so for CDU the class comes only from 080 or from the catalogue's own CDU call numbers. The AI cataloguing (Replace a MARC record) is the place where a model suggests a CDD from the photos of the book; this page sends nothing out.
- **The page** shows the number as the author is typed, the table entry used and, with a class number, the call number and the call numbers of the catalogue that already use the same number in that class, with the numbers right before and after it and whether they are free to use. **Copy** copies the number or the call number. `?format=json` gives the same result as JSON (`code` is the full number with the edition and the copy, `notation` the number alone).
- **Install the page** optionally adds a **Call number** button next to 090 and 092 `$a` and the item call number (952 `$o`), and a **Cutter** button next to 090 and 092 `$b`, in the cataloguing forms, after the CDD button when there is one, and **Cutter Calculator** in the tools of the cataloguing home page (a marked block in `IntranetUserJS`, verified `PRE-CUTTER` backup first). The buttons open the page with the author (100, or 110/111), title (245 and its non-filing indicator), class (the field, or 090), 080 / 082 / 084, subjects (650) and edition (250) of the form; in the item editor they are read from the record. **Use in the record** puts the class in `$a` and the author number in `$b` of 090 / 092, or the whole call number in the item call number (keeping a location prefix such as `R`).
- **Calculate a Cutter number** does the same in the panel with the table you pick, with the numbers used in the class. **Remove the page** removes the page and the buttons; the tables are kept.

### Koha plugins (on or off)

**Library tools > Koha plugins** turns on or off Koha's own plugin system (**Administration > Manage plugins**), which a new Debian instance ships turned off (`<enable_plugins>0</enable_plugins>` in `koha-conf.xml`).

- **Turn Koha plugins on** sets `enable_plugins` to 1, adds `<pluginsdir>` when it is missing (`/var/lib/koha/<instance>/plugins`, created for the instance user), sets `UseKohaPlugins` on Koha versions that still have that preference, and restarts Plack and the background workers.
- **Turn Koha plugins off** sets `enable_plugins` back to 0 and changes nothing else: the plugin files and their data stay, and turning plugins on again brings them back as they were.
- **Where plugins can be installed from**: `.kpz` upload plus the plugin repositories, or only the plugin repositories (`plugins_restricted`). When no repository is set, the panel offers to add the ones `koha-conf.xml` lists as examples (ByWater Solutions, Theke Solutions, PTFS Europe).
- **Register plugins copied into the folder** runs Koha's `koha-plugins --install` (or `install_plugins.pl` on older Koha) after a verified `PRE-PLUGINS` backup, for plugins unpacked into the plugins folder by hand.
- Every change writes a new `koha-conf.xml` only when it is well-formed and reads back with the new values; otherwise the file is left as it was. The previous file stays next to it as `koha-conf.xml.bak-<date>`.

## Automated tasks

Installed in `/etc/cron.d/koha_tasks`:

| When | Task |
|------|------|
| Daily 23:00 | Compressed SQL backup (verified, optional cloud upload) |
| Sundays 03:00 | MARC21 export of bibliographic and authority records |
| Daily 01:30 | Session and Zebra queue cleanup (`cleanup_database.pl --confirm`) |
| Daily 05:00 | Plack restart (keeps memory low) |
| Every 2 min | Zebra indexing watchdog: keeps Koha's indexer daemon (`koha-indexer`) running and restarts it if records wait more than 10 min |
| Every 5 min (Elasticsearch only) | Elasticsearch indexer watchdog |

E-mail notices are left to Koha's own schedule (`koha-common`): overdue and advance notices once a day and the message queue every 15 minutes, for the instance enabled with `koha-email-enable` (done at installation and in **Koha settings > Configure email**). Schedules written by older versions of the panel are upgraded automatically: the 01:30 cleanup gets `--confirm` (without it, it only reported what it would delete) and the old 08:00/08:05 e-mail jobs, which duplicated Koha's, are removed once e-mail is enabled.

## Important files

| Path | Content |
|------|---------|
| `/root/koha_credentials.txt` | First-access credentials |
| `/etc/koha/sites/library/koha-conf.xml` | Koha instance configuration |
| `/var/backups/koha_sql`, `/var/backups/koha_marc` | Local backups |
| `/etc/koha-easy-install/` | Panel settings (language, backup) |
| `/var/log/koha-easy-install/` | Panel, APT and validation logs (`tools/`: library tools, root only) |
| `~/importar` (`C:\Koha\Importar` on Windows) | Drop folder of the Magic Import Tool |
| `/etc/koha-easy-install/import-profiles/` | Column answers the Magic Import Tool remembers |
| `/var/lib/koha/library/kei-xslt/` | Cataloguing card stylesheets (only while the card is enabled) |
| `/etc/koha/sites/library/kei-messaging.conf` | WhatsApp / Telegram settings and tokens (root and Koha only) |
| `/usr/local/lib/site_perl/SMS/Send/KohaEasy/Gateway.pm` | The messaging driver of Koha (with `KohaEasy/Messaging.pm`) |
| `/etc/koha-easy-install/tables/` | Author tables and CDD schedule loaded by the library |
| `/var/lib/koha/library/kei-marc-replace/` | Records as they were before each replacement |
| `/etc/koha-easy-install/windows.conf` | Windows only: what the Windows tools tell the panel (network mode, automatic start...) |
| `C:\Koha\` | Windows only: `Uninstall-Koha.cmd`, `bin\` (scripts, `KohaEasy.exe` and `koha.ico`), `logs\`, `Backups\`, `state.json` |

The installation shows seven numbered steps, one line per task with a small Pac-Man progress bar, and a final screen with the addresses of the catalog and the staff interface. The commands' own output never reaches the screen: it is kept in `/var/log/koha-easy-install/apt.log`. If a task fails, the panel shows the failed step, what to check and the last lines of that log, which is the file to send to IT support.

The panel's other long tasks look the same: switching the search engine, repairing the search index, setting up the Cloudflare Tunnel, updating the system, validation, service repair, deep maintenance and language updates. Their output goes to `/var/log/koha-easy-install/` (for example `search-engine.log`, `zebra-rebuild.log`, `cloudflare.log`, `restore.log` and `apt.log`). Backup restores and the tools the panel installs on demand (Midnight Commander, htop and nethogs) look the same.

The panel's dialogs are drawn with `dialog`, which the panel installs, so buttons, menu items and check boxes also take mouse clicks in terminals that report the mouse: Windows Terminal, the Linux desktop terminals (GNOME Terminal, Konsole, xterm), PuTTY and most SSH clients. The Linux text console only does so with `gpm` installed. `KEI_UI=whiptail` keeps the older keyboard-only look.

On a Linux PC with a graphical desktop, the panel adds a **Koha** launcher (`koha-descomplicado.desktop`) to the applications menu of the user who ran it with `sudo`, and, the first time, to that user's desktop. It opens the panel in a terminal and asks for the `sudo` password.

## Uninstall

`uninstall.sh` **permanently deletes** Koha, its databases, local backups and settings, and asks for confirmation first:

```bash
sudo bash uninstall.sh          # asks you to type APAGAR to confirm
sudo bash uninstall.sh --yes    # no questions (automation)
```

Copy your backups somewhere else before running it.

On Windows, double-click **Uninstall-Koha.cmd** in `C:\Koha`, or use **Settings > Apps > Koha (koha.nexus) > Uninstall**. It asks you to type `KOHA` to confirm, then removes the Debian `koha` (with the Koha databases), the shortcuts, the status icon, the scheduled tasks, the firewall rule (Windows asks for permission once) and the folder. The `Backups` folder is kept unless you choose to delete it too. WSL itself and your `.wslconfig` stay.

## Tests (for contributors)

`tests/` has a [bats-core](https://github.com/bats-core/bats-core) battery that runs the panel against a real MariaDB: corrupt, truncated and empty backups, MariaDB down or refusing the login, full or unwritable disks, CTRL+C / lost SSH connection in the middle of a restore, locks shared with the nightly backups, indexing after engine switches and restores, Debian/Ubuntu releases on amd64/arm64, the library tools (dry run before any change, lock, verified backup, `koha-shell` quoting), the Brazil tools (Latin-1 MARC migration to 952, CPF check digits, movable holidays, label templates, cataloguing card, collection spreadsheets, census reports, ABNT references), the messaging driver (against a WhatsApp / Telegram test double), the author notation, the Cutter Calculator and CDD lookup, the Koha plugins switch in `koha-conf.xml`, `marc_replace.pl` (run as a CGI), the schedule upgrade, the WSL mode, the QR code / browser / link sign-in, and the Windows tools (their PowerShell tests run with [Pester 5](https://pester.dev) when `pwsh` is installed).

```bash
sudo apt-get install bats mariadb-server memcached whiptail yaz xsltproc python3 \
     libmarc-record-perl libmarc-xml-perl libsms-send-perl libcgi-pm-perl libmodern-perl-perl
sudo KEI_TEST_SANDBOX=1 tests/run.sh
```

**Only on a disposable container or VM:** the tests replace the `koha_library` database and install test doubles for the `koha-*` tools and `systemctl`. `tests/run.sh` refuses to run next to a real Koha.

## Translations (for contributors)

The panel texts are in English inside `installer`; each language has a dictionary in `lang/<code>.cache` (`base64(English)|base64(translation)`). The panel itself is pure Bash; the Python scripts below are optional contributor tools.

- Wrap every user-visible text in `$(t "...")`. Variables must be escaped so the English text reaches `t()` unchanged: `$(t "Backup saved in \${file}")`.
- Check coverage and repair dictionaries: `python3 i18n_common.py` / `python3 i18n_common.py --fix`
- Translate only what is missing: `python3 gen_all_langs.py` (offline, Argos Translate) or `python3 gen_lang.py` (online).
- Translations that lose a variable or `%s` are rejected automatically and English is shown instead.

After changing `PANEL_VERSION`, run `python3 i18n_common.py --fix` (each dictionary is stamped with the panel version, and outdated dictionaries are only used as a last resort).

After changing `installer`, regenerate the checksum used by the self-update:

```bash
sha256sum installer > installer.sha256
```

## License

koha.nexus is free software under the [GNU General Public License v3.0 or later](LICENSE) (GPL-3.0-or-later), the same license as Koha itself. You can use, study, share and modify it; if you distribute modified versions, they must stay under the GPL with their source code available. It comes with **no warranty**.

## Support the project

- Pix (Brazil): `076.650.449.21`
- Bitcoin (BTC): `bc1qw0kvacdkzul0panuppxcv90y08ah443m2z89tx`
- ⭐ Star the repository and share it with other libraries.

---

Created with dedication by **Paulo F. Baldi FH** — Library Assistant, Castro Alves Public Library, Palotina, Paraná, Brazil.

<sub>The Koha name and logo belong to the Koha community (koha-community.org); this installer is an independent project.</sub>
