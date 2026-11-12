"""The Language center (study 17.2): one row for the panel and one for each
system, each read from the setting the application itself uses.

  panel     translation.conf (KOHA_PANEL_LANG_FULL), as set_panel_language
            and the first screen write it
  Koha      --task koha-languages: the packs koha-translate installed and
            the OPACLanguages / StaffInterfaceLanguages preferences
  Tainacan  --status-json: the WordPress language the installer set
            (its state file), never the diagnosis
  DSpace    dspace-panel operations languages: the interface languages and
            the fallback of its configuration

Everything here only reads. The rows' buttons lead to the routines that
already change each one, with their own questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .i18n import t

WP_LOCALE = re.compile(r"^[a-z]{2,3}(_[A-Z]{2})?$")

# The WordPress languages offered for Tainacan: the panel's languages, by
# their WordPress locale (kei_tainacan_language checks the code again).
TAINACAN_LOCALES: tuple[tuple[str, str], ...] = (
    ("en_US", "English"),
    ("pt_BR", "Português (Brasil)"),
    ("es_ES", "Español"),
    ("fr_FR", "Français"),
    ("it_IT", "Italiano"),
    ("de_DE", "Deutsch"),
    ("nl_NL", "Nederlands"),
    ("sv_SE", "Svenska"),
    ("pl_PL", "Polski"),
    ("cs_CZ", "Čeština"),
    ("ru_RU", "Русский"),
    ("uk", "Українська"),
    ("tr_TR", "Türkçe"),
    ("tl", "Tagalog"),
    ("id_ID", "Bahasa Indonesia"),
    ("ar", "العربية"),
    ("fa_IR", "فارسی"),
    ("hi_IN", "हिन्दी"),
    ("bn_BD", "বাংলা"),
    ("vi", "Tiếng Việt"),
    ("zh_CN", "中文 (简体)"),
    ("ja", "日本語"),
    ("ko_KR", "한국어"),
)

# The rows of the center, in order: (id, title, platform; "" = the panel).
ROWS: tuple[tuple[str, str, str], ...] = (
    ("panel", "koha.nexus panel", ""),
    ("koha", "Koha (library)", "koha"),
    ("tainacan", "Tainacan (collections)", "tainacan"),
    ("dspace", "DSpace (repository)", "dspace"),
)

# The button of each row: (label, routine or "" for the Koha choice).
BUTTONS = {"panel": "Change", "koha": "Manage", "tainacan": "Change", "dspace": "Choose"}


@dataclass
class Row:
    value: str
    note: str = ""
    button: bool = True     # False: the system is not installed (no button)


def panel_code(conf: Path, fallback: str = "en") -> str:
    """The panel's language as translation.conf has it (the full code)."""
    try:
        text = conf.read_text(encoding="utf-8")
    except OSError:
        text = ""
    m = re.search(r'^\s*KOHA_PANEL_LANG_FULL="?([A-Za-z0-9-]+)"?', text, re.M)
    if m:
        return m.group(1)
    m = re.search(r'^\s*KOHA_PANEL_LANG="?([A-Za-z0-9-]+)"?', text, re.M)
    return m.group(1) if m else fallback


def name_of(code: str, items: list[tuple[str, str]] | tuple[tuple[str, str], ...]) -> str:
    """The name of a code in a (code, name) list; the code itself when it
    is not there. A short code ("pt") finds its full one ("pt-BR")."""
    names = dict(items)
    if code in names:
        return names[code]
    for full, name in items:
        if full.split("-")[0].split("_")[0] == code:
            return name
    return code


def panel_row(code: str, items: list[tuple[str, str]]) -> Row:
    return Row(f"{name_of(code, items)} ({code})", t("Changing it here does not change Koha, Tainacan or DSpace."))


def _codes(value: str) -> list[str]:
    return [c for c in (value or "").replace(" ", "").split(",") if c]


def koha_row(out) -> Row:
    """From --task koha-languages (None: this installer cannot tell)."""
    if out is None:
        return Row(t("Not read"), t("Update this panel to see the active languages here."))
    if out.get("koha") == "absent":
        return Row(t("Not installed"), button=False)
    installed = out.lists.get("installed") or ([out.get("installed")] if out.get("installed") else [])
    opac, staff = _codes(out.get("opac")), _codes(out.get("staff"))
    if not opac and not staff:
        value = t("Database not ready yet")
    else:
        value = f"OPAC: {', '.join(opac) or '-'} · {t('Staff')}: {', '.join(staff) or '-'}"
    note = t("Installed: ${codes}", codes=", ".join(installed) or "-")
    return Row(value, note)


def tainacan_row(lang: str) -> Row:
    lang = lang if WP_LOCALE.match(lang or "") else ""
    if not lang:
        return Row(t("Not recorded"), t("Choose one to set it."))
    return Row(f"WordPress: {name_of(lang, TAINACAN_LOCALES)} ({lang})", t("WordPress and the Tainacan plugin."))


def dspace_row(data: dict | None) -> Row:
    """From operations languages (None: not read)."""
    if not isinstance(data, dict) or not isinstance(data.get("active"), list):
        return Row(t("Not read"), t("Choose to see them."))
    active = [c for c in data["active"] if isinstance(c, str)]
    shown = ", ".join(active[:6]) + (f" (+{len(active) - 6})" if len(active) > 6 else "")
    fallback = data.get("fallback") if isinstance(data.get("fallback"), str) else "-"
    return Row(f"{t('Interface')}: {shown or '-'}", t("Default: ${code}", code=fallback))


def absent_row() -> Row:
    return Row(t("Not installed"), button=False)
