"""The OPAC's and the staff interface's look ("OPAC and Staff Appearance"):
settings, the CSS and JS written into Koha, images, and the login
instructions and footer credits (Koha's HTML customizations).

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
import html
import json
import os
import re
import secrets
import shutil
import tempfile
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .env import CONFIG_DIR

CSS_BEGIN = "/* koha-easy-installer opac-theme begin */"
CSS_END = "/* koha-easy-installer opac-theme end */"
JS_BEGIN = CSS_BEGIN
JS_END = CSS_END
DATA_TAG = "KEI-THEME-DATA:"
CUSTOM_URL = "/images/custom"                       # /usr/share/koha/opac/htdocs/images/custom
STAFF_CUSTOM_URL = "/intranet-tmpl/kei-custom"      # /usr/share/koha/intranet/htdocs/intranet-tmpl/kei-custom
FEED_URL = CUSTOM_URL + "/kei-new-arrivals.json"    # written by the nightly job
LIST_FEED = CUSTOM_URL + "/kei-list-"               # + <list number>.json: each public Koha list, same job
KEYS_FILE = "opac-theme.conf"                       # image host keys (0600)

TEXTURES = {
    "frosted": "Frosted glass",
    "smooth": "Smooth glass",
    "metal": "Brushed metal",
    "anodized": "Anodised aluminium",
    "wood": "Wood grain",
    "paper": "Matte paper",
    "flat": "Flat solid colour",
    "gradient": "Soft diagonal gradient",
}
# The textures drawn as a material (_material): a solid look of their own
# over the card, and the brushed buttons for the two metals.
MATERIALS = ("metal", "anodized", "wood", "paper")
METALS = ("metal", "anodized")
# Each colour of the palette with a texture and an opacity of its own
# (cfg["paint"][colour]): the accent paints the main buttons, the second
# colour the secondary buttons, the page colour the page under the blocks.
# The block background is the Material itself (its texture and opacity).
# "auto": the look before these options existed (the accent follows the
# Material, the second colour only tints the page's glows, the page is a
# plain colour).
PAINTED = ("accent", "accent2", "page")
PAINTS = {"auto": "As the Material (default)", **TEXTURES}
# Style details, the same choices for the OPAC (cfg) and the staff
# interface (cfg["staff"]): key -> (label, {value: name}). The first value
# is the default, the look the panel had before these options existed.
STYLE = {
    "shadow": ("Card shadow", {"texture": "As the texture draws it", "none": "None", "soft": "Soft",
                               "medium": "Medium", "strong": "Strong"}),
    "spacing": ("Spacing", {"normal": "Normal", "compact": "Compact", "airy": "Airy"}),
    "icons": ("Icons", {"filled": "Filled", "outline": "Outline"}),
    "pattern": ("Background pattern", {"none": "None", "dots": "Dots", "grid": "Grid",
                                       "lines": "Diagonal lines", "grain": "Grain"}),
    "chrome": ("Tables and menus", {"plain": "As Koha draws them", "texture": "In the chosen texture"}),
    "login_style": ("Login page", {"koha": "Koha's own", "card": "Highlighted card",
                                   "accent": "Card on the accent colours"}),
    "motion": ("Hover animations", {"subtle": "Subtle", "lively": "Lively", "off": "Off"}),
}
STYLE_DEFAULTS = {key: next(iter(choices)) for key, (_label, choices) in STYLE.items()}
HOVERS = {"zoom": "Smooth zoom", "lift": "Elevation shadow", "tilt": "Tilt", "none": "None"}
# The carousel's styles. flat and coverflow first (1.5.63); the others from
# Paulo's 2026-10-31 references (a cover ring with reflections, a curved
# wall of covers with their titles) and a few of our own.
CAROUSEL_MODES = {"flat": "2D flat", "coverflow": "3D coverflow", "ring": "3D ring (turns around)",
                  "wall": "Curved wall with titles", "shelf": "Bookshelf", "fan": "Fan of cards",
                  "spotlight": "Spotlight (one title at a time)", "ribbon": "Endless ribbon"}
# A title whose cover is missing (none found by the nightly job, or the
# picture does not load in the reader's browser): left out, or a cover
# drawn in the accent colours with its title and author.
CAROUSEL_MISSING = {"hide": "Leave the title out", "drawn": "Draw a cover with the title"}
CAROUSEL_SOURCES = {"new": "New arrivals", "list": "A public Koha list"}
MAX_SHELF = 999_999_999
LINK_STYLES = {"solid": "Solid colour", "gradient": "Gradient", "glass": "Glass (blur)", "metal": "Brushed metal"}
LINK_LAYOUTS = {"list": "One per line", "grid2": "Two columns"}
LINK_TARGETS = {"_self": "Same tab", "_blank": "New tab"}
STAFF_DENSITY = {"comfortable": "Comfortable", "normal": "Normal", "compact": "Compact"}
STAFF_CONTRAST = {"normal": "Normal", "high": "High"}
MAX_LINKS = 12
MAX_ORDER = 999
THEMES = {"light": "Light", "dark": "Dark", "auto": "Follow the device"}
SOURCES = {"none": "None", "local": "File on this server", "url": "Direct URL", "imgbb": "Upload to ImgBB",
           "cloudinary": "Upload to Cloudinary"}
# header: the picture of the large header (it covers the whole header).
ASSETS = ("background", "logo", "favicon", "header")
# The staff interface's own pictures, in cfg["staff"]; their files are
# kei-staff-<name>.* on the staff side (STAFF_CUSTOM_URL).
STAFF_ASSETS = ("background", "logo", "favicon")
# The OPAC header (#header-region: the top bar with the logo, cart and login,
# then the search bar): Koha's own, or a large one under a picture.
HEADER_STYLES = {"normal": "Normal", "large": "Large, with a picture"}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".ico": "image/x-icon"}
MAX_IMAGE = 8_000_000

DEFAULTS: dict = {
    "version": 1,
    "texture": "frosted",
    **STYLE_DEFAULTS,         # card shadow, spacing, icons, pattern, tables and menus, login page, animations
    "blur": 12,               # px, frosted glass
    "opacity": 78,            # % of every glass card (header, search, content, sidebars): 0 clear, 100 solid
    "radius_block": 14,       # px, 0-30
    "radius_input": 10,
    "radius_button": 10,
    "accent": "#2563eb",
    "accent2": "#7c3aed",     # second colour of the gradient
    "surface": "#ffffff",     # background of the blocks (header, search, content, news)
    "page": "",               # background of the page ("" = Koha's own)
    # The texture and opacity (0 clear, 100 solid) of each colour (PAINTED).
    "paint": {key: {"texture": "auto", "opacity": 100} for key in PAINTED},
    "background": {"source": "none", "url": ""},
    "logo": {"source": "none", "url": ""},
    "favicon": {"source": "none", "url": ""},
    "header": {"source": "none", "url": ""},
    "header_bar": True,       # the top bar of the header (logo, cart, lists, login)
    "header_style": "normal",
    "header_height": 280,     # px of the large header
    "film": 55,               # % of the legibility film over a wallpaper
    "dark_switch": True,
    "default_theme": "light",
    "carousel": {"enabled": True, "autoplay": True, "speed": 3500, "count": 12, "hover": "lift",
                 "overlay": True, "title": "New arrivals", "amazon_tag": "", "mode": "flat",
                 # reflect: a mirror image of each cover under it (every
                 # style but the bookshelf, the fan and the spotlight).
                 "reflect": False, "missing": "hide",
                 # source "list": the public Koha list number shelf (Lists,
                 # opac-shelves.pl?op=view&shelfnumber=N) instead of the
                 # newest titles. lists: keep the nightly job (and so the
                 # feeds of KEI.listCarousel and data-kei-list) with the home
                 # page carousel off.
                 "source": "new", "shelf": 0, "lists": False},
    # cart: the whole cart (menu, its message and the "Add to cart" links).
    "ghost": {"rss": True, "cart_badge": True, "cart": False, "community": True, "empty_columns": True},
    "news_buttons": True,
    # Quick access buttons at the top of the home page (link-tree style):
    # [{"icon": "📖", "text": "...", "url": "https://...", "target": "_blank", "sort_order": 1}],
    # shown by sort_order (settings saved before it had one: 1..n, as listed).
    "links": {"enabled": False, "style": "glass", "layout": "list", "items": []},
    # The same buttons on the staff interface's home page (IntranetUserJS),
    # above the module tiles: shortcuts to the library's internal workflows.
    "staff_links": {"enabled": False, "style": "glass", "layout": "list", "items": []},
    # The staff interface (IntranetUserCSS): its own palette, material
    # (the OPAC's textures, blur, opacity and corners), type, contrast and
    # table density, nothing shared with the OPAC unless "Copy OPAC preset"
    # copies it (copy_opac_to_staff()). Settings saved before it had colours
    # start from the OPAC's (normalize()); before it had a material, "flat"
    # with the corners it had, so their look does not change.
    "staff": {"enabled": False, "accent": "#2563eb", "accent2": "#7c3aed", "surface": "#ffffff",
              "page": "", "bar": "", "texture": "flat", "blur": 12, "opacity": 100,
              "radius_block": 12, "radius_input": 10, "radius_button": 8,
              "density": "normal", "contrast": "normal", "font": 100,
              "background": {"source": "none", "url": ""}, "logo": {"source": "none", "url": ""},
              "favicon": {"source": "none", "url": ""}, "film": 55,
              "card": "sections", "card_padding": 16,
              # The top bar and the quick search bar under it in translucent
              # glass (_staff_header_css): off keeps them solid.
              "header_glass": False, "header_opacity": 85, "header_blur": 8,
              # Each staff colour's own texture and opacity, as the OPAC's.
              "paint": {key: {"texture": "auto", "opacity": 100} for key in PAINTED}, **STYLE_DEFAULTS},
    # Koha's HTML customizations (Tools > HTML customizations) the panel
    # writes: the login instructions of the OPAC and of the staff interface
    # (allow-listed HTML, a banner picture above it) and the OPAC footer
    # credits, built from a form. Not in the public stylesheet's settings
    # line (data_line): they travel in theme-settings.json.
    "login": {"opac": {"enabled": False, "html": "", "image": {"source": "none", "url": ""}, "alt": ""},
              "staff": {"enabled": False, "html": "", "image": {"source": "none", "url": ""}, "alt": ""}},
    "credits": {"enabled": False, "name": "", "address": "", "phone": "", "whatsapp": "", "email": "",
                "website": "", "hours": "", "instagram": "", "facebook": "", "youtube": "", "cnpj": "",
                "note": "", "links": [], "order": []},
    # One news item of the panel's own on each side (Koha's News, category
    # "news"): a title, allow-listed HTML and call-to-action buttons.
    "news": {"opac": {"enabled": False, "title": "", "html": "", "buttons": []},
             "staff": {"enabled": False, "title": "", "html": "", "buttons": []}},
}

RANGES = {"blur": (0, 30), "opacity": (0, 100), "radius_block": (0, 30), "radius_input": (0, 30),
          "radius_button": (0, 30), "film": (0, 90), "header_height": (160, 520)}
CAROUSEL_RANGES = {"speed": (2000, 10000), "count": (4, 24)}
STAFF_FONT = (90, 120)
STAFF_FILM = (0, 90)        # % of the film over the staff wallpaper, the OPAC's range: the cards keep the text readable
# The content card: one per section (Koha's .page-section, forms, tables) or
# one for the whole page (.main, the content and its sidebar), with the
# sections inside it clear: never a card inside a card.
STAFF_CARD = {"sections": "One card per section", "page": "One card for the whole page"}
STAFF_CARD_PADDING = (0, 40)  # px inside the card
# The staff material: the OPAC's sliders, same ranges.
STAFF_MATERIAL = ("blur", "opacity", "radius_block", "radius_input", "radius_button")
# The glass top bar: % of the bar's colour left (0 clear, 100 solid) and px of blur behind it.
STAFF_HEADER = {"header_opacity": (0, 100), "header_blur": (0, 30)}


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


def _link(raw, position: int = 1) -> dict | None:
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
    order = _clamp(raw.get("sort_order", position), 1, MAX_ORDER, min(position, MAX_ORDER))
    return {"icon": icon, "text": text, "url": url, "target": target, "sort_order": order}


def _links(raw) -> dict:
    """A set of quick access buttons: the valid ones, by sort_order (a tie
    keeps the order they were listed in), at most MAX_LINKS."""
    lk = raw if isinstance(raw, dict) else {}
    items = lk.get("items") if isinstance(lk.get("items"), list) else []
    kept = [x for x in (_link(i, n) for n, i in enumerate(items, 1)) if x]
    kept.sort(key=lambda x: x["sort_order"])
    return {"enabled": bool(lk.get("enabled", False)),
            "style": lk.get("style") if lk.get("style") in LINK_STYLES else DEFAULTS["links"]["style"],
            "layout": lk.get("layout") if lk.get("layout") in LINK_LAYOUTS else "list",
            "items": kept[:MAX_LINKS]}


def links_on(lk: dict) -> bool:
    return bool(lk["enabled"] and lk["items"])


def _asset(raw) -> dict:
    a = raw if isinstance(raw, dict) else {}
    source = a.get("source") if a.get("source") in SOURCES else "none"
    url = safe_url(a.get("url", ""))
    return {"source": source, "url": url if source != "none" else ""}


# ----------------------------------------------------------------------
# HTML customizations: login instructions and footer credits
# ----------------------------------------------------------------------
# Koha's places for them (additional_contents.location, Koha 23.11 and later):
# the OPAC login page, the staff login page and the OPAC footer.
CONTENT_LOCATIONS = ("OpacLoginInstructions", "StaffLoginInstructions", "opaccredits", "news-opac", "news-staff")
LOGIN_SIDES = {"opac": "OpacLoginInstructions", "staff": "StaffLoginInstructions"}
# The login banners: kei-login.* in the OPAC's folder, kei-staff-login.* in the staff one.
LOGIN_ASSETS = {"opac": "login", "staff": "staff-login"}
# The panel's news items: contents.list place -> Koha's News location. Their
# code is kei-<place>; the title rides on the first line of the HTML file.
NEWS_SIDES = {"opac": "news-opac", "staff": "news-staff"}
NEWS_LOCATIONS = {"news-opac": "opac_only", "news-staff": "staff_only"}
NEWS_TITLE = "<!-- kei-news-title: {} -->"
# The library's own news item the box updates in place (second line).
NEWS_ID = "<!-- kei-news-id: {} -->"
MAX_HTML = 20_000
MAX_CREDIT_LINKS = 6
# What the login instructions keep of the HTML typed or pasted in the panel:
# these tags, and per tag only the attributes below (links and pictures
# through safe_link / safe_url). Script, style, iframes, forms, event
# handlers (onclick=...), style="" and javascript: addresses never reach Koha.
_ALLOWED_TAGS = {"p", "br", "hr", "strong", "b", "em", "i", "u", "small", "span", "div", "a", "img", "ul", "ol",
                 "li", "h2", "h3", "h4", "h5", "blockquote"}
_VOID_TAGS = {"br", "hr", "img"}
_BLOCK_TAGS = {"p", "div", "ul", "ol", "h2", "h3", "h4", "h5", "blockquote", "hr"}
# Dropped with everything inside them.
_DROP_WITH_TEXT = {"script", "style", "iframe", "object", "embed", "template", "noscript", "svg", "math",
                   "textarea", "select", "title", "head", "frameset", "frame", "applet"}
_CLASS = re.compile(r"[A-Za-z0-9_ -]{1,80}")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip: list[str] = []

    def _attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str | None:
        kept: list[tuple[str, str]] = []
        for name, value in attrs:
            value = (value or "").strip()
            if name == "class" and _CLASS.fullmatch(value):
                kept.append((name, value))
            elif tag == "a" and name == "href" and safe_link(value):
                kept.append((name, value))
            elif tag == "a" and name == "target" and value == "_blank":
                kept += [(name, value), ("rel", "noopener noreferrer")]
            elif tag in ("a", "img") and name in ("title", "alt"):
                kept.append((name, value[:200]))
            elif tag == "img" and name == "src" and safe_url(value):
                kept.append((name, value))
            elif tag == "img" and name in ("width", "height") and re.fullmatch(r"\d{1,4}", value):
                kept.append((name, value))
        if tag == "img" and not any(n == "src" for n, _ in kept):
            return None
        if tag == "img":
            kept += [("loading", "lazy"), ("style", "max-width:100%;height:auto")]
        return "".join(f' {n}="{html.escape(v, quote=True)}"' for n, v in kept)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DROP_WITH_TEXT:
            self.skip.append(tag)
            return
        if self.skip or tag not in _ALLOWED_TAGS:
            return
        attr = self._attrs(tag, attrs)
        if attr is None:
            return
        # What the browser would close by itself: a list item before the
        # next one, a paragraph before a block.
        if tag == "li" and self.stack and self.stack[-1] == "li":
            self.handle_endtag("li")
        if tag in _BLOCK_TAGS and "p" in self.stack:
            self.handle_endtag("p")
        self.out.append(f"<{tag}{attr}>")
        if tag not in _VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DROP_WITH_TEXT:
            return
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS and self.stack and self.stack[-1] == tag and not self.skip:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_WITH_TEXT:
            if tag in self.skip:
                while self.skip and self.skip.pop() != tag:
                    pass
            return
        if self.skip or tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        self.close()
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out).strip()


def sanitize_html(value) -> str:
    """The HTML of a login instruction, kept to an allow-list (see
    _ALLOWED_TAGS): what is left is safe to print raw in Koha's page."""
    text = str(value or "")[:MAX_HTML]
    if not text.strip():
        return ""
    parser = _Sanitizer()
    parser.feed(text)
    return parser.result()


def _login(raw) -> dict:
    r = raw if isinstance(raw, dict) else {}
    return {"enabled": bool(r.get("enabled", False)), "html": sanitize_html(r.get("html", "")),
            "image": _asset(r.get("image")), "alt": _text(r.get("alt"), "", 120)}


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


# The free text of the footer credits (name, address, hours, note): no
# limit a librarian would meet (Paulo, 2026-10-31: the 300 characters of
# the note were too few); only a guard against a runaway paste.
CREDITS_TEXT_MAX = 100_000


def _credits(raw) -> dict:
    """The footer credits form: each field checked (links through safe_link,
    e-mail and WhatsApp by their shape); a field that fails is left empty."""
    r = raw if isinstance(raw, dict) else {}
    out = {"enabled": bool(r.get("enabled", False))}
    for key, limit in (("name", CREDITS_TEXT_MAX), ("address", CREDITS_TEXT_MAX), ("phone", 40),
                       ("hours", CREDITS_TEXT_MAX), ("note", CREDITS_TEXT_MAX)):
        out[key] = _text(r.get(key), "", limit)
    wa = _digits(r.get("whatsapp"))
    out["whatsapp"] = wa if 8 <= len(wa) <= 15 else ""
    email = _text(r.get("email"), "", 120)
    out["email"] = email if re.fullmatch(r"[^@\s\"'<>]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email) else ""
    for key in ("website", "facebook", "youtube"):
        url = safe_link(r.get(key, ""))
        out[key] = url if url.startswith(("https://", "http://")) else ""
    ig = str(r.get("instagram") or "").strip()
    if ig.startswith(("https://", "http://")):
        out["instagram"] = safe_link(ig)
    else:
        handle = ig.lstrip("@")
        out["instagram"] = "@" + handle if re.fullmatch(r"[A-Za-z0-9._]{1,30}", handle) else ""
    cnpj = _text(r.get("cnpj"), "", 30)
    d = _digits(cnpj)
    out["cnpj"] = f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else cnpj
    links = []
    for item in r.get("links") if isinstance(r.get("links"), list) else []:
        item = item if isinstance(item, dict) else {}
        text, url = _text(item.get("text"), "", 60), safe_link(item.get("url", ""))
        if text and url:
            links.append({"text": text, "url": url})
    out["links"] = links[:MAX_CREDIT_LINKS]
    out["order"] = _credits_order(r.get("order"), out)
    return out


# The lines of the footer credits in the order the librarian wrote them
# (Paulo, 2026-10-31: the fixed order of the form moved his lines around and
# joined his own lines into one): a field's key, "links" for the other
# links, or "text:" and a line of plain text shown as it is.
CREDITS_ORDER_KEYS = ("name", "address", "phone", "whatsapp", "email", "website", "hours", "instagram",
                      "facebook", "youtube", "links", "note", "cnpj")
MAX_CREDIT_LINES = 60


def _credits_order(raw, fields: dict) -> list[str]:
    out: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str):
            continue
        if item.startswith("text:"):
            line = re.sub(r"\s+", " ", item[5:]).strip()[:CREDITS_TEXT_MAX]
            if line:
                out.append("text:" + line)
        elif item in CREDITS_ORDER_KEYS and item not in out and fields.get(item):
            out.append(item)
        if len(out) >= MAX_CREDIT_LINES:
            break
    return out


def _news(raw) -> dict:
    r = raw if isinstance(raw, dict) else {}
    # The title goes into an HTML comment and Koha's own title field.
    title = re.sub(r"-{2,}", "-", re.sub(r"[<>\r\n]", "", _text(r.get("title"), "", 120)))
    raw_buttons = r.get("buttons") if isinstance(r.get("buttons"), list) else []
    if not raw_buttons and r.get("button_text"):     # 1.5.53 kept a single button
        raw_buttons = [{"text": r.get("button_text"), "url": r.get("button_url", "")}]
    buttons = []
    for item in raw_buttons:
        if not isinstance(item, dict):
            continue
        text, url = _text(item.get("text"), "", 120), safe_link(item.get("url", ""))
        if text and url:
            buttons.append({"text": text, "url": url})
    # koha_id: the library's own news item (additional_contents.id) the box
    # shows and Apply updates in place; 0: the panel's own (code kei-news-*).
    koha_id = r.get("koha_id")
    koha_id = koha_id if isinstance(koha_id, int) and not isinstance(koha_id, bool) and 0 < koha_id < 10**9 else 0
    return {"enabled": bool(r.get("enabled", False)), "title": title.strip(),
            "html": sanitize_html(r.get("html", "")), "buttons": buttons, "koha_id": koha_id}


def news_on(n: dict) -> bool:
    return bool(n["enabled"] and n["title"] and (n["html"] or n["buttons"]))


def news_html(n: dict) -> str:
    """A news item as Koha prints it: the text, then its buttons in one row
    (plain links styled as Koha's primary button on both sides, no script)."""
    parts = [NEWS_TITLE.format(n["title"]), '<div class="kei-news">']
    if n["html"]:
        parts.append(n["html"])
    links = []
    for b in n["buttons"]:
        extra = ' target="_blank" rel="noopener noreferrer"' if b["url"].startswith("http") else ""
        links.append(f'<a class="btn btn-primary kei-news-button" style="margin:0 .4em .4em 0" '
                     f'href="{html.escape(b["url"], quote=True)}"{extra}>{html.escape(b["text"])}</a>')
    if links:
        parts.append('<p class="kei-news-cta">' + "\n".join(links) + "</p>")
    return "\n".join(parts + ["</div>"])


def credits_on(cr: dict) -> bool:
    return bool(cr["enabled"] and any(v for k, v in cr.items() if k != "enabled"))


def login_on(lg: dict) -> bool:
    return bool(lg["enabled"] and (lg["html"] or lg["image"]["url"]))


def login_html(lg: dict) -> str:
    """The login instructions as Koha prints them: the banner (responsive:
    never wider than the box, height kept in proportion) and the HTML."""
    parts = []
    if lg["image"]["url"]:
        parts.append(f'<p class="kei-login-banner-wrap"><img class="kei-login-banner img-fluid" '
                     f'src="{html.escape(lg["image"]["url"], quote=True)}" alt="{html.escape(lg["alt"], quote=True)}" '
                     'style="display:block;max-width:100%;height:auto;margin:0 auto;border-radius:8px"></p>')
    if lg["html"]:
        parts.append(lg["html"])
    return '<div class="kei-login">\n' + "\n".join(parts) + "\n</div>" if parts else ""


CREDITS_TEXT = {"phone": "Phone", "whatsapp": "WhatsApp", "email": "E-mail", "website": "Website",
                "hours": "Opening hours", "cnpj": "CNPJ", "social": "Follow us"}


def credits_html(cr: dict, text: dict | None = None) -> str:
    """The footer credits: one fixed block of markup from the form's
    fields (every value escaped), for Koha's opaccredits."""
    lab = {**CREDITS_TEXT, **(text or {})}
    e = html.escape

    def link(url: str, label: str, new_tab: bool = True) -> str:
        extra = ' target="_blank" rel="noopener noreferrer"' if new_tab else ""
        return f'<a href="{e(url, quote=True)}"{extra}>{e(label)}</a>'

    if cr.get("order"):
        return _credits_ordered_html(cr, lab)
    lines = []
    if cr["name"]:
        lines.append(f'<p class="kei-credits-name"><strong>{e(cr["name"])}</strong></p>')
    if cr["address"]:
        lines.append(f'<p class="kei-credits-address">{e(cr["address"])}</p>')
    contact = []
    if cr["phone"]:
        contact.append(f'{e(lab["phone"])}: {link("tel:" + _digits(cr["phone"]), cr["phone"], False)}'
                       if len(_digits(cr["phone"])) >= 3 else f'{e(lab["phone"])}: {e(cr["phone"])}')
    if cr["whatsapp"]:
        contact.append(f'{e(lab["whatsapp"])}: {link("https://wa.me/" + cr["whatsapp"], "+" + cr["whatsapp"])}')
    if cr["email"]:
        contact.append(f'{e(lab["email"])}: {link("mailto:" + cr["email"], cr["email"], False)}')
    if cr["website"]:
        shown = re.sub(r"^https?://", "", cr["website"]).rstrip("/")
        contact.append(f'{e(lab["website"])}: {link(cr["website"], shown)}')
    if contact:
        lines.append('<p class="kei-credits-contact">' + " · ".join(contact) + "</p>")
    if cr["hours"]:
        lines.append(f'<p class="kei-credits-hours">{e(lab["hours"])}: {e(cr["hours"])}</p>')
    social = []
    if cr["instagram"]:
        url = (cr["instagram"] if cr["instagram"].startswith("http")
               else f"https://www.instagram.com/{cr['instagram'][1:]}/")
        social.append(link(url, "Instagram" + (f" {cr['instagram']}" if cr["instagram"].startswith("@") else "")))
    if cr["facebook"]:
        social.append(link(cr["facebook"], "Facebook"))
    if cr["youtube"]:
        social.append(link(cr["youtube"], "YouTube"))
    if social:
        lines.append(f'<p class="kei-credits-social">{e(lab["social"])}: ' + " · ".join(social) + "</p>")
    if cr["links"]:
        lines.append('<p class="kei-credits-links">'
                     + " · ".join(link(x["url"], x["text"], x["url"].startswith("http")) for x in cr["links"]) + "</p>")
    if cr["note"]:
        lines.append(f'<p class="kei-credits-note">{e(cr["note"])}</p>')
    if cr["cnpj"]:
        lines.append(f'<p class="kei-credits-cnpj">{e(lab["cnpj"])}: {e(cr["cnpj"])}</p>')
    return '<div class="kei-credits">\n' + "\n".join(lines) + "\n</div>" if lines else ""


def _credit_link(url: str, label: str, new_tab: bool = True) -> str:
    extra = ' target="_blank" rel="noopener noreferrer"' if new_tab else ""
    return f'<a href="{html.escape(url, quote=True)}"{extra}>{html.escape(label)}</a>'


