"""The OPAC's look: settings, the CSS and JS written into Koha, images.

The screen (views/opac.py) edits a settings dict; everything else lives
here, with no Textual:

  * settings: DEFAULTS, normalize() (every value checked and clamped: they
    end up in a public stylesheet);
  * css_block() / js_block(): the marked blocks `config.sh --task
    opac-theme-apply` puts in OpacUserCSS and OpacUserJS, the rest of both
    preferences kept as the library wrote it. The first line inside the CSS
    block is /* KEI-THEME-DATA: {...} */, the settings as JSON, read back by
    parse_theme_data() when the screen opens (state lives in Koha, so a
    second server or a restored backup shows the settings it has);
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
    "background": {"source": "none", "url": ""},
    "logo": {"source": "none", "url": ""},
    "favicon": {"source": "none", "url": ""},
    "film": 55,               # % of the legibility film over a wallpaper
    "dark_switch": True,
    "default_theme": "light",
    "carousel": {"enabled": True, "autoplay": True, "speed": 4000, "count": 12, "hover": "lift",
                 "overlay": True, "title": "New arrivals", "amazon_tag": ""},
    "ghost": {"rss": True, "cart_badge": True, "community": True, "empty_columns": True},
    "news_buttons": True,
}

RANGES = {"blur": (0, 30), "opacity": (30, 100), "radius_block": (0, 30), "radius_input": (0, 30),
          "radius_button": (0, 30), "film": (0, 90)}
CAROUSEL_RANGES = {"speed": (2000, 10000), "count": (4, 24)}


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
    g = raw.get("ghost") if isinstance(raw.get("ghost"), dict) else {}
    for key in cfg["ghost"]:
        cfg["ghost"][key] = bool(g.get(key, cfg["ghost"][key]))
    cfg["news_buttons"] = bool(raw.get("news_buttons", DEFAULTS["news_buttons"]))
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


# ----------------------------------------------------------------------
# The stylesheet
# ----------------------------------------------------------------------
_BLOCKS = "#header-region .navbar, .navbar.navbar-expand, #opac-main-search, .main"


def _texture_css(cfg: dict) -> str:
    t = cfg["texture"]
    surface = "rgba(var(--kei-surface-rgb), var(--kei-surface-a))"
    base = [f"{_BLOCKS} {{", f"    background: {surface} !important;",
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
    return "\n".join(base)


def css_body(cfg: dict) -> str:
    cfg = normalize(cfg)
    car, ghost = cfg["carousel"], cfg["ghost"]
    out = [f""":root {{
    --kei-accent: {cfg['accent']};
    --kei-accent-rgb: {_rgb(cfg['accent'])};
    --kei-accent2-rgb: {_rgb(cfg['accent2'])};
    --kei-surface-rgb: 255, 255, 255;
    --kei-surface-a: {cfg['opacity'] / 100:.2f};
    --kei-text: #1f2933;
    --kei-muted: #52606d;
    --kei-edge: rgba(15, 23, 42, .10);
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
.main {{ padding: 1.25rem; margin-top: 1rem; }}
.form-control, .form-select, input[type="text"], input[type="search"], input[type="password"], select,
textarea {{ border-radius: var(--kei-r-input) !important; }}
.btn, button.btn, input[type="submit"] {{ border-radius: var(--kei-r-btn) !important; }}
.btn-primary {{ background-color: var(--kei-accent) !important; border-color: var(--kei-accent) !important; }}
.btn-primary:hover, .btn-primary:focus {{ filter: brightness(1.08); }}
a:focus-visible, .btn:focus-visible {{ outline: 3px solid rgba(var(--kei-accent-rgb), .45); outline-offset: 2px; }}"""]
    bg = cfg["background"]["url"]
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
    return "\n".join(out) + "\n"


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
@media (prefers-reduced-motion: reduce) {{
    .kei-card, .kei-card img, .kei-card-info, .kei-track {{ transition: none; scroll-behavior: auto; }}
}}"""


def css_block(cfg: dict) -> str:
    return "\n".join([CSS_BEGIN, data_line(cfg), css_body(cfg).rstrip("\n"), CSS_END]) + "\n"


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

        // New arrivals, on the OPAC home page only.
        var home = document.getElementById("opac-main") || /opac-main\.pl$/.test(location.pathname)
            || location.pathname === "/";
        if (C.carousel && home && !document.getElementById("kei-carousel") && window.fetch) {
            fetch(C.carousel.feed, { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : { items: [] }; })
                .then(function (feed) { carousel(feed.items || []); })
                .catch(function () { /* no feed yet: no carousel */ });
        }
    });

    function carousel(items) {
        var K = C.carousel;
        items = items.slice(0, K.count);
        if (!items.length) { return; }
        var box = document.createElement("section");
        box.id = "kei-carousel";
        box.setAttribute("aria-label", K.title);
        var h = document.createElement("h2");
        h.textContent = K.title;
        var track = document.createElement("div");
        track.className = "kei-track";
        box.appendChild(h);
        box.appendChild(track);
        var pending = items.length;
        function settled() {
            pending -= 1;
            if (pending === 0 && !track.children.length && box.parentNode) { box.parentNode.removeChild(box); }
        }
        items.forEach(function (it) {
            var id = parseInt(it.biblionumber, 10);
            if (!id || !/^https:\/\//.test(it.cover || "")) { settled(); return; }
            var card = document.createElement("a");
            card.className = "kei-card";
            card.href = "/cgi-bin/koha/opac-detail.pl?biblionumber=" + id;
            var img = document.createElement("img");
            img.loading = "lazy";
            img.alt = it.title || "";
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
            if (K.hover === "tilt") {
                card.addEventListener("mousemove", function (e) {
                    var r = card.getBoundingClientRect();
                    var x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
                    card.style.transform = "perspective(600px) rotateY(" + (x * 12) + "deg) rotateX(" + (-y * 12) + "deg)";
                });
                card.addEventListener("mouseleave", function () { card.style.transform = ""; });
            }
            track.appendChild(card);
        });
        [["kei-prev", "\u2039", -1], ["kei-next", "\u203A", 1]].forEach(function (n) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "kei-nav " + n[0];
            btn.textContent = n[1];
            btn.setAttribute("aria-label", n[2] < 0 ? C.text.prev : C.text.next);
            btn.addEventListener("click", function () { step(n[2]); });
            box.appendChild(btn);
        });
        function step(dir) {
            var w = track.firstElementChild ? track.firstElementChild.getBoundingClientRect().width + 16 : 160;
            if (dir > 0 && track.scrollLeft + track.clientWidth >= track.scrollWidth - 4) { track.scrollLeft = 0; return; }
            track.scrollBy({ left: dir * w, behavior: "smooth" });
        }
        var target = document.getElementById("opacmainuserblock") || document.querySelector(".maincontent")
            || document.querySelector(".main");
        if (!target) { return; }
        target.parentNode.insertBefore(box, target);
        var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (K.autoplay && !still) {
            var paused = false;
            box.addEventListener("mouseenter", function () { paused = true; });
            box.addEventListener("mouseleave", function () { paused = false; });
            box.addEventListener("focusin", function () { paused = true; });
            box.addEventListener("focusout", function () { paused = false; });
            setInterval(function () { if (!paused && !document.hidden) { step(1); } }, K.speed);
        }
    }
})();"""

JS_TEXT = {"switch_title": "Light / dark mode", "available": "Available", "out": "On loan", "prev": "Previous",
           "next": "Next"}


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
                      "hover": car["hover"], "overlay": car["overlay"], "title": car["title"]}
                     if car["enabled"] else None),
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
    """user.css, user.js, prefs (NAME<TAB>VALUE), carousel (on N|off) and
    assets/ (the server files to publish). Private (0700)."""
    cfg = normalize(cfg)
    work = Path(tempfile.mkdtemp(prefix="kei-opac-"))
    os.chmod(work, 0o700)
    (work / "user.css").write_text(css_block(cfg), encoding="utf-8")
    (work / "user.js").write_text(js_block(cfg, text), encoding="utf-8")
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
