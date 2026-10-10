"""The OPAC's look: settings, the CSS and JS written into Koha, images.

The screen (views/opac.py) edits a settings dict; everything else lives
here, with no Textual:

  * settings: DEFAULTS, normalize() (every value checked and clamped: they
    end up in a public stylesheet);
  * css_block() / js_block(): the marked blocks `config.sh --task
    opac-theme-apply` puts in OpacUserCSS and OpacUserJS, the rest of both
    preferences kept as the library wrote it; staff_css_block(): the
    staff interface's block (IntranetUserCSS: colours, type, contrast and
    table density only, none of the OPAC's widgets). The first line inside the CSS
    block is /* KEI-THEME-DATA: {...} */, the settings as JSON, read back by
    parse_theme_data() when the screen opens (state lives in Koha, so a
    second server or a restored backup shows the settings it has; the
    installer also keeps a copy in theme-settings.json and puts it back
    after a database restore);
  * images: a file on the server (copied to Koha's public images folder),
    an upload to an image host (ImgBB with an API key, Cloudinary with an
    unsigned upload preset) or a direct URL. Keys stay in a private file of
    the panel, never in the public stylesheet.

Nothing here talks to Koha: the task does the backup, the lock, the
preferences and the files.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from .env import CONFIG_DIR

CSS_BEGIN = "/* koha-easy-installer opac-theme begin */"
CSS_END = "/* koha-easy-installer opac-theme end */"
JS_BEGIN = CSS_BEGIN
JS_END = CSS_END
DATA_TAG = "KEI-THEME-DATA:"
CUSTOM_URL = "/images/custom"                       # /usr/share/koha/opac/htdocs/images/custom
FEED_URL = CUSTOM_URL + "/kei-new-arrivals.json"    # written by the nightly job
KEYS_FILE = "opac-theme.conf"                       # image host keys (0600)

TEXTURES = {
    "frosted": "Frosted glass",
    "smooth": "Smooth glass",
    "metal": "Brushed metal",
    "flat": "Flat solid colour",
    "gradient": "Soft diagonal gradient",
}
HOVERS = {"zoom": "Smooth zoom", "lift": "Elevation shadow", "tilt": "Tilt", "none": "None"}
CAROUSEL_MODES = {"flat": "2D flat", "coverflow": "3D coverflow"}
LINK_STYLES = {"solid": "Solid colour", "gradient": "Gradient", "glass": "Glass (blur)"}
LINK_TARGETS = {"_self": "Same tab", "_blank": "New tab"}
STAFF_DENSITY = {"comfortable": "Comfortable", "normal": "Normal", "compact": "Compact"}
STAFF_CONTRAST = {"normal": "Normal", "high": "High"}
MAX_LINKS = 12
THEMES = {"light": "Light", "dark": "Dark", "auto": "Follow the device"}
SOURCES = {"none": "None", "local": "File on this server", "url": "Direct URL", "imgbb": "Upload to ImgBB",
           "cloudinary": "Upload to Cloudinary"}
ASSETS = ("background", "logo", "favicon")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".ico": "image/x-icon"}
MAX_IMAGE = 8_000_000

DEFAULTS: dict = {
    "version": 1,
    "texture": "frosted",
    "blur": 12,               # px, frosted glass
    "opacity": 78,            # % of the block surface
    "radius_block": 14,       # px, 0-30
    "radius_input": 10,
    "radius_button": 10,
    "accent": "#2563eb",
    "accent2": "#7c3aed",     # second colour of the gradient
    "surface": "#ffffff",     # background of the blocks (header, search, content, news)
    "page": "",               # background of the page ("" = Koha's own)
    "background": {"source": "none", "url": ""},
    "logo": {"source": "none", "url": ""},
    "favicon": {"source": "none", "url": ""},
    "film": 55,               # % of the legibility film over a wallpaper
    "dark_switch": True,
    "default_theme": "light",
    "carousel": {"enabled": True, "autoplay": True, "speed": 3500, "count": 12, "hover": "lift",
                 "overlay": True, "title": "New arrivals", "amazon_tag": "", "mode": "flat"},
    "ghost": {"rss": True, "cart_badge": True, "community": True, "empty_columns": True},
    "news_buttons": True,
    # Quick access buttons at the top of the home page (link-tree style):
    # [{"icon": "📖", "text": "...", "url": "https://...", "target": "_blank"}]
    "links": {"enabled": False, "style": "glass", "items": []},
    # The staff interface (IntranetUserCSS): the same colours, its own type,
    # contrast and table density.
    "staff": {"enabled": False, "density": "normal", "contrast": "normal", "font": 100},
}

RANGES = {"blur": (0, 30), "opacity": (30, 100), "radius_block": (0, 30), "radius_input": (0, 30),
          "radius_button": (0, 30), "film": (0, 90)}
CAROUSEL_RANGES = {"speed": (2000, 10000), "count": (4, 24)}
STAFF_FONT = (90, 120)


# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------
def _clamp(value, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(float(value))))
    except (TypeError, ValueError):
        return default


def _hex(value, default: str) -> str:
    value = str(value or "").strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        return "#" + value.lstrip("#").lower()
    if re.fullmatch(r"#?[0-9a-fA-F]{3}", value):
        return "#" + "".join(c * 2 for c in value.lstrip("#")).lower()
    return default


def safe_url(value: str) -> str:
    """An image address the stylesheet may carry: https, or a path of this
    OPAC. Anything else (javascript:, quotes, spaces) becomes ""."""
    value = str(value or "").strip()
    if re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?(/[A-Za-z0-9._~!$&'()*+,;=:@%/?-]*)?", value) or \
            re.fullmatch(r"/(?!/)[A-Za-z0-9._~%/?=&-]*", value):
        return "" if re.search(r"['()\\]", value) else value
    return ""


def _text(value, default: str, limit: int = 60) -> str:
    value = re.sub(r"[\x00-\x1f<>]", "", str(value if value is not None else default)).strip()
    return value[:limit]


def safe_link(value: str) -> str:
    """A button's destination: http(s), a path of this OPAC, mailto:, tel:
    or #anchor. Anything else (javascript:, data:, quotes) becomes ""."""
    value = str(value or "").strip()
    if len(value) > 500 or re.search(r"[\s\"'<>\\`]", value):
        return ""
    if re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d+)?(/\S*)?", value) or re.fullmatch(r"/(?!/)\S*", value) \
            or re.fullmatch(r"mailto:[^@\s]+@[A-Za-z0-9.-]+(\?\S*)?", value) or re.fullmatch(r"tel:\+?[0-9().-]{3,20}", value) \
            or re.fullmatch(r"#[\w-]*", value):
        return value
    return ""


def _link(raw) -> dict | None:
    raw = raw if isinstance(raw, dict) else {}
    url = safe_link(raw.get("url", ""))
    text = _text(raw.get("text"), "", 60)
    if not url or not text:
        return None
    icon = _text(raw.get("icon"), "", 24)
    if icon.startswith("fa-"):
        icon = icon if re.fullmatch(r"fa-[a-z0-9-]{1,30}", icon) else ""
    else:
        icon = icon[:4]
    target = raw.get("target") if raw.get("target") in LINK_TARGETS else "_self"
    return {"icon": icon, "text": text, "url": url, "target": target}