_AUTOLINK = re.compile(r"(https?://[^\s<>\"']+[^\s<>\"'.,;:!?)])|([^\s@<>\"'():,;]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _autolink(text: str) -> str:
    """A plain line, escaped, its web and e-mail addresses made links."""
    out, at = [], 0
    for m in _AUTOLINK.finditer(text):
        out.append(html.escape(text[at:m.start()]))
        url = m.group(1)
        out.append(_credit_link(url, url) if url else _credit_link("mailto:" + m.group(2), m.group(2), False))
        at = m.end()
    out.append(html.escape(text[at:]))
    return "".join(out)


def _credits_ordered_html(cr: dict, lab: dict) -> str:
    """The credits one line each, in the order of cr["order"] (fields the
    order leaves out follow at the end)."""
    e, link = html.escape, _credit_link
    order = list(cr["order"]) + [k for k in CREDITS_ORDER_KEYS if cr.get(k) and k not in cr["order"]]
    lines = []
    for key in order:
        if key.startswith("text:"):
            lines.append(f'<p class="kei-credits-line">{_autolink(key[5:])}</p>')
            continue
        value = cr.get(key)
        if not value:
            continue
        if key == "name":
            body = f"<strong>{e(value)}</strong>"
        elif key in ("address", "note"):
            body = e(value)
        elif key == "phone":
            body = (f'{e(lab["phone"])}: {link("tel:" + _digits(value), value, False)}'
                    if len(_digits(value)) >= 3 else f'{e(lab["phone"])}: {e(value)}')
        elif key == "whatsapp":
            body = f'{e(lab["whatsapp"])}: {link("https://wa.me/" + value, "+" + value)}'
        elif key == "email":
            body = f'{e(lab["email"])}: {link("mailto:" + value, value, False)}'
        elif key == "website":
            body = f'{e(lab["website"])}: {link(value, re.sub(r"^https?://", "", value).rstrip("/"))}'
        elif key in ("hours", "cnpj"):
            body = f"{e(lab[key])}: {e(value)}"
        elif key == "instagram":
            url = value if value.startswith("http") else f"https://www.instagram.com/{value[1:]}/"
            body = link(url, "Instagram" + (f" {value}" if value.startswith("@") else ""))
        elif key in ("facebook", "youtube"):
            body = link(value, "Facebook" if key == "facebook" else "YouTube")
        else:   # links
            body = " · ".join(link(x["url"], x["text"], x["url"].startswith("http")) for x in value)
        lines.append(f'<p class="kei-credits-{key}">{body}</p>')
    return '<div class="kei-credits kei-credits-ordered">\n' + "\n".join(lines) + "\n</div>" if lines else ""


def contents(cfg: dict, text: dict | None = None) -> dict[str, str]:
    """{location: HTML} of the three places the panel manages; "" turns the
    panel's entry there off (the library's own entries come back)."""
    cfg = normalize(cfg)
    out = {loc: (login_html(cfg["login"][side]) if login_on(cfg["login"][side]) else "")
           for side, loc in LOGIN_SIDES.items()}
    out["opaccredits"] = credits_html(cfg["credits"], text) if credits_on(cfg["credits"]) else ""
    for side, place in NEWS_SIDES.items():
        nw = cfg["news"][side]
        markup = news_html(nw) if news_on(nw) else ""
        if markup and nw["koha_id"]:
            first, rest = markup.split("\n", 1)
            markup = f"{first}\n{NEWS_ID.format(nw['koha_id'])}\n{rest}"
        out[place] = markup
    return out


def parse_contents(text: str) -> dict:
    """The login and credits settings that opac-theme-get read from
    theme-settings.json ({} when there are none)."""
    try:
        data = json.loads(text or "{}", strict=False)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    cfg = normalize({k: data.get(k) for k in ("login", "credits", "news")})
    return {k: cfg[k] for k in ("login", "credits", "news") if k in data}


def contents_settings(cfg: dict) -> dict:
    """The settings of the HTML customizations, kept out of the public
    stylesheet (theme-settings.json holds them)."""
    cfg = normalize(cfg)
    return {"login": cfg["login"], "credits": cfg["credits"], "news": cfg["news"]}


def _style(raw: dict) -> dict:
    """The style details of one side: a known choice, else the default."""
    return {key: raw[key] if isinstance(raw.get(key), str) and raw[key] in choices else STYLE_DEFAULTS[key]
            for key, (_label, choices) in STYLE.items()}


def _paints(raw) -> dict:
    """The texture and opacity of each colour (PAINTED), checked."""
    pt = raw if isinstance(raw, dict) else {}
    out = {}
    for key in PAINTED:
        one = pt.get(key) if isinstance(pt.get(key), dict) else {}
        out[key] = {"texture": one.get("texture") if one.get("texture") in PAINTS else "auto",
                    "opacity": _clamp(one.get("opacity", 100), 0, 100, 100)}
    return out


def normalize(raw: dict | None) -> dict:
    """Every setting checked: unknown keys dropped, numbers clamped, colours
    and URLs validated, defaults where missing."""
    raw = raw if isinstance(raw, dict) else {}
    cfg = copy.deepcopy(DEFAULTS)
    cfg["texture"] = raw.get("texture") if raw.get("texture") in TEXTURES else DEFAULTS["texture"]
    cfg.update(_style(raw))
    for key, (lo, hi) in RANGES.items():
        cfg[key] = _clamp(raw.get(key, DEFAULTS[key]), lo, hi, DEFAULTS[key])
    cfg["accent"] = _hex(raw.get("accent"), DEFAULTS["accent"])
    cfg["accent2"] = _hex(raw.get("accent2"), DEFAULTS["accent2"])
    cfg["surface"] = _hex(raw.get("surface"), DEFAULTS["surface"])
    cfg["page"] = _hex(raw.get("page"), "") if raw.get("page") else ""
    cfg["paint"] = _paints(raw.get("paint"))
    for name in ASSETS:
        cfg[name] = _asset(raw.get(name))
    cfg["dark_switch"] = bool(raw.get("dark_switch", DEFAULTS["dark_switch"]))
    cfg["header_bar"] = bool(raw.get("header_bar", True))
    cfg["header_style"] = raw.get("header_style") if raw.get("header_style") in HEADER_STYLES else "normal"
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
    car["reflect"] = bool(c.get("reflect", car["reflect"]))
    car["missing"] = c.get("missing") if c.get("missing") in CAROUSEL_MISSING else car["missing"]
    car["shelf"] = _clamp(c.get("shelf", 0), 0, MAX_SHELF, 0)
    car["source"] = "list" if c.get("source") == "list" and car["shelf"] else "new"
    car["lists"] = bool(c.get("lists", car["lists"]))
    g = raw.get("ghost") if isinstance(raw.get("ghost"), dict) else {}
    for key in cfg["ghost"]:
        cfg["ghost"][key] = bool(g.get(key, cfg["ghost"][key]))
    cfg["news_buttons"] = bool(raw.get("news_buttons", DEFAULTS["news_buttons"]))
    cfg["links"] = _links(raw.get("links"))
    cfg["staff_links"] = _links(raw.get("staff_links"))
    st = raw.get("staff") if isinstance(raw.get("staff"), dict) else {}
    cfg["staff"] = {"enabled": bool(st.get("enabled", False)),
                    "accent": _hex(st.get("accent"), cfg["accent"]),
                    "accent2": _hex(st.get("accent2"), cfg["accent2"]),
                    "surface": _hex(st.get("surface"), DEFAULTS["staff"]["surface"]),
                    "density": st.get("density") if st.get("density") in STAFF_DENSITY else "normal",
                    "contrast": st.get("contrast") if st.get("contrast") in STAFF_CONTRAST else "normal",
                    "font": _clamp(st.get("font", 100), *STAFF_FONT, 100),
                    "film": _clamp(st.get("film", DEFAULTS["staff"]["film"]), *STAFF_FILM, DEFAULTS["staff"]["film"]),
                    "card": st.get("card") if st.get("card") in STAFF_CARD else DEFAULTS["staff"]["card"],
                    "card_padding": _clamp(st.get("card_padding", DEFAULTS["staff"]["card_padding"]),
                                           *STAFF_CARD_PADDING, DEFAULTS["staff"]["card_padding"]),
                    "texture": st.get("texture") if st.get("texture") in TEXTURES else DEFAULTS["staff"]["texture"],
                    "page": _hex(st.get("page"), "") if st.get("page") else "",
                    # The top bar's own colour ("" = automatic, staff_bar()).
                    "bar": _hex(st.get("bar"), "") if st.get("bar") else ""}
    for key in STAFF_MATERIAL:
        default = DEFAULTS["staff"][key]
        cfg["staff"][key] = _clamp(st.get(key, default), *RANGES[key], default)
    cfg["staff"].update(_style(st))
    cfg["staff"]["header_glass"] = bool(st.get("header_glass", False))
    cfg["staff"]["dark_switch"] = bool(st.get("dark_switch", False))
    cfg["staff"]["paint"] = _paints(st.get("paint"))
    for key, (lo, hi) in STAFF_HEADER.items():
        default = DEFAULTS["staff"][key]
        cfg["staff"][key] = _clamp(st.get(key, default), lo, hi, default)
    for name in STAFF_ASSETS:
        cfg["staff"][name] = _asset(st.get(name))
    lg = raw.get("login") if isinstance(raw.get("login"), dict) else {}
    cfg["login"] = {side: _login(lg.get(side)) for side in LOGIN_SIDES}
    cfg["credits"] = _credits(raw.get("credits"))
    nw = raw.get("news") if isinstance(raw.get("news"), dict) else {}
    cfg["news"] = {side: _news(nw.get(side)) for side in NEWS_SIDES}
    return cfg


# Ready-made looks (Paulo, 2026-10-31: "uns 5 presets ... bonitos e bem
# equilibrados"). Each sets the palette, the material, the opacity, the
# blur and the corners of the OPAC and of the staff interface together;
# pictures, texts, news, links and the carousel are left as they are, and
# nothing reaches Koha until Apply. Checked by hand: text 7:1 and links
# 4.5:1 on the cards, the accent at 3:1 or more on the page (tests).
PRESETS: dict[str, dict] = {
    "koha": {"label": "Koha green", "note": "Koha's own green on white, solid and calm.",
             "look": {"texture": "flat", "opacity": 100, "blur": 0, "radius_block": 8, "radius_input": 6,
                      "radius_button": 6, "accent": "#3d7a37", "accent2": "#2c5a28", "surface": "#ffffff",
                      "page": "#f2f5f1", "film": 45, "shadow": "soft"},
             "bar": "#24331f"},
    "glass": {"label": "Blue glass", "note": "Frosted glass in blue over a pale sky: the wallpaper shows through.",
              "look": {"texture": "frosted", "opacity": 72, "blur": 14, "radius_block": 18, "radius_input": 10,
                       "radius_button": 10, "accent": "#2563eb", "accent2": "#0891b2", "surface": "#ffffff",
                       "page": "#e8eef8", "film": 35, "shadow": "texture"},
              "bar": "#16213a"},
    "graphite": {"label": "Graphite and amber", "note": "Smooth glass, graphite bar, warm amber buttons.",
                 "look": {"texture": "smooth", "opacity": 86, "blur": 10, "radius_block": 12, "radius_input": 8,
                          "radius_button": 8, "accent": "#b45309", "accent2": "#475569", "surface": "#ffffff",
                          "page": "#eceef1", "film": 50, "shadow": "medium"},
                 "bar": "#1f2733"},
    "paper": {"label": "Paper and terracotta", "note": "Matte paper, cream blocks and terracotta: a reading room.",
              "look": {"texture": "paper", "opacity": 96, "blur": 0, "radius_block": 10, "radius_input": 6,
                       "radius_button": 8, "accent": "#b4462a", "accent2": "#7a5c3e", "surface": "#fffaf1",
                       "page": "#ede4d6", "film": 55, "shadow": "soft"},
              "bar": "#3a2a22"},
    "metal": {"label": "Metal and petrol", "note": "Brushed metal with a petrol-blue accent, crisp and technical.",
              "look": {"texture": "metal", "opacity": 100, "blur": 0, "radius_block": 8, "radius_input": 6,
                       "radius_button": 6, "accent": "#0f766e", "accent2": "#64748b", "surface": "#f8fafc",
                       "page": "#e3e8ed", "film": 50, "shadow": "texture"},
              "bar": "#2a343e"},
}


def apply_preset(raw: dict | None, name: str) -> dict:
    """The settings with preset name on both sides (OPAC and staff): its
    palette, material, opacity, blur, corners and card shadow; each
    colour's texture back to automatic; the staff top bar in the preset's
    colour, its opacity following the blocks; the staff colours turned on.
    Everything else is kept."""
    cfg = normalize(raw)
    pre = PRESETS[name]
    look = pre["look"]
    for key, value in look.items():
        cfg[key] = value
    cfg["paint"] = {key: {"texture": "auto", "opacity": 100} for key in PAINTED}
    st = cfg["staff"]
    for key, value in look.items():
        if key == "film":
            st[key] = _clamp(value, *STAFF_FILM, DEFAULTS["staff"]["film"])
        else:
            st[key] = value
    st["paint"] = {key: {"texture": "auto", "opacity": 100} for key in PAINTED}
    st["bar"] = pre["bar"]
    st["header_glass"] = False
    st["enabled"] = True
    return normalize(cfg)


# The library's own looks (Paulo, 2026-10-31: "o usuário também vai poder
# salvar até 5 presets"): the look fields of both sides, kept in the panel's
# private folder next to the image host keys, never in Koha. A saved look
# carries what a ready-made one does plus the rest of the look (style
# details, each colour's texture, the staff top bar, card, density,
# contrast, text size); pictures, texts, news, buttons and the carousel stay
# out, as with the ready-made ones.
MAX_USER_PRESETS = 5
USER_PRESETS_FILE = "look-presets.json"
LOOK_KEYS = ("texture", "opacity", "blur", "radius_block", "radius_input", "radius_button", "accent", "accent2",
             "surface", "page", "film", "paint", *STYLE)
STAFF_LOOK_KEYS = (*LOOK_KEYS, "enabled", "bar", "header_glass", "header_opacity", "header_blur", "card",
                   "card_padding", "density", "contrast", "font")


def look_of(raw: dict | None) -> dict:
    """The look fields of the settings: {"opac": {...}, "staff": {...}}."""
    cfg = normalize(raw)
    return {"opac": {k: copy.deepcopy(cfg[k]) for k in LOOK_KEYS},
            "staff": {k: copy.deepcopy(cfg["staff"][k]) for k in STAFF_LOOK_KEYS}}


def apply_look(raw: dict | None, look: dict) -> dict:
    """The settings with a saved look laid over them (normalize() checks
    every value); everything that is not a look field is kept."""
    cfg = normalize(raw)
    for key, value in (look.get("opac") or {}).items():
        if key in LOOK_KEYS:
            cfg[key] = copy.deepcopy(value)
    for key, value in (look.get("staff") or {}).items():
        if key in STAFF_LOOK_KEYS:
            cfg["staff"][key] = copy.deepcopy(value)
    return normalize(cfg)


def user_presets_file() -> Path:
    return Path(os.environ.get("KEI_OPAC_PRESETS") or CONFIG_DIR / USER_PRESETS_FILE)


def load_user_presets() -> list[dict]:
    """The saved looks, [{"name", "look"}], at most MAX_USER_PRESETS; a
    damaged file reads as none."""
    try:
        data = json.loads(user_presets_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("look"), dict):
            name = item["name"].strip()[:40]
            if name and len(out) < MAX_USER_PRESETS:
                out.append({"name": name, "look": look_of(apply_look({}, item["look"]))})
    return out


def save_user_presets(items: list[dict]) -> None:
    if len(items) > MAX_USER_PRESETS:
        raise ValueError(f"at most {MAX_USER_PRESETS} saved looks")
    path = user_presets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump([{"name": i["name"], "look": i["look"]} for i in items], fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def look_saved(raw: dict | None, items: list[dict] | None = None) -> bool:
    """The look of the settings is one of the saved looks or a ready-made one
    as it is (nothing to lose by switching)."""
    now = look_of(raw)
    if any(look_of(apply_preset(raw, name)) == now for name in PRESETS):
        return True
    return any(item["look"] == now for item in (load_user_presets() if items is None else items))


# Pictures an https address shows on both sides; a file of this server is
# in the OPAC's folder (/images/custom), which the staff side does not serve.
def copy_opac_to_staff(raw: dict | None) -> tuple[dict, list[str]]:
    """"Copy OPAC preset": the OPAC's material, style details, colours, page
    colour and pictures into cfg["staff"] (turned on), the staff's own type
    size, contrast and table density kept. Returns (settings, the names of
    the pictures left out: OPAC files on this server, re-chosen on the staff
    side)."""
    cfg = normalize(raw)
    st = cfg["staff"]
    st["enabled"] = True
    for key in ("texture", "accent", "accent2", "surface", "page", *STAFF_MATERIAL, *STYLE):
        st[key] = cfg[key]
    st["paint"] = copy.deepcopy(cfg["paint"])
    st["film"] = _clamp(cfg["film"], *STAFF_FILM, DEFAULTS["staff"]["film"])
    skipped = []
    for name in STAFF_ASSETS:
        pic = cfg[name]
        if pic["url"].startswith("https://"):
            st[name] = {"source": "url", "url": pic["url"]}
        elif pic["url"]:
            skipped.append(name)
    return normalize(cfg), skipped


def data_line(cfg: dict) -> str:
    """The settings as a CSS comment (one line; "*/" cannot end it early).
    The login instructions, credits and news stay out (contents_settings())."""
    data = normalize(cfg)
    for key in ("login", "credits", "news"):
        data.pop(key)
    text = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
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


def _json(text: str) -> dict | None:
    # strict=False: the protocol line turns the "\\n" of a value into a real
    # new line, which JSON strings may then hold.
    try:
        data = json.loads(text or "", strict=False)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _from_script(conf: dict) -> dict:
    """The settings that the config of our OpacUserJS script still tells
    (when the settings line itself is gone)."""
    car = conf.get("carousel") if isinstance(conf.get("carousel"), dict) else None
    lists = conf.get("lists") if isinstance(conf.get("lists"), dict) else None
    lk = conf.get("links") if isinstance(conf.get("links"), dict) else None
    return {"default_theme": conf.get("default_theme"), "dark_switch": conf.get("dark_switch", True),
            "news_buttons": conf.get("news_buttons", True),
            "ghost": {"empty_columns": conf.get("empty_columns", True)},
            "carousel": {**(lists or {}), **(car or {}), "enabled": car is not None,
                         "lists": bool(lists and lists.get("always"))},
            "links": {**(lk or {}), "enabled": lk is not None}}


# The values of the panel's stylesheets that someone can edit in Koha
# (Administration > System preferences): the CSS variable -> (setting,
# kind). They win over the settings line, which only says what the panel
# wrote last (Paulo, 2026-10-31: the instance is always the base).
_CSS_VARS = {"--nexus-primary": ("accent", "hex"), "--nexus-secondary": ("accent2", "hex"),
             "--nexus-surface": ("surface", "hex"), "--koha-card-alpha": ("opacity", "alpha"),
             "--koha-glass-blur": ("blur", "px"), "--koha-card-radius": ("radius_block", "px"),
             "--kei-r-input": ("radius_input", "px"), "--kei-r-btn": ("radius_button", "px"),
             "--kei-film": ("film", "alpha")}
_STAFF_CSS_VARS = {"--nexus-staff-primary": ("accent", "hex"), "--nexus-staff-secondary": ("accent2", "hex"),
                   "--nexus-staff-card": ("surface", "hex"), "--nexus-staff-surface-a": ("opacity", "alpha"),
                   "--nexus-staff-blur": ("blur", "px"), "--nexus-staff-radius": ("radius_block", "px"),
                   "--nexus-staff-r-input": ("radius_input", "px"), "--nexus-staff-r-btn": ("radius_button", "px"),
                   "--nexus-staff-card-pad": ("card_padding", "px"), "--nexus-staff-bar-colour": ("bar", "hex")}


def css_values(css: str, staff: bool = False) -> dict:
    """The settings the panel's stylesheet in Koha says now: the variables
    of its first :root rule (colours, opacity, blur, corners) and, for the
    OPAC, the logo and wallpaper addresses. Only what is there."""
    out: dict = {}
    m = re.search(r":root\s*\{(.*?)\}", css or "", re.S)
    if m:
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)):
            key, kind = (_STAFF_CSS_VARS if staff else _CSS_VARS).get(name, (None, None))
            value = value.strip()
            if not key:
                continue
            if kind == "hex" and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                out[key] = value.lower()
            elif kind == "alpha" and re.fullmatch(r"[0-9.]+", value):
                out[key] = round(float(value) * 100)
            elif kind == "px" and re.fullmatch(r"[0-9.]+px", value):
                out[key] = round(float(value[:-2]))
    if not staff:
        logo = re.search(r'#logo, h1#logo a[^{]*\{\s*background-image:\s*url\("([^"]+)"\)', css or "")
        wall = re.search(r'body\.kei-wallpaper\s*\{\s*background:\s*url\("([^"]+)"\)', css or "")
        for key, hit in (("logo", logo), ("background", wall)):
            if hit:
                out[key] = hit.group(1)
    return out


# Koha 26's own look (opac.scss, staff _variables.scss), the base of the
# fields when none of the panel's look is in Koha: the OPAC's green buttons
# ($base-theme-color), the staff's green ($background-color-primary),
# white blocks, solid and square-ish like Koha draws them.
KOHA_OWN = {"texture": "flat", "opacity": 100, "blur": 0, "accent": "#548300", "accent2": "#3f6200",
            "surface": "#ffffff", "page": "", "radius_block": 0, "radius_input": 4, "radius_button": 4,
            "dark_switch": False, "carousel": {"enabled": False}, "ghost": {"rss": False, "cart_badge": False,
                                                                             "community": False, "empty_columns": False},
            "staff": {"enabled": False, "accent": "#408540", "accent2": "#2f6b2f", "surface": "#ffffff",
                      "texture": "flat", "opacity": 100, "radius_block": 4, "radius_input": 4, "radius_button": 4}}


def split_block(text: str) -> tuple[str, str]:
    """(the panel's block, the library's own lines) of a preference."""
    block, own, inside = [], [], False
    for line in (text or "").replace("\r", "").split("\n"):
        if line.strip() == CSS_BEGIN:
            inside = True
        elif line.strip() == CSS_END:
            inside = False
        elif inside:
            block.append(line)
        else:
            own.append(line)
    return "\n".join(block), "\n".join(own)


_HEX = r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b"


def _hex6(value: str) -> str:
    value = value.lower()
    return "#" + "".join(c * 2 for c in value[1:]) if len(value) == 4 else value


def own_css_values(css: str, staff: bool = False) -> dict:
    """What the library's own CSS (written by hand in Koha, outside the
    panel's block) says of the fields: the panel's variables if it uses
    them, the main buttons' colour (accent), the page's colour or picture,
    the content's background (blocks), the logo. The last rule wins, as in
    the browser."""
    css = re.sub(r"/\*.*?\*/", "", css or "", flags=re.S)
    # The dark theme's rules are not the fields (its darker buttons).
    css = re.sub(r"""[^{}]*\[data-kei-theme\s*=\s*["']?dark["']?\][^{}]*\{[^{}]*\}""", "", css)
    out: dict = {}
    names = _STAFF_CSS_VARS if staff else _CSS_VARS
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;}]+)", css):
        key, kind = names.get(name, (None, None))
        value = value.strip()
        if kind == "hex" and re.fullmatch(_HEX, value):
            out[key] = _hex6(value)
        elif kind == "alpha" and re.fullmatch(r"[0-9.]+", value):
            out[key] = round(float(value) * 100)
        elif kind == "px" and re.fullmatch(r"[0-9.]+px", value):
            out[key] = round(float(value[:-2]))
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        sels = [x.strip().lower() for x in selectors.split(",")]
        colour = re.search(r"background(?:-color)?\s*:[^;]*?(" + _HEX + ")", body)
        picture = re.search(r"background(?:-image)?\s*:[^;]*?url\(\s*['\"]?([^'\")\s]+)", body)
        if any(x.endswith(".btn-primary") for x in sels) and colour:
            out["accent"] = _hex6(colour.group(1))
        if any(x in ("body", "html body", "html") for x in sels):
            if picture and not staff:
                out["background"] = picture.group(1)
            elif colour:
                out["page"] = _hex6(colour.group(1))
        if any(x in (".main", "#main", "html body .main") for x in sels) and colour:
            out["surface"] = _hex6(colour.group(1))
        if not staff and any("#logo" in x for x in sels) and picture:
            out["logo"] = picture.group(1)
    return out


def _css_overlay(cfg: dict, found: dict[str, str]) -> tuple[dict, list[str]]:
    """cfg with what the stylesheets in Koha say now (css_values()), and the
    names of the settings that differed from the settings line."""
    changed: list[str] = []
    raw = copy.deepcopy(cfg)
    for pref, staff in (("OpacUserCSS", False), ("IntranetUserCSS", True)):
        text = found.get(f"css_{pref}", "")
        if not text:
            continue
        try:
            whole = base64.b64decode(text, validate=True).decode("utf-8", "replace")
        except ValueError:
            continue
        block, own = split_block(whole)
        place = raw["staff"] if staff else raw
        # The library's own CSS first, the panel's block after it (it comes
        # last in Koha, so it wins where both say something).
        values = {**own_css_values(own, staff), **css_values(block, staff)}
        for key, value in values.items():
            if key == "page":
                if place.get("page") != value:
                    place["page"] = value
                    changed.append(("staff " if staff else "") + key)
                continue
            if key in ("logo", "background"):
                if value != place[key]["url"]:
                    # https: a direct address; a path: a file published on this server.
                    place[key] = {"source": "url" if value.startswith("https://") else "local", "url": value}
                    changed.append(key)
                continue
            if key == "blur" and not value:
                continue          # a flat material draws no blur: the slider keeps its value
            if place.get(key) != value:
                place[key] = value
                changed.append(("staff " if staff else "") + key)
        if staff and found.get("block_IntranetUserCSS") == "yes":
            raw["staff"]["enabled"] = True
    # The favicons Koha shows now (preferences OpacFavicon, IntranetFavicon).
    for pref, place, name in (("OpacFavicon", raw, "favicon"), ("IntranetFavicon", raw["staff"], "staff favicon")):
        url = safe_url(found.get(f"pref_{pref}", ""))
        if url and url != place["favicon"]["url"]:
            place["favicon"] = {"source": "url" if url.startswith("https://") else "local", "url": url}
            changed.append(name)
    return normalize(raw), changed


def source_notes(found: dict[str, str]) -> list[tuple[str, dict]]:
    """Where the sync read: the Koha instance, its database, the installer's
    version and what each preference holds, so a wrong instance or an
    installer older than the panel shows at once."""
    if not found.get("installer_version"):
        return [("The installer (config.sh) is older than the panel and does not hand over all of Koha's "
                 "settings: update it (Update in the panel's menu), then sync again.", {})]
    notes = [("Read from Koha: instance ${instance} (database ${database}), installer ${version}.",
              {"instance": found.get("instance", "?"), "database": found.get("database", "?"),
               "version": found["installer_version"]})]
    for pref in ("OpacUserCSS", "OpacUserJS", "IntranetUserCSS", "IntranetUserJS"):
        notes.append(("${pref}: ${n} characters; the panel's block: ${block}.",
                      {"pref": pref, "n": found.get(f"chars_{pref}", "0"),
                       "block": "yes" if found.get(f"block_{pref}") == "yes" else "no"}))
    return notes


