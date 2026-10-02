#!/usr/bin/env python3
"""
Shared helpers for the panel translation tools (gen_all_langs.py, gen_lang.py).

Dictionary format (lang/<code>.cache), one entry per line:
    base64(English text)|base64(translation)

The English text is the key the panel looks up, exactly as the t() function
receives it at run time. Strings may contain variables (${VAR}, $VAR,
${VAR:-default}), printf markers (%s) and literal "\\n" sequences: they must
survive the translation untouched, otherwise the panel ignores the entry and
shows the English text.

Run directly to check or repair the dictionaries without any translation engine:
    python3 i18n_common.py            # coverage report
    python3 i18n_common.py --fix      # repair variables/icons, drop broken and stale entries
                                      # (run it after every PANEL_VERSION change: the
                                      # panel prefers dictionaries of its own version)
"""
import base64
import html
import os
import re
import sys

INSTALLER_FILE = "installer"
LANG_DIR = "lang"
# Windows scripts: their texts go through T '...' (windows/KohaEasy.Lang.psm1)
# and share the same dictionaries.
WINDOWS_DIR = "windows"

# Dictionaries shipped with the panel (file names, see normalize_panel_language
# in the installer for the mapping from Koha language codes).
TARGET_LANGS = [
    "pt", "es", "fr", "de", "it",
    "nl", "ru", "pl", "uk", "cs",
    "sv", "tr", "ar", "ja", "zh",
    "hi", "bn", "id", "tl", "fa",
    "vi", "ko",
]

# ----------------------------------------------------------------------
# Extraction
# ----------------------------------------------------------------------
# t "..." / t '...' (but not "gzip -t" or "sort -t") and display_explanation "...",
# whose argument is translated inside the function.
_CALL_RE = re.compile(
    r"""(?:(?<![\w$.\-/])t|\bdisplay_explanation)\s+(?:"((?:[^"\\]|\\.)*)"|'([^']*)')"""
)
_BASH_DQ_ESCAPE = re.compile(r'\\([$`"\\\n])')
# PowerShell: T 'text' (single quotes, '' is one quote), placeholders {0}.
_PS_CALL_RE = re.compile(r"""(?<![\w$.\-])T\s+'((?:[^']|'')*)'""")


def bash_unescape_double_quoted(text):
    """What bash passes to the function for a double-quoted literal."""
    return _BASH_DQ_ESCAPE.sub(r"\1", text)


def extract_strings(installer_file=INSTALLER_FILE):
    if not os.path.exists(installer_file):
        print(f"[ERRO] Arquivo {installer_file} não encontrado no diretório atual.")
        return []
    with open(installer_file, "r", encoding="utf-8") as fh:
        # Full-line comments may show usage examples: they are not UI text.
        content = "".join(line for line in fh if not line.lstrip().startswith("#"))

    found = set()
    for double_q, single_q in _CALL_RE.findall(content):
        text = bash_unescape_double_quoted(double_q) if double_q else single_q
        if not text or len(text.strip()) < 2:
            continue
        # A bare variable ("$1", "$var") is not translatable text.
        if re.fullmatch(r"\$\{?[A-Za-z0-9_]+\}?", text.strip()):
            continue
        # Command substitutions are expanded before t() runs: never a stable key.
        if "$(" in text:
            continue
        found.add(text)
    found.update(extract_windows_strings())
    return sorted(found)


def extract_windows_strings(windows_dir=WINDOWS_DIR):
    found = set()
    if not os.path.isdir(windows_dir):
        return found
    for name in sorted(os.listdir(windows_dir)):
        if not name.endswith((".ps1", ".psm1")):
            continue
        with open(os.path.join(windows_dir, name), "r", encoding="utf-8-sig") as fh:
            content = "".join(line for line in fh if not line.lstrip().startswith("#"))
        for text in _PS_CALL_RE.findall(content):
            text = text.replace("''", "'")
            if len(text.strip()) >= 2:
                found.add(text)
    return found


# ----------------------------------------------------------------------
# Placeholders
# ----------------------------------------------------------------------
VAR_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}|\$[A-Za-z_][A-Za-z0-9_]*")