def normalize(raw: dict | None) -> dict:
    """Every setting checked: unknown keys dropped, numbers clamped, colours
    and URLs validated, defaults where missing."""
    raw = raw if isinstance(raw, dict) else {}
    cfg = copy.deepcopy(DEFAULTS)
    cfg["texture"] = raw.get("texture") if raw.get("texture") in TEXTURES else DEFAULTS["texture"]
    for key, (lo, hi) in RANGES.items():
        cfg[key] = _clamp(raw.get(key, DEFAULTS[key]), lo, hi, DEFAULTS[key])
    cfg["accent"] = _hex(raw.get("accent"), DEFAULTS["accent"])
    cfg["accent2"] = _hex(raw.get("accent2"), DEFAULTS["accent2"])
    cfg["surface"] = _hex(raw.get("surface"), DEFAULTS["surface"])
    cfg["page"] = _hex(raw.get("page"), "") if raw.get("page") else ""
    for name in ASSETS:
        a = raw.get(name) if isinstance(raw.get(name), dict) else {}
        source = a.get("source") if a.get("source") in SOURCES else "none"
        url = safe_url(a.get("url", ""))
        cfg[name] = {"source": source, "url": url if source != "none" else ""}
    cfg["dark_switch"] = bool(raw.get("dark_switch", DEFAULTS["dark_switch"]))
    cfg["default_theme"] = raw.get("default_theme") if raw.get("default_theme") in THEMES else "light"
    c = raw.get("carousel") if isinstance(raw.get("carousel"), dict) else {}
    car = cfg["carousel"]
    car["enabled"] = bool(c.get("enabled", car["enabled"]))
    car["autoplay"] = bool(c.get("autoplay", car["autoplay"]))
    for key, (lo, hi) in CAROUSEL_RANGES.items():
        car[key] = _clamp(c.get(key, car[key]), lo, hi, car[key])
    car["hover"] = c.get("hover") if c.get("hover") in HOVERS else car["hover"]
    car["overlay"] = bool(c.get("overlay", car["overlay"]))
    car["title"] = _text(c.get("title"), car["title"])
    tag = str(c.get("amazon_tag", "")).strip()
    car["amazon_tag"] = tag if re.fullmatch(r"[A-Za-z0-9-]{0,40}", tag) else ""
    car["mode"] = c.get("mode") if c.get("mode") in CAROUSEL_MODES else car["mode"]
    g = raw.get("ghost") if isinstance(raw.get("ghost"), dict) else {}
    for key in cfg["ghost"]:
        cfg["ghost"][key] = bool(g.get(key, cfg["ghost"][key]))
    cfg["news_buttons"] = bool(raw.get("news_buttons", DEFAULTS["news_buttons"]))
    lk = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    items = lk.get("items") if isinstance(lk.get("items"), list) else []
    cfg["links"] = {"enabled": bool(lk.get("enabled", False)),
                    "style": lk.get("style") if lk.get("style") in LINK_STYLES else DEFAULTS["links"]["style"],
                    "items": [x for x in (_link(i) for i in items) if x][:MAX_LINKS]}
    st = raw.get("staff") if isinstance(raw.get("staff"), dict) else {}
    cfg["staff"] = {"enabled": bool(st.get("enabled", False)),
                    "density": st.get("density") if st.get("density") in STAFF_DENSITY else "normal",
                    "contrast": st.get("contrast") if st.get("contrast") in STAFF_CONTRAST else "normal",
                    "font": _clamp(st.get("font", 100), *STAFF_FONT, 100)}
    return cfg


