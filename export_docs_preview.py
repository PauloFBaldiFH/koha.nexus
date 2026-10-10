#!/usr/bin/env python3
"""
Export the panel's menus, screens and translations for the website's
Interactive Preview and Manual (preview/ on koha.nexus).

Everything the preview shows comes from the code, read without importing
Textual or touching a Koha server:

  panel/kei_panel/menus.py     SECTIONS (sidebar, cards) and DESCRIPTIONS
  panel/kei_panel/views/*.py   the boxes, fields and buttons of each screen
                               (FEATURES below names them; every text is
                               checked against the source file)
  installer                    PANEL_LANG_ITEMS (the panel's languages) and
                               the _MENU_PT table
  lang/<code>.cache            the panel's dictionaries (the t() keys)
  preview/manual/<code>.json   the manual itself, one file per language
  docs/images/panel/*.webp,    screenshots, matched by section or item id
  preview/img/*.webp

and written as one JSON file (preview/data/preview.json by default) that
preview/index.html reads.

    python3 export_docs_preview.py               # write preview/data/preview.json
    python3 export_docs_preview.py --check       # exit 1 if that file is stale
    python3 export_docs_preview.py --report      # translation and manual coverage
    python3 export_docs_preview.py --scaffold es # start preview/manual/es.json
    python3 export_docs_preview.py --stamp pt-BR # mark a translation as up to date

A FEATURES text that is no longer in its source file marks the feature
"pending" (and is reported): the preview shows what the code has, not
what it used to have.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import i18n_common  # noqa: E402  (repo-local helper: cache reader, rules)

PANEL = ROOT / "panel" / "kei_panel"
INSTALLER = ROOT / "installer"
LANG_DIR = ROOT / "lang"
MANUAL_DIR = ROOT / "preview" / "manual"
DEFAULT_OUT = ROOT / "preview" / "data" / "preview.json"
MEDIA_DIRS = (ROOT / "docs" / "images" / "panel", ROOT / "preview" / "img")
SCHEMA = 1

# Manual text fields, in the order the page shows them.
TEXT_FIELDS = ("title", "summary")
LIST_FIELDS = ("overview", "steps", "options", "tips", "warnings")
RTL = {"ar", "fa", "he", "ur"}
# The website's own language codes (index.html: setLanguage('br') ...).
SITE_CODES = {"pt": "br"}


# ----------------------------------------------------------------------
# Reading Python sources without importing them
# ----------------------------------------------------------------------
class Source:
    """A Python file: its string literals and its module-level constants."""

    _cache: dict[Path, "Source"] = {}

    def __init__(self, path: Path):
        self.path = path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.strings: set[str] = set()
        self.t_calls: set[str] = set()
        self.constants: dict[str, object] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.strings.add(node.value)
            elif (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "t" and node.args
                  and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                self.t_calls.add(node.args[0].value)
        # Implicitly concatenated literals are one Constant already; a
        # constant built from "a" "b" across lines is too.
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
                targets = [node.target.id]
                value = node.value
            for name in targets:
                self.constants[name] = _literal(value)

    @classmethod
    def get(cls, rel: str) -> "Source":
        path = PANEL / rel
        if path not in cls._cache:
            cls._cache[path] = Source(path)
        return cls._cache[path]


def _literal(node: ast.AST) -> object:
    """literal_eval, keeping what can be read of a dict or tuple whose other
    values are expressions (FALLBACK's Ollama entry is a generator)."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        pass
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            try:
                out[ast.literal_eval(k)] = ast.literal_eval(v)
            except (ValueError, SyntaxError, TypeError):
                continue
        return out
    return None


def load_menus() -> object:
    """menus.py on its own (it needs only dataclasses): SECTIONS, DESCRIPTIONS."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("kei_menus_export", PANEL / "menus.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses looks the module up
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------------
# The screens: which boxes and controls the preview draws for each one
# ----------------------------------------------------------------------
# A control's texts are t() keys of its source file. "options" names a
# constant: "CODECS" in the same file, or "opac_theme.TEXTURES" in another
# module of the panel. Values (the colour shown, a slider position) only
# decorate the mockup.
def button(label, primary=False): return {"type": "button", "label": label, "primary": primary}
def select(label, options, value=0): return {"type": "select", "label": label, "options": options, "value": value}
def switch(label, on=True): return {"type": "switch", "label": label, "on": on}
def field_(label, value="", placeholder=""): return {"type": "input", "label": label, "value": value,
                                                     "placeholder": placeholder}
def slider(label, value=50, unit="%"): return {"type": "slider", "label": label, "value": value, "unit": unit}
def color(label, value): return {"type": "color", "label": label, "value": value}
def status(label, value, state="ok"): return {"type": "status", "label": label, "value": value, "state": state}
def note(text): return {"type": "note", "text": text}
def table(columns, rows): return {"type": "table", "columns": columns, "rows": rows}


@dataclass
class Feature:
    id: str
    section: str
    source: str              # panel/kei_panel/<source>
    label: str               # the box title (a key of the source)
    controls: list = field(default_factory=list)
    extra_sources: tuple = ()


FEATURES: tuple[Feature, ...] = (
    # Control Dashboard
    Feature("dash-status", "dashboard", "views/dashboard.py", "Koha", [
        status("Koha", "Running"), status("Last backup", "None yet", "warn"), status("Disk free", "62 GB"),
        status("Memory available", "2.1 GB"),
        button("Refresh"),
    ]),
    Feature("dash-addresses", "dashboard", "views/dashboard.py", "Addresses", [
        status("On the server itself", "http://localhost:8080"),
        status("Other computers on the network", "http://192.168.0.20:8080"),
        status("Cloudflare Tunnel", "Not published on the Internet", "warn"),
    ]),
    Feature("dash-components", "dashboard", "views/dashboard.py", "Components", [
        status("HTTP response", "Staff / OPAC"), status("Staff / OPAC", "Answers (HTTP ${code})"),
    ]),
    Feature("dash-restart", "dashboard", "views/dashboard.py", "Restart Koha", [button("Restart Koha", True)]),
    Feature("dash-export", "dashboard", "views/dashboard.py", "Export diagnostics", [button("Export diagnostics")]),
    # Backup center
    Feature("backup-download", "backup", "views/backup.py", "📥 Download latest backup", [
        button("📥 Download latest backup", True),
    ]),
    Feature("backup-status", "backup", "views/backup.py", "Last backup", [
        status("Last backup", "${age} ago"), status("Size", "184 MB"), status("Result", "OK"),
    ], extra_sources=("views/dashboard.py",)),
    Feature("backup-compression", "backup", "views/backup.py", "New backups", [
        select("Compression", "CODECS", 1), note("CODEC_NOTE"),
    ]),
    Feature("backup-safety", "backup", "routines/backup.py", "Safety backup:", [
        status("Safety backup:", "pre_restore_safety_backup_2026-10-10_14h07m33.sql.zst"),
        status("Search engine", "Zebra"), status("Tables", "312"),
    ]),
    # Database tables
    Feature("db-tables", "database", "views/database.py", "tables", [
        button("Refresh"),
        table(["Table", "Rows", "Size"], [["biblio_metadata", "48,210", "391 MB"], ["items", "61,877", "58 MB"],
                                          ["action_logs", "1,204,553", "41 MB"]]),
    ]),
    # AI
    Feature("ai-provider", "ai", "views/ai.py", "Provider", [
        select("Provider", "aiconf.LABELS", 1), field_("Server URL", "https://generativelanguage.googleapis.com"),
        field_("API key", "", "paste the API key here"), field_("Vision model", "gemini-flash-latest"),
        field_("Chat model", "", "empty: the same as the vision model"),
        button("Test connection"), button("Save", True),
    ]),
    Feature("ai-models", "ai", "views/ai.py", "Models", [
        select("Choose a model", "aimodels.FALLBACK"), button("Load models", True),
        button("Use for cataloguing"), button("Use for chat"),
    ]),
    Feature("ai-ollama", "ai", "views/ai.py", "Ollama on this server", [
        button("Check Ollama"), button("Install Ollama"), select("Model", "aiconf.OLLAMA_PRESETS", 3),
        button("Download", True), note("Without a GPU, prefer the light models: a 7B vision model can take "
                                       "minutes per answer on a CPU."),
    ]),
    Feature("ai-tools", "ai", "views/ai.py", "The AI tools", [
        status("MARC Replace", "Open MARC Replace"), status("💬  AI assistant", "Installed"),
        button("Open MARC Replace"), button("Install, update or remove the assistant"),
    ]),
    # Z39.50 / SRU
    Feature("z3950-inbound", "z3950", "views/z3950.py", "This catalogue's Z39.50 / SRU server (inbound)", [
        switch("Z39.50/SRU server (koha-z3950-daemon)", False),
        note("Lets other libraries search this catalogue by Z39.50 and SRU (koha-z3950-daemon). Turning it on "
             "opens its port in the firewall; off closes it, also after a restart."),
    ]),
    Feature("z3950-network", "z3950", "views/z3950.py", "Community network", [
        switch("Community network", False),
        note("The shared catalogue of the koha.nexus libraries. Turning it on adds it to Koha's Z39.50/SRU "
             "servers, checked for the cataloguing searches; off takes it out."),
    ]),
    Feature("z3950-outbound", "z3950", "views/z3950.py", "Catalogues to copy records from (outbound)", [
        button("Scan", True), button("Add to Koha"), button("Login"), button("Hide"), button("Community list"),
        button("Import"), button("Export"), button("Show hidden"),
        table(["Server", "Status", "Format", "Address"], "targets"),
    ]),
    Feature("z3950-zeus", "z3950", "data/z3950_targets.json", "Catálogo Zeus (UFSC bridge, SRU)", [
        table(["Server", "Status", "Format", "Address"], "targets:Zeus"),
    ]),
    Feature("z3950-pergamum", "z3950", "data/z3950_targets.json", "Catálogo Rede Pergamum (CRP bridge, SRU)", [
        table(["Server", "Status", "Format", "Address"], "targets:Pergamum"),
    ]),
    # OPAC and Staff Appearance
    Feature("opac-material", "opac", "views/opac.py", "Material", [
        select("Texture", "opac_theme.TEXTURES"), slider("Blur", 12, "px"), slider("Opacity", 82),
        slider("Content panels", 94),
        slider("Blocks", 14, "px"), slider("Inputs", 10, "px"), slider("Buttons", 10, "px"),
        color("Accent colour", "#2f7d5b"), color("Second colour", "#1e4f86"), color("Block background", "#ffffff"),
        switch("Page colour", False),
    ]),
    Feature("opac-pictures", "opac", "views/opac.py", "Pictures", [
        select("Wallpaper", "opac_theme.SOURCES", 1), select("Logo", "opac_theme.SOURCES", 3),
        select("Favicon", "opac_theme.SOURCES", 0),
    ]),
    Feature("opac-dark", "opac", "views/opac.py", "Legibility and dark mode", [
        slider("Legibility film", 70), switch("Light/dark switch"), select("Default theme", "opac_theme.THEMES", 2),
    ]),
    Feature("opac-carousel", "opac", "views/opac.py", "New arrivals carousel", [
        switch("Show"), select("Style", "opac_theme.CAROUSEL_MODES", 1), field_("Title", "New arrivals"),
        switch("Autoplay"), slider("Speed", 3500, " ms"), slider("Titles", 12, ""),
        select("Hover effect", "opac_theme.HOVERS"), switch("Details"), field_("Amazon tag", "", "optional"),
    ]),
    Feature("opac-links", "opac", "views/opac.py", "Quick access buttons", [
        switch("Show"), select("Style", "opac_theme.LINK_STYLES", 3), select("Layout", "opac_theme.LINK_LAYOUTS", 1),
        field_("Order (1 comes first)", "1"), field_("Text", "📖 Renew my loans"), button("Add a button"),
    ]),
    Feature("opac-staff-links", "opac", "views/opac.py", "Staff home page buttons", [
        switch("Show"), select("Style", "opac_theme.LINK_STYLES", 0), select("Layout", "opac_theme.LINK_LAYOUTS", 1),
        field_("Order (1 comes first)", "1"), field_("Text", "📅 Holds to pull"), button("Add a button"),
    ]),
    Feature("opac-staff", "opac", "views/opac.py", "Staff interface", [
        switch("Apply color theme to Staff Client"), color("Accent colour", "#1e4f86"),
        color("Second colour", "#2f7d5b"), slider("Legibility film", 80),
        select("Table density", "opac_theme.STAFF_DENSITY", 1), select("Contrast", "opac_theme.STAFF_CONTRAST"),
        slider("Text size", 100),
    ]),
    Feature("opac-login", "opac", "views/opac.py", "OPAC login page", [
        switch("Show"), select("Login banner", "opac_theme.SOURCES", 1), field_("Picture description", "Library front"),
        field_("Text (HTML)", "<h2>Don't have a password yet?</h2>"),
    ]),
    Feature("opac-staff-login", "opac", "views/opac.py", "Staff login page", [
        switch("Show"), select("Login banner", "opac_theme.SOURCES", 1),
        field_("Text (HTML)", "<p>Staff only. Forgot your password? Call the coordinator.</p>"),
    ]),
    Feature("opac-credits", "opac", "views/opac.py", "Footer credits", [
        switch("Show"), field_("Library name", "Biblioteca Pública Municipal"), field_("Address", "Rua ..., Centro"),
        field_("Phone", "+55 (44) 3649-1214"), field_("E-mail", "biblioteca@..."), field_("Instagram", "@biblioteca"),
        field_("CNPJ", "00.000.000/0000-00"),
    ]),
    Feature("opac-hide", "opac", "views/opac.py", "Hide", [
        switch("RSS icons"), switch("Cart badge", False), switch("Community links"), switch("Empty table columns"),
    ]),
    Feature("opac-news", "opac", "views/opac.py", "News action buttons", [
        switch("Buttons"), note("In a news item (Tools > News), this marker becomes a button:"),
    ]),
    Feature("opac-actions", "opac", "views/opac.py", "Apply", [
        button("Apply", True), button("Preview"), button("Sync current OPAC settings"), button("Refresh carousel"),
        button("Image host keys"), button("Remove"),
    ]),
    # Messaging & interoperability
    Feature("hub-email", "hub", "views/hub.py", "📧  E-mail", [
        button("Turn on Koha's e-mail", True), button("SMTP servers"), button("New SMTP server"),
        button("Library e-mail address"), button("Create a Google app password"),
    ]),
    Feature("hub-whatsapp", "hub", "views/hub.py", "💬  WhatsApp & Telegram", [
        note("Sends Koha's notices (holds waiting, overdue, due soon) by WhatsApp or Telegram too, with the "
             "reader's mobile number. The setup asks for the service's keys."),
        button("Set up WhatsApp and Telegram", True),
    ]),
    Feature("hub-sms", "hub", "views/hub.py", "📱  SMS", [
        button("SMS driver (SMSSendDriver)"), button("Readers' messaging preferences"),
    ]),
    Feature("hub-sip2", "hub", "views/hub.py", "🏧  SIP2", [
        field_("Port", "6001"), select("Network", ["Only this server (127.0.0.1)",
                                                   "Every network (opens the firewall port)"]),
        field_("SIP login", "selfcheck"), field_("Password", "", "at least 8 characters"),
        field_("Library", "", "Choose the library"), switch("Remove examples"), button("Save", True),
        button("Create the SIP patron in Koha"),
    ]),
    Feature("hub-z3950", "hub", "views/hub.py", "📡  Z39.50", [
        button("📡  Z39.50 / SRU servers", True),
    ]),
    # WireGuard VPN
    Feature("vpn-server", "vpn", "views/vpn.py", "Server", [
        field_("Address", "", "public IP or name, e.g. vpn.library.org"), field_("UDP port", "51820"),
        button("Set up the VPN", True), button("Turn off"),
    ]),
    Feature("vpn-devices", "vpn", "views/vpn.py", "Devices", [
        field_("New device", "", "e.g. maria-laptop"), button("Add device", True), button("QR code & profile"),
        button("Revoke"),
        table(["Device", "Address", "Last seen", "Received", "Sent"],
              [["maria-laptop", "10.66.0.2", "2 min", "14 MB", "3 MB"], ["desk-phone", "10.66.0.3", "1 h", "2 MB", "1 MB"]]),
    ]),
)


# ----------------------------------------------------------------------
# Languages and dictionaries
# ----------------------------------------------------------------------
def panel_languages() -> list[dict]:
    """PANEL_LANG_ITEMS of the installer: the panel's own language list."""
    text = INSTALLER.read_text(encoding="utf-8")
    m = re.search(r"^PANEL_LANG_ITEMS=\($(.*?)^\)", text, re.S | re.M)
    items = re.findall(r'"([^"]+)"\s+"([^"]+)"', m.group(1)) if m else []
    if not items:
        raise SystemExit("PANEL_LANG_ITEMS not found in the installer")
    out = []
    for panel_code, name in items:
        dict_code = normalize(panel_code)
        # Website code: pt-BR keeps its region, the others are the dictionary name.
        code = "pt-BR" if dict_code == "pt" else dict_code
        out.append({"code": code, "panel": panel_code, "dict": dict_code, "name": name,
                    "site": SITE_CODES.get(dict_code, dict_code), "dir": "rtl" if dict_code in RTL else "ltr"})
    return out


def normalize(code: str) -> str:
    """normalize_panel_language (panel/kei_panel/env.py) for the listed codes."""
    base = re.split(r"[-_]", code, maxsplit=1)[0]
    return {"fil": "tl"}.get(base, base)


def menu_pt() -> dict[str, str]:
    text = INSTALLER.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^declare -A _MENU_PT=\($(.*?)^\)", text, re.S | re.M)
    if not m:
        return {}
    pairs = re.findall(r'\["((?:[^"\\]|\\.)*)"\]="((?:[^"\\]|\\.)*)"', m.group(1))
    return {i18n_common.bash_unescape_double_quoted(k): i18n_common.bash_unescape_double_quoted(v)
            for k, v in pairs}


class Dictionaries:
    def __init__(self, languages: list[dict]):
        self.tables: dict[str, dict[str, str]] = {}
        for lang in languages:
            if lang["dict"] == "en":
                continue
            table = i18n_common.read_cache(str(LANG_DIR / f"{lang['dict']}.cache"))
            if lang["dict"] == "pt":
                table = {**table, **menu_pt()}     # _MENU_PT wins, as in the panel
            self.tables[lang["code"]] = table

    def lookup(self, code: str, key: str) -> str | None:
        if code == "en":
            return key
        val = self.tables.get(code, {}).get(key)
        return val if val and i18n_common.is_valid(key, val) else None


# ----------------------------------------------------------------------
# Building the document
# ----------------------------------------------------------------------
def item_hash(item: dict) -> str:
    """Hash of an English manual item: a translation stamped with an older
    hash is reported as outdated."""
    clean = {k: v for k, v in item.items() if not k.startswith("_") and k != "related"}
    return hashlib.sha1(json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]


def read_manuals(languages: list[dict]) -> dict[str, dict]:
    out = {}
    for lang in languages:
        path = MANUAL_DIR / f"{lang['code']}.json"
        if path.is_file():
            out[lang["code"]] = json.loads(path.read_text(encoding="utf-8"))
    if "en" not in out:
        raise SystemExit(f"{MANUAL_DIR / 'en.json'} is missing: the English manual is the base of every language")
    return out


def media_for(*names: str) -> list[str]:
    found = []
    for folder in MEDIA_DIRS:
        if not folder.is_dir():
            continue
        for name in names:
            for path in sorted(folder.glob(f"{name}.webp")) + sorted(folder.glob(f"{name}--*.webp")):
                rel = path.relative_to(ROOT).as_posix()
                if rel not in found:
                    found.append(rel)
    return found


class Builder:
    def __init__(self):
        self.menus = load_menus()
        self.languages = panel_languages()
        self.dicts = Dictionaries(self.languages)
        self.manuals = read_manuals(self.languages)
        self.keys: list[str] = []          # every t() key the page needs, in order
        self.warnings: list[str] = []
        self.targets = json.loads((PANEL / "data" / "z3950_targets.json").read_text(encoding="utf-8"))["targets"]

    def key(self, text: str) -> str:
        if text and text not in self.keys:
            self.keys.append(text)
        return text

    # -- menus ----------------------------------------------------------
    def sections(self) -> tuple[list[dict], dict[str, dict]]:
        sections, items = [], {}
        for s in self.menus.SECTIONS:
            sec = {"id": s.id, "item": f"sec-{s.id}", "label": self.key(s.label), "title": self.key(s.title),
                   "prompt": self.key(s.prompt), "icon": s.icon, "key": s.key, "view": s.view,
                   "sidebar": s.sidebar, "parent": s.parent, "entries": [], "features": [],
                   "media": media_for(s.id, f"sec-{s.id}")}
            for e in s.entries:
                eid = e.action if e.kind != "view" else f"sec-{e.action}"
                sec["entries"].append(eid)
                if e.kind == "view" or eid in items:
                    continue
                desc = self.menus.DESCRIPTIONS.get(e.action, "")
                items[eid] = {"id": eid, "type": "entry", "section": s.id, "label": self.key(e.label),
                              "description": self.key(desc), "kind": e.kind,
                              "status": "hidden" if e.hidden else "available", "media": media_for(eid)}
            # A section that is only its own card (Install, Restore...) is
            # that entry: the page opens the entry directly.
            single = len(s.entries) == 1 and s.entries[0].kind != "view"
            sec["single"] = sec["entries"][0] if single else ""
            if not single:
                items[sec["item"]] = {"id": sec["item"], "type": "section", "section": s.id,
                                      "label": sec["label"], "description": self.key(sec["prompt"]),
                                      "kind": "view" if s.view != "section" else "menu",
                                      "status": "available", "media": sec["media"]}
            sections.append(sec)
        return sections, items

    # -- screens --------------------------------------------------------
    def resolve_options(self, source: Source, ref) -> tuple[list[dict], list[str]]:
        """Option list of a select: [{"text": key, "literal": bool}], missing keys."""
        if isinstance(ref, list):
            return [{"text": self.key(x)} for x in ref], [x for x in ref if x not in source.strings]
        module, _, name = ref.rpartition(".")
        src = Source.get(f"{module}.py") if module else source
        value = src.constants.get(name)
        if value is None:
            return [], [ref]
        if isinstance(value, dict) and all(isinstance(v, str) for v in value.values()):
            return [{"text": self.key(v)} for v in value.values()], []
        if isinstance(value, dict):        # FALLBACK: provider -> model ids
            models = [m for v in value.values() if isinstance(v, (tuple, list)) for m in v]
            return [{"text": m, "literal": True} for m in models], []
        if isinstance(value, (tuple, list)) and value and isinstance(value[0], (tuple, list)):
            return [{"text": self.key(row[1]), "prefix": row[0]} for row in value], []
        return [], [ref]

    def target_rows(self, which: str) -> list[list[str]]:
        rows = []
        for t in self.targets:
            if which and which.lower() not in t["name"].lower():
                continue
            fmt = "SRU" if t.get("kind") == "sru" else "Z39.50"
            rows.append([t["name"], "In Koha" if t.get("preselect") else "Not scanned yet",
                         f"{fmt} · {t.get('syntax', '')}", f"{t['host']}:{t['port']}/{t.get('db', '')}"])
            if len(rows) >= (6 if not which else 1):
                break
        return rows

    def feature(self, f: Feature) -> dict:
        data_file = f.source.endswith(".json")
        source = None if data_file else Source.get(f.source)
        known = set()
        if source:
            known = set(source.strings)
            for extra in f.extra_sources:
                known |= Source.get(extra).strings
        else:
            known = {t["name"] for t in self.targets}
        missing = [] if f.label in known else [f.label]
        controls = []
        for c in f.controls:
            c = dict(c)
            for k in ("label", "text", "placeholder"):
                text = c.get(k)
                if not text:
                    continue
                if text.isupper() and source and text in source.constants:   # CODEC_NOTE
                    text = c[k] = source.constants[text]
                elif text not in known and not (c["type"] == "status" and k == "label" and data_file):
                    missing.append(text)
                self.key(text)
            if c["type"] in ("status",) and c.get("value") in known:
                self.key(c["value"])
            if c["type"] == "select":
                c["options"], miss = self.resolve_options(source, c["options"])
                missing += miss
            if c["type"] == "table":
                for col in c["columns"]:
                    self.key(col)
                    if source and col not in known:
                        missing.append(col)
                if isinstance(c["rows"], str):
                    _, _, which = c["rows"].partition(":")
                    c["rows"] = self.target_rows(which)
                    for row in c["rows"]:
                        self.key(row[1])
            controls.append(c)
        if missing:
            self.warnings.append(f"{f.id}: not in {f.source} (marked pending): {', '.join(sorted(set(missing)))}")
        self.key(f.label)
        return {"id": f.id, "type": "feature", "section": f.section, "label": f.label, "description": "",
                "kind": "screen", "status": "pending" if missing else "available",
                "source": f"panel/kei_panel/{f.source}", "controls": controls,
                "media": media_for(f.id)}

    # -- manual ---------------------------------------------------------
    def manual(self, items: dict[str, dict]) -> tuple[dict, dict, dict]:
        en = self.manuals["en"].get("items", {})
        hashes = {k: item_hash(v) for k, v in en.items()}
        manual: dict[str, dict] = {}
        coverage: dict[str, dict] = {}
        wanted = [i for i, it in items.items() if it["status"] != "hidden"]
        for k in en:
            if k not in items:
                self.warnings.append(f"manual/en.json: item '{k}' is not on the dashboard any more")
        for k in wanted:
            if k not in en:
                self.warnings.append(f"manual/en.json: no text for '{k}'")
        for lang in self.languages:
            code = lang["code"]
            data = self.manuals.get(code, {}).get("items", {})
            done, outdated = 0, []
            for k in wanted:
                item = data.get(k)
                if not item:
                    continue
                entry = {f: item[f] for f in TEXT_FIELDS + LIST_FIELDS if item.get(f)}
                if code == "en":
                    entry["related"] = [r for r in item.get("related", []) if r in items]
                elif item.get("_en") and item["_en"] != hashes.get(k):
                    entry["outdated"] = True
                    outdated.append(k)
                manual.setdefault(k, {})[code] = entry
                done += 1
            coverage[code] = {"manual": done, "manual_total": len(wanted), "manual_outdated": outdated}
        ui = {}
        for code, data in self.manuals.items():
            for k, v in data.get("ui", {}).items():
                ui.setdefault(k, {})[code] = v
        return manual, coverage, ui

    # -- everything -----------------------------------------------------
    def build(self) -> dict:
        sections, items = self.sections()
        by_id = {s["id"]: s for s in sections}
        for f in FEATURES:
            if f.section not in by_id:
                self.warnings.append(f"{f.id}: section '{f.section}' is not in menus.py")
                continue
            items[f.id] = self.feature(f)
            by_id[f.section]["features"].append(f.id)
        manual, coverage, ui = self.manual(items)
        # The simulator's key bar ends with the app's own binding (app.py).
        if "Exit" in Source.get("app.py").t_calls:
            self.key("Exit")
        strings = {}
        for k in self.keys:
            strings[k] = {lang["code"]: self.dicts.lookup(lang["code"], k) for lang in self.languages}
        for lang in self.languages:
            code = lang["code"]
            got = sum(1 for k in self.keys if strings[k][code])
            coverage[code]["strings"] = got
            coverage[code]["strings_total"] = len(self.keys)
            lang["manual"] = coverage[code]["manual"] > 0
        return {
            "schema": SCHEMA,
            "panel_version": i18n_common.panel_version(str(INSTALLER)),
            "languages": self.languages,
            "sections": sections,
            "items": items,
            "strings": strings,
            "ui": ui,
            "manual": manual,
            "coverage": coverage,
        }


def dump(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


# ----------------------------------------------------------------------
# Translator helpers
# ----------------------------------------------------------------------
def scaffold(code: str, languages: list[dict]) -> Path:
    """preview/manual/<code>.json with every English text to translate.
    Items already translated are kept; new ones come in English with the
    hash of the English text (_en), so --report can tell what is left."""
    if code not in {lang["code"] for lang in languages}:
        raise SystemExit(f"'{code}' is not a panel language: {', '.join(lang['code'] for lang in languages)}")
    en = json.loads((MANUAL_DIR / "en.json").read_text(encoding="utf-8"))
    path = MANUAL_DIR / f"{code}.json"
    cur = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    out = {"language": code, "ui": {**en.get("ui", {}), **cur.get("ui", {})}, "items": {}}
    for k, item in en["items"].items():
        if k in cur.get("items", {}):
            out["items"][k] = cur["items"][k]
        else:
            out["items"][k] = {**{f: v for f, v in item.items() if f != "related"}, "_en": item_hash(item),
                               "_todo": True}
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def stamp(code: str) -> Path:
    """Record that every item of <code>.json matches the current English text."""
    en = json.loads((MANUAL_DIR / "en.json").read_text(encoding="utf-8"))["items"]
    path = MANUAL_DIR / f"{code}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for k, item in data.get("items", {}).items():
        if k in en and not item.get("_todo"):
            item["_en"] = item_hash(en[k])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def report(doc: dict) -> str:
    lines = [f"{'lang':8} {'panel texts':>13} {'manual':>9}  outdated"]
    for lang in doc["languages"]:
        c = doc["coverage"][lang["code"]]
        lines.append(f"{lang['code']:8} {c['strings']:>5}/{c['strings_total']:<5} "
                     f"{c['manual']:>4}/{c['manual_total']:<4} {len(c['manual_outdated']) or ''}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true", help="exit 1 if the output file is not up to date")
    ap.add_argument("--report", action="store_true", help="print translation and manual coverage")
    ap.add_argument("--scaffold", metavar="LANG", help="create or complete preview/manual/LANG.json")
    ap.add_argument("--stamp", metavar="LANG", help="mark LANG's translated items as matching the English")
    args = ap.parse_args(argv)

    if args.scaffold:
        print(f"wrote {scaffold(args.scaffold, panel_languages()).relative_to(ROOT)}")
        return 0
    if args.stamp:
        print(f"stamped {stamp(args.stamp).relative_to(ROOT)}")
        return 0

    builder = Builder()
    doc = builder.build()
    for w in builder.warnings:
        print(f"warning: {w}", file=sys.stderr)
    text = dump(doc)
    if args.check:
        current = json.loads(args.out.read_text(encoding="utf-8")) if args.out.is_file() else {}
        # A version bump alone does not make the preview stale.
        current.pop("panel_version", None)
        if current != {k: v for k, v in json.loads(text).items() if k != "panel_version"}:
            print(f"{args.out} is out of date: run python3 export_docs_preview.py", file=sys.stderr)
            return 1
        print(f"{args.out.relative_to(ROOT)} is up to date")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out.relative_to(ROOT)}: {len(doc['items'])} items, {len(doc['strings'])} texts, "
              f"{len(doc['languages'])} languages")
    if args.report:
        print(report(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