# Terms that must never be translated (besides variables and printf markers).
PROTECTED_TERMS = [
    r"\\n",
    VAR_RE.pattern,
    r"%[sdb]",
    r"\{\d+\}",
    r"https?://[^\s'\"]+",
    r"(?<![\w/])/(?:etc|var|root|usr|tmp|run|media|mnt)/[A-Za-z0-9_\-./*@]+",
    r"--[a-z0-9][a-z0-9_-]*",
    r"koha-[a-z0-9_@.-]+",
    r"[a-z0-9_-]+\.(?:sh|pl|xml|conf|log|txt|yml|sql\.gz|sql|bat|json|mrc)\b",
    r"\bmariadb[a-z0-9_-]*",
    r"\b(?:systemctl|apache2|memcached|cloudflared|whiptail|rclone|journalctl|certbot|nano|htop|nethogs|scp|ssh|ufw|zcat|gzip)\b",
    r"\b(?:Koha|Zebra|Elasticsearch|MariaDB|Plack|RabbitMQ|STOMP|OPAC|Staff|MARC21|Memcached|Apache|Cloudflare|Rclone|Google Drive|Search Console|OpacMetaRobots|SearchEngine|SIP2|Z39\.50|UFW|Fail2ban|Certbot|Midnight Commander|Links|PowerShell|Windows|macOS|Linux)\b",
]
_PROTECT_RE = re.compile("|".join(f"(?:{p})" for p in PROTECTED_TERMS))
_TOKEN_RE = re.compile(r"\[\[\s*(\d+)\s*\]\]")


def protect_text(text):
    """Replaces untranslatable parts by [[n]] tokens. Returns (text, tokens)."""
    tokens = []

    def repl(match):
        tokens.append(match.group(0))
        return f"[[{len(tokens) - 1}]]"

    return _PROTECT_RE.sub(repl, text), tokens


def unprotect_text(text, tokens):
    def repl(match):
        idx = int(match.group(1))
        return tokens[idx] if idx < len(tokens) else match.group(0)

    return _TOKEN_RE.sub(repl, text).strip()


