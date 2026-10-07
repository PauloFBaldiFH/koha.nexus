# Koha Nexus - Development Roadmap & Master Prompts

This document contains the architectural "Master Prompts" to guide AI-assisted development. To maximize context and save tokens, each Subject should be executed in a clean, fresh chat session.

---

## Subject 1: Core UI/UX, Themes, Panel Cleanup & Database Transfer Hub
**(Status: Pending)**

```text
Act as a Senior Python UI/UX Developer and Systems Integration Specialist. I need to polish the core interface, theme stability, and database transfer workflows of our Textual-based Koha management panel. Please implement the following refactoring:

1. Layout & Cleanup:
- Remove the broken "screenshot" and "maximize focused widget" options entirely.
- Move the "Ferramenta de Importação Mágica" to the primary main menu so it has top visibility.
- Add an emoji to the main dashboard title: "🎛️ Painel de Controle".
- Remove all CPF verification checks and LGPD/privacy disclaimer blocks from intake forms to ensure a frictionless flow.
- Hide/remove manual upload prompts for Cutter, PHA, and CDD tables. Keep this logic dormant in the backend or use automated rules; do not clutter the UI with it.

2. Themes & Animations:
- Fix Theme Persistence: Ensure the selected theme saves permanently and restores upon app restart.
- Set the default theme to "Flexoki".
- Fix the CSS/Hover bug in the "Search for commands" screen where hover colors blend poorly with the background.
- Adjust the "Pacman" animation: Only use the Pacman animation for infinite/indeterminate loading loops. For standard percentage-based progress bars, use a clean, normal progress bar.

3. "Copy to Clipboard" Helpers:
- Add a highly visible "[📋 Copiar Comando]" button wherever terminal/PowerShell commands, Pix keys, BTC addresses, or GitHub links are shown.
- Ensure the copied text is clean (no ANSI codes) and provide visual feedback (e.g., changing to "✓ Copiado!").
- Update the PowerShell instructions text to explicitly state: "Abra o PowerShell como Administrador e execute:".

4. Seamless Database File Drag & Drop & Direct Download (SCP/SFTP Hub):
- Database Restore Drag & Drop Zone:
  * In the database restoration view, create an intuitive drop area / file input where the user can drag and drop a SQL or gzip dump file (.sql / .sql.gz) straight into the terminal interface.
  * Once the path is dropped/provided, the panel handles transferring the file to the target Koha server automatically via SCP/SFTP (Paramiko) with an active progress bar, staging it for safe MariaDB ingestion.
- One-Click Backup Download to Local Machine:
  * In the backup section, provide a prominent "[⬇️ Baixar Backup Recente]" button next to newly completed server dumps.
  * When clicked, the backend pulls the latest backup archive via SCP/SFTP and writes it directly to the user's local Downloads folder (resolving cross-platform paths: Windows `%USERPROFILE%/Downloads`, Linux/macOS `~/Downloads`, or WSL host path `/mnt/c/Users/<user>/Downloads`).
  * Display transfer metrics (file size, speed, ETA) and trigger a clear completion toast when finished.

5. Terminal & Window Optimization:
- Ensure the Python app launches maximized by default. Use `sys.stdout.write("\x1b[9;1t")` on startup, and update the Windows `.bat` launcher to use `wt.exe -M wsl -d <distro>`.
- Remove the broken text-based internal browser. Replace it with a native OS launcher (`webbrowser.open(url)`) or a lightweight `pywebview` window so Koha interfaces open with full JS/CSS support.
```

---

## Subject 2: Ultra-Intelligent "Magic Importer" & Database Management
**(Status: Pending)**

