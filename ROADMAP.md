# Koha Nexus - Development Roadmap & Master Prompts

This document contains the architectural "Master Prompts" to guide AI-assisted development. To maximize context and save tokens, each Subject should be executed in a clean, fresh chat session.

---

## Subject 1: Core UI/UX, Themes & Panel Cleanup
**(Status: Pending)**

```text
Act as a Senior Python UI/UX Developer. I need to polish the core interface and UX of our Textual-based Koha management panel. Please implement the following UI/UX refactoring:

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

4. Terminal & Window Optimization:
- Ensure the Python app launches maximized by default. Use `sys.stdout.write("\x1b[9;1t")` on startup, and update the Windows `.bat` launcher to use `wt.exe -M wsl -d <distro>`.
- Remove the broken text-based internal browser. Replace it with a native OS launcher (`webbrowser.open(url)`) or a lightweight `pywebview` window so Koha interfaces open with full JS/CSS support.
```

---

## Subject 2: Magic Importer & Database Management
**(Status: Pending)**

```text
Act as a Principal Data Engineer. I need to build the "Magic Importer" and Database Manager module for the Koha ILS.

1. Universal File Ingestion & Auto-Detection:
- Accept CSV, Excel, MARC, JSON, XML, or SQL dumps.
- Implement a Drag & Drop zone in the TUI terminal for database files and data dumps.
- Add a feature to download the database directly from this UI.
- Use Python (Pandas, PyMARC) and local AI to automatically detect file structures, fix character encodings (ISO-8859-1 to UTF-8), and map weird legacy column headers to MARC21/Koha schemas.

2. Polymorphic Separation & Auto-Healing:
- Slice mixed legacy data into distinct streams: Bibliographic Records, Patrons, and Authorities.
- Auto-heal missing mandatory fields based on context.

3. MARC Replace Bugfix:
- Fix the current MARC replace logic: If the `biblionumber` is missing from the incoming data, the script should gracefully default to a standard normal import (creating a new record) instead of failing.

4. Safety Preview & Transaction Gate:
- Before injecting data into Koha's MariaDB, generate a clear summary (e.g., "Found 120 books, 45 patrons. 2 errors"). Require an explicit "Confirm / Execute" button.
```

---

## Subject 3: Centralized AI Settings & Architecture
**(Status: Pending)**

```text
Act as a Senior AI Architect. I need to fix the AI architecture of our Koha assistant and consolidate its configuration.

1. Single Source of Truth for AI Settings:
- Create a unified "AI Settings" tab in the panel. Do not ask for API keys inside individual tools (like Chat or MARC tool).
- Support OpenAI, Anthropic, Gemini, and Local (Ollama/LM Studio).
- Update the default Gemini model string in the code, as the old one is deprecated.
- Make the UI dynamic: if "Ollama" is selected, hide the API key field and pre-fill the endpoint.

2. AI Architecture Fixes (Routing & Memory):
- Implement Semantic Routing: Prevent the LLM from triggering database SQL tools for casual greetings ("hello").
- Fix Coreference Resolution & Contextual Amnesia: Ensure the Conversation Buffer correctly passes previous subjects (e.g., "his clown book" referring to Stephen King) to the tool calls.
- Strict Anti-Hallucination Guardrails: Stop the AI from faking tool outputs (e.g., inventing names like "João Baldi"). Force the LLM to output the exact tool call, pause execution, wait for the backend SQL/API observation, and then format the real data.
```

---

## Subject 4: OPAC Visual Customization Engine
**(Status: Pending)**

```text
Act as a Front-End Developer & UI/UX Specialist. I am building a visual customization module for the Koha OPAC. The Python panel will generate CSS/JS and inject it into Koha's MariaDB systempreferences (OpacUserCSS, OpacUserJS, OpacMainUserBlock).

Features to implement:
1. Branding: Options for background images and library logos (direct URL or local file upload to Koha's Apache dir).
2. Ghost Elements: Auto-hide RSS, cart buttons, and empty columns.
3. Textures & Materials: Allow users to apply Frosted Glass (backdrop-filter: blur), Smooth Glass, Brushed Metal, or Solid Colors to OPAC blocks, with border-radius sliders.
4. Smart Dark/Light Mode: Inject a JS toggle (🌓) in the OPAC footer. Save preference in localStorage so it's user-specific. Add a legibility overlay (film effect) to ensure text is readable over wallpapers.
5. Dynamic OPAC News Buttons: Convert raw HTML in `additional-contents.pl` into modern interactive buttons.
6. Persistence: Save all panel UI choices as a JSON string inside a CSS comment in OpacUserCSS, allowing the Python panel to restore state upon reopening.
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