def sync_settings(found: dict[str, str], text: dict | None = None) -> tuple[dict, list[tuple[str, dict]], bool]:
    """What `--task opac-theme-sync` read in Koha, as the screen's settings,
    a report: (message, values) pairs, in English, for the screen to
    translate, and whether any of the panel's look is in Koha.

    Koha (the instance) decides, never the panel's own copy: the settings
    line of OpacUserCSS wins; without it, while our block is still in
    OpacUserCSS, the copy saved by the last apply (theme-settings.json);
    without that, what the config of our scripts in OpacUserJS and
    IntranetUserJS still tells. The login instructions, credits and news are
    the panel's entries now in Koha (live_contents()). Nothing of ours in
    Koha: the defaults, Koha's own look. [kei-button] markers in
    OpacMainUserBlock turn the news action buttons on."""
    notes: list[tuple[str, dict]] = []
    yes = {k: found.get(f"block_{k}") == "yes" for k in ("OpacUserCSS", "OpacUserJS", "IntranetUserCSS",
                                                          "IntranetUserJS")}
    cfg = parse_theme_data(found.get("data", ""))
    if cfg:
        notes.append(("Settings: read from OpacUserCSS.", {}))
    else:
        state = _json(found.get("state", "")) if yes["OpacUserCSS"] else None
        if state:
            cfg = normalize(state)
            notes.append(("Settings: not in OpacUserCSS; taken from the copy saved by the last Apply "
                          "(theme-settings.json).", {}))
        else:
            opac_js = _json(found.get("config_OpacUserJS", ""))
            staff_js = _json(found.get("config_IntranetUserJS", ""))
            if opac_js or staff_js:
                raw = _from_script(opac_js) if opac_js else {}
                if staff_js and isinstance(staff_js.get("links"), dict):
                    raw["staff_links"] = {**staff_js["links"], "enabled": True}
                cfg = normalize({**KOHA_OWN, **raw})
                notes.append(("Settings: rebuilt from the panel's scripts in Koha (buttons, carousel, "
                              "light/dark); colours and pictures from the stylesheets in Koha.", {}))
    # The panel's look is in Koha: its settings, or at least its block.
    look = cfg is not None or yes["OpacUserCSS"] or yes["IntranetUserCSS"]
    if cfg is None:
        # Nothing of the panel's settings: the base is Koha's own look, and
        # over it what the stylesheets in Koha say (the library's own CSS,
        # a block of ours without its settings line), never the panel's
        # factory settings.
        cfg, changed = _css_overlay(normalize(KOHA_OWN), found)
        if changed:
            notes.append(("Read from the stylesheets and preferences in Koha: ${names}.",
                          {"names": ", ".join(changed)}))
    else:
        cfg, changed = _css_overlay(cfg, found)
        if changed:
            notes.append(("Edited in Koha's stylesheets, read from there: ${names}.",
                          {"names": ", ".join(changed)}))
    in_koha = look
    try:
        live = live_contents(found, text)
    except Exception as e:      # noqa: BLE001 (one unreadable entry must not cost the rest of the look)
        live = None
        notes.append(("Login instructions, footer credits and news could not be read: ${error}",
                      {"error": str(e)}))
    if live is not None:
        extra, more = live
        on = (any(login_on(lg) for lg in extra["login"].values()) or credits_on(extra["credits"])
              or any(news_on(n) for n in extra["news"].values()))
        in_koha = in_koha or on
        cfg = normalize({**cfg, **extra})
        notes += more
    else:
        extra = parse_contents(found.get("contents_settings", ""))
        if look and extra:
            cfg = normalize({**cfg, **extra})
            notes.append(("Login instructions and footer credits: read from theme-settings.json.", {}))
    if not in_koha:
        notes.insert(0, ("Nothing of the panel's look is in Koha: the fields show Koha's own look and what "
                         "the library's own CSS and preferences say.", {}))
    if look:
        if not yes["OpacUserCSS"] or not yes["OpacUserJS"]:
            missing = [k for k in ("OpacUserCSS", "OpacUserJS") if not yes[k]]
            notes.append(("The panel's block is missing from ${prefs}: Apply writes it again.",
                          {"prefs": ", ".join(missing)}))
        if staff_active(cfg) and not yes["IntranetUserCSS"]:
            notes.append(("The panel's block is missing from ${prefs}: Apply writes it again.",
                          {"prefs": "IntranetUserCSS"}))
        if staff_js_on(cfg) and not yes["IntranetUserJS"]:
            notes.append(("The panel's block is missing from ${prefs}: Apply writes it again.",
                          {"prefs": "IntranetUserJS"}))
        notes.append(("Quick access buttons: OPAC ${opac}, staff ${staff}.",
                      {"opac": str(len(cfg["links"]["items"]) if cfg["links"]["enabled"] else 0),
                       "staff": str(len(cfg["staff_links"]["items"]) if cfg["staff_links"]["enabled"] else 0)}))
    for pref in ("OpacUserCSS", "OpacUserJS", "IntranetUserCSS", "IntranetUserJS"):
        own = found.get(f"own_{pref}", "0")
        if own.isdigit() and int(own):
            notes.append(("${pref}: ${n} lines of the library's own, kept as they are.", {"pref": pref, "n": own}))
    markers = found.get("mainblock_buttons", "0")
    markers = int(markers) if markers.isdigit() else 0
    if markers:
        notes.append(("OpacMainUserBlock: ${n} [kei-button] markers.", {"n": str(markers)}))
        if cfg and not cfg["news_buttons"]:
            cfg["news_buttons"] = True
            notes.append(("News action buttons turned on, so those markers become buttons.", {}))
    elif found.get("mainblock") == "yes":
        notes.append(("OpacMainUserBlock: no [kei-button] markers.", {}))
    return cfg, notes, in_koha


# ----------------------------------------------------------------------
# The HTML customizations as Koha holds them now
# ----------------------------------------------------------------------
# opac-theme-get hands back the panel's own entries (code kei-<place>) that
# are in Koha now, as live_contents={place: {"title", "content"}}. They are
# what the OPAC and the staff interface show, so they decide what the screen
# shows: a backup restore or an edit made in Koha's own News / HTML
# customizations tool comes back into the fields. The form settings saved by
# the last apply (theme-settings.json) are used only where they still give
# exactly the HTML that is in Koha (the credits form keeps its fields that way).
_TAG = re.compile(r"<[^>]+>")
_ATTR = re.compile(r'([a-zA-Z-]+)\s*=\s*"([^"]*)"')


def _plain(fragment: str) -> str:
    """The text of an HTML fragment, entities decoded, spaces folded."""
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment or ""))).strip()


def _anchors(fragment: str) -> list[tuple[dict, str]]:
    """(attributes, text) of each <a> of fragment, in order."""
    out = []
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a\s*>", fragment or "", re.S | re.I):
        attrs = {k.lower(): html.unescape(v) for k, v in _ATTR.findall(m.group(1))}
        out.append((attrs, _plain(m.group(2))))
    return out


def _after_label(fragment: str) -> str:
    """"Label: value" -> value (the label is in the panel's language)."""
    text = _plain(fragment)
    return text.split(": ", 1)[1].strip() if ": " in text else text


def _by_class(content: str, tag: str, cls: str) -> list[str]:
    """The inner HTML of each <tag class="... cls ..."> of content."""
    pattern = rf'<{tag}\b[^>]*class="[^"]*\b{re.escape(cls)}\b[^"]*"[^>]*>(.*?)</{tag}\s*>'
    return re.findall(pattern, content or "", re.S | re.I)


def _unwrap(content: str, cls: str) -> tuple[str, bool]:
    """content without our outer <div class="cls"> (and whether it was there)."""
    text = (content or "").strip()
    m = re.fullmatch(rf'<div\b[^>]*class="[^"]*\b{re.escape(cls)}\b[^"]*"[^>]*>(.*)</div\s*>', text, re.S | re.I)
    return (m.group(1).strip(), True) if m else (text, False)


def login_from_html(content: str) -> dict:
    """The login instructions form of what Koha shows on a login page."""
    inner, _ours = _unwrap(content, "kei-login")
    image = {"source": "url", "url": ""}
    alt = ""
    banner = re.search(r'<p\b[^>]*class="[^"]*\bkei-login-banner-wrap\b[^"]*"[^>]*>\s*(<img\b[^>]*>)\s*</p\s*>',
                       inner, re.S | re.I)
    if banner:
        attrs = {k.lower(): html.unescape(v) for k, v in _ATTR.findall(banner.group(1))}
        image["url"] = attrs.get("src", "")
        alt = attrs.get("alt", "")
        inner = (inner[:banner.start()] + inner[banner.end():]).strip()
    return _login({"enabled": True, "html": inner, "image": image, "alt": alt})


# A link that looks like a button: Koha's / Bootstrap's .btn, the panel's
# .kei-news-button, or a library's own class with "btn" or "button" in it
# (.btn-acesso).
_BUTTON_LINK = re.compile(r'<a\b(?=[^>]*\bclass="[^"]*(?:\bbtn|button)[^"]*")[^>]*>.*?</a\s*>', re.S | re.I)


def news_from_html(title: str, content: str, koha_id: int = 0) -> dict:
    """The news form of a news item as Koha holds it: the title of Koha's
    own field, the text, and its buttons (the panel's button row, or the
    library's own button links, wherever they are in the text)."""
    text = re.sub(r"<!--\s*kei-news-(?:title|id):.*?-->", "", content or "", flags=re.S)
    inner, _ours = _unwrap(text, "kei-news")
    buttons = []
    for m in _BUTTON_LINK.finditer(inner):
        for attrs, label in _anchors(m.group(0)):
            if label and attrs.get("href"):
                buttons.append({"text": label, "url": attrs["href"]})
    inner = _BUTTON_LINK.sub("", inner)
    inner = re.sub(r'<p\b[^>]*class="[^"]*\bkei-news-cta\b[^"]*"[^>]*>\s*</p\s*>', "", inner, flags=re.S | re.I)
    html_text = sanitize_html(inner)
    if not _plain(html_text) and "<img" not in html_text:
        html_text = ""          # only spaces and &nbsp; were left between the buttons
    return _news({"enabled": True, "title": title, "html": html_text, "buttons": buttons, "koha_id": koha_id})


def credits_from_html(content: str) -> dict:
    """The footer credits form of the credits Koha shows: each line of our
    markup back into its field. Credits that are not the panel's markup at
    all go into the note as plain text."""
    inner, ours = _unwrap(content, "kei-credits")
    if ours and re.match(r'\s*<div\b[^>]*class="[^"]*\bkei-credits-ordered\b', content or ""):
        return _credits_ordered_from_html(inner)
    if not ours and not _by_class(inner, "p", "kei-credits-name"):
        # The library's own credits: each of its lines kept, in its order,
        # the first one as the name (as in the panel's text box).
        lines = [ln for ln in (_plain(x) for x in _BREAKS.split(inner)) if ln]
        if len(lines) < 2:
            return _credits({"enabled": True, "order": ["text:" + ln for ln in lines]})
        return _credits({"enabled": True, "name": lines[0],
                         "order": ["name"] + ["text:" + ln for ln in lines[1:]]})
    r: dict = {"enabled": True}
    first = lambda cls: (_by_class(inner, "p", cls) or [""])[0]   # noqa: E731
    r["name"] = _plain(first("kei-credits-name"))
    r["address"] = _plain(first("kei-credits-address"))
    r["hours"] = _after_label(first("kei-credits-hours"))
    r["note"] = _plain(first("kei-credits-note"))
    r["cnpj"] = _after_label(first("kei-credits-cnpj"))
    for part in first("kei-credits-contact").split(" · "):
        found = _anchors(part)
        if not found:
            if _plain(part):
                r["phone"] = _after_label(part)
            continue
        attrs, label = found[0]
        href = attrs.get("href", "")
        if href.startswith("tel:"):
            r["phone"] = label
        elif "wa.me/" in href:
            r["whatsapp"] = href.rsplit("/", 1)[-1]
        elif href.startswith("mailto:"):
            r["email"] = href[len("mailto:"):]
        elif href.startswith(("https://", "http://")):
            r["website"] = href
    for attrs, label in _anchors(first("kei-credits-social")):
        href = attrs.get("href", "")
        if "instagram.com" in href:
            handle = label.split(" ", 1)[1] if label.startswith("Instagram @") else ""
            r["instagram"] = handle or href
        elif "facebook.com" in href or label == "Facebook":
            r["facebook"] = href
        elif "youtube.com" in href or "youtu.be" in href or label == "YouTube":
            r["youtube"] = href
    r["links"] = [{"text": label, "url": attrs.get("href", "")} for attrs, label in _anchors(first("kei-credits-links"))]
    return _credits(r)


_BREAKS = re.compile(r"<br\s*/?>|</(?:p|div|li|h[1-6]|tr)\s*>|<hr\b[^>]*>|\n", re.I)


def _credits_ordered_from_html(inner: str) -> dict:
    """The form of the panel's credits written one line each, in order."""
    r: dict = {"enabled": True, "links": []}
    order: list[str] = []
    for m in re.finditer(r'<p\b[^>]*class="kei-credits-([a-z]+)"[^>]*>(.*?)</p\s*>', inner, re.S | re.I):
        key, body = m.group(1), m.group(2)
        found = _anchors(body)
        href = found[0][0].get("href", "") if found else ""
        if key == "line":
            # Its links (addresses made links) back into the text as they were.
            line = re.sub(r"\s+", " ", html.unescape(_TAG.sub("", body))).strip()
            if line:
                order.append("text:" + line)
            continue
        if key not in CREDITS_ORDER_KEYS:
            continue
        if key in ("name", "address", "note"):
            r[key] = _plain(body)
        elif key in ("hours", "cnpj"):
            r[key] = _after_label(body)
        elif key == "phone":
            r[key] = found[0][1] if found else _after_label(body)
        elif key == "whatsapp":
            r[key] = href.rsplit("/", 1)[-1]
        elif key == "email":
            r[key] = href[len("mailto:"):] if href.startswith("mailto:") else _after_label(body)
        elif key == "instagram":
            label = found[0][1] if found else ""
            r[key] = (label.split(" ", 1)[1] if label.startswith("Instagram @") else "") or href
        elif key in ("website", "facebook", "youtube"):
            r[key] = href
        else:
            r["links"] = [{"text": label, "url": a.get("href", "")} for a, label in found]
        order.append(key)
    r["order"] = order
    return _credits(r)


def _same(a: str, b: str) -> bool:
    return re.sub(r"\s+", " ", a or "").strip() == re.sub(r"\s+", " ", b or "").strip()


def live_contents(found: dict[str, str], text: dict | None = None) -> tuple[dict, list[tuple[str, dict]]] | None:
    """The login, credits and news settings of what Koha holds now (see
    above), and a report; None when the installer did not read them (an
    older installer, or a Koha before 23.11)."""
    raw = (found.get("live_contents") or "").strip()
    if not raw:
        return None
    if not raw.startswith("{"):     # base64 of the JSON, as the installer sends it
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    live = _json(raw)
    if live is None:
        return None
    saved = parse_contents(found.get("contents_settings", ""))
    saved = normalize(saved) if saved else None
    entry = lambda place: live.get(place) if isinstance(live.get(place), dict) else None   # noqa: E731
    out = {"login": {}, "credits": {}, "news": {}}
    notes: list[tuple[str, dict]] = []
    edited: list[str] = []
    for side, place in LOGIN_SIDES.items():
        got = entry(place)
        if not got:
            out["login"][side] = _login({})
            continue
        content = str(got.get("content") or "")
        if saved and login_on(saved["login"][side]) and _same(login_html(saved["login"][side]), content):
            out["login"][side] = saved["login"][side]
        else:
            out["login"][side] = login_from_html(content)
            edited.append(place)
    got = entry("opaccredits")
    if not got:
        out["credits"] = _credits({})
    else:
        content = str(got.get("content") or "")
        if saved and credits_on(saved["credits"]) and _same(credits_html(saved["credits"], text), content):
            out["credits"] = saved["credits"]
        else:
            out["credits"] = credits_from_html(content)
            edited.append("opaccredits")
    for side, place in NEWS_SIDES.items():
        got = entry(place)
        if not got:
            out["news"][side] = _news({})
            continue
        title, content = str(got.get("title") or ""), str(got.get("content") or "")
        koha_id = got.get("id") if got.get("own") and isinstance(got.get("id"), int) else 0
        mine = saved["news"][side] if saved else None
        if (mine and news_on(mine) and mine["title"] == title.strip() and mine["koha_id"] == koha_id
                and _same(news_html(mine).split("\n", 1)[1], content)):
            out["news"][side] = mine
        else:
            out["news"][side] = news_from_html(title, content, koha_id)
            edited.append(place)
        if koha_id:
            notes.append(("${place}: the library's own news item ${id} (Tools > News) is shown here; Apply "
                          "updates it in place.", {"place": place, "id": str(koha_id)}))
    on = [place for side, place in LOGIN_SIDES.items() if login_on(out["login"][side])]
    on += ["opaccredits"] if credits_on(out["credits"]) else []
    on += [place for side, place in NEWS_SIDES.items() if news_on(out["news"][side])]
    notes.append(("Login instructions, footer credits and news: read from Koha (${places}).",
                  {"places": ", ".join(on) if on else "-"}))
    if edited:
        notes.append(("Changed in Koha since the last Apply, read from Koha's HTML: ${places}.",
                      {"places": ", ".join(edited)}))
    buttons = sum(len(out["news"][side]["buttons"]) for side in NEWS_SIDES)
    if buttons:
        notes.append(("News buttons in Koha: ${n}.", {"n": str(buttons)}))
    return out, notes


def _rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def mix(a: str, b: str, amount: float) -> str:
    """#rrggbb: a with amount (0-1) of b mixed in."""
    ca, cb = (tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(ca, cb))


def luminance(hex_color: str) -> float:
    """Relative luminance (WCAG) of #rrggbb, 0 (black) to 1 (white)."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def text_on(hex_color: str) -> str:
    """Dark or light text, whichever has the higher contrast on hex_color
    (a fixed luminance cut put white on orange and mid greens at 2.8:1)."""
    return "#111827" if contrast("#111827", hex_color) > contrast("#ffffff", hex_color) else "#ffffff"


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two #rrggbb colours (1 to 21)."""
    la, lb = luminance(a) + .05, luminance(b) + .05
    return max(la, lb) / min(la, lb)


def readable(color: str, bg: str, minimum: float = 4.5) -> str:
    """color, darkened (on a light bg) or lightened (on a dark one) just
    enough to reach the minimum contrast on bg (WCAG AA: 4.5)."""
    target = "#000000" if luminance(bg) > .18 else "#ffffff"
    for step in range(21):
        out = mix(color, target, step / 20)
        if contrast(out, bg) >= minimum:
            return out
    return target


def colourful(hex_color: str) -> bool:
    """A colour with a hue of its own: not a grey, nor almost black or white
    (HSL saturation 25% or more, lightness between 10% and 92%)."""
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hi, lo = max(r, g, b), min(r, g, b)
    light = (hi + lo) / 2
    if hi == lo or not .10 <= light <= .92:
        return False
    return (hi - lo) / (1 - abs(2 * light - 1)) >= .25


# Links when neither colour has a hue: a plain, legible blue.
LINK_FALLBACK = "#1d5fa8"


def link_base(accent: str, accent2: str) -> str:
    """The hue links and headings take. The accent is the highlight of the
    buttons; links only borrow it when it is a colour: a black, grey or
    white accent made the links look like the text around them (Paulo,
    2026-10-31: the accent changed the letters). Then the second colour,
    else a plain blue."""
    for c in (accent, accent2):
        if colourful(c):
            return c
    return LINK_FALLBACK


def staff_bar(st: dict) -> str:
    """The staff top bar's colour: its own when chosen, else a dark slate
    with a hint of the accent, so the accent stays on the buttons and the
    bar keeps light, readable menus whatever the accent is."""
    return st.get("bar") or mix("#1f252d", st["accent"], .14)


def panel_colors(cfg: dict, dark: bool) -> dict:
    """The colours of the one glass card every surface shares: in light
    mode a light glass (the block background when it is light, else white)
    with #1a1a1a text; in dark mode #161b22 glass with #e6edf3 text. The
    card is as see-through as the opacity slider says, so every colour is
    checked against the card over a black and over a white wallpaper: text
    gets 7:1, muted text, links and headings 4.5:1, as far as the opacity
    allows (a clear card leans on the text shadow)."""
    accent, hue = cfg["accent"], link_base(cfg["accent"], cfg["accent2"])
    if dark:
        card, text = "#161b22", "#e6edf3"
        muted, link, ink = "#9da7b3", "#79b8ff", "#f0f3f6"
        border, pane, stripe = "rgba(255, 255, 255, .08)", "rgba(255, 255, 255, .10)", "rgba(255, 255, 255, .05)"
        shadow = "0 1px 2px rgba(0, 0, 0, .65)"
    else:
        base = cfg["surface"] if luminance(cfg["surface"]) >= .30 else "#ffffff"
        card, text = mix(base, accent, .03), "#1a1a1a"
        # Headings in the text's own tone: letters never take the accent
        # (Paulo, 2026-10-31); only links carry a hue.
        muted, link, ink = "#4b5563", mix(hue, "#000000", .15), "#111827"
        border, pane, stripe = "rgba(255, 255, 255, .2)", "rgba(15, 23, 42, .12)", "rgba(15, 23, 42, .04)"
        shadow = "0 1px 1px rgba(255, 255, 255, .55)"
    a = cfg["opacity"] / 100
    grounds = [mix(card, wall, 1 - a) for wall in ("#000000", "#ffffff")]

    def fit(c: str, minimum: float = 4.5) -> str:
        # Towards white on the dark glass, towards black on the light one,
        # until the colour holds on every ground.
        target = "#ffffff" if dark else "#000000"
        for step in range(21):
            out = mix(c, target, step / 20)
            if min(contrast(out, g) for g in grounds) >= minimum:
                return out
        return target
    return {"card": card, "text": fit(text, 7), "muted": fit(muted), "link": fit(link), "ink": fit(ink),
            "border": border, "pane": pane, "stripe": stripe, "shadow": shadow, "grounds": grounds}


# ----------------------------------------------------------------------
# The stylesheet
# ----------------------------------------------------------------------
# One glass card for every surface (_cards_css): the header and search
# blocks, the page's content (.main), and Koha's own boxes when a page puts
# them outside .main. Inside .main the boxes take no background of their own
# (_panels_css): they show the card's glass, so nothing stacks into a
# thicker layer. "html body" before each one, and !important, so Koha's
# Bootstrap rules never win over the shared variables.
_BLOCKS = "#header-region .navbar, .navbar.navbar-expand, #opac-main-search, .mastheadsearch"
_CONTENT = "#opacmainuserblock, #opacmainblock, #news .newsitem, .newsitem, .news-item"
# Koha's boxes: the record, its action sidebar, breadcrumbs, the account
# menu, facets, tabs, toolbars. A card of their own outside .main (and
# outside dialogs), the card's glass showing through inside it.
_PANES = ("#catalogue_detail_biblio", "#ulactioncontainer", ".searchresults-sidebar", "#breadcrumbs", ".breadcrumb",
          "#usermenu", "#menu", "#facets", "#search-facets", ".tab-content", "#notes", "#toolbar", ".toolbar",
          ".selections-toolbar", "#action", ".nav_results", ".card", ".well", ".nav-pills", "#views .view a",
          "#views .view span", ".current-view", "#opacmainuserblock", "#opacmainblock", "#news .newsitem",
          ".newsitem", ".news-item")
# Outside .main only the outermost of those boxes is a card (never a card
# in a card), and never inside a dialog or a menu.
_OWN_CARDS = ("#catalogue_detail_biblio", "#ulactioncontainer", ".searchresults-sidebar", "#breadcrumbs",
              ".breadcrumb", "#usermenu", "#menu", "#facets", "#search-facets", ".tab-content", "#notes",
              "#opacmainuserblock", "#opacmainblock", ".newsitem", ".news-item")
_OUTSIDE = (":not(.main *):not(.modal *):not(.dropdown-menu *)"
            ":not(:is(" + ", ".join(_OWN_CARDS) + ") *)")
# Koha's own fills inside those boxes (opac.scss): pagers, toolbars, the
# "Browse results" box, the facet headings, the "Did you mean" bar.
_FILLS = (".tab-pane", ".list-group-item", ".card-body", ".card-header", ".nav-pills li", "#action li",
          ".view", ".results-pagination", ".pagination_footer", ".l_Results", ".pg_menu", ".pg_menu .pg_link span",
          ".pages .inactive", ".pages a", ".pages .currentPage", "#didyoumean", "#search-facets h2 a",
          "#toolbar.clearfix", ".nav_results ul", ".nav_results li")


def _strong(selectors: str) -> str:
    return ", ".join("html body " + x.strip() for x in selectors.split(","))


def _noise(freq: str, octaves: int, matrix: str, size: str = "256 256", kind: str = "fractalNoise") -> str:
    """A tile of SVG noise as a CSS url(): no picture file, a few hundred
    bytes in the CSS. freq "x y" stretches it (a low x and a high y give the
    fine horizontal streaks of brushed metal or of wood); matrix is the
    feColorMatrix that turns the noise into colour and alpha. Only <, >, #,
    % and quotes are escaped: the SVG has no script and no closing style tag."""
    w, h = size.split()
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'>"
           f"<filter id='n'><feTurbulence type='{kind}' baseFrequency='{freq}' numOctaves='{octaves}' "
           f"seed='7' stitchTiles='stitch'/><feColorMatrix values='{matrix}'/></filter>"
           f"<rect width='100%' height='100%' filter='url(%23n)'/></svg>")
    svg = svg.replace("%", "%25").replace("%2523", "%23").replace("<", "%3C").replace(">", "%3E").replace('"', "'")
    return f'url("data:image/svg+xml,{svg}")'