```text
Act as a Principal Data Engineer, AI Systems Architect, and MARC21 Cataloging Specialist. I need to build the ultimate, ultra-resilient "Magic Importer" and Database Manager for the Koha ILS using Python (Pandas, PyMARC, SQLAlchemy, Pydantic) coupled with LLM semantic intelligence (local Ollama or OpenAI/Gemini APIs).

The tool must ingest legacy catalog dumps regardless of corruption, encoding issues, or total absence of schema headers, translating raw dumps into pristine MARC21 bibliographic records and standard Koha entities.

Implement the following architectural modules:

1. Zero-Header & Blind Semantic Column Ingestion:
- Ingestion formats: CSV, TSV, XLSX, JSON, XML, SQL dumps, and raw MARC/ISO-2709.
- Blind Column Auto-Detection: If column headers are completely missing, illegible, or cryptic (e.g., "COL1", "CAMPO_X", "A1"):
  * Sample 5 to 10 random rows of the raw data.
  * Pass the sampled matrix to the AI inference pipeline to classify each column's semantic identity (Title, Author/Statement of Responsibility, ISBN, Publication Year, Publisher, City, Call Number, Subject/Topical Term, Barcode, etc.).
- Encoding Auto-Healing: Automatically detect and convert legacy encodings (CP1252, ISO-8859-1, IBM850/MS-DOS) to clean UTF-8 before parsing.

2. Catalog Modernizer & Smart Casing Normalization (DOS/All-Caps Cleanup):
- Legacy catalogs from the 80s/90s (Microisis, ISIS, dBase, CDS/ISIS) often contain records written ENTIRELY IN CAPITAL LETTERS.
- Implement an AI/NLP contextual Title-Casing engine:
  * Do NOT use naive Python `.title()` or `.capitalize()`.
  * Contextually preserve lowercase particles, prepositions, and articles (e.g., "de", "da", "do", "das", "dos", "e", "em", "por", "von", "van").
  * Retain full uppercase for authentic acronyms and Roman numerals (e.g., "ABNT", "UNESCO", "III", "XIV", "EUA", "UFPR").
  * Properly capitalize personal names, surnames, corporate bodies, and geographic places while respecting sentence capitalization for general subtitles and notes.

3. Automated Contextual MARC Synthesis (Tag 008 & 245$c):
- Fixed-Length Field 008 Generator:
  * Automatically construct the 40-character fixed-length 008 control field.
  * Extract/infer the publication date into positions 07-10 (Date 1).
  * Infer language code into positions 35-37 (e.g., "por", "eng", "spa") using fast text language detection.
  * Default record type to 's' (single date) or 'n' (unknown) and set cataloging source conventions correctly.
- Dynamic Statement of Responsibility (245$c) Generation:
  * If the input provides author data (Tag 100/700) or statement data, format 245$c cleanly (e.g., "por Paulo Fernando Baldi Filho").
  * If author fields are populated but 245$c is missing, synthesize 245$c contextually from Tag 100/700 without duplicating syntax.

4. Polymorphic Separation & Entity Segmentation:
- Autonomously segment mixed dump files into distinct staging streams:
  * Bibliographic Records (Books, Maps, Serials).
  * Patrons / Borrowers (synthesized into Koha `borrowers` schema).
  * Authorities (Names, Subjects, Series).
  * Item/Holding Data (Koha 952 tags: barcode, branchcode, shelving location, call number).

5. MARC Replace & Safe Update Fallback:
- When running in "MARC Replace" mode:
  * Check for existing record target (`biblionumber` or matching ISBN/ISSN).
  * Bugfix rule: If `biblionumber` is missing or the target record cannot be verified, gracefully fall back to creating a new MARC21 bibliographic record instead of throwing an unhandled exception or aborting the batch.

6. Safety Validation Preview & TUI Transaction Gate:
- Terminal Drag & Drop integration: Allow drag-and-drop of database files directly into the TUI file input.
- Direct database export/download utility from the terminal panel.
- Human-in-the-Loop Review Gate: Prior to writing to MariaDB or triggering `koha-elasticsearch --rebuild`, render a structured preview report:
  * Total items scanned, categorized entities count (books vs patrons).
  * Number of casing normalizations performed and encoding corrections made.
  * Flag critical anomalies for human review with an explicit [Confirm & Import] safety lock.
```

---

## Subject 3: Centralized AI Settings & Agentic Worker Architecture (Koha API / Search Engine)
**(Status: Pending)**