def var_signature(text):
    """Variables of a template, as the panel compares them ("name" or "name:-")."""
    sig = []
    for tok in VAR_RE.findall(text):
        name = re.match(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", tok).group(1)
        sig.append(name + (":-" if ":-" in tok else ""))
    if re.search(r"\$\{(?![A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\})", text):
        sig.append("?broken")
    return sorted(set(sig))


def is_valid(src, tr):
    """Same rules as _t_is_safe() in the installer, plus sanity checks."""
    if not tr or not tr.strip():
        return False
    if "[[" in tr and "[[" not in src:
        return False
    if src.count("%") != tr.count("%"):
        return False
    if var_signature(src) != var_signature(tr):
        return False
    if sorted(set(re.findall(r"\{\d+\}", src))) != sorted(set(re.findall(r"\{\d+\}", tr))):
        return False
    return True


# Sources are English, so a leading run of non-ASCII symbols (or "-", "•",
# "=") followed by spaces is an icon/bullet: "⚙  Install...", "ℹ  View...".
_ICON_PREFIX_RE = re.compile(r"^((?:[^\sA-Za-z0-9\\\[\(<'\"$`]\ufe0f?)+\s+)")
_ENTITY_RE = re.compile(r"&(?:quot|gt|lt|amp|apos|#\d+);")


def fix_icon_prefix(src, tr):
    """Menu entries start with an icon ("⚙  Install..."); keep it identical."""
    m = _ICON_PREFIX_RE.match(src)
    if not m:
        return tr
    prefix = m.group(1)
    if tr.startswith(prefix):
        return tr
    icons = set(prefix.strip())
    body = tr.lstrip()
    while body and (body[0] in icons or body[0] == "\ufe0f"
                    or (not body[0].isalnum() and body[0] not in "\\[(<'\"$`")):
        body = body[1:].lstrip()
    # Some engines turn the "ℹ" icon into a plain "i".
    if "ℹ" in icons and re.match(r"i\s", body):
        body = body[1:].lstrip()
    return prefix + body


def fix_entities(src, tr):
    """Engines sometimes return HTML entities, even for a plain "&"."""
    if not _ENTITY_RE.search(tr) or _ENTITY_RE.search(src):
        return tr
    if "&" in src:
        return _ENTITY_RE.sub("&", tr)
    return html.unescape(tr)


def repair_translation(src, tr):
    """Fixes the usual machine-translation damage. Returns None if unusable."""
    if tr is None:
        return None
    tr = tr.replace("\\ n", "\\n").replace("\\N", "\\n")
    tr = fix_entities(src, tr)
    tr = fix_icon_prefix(src, tr)
    # Restore variables whose name was mangled ("${DB NAME}", "$V FAIL", "$Opac_url")
    for tok in dict.fromkeys(VAR_RE.findall(src)):
        if tok in tr:
            continue
        name = re.match(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", tok).group(1)
        fuzzy_name = r"[\s_]*".join(re.escape(part) for part in name.split("_"))
        if tok.startswith("${"):
            pattern = r"\$\s*\{?\s*" + fuzzy_name + r"\s*(?::-[^}]*)?\}?"
        else:
            pattern = r"\$\s*" + fuzzy_name + r"(?![A-Za-z0-9_])"
        tr, n = re.subn(pattern, lambda _m, t=tok: t, tr, count=1, flags=re.IGNORECASE)
    return tr if is_valid(src, tr) else None


# ----------------------------------------------------------------------
# Dictionary files
# ----------------------------------------------------------------------
def cache_path(lang):
    return os.path.join(LANG_DIR, f"{lang}.cache")


def read_cache(path):
    entries = {}
    if not os.path.exists(path):
        return entries
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            k, v = line.split("|", 1)
            try:
                entries[base64.b64decode(k).decode("utf-8")] = base64.b64decode(v).decode("utf-8")
            except Exception:
                continue
    return entries


def panel_version(installer_file=INSTALLER_FILE):
    """PANEL_VERSION of the installer, without the leading space."""
    try:
        with open(installer_file, "r", encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r'^PANEL_VERSION="\s*([^"]*)"', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return "unknown"


def cache_header():
    """First line of every dictionary; the panel checks it (LANG_CACHE_HEADER)."""
    return f"# koha-easy-installer lang {panel_version()}"


def write_cache(path, entries, order=None):
    keys = [k for k in (order or sorted(entries)) if k in entries]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as out:
        out.write(cache_header() + "\n")
        for k in keys:
            kb = base64.b64encode(k.encode("utf-8")).decode("ascii")
            vb = base64.b64encode(entries[k].encode("utf-8")).decode("ascii")
            out.write(f"{kb}|{vb}\n")
    os.replace(tmp, path)


def clean_entries(strings, entries):
    """Keeps only current keys, repaired. Returns (clean, dropped_keys)."""
    wanted = set(strings)
    by_stripped = {}
    for key in strings:
        by_stripped.setdefault(key.strip(), []).append(key)
    # Keys extracted by older tools kept bash escapes (\" and \$) and lost
    # their leading/trailing spaces, so they never matched at run time.
    for old_key in list(entries):
        if old_key in wanted:
            continue
        fixed = bash_unescape_double_quoted(old_key)
        for key in by_stripped.get(fixed.strip(), []):
            if key in entries:
                continue
            lead = key[: len(key) - len(key.lstrip())]
            trail = key[len(key.rstrip()):]
            entries[key] = lead + entries[old_key].strip() + trail
    clean, dropped = {}, []
    for key in strings:
        if key not in entries:
            continue
        tr = repair_translation(key, entries[key])
        if tr is None:
            dropped.append(key)
        else:
            clean[key] = tr
    return clean, dropped


def main(argv):
    fix = "--fix" in argv
    strings = extract_strings()
    print(f"[INFO] Frases traduzíveis no installer: {len(strings)}")
    for lang in TARGET_LANGS:
        path = cache_path(lang)
        entries = read_cache(path)
        clean, dropped = clean_entries(strings, dict(entries))
        stale = len([k for k in entries if k not in clean and k not in dropped])
        missing = len(strings) - len(clean)
        print(f"  {lang:>3}: {len(clean):4}/{len(strings)} ok | faltando {missing:3} | "
              f"quebradas {len(dropped):3} | obsoletas {stale:3}")
        if fix:
            write_cache(path, clean, order=strings)
    if fix:
        print("[OK] Dicionários reparados. Rode gen_all_langs.py para traduzir o que falta.")


if __name__ == "__main__":
    main(sys.argv[1:])