def data_line(cfg: dict) -> str:
    """The settings as a CSS comment (one line; "*/" cannot end it early)."""
    text = json.dumps(normalize(cfg), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    text = text.replace("*/", "*\\/").replace("</", "<\\/")
    return "/* " + DATA_TAG + " " + text + " */"


def parse_theme_data(text: str) -> dict | None:
    """The settings of a KEI-THEME-DATA comment anywhere in text (the CSS
    block, or the whole OpacUserCSS), or None."""
    m = re.search(r"/\*\s*" + re.escape(DATA_TAG) + r"\s*(\{.*?\})\s*\*/", text or "", re.S)
    if not m:
        return None
    try:
        return normalize(json.loads(m.group(1)))
    except ValueError:
        return None


def _rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def luminance(hex_color: str) -> float:
    """Relative luminance (WCAG) of #rrggbb, 0 (black) to 1 (white)."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def text_on(hex_color: str) -> str:
    """Dark or light text, whichever reads better on hex_color."""
    return "#111827" if luminance(hex_color) > 0.40 else "#ffffff"


# ----------------------------------------------------------------------
# The stylesheet
# ----------------------------------------------------------------------
# The big blocks (the texture) and the content blocks inside them (a
# solid card with the accent on its edge). "html body" before each one, and
# !important, so Koha's Bootstrap rules never win over the chosen colours.
_BLOCKS = "#header-region .navbar, .navbar.navbar-expand, #opac-main-search, .mastheadsearch, .main"
_CONTENT = "#opacmainuserblock, #opacmainblock, #news .newsitem, .newsitem, .news-item"


def _strong(selectors: str) -> str:
    return ", ".join("html body " + x.strip() for x in selectors.split(","))


def _texture_css(cfg: dict) -> str:
    t = cfg["texture"]
    surface = "rgba(var(--kei-surface-rgb), var(--kei-surface-a))"
    base = [f"{_strong(_BLOCKS)} {{", f"    background: {surface} !important;", "    color: var(--kei-text);",
            "    border-radius: var(--kei-r-block) !important;", "    border: 1px solid var(--kei-edge) !important;"]
    if t == "frosted":
        base += ["    -webkit-backdrop-filter: blur(var(--kei-blur)) saturate(140%);",
                 "    backdrop-filter: blur(var(--kei-blur)) saturate(140%);",
                 "    box-shadow: 0 8px 32px rgba(0, 0, 0, .12);"]
    elif t == "smooth":
        base += ["    box-shadow: 0 4px 18px rgba(0, 0, 0, .08);"]
    elif t == "metal":
        base[1] = (f"    background: linear-gradient(180deg, rgba(255, 255, 255, .22), rgba(0, 0, 0, .06)), "
                   "repeating-linear-gradient(90deg, rgba(255, 255, 255, .05) 0 1px, transparent 1px 3px), "
                   f"{surface} !important;")
        base += ["    box-shadow: inset 0 1px 0 rgba(255, 255, 255, .55), inset 0 -1px 0 rgba(0, 0, 0, .18), "
                 "0 2px 8px rgba(0, 0, 0, .14);"]
    elif t == "flat":
        base[1] = "    background: rgb(var(--kei-surface-rgb)) !important;"
    elif t == "gradient":
        base[1] = (f"    background: linear-gradient(135deg, {surface} 0%, "
                   "rgba(var(--kei-accent-rgb), .10) 55%, rgba(var(--kei-accent2-rgb), .14) 100%) !important;")
    base.append("}")
    base.append(f"""{_strong(_CONTENT)} {{
    background: rgba(var(--kei-surface-rgb), calc(var(--kei-surface-a) * .5 + .5)) !important;
    color: var(--kei-text) !important;
    border: 1px solid var(--kei-edge) !important;
    border-left: 4px solid var(--nexus-primary) !important;
    border-radius: calc(var(--kei-r-block) * .7) !important;
    padding: .9rem 1.1rem;
    margin-bottom: 1rem;
}}
html body .main h1, html body .main h2, html body .main h3, html body .main h4, html body .main legend,
html body .newsitem h3, html body .news-item h3 {{ color: var(--kei-text); }}
html body .main .text-muted, html body .newsitem .newsfooter {{ color: var(--kei-muted) !important; }}""")
    return "\n".join(base)


def css_body(cfg: dict) -> str:
    cfg = normalize(cfg)
    car, ghost = cfg["carousel"], cfg["ghost"]
    dark_surface = luminance(cfg["surface"]) < 0.30
    text, muted, edge = (("#f1f5f9", "#cbd5e1", "rgba(255, 255, 255, .14)") if dark_surface
                         else ("#1f2933", "#52606d", "rgba(15, 23, 42, .10)"))
    out = [f""":root {{
    --nexus-primary: {cfg['accent']};
    --nexus-secondary: {cfg['accent2']};
    --nexus-surface: {cfg['surface']};
    --nexus-text: {text};
    --nexus-on-primary: {text_on(cfg['accent'])};
    --kei-accent: {cfg['accent']};
    --kei-accent-rgb: {_rgb(cfg['accent'])};
    --kei-accent2-rgb: {_rgb(cfg['accent2'])};
    --kei-surface-rgb: {_rgb(cfg['surface'])};
    --kei-surface-a: {cfg['opacity'] / 100:.2f};
    --kei-text: {text};
    --kei-muted: {muted};
    --kei-edge: {edge};
    --kei-blur: {cfg['blur']}px;
    --kei-r-block: {cfg['radius_block']}px;
    --kei-r-input: {cfg['radius_input']}px;
    --kei-r-btn: {cfg['radius_button']}px;
    --kei-film: {cfg['film'] / 100:.2f};
}}
html[data-kei-theme="dark"] {{
    --kei-surface-rgb: 22, 27, 34;
    --kei-text: #e6edf3;
    --kei-muted: #9da7b3;
    --kei-edge: rgba(255, 255, 255, .10);
    color-scheme: dark;
}}
html[data-kei-theme="dark"] body {{ background-color: #0d1117; color: var(--kei-text); }}
html[data-kei-theme="dark"] .main, html[data-kei-theme="dark"] .main h1, html[data-kei-theme="dark"] .main h2,
html[data-kei-theme="dark"] .main h3, html[data-kei-theme="dark"] .table, html[data-kei-theme="dark"] .navbar,
html[data-kei-theme="dark"] #opac-main-search {{ color: var(--kei-text) !important; }}
html[data-kei-theme="dark"] .table {{ --bs-table-bg: transparent; --bs-table-color: var(--kei-text); }}
html[data-kei-theme="dark"] .form-control, html[data-kei-theme="dark"] .form-select,
html[data-kei-theme="dark"] input[type="text"], html[data-kei-theme="dark"] select,
html[data-kei-theme="dark"] textarea {{ background-color: #161b22; color: var(--kei-text); border-color: #30363d; }}
html[data-kei-theme="dark"] a:not(.btn) {{ color: #79b8ff; }}
html[data-kei-theme="dark"] .text-muted, html[data-kei-theme="dark"] .breadcrumb-item {{ color: var(--kei-muted) !important; }}
{_texture_css(cfg)}
html body .main {{ padding: 1.25rem; margin-top: 1rem; }}
.form-control, .form-select, input[type="text"], input[type="search"], input[type="password"], select,
textarea {{ border-radius: var(--kei-r-input) !important; }}
{_buttons_css(cfg)}
a:focus-visible, .btn:focus-visible {{ outline: 3px solid rgba(var(--kei-accent-rgb), .45); outline-offset: 2px; }}"""]
    bg = cfg["background"]["url"]
    if not bg:
        out.append(_canvas_css(cfg))
    elif cfg["page"]:
        out.append(f"html body {{ background-color: {cfg['page']} !important; }}")
    if bg:
        out.append(f"""body.kei-wallpaper {{
    background: url("{bg}") center / cover no-repeat fixed !important;
    position: relative;
    z-index: 0;
}}
/* The legibility film: between the wallpaper and the blocks. */
body.kei-wallpaper::before {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: rgba(255, 255, 255, var(--kei-film));
}}
html[data-kei-theme="dark"] body.kei-wallpaper::before {{ background: rgba(8, 12, 20, calc(var(--kei-film) + .1)); }}""")
    logo = cfg["logo"]["url"]
    if logo:
        out.append(f"""#logo, h1#logo a, .navbar-brand#logo {{
    background-image: url("{logo}") !important;
    background-size: contain !important;
    background-repeat: no-repeat !important;
    background-position: left center !important;
    min-width: 140px;
}}""")
    hidden = []
    if ghost["rss"]:
        hidden += ["#rssnews", ".rsssearchlink", "a[href*='opac-news-rss']", "a[href*='format=rss']", "#rss"]
    if ghost["cart_badge"]:
        hidden += ["#basketcount", "#cartDetails", "#cartmenulink .badge"]
    if ghost["community"]:
        hidden += ["#koha_url", "a[href*='koha-community.org']"]
    if hidden:
        out.append(",\n".join(hidden) + " { display: none !important; }")
    if ghost["empty_columns"]:
        out.append(".kei-empty-col { display: none !important; }")
    if cfg["dark_switch"]:
        out.append("""#kei-theme-switch {
    border: 1px solid var(--kei-edge);
    background: rgba(var(--kei-surface-rgb), .85);
    color: var(--kei-text);
    border-radius: 999px;
    padding: .2rem .65rem;
    margin: 0 .5rem;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1.4;
}
#kei-theme-switch:hover { border-color: var(--kei-accent); }""")
    if cfg["news_buttons"]:
        out.append(""".kei-action {
    display: flex;
    gap: .9rem;
    align-items: center;
    padding: .9rem 1.1rem;
    margin: .6rem 0;
    border-radius: var(--kei-r-btn);
    border: 1px solid var(--kei-edge);
    background: rgba(var(--kei-surface-rgb), var(--kei-surface-a));
    color: var(--kei-text) !important;
    text-decoration: none !important;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.kei-action:hover, .kei-action:focus { transform: translateY(-2px); border-color: var(--kei-accent);
    box-shadow: 0 10px 24px rgba(var(--kei-accent-rgb), .18); }
.kei-action-icon { font-size: 1.6rem; color: var(--kei-accent); min-width: 2rem; text-align: center; }
.kei-action-title { display: block; font-weight: 600; }
.kei-action-text { display: block; color: var(--kei-muted); font-size: .92em; }""")
    if car["enabled"]:
        out.append(_carousel_css(car))
    if cfg["links"]["enabled"] and cfg["links"]["items"]:
        out.append(_links_css())
    return "\n".join(out) + "\n"


# Every kind of button Koha draws: Bootstrap's, the masthead search button
# and the bare submit inputs of older templates and news. The carousel
# arrows, the theme switch and the quick-access links keep their own look.
_BTN_MAIN = ('.btn-primary, #searchsubmit, .btn-acesso, input[type="submit"]:not(.btn), '
             'button[type="submit"]:not(.btn):not(.kei-nav)')
_BTN_SOFT = ('.btn-default, .btn-secondary, .btn-light, .btn-outline-primary, .btn-outline-secondary, '
             'input[type="button"]:not(.btn), input[type="reset"]:not(.btn), #backtotop')
# Buttons inside the news and the library's own home page block: action
# cards, full width, big enough to tap.
_CARD_AREAS = ("#news .newsitem", ".newsitem", ".news-item", "#opacmainuserblock", "#OpacMainUserBlock")
_CARD_BUTTONS = (".btn", 'input[type="submit"]', 'input[type="button"]', 'button[type="submit"]')


def _buttons_css(cfg: dict) -> str:
    """The OPAC's buttons: the main ones in the accent colour (a brushed
    sheen with the metal texture), the secondary ones on the block surface,
    and full-width touch targets inside the news and the home page block."""
    main, soft = _strong(_BTN_MAIN), _strong(_BTN_SOFT)

    def hover(sel: str) -> str:
        return ", ".join(f"{x}:hover, {x}:focus" for x in sel.split(", "))

    if cfg["texture"] == "metal":
        main_bg = ("linear-gradient(180deg, rgba(255, 255, 255, .38) 0%, rgba(255, 255, 255, .08) 50%, "
                   "rgba(0, 0, 0, .14) 100%), var(--nexus-primary)")
        soft_bg = "linear-gradient(180deg, #f0f0f0 0%, #dcdcdc 50%, #c9c9c9 100%)"
        soft_fg, soft_edge = "#333", "#b3b3b3"
        shadow = ("inset 0 1px 0 rgba(255, 255, 255, .6), inset 0 -1px 0 rgba(0, 0, 0, .2), "
                  "0 4px 6px rgba(0, 0, 0, .12)")
    else:
        main_bg = ("linear-gradient(180deg, rgba(255, 255, 255, .16), rgba(255, 255, 255, 0) 60%), "
                   "var(--nexus-primary)")
        soft_bg = "rgba(var(--kei-surface-rgb), calc(var(--kei-surface-a) * .5 + .5))"
        soft_fg, soft_edge = "var(--kei-text)", "var(--kei-edge)"
        shadow = "inset 0 1px 0 rgba(255, 255, 255, .25), 0 2px 6px rgba(15, 23, 42, .14)"
    areas = ", ".join(f"html body {a} {b}" for a in _CARD_AREAS for b in _CARD_BUTTONS)
    return f""".btn, button.btn, input[type="submit"], input[type="button"], input[type="reset"] {{
    border-radius: var(--kei-r-btn) !important; }}
{main} {{
    background: {main_bg} !important;
    border: 1px solid var(--nexus-primary) !important;
    color: var(--nexus-on-primary) !important;
    font-weight: 600 !important;
    box-shadow: {shadow} !important;
    transition: filter .18s ease, transform .18s ease, box-shadow .18s ease;
    cursor: pointer;
}}
{soft} {{
    background: {soft_bg} !important;
    border: 1px solid {soft_edge} !important;
    color: {soft_fg} !important;
    font-weight: 600 !important;
    box-shadow: {shadow} !important;
    transition: filter .18s ease, transform .18s ease, border-color .18s ease;
    cursor: pointer;
}}
{hover(main)}, {hover(soft)} {{ filter: brightness(1.06); transform: translateY(-1px); }}
{hover(soft)} {{ border-color: var(--nexus-primary) !important; }}
{areas} {{
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
    min-height: 44px;
    padding: .75rem 1.1rem !important;
    line-height: 1.4;
    text-decoration: none !important;
    margin: .5rem 0 !important;
    font-size: 1.02rem;
    text-align: center;
    white-space: normal;
}}
@media (prefers-reduced-motion: reduce) {{ {main}, {soft} {{ transition: none; }} }}"""


def _canvas_css(cfg: dict) -> str:
    """No wallpaper: a page with some depth instead of a flat white sheet,
    so the blocks (white ones above all) stand out and glass has something
    to blur. The library's page colour, or a soft grey, under two faint
    glows of the accent colours; the blocks get a layered shadow."""
    light = luminance(cfg["surface"]) >= 0.30
    base = cfg["page"] or ("#e8ecf2" if light else "#1b2230")
    shadow = ("0 1px 2px rgba(15, 23, 42, .06), 0 12px 32px -10px rgba(15, 23, 42, .22)" if light
              else "0 1px 2px rgba(0, 0, 0, .25), 0 12px 32px -10px rgba(0, 0, 0, .55)")
    glows = ("radial-gradient(1200px 600px at 0% 0%, rgba(var(--kei-accent-rgb), .16), transparent 60%), "
             "radial-gradient(1000px 600px at 100% 100%, rgba(var(--kei-accent2-rgb), .14), transparent 60%)")
    lines = [f"""html body {{
    background: {glows}, {base} !important;
    background-attachment: fixed !important;
}}
html[data-kei-theme="dark"] body {{
    background: {glows.replace(".16", ".10").replace(".14", ".08")}, #0d1117 !important;
}}"""]
    if cfg["texture"] != "metal":
        lines.append(f"""{_strong(_BLOCKS + ", " + _CONTENT)} {{
    box-shadow: {shadow}, inset 0 1px 0 rgba(255, 255, 255, {".55" if light else ".06"});
}}""")
    return "\n".join(lines)


def _links_css() -> str:
    return """#kei-links {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
    gap: .75rem;
    margin: 0 0 1.25rem;
}
html body a.kei-link {
    display: flex;
    align-items: center;
    gap: .75rem;
    padding: .85rem 1.1rem;
    border-radius: var(--kei-r-btn);
    font-weight: 600;
    text-decoration: none !important;
    transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
}
html body a.kei-link:hover, html body a.kei-link:focus-visible { transform: translateY(-2px); filter: brightness(1.05); }
.kei-link-icon { font-size: 1.35rem; line-height: 1; min-width: 1.6rem; text-align: center; }
html body .kei-links-solid a.kei-link { background: var(--nexus-primary); color: var(--nexus-on-primary) !important;
    box-shadow: 0 4px 14px rgba(var(--kei-accent-rgb), .30); }
html body .kei-links-gradient a.kei-link { color: #fff !important;
    background: linear-gradient(135deg, var(--nexus-primary), var(--nexus-secondary));
    box-shadow: 0 6px 18px rgba(var(--kei-accent2-rgb), .28); }
html body .kei-links-glass a.kei-link { color: var(--kei-text) !important;
    background: rgba(var(--kei-surface-rgb), .55);
    -webkit-backdrop-filter: blur(10px) saturate(150%);
    backdrop-filter: blur(10px) saturate(150%);
    border: 1px solid rgba(255, 255, 255, .45);
    box-shadow: 0 8px 24px rgba(0, 0, 0, .12), inset 0 1px 0 rgba(255, 255, 255, .35); }
html body .kei-links-glass a.kei-link:hover { border-color: var(--nexus-primary); }
@media (prefers-reduced-motion: reduce) { html body a.kei-link { transition: none; } }"""


def _carousel_css(car: dict) -> str:
    hover = {
        "zoom": ".kei-card:hover img, .kei-card:focus img { transform: scale(1.06); }",
        "lift": ".kei-card:hover, .kei-card:focus { transform: translateY(-6px); "
                "box-shadow: 0 18px 36px rgba(0, 0, 0, .28); }",
        "tilt": ".kei-card { transform-style: preserve-3d; will-change: transform; }",
        "none": "",
    }[car["hover"]]
    return f"""#kei-carousel {{ position: relative; margin: 0 0 1.5rem; }}
#kei-carousel h2 {{ font-size: 1.35rem; margin: 0 0 .75rem; }}
.kei-track {{
    display: flex;
    gap: 1rem;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scroll-behavior: smooth;
    padding: .5rem .25rem 1rem;
    scrollbar-width: thin;
}}
.kei-card {{
    position: relative;
    flex: 0 0 auto;
    width: 150px;
    aspect-ratio: 2 / 3;
    scroll-snap-align: start;
    border-radius: calc(var(--kei-r-block) * .6);
    overflow: hidden;
    background: rgba(var(--kei-surface-rgb), .6);
    box-shadow: 0 6px 16px rgba(0, 0, 0, .18);
    transition: transform .25s ease, box-shadow .25s ease;
}}
.kei-card img {{ width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .35s ease; }}
{hover}
.kei-card-info {{
    position: absolute;
    inset: auto 0 0 0;
    padding: .6rem .6rem .5rem;
    color: #fff;
    font-size: .8rem;
    line-height: 1.25;
    background: linear-gradient(180deg, transparent, rgba(0, 0, 0, .85) 45%);
    opacity: 0;
    transform: translateY(12px);
    transition: opacity .25s ease, transform .25s ease;
}}
.kei-card:hover .kei-card-info, .kei-card:focus .kei-card-info {{ opacity: 1; transform: none; }}
.kei-card-info strong {{ display: block; font-size: .86rem; }}
.kei-card-info span {{ display: block; opacity: .85; }}
.kei-badge {{ display: inline-block; margin-top: .3rem; padding: .05rem .45rem; border-radius: 999px;
    font-size: .72rem; font-weight: 600; background: #2f855a; color: #fff; }}
.kei-badge.kei-out {{ background: #b7791f; }}
.kei-nav {{
    position: absolute;
    top: 45%;
    z-index: 2;
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 50%;
    border: 1px solid var(--kei-edge);
    background: rgba(var(--kei-surface-rgb), .9);
    color: var(--kei-text);
    font-size: 1.3rem;
    line-height: 1;
    cursor: pointer;
}}
.kei-nav:hover {{ border-color: var(--kei-accent); }}
.kei-prev {{ left: -.6rem; }}
.kei-next {{ right: -.6rem; }}
/* 3D coverflow: the cards stand on a stage and turn around the centre one. */
.kei-mode-coverflow .kei-stage {{
    position: relative;
    height: 290px;
    perspective: 1100px;
    overflow: hidden;
    touch-action: pan-y;
    user-select: none;
}}
.kei-mode-coverflow .kei-card {{
    position: absolute;
    left: 50%;
    top: 12px;
    width: 170px;
    margin-left: -85px;
    transition: transform .6s cubic-bezier(.22, .61, .36, 1), opacity .6s ease, box-shadow .6s ease;
    box-shadow: 0 18px 30px rgba(0, 0, 0, .35);
}}
.kei-mode-coverflow .kei-card::after {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(90deg, rgba(0, 0, 0, var(--kei-shade-l, 0)), rgba(0, 0, 0, var(--kei-shade-r, 0)));
    transition: background .6s ease;
}}
.kei-mode-coverflow .kei-card.kei-center {{ box-shadow: 0 24px 40px rgba(0, 0, 0, .45); }}
.kei-mode-coverflow .kei-card.kei-center .kei-card-info {{ opacity: 1; transform: none; }}
.kei-mode-coverflow .kei-nav {{ top: 42%; }}
.kei-mode-coverflow .kei-prev {{ left: .4rem; }}
.kei-mode-coverflow .kei-next {{ right: .4rem; }}
@media (prefers-reduced-motion: reduce) {{
    .kei-card, .kei-card img, .kei-card-info, .kei-track {{ transition: none; scroll-behavior: auto; }}
    .kei-mode-coverflow .kei-card {{ transition: none; }}
}}"""


def css_block(cfg: dict) -> str:
    return "\n".join([CSS_BEGIN, data_line(cfg), css_body(cfg).rstrip("\n"), CSS_END]) + "\n"


# ----------------------------------------------------------------------
# The staff interface (IntranetUserCSS)
# ----------------------------------------------------------------------
_STAFF_PAD = {"compact": ".2rem .45rem", "comfortable": ".65rem .85rem"}


def staff_css_body(cfg: dict) -> str:
    """The OPAC's colours on the staff interface, with its own type size,
    contrast and table density. Only CSS: no carousel, buttons or other
    OPAC widget ever reaches the staff pages."""
    cfg = normalize(cfg)
    st = cfg["staff"]
    on = text_on(cfg["accent"])
    out = [f""":root {{
    --nexus-primary: {cfg['accent']};
    --nexus-secondary: {cfg['accent2']};
    --nexus-on-primary: {on};
    --nexus-primary-rgb: {_rgb(cfg['accent'])};
}}
html {{ font-size: {st['font']}%; }}
html body #header.navbar, html body #header, html body .navbar.navbar-expand#header {{
    background: linear-gradient(90deg, var(--nexus-primary), var(--nexus-secondary)) !important;
    border-color: transparent !important;
}}
html body #header a, html body #header .navbar-nav > li > a, html body #header .nav-link,
html body #header .navbar-text {{ color: var(--nexus-on-primary) !important; }}
html body .btn-primary, html body .btn-primary:hover, html body .btn-primary:focus {{
    background-color: var(--nexus-primary) !important;
    border-color: var(--nexus-primary) !important;
    color: var(--nexus-on-primary) !important;
}}
html body .nav-tabs .nav-link.active, html body .ui-tabs .ui-tabs-nav li.ui-tabs-active {{
    border-top: 3px solid var(--nexus-primary) !important;
}}
html body a:focus-visible, html body .btn:focus-visible, html body input:focus, html body select:focus,
html body textarea:focus {{
    outline: 3px solid rgba(var(--nexus-primary-rgb), .45) !important;
    outline-offset: 1px;
}}"""]
    pad = _STAFF_PAD.get(st["density"])
    if pad:
        out.append(f"""html body table td, html body table th, html body .table > :not(caption) > * > * {{
    padding: {pad} !important;
}}""")
        if st["density"] == "compact":
            out.append("html body table { line-height: 1.25; }")
    if st["contrast"] == "high":
        out.append("""html body { color: #000 !important; }
html body .text-muted, html body .hint, html body .help-block, html body .form-text { color: #1f1f1f !important; }
html body table, html body table td, html body table th { border-color: #4b5563 !important; }
html body a:not(.btn) { text-decoration: underline; text-underline-offset: 2px; }
html body .btn { border-width: 2px; }""")
    return "\n".join(out) + "\n"


def staff_css_block(cfg: dict) -> str:
    return "\n".join([CSS_BEGIN, staff_css_body(cfg).rstrip("\n"), CSS_END]) + "\n"


# ----------------------------------------------------------------------
# The script
# ----------------------------------------------------------------------
_JS = r"""(function () {
    "use strict";
    var C = __CONFIG__;
    var root = document.documentElement;
    var KEY = "kei_theme";
    function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
    function save(t) { try { localStorage.setItem(KEY, t); } catch (e) { /* private window */ } }
    function setTheme(t) { root.setAttribute("data-kei-theme", t); }
    var theme = stored();
    if (theme !== "dark" && theme !== "light") {
        theme = C.default_theme === "auto"
            ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
            : C.default_theme;
    }
    setTheme(theme);

    function ready(fn) {
        if (document.readyState !== "loading") { fn(); } else { document.addEventListener("DOMContentLoaded", fn); }
    }

    ready(function () {
        if (C.wallpaper) { document.body.classList.add("kei-wallpaper"); }

        // The theme switch, next to the language selector of the bottom bar.
        if (C.dark_switch && !document.getElementById("kei-theme-switch")) {
            var b = document.createElement("button");
            b.type = "button";
            b.id = "kei-theme-switch";
            b.title = C.text.switch_title;
            b.setAttribute("aria-label", C.text.switch_title);
            b.textContent = "\uD83C\uDF13";
            b.addEventListener("click", function () {
                theme = root.getAttribute("data-kei-theme") === "dark" ? "light" : "dark";
                setTheme(theme);
                save(theme);
            });
            var place = document.getElementById("changelanguage") || document.querySelector("#i18nMenu, .i18nMenu")
                || document.querySelector("footer, #opac-footer, .footer");
            if (place && place.parentNode && place.id === "changelanguage") {
                place.appendChild(b);
            } else if (place) {
                place.insertBefore(b, place.firstChild);
            } else {
                b.style.position = "fixed"; b.style.right = "1rem"; b.style.bottom = "1rem"; b.style.zIndex = "1000";
                document.body.appendChild(b);
            }
        }

        // Ghost columns: a column of a results table with nothing in it.
        if (C.empty_columns) {
            Array.prototype.forEach.call(document.querySelectorAll(".main table"), function (table) {
                var rows = table.querySelectorAll("tbody tr");
                if (!rows.length) { return; }
                var n = rows[0].children.length;
                for (var i = 0; i < n; i++) {
                    var empty = true;
                    for (var r = 0; r < rows.length && empty; r++) {
                        var cell = rows[r].children[i];
                        if (cell && (cell.textContent.trim() || cell.querySelector("img, input, a, button"))) { empty = false; }
                    }
                    if (!empty) { continue; }
                    Array.prototype.forEach.call(table.querySelectorAll("tr"), function (tr) {
                        if (tr.children[i]) { tr.children[i].classList.add("kei-empty-col"); }
                    });
                }
            });
        }

        // News action buttons: [kei-button title="..." icon="..." url="..."]text[/kei-button]
        if (C.news_buttons) {
            var MARK = /\[kei-button([^\]]*)\]([\s\S]*?)\[\/kei-button\]/g;
            var areas = document.querySelectorAll("#news, .newsitem, .newscontainer, #opacmainuserblock, #OpacMainUserBlock, .default_item");
            Array.prototype.forEach.call(areas, function (area) {
                if (area.getAttribute("data-kei-buttons") || area.innerHTML.indexOf("[kei-button") < 0) { return; }
                area.setAttribute("data-kei-buttons", "1");
                var made = [];
                area.innerHTML = area.innerHTML.replace(MARK, function (all, attrs, body) {
                    made.push({ attrs: attrs.replace(/&quot;/g, "\"").replace(/&amp;/g, "&"), body: body });
                    return "<span data-kei-btn=\"" + (made.length - 1) + "\"></span>";
                });
                made.forEach(function (m, i) {
                    var a = {};
                    m.attrs.replace(/(\w+)\s*=\s*"([^"]*)"/g, function (x, k, v) { a[k.toLowerCase()] = v; return x; });
                    var tmp = document.createElement("template");   // inert: nothing in it runs
                    tmp.innerHTML = m.body;
                    tmp = tmp.content;
                    var url = /^(https?:\/\/|\/|#)/.test(a.url || "") ? a.url : "#";
                    var link = document.createElement("a");
                    link.className = "kei-action";
                    link.href = url;
                    if (/^https?:/.test(url) && url.indexOf(location.host) < 0) { link.rel = "noopener"; link.target = "_blank"; }
                    var icon = document.createElement("span");
                    icon.className = "kei-action-icon";
                    if (/^fa-[a-z0-9-]+$/.test(a.icon || "")) {
                        var i2 = document.createElement("i");
                        i2.className = "fa " + a.icon;
                        i2.setAttribute("aria-hidden", "true");
                        icon.appendChild(i2);
                    } else {
                        icon.textContent = (a.icon || "\u279C").slice(0, 4);
                    }
                    var words = document.createElement("span");
                    var t = document.createElement("span");
                    t.className = "kei-action-title";
                    t.textContent = a.title || tmp.textContent.trim();
                    words.appendChild(t);
                    if (a.title && tmp.textContent.trim()) {
                        var d = document.createElement("span");
                        d.className = "kei-action-text";
                        d.textContent = tmp.textContent.trim();
                        words.appendChild(d);
                    }
                    link.appendChild(icon);
                    link.appendChild(words);
                    var holder = area.querySelector("[data-kei-btn=\"" + i + "\"]");
                    if (holder) { holder.parentNode.replaceChild(link, holder); }
                });
            });
        }

        var home = document.getElementById("opac-main") || /opac-main\.pl$/.test(location.pathname)
            || location.pathname === "/";

        // Quick access buttons (link-tree style), at the top of the home page.
        if (C.links && home && !document.getElementById("kei-links")) { links(C.links); }

        // New arrivals, on the OPAC home page only.
        if (C.carousel && home && !document.getElementById("kei-carousel") && window.fetch) {
            fetch(C.carousel.feed, { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : { items: [] }; })
                .then(function (feed) { carousel(feed.items || []); })
                .catch(function () { /* no feed yet: no carousel */ });
        }
    });

    function homeTarget() {
        return document.getElementById("opacmainuserblock") || document.getElementById("opacmainblock")
            || document.querySelector(".maincontent") || document.querySelector(".main");
    }

    function links(L) {
        var place = homeTarget();
        if (!place || !L.items || !L.items.length) { return; }
        var nav = document.createElement("nav");
        nav.id = "kei-links";
        nav.className = "kei-links-" + L.style;
        nav.setAttribute("aria-label", C.text.links);
        L.items.forEach(function (it) {
            var url = /^(https?:\/\/|\/(?!\/)|mailto:|tel:|#)/.test(it.url || "") ? it.url : "";
            if (!url) { return; }
            var a = document.createElement("a");
            a.className = "kei-link";
            a.href = url;
            if (it.target === "_blank") { a.target = "_blank"; a.rel = "noopener noreferrer"; }
            var icon = document.createElement("span");
            icon.className = "kei-link-icon";
            icon.setAttribute("aria-hidden", "true");
            if (/^fa-[a-z0-9-]+$/.test(it.icon || "")) {
                var i = document.createElement("i");
                i.className = "fa " + it.icon;
                icon.appendChild(i);
            } else {
                icon.textContent = it.icon || "➜";
            }
            var label = document.createElement("span");
            label.textContent = it.text;
            a.appendChild(icon);
            a.appendChild(label);
            nav.appendChild(a);
        });
        if (!nav.children.length) { return; }
        if (place.id === "opacmainuserblock" || place.id === "opacmainblock") {
            place.insertBefore(nav, place.firstChild);
        } else {
            place.parentNode.insertBefore(nav, place);
        }
    }

    // New arrivals: 2D flat (a strip that loops for ever) or 3D coverflow
    // (the cards turn around the centre one, like a real carousel). Both
    // keep turning after a click or a swipe; only a hidden tab, keyboard
    // focus inside or "reduce motion" stop them.
    function carousel(items) {
        var K = C.carousel;
        items = items.filter(function (it) {
            return parseInt(it.biblionumber, 10) && /^https:\/\//.test(it.cover || "");
        }).slice(0, K.count);
        if (!items.length) { return; }
        var flow = K.mode === "coverflow";
        var box = document.createElement("section");
        box.id = "kei-carousel";
        box.className = flow ? "kei-mode-coverflow" : "kei-mode-flat";
        box.setAttribute("aria-label", K.title);
        box.setAttribute("aria-roledescription", "carousel");
        var h = document.createElement("h2");
        h.textContent = K.title;
        var track = document.createElement("div");
        track.className = flow ? "kei-stage" : "kei-track";
        box.appendChild(h);
        box.appendChild(track);
        var pending = items.length;
        function settled() {
            pending -= 1;
            if (pending > 0) { return; }
            if (!track.children.length) { if (box.parentNode) { box.parentNode.removeChild(box); } return; }
            (flow ? coverflow : flat)(box, track);
        }
        items.forEach(function (it) {
            var card = document.createElement("a");
            card.className = "kei-card";
            card.href = "/cgi-bin/koha/opac-detail.pl?biblionumber=" + parseInt(it.biblionumber, 10);
            var img = document.createElement("img");
            img.loading = flow ? "eager" : "lazy";
            img.alt = it.title || "";
            img.draggable = false;
            // Amazon answers a missing cover with a 1x1 image: no card then.
            img.addEventListener("load", function () {
                if (img.naturalWidth <= 1 && card.parentNode) { card.parentNode.removeChild(card); }
                settled();
            });
            img.addEventListener("error", function () { if (card.parentNode) { card.parentNode.removeChild(card); } settled(); });
            img.src = it.cover;
            card.appendChild(img);
            if (K.overlay) {
                var info = document.createElement("span");
                info.className = "kei-card-info";
                var s = document.createElement("strong");
                s.textContent = it.title || "";
                info.appendChild(s);
                [it.author, it.callnumber].forEach(function (v) {
                    if (v) { var x = document.createElement("span"); x.textContent = v; info.appendChild(x); }
                });
                var badge = document.createElement("em");
                badge.className = "kei-badge" + (it.available > 0 ? "" : " kei-out");
                badge.textContent = it.available > 0 ? C.text.available : C.text.out;
                info.appendChild(badge);
                card.appendChild(info);
            }
            if (K.hover === "tilt" && !flow) {
                card.addEventListener("mousemove", function (e) {
                    var r = card.getBoundingClientRect();
                    var x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
                    card.style.transform = "perspective(600px) rotateY(" + (x * 12) + "deg) rotateX(" + (-y * 12) + "deg)";
                });
                card.addEventListener("mouseleave", function () { card.style.transform = ""; });
            }
            track.appendChild(card);
        });
        var target = homeTarget();
        if (!target) { return; }
        var after = document.getElementById("kei-links");
        if (after && after.parentNode === target) {
            target.insertBefore(box, after.nextSibling);
        } else {
            target.parentNode.insertBefore(box, target);
        }
    }

    function navButtons(box, step) {
        [["kei-prev", "‹", -1], ["kei-next", "›", 1]].forEach(function (n) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "kei-nav " + n[0];
            btn.textContent = n[1];
            btn.setAttribute("aria-label", n[2] < 0 ? C.text.prev : C.text.next);
            btn.addEventListener("click", function () { step(n[2], true); });
            box.appendChild(btn);
        });
    }

    // autoplay(box, step): every K.speed ms, for ever (a click restarts the count).
    function autoplay(box, step) {
        var K = C.carousel;
        var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (!K.autoplay || still) { return function () {}; }
        var focused = false, timer = null;
        box.addEventListener("focusin", function () { focused = true; });
        box.addEventListener("focusout", function () { focused = false; });
        function arm() {
            if (timer) { clearInterval(timer); }
            timer = setInterval(function () { if (!focused && !document.hidden) { step(1, false); } }, K.speed);
        }
        arm();
        return arm;
    }

    function flat(box, track) {
        // The cards twice in a row: past the first set the strip jumps back
        // by its width, so it loops with no visible end.
        var originals = Array.prototype.slice.call(track.children);
        var looping = track.scrollWidth > track.clientWidth + 8;
        if (looping) {
            originals.forEach(function (c) {
                var copy = c.cloneNode(true);
                copy.setAttribute("aria-hidden", "true");
                copy.tabIndex = -1;
                track.appendChild(copy);
            });
        }
        function period() { return originals.length ? (track.scrollWidth / (looping ? 2 : 1)) : 0; }
        function width() {
            var c = track.firstElementChild;
            return c ? c.getBoundingClientRect().width + 16 : 160;
        }
        var restart = function () {};
        function step(dir, byHand) {
            if (looping) {
                if (dir < 0 && track.scrollLeft < width()) { track.scrollLeft += period(); }
                if (dir > 0 && track.scrollLeft >= period()) { track.scrollLeft -= period(); }
            } else if (dir > 0 && track.scrollLeft + track.clientWidth >= track.scrollWidth - 4) {
                track.scrollLeft = 0;
                return;
            }
            track.scrollBy({ left: dir * width(), behavior: "smooth" });
            if (byHand) { restart(); }
        }
        if (looping) {
            track.addEventListener("scroll", function () {
                if (track.scrollLeft >= period()) { track.scrollLeft -= period(); }
            });
        }
        navButtons(box, step);
        restart = autoplay(box, step);
    }

    function coverflow(box, track) {
        var cards = Array.prototype.slice.call(track.children);
        var n = cards.length, current = 0;
        function layout() {
            cards.forEach(function (card, i) {
                var d = i - current;
                if (d > n / 2) { d -= n; }
                if (d < -n / 2) { d += n; }
                var a = Math.abs(d), side = d < 0 ? -1 : 1;
                var x = d === 0 ? 0 : side * (110 + (a - 1) * 70);
                card.style.transform = "translateX(" + x + "px) translateZ(" + (-a * 140) + "px) rotateY(" +
                    (d === 0 ? 0 : -side * 48) + "deg)";
                card.style.zIndex = String(100 - a);
                card.style.opacity = a > 3 ? "0" : "1";
                card.style.pointerEvents = a > 3 ? "none" : "";
                card.style.setProperty("--kei-shade-l", d > 0 ? String(Math.min(.15 * a + .15, .6)) : "0");
                card.style.setProperty("--kei-shade-r", d < 0 ? String(Math.min(.15 * a + .15, .6)) : "0");
                card.classList.toggle("kei-center", d === 0);
                card.tabIndex = d === 0 ? 0 : -1;
                card.setAttribute("aria-hidden", d === 0 ? "false" : "true");
            });
        }
        var restart = function () {};
        function step(dir, byHand) {
            current = (current + dir + n) % n;
            layout();
            if (byHand) { restart(); }
        }
        cards.forEach(function (card, i) {
            card.addEventListener("click", function (e) {
                if (!card.classList.contains("kei-center")) {
                    e.preventDefault();
                    current = i;
                    layout();
                    restart();
                }
            });
        });
        // Swipe (touch or mouse drag).
        var x0 = null;
        track.addEventListener("pointerdown", function (e) { x0 = e.clientX; });
        track.addEventListener("pointerup", function (e) {
            if (x0 === null) { return; }
            var dx = e.clientX - x0;
            x0 = null;
            if (Math.abs(dx) > 40) { step(dx < 0 ? 1 : -1, true); }
        });
        box.addEventListener("keydown", function (e) {
            if (e.key === "ArrowRight") { step(1, true); e.preventDefault(); }
            if (e.key === "ArrowLeft") { step(-1, true); e.preventDefault(); }
        });
        layout();
        navButtons(box, step);
        restart = autoplay(box, step);
    }
})();"""

JS_TEXT = {"switch_title": "Light / dark mode", "available": "Available", "out": "On loan", "prev": "Previous",
           "next": "Next", "links": "Quick access"}


def js_config(cfg: dict, text: dict | None = None) -> dict:
    cfg = normalize(cfg)
    car = cfg["carousel"]
    return {
        "default_theme": cfg["default_theme"],
        "dark_switch": cfg["dark_switch"],
        "wallpaper": bool(cfg["background"]["url"]),
        "empty_columns": cfg["ghost"]["empty_columns"],
        "news_buttons": cfg["news_buttons"],
        "carousel": ({"feed": FEED_URL, "count": car["count"], "autoplay": car["autoplay"], "speed": car["speed"],
                      "hover": car["hover"], "overlay": car["overlay"], "title": car["title"], "mode": car["mode"]}
                     if car["enabled"] else None),
        "links": ({"style": cfg["links"]["style"], "items": cfg["links"]["items"]}
                  if cfg["links"]["enabled"] and cfg["links"]["items"] else None),
        "text": {**JS_TEXT, **(text or {})},
    }


def js_block(cfg: dict, text: dict | None = None) -> str:
    conf = json.dumps(js_config(cfg, text), ensure_ascii=True, sort_keys=True).replace("</", "<\\/")
    return "\n".join([JS_BEGIN, _JS.replace("__CONFIG__", conf), JS_END]) + "\n"


def check_block(text: str, begin: str, end: str) -> str:
    """"" when text is one well-formed block for Koha, else the reason."""
    lines = text.rstrip("\n").split("\n")
    if lines[0] != begin or lines[-1] != end:
        return "the block does not start and end with its markers"
    if any(ln in (begin, end) for ln in lines[1:-1]):
        return "a marker inside the block"
    if re.search(r"</\s*(script|style)", text, re.I):
        return "a closing script or style tag"
    return ""


# ----------------------------------------------------------------------
# Images
# ----------------------------------------------------------------------
def image_problem(path: Path) -> str:
    """"" for a picture the OPAC may serve, else why not. SVG is refused
    (it can carry scripts); the bytes must match the extension."""
    ext = path.suffix.lower()
    if ext not in IMAGE_TYPES:
        return "use a PNG, JPEG, GIF, WebP or ICO picture"
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            head = fh.read(16)
    except OSError as e:
        return str(e)
    if not size or size > MAX_IMAGE:
        return "the picture must be between 1 byte and 8 MB"
    magic = {".png": head.startswith(b"\x89PNG\r\n\x1a\n"), ".gif": head[:6] in (b"GIF87a", b"GIF89a"),
             ".jpg": head.startswith(b"\xff\xd8\xff"), ".jpeg": head.startswith(b"\xff\xd8\xff"),
             ".webp": head[:4] == b"RIFF" and head[8:12] == b"WEBP", ".ico": head[:4] == b"\x00\x00\x01\x00"}
    return "" if magic[ext] else "the file is not the picture its name says"


def local_name(role: str, path: Path) -> str:
    ext = path.suffix.lower().replace(".jpeg", ".jpg")
    return f"kei-{role}{ext}"


def local_url(role: str, path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
    return f"{CUSTOM_URL}/{local_name(role, path)}?v={digest}"


def keys_file() -> Path:
    return Path(os.environ.get("KEI_OPAC_KEYS") or CONFIG_DIR / KEYS_FILE)


def load_keys() -> dict:
    try:
        data = json.loads(keys_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_keys(keys: dict) -> None:
    path = keys_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in keys.items() if v}, fh)
    os.replace(tmp, path)


def _post(url: str, body: bytes, content_type: str, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type,
                                                          "User-Agent": "koha.nexus-panel"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 (fixed https hosts)
        return json.loads(resp.read(1_000_000).decode("utf-8", "replace"))


def upload_imgbb(path: Path, key: str, post=_post) -> str:
    """ImgBB (api.imgbb.com/1/upload): the direct https link of the picture."""
    if not key:
        raise ValueError("no ImgBB API key")
    body = urllib.parse.urlencode({"key": key, "name": path.stem,
                                   "image": base64.b64encode(path.read_bytes()).decode()}).encode()
    data = post("https://api.imgbb.com/1/upload", body, "application/x-www-form-urlencoded")
    url = ((data or {}).get("data") or {}).get("url", "")
    if not (data or {}).get("success") or not safe_url(url):
        raise ValueError(((data or {}).get("error") or {}).get("message") or "ImgBB did not return a link")
    return url


def upload_cloudinary(path: Path, cloud: str, preset: str, post=_post) -> str:
    """Cloudinary unsigned upload (an upload preset, no API secret on the
    server): the secure_url of the picture."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cloud or "") or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", preset or ""):
        raise ValueError("set the Cloudinary cloud name and unsigned upload preset first")
    boundary = "kei" + secrets.token_hex(12)
    mime = IMAGE_TYPES.get(path.suffix.lower(), "application/octet-stream")
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"upload_preset\"\r\n\r\n{preset}\r\n".encode(),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
         f"Content-Type: {mime}\r\n\r\n").encode() + path.read_bytes() + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    data = post(f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", b"".join(parts),
                f"multipart/form-data; boundary={boundary}")
    url = (data or {}).get("secure_url", "")
    if not safe_url(url):
        raise ValueError(((data or {}).get("error") or {}).get("message") or "Cloudinary did not return a link")
    return url


# ----------------------------------------------------------------------
# The folder handed to `config.sh --task opac-theme-apply DIR`
# ----------------------------------------------------------------------
def write_apply_dir(cfg: dict, files: dict[str, Path], text: dict | None = None) -> Path:
    """user.css, user.js, staff.css (when the staff interface takes the
    colours), prefs (NAME<TAB>VALUE), carousel (on N|off) and assets/ (the
    server files to publish). Private (0700)."""
    cfg = normalize(cfg)
    work = Path(tempfile.mkdtemp(prefix="kei-opac-"))
    os.chmod(work, 0o700)
    (work / "user.css").write_text(css_block(cfg), encoding="utf-8")
    (work / "user.js").write_text(js_block(cfg, text), encoding="utf-8")
    # No staff.css: the task takes the staff interface's block out again.
    if cfg["staff"]["enabled"]:
        (work / "staff.css").write_text(staff_css_block(cfg), encoding="utf-8")
    prefs = []
    car = cfg["carousel"]
    if car["enabled"]:
        prefs.append(("OPACAmazonCoverImages", "1"))
        if car["amazon_tag"]:
            prefs.append(("AmazonAssocTag", car["amazon_tag"]))
    if cfg["favicon"]["url"]:
        prefs.append(("OpacFavicon", cfg["favicon"]["url"]))
    (work / "prefs").write_text("".join(f"{k}\t{v}\n" for k, v in prefs), encoding="utf-8")
    (work / "carousel").write_text(f"on {car['count']}\n" if car["enabled"] else "off\n", encoding="utf-8")
    assets = work / "assets"
    assets.mkdir()
    for role, src in files.items():
        shutil.copyfile(src, assets / local_name(role, src))
    return work