```text
Act as a Principal AI Architect and Koha Integration Engineer. I need to redesign our AI Assistant architecture. 

Direct SQL manipulation by the LLM is deprecated due to safety and state desynchronization risks. Instead, the AI Assistant must operate as a secure, tool-calling Agent/Worker that interacts exclusively with Koha's official REST API (/api/v1/), Koha's internal search engines (Elasticsearch / Zebra query builders), and CLI utility wrappers, enforced by a strict Human-in-the-Loop transaction gate for mutations.

Implement the following architectural modules:

1. Single Source of Truth for AI Settings:
- Create a unified "AI Settings" manager/tab in the Python panel.
- Centralize credentials for OpenAI, Anthropic Claude, Google Gemini, and Local LLMs (Ollama / LM Studio / OpenAI-compatible).
- Dynamic UI behavior: When "Ollama" is selected, dynamically hide the API key field and auto-populate the local endpoint ([http://127.0.0.1:11434](http://127.0.0.1:11434)).
- Update the default Gemini model string in code to the current active release (gemini-1.5-pro / gemini-1.5-flash or current OpenAI-compatible endpoint).

2. Safe Agentic Worker & Tool-Calling Pipeline (No Direct Raw SQL):
- Search & Retrieval Tool (Read-Only):
  * Construct tools that query Koha via its native REST API (`/api/v1/biblios`, `/api/v1/patrons`) or directly generate Elasticsearch/Zebra structured queries.
  * The tool returns real parsed JSON objects to the LLM observation window, preventing hallucinations of book titles or fake patron records.
- Staged Mutations & Human-in-the-Loop (Write Actions):
  * If the user asks the assistant to update a record, reserve a book, or edit patron details, the AI CANNOT execute the write operation immediately.
  * Instead, the AI generates a structured "Action Proposal" (Payload Preview: target entity ID, proposed field diff, and action type).
  * The UI presents this proposal with a clear review card and an explicit [Approve & Execute] / [Reject] button before any API POST/PUT or Koha Perl script is triggered.

3. Intent Routing & Semantic Guardrails:
- Implement a lightweight Router Layer (Semantic / Regex / Function gating):
  * Casual conversation or greetings ("hello", "good morning", "who are you?") must be handled directly by the LLM conversational system prompt without triggering Koha tools or search calls.
  * Domain queries (catalog searches, patron checks, library hours) route dynamically to the appropriate tool runner.

4. Memory Management & Coreference Resolution:
- Maintain a structured Conversation Buffer:
  * Enable the agent to resolve contextual references across turns (e.g., User: "Do you have Stephen King books?" -> Agent: [Lists books] -> User: "Which one is his clown book?" -> Agent correctly merges context to search for "Stephen King clown" or filters the prior list for "It").
- Strict Anti-Hallucination Enforcement:
  * When a tool returns empty results or zero matches, the system prompt strictly forbids inventing dummy data. The assistant must truthfully state that no matching records were found in the library catalog.
```

---

## Subject 4: OPAC Visual Customization Engine & Dynamic Cover Carousel
**(Status: Pending)**

```text
Act as a Principal Front-End Developer, Koha System Architect, and UI/UX Specialist. I am building a visual customization module for the Koha OPAC. The Python panel will generate clean CSS/JS and inject it directly into Koha's MariaDB system preferences (`OpacUserCSS`, `OpacUserJS`, `OpacMainUserBlock`) or Koha's Apache web directories.

Feel free to leverage full creative freedom to deliver a modern, high-end visual experience.

Implement the following features:

1. Flexible Asset Upload & Storage (Backgrounds, Logos & Favicons):
- Allow the user to configure custom background images, library logos, and site favicons.
- Multi-Destination Storage Engine:
  * Local Server / Apache Option: Copy files directly into Koha's Apache public web directory (`/usr/share/koha/opac/htdocs/images/custom/`).
  * Cloud / Image Host Option: Integrate automated upload to external image hosting providers (e.g., Postimages API, ImgBB, or Cloudinary) and inject the returned direct HTTPS link into the CSS/JS.
  * Direct URL Input: Let users paste an arbitrary direct image URL manually.

2. Dynamic "New Arrivals" Cover Carousel (Amazon Integration):
- Build a responsive, interactive book carousel component in the main OPAC landing area displaying the latest cataloged titles.
- System Preference Automation:
  * Ensure the required Koha preferences for external covers are enabled (`OPACAmazonCoverImages = 1`, `AmazonAssocTag`, and relevant ISBN cover fetchers).
- Smart Filtering:
  * Filter and display exclusively items that successfully resolve an active Amazon book cover image. If a newly cataloged title lacks an Amazon cover, skip it gracefully so the carousel only renders high-quality visual cards.
- Extended Carousel Customization (Creative Freedom):
  * Configurable autoplay toggle and slide speed interval.
  * Card hover effects (smooth zoom, elevation shadows, tilt effect).
  * Direct click-through from the cover card to the item's bibliographic detail page (`/cgi-bin/koha/opac-detail.pl?biblionumber=X`).
  * Display optional metadata overlay on hover (title, author, call number, availability badge).

3. Ghost Elements & UI Cleanup:
- Automatically inject rules (`display: none !important`) for clutter: empty table columns, RSS feed icons, default cart badges, and generic community links.

4. Textures, Glassmorphism & Materials:
- Provide presets and CSS variables for structural OPAC blocks (`.navbar`, `#opac-main-search`, `.main`):
  * Frosted Glass (glassmorphism with adjustable `backdrop-filter: blur()`).
  * Smooth Glass (semi-transparent without blur).
  * Brushed Metal (linear gradients with inset shadows for subtle 3D metallic feel).
  * Flat Solid Colors and Soft Diagonal Gradients.