# Brushed streaks: light and dark hairlines along the brushing, from noise
# much finer across than along. Two tiles, one lightens and one darkens, so
# the streaks stay visible on a white card and on a dark one.
_BRUSH_LIGHT = _noise(".0006 .9", 3, "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1.35 -.63", "1600 160")
_BRUSH_DARK = _noise(".0009 .7", 2, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.1 .57", "1600 160")
# Wood: thin dark rings along the board (the ridges of turbulence noise,
# stretched) over a finer grain, both in browns.
_WOOD_RINGS = _noise(".0012 .04", 3, "0 0 0 0 .30  0 0 0 0 .17  0 0 0 0 .06  0 0 0 -9 1.05", "1600 400",
                     "turbulence")
_WOOD_GRAIN = _noise(".0015 .5", 2, "0 0 0 0 .32  0 0 0 0 .19  0 0 0 0 .08  0 0 0 -1.6 .78", "1600 160")
_PAPER_TOOTH = _noise(".85", 2, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -.5 .34", "180 180")
_PAPER_FIBRE = _noise(".006 .06", 2, "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .8 -.42", "800 400")


def _material(t: str, accent_rgb: str) -> dict:
    """The look of a material texture over a card, for the OPAC and the
    staff interface alike: the layers above the card's own colour (sheen),
    its edge and shadow (shadow). accent_rgb is the CSS variable with the
    accent as "r, g, b" (the anodised aluminium takes its colour).

    Metal: brushed streaks, a bright specular band at the top fading into a
    soft shade and a second, fainter reflection lower down, and a bevel
    (light top and left edges, dark bottom and right). Anodised aluminium:
    the same metal dyed in the accent colour. Wood: warm boards with rings
    and grain. Paper: a warm matte sheet with a fine tooth."""
    bevel = ("inset 0 1px 0 rgba(255, 255, 255, .85), inset 1px 0 0 rgba(255, 255, 255, .35), "
             "inset 0 -1px 0 rgba(0, 0, 0, .28), inset -1px 0 0 rgba(0, 0, 0, .14)")
    drop = "0 1px 2px rgba(0, 0, 0, .22), 0 10px 24px -8px rgba(0, 0, 0, .30)"
    light = (f"{_BRUSH_LIGHT}, {_BRUSH_DARK}, "
             "linear-gradient(180deg, rgba(255, 255, 255, .62) 0, rgba(255, 255, 255, .18) 34px, "
             "rgba(0, 0, 0, .05) 90px, rgba(255, 255, 255, .16) 150px, rgba(0, 0, 0, .07) 260px, "
             "rgba(0, 0, 0, 0) 420px) top / 100% 420px no-repeat, "
             "linear-gradient(112deg, rgba(255, 255, 255, 0) 30%, rgba(255, 255, 255, .22) 46%, "
             "rgba(255, 255, 255, 0) 60%)")
    if t == "metal":
        return {"sheen": f"{light}, linear-gradient(rgba(128, 138, 150, .30), rgba(128, 138, 150, .30))",
                "shadow": f"{bevel}, {drop}"}
    if t == "anodized":
        return {"sheen": f"{light}, linear-gradient(rgba(var({accent_rgb}), .26), rgba(var({accent_rgb}), .26)), "
                         "linear-gradient(rgba(120, 128, 140, .22), rgba(120, 128, 140, .22))",
                "shadow": f"{bevel}, {drop}"}
    if t == "wood":
        return {"sheen": f"{_WOOD_GRAIN}, {_WOOD_RINGS}, "
                         "linear-gradient(180deg, rgba(255, 240, 210, .30), rgba(255, 240, 210, 0) 40px), "
                         "linear-gradient(rgba(176, 116, 58, .34), rgba(150, 92, 40, .34))",
                "shadow": "inset 0 1px 0 rgba(255, 236, 200, .55), inset 0 -2px 0 rgba(70, 40, 15, .25), "
                          "0 1px 2px rgba(60, 35, 10, .25), 0 12px 26px -10px rgba(60, 35, 10, .40)"}
    if t == "paper":
        return {"sheen": f"{_PAPER_TOOTH}, {_PAPER_FIBRE}, "
                         "linear-gradient(rgba(250, 242, 222, .30), rgba(250, 242, 222, .30))",
                "shadow": "0 1px 1px rgba(60, 50, 30, .10), 0 2px 4px rgba(60, 50, 30, .06), "
                          "0 14px 24px -14px rgba(60, 50, 30, .35)"}
    return {"sheen": "", "shadow": ""}


def _texture(cfg: dict) -> dict:
    """What the texture adds to the shared card, the same on every surface:
    a sheen layered over the glass, a shadow, and whether it blurs."""
    t = cfg["texture"]
    none = "linear-gradient(transparent, transparent)"
    if t in MATERIALS:
        return {**_material(t, "--kei-accent-rgb"), "blur": cfg["blur"]}
    if t == "gradient":
        return {"sheen": "linear-gradient(135deg, transparent 0%, rgba(var(--kei-accent-rgb), .10) 55%, "
                         "rgba(var(--kei-accent2-rgb), .14) 100%)", "shadow": "0 4px 18px rgba(0, 0, 0, .08)",
                "blur": cfg["blur"]}
    if t == "flat":
        return {"sheen": none, "shadow": "none", "blur": 0}
    if t == "smooth":
        return {"sheen": none, "shadow": "0 4px 18px rgba(0, 0, 0, .08)", "blur": cfg["blur"]}
    return {"sheen": none, "shadow": "0 8px 32px rgba(0, 0, 0, .12)", "blur": cfg["blur"]}


def _card_tokens(c: dict) -> str:
    return (f"    --koha-card-rgb: {_rgb(c['card']).replace(',', ', ')};\n"
            f"    --koha-card-border: {c['border']};\n    --koha-pane-border: {c['pane']};\n    --koha-text: {c['text']};\n    --koha-muted: {c['muted']};\n"
            f"    --koha-link: {c['link']};\n    --koha-ink: {c['ink']};\n    --koha-stripe: {c['stripe']};\n"
            f"    --koha-text-shadow: {c['shadow']};")


def _cards_css(cfg: dict) -> str:
    """The one glass card: the same background (--koha-card-bg), blur
    (--koha-glass-blur), border and radius on the header and search
    blocks, the page's content and any of Koha's boxes outside it. The
    content's blur sits on a layer behind it: on .main itself it would
    become the frame of every position: fixed thing inside (Koha's modals)."""
    own = ", ".join(f"html body {x}{_OUTSIDE}" for x in _OWN_CARDS)
    card = """    background: var(--koha-card-sheen), var(--koha-card-bg) !important;
    color: var(--koha-text) !important;
    border: 1px solid var(--koha-card-border) !important;
    border-radius: var(--koha-card-radius) !important;
    box-shadow: var(--koha-card-shadow) !important;"""
    blur = """    -webkit-backdrop-filter: blur(var(--koha-glass-blur));
    backdrop-filter: blur(var(--koha-glass-blur));"""
    return f"""/* One glass card for every surface. */
{_strong(_BLOCKS)}, html body .main {{
{card}
}}
{_strong(_BLOCKS)} {{
{blur}
}}
/* Koha's boxes when a page puts them outside .main: the same card. A rule
   of its own, so a browser without :is() / :not(a b) keeps the others. */
{own} {{
{card}
{blur}
    padding: .75rem 1rem;
    margin-bottom: 1rem;
    text-shadow: var(--koha-text-shadow);
}}
html body .main {{
    position: relative;
    isolation: isolate;
    text-shadow: var(--koha-text-shadow);
}}
html body .main::before {{
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    pointer-events: none;
{blur}
}}
html body .main h1, html body .main h2, html body .main h3, html body .main h4, html body .main legend,
html body .newsitem h3, html body .news-item h3 {{ color: var(--koha-ink); }}
html body .main .text-muted, html body .newsitem .newsfooter {{ color: var(--koha-muted) !important; }}""" + (
        _material_main_css() if cfg["texture"] in MATERIALS else "")


def _header_css(cfg: dict) -> list[str]:
    """The OPAC header (#header-region): its top bar hidden, or the large
    header: taller, the picture covering all of it (else the two colours),
    a film for the legibility of the bar and the search over it."""
    out = []
    if not cfg["header_bar"]:
        out.append("html body #header-region > nav.navbar { display: none !important; }")
    if cfg["header_style"] != "large":
        return out
    pic = cfg["header"]["url"]
    paint = (f'url("{pic}") center / cover no-repeat' if pic
             else "linear-gradient(135deg, var(--kei-accent), var(--kei-accent2))")
    h = cfg["header_height"]
    out.append(f"""/* Large header: the picture covers the whole header. */
html body #header-region {{
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: {h}px;
    background: {paint} !important;
    border-radius: 0 0 var(--kei-r-block) var(--kei-r-block);
    overflow: visible;
}}
html body #header-region::before {{
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(180deg, rgba(0, 0, 0, .45), rgba(0, 0, 0, .12) 45%, rgba(0, 0, 0, .50));
    pointer-events: none;
}}
html body #header-region > * {{ position: relative; z-index: 1; }}
html body #header-region > nav.navbar, html body #header-region .navbar {{
    background: transparent !important;
    box-shadow: none !important;
    border: 0 !important;
}}
html body #header-region > nav.navbar .nav-link, html body #header-region > nav.navbar .navbar-text,
html body #header-region > nav.navbar .cartlabel, html body #header-region > nav.navbar #carticon,
html body #header-region > nav.navbar .userlabel {{
    color: #fff !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, .6);
}}
html body #header-region #opac-main-search, html body #header-region .mastheadsearch,
html body #header-region #moresearches {{
    background: transparent !important;
    box-shadow: none !important;
    border: 0 !important;
}}
html body #header-region #moresearches a {{ color: #fff !important; text-shadow: 0 1px 3px rgba(0, 0, 0, .6); }}
@media (max-width: 767px) {{
    html body #header-region {{ min-height: {max(160, h * 6 // 10)}px; }}
}}""")
    return out


def _material_main_css() -> str:
    """A material's streaks and grain on .main sit on a layer above its blur
    layer (::before): on .main itself the blur would smear them, since the
    blur layer is inside .main's own stacking context."""
    return """
html body .main { background: var(--koha-card-bg) !important; }
html body .main::after {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    pointer-events: none;
    background: var(--koha-card-sheen);
}"""


def css_body(cfg: dict) -> str:
    cfg = normalize(cfg)
    car, ghost = cfg["carousel"], cfg["ghost"]
    # One source of truth: every surface is the same glass card, its colours
    # from panel_colors (light and dark), its opacity and blur the sliders'.
    light, dark, tex = panel_colors(cfg, False), panel_colors(cfg, True), _texture(cfg)
    text = light["text"]
    out = [f""":root {{
    --nexus-primary: {cfg['accent']};
    --nexus-secondary: {cfg['accent2']};
    --nexus-surface: {cfg['surface']};
    --nexus-text: {text};
    --nexus-on-primary: {text_on(cfg['accent'])};
    --nexus-on-secondary: {text_on(cfg['accent2'])};
    --kei-accent: {cfg['accent']};
    --kei-accent-rgb: {_rgb(cfg['accent'])};
    --kei-accent2-rgb: {_rgb(cfg['accent2'])};
{_card_tokens(light)}
    --koha-card-alpha: {cfg['opacity'] / 100:.2f};
    --koha-card-bg: rgba(var(--koha-card-rgb), var(--koha-card-alpha));
    --koha-glass-blur: {tex['blur']}px;
    --koha-card-radius: {cfg['radius_block']}px;
    --koha-card-sheen: {tex['sheen']};
    --koha-card-shadow: {tex['shadow']};
    --kei-surface-rgb: var(--koha-card-rgb);
    --kei-surface-a: var(--koha-card-alpha);
    --kei-text: var(--koha-text);
    --kei-muted: var(--koha-muted);
    --kei-ink: var(--koha-ink);
    --kei-edge: var(--koha-card-border);
    --kei-blur: var(--koha-glass-blur);
    --kei-r-block: var(--koha-card-radius);
    --kei-r-input: {cfg['radius_input']}px;
    --kei-r-btn: {cfg['radius_button']}px;
    --kei-film: {cfg['film'] / 100:.2f};
}}
html[data-kei-theme="dark"] {{
{_card_tokens(dark)}
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
html[data-kei-theme="dark"] ::placeholder {{ color: #9da7b3; opacity: 1; }}
html[data-kei-theme="dark"] .text-muted, html[data-kei-theme="dark"] .breadcrumb-item {{ color: var(--kei-muted) !important; }}
{_cards_css(cfg)}
/* The header and its menus above the search bar: the glass of each block
   is a stacking context of its own, so the header's one has to win. */
html body #header-region, html body #header-region .navbar {{ position: relative; z-index: 1030; overflow: visible !important; }}
html body #header-region .dropdown-menu {{ z-index: 1060; }}
html body .main {{ padding: 1.25rem; margin-top: 1rem; }}
.form-control, .form-select, input[type="text"], input[type="search"], input[type="password"], select,
textarea {{ border-radius: var(--kei-r-input) !important; }}
{_buttons_css(cfg)}
{_dark_css(cfg)}
a:focus-visible, .btn:focus-visible {{ outline: 3px solid rgba(var(--kei-accent-rgb), .45); outline-offset: 2px; }}
{_panels_css(cfg)}"""]
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
    out += _header_css(cfg)
    out.append(_phone_css(cfg))
    hidden = []
    if ghost["rss"]:
        hidden += ["#rssnews", ".rsssearchlink", "a[href*='opac-news-rss']", "a[href*='format=rss']", "#rss"]
    if ghost["cart_badge"]:
        hidden += ["#basketcount", "#cartDetails", "#cartmenulink .badge"]
    if ghost["cart"]:
        # Koha 22-26: the Cart menu of the top bar, its message, the "Add to
        # cart" links and buttons of the results and of a record.
        hidden += ["#cart-list-nav > li:has(#cartmenulink)", "#cartmenulink", "#cartDetails", "#basketcount",
                   ".addtocart", "a.addtocart", ".cartRemove", "#addto option[value='addtocart']",
                   ".selections-toolbar .addtocart", "#toolbar .addtocart", ".cart-message"]
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
        out.append(SWITCH_ICON_CSS)
    if cfg["news_buttons"]:
        out.append(""".kei-action {
    display: flex;
    width: 100%;
    box-sizing: border-box;
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
.kei-action-title { display: block; font-weight: 600; overflow-wrap: anywhere; }
.kei-action-text { display: block; color: var(--kei-muted); font-size: .92em; }""")
    if car["enabled"] or car["lists"]:
        out.append(_carousel_css(car))
    if links_on(cfg["links"]):
        out.append(_links_css("#kei-links"))
    out.append(style_css(cfg, "opac"))
    return "\n".join(x for x in out if x) + "\n"


_TEXT = ("p", "li", "dd", "dt", "td", "th", "label", "legend", "caption", "blockquote", ".results_summary",
         ".note", ".content_set", ".authstanza", ".authstanzaheading", ".usedin", ".maincontent", ".tab-pane",
         ".heading", ".authorized")
_MUTED = (".text-muted", ".hint", "small", ".form-text", "p.details", ".label", ".results_summary .label",
          ".newsfooter", ".breadcrumb-item")
_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6", "legend")
_LINK_SKIP = (".btn", ".nav-link", ".dropdown-item", ".kei-link", ".kei-action", ".page-link", ".btn-acesso")


def _panels_css(cfg: dict) -> str:
    """Inside the card (.main): Koha paints its boxes white or grey (the
    record, its sidebar, breadcrumbs, the account menu, facets, tabs,
    toolbars, table stripes); here none keeps a background of its own, they
    show the card's glass with one hairline border (--koha-pane-border) and radius, so the page
    reads as one surface at any opacity. Text, labels, headings and links
    take colours checked against the card (panel_colors), with a soft text
    shadow and bolder labels. The footer credits sit on the page with no
    box, readable through a halo around the letters."""
    def sel(items, prefix: str = "html body .main ") -> str:
        return ", ".join(prefix + x for x in items)
    panes = sel(_PANES)
    links = "html body .main a" + "".join(f":not({x})" for x in _LINK_SKIP)
    return f"""/* Inside the card: Koha's boxes show its glass, no fills of their own. */
{panes} {{
    background: transparent !important;
    color: var(--koha-text) !important;
    border: 1px solid var(--koha-pane-border) !important;
    border-radius: calc(var(--koha-card-radius) * .6) !important;
    box-shadow: none !important;
    -webkit-backdrop-filter: none !important;
    backdrop-filter: none !important;
}}
/* The breadcrumbs blend into the card: a line under them, no box. */
html body .main #breadcrumbs, html body .main .breadcrumb {{
    border: 0 !important;
    border-radius: 0 !important;
    border-bottom: 1px solid var(--koha-pane-border) !important;
    padding: 0 0 .6rem !important;
    margin: 0 0 1rem !important;
}}
html body .main #breadcrumbs .breadcrumb {{ border-bottom: 0 !important; padding: 0 !important; margin: 0 !important; }}
html body .breadcrumb a {{ color: var(--koha-link) !important; }}
html body .breadcrumb-item, html body .breadcrumb-item.active {{ color: var(--koha-muted) !important; }}
html[data-kei-theme="dark"] body .breadcrumb-item + .breadcrumb-item::before {{ filter: invert(1); opacity: .7; }}
html body .main .btn, html body .main input, html body .main select, html body .main textarea,
html body .main .form-control, html body .main .badge {{ text-shadow: none; }}
html body .main label, html body .main dt, html body .main th, html body .main legend,
html body .main .results_summary .label {{ font-weight: 600; }}
/* The footer credits: no box, straight on the page, a halo around the
   letters (light in light mode, dark in dark mode) keeps them readable. */
html body #opaccredits {{ margin: 1rem 0; padding: .5rem 1rem; text-align: center; background: transparent !important; }}
html body #opaccredits, html body #opaccredits p, html body #opaccredits li {{ color: var(--koha-text) !important; }}
html body #opaccredits a {{ color: var(--koha-link) !important; font-weight: 600; }}
html body #opaccredits {{ text-shadow: 0 0 6px rgba(255, 255, 255, .95), 0 1px 1px rgba(255, 255, 255, .95); }}
html[data-kei-theme="dark"] body #opaccredits {{ text-shadow: 0 0 6px rgba(0, 0, 0, .95), 0 1px 2px rgba(0, 0, 0, .95); }}
html body .kei-credits p {{ margin: .2rem 0; }}
html body .kei-credits-name {{ font-size: 1.05rem; }}
html body .kei-login-banner-wrap {{ margin: 0 0 1rem; }}
html body .main .tab-content {{ border-top-left-radius: 0 !important; padding: .9rem 1rem; }}
{sel(_FILLS)} {{ background: transparent !important; color: var(--koha-text); }}
html body .main .pages .currentPage {{ background: rgba(var(--kei-accent-rgb), .14) !important; }}
html body .main .nav-tabs {{ border-bottom-color: var(--koha-pane-border); }}
html body .main .nav-tabs .nav-link {{ color: var(--koha-link) !important; background: transparent !important; }}
html body .main .nav-tabs .nav-link.active, html body .main .nav-tabs .nav-item.show .nav-link,
html body .main .nav-tabs .active > a {{
    background: var(--koha-stripe) !important;
    color: var(--koha-text) !important;
    border-color: var(--koha-pane-border) var(--koha-pane-border) transparent !important;
}}
/* The user menu (account pages), the facets and the action sidebar: one list, one radius. */
html body .main #menu ul, html body .main #usermenu ul {{ border: 0; overflow: hidden; }}
html body .main #menu li a, html body .main #usermenu li a {{
    background: transparent !important;
    color: var(--koha-link) !important;
    border: 0 !important;
    border-bottom: 1px solid var(--koha-pane-border) !important;
}}
html body .main #menu li:last-child a, html body .main #usermenu li:last-child a {{ border-bottom: 0 !important; }}
html body .main #menu li.active a, html body .main #usermenu li.active a,
html body .main #menu li a:hover, html body .main #usermenu li a:hover,
html body .main .nav-pills .nav-link.active {{
    background: rgba(var(--kei-accent-rgb), .14) !important;
    color: var(--koha-ink) !important;
    box-shadow: inset 3px 0 0 var(--nexus-primary);
}}
html body .main #search-facets ul, html body .main #search-facets li, html body .main #facets ul,
html body .main #facets li {{ background: transparent !important; }}
/* Tables and search results: rows on the card, stripes a faint see-through tint. */
html body .main table, html body .main .table {{
    --bs-table-bg: transparent;
    --bs-table-color: var(--koha-text);
    --bs-table-striped-bg: var(--koha-stripe);
    --bs-table-striped-color: var(--koha-text);
    --bs-table-hover-bg: rgba(var(--kei-accent-rgb), .08);
    --bs-table-hover-color: var(--koha-text);
    --bs-table-border-color: var(--koha-pane-border);
    background-color: transparent !important;
    color: var(--koha-text);
}}
html body .main table > * > tr > td, html body .main table > * > tr > th {{
    background-color: transparent !important;
    border-color: var(--koha-pane-border) !important;
}}
html body .main table > thead > tr > th, html body .main .table-striped > tbody > tr:nth-of-type(odd) > *,
html body .main .searchresults table > tbody > tr:nth-of-type(odd) > * {{ background-color: var(--koha-stripe) !important; }}
html body .main .pagination .page-link {{ background: transparent; border-color: var(--koha-pane-border); color: var(--koha-link); }}
html body .main .pagination .active .page-link, html body .main .pagination .page-item.active .page-link {{
    background: var(--nexus-primary); border-color: var(--nexus-primary); color: var(--nexus-on-primary);
}}
/* Text: crisp on the card, never the faint grey of Koha's defaults. */
html body .main, {sel(_TEXT)} {{ color: var(--koha-text) !important; }}
{sel(_MUTED)} {{ color: var(--koha-muted) !important; }}
{sel(_HEADINGS)} {{ color: var(--koha-ink) !important; }}
html body .main .alert h1, html body .main .alert h2, html body .main .alert h3, html body .main .alert h4,
html body .main .alert h5, html body .main .alert p, html body .main .alert li {{ color: inherit !important; }}
{links} {{ color: var(--koha-link); }}
html body .main .nav_results a, html body .main #a_listResults, html body .main #action a {{ color: var(--koha-link) !important; }}
/* Koha's alerts: a see-through tint of their colour on the card, in both modes. */
html body .main .alert {{
    background: rgba(var(--kei-accent-rgb), .12) !important;
    border-color: rgba(var(--kei-accent-rgb), .40) !important;
    color: var(--koha-text) !important;
}}
html body .main .alert-warning {{ background: rgba(227, 179, 65, .14) !important; border-color: rgba(227, 179, 65, .45) !important; }}
html body .main .alert-danger, html body .main .alert-error {{
    background: rgba(248, 81, 73, .12) !important; border-color: rgba(248, 81, 73, .45) !important; }}
html body .main .alert-success {{ background: rgba(63, 185, 80, .12) !important; border-color: rgba(63, 185, 80, .45) !important; }}
html[data-kei-theme="dark"] body .main .available, html[data-kei-theme="dark"] body .main .text-success {{ color: #56d364 !important; }}
html[data-kei-theme="dark"] body .main .unavailable, html[data-kei-theme="dark"] body .main .text-danger {{ color: #ff7b72 !important; }}
html[data-kei-theme="dark"] body .main .text-warning {{ color: #e3b341 !important; }}
html[data-kei-theme="dark"] body .main .term {{ color: #1a1a1a !important; }}"""

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
_CARD_BUTTONS = (".btn", ".btn-acesso", 'input[type="submit"]', 'input[type="button"]', 'button[type="submit"]')


# Brushed buttons for the metal textures, OPAC and staff alike: the
# streaks over a satin gradient with a hard specular edge at the middle.
_METAL_MAIN = (f"{_BRUSH_LIGHT}, linear-gradient(180deg, rgba(255, 255, 255, .42) 0%, rgba(255, 255, 255, .14) 48%, "
               "rgba(0, 0, 0, .06) 52%, rgba(0, 0, 0, .18) 100%), {c}")
_METAL_SOFT = (f"{_BRUSH_LIGHT}, {_BRUSH_DARK}, "
               "linear-gradient(180deg, #f8f9fa 0%, #e3e6ea 47%, #cdd2d8 53%, #dfe2e6 100%)")
_METAL_SHADOW = ("inset 0 1px 0 rgba(255, 255, 255, .75), inset 0 -1px 0 rgba(0, 0, 0, .22), "
                 "0 1px 1px rgba(0, 0, 0, .18), 0 4px 8px -2px rgba(0, 0, 0, .22)")


def _phone_css(cfg: dict) -> str:
    """The search results' toolbar and the phone layout (Koha 26):

    - #floating (the "Select all / Add to cart / Place hold" bar that sticks
      to the top while the results scroll) is one of the boxes left clear
      inside the content card, so the titles and covers scrolling under it
      showed through: it gets a near solid card of its own above them.
    - Under 700 px Koha swaps the logo for a 14 px house icon; the
      library's logo keeps a readable size instead.
    - Under 768 px a result is the cover above the text, not beside it.
    - The holdings tables (#holdingst, #otherholdingst) become one card per
      copy with "heading: value" lines (the headings from data-kei-label,
      set by the OPAC script), every column shown: DataTables hides the
      columns that do not fit, which left only two and an empty one."""
    logo = ""
    if cfg["logo"]["url"]:
        logo = """
@media only screen and (max-width: 700px) {
    html body #header-region #logo {
        flex: 0 0 auto !important;
        width: 132px !important;
        min-width: 132px;
        height: 40px;
        margin: 4px 8px !important;
        background-size: contain !important;
        background-position: left center !important;
    }
    html body #header-region #logo a { width: 132px !important; padding: 40px 0 0 !important; }
}"""
    return f"""/* The results toolbar that sticks to the top: a solid card above the results. */
html body #floating, html body .main #floating, html body .main .floating.sticky {{
    background: var(--koha-card-sheen), rgba(var(--koha-card-rgb), .96) !important;
    -webkit-backdrop-filter: blur(10px);
    backdrop-filter: blur(10px);
    border-radius: var(--kei-r-block);
    box-shadow: 0 8px 18px -12px rgba(15, 23, 42, .45);
    padding: .35rem .6rem;
    z-index: 1020 !important;
}}
html body .main #floating #toolbar, html body .main #floating .selections-toolbar {{ background: transparent !important; }}{logo}
@media only screen and (max-width: 767px) {{
    /* A result: the selection box and number on one line, the cover
       above the text, the text on the card's full width. */
    html body .searchresults table, html body .searchresults table > tbody {{ display: block; width: 100%; }}
    html body .searchresults table > tbody > tr {{
        display: flex !important;
        flex-wrap: wrap;
        align-items: center;
        padding: .6rem 0;
        border-bottom: 1px solid var(--koha-card-border);
    }}
    html body .searchresults table > tbody > tr > td:not(.hidden):not(.d-none) {{ display: block; border: 0 !important; }}
    html body .searchresults td.selectcol, html body .searchresults td.numcol, html body .searchresults td.itypecol {{
        flex: 0 0 auto; width: auto !important; padding: .2rem .4rem !important;
    }}
    html body .searchresults td.covercol {{ flex: 1 1 100%; width: 100% !important; text-align: center; padding: .3rem 0 !important; }}
    html body .searchresults td.covercol img {{ max-height: 220px; width: auto; max-width: 70%; margin: 0 auto; }}
    html body .searchresults td.covercol .cover-slider {{ display: inline-block; }}
    html body .searchresults td.bibliocol {{ flex: 1 1 100%; width: 100% !important; padding: .3rem .4rem !important; }}
    /* The holdings: one card per copy, every column a "heading: value" line. */
    html body table.kei-stack {{ display: block; width: 100% !important; border: 0 !important; }}
    html body table.kei-stack > thead, html body table.kei-stack > tbody > tr.child,
    html body table.kei-stack td.dtr-control, html body table.kei-stack th.dtr-control {{ display: none !important; }}
    html body table.kei-stack > tbody {{ display: block; }}
    html body table.kei-stack > tbody > tr {{
        display: block;
        margin: 0 0 .75rem;
        padding: .5rem .75rem;
        border: 1px solid var(--koha-card-border);
        border-radius: var(--kei-r-block);
        background: rgba(var(--koha-card-rgb), .55);
    }}
    html body table.kei-stack > tbody > tr > td {{
        display: flex !important;
        gap: .75rem;
        width: auto !important;
        padding: .3rem 0 !important;
        border: 0 !important;
        border-bottom: 1px dashed var(--koha-card-border) !important;
        text-align: left !important;
        white-space: normal !important;
        word-break: break-word;
    }}
    html body table.kei-stack > tbody > tr > td:last-child {{ border-bottom: 0 !important; }}
    html body table.kei-stack > tbody > tr > td[data-kei-label]::before {{
        content: attr(data-kei-label);
        flex: 0 0 40%;
        font-weight: 600;
        color: var(--koha-muted);
    }}
    html body table.kei-stack > tbody > tr > td:empty, html body table.kei-stack > tbody > tr > td[data-kei-label=""] {{
        display: none !important;
    }}
}}"""


def _paint(texture: str, rgb_var: str, opacity: int, button: bool) -> dict:
    """One colour in its own texture and opacity: {"bg": the background
    layers, "shadow": a box-shadow or "", "blur": True to blur what shows
    through}. rgb_var is the CSS variable with the colour as "r, g, b";
    button: a button (brushed like the metal buttons) or the page."""
    a = f"{opacity / 100:.2f}"
    colour = f"linear-gradient(rgba(var({rgb_var}), {a}), rgba(var({rgb_var}), {a}))"
    gloss = "linear-gradient(180deg, rgba(255, 255, 255, .16), rgba(255, 255, 255, 0) 60%)"
    if texture in METALS and button:
        return {"bg": _METAL_MAIN.format(c=f"rgba(var({rgb_var}), {a})"), "shadow": _METAL_SHADOW, "blur": False}
    if texture in MATERIALS:
        look = _material(texture, rgb_var)
        return {"bg": f"{look['sheen']}, {colour}", "shadow": look["shadow"] if button else "", "blur": False}
    if texture == "gradient":
        return {"bg": "linear-gradient(135deg, rgba(255, 255, 255, .26) 0%, rgba(255, 255, 255, 0) 50%, "
                      f"rgba(0, 0, 0, .12) 100%), {colour}", "shadow": "", "blur": False}
    if texture == "smooth":
        return {"bg": f"{gloss}, {colour}", "shadow": "0 4px 14px rgba(15, 23, 42, .16)" if button else "",
                "blur": True}
    if texture == "frosted":
        return {"bg": f"{gloss}, {colour}", "shadow": "0 8px 22px rgba(15, 23, 42, .18)" if button else "",
                "blur": True}
    return {"bg": colour, "shadow": "none" if button else "", "blur": False}


def _paint_rule(sel: str, paint: dict, fg: str) -> str:
    """The rule that paints the buttons sel with a _paint()."""
    lines = [f"    background: {paint['bg']} !important;"]
    if paint["shadow"]:
        lines.append(f"    box-shadow: {paint['shadow']} !important;")
    if paint["blur"]:
        lines += ["    -webkit-backdrop-filter: blur(var(--koha-glass-blur));",
                  "    backdrop-filter: blur(var(--koha-glass-blur));"]
    if fg:
        lines.append(f"    color: {fg} !important;")
    return sel + " {\n" + "\n".join(lines) + "\n}"


def _buttons_css(cfg: dict) -> str:
    """The OPAC's buttons: the main ones in the accent colour (brushed with
    the two metal textures), the secondary ones on the block surface,
    and full-width touch targets inside the news and the home page block."""
    main, soft = _strong(_BTN_MAIN), _strong(_BTN_SOFT)

    def hover(sel: str) -> str:
        return ", ".join(f"{x}:hover, {x}:focus" for x in sel.split(", "))

    if cfg["texture"] in METALS:
        main_bg, soft_bg, shadow = _METAL_MAIN.format(c="var(--nexus-primary)"), _METAL_SOFT, _METAL_SHADOW
        soft_fg, soft_edge = "#2a3038", "#9ba2ab"
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
@media (prefers-reduced-motion: reduce) {{ {main}, {soft} {{ transition: none; }} }}{_painted_buttons(cfg, main, soft)}"""


DARK_CARD = "#161b22"


def _dark_css(cfg: dict) -> str:
    """The dark theme (Paulo, 2026-10-31, 20:20):

    - a light accent or second colour (#f4f4f6 buttons) turns into a dark
      shade of itself, so the buttons darken with the page; the brushed
      secondary buttons of the metal textures too;
    - the catalogue card (ficha catalográfica) stays black on white, as on
      paper, and its "Show" button follows the theme;
    - the previous / back to results / next bar of a record (.nav_results,
      white in Koha's own CSS) goes dark."""
    d = 'html[data-kei-theme="dark"]'
    swaps = []
    for colour, var, rgb, on in ((cfg["accent"], "--nexus-primary", "--kei-accent-rgb", "--nexus-on-primary"),
                                 (cfg["accent2"], "--nexus-secondary", "--kei-accent2-rgb", "--nexus-on-secondary")):
        if luminance(colour) > .45:
            dark = mix(colour, DARK_CARD, .72)
            swaps.append(f"    {var}: {dark};\n    {rgb}: {_rgb(dark)};\n    {on}: {text_on(dark)};")
            if var == "--nexus-primary":
                swaps.append(f"    --kei-accent: {dark};")
    out = [f"{d} {{\n" + "\n".join(swaps) + "\n}"] if swaps else []
    if cfg["texture"] in METALS:
        out.append(f"""{", ".join(f"{d} body {x.strip()}" for x in _BTN_SOFT.split(","))} {{
    background: {_BRUSH_LIGHT}, linear-gradient(180deg, #3a414b 0%, #2b3138 47%, #22272e 53%, #2b3138 100%) !important;
    color: #e6edf3 !important;
    border-color: #4b5563 !important;
}}""")
    out.append(f"""/* The catalogue card stays black on white, as printed. */
html body .main .kei-ficha-box .kei-ficha, html body .main .kei-ficha-box .kei-ficha *,
html[data-kei-theme] body .main .kei-ficha-box .kei-ficha, html[data-kei-theme] body .main .kei-ficha-box .kei-ficha * {{
    color: #000 !important;
    text-shadow: none !important;
}}
html body .main .kei-ficha-box .kei-ficha, html[data-kei-theme] body .main .kei-ficha-box .kei-ficha {{ background: #fff !important; }}
{d} body .main .kei-ficha-show {{
    background: rgba(255, 255, 255, .08) !important;
    color: var(--kei-text) !important;
    border-color: rgba(255, 255, 255, .25) !important;
    text-shadow: none !important;
}}
/* Previous / back to results / next of a record. */
{d} body .nav_results, {d} body .nav_results .l_Results, {d} body .nav_results .pg_menu,
{d} body .nav_results .pg_menu li, {d} body .nav_results .pg_menu li a {{
    background: transparent !important;
    color: var(--kei-text) !important;
    border-color: rgba(255, 255, 255, .14) !important;
    text-shadow: none !important;
}}
{d} body .nav_results .pg_menu li a:hover {{ background: rgba(255, 255, 255, .08) !important; }}
{d} body .nav_results .pg_menu li:not(:has(a)) {{ color: var(--kei-muted) !important; }}""")
    return "\n".join(out)


def _painted_buttons(cfg: dict, main: str, soft: str) -> str:
    """The accent and the second colour in their own texture and opacity:
    the accent on the main buttons, the second colour on the secondary
    ones. Nothing while both are "auto" at full opacity (the look before)."""
    out = []
    p = cfg["paint"]["accent"]
    if p["texture"] != "auto" or p["opacity"] < 100:
        texture = p["texture"] if p["texture"] != "auto" else ("metal" if cfg["texture"] in METALS else "smooth")
        out.append(_paint_rule(main, _paint(texture, "--kei-accent-rgb", p["opacity"], True), ""))
    p = cfg["paint"]["accent2"]
    if p["texture"] != "auto":
        out.append(_paint_rule(soft, _paint(p["texture"], "--kei-accent2-rgb", p["opacity"], True),
                               "var(--nexus-on-secondary)"))
        out.append(f"{soft} {{ border-color: var(--nexus-secondary) !important; }}")
    return ("\n/* Each colour in its own texture and opacity. */\n" + "\n".join(out)) if out else ""


def _canvas_css(cfg: dict) -> str:
    """No wallpaper: a page with some depth instead of a flat white sheet,
    so the blocks (white ones above all) stand out and glass has something
    to blur. The library's page colour, or a soft grey, under two faint
    glows of the accent colours; the blocks get a layered shadow."""
    light = luminance(cfg["surface"]) >= 0.30
    base = cfg["page"] or ("#e8ecf2" if light else "#1b2230")
    shadow = ("0 1px 2px rgba(15, 23, 42, .06), 0 12px 32px -10px rgba(15, 23, 42, .22)" if light
              else "0 1px 2px rgba(0, 0, 0, .25), 0 12px 32px -10px rgba(0, 0, 0, .55)")
    # The second colour on "auto" only tints the glow at the bottom right:
    # its opacity there scales that glow.
    p2 = cfg["paint"]["accent2"]
    glow2 = f"{.14 * p2['opacity'] / 100:.2f}" if p2["texture"] == "auto" else ".14"
    glows = ("radial-gradient(1200px 600px at 0% 0%, rgba(var(--kei-accent-rgb), .16), transparent 60%), "
             f"radial-gradient(1000px 600px at 100% 100%, rgba(var(--kei-accent2-rgb), {glow2}), transparent 60%)")
    pp = cfg["paint"]["page"]
    if pp["texture"] != "auto" or pp["opacity"] < 100:
        # The page colour in its own texture; under it the browser's white
        # (or black in the dark theme), so a lower opacity makes it paler.
        base = _paint(pp["texture"], "--kei-page-rgb", pp["opacity"], False)["bg"] + ", #ffffff"
        lines = [f":root {{ --kei-page-rgb: {_rgb(cfg['page'] or ('#e8ecf2' if light else '#1b2230'))}; }}"]
    else:
        lines = []
    lines += [f"""html body {{
    background: {glows}, {base} !important;
    background-attachment: fixed !important;
}}
html[data-kei-theme="dark"] body {{
    background: {glows.replace(".16", ".10").replace(".14", ".08")}, #0d1117 !important;
}}"""]
    if cfg["texture"] in ("frosted", "smooth", "gradient"):
        lines.append(f""":root {{ --koha-card-shadow: {shadow}, inset 0 1px 0 rgba(255, 255, 255, {".55" if light else ".06"}); }}""")
    return "\n".join(lines)


def _links_css(nav: str) -> str:
    """The quick access buttons of the nav with id nav: one full-width
    button per line, like the buttons of the home page block, or two
    columns (kei-layout-grid2) that stack the icon over the text on a phone
    and fall back to one column on the narrowest screens. The look is the
    nav's class: kei-links-solid, -gradient, -glass or -metal."""
    n = f"html body {nav}"
    dark = f'html[data-kei-theme="dark"] body {nav}'
    return f"""{nav} {{
    display: flex;
    flex-direction: column;
    gap: .6rem;
    width: 100%;
    margin: 0 0 1.25rem;
}}
{n}.kei-layout-grid2 {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: .6rem;
}}
{n} a.kei-link {{
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    box-sizing: border-box;
    min-height: 48px;
    gap: .75rem;
    padding: .8rem 1.1rem;
    text-align: center;
    overflow-wrap: anywhere;
    border-radius: var(--kei-r-btn);
    font-weight: 600;
    text-decoration: none !important;
    transition: transform .18s ease, box-shadow .18s ease, filter .18s ease, border-color .18s ease;
}}
{n} a.kei-link:hover, {n} a.kei-link:focus-visible {{ transform: translateY(-2px); filter: brightness(1.05); }}
{n} .kei-link-icon {{ font-size: 1.35rem; line-height: 1; min-width: 1.6rem; text-align: center; }}
{n}.kei-links-solid a.kei-link {{ background: var(--nexus-primary); color: var(--nexus-on-primary) !important;
    box-shadow: 0 4px 14px rgba(var(--kei-accent-rgb), .30); }}
{n}.kei-links-gradient a.kei-link {{ color: #fff !important;
    background: linear-gradient(135deg, var(--nexus-primary), var(--nexus-secondary));
    box-shadow: 0 6px 18px rgba(var(--kei-accent2-rgb), .28); }}
{n}.kei-links-glass a.kei-link {{ color: var(--kei-text) !important;
    background: rgba(var(--kei-surface-rgb), .55);
    -webkit-backdrop-filter: blur(10px) saturate(150%);
    backdrop-filter: blur(10px) saturate(150%);
    border: 1px solid rgba(255, 255, 255, .45);
    box-shadow: 0 8px 24px rgba(0, 0, 0, .12), inset 0 1px 0 rgba(255, 255, 255, .35); }}
{n}.kei-links-glass a.kei-link:hover {{ border-color: var(--nexus-primary); }}
/* Brushed metal: fine horizontal grain over a satin silver gradient, a
   bevel of light and shade, and a specular band that sweeps across on hover. */
{n}.kei-links-metal a.kei-link {{ color: #1f2933 !important;
    background: repeating-linear-gradient(180deg, rgba(255, 255, 255, .10) 0 1px, rgba(0, 0, 0, .03) 1px 2px,
            transparent 2px 3px),
        linear-gradient(180deg, #f6f7f9 0%, #e1e5ea 42%, #cbd0d7 58%, #e7eaee 100%);
    border: 1px solid #a9afb7;
    border-top-color: #d8dce1;
    border-bottom-color: #8e949c;
    text-shadow: 0 1px 0 rgba(255, 255, 255, .75);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, .9), inset 0 -1px 0 rgba(0, 0, 0, .14),
        0 3px 8px rgba(15, 23, 42, .18); }}
{n}.kei-links-metal a.kei-link::after {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(105deg, transparent 35%, rgba(255, 255, 255, .7) 50%, transparent 65%);
    transform: translateX(-120%);
    transition: transform .6s ease;
}}
{n}.kei-links-metal a.kei-link:hover::after, {n}.kei-links-metal a.kei-link:focus-visible::after {{
    transform: translateX(120%); }}
{n}.kei-links-metal a.kei-link:hover, {n}.kei-links-metal a.kei-link:focus-visible {{
    border-color: var(--nexus-primary);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, .9), inset 0 -1px 0 rgba(0, 0, 0, .14),
        0 8px 18px rgba(var(--kei-accent-rgb), .28); }}
{n}.kei-links-metal .kei-link-icon {{ color: var(--nexus-primary); text-shadow: none; }}
{dark}.kei-links-metal a.kei-link {{ color: #eef1f4 !important;
    background: repeating-linear-gradient(180deg, rgba(255, 255, 255, .05) 0 1px, rgba(0, 0, 0, .06) 1px 2px,
            transparent 2px 3px),
        linear-gradient(180deg, #5b626b 0%, #434951 45%, #33383f 58%, #4a5058 100%);
    border-color: #2a2e34;
    border-top-color: #6c737c;
    text-shadow: 0 -1px 0 rgba(0, 0, 0, .5); }}
{dark}.kei-links-metal a.kei-link::after {{
    background: linear-gradient(105deg, transparent 35%, rgba(255, 255, 255, .22) 50%, transparent 65%); }}
@media (max-width: 576px) {{
    {n}.kei-layout-grid2 a.kei-link {{ flex-direction: column; gap: .35rem; min-height: 64px;
        padding: .7rem .5rem; font-size: .92rem; }}
}}
@media (max-width: 340px) {{ {n}.kei-layout-grid2 {{ grid-template-columns: 1fr; }} }}
@media (prefers-reduced-motion: reduce) {{
    {n} a.kei-link, {n}.kei-links-metal a.kei-link::after {{ transition: none; }}
}}"""


def staff_links_css(cfg: dict) -> str:
    """The staff home page's quick access buttons: the same rules, with the
    staff interface's colours set on the nav itself, so they work with or
    without the staff colour theme."""
    st = normalize(cfg)["staff"]
    accent, accent2, surface = st["accent"], st["accent2"], st["surface"]
    return f"""html body #kei-staff-links {{
    --nexus-primary: {accent};
    --nexus-secondary: {accent2};
    --nexus-on-primary: {text_on(accent)};
    --kei-accent-rgb: {_rgb(accent)};
    --kei-accent2-rgb: {_rgb(accent2)};
    --kei-surface-rgb: {_rgb(mix(surface, accent, .08))};
    --kei-text: {text_on(surface)};
    --kei-r-btn: 10px;
    margin-top: .5rem;
}}
{_links_css("#kei-staff-links")}
"""


def _carousel_css(car: dict) -> str:
    hover = {
        "zoom": ".kei-card:hover .kei-face img, .kei-card:focus .kei-face img { transform: scale(1.06); }",
        "lift": ".kei-card:hover, .kei-card:focus { transform: translateY(-6px); "
                "box-shadow: 0 10px 16px -6px rgba(0, 0, 0, .32); }",
        "tilt": ".kei-card { transform-style: preserve-3d; will-change: transform; }",
        "none": "",
    }[car["hover"]]
    return f""".kei-carousel {{ position: relative; margin: 0 0 1.5rem; }}
.kei-carousel h2 {{ font-size: 1.35rem; margin: 0 0 .75rem; }}
.kei-track {{
    display: flex;
    gap: 1rem;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scroll-behavior: smooth;
    padding: .75rem .4rem 1.25rem;
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
    box-shadow: 0 4px 10px -3px rgba(0, 0, 0, .22);
    transition: transform .25s ease, box-shadow .25s ease;
}}
.kei-face {{ position: absolute; inset: 0; overflow: hidden; border-radius: inherit; }}
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
    height: 300px;
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
    /* Short shadows: they stay inside the stage, which clips (Paulo, 2026-10-31). */
    box-shadow: 0 8px 12px -4px rgba(0, 0, 0, .35);
}}
.kei-mode-coverflow .kei-card::after {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(90deg, rgba(0, 0, 0, var(--kei-shade-l, 0)), rgba(0, 0, 0, var(--kei-shade-r, 0)));
    transition: background .6s ease;
}}
.kei-mode-coverflow .kei-card.kei-center {{ box-shadow: 0 10px 16px -4px rgba(0, 0, 0, .45); }}
.kei-mode-coverflow .kei-card.kei-center .kei-card-info {{ opacity: 1; transform: none; }}
.kei-mode-coverflow .kei-nav {{ top: 42%; }}
.kei-mode-coverflow .kei-prev {{ left: .4rem; }}
.kei-mode-coverflow .kei-next {{ right: .4rem; }}
{_CAROUSEL_STYLES_CSS}
@media (prefers-reduced-motion: reduce) {{
    .kei-card, .kei-card img, .kei-card-info, .kei-track {{ transition: none; scroll-behavior: auto; }}
    .kei-mode-coverflow .kei-card {{ transition: none; }}
    .kei-belt {{ animation: none; }}
    .kei-mode-ribbon .kei-track {{ overflow-x: auto; }}
}}"""


# The styles added in 1.5.150 (Paulo, 2026-10-31: "more carousel styles, be
# creative"), the drawn cover of a title with none and the reflections.
# The 3D ones (ring, wall, fan, spotlight) are placed by the script frame by
# frame (spin()); these rules only give them their stage and their looks.
_CAROUSEL_STYLES_CSS = """/* A title with no cover: a cover drawn in the accent colours. */
.kei-blank {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: .45rem;
    padding: 14% 12% 14% 18%;
    text-align: center;
    color: #fff;
    font-family: Georgia, "Times New Roman", serif;
    background: linear-gradient(180deg, transparent 38%, rgba(0, 0, 0, .18) 38%, rgba(0, 0, 0, .18) 62%, transparent 62%),
        linear-gradient(160deg, var(--kei-accent), rgb(var(--kei-accent2-rgb)));
    text-shadow: 0 1px 2px rgba(0, 0, 0, .45);
}
.kei-blank::before {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    left: 9%;
    width: 2px;
    background: rgba(255, 255, 255, .35);
}
.kei-blank b { font-size: .92rem; line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 5;
    -webkit-box-orient: vertical; overflow: hidden; }
.kei-blank i { font-style: normal; font-size: .72rem; opacity: .9; }
.kei-blank small { position: absolute; left: 0; right: 0; bottom: 6%; font-size: .58rem; letter-spacing: .14em;
    text-transform: uppercase; opacity: .75; font-family: inherit; }
/* Reflections: the cover again, upside down, fading into the page. */
.kei-reflect .kei-card { overflow: visible; }
.kei-mirror {
    position: absolute;
    left: 0;
    right: 0;
    top: calc(100% + 3px);
    height: 38%;
    overflow: hidden;
    pointer-events: none;
    border-radius: inherit;
    -webkit-mask-image: linear-gradient(rgba(0, 0, 0, .4), transparent 90%);
    mask-image: linear-gradient(rgba(0, 0, 0, .4), transparent 90%);
}
.kei-mirror > img, .kei-mirror > .kei-blank { position: absolute; left: 0; top: 0; width: 100%;
    height: calc(100% / .38); transform: scaleY(-1); }
.kei-reflect .kei-track { padding-bottom: 5.8rem; }
.kei-reflect.kei-mode-coverflow .kei-stage { height: 370px; }
/* Every stage: the cards stand on it, the script moves them. */
.kei-stage { touch-action: pan-y; user-select: none; -webkit-user-select: none; }
.kei-stage .kei-card.kei-center .kei-card-info { opacity: 1; transform: none; }
/* 3D ring: the covers go round, the far ones small and high (a carousel seen from above). */
.kei-mode-ring .kei-stage { position: relative; height: 330px; perspective: 1000px; perspective-origin: 50% 0;
    overflow: hidden; }
.kei-reflect.kei-mode-ring .kei-stage { height: 380px; }
.kei-mode-ring .kei-card { position: absolute; left: 50%; top: 60px; width: 140px; margin-left: -70px;
    box-shadow: 0 8px 14px -6px rgba(0, 0, 0, .4); }
.kei-mode-ring .kei-nav, .kei-mode-wall .kei-nav, .kei-mode-fan .kei-nav { top: 42%; }
.kei-mode-ring .kei-prev, .kei-mode-wall .kei-prev, .kei-mode-fan .kei-prev, .kei-mode-spotlight .kei-prev { left: .4rem; }
.kei-mode-ring .kei-next, .kei-mode-wall .kei-next, .kei-mode-fan .kei-next, .kei-mode-spotlight .kei-next { right: .4rem; }
/* Curved wall: the covers on the inside of a curve, the title under each one. */
.kei-mode-wall .kei-stage { position: relative; height: 360px; perspective: 900px; overflow: hidden; }
.kei-reflect.kei-mode-wall .kei-stage { height: 420px; }
.kei-mode-wall .kei-card { position: absolute; left: 50%; top: 34px; width: 150px; margin-left: -75px;
    box-shadow: 0 8px 14px -6px rgba(0, 0, 0, .35); }
.kei-caption {
    position: absolute;
    left: -6px;
    right: -6px;
    top: calc(100% + 8px);
    font-size: .8rem;
    line-height: 1.2;
    text-align: center;
    color: var(--kei-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.kei-mode-wall .kei-card.kei-center .kei-caption { font-weight: 600; }
/* Bookshelf: the covers stand on a wooden board, with a spine and the pages' edge. */
.kei-mode-shelf .kei-track {
    align-items: flex-end;
    gap: .9rem;
    padding: 1.5rem 1.4rem 30px;
    background: linear-gradient(180deg, transparent calc(100% - 30px), #9a6a3f calc(100% - 30px),
        #7a4e2b calc(100% - 12px), #4a2e18 calc(100% - 12px), rgba(0, 0, 0, .18) calc(100% - 4px), transparent 100%);
    border-radius: calc(var(--kei-r-block) * .5);
}
.kei-mode-shelf .kei-card {
    width: 128px;
    border-radius: 2px 5px 5px 2px;
    transform-origin: bottom center;
    box-shadow: 3px 0 0 #f1ead9, 5px 0 0 #cdbfa3, 8px 2px 10px rgba(0, 0, 0, .4);
}
.kei-mode-shelf .kei-card:nth-child(3n+2) { width: 138px; }
.kei-mode-shelf .kei-card:nth-child(4n+3) { width: 118px; }
.kei-mode-shelf .kei-face::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(90deg, rgba(0, 0, 0, .4), rgba(255, 255, 255, .2) 4%, transparent 10%);
}
.kei-mode-shelf .kei-card:hover, .kei-mode-shelf .kei-card:focus { transform: translateY(-12px) rotate(-1.5deg); }
.kei-mode-shelf .kei-nav { top: 40%; }
/* Fan of cards: held in a hand, the one in front in the middle. */
.kei-mode-fan .kei-stage { position: relative; height: 380px; overflow: hidden; }
.kei-mode-fan .kei-card { position: absolute; left: 50%; top: 30px; width: 160px; margin-left: -80px;
    transform-origin: 50% 135%; box-shadow: 0 6px 16px -4px rgba(0, 0, 0, .45); }
/* Spotlight: one title at a time, large, over its own cover blurred. */
.kei-mode-spotlight .kei-stage { position: relative; height: 310px; overflow: hidden;
    border-radius: var(--kei-r-block); background: rgba(var(--kei-surface-rgb), .55); }
.kei-mode-spotlight .kei-card {
    position: absolute;
    inset: 0;
    width: auto;
    aspect-ratio: auto;
    display: flex;
    align-items: center;
    gap: 1.6rem;
    padding: 24px 64px;
    border-radius: 0;
    background: none;
    box-shadow: none;
    isolation: isolate;
    text-decoration: none;
}
.kei-backdrop { position: absolute; inset: -40px; z-index: -1; overflow: hidden; opacity: .5;
    filter: blur(30px) saturate(1.4); }
.kei-backdrop img { width: 100%; height: 100%; object-fit: cover; }
.kei-mode-spotlight .kei-face { position: relative; flex: 0 0 170px; height: 255px;
    border-radius: calc(var(--kei-r-block) * .6); box-shadow: 0 12px 24px -8px rgba(0, 0, 0, .55); }
.kei-mode-spotlight .kei-card-info { position: static; opacity: 1; transform: none; background: none; padding: 0;
    color: var(--kei-text); font-size: 1rem; line-height: 1.35; max-width: 34rem; }
.kei-mode-spotlight .kei-card-info strong { font-size: 1.45rem; line-height: 1.2; margin-bottom: .35rem; }
.kei-mode-spotlight .kei-card:hover, .kei-mode-spotlight .kei-card:focus { box-shadow: none; }
.kei-dots { display: flex; justify-content: center; gap: .4rem; margin-top: .6rem; }
.kei-dots button { width: .6rem; height: .6rem; padding: 0; border-radius: 50%; border: 1px solid var(--kei-edge);
    background: rgba(var(--kei-surface-rgb), .9); cursor: pointer; }
.kei-dots button[aria-current="true"] { background: var(--kei-accent); border-color: var(--kei-accent); }
@media (max-width: 560px) {
    .kei-mode-ring .kei-card { width: 110px; margin-left: -55px; }
    .kei-mode-wall .kei-card { width: 120px; margin-left: -60px; }
    .kei-mode-wall .kei-stage { height: 300px; }
    .kei-reflect.kei-mode-wall .kei-stage { height: 340px; }
    .kei-mode-wall .kei-card:not(.kei-center) .kei-caption { visibility: hidden; }
    .kei-mode-fan .kei-card { width: 130px; margin-left: -65px; }
    .kei-mode-spotlight .kei-stage { height: 380px; }
    .kei-mode-spotlight .kei-card { flex-direction: column; justify-content: center; gap: .8rem; padding: 16px 48px;
        text-align: center; }
    .kei-mode-spotlight .kei-face { flex: 0 0 auto; width: 130px; height: 195px; }
    .kei-mode-spotlight .kei-card-info strong { font-size: 1.1rem; }
}
/* Endless ribbon: the covers glide by without stopping; a pointer or the keyboard holds them. */
.kei-mode-ribbon .kei-track { overflow: hidden; scroll-snap-type: none; }
.kei-mode-ribbon.kei-still .kei-track { overflow-x: auto; }
.kei-belt { display: flex; width: max-content; animation: kei-ribbon var(--kei-ribbon-time, 60s) linear infinite; }
.kei-still .kei-belt { animation: none; }
.kei-belt .kei-card { margin-right: 1rem; }
.kei-mode-ribbon:hover .kei-belt, .kei-mode-ribbon:focus-within .kei-belt { animation-play-state: paused; }
@keyframes kei-ribbon { to { transform: translateX(-50%); } }"""


def css_block(cfg: dict) -> str:
    return "\n".join([CSS_BEGIN, data_line(cfg), css_body(cfg).rstrip("\n"), CSS_END]) + "\n"


# ----------------------------------------------------------------------
# The staff interface (IntranetUserCSS)
# ----------------------------------------------------------------------
_STAFF_PAD = {"compact": ".2rem .45rem", "comfortable": ".65rem .85rem"}


def staff_css_body(cfg: dict) -> str:
    """The staff interface's own look, from cfg["staff"] only: one hue for
    the top bar and the quick search bar under it, the home page modules as
    cards, the news column on a tinted surface, the buttons and links in the
    palette; its own material (the OPAC's textures, blur, opacity and
    corner rounding, _staff_material_css), type size, contrast and table
    density. Only CSS: no carousel, button or other OPAC widget ever
    reaches the staff pages.

    Koha's own rules are beaten by specificity (html body + the same ids);
    !important only where Koha or Bootstrap use it themselves (.bg-dark) or
    where a library's own inline <style> (news buttons) would win."""
    cfg = normalize(cfg)
    st = cfg["staff"]
    accent, accent2, surface = st["accent"], st["accent2"], st["surface"]
    light = luminance(surface) >= 0.30
    # The top bar has its own colour (staff_bar): the accent only marks the
    # main buttons, the module icons, the active tab and the focus ring
    # (Paulo, 2026-10-31: the accent dyed the letters, the buttons and the
    # bar). The quick search bar under it: the bar's hue, a step darker.
    top = staff_bar(st)
    top_dark = luminance(top) < .18
    on_bar = text_on(top)
    bar = mix(top, "#000000", .22 if top_dark else .08)
    on_rgb = _rgb(on_bar)
    menu = mix(top, "#000000", .55) if top_dark else "#212529"
    # Only a chosen bar colour is written as a setting (css_values reads it
    # back); the automatic one follows the accent.
    chosen = f"    --nexus-staff-bar-colour: {st['bar']};\n" if st["bar"] else ""
    page = staff_page(st)
    card = surface
    text, muted = ("#1f2933", "#5b6875") if light else ("#e6edf3", "#9da7b3")
    # Letters are automatic: dark or light from the background they sit on,
    # never the accent (Paulo, 2026-10-31: "a cor de destaque afeta as
    # letras"). Headings are the text colour, a step stronger; only links
    # carry a hue (link_base), darkened or lightened until they read well.
    ink = "#111827" if light else "#f0f3f6"
    hue = link_base(accent, accent2)
    link = mix(hue, "#000000", .12) if light else mix(hue, "#ffffff", .35)
    link = readable(link, card, 5.5)
    out = [f""":root {{
    --nexus-staff-primary: {accent};
    --nexus-staff-secondary: {accent2};
    --nexus-staff-on-primary: {text_on(accent)};
    --nexus-staff-on-secondary: {text_on(accent2)};
    --nexus-staff-bar: {bar};
    --nexus-staff-bar-rgb: {_rgb(bar)};
    --nexus-staff-topbar: {top};
    --nexus-staff-topbar-rgb: {_rgb(top)};
    --nexus-staff-topbar-end: {mix(top, "#000000", .12)};
    --nexus-staff-topbar-end-rgb: {_rgb(mix(top, "#000000", .12))};
    --nexus-staff-on-topbar: {on_bar};
    --nexus-staff-on-topbar-rgb: {on_rgb};
    --nexus-staff-menu: {menu};
{chosen}    --nexus-staff-primary-rgb: {_rgb(accent)};
    --nexus-staff-secondary-rgb: {_rgb(accent2)};
    --nexus-staff-page: {page};
    --nexus-staff-card: {card};
    --nexus-staff-text: {text};
    --nexus-staff-muted: {muted};
    --nexus-staff-ink: {ink};
    --nexus-staff-link: {link};
    --nexus-staff-edge: rgba({_rgb(accent)}, .16);
    --nexus-staff-shadow: 0 1px 2px rgba(15, 23, 42, .06), 0 6px 18px -6px rgba(15, 23, 42, .16);
    --nexus-staff-shadow-hi: 0 2px 4px rgba(15, 23, 42, .08), 0 14px 28px -8px rgba({_rgb(accent)}, .35);
    --nexus-staff-radius: {st['radius_block']}px;
    --nexus-staff-r-input: {st['radius_input']}px;
    --nexus-staff-r-btn: {st['radius_button']}px;
    --nexus-staff-surface-rgb: {_rgb(surface)};
    --nexus-staff-surface-a: {st['opacity'] / 100:.2f};
    /* The module tiles and other buttons-as-cards: the block background at
       the opacity slider, a touch more solid so their text stays crisp. */
    --nexus-staff-tile: rgba(var(--nexus-staff-surface-rgb), calc(var(--nexus-staff-surface-a) * .5 + .5));
    --nexus-staff-blur: {st['blur']}px;
    --nexus-staff-card-pad: {st['card_padding']}px;
}}
html {{ font-size: {st['font']}%; }}
html body {{ background-color: var(--nexus-staff-page); color: var(--nexus-staff-text); }}
html body #container-main a:not(.btn):not(.icon_general):not(.btn-acesso):not(.dropdown-item),
html body .main a:not(.btn):not(.dropdown-item):not(.nav-link),
html body #breadcrumbs a {{ color: var(--nexus-staff-link); }}

/* Top bar: its own colour (not the accent), a gentle fall to a darker shade of it. */
html body nav.navbar.bg-dark, html body nav.navbar.navbar-dark {{
    background: linear-gradient(90deg, var(--nexus-staff-topbar), var(--nexus-staff-topbar-end)) !important;
    border: 0;
    box-shadow: 0 1px 0 rgba(255, 255, 255, .08) inset;
}}
html body nav.navbar #header .nav-link, html body nav.navbar #logged-in-info-full,
html body nav.navbar .navbar-text, html body nav.navbar .navbar-nav > li > a,
html body nav.navbar #user-menu .nav-link, html body nav.navbar .dropdown-toggle {{ color: var(--nexus-staff-on-topbar); }}
html body nav.navbar #header .nav-link:hover, html body nav.navbar #header .nav-link:focus {{
    background-color: rgba({on_rgb}, .14);
    border-radius: 8px;
}}
html body nav.navbar #catalog-search-link {{ border-right-color: rgba({on_rgb}, .25); }}
html body nav.navbar .dropdown-menu-dark {{
    --bs-dropdown-bg: var(--nexus-staff-menu);
    --bs-dropdown-link-hover-bg: rgba(255, 255, 255, .12);
    --bs-dropdown-link-active-bg: var(--nexus-staff-primary);
    border: 0;
    border-radius: 10px;
    box-shadow: 0 12px 28px rgba(0, 0, 0, .3);
}}

/* Quick search bar: the same hue, darker; the field and its button as one piece. */
html body #header_search, html body #header_search ul, html body #header_search .form-title,
html body #header_search .nav-tabs > li > a, html body #header_search .nav-tabs > li > a:hover,
html body #header_search .nav-tabs > li > a:focus {{
    background-color: var(--nexus-staff-bar);
    border-color: var(--nexus-staff-bar);
}}
html body #header_search {{ padding-top: .45rem; padding-bottom: .45rem; gap: .5rem; }}
html body #header_search form {{ align-items: center; }}
html body #header_search .form-title label {{ color: var(--nexus-staff-on-topbar); letter-spacing: .01em; }}
html body #header_search .form-content {{
    background-color: var(--nexus-staff-card);
    border-radius: var(--nexus-staff-r-input) 0 0 var(--nexus-staff-r-input);
    margin-left: 0;
    padding-left: .35rem;
    min-height: 2.25rem;
    align-items: center;
    box-shadow: inset 0 1px 2px rgba(15, 23, 42, .12);
}}
html body #header_search .form-content input[type="text"] {{ color: var(--nexus-staff-text); height: 2.25rem; }}
html body #header_search input[type="submit"], html body #header_search button[type="submit"] {{
    height: 2.25rem;
    margin-left: 0;
    padding: 0 1rem;
    border-radius: 0 var(--nexus-staff-r-input) var(--nexus-staff-r-input) 0;
    background-color: var(--nexus-staff-secondary);
    color: var(--nexus-staff-on-secondary);
    transition: filter .15s ease;
}}
html body #header_search input[type="submit"]:hover,
html body #header_search button[type="submit"]:hover {{ background-color: var(--nexus-staff-secondary); filter: brightness(1.1); }}
html body #header_search .nav-tabs > li > a {{
    color: rgba({on_rgb}, .82);
    border-radius: 8px;
    margin: 0 .1rem;
    padding: .15rem .4rem;
    transition: background-color .15s ease, color .15s ease;
}}
html body #header_search .nav-tabs > li > a:hover, html body #header_search .nav-tabs > li > a:focus {{
    background-color: rgba({on_rgb}, .12);
    border-color: transparent;
    color: var(--nexus-staff-on-topbar);
}}
html body #header_search .nav-tabs > li > a.active, html body #header_search .nav-tabs > li > a.active:hover {{
    background-color: rgba({on_rgb}, .16);
    border-color: transparent;
    border-bottom: 2px solid var(--nexus-staff-primary);
    color: var(--nexus-staff-on-topbar);
}}
html body #header_search .form-extra-content {{ border-color: var(--nexus-staff-bar); border-radius: 0 0 10px 10px; }}

/* Home page modules: cards with an icon tile, a lift on hover. */
html body ul.biglinks-list li {{ margin-bottom: .85rem; }}
html body ul.biglinks-list li a.icon_general {{
    height: auto;
    min-height: 56px;
    gap: .8rem;
    padding: .7rem 1rem;
    background-color: var(--nexus-staff-tile);
    color: var(--nexus-staff-text);
    font-weight: 600;
    border: 1px solid var(--nexus-staff-edge);
    border-radius: var(--nexus-staff-radius);
    box-shadow: var(--nexus-staff-shadow);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}}
html body ul.biglinks-list li a.icon_general > .fa-fw, html body ul.biglinks-list li a.icon_general > .fa-stack {{
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.4rem;
    height: 2.4rem;
    margin: 0;
    font-size: 1.15rem;
    line-height: 1;
    border-radius: 10px;
    color: var(--nexus-staff-primary);
    background-color: rgba(var(--nexus-staff-primary-rgb), .12);
}}
/* Koha draws the two search modules with two stacked icons (a book or a list
   under a magnifier); in a small tile they collide, so only the magnifier stays. */
html body ul.biglinks-list li a.icon_general > .fa-stack .fa-stack-1x {{ display: none; }}
html body ul.biglinks-list li a.icon_general > .fa-stack .fa-stack-2x {{
    position: static;
    width: auto;
    margin: 0;
    font-size: 1.15rem;
    line-height: 1;
    color: inherit;
}}
html body ul.biglinks-list li a.icon_general:hover, html body ul.biglinks-list li a.icon_general:focus-visible {{
    background-color: var(--nexus-staff-tile);
    color: var(--nexus-staff-ink);
    border-color: var(--nexus-staff-primary);
    box-shadow: var(--nexus-staff-shadow-hi);
    transform: translateY(-2px);
}}
html body ul.biglinks-list li a.icon_general:hover > .fa-fw, html body ul.biglinks-list li a.icon_general:hover > .fa-stack {{
    background-color: var(--nexus-staff-primary);
    color: var(--nexus-staff-on-primary);
}}
html body #koha_version a {{ color: var(--nexus-staff-muted); }}
/* A library's own home page buttons that copy the module tiles (Paulo's
   .btn-koha-clone grid in an HTML customization, grey #DCDCDC with
   !important): they take the tiles' look, so they follow the colours, the
   opacity and the dark mode instead of staying grey. */
html body .grid-acesso-koha .btn-koha-clone {{
    background-color: var(--nexus-staff-tile) !important;
    color: var(--nexus-staff-text) !important;
    border: 1px solid var(--nexus-staff-edge) !important;
    border-radius: var(--nexus-staff-radius) !important;
    box-shadow: var(--nexus-staff-shadow) !important;
}}
html body .grid-acesso-koha .btn-koha-clone:hover, html body .grid-acesso-koha .btn-koha-clone:focus-visible {{
    background-color: var(--nexus-staff-tile) !important;
    color: var(--nexus-staff-ink) !important;
    border-color: var(--nexus-staff-primary) !important;
    box-shadow: var(--nexus-staff-shadow-hi) !important;
}}

/* News column: a tinted card, clear headings, an airy list. */
html body #area-news {{
    background-color: {mix(surface, accent, .06)};
    border: 1px solid var(--nexus-staff-edge);
    border-radius: var(--nexus-staff-radius);
    box-shadow: var(--nexus-staff-shadow);
    padding: .9rem 1rem;
}}
html body #area-news h3 {{
    opacity: 1;
    padding: 0 0 .5rem;
    color: var(--nexus-staff-ink);
    font-size: .82rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    border-bottom: 2px solid var(--nexus-staff-primary);
}}
html body #area-news .newsitem {{
    opacity: 1;
    margin: .75rem 0 0;
    padding: .75rem .85rem;
    background-color: var(--nexus-staff-card);
    border: 0;
    border-radius: calc(var(--nexus-staff-radius) * .8);
    box-shadow: 0 1px 2px rgba(15, 23, 42, .06);
    line-height: 1.5;
}}
html body #area-news .newsitem h4 {{ color: var(--nexus-staff-text); font-size: 1rem; font-weight: 700; margin-bottom: .4rem; }}
html body #area-news .newsitem ul {{ padding-left: 1.1rem; margin: .4rem 0; }}
html body #area-news .newsitem li {{ margin: .2rem 0; }}
html body #area-news .newsfooter {{ color: var(--nexus-staff-muted); font-size: .82rem; margin: .5rem 0 0; }}
html body #area-news .newsitem .btn-acesso {{
    display: flex !important;
    align-items: center;
    gap: .5rem;
    width: 100% !important;
    height: auto !important;
    min-height: 44px;
    margin: 0 0 .5rem !important;
    padding: .55rem .8rem !important;
    font-size: .95rem !important;
    font-weight: 600;
    background-color: var(--nexus-staff-card) !important;
    color: var(--nexus-staff-text) !important;
    border: 1px solid var(--nexus-staff-edge) !important;
    border-radius: var(--nexus-staff-r-btn) !important;
    text-decoration: none !important;
}}
html body #area-news .newsitem .btn-acesso:hover, html body #area-news .newsitem .btn-acesso:focus-visible {{
    background-color: var(--nexus-staff-primary) !important;
    border-color: var(--nexus-staff-primary) !important;
    color: var(--nexus-staff-on-primary) !important;
}}

/* Buttons, tabs, focus. */
html body .btn-primary, html body input[type="submit"].btn-primary {{
    background-color: var(--nexus-staff-primary);
    border-color: var(--nexus-staff-primary);
    color: var(--nexus-staff-on-primary);
}}
html body .btn-primary:hover, html body .btn-primary:focus {{
    background-color: {mix(accent, "#000000", .12)};
    border-color: {mix(accent, "#000000", .12)};
    color: var(--nexus-staff-on-primary);
}}
html body .btn-default:hover, html body .btn-default:focus {{ border-color: var(--nexus-staff-primary); }}
html body .btn, html body input[type="submit"], html body input[type="button"], html body input[type="reset"],
html body button.btn {{ border-radius: var(--nexus-staff-r-btn); }}
html body .main .form-control, html body .main .form-select, html body .main input[type="text"],
html body .main input[type="search"], html body .main input[type="password"], html body .main input[type="email"],
html body .main input[type="number"], html body .main input[type="tel"], html body .main select,
html body .main textarea, html body #area-news textarea {{ border-radius: var(--nexus-staff-r-input); }}
html body .nav-tabs .nav-link.active, html body .ui-tabs .ui-tabs-nav li.ui-tabs-active {{
    border-top: 3px solid var(--nexus-staff-primary);
}}
html body a:focus-visible, html body .btn:focus-visible, html body input:focus, html body select:focus,
html body textarea:focus {{
    outline: 3px solid rgba(var(--nexus-staff-primary-rgb), .45);
    outline-offset: 1px;
}}
@media (prefers-reduced-motion: reduce) {{
    html body ul.biglinks-list li a.icon_general {{ transition: none; }}
    html body ul.biglinks-list li a.icon_general:hover {{ transform: none; }}
}}"""]
    pad = _STAFF_PAD.get(st["density"])
    if pad:
        out.append(f"""html body table td, html body table th, html body .table > :not(caption) > * > * {{
    padding: {pad} !important;
}}""")
        if st["density"] == "compact":
            out.append("html body table { line-height: 1.25; }")
    out.append(_staff_panels_css(st))
    out += _staff_material_css(st)
    out += _staff_header_css(st)
    out += _staff_pictures_css(st)
    out += _staff_inner_css(st)
    out += _staff_paint_css(st)
    if st["contrast"] == "high":
        out.append("""html body { color: #000 !important; }
html body .text-muted, html body .hint, html body .help-block, html body .form-text { color: #1f1f1f !important; }
html body table, html body table td, html body table th { border-color: #4b5563 !important; }
html body a:not(.btn) { text-decoration: underline; text-underline-offset: 2px; }
html body .btn { border-width: 2px; }""")
    out.append(style_css(cfg, "staff"))
    return "\n".join(x for x in out if x) + "\n"


def _staff_panels_css(st: dict) -> str:
    """The staff pages' panels in the staff palette: the breadcrumb bar a
    card instead of Koha's flat strip, the content sections on the card
    colour, the login page's instructions box; with a dark block background
    Koha's white tables, forms and dialogs follow it, so light text never
    lands on white."""
    light = luminance(st["surface"]) >= 0.30
    page = st["card"] == "page"
    out = ["""/* Koha's page wrappers carry no colour of their own (Bootstrap paints the
   body white and the old .main rule painted the whole content area): only
   the cards below do, so the page colour or the wallpaper shows between them. */
html body #container-main,""" + ("" if page else " html body .main,") + """ html body main, html body .container-fluid:not(.main),
html body #sub-header, html body #sidebar-container, html body #sidebar-container aside,
html body .main > .row, html body .main > .row > [class*="col"],
html body #container-main > .row, html body #container-main > .row > [class*="col"] {
    background-color: transparent !important;
}
html body #breadcrumbs { background: transparent; border: 0; box-shadow: none; }
html body #breadcrumbs .breadcrumb {
    background-color: var(--nexus-staff-card);
    border: 1px solid var(--nexus-staff-edge);
    border-radius: calc(var(--nexus-staff-radius) * .6);
    box-shadow: var(--nexus-staff-shadow);
    padding: .45rem .9rem;
    margin: .5rem 0;
}
html body #breadcrumbs .breadcrumb-item, html body #breadcrumbs .breadcrumb-item.active { color: var(--nexus-staff-muted); }
html body .page-section {
    background-color: var(--nexus-staff-card);
    color: var(--nexus-staff-text);
    border-radius: var(--nexus-staff-radius);
    padding: var(--nexus-staff-card-pad);
}
html body #login #StaffLoginInstructions {
    background-color: var(--nexus-staff-card);
    color: var(--nexus-staff-text);
    border: 1px solid var(--nexus-staff-edge);
    border-radius: var(--nexus-staff-radius);
    box-shadow: var(--nexus-staff-shadow);
}
html body #login .kei-login-banner-wrap { margin: 0 0 .75rem; }"""]
    if page:
        # Koha's .main (main-container.inc) holds the content and its sidebar;
        # pages without it (the home page) keep their section cards. No
        # !important: the texture and the wallpaper set its background below.
        out.append("""/* One card for the whole page: .main. */
html body .main {
    background-color: var(--nexus-staff-card);
    color: var(--nexus-staff-text);
    border: 1px solid var(--nexus-staff-edge);
    border-radius: var(--nexus-staff-radius);
    box-shadow: var(--nexus-staff-shadow);
    /* Bootstrap's rows inside pull out by half a gutter: put it back on the
       sides, so 0 is Koha's own spacing and the slider adds to it. */
    padding: var(--nexus-staff-card-pad) calc(var(--nexus-staff-card-pad) + var(--bs-gutter-x, 1.5rem) * .5);
    margin-top: .9rem;
    margin-bottom: .9rem;
}""")
    if not light:
        field = mix(st["surface"], "#000000", .25)
        out.append(f"""/* A dark block background: Koha's white surfaces follow it. */
html body h1, html body h2, html body h3, html body h4, html body h5, html body legend {{ color: var(--nexus-staff-ink); }}
html body .text-muted, html body .hint, html body .form-text, html body .breadcrumb-item {{ color: var(--nexus-staff-muted) !important; }}
html body table, html body .table {{
    --bs-table-bg: transparent;
    --bs-table-color: var(--nexus-staff-text);
    --bs-table-striped-bg: rgba(255, 255, 255, .04);
    --bs-table-striped-color: var(--nexus-staff-text);
    --bs-table-border-color: rgba(255, 255, 255, .12);
    color: var(--nexus-staff-text);
}}
html body table td, html body table th, html body table.dataTable tbody tr, html body .dataTables_wrapper {{
    background-color: transparent !important;
    color: var(--nexus-staff-text);
    border-color: rgba(255, 255, 255, .12) !important;
}}
html body table thead th, html body table tbody tr:nth-child(odd) td {{ background-color: rgba(255, 255, 255, .04) !important; }}
html body .main input[type="text"], html body .main input[type="search"], html body .main input[type="password"],
html body .main input[type="email"], html body .main input[type="number"], html body .main input[type="tel"],
html body .main select, html body .main textarea, html body .main .form-control, html body .main .form-select {{
    background-color: {field};
    color: var(--nexus-staff-text);
    border-color: rgba(255, 255, 255, .18);
}}
html body .modal-content, html body .dropdown-menu:not(.dropdown-menu-dark), html body fieldset.rows,
html body .toptabs .tab-content, html body .tab-content {{
    background-color: var(--nexus-staff-card);
    color: var(--nexus-staff-text);
}}
html body fieldset.rows label, html body fieldset.rows legend {{ color: var(--nexus-staff-text); }}""")
    return "\n".join(out)


_STAFF_BTN_MAIN = 'html body .btn-primary, html body input[type="submit"].btn-primary'
_STAFF_BTN_SOFT = "html body .btn-default, html body .btn-secondary, html body .btn-light"


def _staff_paint_css(st: dict) -> list[str]:
    """The staff colours in their own texture and opacity (st["paint"]),
    as on the OPAC: the accent on the main buttons, the second colour on
    the secondary ones, the page colour on the page (without a staff
    wallpaper). Nothing while all are "auto" at full opacity."""
    out = []
    p = st["paint"]["accent"]
    if p["texture"] != "auto" or p["opacity"] < 100:
        texture = p["texture"] if p["texture"] != "auto" else ("metal" if st["texture"] in METALS else "flat")
        out.append(_paint_rule(_STAFF_BTN_MAIN, _paint(texture, "--nexus-staff-primary-rgb", p["opacity"], True),
                               "var(--nexus-staff-on-primary)"))
    p = st["paint"]["accent2"]
    if p["texture"] != "auto":
        out.append(_paint_rule(_STAFF_BTN_SOFT, _paint(p["texture"], "--nexus-staff-secondary-rgb", p["opacity"],
                                                       True), "var(--nexus-staff-on-secondary)"))
        out.append(f"{_STAFF_BTN_SOFT} {{ border-color: var(--nexus-staff-secondary) !important; }}")
    p = st["paint"]["page"]
    if not st["background"]["url"] and (p["texture"] != "auto" or p["opacity"] < 100):
        paint = _paint(p["texture"], "--nexus-staff-page-rgb", p["opacity"], False)
        out.append(f""":root {{ --nexus-staff-page-rgb: {_rgb(staff_page(st))}; }}
html body {{
    background: {paint['bg']}, #ffffff !important;
    background-attachment: fixed !important;
}}""")
    return (["/* Each staff colour in its own texture and opacity. */\n" + "\n".join(out)] if out else [])


def staff_page(st: dict) -> str:
    """The staff page colour: the chosen one, else the surface with a hint of the accent."""
    if st["page"]:
        return st["page"]
    light = luminance(st["surface"]) >= 0.30
    return mix(st["surface"], st["accent"], .04 if light else .08)


# The staff blocks that take the texture (the content sections, the news
# column, the forms) and the cards inside them (home page modules, news).
_STAFF_BLOCKS = ".page-section, #area-news, fieldset.rows"
_STAFF_CARDS = "ul.biglinks-list li a.icon_general, #area-news .newsitem"


def _staff_blocks(st: dict, blocks: str = _STAFF_BLOCKS) -> str:
    """The staff blocks that are cards: with one card for the whole page,
    .main joins them (the sections inside it go clear, _staff_inner_css)."""
    return blocks + (", .main" if st["card"] == "page" else "")


# Inside the one page card these lose their own surface: one layer only.
_STAFF_INNER = (".page-section, fieldset.rows, .sidebar_menu, .dataTables_wrapper, form .action, "
                "#area-news, .tab-content")


def _staff_inner_css(st: dict) -> list[str]:
    """One card for the whole page: Koha's sections, forms, sidebar menus
    and tables inside .main are clear (beaten by specificity, .main in the
    selector), so the card's opacity is the only one on the page."""
    if st["card"] != "page":
        return []
    inner = ", ".join("html body .main " + x.strip() for x in _STAFF_INNER.split(","))
    # The frosted blur layers of the sections (_staff_material_css).
    before = ", ".join(f"html body .main {x.strip()}::before" for x in _STAFF_BLOCKS.split(","))
    return [f"""{inner} {{
    background: transparent;
    border-color: transparent;
    box-shadow: none;
}}
{before} {{ content: none; }}
html body .main .page-section {{ padding: .5rem 0; }}"""]


def _staff_material_css(st: dict) -> list[str]:
    """The OPAC's materials on the staff blocks, from cfg["staff"]: frosted
    glass (blur + opacity), smooth glass, brushed metal and anodised
    aluminium (with metal buttons like the OPAC's), wood, matte paper, a
    soft diagonal gradient. "flat" adds nothing: the
    solid cards of the staff palette. Without a staff wallpaper, glass gets a
    page with two faint accent glows to blur (the OPAC's canvas)."""
    t = st["texture"]
    if t == "flat":
        return []
    blocks, cards = _strong(_staff_blocks(st)), _strong(_STAFF_CARDS)
    surface = "rgba(var(--nexus-staff-surface-rgb), var(--nexus-staff-surface-a))"
    wash = ("linear-gradient(135deg, rgba(var(--nexus-staff-primary-rgb), .08), "
            "rgba(var(--nexus-staff-secondary-rgb), .08))")
    light = luminance(st["surface"]) >= 0.30
    shadow = ("0 1px 2px rgba(15, 23, 42, .06), 0 12px 32px -10px rgba(15, 23, 42, .22)" if light
              else "0 1px 2px rgba(0, 0, 0, .25), 0 12px 32px -10px rgba(0, 0, 0, .55)")
    rule = [f"{blocks} {{", f"    background: {wash}, {surface};",
            "    border: 1px solid var(--nexus-staff-edge);", "    border-radius: var(--nexus-staff-radius);"]
    if t == "frosted":
        # The blur sits on a layer behind the content, not on the block: a
        # backdrop-filter on the block would make it the frame of every
        # position: fixed thing inside it (Koha's modals, the assistant's
        # wider view).
        rule += ["    position: relative;", "    isolation: isolate;", f"    box-shadow: {shadow};"]
    elif t == "smooth":
        rule += [f"    box-shadow: {shadow};"]
    elif t in MATERIALS:
        mat = _material(t, "--nexus-staff-primary-rgb")
        rule[1] = f"    background: {mat['sheen']}, {surface};"
        rule += [f"    box-shadow: {mat['shadow']};"]
    elif t == "gradient":
        rule[1] = (f"    background: linear-gradient(135deg, {surface} 0%, "
                   "rgba(var(--nexus-staff-primary-rgb), .10) 55%, rgba(var(--nexus-staff-secondary-rgb), .14) 100%);")
        rule += [f"    box-shadow: {shadow};"]
    rule.append("}")
    # The cards inside: the same surface, a touch more solid, so text stays crisp.
    rule.append(f"""{cards} {{
    background-color: rgba(var(--nexus-staff-surface-rgb), calc(var(--nexus-staff-surface-a) * .5 + .5));
}}""")
    if t == "frosted":
        layer = ", ".join(f"{x}::before" for x in blocks.split(", "))
        rule.append(f"""{layer} {{
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    pointer-events: none;
    -webkit-backdrop-filter: blur(var(--nexus-staff-blur)) saturate(140%);
    backdrop-filter: blur(var(--nexus-staff-blur)) saturate(140%);
}}""")
        if st["card"] == "page":
            # .main holds Koha's modals and dropdowns: isolated, it would trap
            # them under Bootstrap's backdrop (a child of body). Its blur layer
            # sits in the body's stacking context instead.
            rule.append("""html body { position: relative; z-index: 0; }
html body .main { isolation: auto; }""")
    if t in METALS:
        # The top bar and the buttons brushed, like the OPAC's.
        bar = _METAL_MAIN.format(c="var(--nexus-staff-topbar)")
        rule.append(f"""html body nav.navbar.bg-dark, html body nav.navbar.navbar-dark {{
    background: {bar} !important;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, .45), inset 0 -1px 0 rgba(0, 0, 0, .35);
}}
html body .btn-primary, html body input[type="submit"].btn-primary {{
    background: {_METAL_MAIN.format(c="var(--nexus-staff-primary)")};
    box-shadow: {_METAL_SHADOW};
}}
html body .btn-default, html body .btn-secondary, html body .btn-light {{
    background: {_METAL_SOFT};
    border-color: #9ba2ab;
    color: #2a3038;
    box-shadow: {_METAL_SHADOW};
}}""")
    if not st["background"]["url"] and t in ("frosted", "smooth"):
        base = staff_page(st)
        rule.append(f"""html body {{
    background: radial-gradient(1200px 600px at 0% 0%, rgba(var(--nexus-staff-primary-rgb), .14), transparent 60%),
        radial-gradient(1000px 600px at 100% 100%, rgba(var(--nexus-staff-secondary-rgb), .12), transparent 60%), {base};
    background-attachment: fixed;
}}""")
    return ["\n".join(rule)]


# ----------------------------------------------------------------------
# Style details (STYLE): card shadow, spacing, icons, background pattern,
# tables and menus, login page, hover animations. One builder for both
# sides; each side names its own variables and blocks (_STYLE_SIDES).
# ----------------------------------------------------------------------
_SHADOWS = {
    "none": "",
    "soft": "0 1px 2px rgba(0, 0, 0, .08), 0 4px 12px -2px rgba(0, 0, 0, .10)",
    "medium": "0 2px 4px rgba(0, 0, 0, .10), 0 14px 30px -8px rgba(0, 0, 0, .26)",
    "strong": "0 4px 10px rgba(0, 0, 0, .16), 0 26px 52px -12px rgba(0, 0, 0, .45)",
}
_METAL_BEVEL = ("inset 0 1px 0 rgba(255, 255, 255, .85), inset 1px 0 0 rgba(255, 255, 255, .35), "
                "inset 0 -1px 0 rgba(0, 0, 0, .28), inset -1px 0 0 rgba(0, 0, 0, .14)")
_GRAIN = _noise(".75", 2, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -.6 .36", "200 200")
_ICONS = ('i[class*="fa-"]', 'span[class*="fa-"]:not(.fa-stack)', "i.fa", "span.fa")


def _side_vars(cfg: dict, side: str) -> dict:
    """The CSS each side's style details are built from: its accent
    colours, its card (colour, sheen, blur, edge, corners, text), its blocks
    and whether it has a wallpaper."""
    if side == "opac":
        return {"accent": "var(--kei-accent-rgb)", "accent2": "var(--kei-accent2-rgb)",
                "solid": "rgba(var(--koha-card-rgb), calc(var(--koha-card-alpha) * .3 + .7))",
                "sheen": "var(--koha-card-sheen)", "blur": "var(--koha-glass-blur)",
                "edge": "var(--koha-card-border)", "radius": "var(--koha-card-radius)", "text": "var(--koha-text)",
                "blocks": f"{_strong(_BLOCKS)}, html body .main", "texture": cfg["texture"],
                "wallpaper": bool(cfg["background"]["url"]), "login": "html body#opac-login-page",
                "login_main": "html body#opac-login-page .main", "login_card": "#opac-auth",
                "login_form": "#auth", "menus": "html body .main #menu, html body .main #usermenu",
                # The news blocks stay still: only their buttons move.
                "cards": "html body a.kei-link, html body .kei-action"}
    st = cfg["staff"]
    t = st["texture"]
    if t in MATERIALS:
        sheen = _material(t, "--nexus-staff-primary-rgb")["sheen"]
    elif t == "gradient":
        sheen = ("linear-gradient(135deg, transparent 0%, rgba(var(--nexus-staff-primary-rgb), .10) 55%, "
                 "rgba(var(--nexus-staff-secondary-rgb), .14) 100%)")
    else:
        sheen = "linear-gradient(transparent, transparent)"
    return {"accent": "var(--nexus-staff-primary-rgb)", "accent2": "var(--nexus-staff-secondary-rgb)",
            "solid": "rgba(var(--nexus-staff-surface-rgb), calc(var(--nexus-staff-surface-a) * .3 + .7))",
            "sheen": sheen, "blur": "var(--nexus-staff-blur)" if t in ("frosted", "smooth") else "0px",
            "edge": "var(--nexus-staff-edge)", "radius": "var(--nexus-staff-radius)",
            "text": "var(--nexus-staff-text)", "blocks": _strong(_staff_blocks(st)), "texture": t,
            "wallpaper": bool(st["background"]["url"]), "login": "html body#main_auth",
            "login_main": "html body#main_auth .main", "login_card": "#login", "login_form": "#loginform",
            "menus": "html body #navmenulist, html body .sidebar_menu",
            "cards": "html body ul.biglinks-list li a.icon_general"}


def style_css(cfg: dict, side: str) -> str:
    """The style details of one side ("opac": cfg, "staff": cfg["staff"])
    as CSS, after the side's own rules so they win. The defaults add
    nothing: the look stays as it was before these options existed."""
    s = cfg if side == "opac" else cfg["staff"]
    v = _side_vars(cfg, side)
    out = []
    if s["shadow"] != "texture":
        drop = _SHADOWS[s["shadow"]]
        bevel = _METAL_BEVEL if v["texture"] in METALS else ""
        shadow = ", ".join(x for x in (bevel, drop) if x) or "none"
        var = "--koha-card-shadow" if side == "opac" else "--nexus-staff-shadow"
        out.append(f""":root {{ {var}: {shadow}; }}
{v['blocks']} {{ box-shadow: {shadow} !important; }}""")
    out.append(_spacing_css(s["spacing"], side))
    if s["icons"] == "outline":
        icons = ", ".join("html body " + x for x in _ICONS)
        out.append(f"""/* Outline icons: the glyph drawn as its contour, in the text colour. */
@supports (-webkit-text-stroke: 1px black) {{
    {icons} {{ -webkit-text-fill-color: transparent; -webkit-text-stroke: .9px currentColor; }}
}}""")
    if s["pattern"] != "none" and not v["wallpaper"]:
        out.append(f"""/* A faint pattern over the page colour, under every block (no wallpaper). */
html body {{ position: relative; z-index: 0; }}
html body::before {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: {_pattern(s['pattern'], v['accent'])};
}}""")
    if s["chrome"] == "texture":
        out.append(f"""/* Tables and menus in the chosen texture. */
html body .dropdown-menu {{
    background: {v['sheen']}, {v['solid']} !important;
    -webkit-backdrop-filter: blur({v['blur']});
    backdrop-filter: blur({v['blur']});
    border: 1px solid {v['edge']} !important;
    border-radius: min({v['radius']}, 14px) !important;
    box-shadow: 0 14px 30px -10px rgba(0, 0, 0, .38) !important;
}}
html body .dropdown-menu .dropdown-item {{ color: {v['text']} !important; background: transparent !important; }}
html body .dropdown-menu .dropdown-item:hover, html body .dropdown-menu .dropdown-item:focus {{
    background: rgba({v['accent']}, .16) !important; }}
html body table thead th, html body .table thead th {{
    background: {v['sheen']}, rgba({v['accent']}, .12) !important;
    color: {v['text']} !important;
}}
{v['menus']} {{
    background: {v['sheen']}, rgba({v['accent']}, .07);
    border: 1px solid {v['edge']};
    border-radius: min({v['radius']}, 14px);
    overflow: hidden;
}}""")
    if s["login_style"] != "koha":
        card, page = f"{v['login']} {v['login_card']}", ""
        if s["login_style"] == "accent":
            page = f"""
{v['login']} {{
    background: radial-gradient(900px 500px at 15% 10%, rgba(255, 255, 255, .22), transparent 60%),
        linear-gradient(135deg, rgb({v['accent']}), rgb({v['accent2']})) fixed !important;
}}"""
        out.append(_login_css(v, side, card, page))
    out.append(_motion_css(s["motion"], v))
    return "\n".join(x for x in out if x)


def _login_css(v: dict, side: str, card: str, page: str) -> str:
    width = f"\n{card} {{ max-width: 26rem; }}" if side == "staff" else ""
    return f"""/* The login page: the form on one highlighted card, the page's own card clear. */
{v['login_main']} {{
    background: transparent !important;
    border-color: transparent !important;
    box-shadow: none !important;
}}
{v['login_main']}::before, {v['login_main']}::after {{ content: none !important; }}
{card} {{
    background: {v['sheen']}, {v['solid']};
    -webkit-backdrop-filter: blur({v['blur']});
    backdrop-filter: blur({v['blur']});
    border: 1px solid {v['edge']};
    border-top: 4px solid rgb({v['accent']});
    border-radius: {v['radius']};
    padding: 1.5rem 1.75rem;
    margin: 2rem auto;
    box-shadow: {_SHADOWS['strong']};
    color: {v['text']};
}}{width}
{card} h1, {card} h2 {{ text-align: center; }}
{card} {v['login_form']} .btn, {card} {v['login_form']} input[type="submit"] {{
    width: 100%;
    min-height: 44px;
}}{page}"""


def _pattern(kind: str, accent: str) -> str:
    ink = f"rgba({accent}, .13)"
    if kind == "dots":
        return f"radial-gradient(circle, {ink} 1.2px, transparent 1.7px) 0 0 / 18px 18px"
    if kind == "grid":
        return (f"linear-gradient({ink} 1px, transparent 1px) 0 0 / 28px 28px, "
                f"linear-gradient(90deg, {ink} 1px, transparent 1px) 0 0 / 28px 28px")
    if kind == "lines":
        return f"repeating-linear-gradient(45deg, {ink} 0 1px, transparent 1px 14px)"
    return _GRAIN


def _spacing_css(kind: str, side: str) -> str:
    """Compact or airy: the room around the content, the paragraphs and the
    table cells. The staff's table density and card padding stay its own."""
    if kind == "normal":
        return ""
    compact = kind == "compact"
    line, gap = ("1.35", ".4rem") if compact else ("1.7", "1rem")
    if side == "opac":
        pad, cell = (".7rem", ".3rem .5rem") if compact else ("2rem", ".7rem 1rem")
        return f"""/* Spacing: {kind}. */
html body {{ line-height: {line}; }}
html body .main {{ padding: {pad}; margin-top: {".5rem" if compact else "1.5rem"}; }}
html body .main p, html body .main li {{ margin-bottom: {gap}; }}
html body .main table td, html body .main table th {{ padding: {cell} !important; }}
html body #opac-main-search {{ padding-top: {".35rem" if compact else "1rem"}; padding-bottom: {".35rem" if compact else "1rem"}; }}"""
    return f"""/* Spacing: {kind}. */
html body {{ line-height: {line}; }}
html body .page-section, html body fieldset.rows, html body #area-news {{ margin-bottom: {".5rem" if compact else "1.75rem"}; }}
html body fieldset.rows li {{ padding-bottom: {".1rem" if compact else ".55rem"}; }}
html body .main p {{ margin-bottom: {gap}; }}"""


def _motion_css(kind: str, v: dict) -> str:
    """Off: nothing moves or fades (as under the device's reduced motion).
    Lively: the cards and buttons lift and table rows light up on hover,
    only where the device does not ask for less motion."""
    if kind == "off":
        return f"""/* Animations off. */
html body *, html body *::before, html body *::after {{
    transition: none !important;
    animation-duration: .001s !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
}}
html body .btn:hover, html body .btn:focus, html body button:hover, html body input[type="submit"]:hover,
{", ".join(x.strip() + ":hover" for x in v["cards"].split(","))} {{ transform: none !important; }}"""
    if kind == "lively":
        hover = ", ".join(x.strip() + ":hover" for x in v["cards"].split(","))
        return f"""/* Lively hover animations. */
@media (prefers-reduced-motion: no-preference) {{
    {v['cards']} {{ transition: transform .25s cubic-bezier(.2, .8, .2, 1), box-shadow .25s ease; }}
    {hover} {{
        transform: translateY(-4px) scale(1.01);
        box-shadow: 0 18px 34px -14px rgba({v['accent']}, .45) !important;
    }}
    html body .btn, html body input[type="submit"], html body a.btn-acesso {{
        transition: transform .2s ease, filter .2s ease, box-shadow .2s ease;
    }}
    html body .btn:hover, html body input[type="submit"]:hover, html body a.btn-acesso:hover {{
        transform: translateY(-2px) scale(1.03);
    }}
    html body .btn:active, html body input[type="submit"]:active, html body a.btn-acesso:active {{
        transform: translateY(0) scale(.98);
    }}
    html body table tbody tr td {{ transition: background-color .2s ease; }}
    html body table tbody tr:hover td {{ background-color: rgba({v['accent']}, .07); }}
}}"""
    return ""


def _staff_header_css(st: dict) -> list[str]:
    """The top bar (nav.navbar) and the quick search bar (#header_search) in
    translucent glass: the bar's own colours at --nexus-staff-header-a over a
    blur of --nexus-staff-header-blur. Only the bars' backgrounds go
    translucent (rgba, never opacity), so the links, the search field, its
    button and the dropdown menus keep full opacity and contrast. Off, or
    where the device asks for less transparency or the browser has no
    backdrop-filter, the bars stay solid. Comes after the texture, so it
    also wins over the metal bar.

    The bars follow the blocks' opacity and blur (Paulo, 2026-10-31: "a
    barra superior não aplica transparência"); the "Translucent top bar"
    switch gives them an opacity and blur of their own instead. The colours
    are variables, so the dark mode's bar is translucent too."""
    own = st["header_glass"]
    alpha, blur = (st["header_opacity"], st["header_blur"]) if own else (st["opacity"], st["blur"])
    if alpha >= 100:
        return []
    a = "var(--nexus-staff-header-a)"
    top, end, bar = "var(--nexus-staff-topbar-rgb)", "var(--nexus-staff-topbar-end-rgb)", "var(--nexus-staff-bar-rgb)"
    bars = "html body nav.navbar.bg-dark, html body nav.navbar.navbar-dark, html body #header_search"
    return [f""":root {{
    --nexus-staff-header-a: {alpha / 100:.2f};
    --nexus-staff-header-blur: {blur}px;
}}
html body nav.navbar.bg-dark, html body nav.navbar.navbar-dark {{
    background: linear-gradient(90deg, rgba({top}, {a}), rgba({end}, {a})) !important;
    border-bottom: 1px solid rgba(255, 255, 255, .18);
}}
html body #header_search {{ background-color: rgba({bar}, {a}) !important; border-color: transparent; }}
/* One layer only: the tabs, labels and lists inside the search bar are clear,
   the bar behind them carries the colour. */
html body #header_search ul, html body #header_search .form-title,
html body #header_search .nav-tabs > li > a:not(.active):not(:hover):not(:focus) {{
    background-color: transparent;
    border-color: transparent;
}}
/* The blur sits on a layer behind the bar (as on the frosted blocks), and the
   bar stays above the page so its dropdown menus are never covered. */
{bars} {{ position: relative; isolation: isolate; z-index: 1030; }}
html body #header_search {{ z-index: 1029; }}
{", ".join(f"{x}::before" for x in bars.split(", "))} {{
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    -webkit-backdrop-filter: blur(var(--nexus-staff-header-blur)) saturate(140%);
    backdrop-filter: blur(var(--nexus-staff-header-blur)) saturate(140%);
}}
/* Full opacity and contrast for what sits on the glass. */
html body nav.navbar #header .nav-link, html body nav.navbar #logged-in-info-full, html body nav.navbar .navbar-text,
html body #header_search .form-title label, html body #header_search .nav-tabs > li > a {{
    text-shadow: 0 1px 2px rgba(0, 0, 0, .35);
}}
html body #header_search .form-content, html body #header_search .form-extra-content,
html body nav.navbar .dropdown-menu:not(.dropdown-menu-dark) {{ background-color: var(--nexus-staff-card); }}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {{
    :root {{ --nexus-staff-header-a: 1; }}
}}
@media (prefers-reduced-transparency: reduce) {{
    :root {{ --nexus-staff-header-a: 1; }}
}}"""]


def _staff_pictures_css(st: dict) -> list[str]:
    """The staff logo in the top bar and the staff wallpaper under a film of
    the page colour. Over a wallpaper the cards (content sections, sidebar
    menus, tables, forms) take the staff surface at the opacity slider, one
    layer only: a card inside a card stays clear, as on the OPAC. The
    favicon is IntranetFavicon."""
    out = []
    logo = st["logo"]["url"]
    if logo:
        out.append(f"""html body nav.navbar #logo.navbar-brand {{
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    width: 150px;
    height: 34px;
    padding: 0;
    background: url("{logo}") left center / contain no-repeat;
}}
html body nav.navbar #logo.navbar-brand img {{ display: none; }}
@media (max-width: 575px) {{ html body nav.navbar #logo.navbar-brand {{ width: 96px; height: 28px; }} }}""")
    bg = st["background"]["url"]
    if bg:
        page = staff_page(st)
        out.append(f"""html body {{
    background: url("{bg}") center / cover no-repeat fixed;
    position: relative;
    z-index: 0;
}}
html body::before {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: rgba({_rgb(page)}, {st['film'] / 100:.2f});
}}
{_strong(_staff_blocks(st, ".page-section, .sidebar_menu, .dataTables_wrapper, fieldset.rows, form .action"))} {{
    background-color: rgba(var(--nexus-staff-surface-rgb), var(--nexus-staff-surface-a));
    border-radius: var(--nexus-staff-radius);
}}
html body .page-section .page-section, html body .page-section .dataTables_wrapper,
html body .page-section fieldset.rows, html body .page-section form .action,
html body fieldset.rows fieldset.rows, html body .dataTables_wrapper fieldset.rows {{
    background: transparent;
}}
html body .page-section table, html body .page-section .table,
html body .dataTables_wrapper table, html body .dataTables_wrapper .table {{
    --bs-table-bg: transparent;
    background-color: transparent;
}}""")
    return out


def staff_active(cfg: dict) -> bool:
    """Something of ours goes into the staff interface: its colours or its
    home page buttons."""
    cfg = normalize(cfg)
    return cfg["staff"]["enabled"] or links_on(cfg["staff_links"])


def staff_dark(cfg: dict) -> bool:
    """The staff interface has the light/dark switch (with its own colours on)."""
    cfg = normalize(cfg)
    return cfg["staff"]["enabled"] and cfg["staff"]["dark_switch"]


def staff_dark_css(cfg: dict) -> str:
    """The staff interface in dark mode (html[data-kei-theme="dark"], set by
    the switch of staff.js): the staff variables on dark surfaces, and
    Koha's and Bootstrap's white boxes, tables, fields and menus with them."""
    st = normalize(cfg)["staff"]
    card = "#161b22"
    link = readable(mix(link_base(st["accent"], st["accent2"]), "#ffffff", .45), card, 5.5)
    # The accents lifted until they stand out on the dark cards (a black
    # accent made black buttons and invisible module icons on #161b22).
    primary, secondary = readable(st["accent"], card, 3), readable(st["accent2"], card, 3)
    # A light top bar turns dark with the page; a dark one stays.
    top = staff_bar(st)
    if luminance(top) >= .18:
        top = mix(top, "#0d1117", .88)
    end, bar = mix(top, "#000000", .12), mix(top, "#000000", .22)
    d = 'html[data-kei-theme="dark"]'
    film = ""
    if st["background"]["url"]:
        # The wallpaper's film goes dark with the page, never a white veil.
        film = f"\n{d} body::before {{ background: rgba(8, 12, 20, {min(st['film'] + 15, 92) / 100:.2f}); }}"
    return f"""/* Staff dark mode (the light/dark switch). */
{d} {{
    --nexus-staff-page: #0d1117;
    --nexus-staff-card: {card};
    --nexus-staff-text: #e6edf3;
    --nexus-staff-muted: #9da7b3;
    --nexus-staff-ink: #f0f3f6;
    --nexus-staff-link: {link};
    --nexus-staff-primary: {primary};
    --nexus-staff-primary-rgb: {_rgb(primary)};
    --nexus-staff-on-primary: {text_on(primary)};
    --nexus-staff-secondary: {secondary};
    --nexus-staff-secondary-rgb: {_rgb(secondary)};
    --nexus-staff-on-secondary: {text_on(secondary)};
    --nexus-staff-topbar: {top};
    --nexus-staff-topbar-rgb: {_rgb(top)};
    --nexus-staff-topbar-end: {end};
    --nexus-staff-topbar-end-rgb: {_rgb(end)};
    --nexus-staff-bar: {bar};
    --nexus-staff-bar-rgb: {_rgb(bar)};
    --nexus-staff-on-topbar: #e6edf3;
    --nexus-staff-on-topbar-rgb: 230,237,243;
    --nexus-staff-menu: #0d1117;
    --nexus-staff-shadow: 0 1px 2px rgba(0, 0, 0, .35), 0 8px 22px -8px rgba(0, 0, 0, .6);
    --nexus-staff-shadow-hi: 0 2px 4px rgba(0, 0, 0, .4), 0 14px 28px -8px rgba({_rgb(primary)}, .45);
    --nexus-staff-surface-rgb: 22, 27, 34;
    --nexus-staff-edge: rgba(255, 255, 255, .10);
    --bs-body-bg: #0d1117;
    --bs-body-color: #e6edf3;
    --bs-border-color: #30363d;
    color-scheme: dark;
}}
{d} body {{ background-color: var(--nexus-staff-page); color: var(--nexus-staff-text); }}
{d} body .main, {d} body .main h1, {d} body .main h2, {d} body .main h3, {d} body .main h4,
{d} body .main label, {d} body .main legend, {d} body .main th, {d} body .main td, {d} body #breadcrumbs,
{d} body .sidebar_menu, {d} body #navmenulist {{ color: var(--nexus-staff-text) !important; }}
{d} body .page-section, {d} body fieldset.rows, {d} body .modal-content, {d} body .dropdown-menu:not(.dropdown-menu-dark),
{d} body #area-news .newsitem, {d} body .card, {d} body .list-group-item, {d} body .toptabs:not(#header_search) .tab-content,
{d} body .ui-tabs-panel, {d} body #navmenu, {d} body .sidebar_menu, {d} body .dataTables_wrapper {{
    background-color: rgba(var(--nexus-staff-surface-rgb), calc(var(--nexus-staff-surface-a) * .3 + .7)) !important;
    color: var(--nexus-staff-text);
    border-color: #30363d;
}}
{d} body .table, {d} body table {{
    --bs-table-bg: transparent;
    --bs-table-color: var(--nexus-staff-text);
    --bs-table-striped-bg: rgba(255, 255, 255, .03);
    --bs-table-hover-bg: rgba(255, 255, 255, .06);
    background-color: transparent;
    color: var(--nexus-staff-text);
}}
{d} body table th {{ background-color: #1c2230 !important; }}
{d} body table tr td, {d} body table tr.odd td, {d} body table tr.even td {{
    background-color: transparent !important; border-color: #30363d;
}}
{d} body .form-control, {d} body .form-select, {d} body input[type="text"], {d} body input[type="password"],
{d} body input[type="search"], {d} body input[type="email"], {d} body input[type="number"], {d} body select,
{d} body textarea {{ background-color: #0d1117; color: var(--nexus-staff-text); border-color: #30363d; }}
{d} body ::placeholder {{ color: #9da7b3; opacity: 1; }}
{d} body .main a:not(.btn):not(.dropdown-item):not(.nav-link), {d} body #breadcrumbs a {{ color: var(--nexus-staff-link); }}
{d} body .text-muted, {d} body .hint {{ color: var(--nexus-staff-muted) !important; }}
{d} body .btn-default, {d} body .btn-light {{ background-color: #21262d; color: var(--nexus-staff-text); border-color: #30363d; }}
{d} body #area-news {{ background-color: rgba(22, 27, 34, .55); }}
/* The light textures' sheen (brushed metal, paper, wood) would be a pale
   veil on the dark cards: in dark mode the blocks are the dark glass only. */
{", ".join(f"{d} body {x.strip()}" for x in _staff_blocks(st).split(","))} {{
    background-image: none !important;
    background-color: rgba(22, 27, 34, calc(var(--nexus-staff-surface-a) * .3 + .7)) !important;
}}
{d} body #changelanguage, {d} body #changelanguage.bg-light {{
    background-color: var(--nexus-staff-page) !important;
    border-color: #30363d;
}}
{d} body #changelanguage .nav-link, {d} body #changelanguage .navbar-text {{ color: var(--nexus-staff-link); }}
{d} body #changelanguage .nav-link.disabled, {d} body #changelanguage .currentlanguage {{ color: var(--nexus-staff-text); }}
{d} body #koha_version, {d} body #koha_version a {{ color: var(--nexus-staff-muted); }}
{d} body #helper, {d} body #helper a, {d} body #breadcrumbs #helper {{ color: var(--nexus-staff-link); }}
{d} body .ui-autocomplete, {d} body .ui-widget-content {{
    background-color: var(--nexus-staff-card); color: var(--nexus-staff-text); border-color: #30363d;
}}{film}
/* The switch sits at the foot of the page, with the languages (as on the OPAC). */
#kei-theme-switch {{
    border: 1px solid var(--nexus-staff-edge, rgba(0, 0, 0, .15));
    background: var(--nexus-staff-card, #fff);
    color: var(--nexus-staff-text, #1f2933);
    border-radius: 999px;
    padding: .2rem .65rem;
    margin: 0 .5rem;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1.4;
    align-self: center;
}}
#kei-theme-switch:hover {{ border-color: var(--nexus-staff-primary, #408540); }}
#kei-theme-switch.kei-theme-floating {{
    position: fixed; right: 1rem; bottom: 1rem; z-index: 1080; margin: 0;
    box-shadow: var(--nexus-staff-shadow, 0 4px 12px rgba(0, 0, 0, .2));
}}
{SWITCH_ICON_CSS}
"""


def staff_css_block(cfg: dict) -> str:
    """IntranetUserCSS: the staff colours when they are on, the home page
    buttons when there are some."""
    cfg = normalize(cfg)
    parts = []
    if cfg["staff"]["enabled"]:
        parts.append(staff_css_body(cfg).rstrip("\n"))
    if staff_dark(cfg):
        parts.append(staff_dark_css(cfg).rstrip("\n"))
    if links_on(cfg["staff_links"]):
        parts.append(staff_links_css(cfg).rstrip("\n"))
    return "\n".join([CSS_BEGIN, *parts, CSS_END]) + "\n"


# ----------------------------------------------------------------------
# The script
# ----------------------------------------------------------------------
# The nav of quick access buttons (OPAC and staff home page): id, the
# settings ({style, layout, items}, already in sort_order) and its label.
_LINK_NAV = r"""    function linkNav(id, L, label) {
        if (!L || !L.items || !L.items.length) { return null; }
        var nav = document.createElement("nav");
        nav.id = id;
        nav.className = "kei-links-" + L.style + " kei-layout-" + (L.layout || "list");
        nav.setAttribute("aria-label", label);
        L.items.slice().sort(function (a, b) { return (a.sort_order || 0) - (b.sort_order || 0); }).forEach(function (it) {
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
                icon.textContent = it.icon || "\u279C";
            }
            var text = document.createElement("span");
            text.textContent = it.text;
            a.appendChild(icon);
            a.appendChild(text);
            nav.appendChild(a);
        });
        return nav.children.length ? nav : null;
    }"""

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

    // KEI.listCarousel(shelfId, target, options): mounts a carousel of the
    // public Koha list shelfId (opac-shelves.pl?op=view&shelfnumber=N) inside
    // target (a CSS selector or an element), at the end of what it holds.
    // options: title, mode ("flat", "coverflow", "ring", "wall", "shelf",
    // "fan", "spotlight", "ribbon"), count, autoplay, speed, overlay,
    // reflect, missing ("hide" | "drawn"); the panel's carousel settings
    // otherwise. Covers come
    // from the nightly job's kei-list-N.json (Koha's uploaded cover, else
    // OpenLibrary, else Amazon). Resolves to the carousel's element, or
    // null (no such public list, no cover yet, no target).
    var KEI = window.KEI = window.KEI || {};
    KEI.listCarousel = function (shelfId, target, options) {
        var id = parseInt(shelfId, 10);
        var place = typeof target === "string" ? document.querySelector(target) : target;
        var none = window.Promise ? Promise.resolve(null) : { then: function () {} };
        if (!C.lists || !(id > 0) || !place || !place.appendChild) { return none; }
        var K = {}, o = options || {};
        Object.keys(C.lists).forEach(function (k) { K[k] = C.lists[k]; });
        Object.keys(o).forEach(function (k) { if (o[k] !== undefined && o[k] !== null) { K[k] = o[k]; } });
        K.count = Math.max(1, Math.min(parseInt(K.count, 10) || C.lists.count, 24));
        K.speed = Math.max(2000, parseInt(K.speed, 10) || C.lists.speed);
        K.title = String(K.title || "");
        return feed(C.lists.feed + id + ".json").then(function (items) {
            return carousel(items, K, function (box) { place.appendChild(box); });
        });
    };

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
            b.innerHTML = __SWITCH_ICONS__;
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

        // Holdings on a phone: every cell carries its column's heading, which
        // the stylesheet shows before the value when the table is stacked
        // into one card per copy (kei-stack). Again after DataTables draws.
        function labelHoldings() {
            Array.prototype.forEach.call(document.querySelectorAll("#holdingst, #otherholdingst"), function (table) {
                var heads = table.querySelectorAll("thead tr:last-child th");
                Array.prototype.forEach.call(table.querySelectorAll("tbody tr"), function (tr) {
                    Array.prototype.forEach.call(tr.children, function (td, i) {
                        if (heads[i] && td.tagName === "TD") {
                            td.setAttribute("data-kei-label", heads[i].textContent.replace(/\s+/g, " ").trim());
                        }
                    });
                });
                table.classList.add("kei-stack");
            });
        }
        labelHoldings();
        setTimeout(labelHoldings, 1500);
        if (window.jQuery) { window.jQuery(document).on("draw.dt", labelHoldings); }

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

        // New arrivals (or the list chosen in the panel), on the OPAC home page only.
        if (C.carousel && home && !document.getElementById("kei-carousel")) {
            feed(C.carousel.feed).then(function (items) { carousel(items, C.carousel, homePlace); });
        }

        // <div data-kei-list="7" data-title="..." data-mode="ring" data-reflect="1"
    // data-missing="drawn"></div>
        // in news or an HTML customization: a carousel of that public list.
        Array.prototype.forEach.call(document.querySelectorAll("[data-kei-list]"), function (el) {
            if (el.getAttribute("data-kei-mounted")) { return; }
            el.setAttribute("data-kei-mounted", "1");
            var opts = {};
            ["title", "mode", "count", "missing"].forEach(function (k) {
                if (el.hasAttribute("data-" + k)) { opts[k] = el.getAttribute("data-" + k); }
            });
            if (el.hasAttribute("data-reflect")) {
                opts.reflect = !/^(0|false|no|off)$/i.test(el.getAttribute("data-reflect"));
            }
            KEI.listCarousel(el.getAttribute("data-kei-list"), el, opts);
        });
    });

    // feed(url): the items of one of the nightly job's feeds ([] when missing).
    function feed(url) {
        if (!window.fetch || !window.Promise) { return { then: function () {} }; }
        return fetch(url, { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : { items: [] }; })
            .then(function (f) { return f.items || []; }, function () { return []; });
    }


    function homeTarget() {
        return document.getElementById("opacmainuserblock") || document.getElementById("opacmainblock")
            || document.querySelector(".maincontent") || document.querySelector(".main");
    }

__LINK_NAV__

    function links(L) {
        var place = homeTarget();
        var nav = place && linkNav("kei-links", L, C.text.links);
        if (!nav) { return; }
        if (place.id === "opacmainuserblock" || place.id === "opacmainblock") {
            place.insertBefore(nav, place.firstChild);
        } else {
            place.parentNode.insertBefore(nav, place);
        }
    }

    // The home page carousel: under the quick access buttons, else above
    // the main block.
    function homePlace(box) {
        var target = homeTarget();
        if (!target) { return; }
        box.id = "kei-carousel";
        var after = document.getElementById("kei-links");
        if (after && after.parentNode === target) {
            target.insertBefore(box, after.nextSibling);
        } else {
            target.parentNode.insertBefore(box, target);
        }
    }

    // carousel(items, K, place): the cards of items in the style K.mode
    // (MODES: a scrolling strip, "track", or a stage where the script
    // places every card, "stage"), with the settings K, put in the page by
    // place(box). They keep turning after a click or a swipe; only a hidden
    // tab, keyboard focus inside or "reduce motion" stop them. A title with
    // no cover (none found by the nightly job, or the picture does not load)
    // is left out, or gets a drawn cover with K.missing "drawn". Returns the
    // element (null with no card to show).
    var MODES = { flat: "track", shelf: "track", ribbon: "track", coverflow: "stage", ring: "stage",
                  wall: "stage", fan: "stage", spotlight: "stage" };
    var MIRRORED = { flat: 1, coverflow: 1, ring: 1, wall: 1, ribbon: 1 };
    var GOOD_COVER = /^(https:\/\/|\/cgi-bin\/koha\/opac-image\.pl\?)/;
    function carousel(items, K, place) {
        var mode = MODES.hasOwnProperty(K.mode) ? K.mode : "flat";
        var drawn = K.missing === "drawn";
        items = items.filter(function (it) {
            if (!parseInt(it.biblionumber, 10)) { return false; }
            return GOOD_COVER.test(it.cover || "") || (drawn && !it.cover);
        }).slice(0, K.count);
        if (!items.length) { return null; }
        var staged = MODES[mode] === "stage";
        var mirror = !!K.reflect && MIRRORED.hasOwnProperty(mode);
        var box = document.createElement("section");
        box.className = "kei-carousel kei-mode-" + mode + (mirror ? " kei-reflect" : "");
        if (K.title) { box.setAttribute("aria-label", K.title); }
        box.setAttribute("aria-roledescription", "carousel");
        if (K.title) {
            var h = document.createElement("h2");
            h.textContent = K.title;
            box.appendChild(h);
        }
        var track = document.createElement("div");
        track.className = staged ? "kei-stage" : "kei-track";
        box.appendChild(track);
        var pending = items.length;
        function settled() {
            pending -= 1;
            if (pending > 0) { return; }
            if (!track.children.length) { if (box.parentNode) { box.parentNode.removeChild(box); } return; }
            ({ flat: flat, shelf: flat, ribbon: ribbon, coverflow: coverflow, ring: spin, wall: spin, fan: spin,
               spotlight: spin })[mode](box, track, K, mode);
        }
        items.forEach(function (it) {
            var card = document.createElement("a");
            card.className = "kei-card";
            card.href = "/cgi-bin/koha/opac-detail.pl?biblionumber=" + parseInt(it.biblionumber, 10);
            var face = document.createElement("span");
            face.className = "kei-face";
            card.appendChild(face);
            // done(pic): the cover is in (the picture, or a drawn one): its
            // reflection, and the blurred backdrop of the spotlight.
            function done(pic) {
                if (pic.parentNode !== face) { face.insertBefore(pic, face.firstChild); }
                if (mirror) {
                    var m = document.createElement("span");
                    m.className = "kei-mirror";
                    m.setAttribute("aria-hidden", "true");
                    var copy = pic.cloneNode(true);
                    if (copy.alt !== undefined) { copy.alt = ""; }
                    m.appendChild(copy);
                    card.appendChild(m);
                }
                if (mode === "spotlight" && pic.tagName === "IMG") {
                    var back = document.createElement("span");
                    back.className = "kei-backdrop";
                    back.setAttribute("aria-hidden", "true");
                    var b2 = pic.cloneNode(true);
                    b2.alt = "";
                    back.appendChild(b2);
                    card.insertBefore(back, card.firstChild);
                }
            }
            function missing() {
                if (img && img.parentNode) { img.parentNode.removeChild(img); }
                if (drawn) { done(blank(it)); } else if (card.parentNode) { card.parentNode.removeChild(card); }
                settled();
            }
            var img = null;
            if (it.cover) {
                img = document.createElement("img");
                img.loading = staged || mode === "ribbon" ? "eager" : "lazy";
                img.alt = it.title || "";
                img.draggable = false;
                // Amazon answers a missing cover with a 1x1 image.
                img.addEventListener("load", function () {
                    if (img.naturalWidth <= 1) { missing(); return; }
                    done(img);
                    settled();
                });
                img.addEventListener("error", missing);
                img.src = it.cover;
                face.appendChild(img);   // in the page, so a lazy one loads when it comes into view
            } else {
                done(blank(it));
                setTimeout(settled, 0);
            }
            if (K.overlay || mode === "spotlight") {
                var info = document.createElement("span");
                info.className = "kei-card-info";
                var s = document.createElement("strong");
                s.textContent = it.title || "";
                info.appendChild(s);
                [it.author, it.callnumber].forEach(function (v) {
                    if (v) { var x = document.createElement("span"); x.textContent = v; info.appendChild(x); }
                });
                // A list may hold a title with no copy (an e-book): no badge then.
                if (it.total !== 0) {
                    var badge = document.createElement("em");
                    badge.className = "kei-badge" + (it.available > 0 ? "" : " kei-out");
                    badge.textContent = it.available > 0 ? C.text.available : C.text.out;
                    info.appendChild(badge);
                }
                (mode === "spotlight" ? card : face).appendChild(info);
            }
            if (mode === "wall") {
                var cap = document.createElement("span");
                cap.className = "kei-caption";
                cap.textContent = it.title || "";
                card.appendChild(cap);
            }
            if (K.hover === "tilt" && (mode === "flat" || mode === "ribbon")) {
                card.addEventListener("mousemove", function (e) {
                    var r = card.getBoundingClientRect();
                    var x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
                    card.style.transform = "perspective(600px) rotateY(" + (x * 12) + "deg) rotateX(" + (-y * 12) + "deg)";
                });
                card.addEventListener("mouseleave", function () { card.style.transform = ""; });
            }
            track.appendChild(card);
        });
        place(box);
        return box;
    }

    // blank(it): the cover drawn for a title with none.
    function blank(it) {
        var el = document.createElement("span");
        el.className = "kei-blank";
        el.setAttribute("role", "img");
        el.setAttribute("aria-label", (it.title || "") + " (" + C.text.no_cover + ")");
        var t = document.createElement("b");
        t.textContent = it.title || "";
        el.appendChild(t);
        if (it.author) {
            var a = document.createElement("i");
            a.textContent = it.author;
            el.appendChild(a);
        }
        var n = document.createElement("small");
        n.textContent = C.text.no_cover;
        el.appendChild(n);
        return el;
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

    // autoplay(box, step, K): every K.speed ms, for ever (a click restarts the count).
    function autoplay(box, step, K) {
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

    function flat(box, track, K) {
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
        restart = autoplay(box, step, K);
    }

    function coverflow(box, track, K) {
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
        controls(box, track, step);
        layout();
        navButtons(box, step);
        restart = autoplay(box, step, K);
    }

    // controls(box, track, step): swipe (touch or mouse drag) and the arrow keys.
    function controls(box, track, step) {
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
    }

    function clamp01(v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }

    // Where each card of a stage stands, from d: how far it is from the
    // centre (in cards, with a fraction while they move; -n/2 to n/2).
    var STAGES = {
        // The ring seen from above: the far covers small and high.
        ring: function (card, d, n, track) {
            var r = Math.max(110, Math.min((track.clientWidth || 800) * .36, 480));
            var t = d * 2 * Math.PI / n, c = Math.cos(t);
            card.style.transform = "translate3d(" + (r * Math.sin(t)).toFixed(1) + "px," + (-(1 - c) * 28).toFixed(1) +
                "px," + (r * (c - 1)).toFixed(1) + "px)";
            card.style.zIndex = String(Math.round(500 + c * 400));
            card.style.opacity = (.62 + .38 * (c + 1) / 2).toFixed(3);
            card.style.pointerEvents = "";
        },
        // The inside of a curve: the centre one larger and closer.
        wall: function (card, d, n, track) {
            var a = Math.abs(d), side = d < 0 ? -1 : 1, near = clamp01(1 - a);
            var shown = clamp01(Math.min(4, (n - 1) / 2) + .6 - a);
            var x = d * Math.min(132, (track.clientWidth || 800) / 7) + side * Math.min(a, 1) * 34;
            card.style.transform = "translateX(" + x.toFixed(1) + "px) translateZ(" + (near * 70).toFixed(1) +
                "px) rotateY(" + Math.max(-50, Math.min(50, d * 15)).toFixed(2) + "deg)";
            card.style.zIndex = String(100 - Math.round(a * 10));
            card.style.opacity = shown.toFixed(3);
            card.style.pointerEvents = shown < .2 ? "none" : "";
        },
        // A hand of cards.
        fan: function (card, d, n) {
            var a = Math.abs(d), shown = clamp01(Math.min(3, (n - 1) / 2) + .6 - a);
            card.style.transform = "translateX(" + (d * 54).toFixed(1) + "px) translateY(" + (a * a * 5).toFixed(1) +
                "px) rotate(" + (d * 9).toFixed(2) + "deg) scale(" + (1 + .08 * clamp01(1 - a)).toFixed(3) + ")";
            card.style.zIndex = String(100 - Math.round(a * 10));
            card.style.opacity = shown.toFixed(3);
            card.style.pointerEvents = shown < .2 ? "none" : "";
        },
        // One at a time: the next one slides in as this one fades out.
        spotlight: function (card, d) {
            var a = Math.abs(d), shown = clamp01(1 - a * 1.6);
            card.style.transform = "translateX(" + (d * 60).toFixed(1) + "px)";
            card.style.zIndex = String(100 - Math.round(a * 10));
            card.style.opacity = shown.toFixed(3);
            card.style.visibility = shown > 0 ? "" : "hidden";
            card.style.pointerEvents = a > .5 ? "none" : "";
        }
    };

    // spin(box, track, K, mode): the stages above. pos glides towards
    // target frame by frame, so the cards follow their true path (round the
    // ring, along the curve) and never jump; a click on a side card brings
    // it to the centre by the shorter way.
    function spin(box, track, K, mode) {
        var cards = Array.prototype.slice.call(track.children);
        var n = cards.length, pos = 0, target = 0, raf = 0, dots = [];
        var place = STAGES[mode];
        var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        var frame = window.requestAnimationFrame || function (f) { return setTimeout(f, 16); };
        function wrap(d) { d = ((d % n) + n) % n; return d >= n / 2 ? d - n : d; }
        function centre() { return ((Math.round(pos) % n) + n) % n; }
        function draw() {
            var c = centre();
            cards.forEach(function (card, i) {
                place(card, n === 1 ? 0 : wrap(i - pos), n, track);
                card.classList.toggle("kei-center", i === c);
                card.tabIndex = i === c ? 0 : -1;
                card.setAttribute("aria-hidden", i === c ? "false" : "true");
            });
            dots.forEach(function (dot, i) { dot.setAttribute("aria-current", i === c ? "true" : "false"); });
        }
        function tick() {
            var gap = target - pos;
            if (still || Math.abs(gap) < .003) { pos = target; raf = 0; draw(); return; }
            pos += gap * .14;
            draw();
            raf = frame(tick);
        }
        function go() { if (!raf) { raf = frame(tick); } }
        var restart = function () {};
        function step(dir, byHand) {
            target += dir;
            go();
            if (byHand) { restart(); }
        }
        function show(i) {
            var from = Math.round(target);
            target = from + wrap(i - from);
            go();
            restart();
        }
        cards.forEach(function (card, i) {
            card.addEventListener("click", function (e) {
                if (!card.classList.contains("kei-center")) { e.preventDefault(); show(i); }
            });
        });
        if (mode === "spotlight" && n > 1 && n <= 24) {
            var row = document.createElement("div");
            row.className = "kei-dots";
            cards.forEach(function (card, i) {
                var dot = document.createElement("button");
                dot.type = "button";
                dot.setAttribute("aria-label", String(i + 1) + " / " + n);
                dot.addEventListener("click", function () { show(i); });
                row.appendChild(dot);
                dots.push(dot);
            });
            box.appendChild(row);
        }
        controls(box, track, step);
        window.addEventListener("resize", draw);
        draw();
        if (n > 1) {
            navButtons(box, step);
            restart = autoplay(box, step, K);
        }
    }

    // ribbon(box, track, K): the covers glide by for ever (a CSS animation
    // over the cards twice in a row); held by a pointer or the keyboard.
    // Still (a strip to scroll, with the arrows) with autoplay off, "reduce
    // motion", or too few covers to fill the width.
    function ribbon(box, track, K) {
        var belt = document.createElement("div");
        belt.className = "kei-belt";
        while (track.firstChild) { belt.appendChild(track.firstChild); }
        track.appendChild(belt);
        var originals = Array.prototype.slice.call(belt.children);
        var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (!K.autoplay || still || belt.scrollWidth <= track.clientWidth + 8) {
            box.classList.add("kei-still");
            navButtons(box, function (dir) {
                var c = belt.firstElementChild;
                track.scrollBy({ left: dir * (c ? c.getBoundingClientRect().width + 16 : 160), behavior: "smooth" });
            });
            return;
        }
        originals.forEach(function (c) {
            var copy = c.cloneNode(true);
            copy.setAttribute("aria-hidden", "true");
            copy.tabIndex = -1;
            belt.appendChild(copy);
        });
        // K.speed: the time each cover takes to pass, about half the turn of the strip.
        belt.style.setProperty("--kei-ribbon-time", Math.round(originals.length * K.speed / 2000 * 1.6) + "s");
    }
})();"""

# The staff home page (mainpage.pl): the buttons above the module tiles.
_STAFF_JS = r"""(function () {
    "use strict";
    var C = __CONFIG__;
    var root = document.documentElement;
    var KEY = "kei_staff_theme";
    function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
    function save(t) { try { localStorage.setItem(KEY, t); } catch (e) { /* private window */ } }
    if (C.dark_switch) { root.setAttribute("data-kei-theme", stored() === "dark" ? "dark" : "light"); }
__LINK_NAV__

    function ready(fn) {
        if (document.readyState !== "loading") { fn(); } else { document.addEventListener("DOMContentLoaded", fn); }
    }

    // The light/dark switch at the foot of the page, with the languages
    // (Koha's #changelanguage bar), as on the OPAC (Paulo, 2026-10-31); a
    // corner button when Koha shows no language bar (one language only).
    ready(function () {
        if (!C.dark_switch || document.getElementById("kei-theme-switch")) { return; }
        var b = document.createElement("button");
        b.type = "button";
        b.id = "kei-theme-switch";
        b.title = C.switch_title;
        b.setAttribute("aria-label", C.switch_title);
        b.innerHTML = __SWITCH_ICONS__;
        b.addEventListener("click", function () {
            var t = root.getAttribute("data-kei-theme") === "dark" ? "light" : "dark";
            root.setAttribute("data-kei-theme", t);
            save(t);
        });
        var menu = document.querySelector("#changelanguage #i18nMenu, #changelanguage .navbar-nav");
        if (menu) {
            var li = document.createElement("li");
            li.className = "nav-item";
            li.style.display = "flex";
            li.appendChild(b);
            menu.appendChild(li);
            var r = b.getBoundingClientRect();
            if (r.width && r.right <= (window.innerWidth || document.documentElement.clientWidth)) { return; }
            li.parentNode.removeChild(li);
        }
        b.className = "kei-theme-floating";
        document.body.appendChild(b);
    });

    ready(function () {
        if (!C.links) { return; }
        var home = (document.body && document.body.id === "main_intranet-main") || /\/mainpage\.pl$/.test(location.pathname);
        if (!home || document.getElementById("kei-staff-links")) { return; }
        var nav = linkNav("kei-staff-links", C.links, C.label);
        if (!nav) { return; }
        var tiles = document.querySelector("#container-main .biglinks-list");
        var row = tiles && tiles.closest ? tiles.closest(".row") : null;
        var main = document.getElementById("container-main") || document.querySelector(".main");
        if (row && row.parentNode) {
            row.parentNode.insertBefore(nav, row);
        } else if (main) {
            main.insertBefore(nav, main.firstChild);
        }
    });
})();"""

JS_TEXT = {"switch_title": "Light / dark mode", "available": "Available", "out": "On loan", "prev": "Previous",
           "next": "Next", "links": "Quick access", "no_cover": "No cover"}


def js_config(cfg: dict, text: dict | None = None) -> dict:
    cfg = normalize(cfg)
    car = cfg["carousel"]
    look = {k: car[k] for k in ("count", "autoplay", "speed", "hover", "overlay", "mode", "reflect", "missing")}
    return {
        "default_theme": cfg["default_theme"],
        "dark_switch": cfg["dark_switch"],
        "wallpaper": bool(cfg["background"]["url"]),
        "empty_columns": cfg["ghost"]["empty_columns"],
        "news_buttons": cfg["news_buttons"],
        "carousel": ({**look, "title": car["title"], "source": car["source"], "shelf": car["shelf"],
                      "feed": f"{LIST_FEED}{car['shelf']}.json" if car["source"] == "list" else FEED_URL}
                     if car["enabled"] else None),
        # KEI.listCarousel() and <div data-kei-list="N">: the same look.
        "lists": {**look, "feed": LIST_FEED, "always": car["lists"]} if car["enabled"] or car["lists"] else None,
        "links": _links_conf(cfg["links"]) if links_on(cfg["links"]) else None,
        "text": {**JS_TEXT, **{k: v for k, v in (text or {}).items() if k in JS_TEXT}},
    }


def _links_conf(lk: dict) -> dict:
    return {"style": lk["style"], "layout": lk["layout"], "items": lk["items"]}


# The light/dark switch's face: a moon in light mode (go dark), a sun in
# dark mode (go light), drawn in the text colour. The old half-moon emoji
# came out as a purple and yellow blob that nobody read as a switch (Paulo,
# 2026-10-31).
_SWITCH_ICONS = ('<svg class="kei-ico-moon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                 '<path fill="currentColor" d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
                 '<svg class="kei-ico-sun" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                 '<circle cx="12" cy="12" r="4.5" fill="currentColor"/><g stroke="currentColor" '
                 'stroke-width="2" stroke-linecap="round"><path d="M12 1.5v2.5M12 20v2.5M1.5 12H4M20 12h2.5'
                 'M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8"/></g></svg>')
# Which face shows (OPAC and staff).
SWITCH_ICON_CSS = """#kei-theme-switch { display: inline-flex; align-items: center; justify-content: center; }
#kei-theme-switch svg { width: 1.1em; height: 1.1em; display: block; }
#kei-theme-switch .kei-ico-sun, html[data-kei-theme="dark"] #kei-theme-switch .kei-ico-moon { display: none; }
html[data-kei-theme="dark"] #kei-theme-switch .kei-ico-sun { display: block; }"""


def _script(template: str, conf: dict) -> str:
    conf = json.dumps(conf, ensure_ascii=True, sort_keys=True).replace("</", "<\\/")
    icons = json.dumps(_SWITCH_ICONS).replace("</", "<\\/")
    return (template.replace("__LINK_NAV__", _LINK_NAV).replace("__CONFIG__", conf)
            .replace("__SWITCH_ICONS__", icons))


def js_block(cfg: dict, text: dict | None = None) -> str:
    return "\n".join([JS_BEGIN, _script(_JS, js_config(cfg, text)), JS_END]) + "\n"


def staff_js_config(cfg: dict, text: dict | None = None) -> dict:
    cfg = normalize(cfg)
    words = {**JS_TEXT, **(text or {})}
    return {"links": _links_conf(cfg["staff_links"]),
            "label": words["links"], "dark_switch": staff_dark(cfg), "switch_title": words["switch_title"]}


def staff_js_on(cfg: dict) -> bool:
    """staff.js goes into IntranetUserJS: home page buttons or the switch."""
    return links_on(normalize(cfg)["staff_links"]) or staff_dark(cfg)


def staff_js_block(cfg: dict, text: dict | None = None) -> str:
    """IntranetUserJS: the staff home page buttons and the light/dark switch."""
    return "\n".join([JS_BEGIN, _script(_STAFF_JS, staff_js_config(cfg, text)), JS_END]) + "\n"


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
    """The address of a picture copied to the server: the OPAC's folder, or
    the staff interface's for the staff-* roles (another web root)."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
    base = STAFF_CUSTOM_URL if role.startswith("staff-") else CUSTOM_URL
    return f"{base}/{local_name(role, path)}?v={digest}"


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
    colours or has home page buttons), staff.js (the buttons), prefs (NAME<TAB>VALUE), carousel (on N|off), assets/ (the
    server files to publish) and the HTML customizations (contents.list,
    contents/, contents.json). Private (0700)."""
    cfg = normalize(cfg)
    work = Path(tempfile.mkdtemp(prefix="kei-opac-"))
    os.chmod(work, 0o700)
    (work / "user.css").write_text(css_block(cfg), encoding="utf-8")
    (work / "user.js").write_text(js_block(cfg, text), encoding="utf-8")
    # No staff.css / staff.js: the task takes our blocks out of the staff
    # interface's preferences again.
    if staff_active(cfg):
        (work / "staff.css").write_text(staff_css_block(cfg), encoding="utf-8")
    if staff_js_on(cfg):
        (work / "staff.js").write_text(staff_js_block(cfg, text), encoding="utf-8")
    prefs = []
    car = cfg["carousel"]
    if car["enabled"] or car["lists"]:
        prefs.append(("OPACAmazonCoverImages", "1"))
        if car["amazon_tag"]:
            prefs.append(("AmazonAssocTag", car["amazon_tag"]))
    if cfg["favicon"]["url"]:
        prefs.append(("OpacFavicon", cfg["favicon"]["url"]))
    if cfg["staff"]["enabled"] and cfg["staff"]["favicon"]["url"]:
        prefs.append(("IntranetFavicon", cfg["staff"]["favicon"]["url"]))
    (work / "prefs").write_text("".join(f"{k}\t{v}\n" for k, v in prefs), encoding="utf-8")
    on = car["enabled"] or car["lists"]
    (work / "carousel").write_text(f"on {car['count']}\n" if on else "off\n", encoding="utf-8")
    assets = work / "assets"
    assets.mkdir()
    for role, src in files.items():
        shutil.copyfile(src, assets / local_name(role, src))
    # Koha's HTML customizations: contents.list says which of the three
    # places the panel fills (on) or gives back to the library (off);
    # contents/<location>.html is what goes there; contents.json the form's
    # settings, for theme-settings.json.
    folder = work / "contents"
    folder.mkdir()
    listing = []
    for location, markup in contents(cfg, text).items():
        listing.append(f"{location}\t{'on' if markup else 'off'}\n")
        if markup:
            (folder / f"{location}.html").write_text(markup + "\n", encoding="utf-8")
    (work / "contents.list").write_text("".join(listing), encoding="utf-8")
    (work / "contents.json").write_text(json.dumps(contents_settings(cfg), ensure_ascii=False, sort_keys=True),
                                        encoding="utf-8")
    return work