- Granular sliders for border-radius (0px to 30px) across blocks, inputs, and buttons.

5. Smart Independent Dark/Light Mode & Legibility Overlay:
- Inject a theme switch button (🌓) in the bottom bar near the language selector.
- Store preference in `localStorage` (`kei_theme = dark`) so toggling only affects the individual user's browser session.
- Legibility Filter Overlay: Inject a subtle dynamic film layer between custom wallpaper backgrounds and content blocks (whitened in Light Mode, dimmed/tinted in Dark Mode) to guarantee WCAG-compliant text contrast.

6. Interactive OPAC News Action Buttons:
- Convert simple HTML markers placed in `additional-contents.pl` into interactive action buttons (title, description, icon, destination URL) styled to match the active material/texture.

7. State Management & Persistence:
- Store all active UI configuration options as a serialized JSON string in a top-level CSS comment inside `OpacUserCSS` (e.g., `/* KEI-THEME-DATA: {"texture": "metal", "carousel_speed": 4000, ...} */`).
- When launching the customization panel in Python, parse this comment to hydrate the UI controls with the active live settings.
```

---

## Subject 5: Administration Hub (Messaging, Cron & Cloud)
**(Status: Pending)**

```text
Act as a Systems Architect. I need to replace walls of text instructions in our panel with automated wizards and deep-links.

1. Messaging & Notifications Hub:
- Group Email (SMTP), WhatsApp, Telegram, SMS, Z39.50, and SIP2 into one unified screen.
- Instead of telling the user to edit `SIPconfig.xml`, create a Python GUI to take parameters and modify the XML automatically, with a deep-link to create the SIP2 account in Koha.
- For Email/SMTP: Provide a visual Gmail Cheat Sheet and direct clickable deep-links that open the exact Koha staff pages (e.g., `/cgi-bin/koha/admin/smtp_servers.pl`).

2. Visual Scheduled Tasks (Cron) Manager:
- Replace launching `nano` with a modern TUI checkbox/dropdown interface for crontab.
- Include presets for: Nightly DB backups, Index rebuilding, and Fine calculations.

3. Rclone Cloud Backup GUI:
- Keep the automated Google Drive backup separate.
- Build a visual setup flow for Manual Rclone (OneDrive, Mega, S3). Let users pick the provider visually.
- Handle headless OAuth properly by providing a "Copy Link" button for the auth URL and a paste box for the token, so the user never types raw `rclone` CLI commands.
```

---

## Subject 6: WireGuard VPN Module (Networking)
**(Status: Pending)**

```text
Act as a Senior Linux Network Engineer. I want to add an optional, production-ready WireGuard VPN module into our Koha management panel for secure Staff (:8080) and SSH access.

Critical Constraints:
1. Strict Split-Tunneling: Client profiles MUST use `AllowedIPs = 10.66.0.0/24`. NEVER use `0.0.0.0/0`.
2. Network Stability: Enforce `MTU = 1360` and `PersistentKeepalive = 25` to prevent fragmentation and NAT timeouts.
3. API Preservation: Third-party requests (Amazon covers, Syndetics) must resolve via the client's local ISP. Do not override client DNS.

Features:
- Automate server setup (`wg0.conf`, `net.ipv4.ip_forward`, iptables NAT/MASQUERADE).
- Provide a UI to add/revoke peers easily.
- Render a terminal ANSI QR code (`qrencode -t ansiutf8`) for mobile clients and a copy button for desktop `.conf` export.
```

---

## Subject 7: Final Adjustments & Documentation
**(Status: Pending)**

- Update the main `README.md` file in the repository to include a prominent link redirecting to the official website: **koha.nexus**.
