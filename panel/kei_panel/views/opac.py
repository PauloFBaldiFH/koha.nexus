"""OpacView: the public catalogue's look, written into Koha in one click.

Every setting is a field of this screen; opac_theme.py turns them into the
marked blocks of OpacUserCSS and OpacUserJS, and
`config.sh --task opac-theme-apply` puts them in Koha (backup first, the
rest of both preferences kept). The settings travel inside the CSS block
(/* KEI-THEME-DATA */): opening the screen reads them back from Koha.

More boxes: the quick access buttons of the home page (icon, text,
address, tab and order; solid, gradient, glass or brushed metal; one per
line or two columns), the same buttons for the staff interface's home page
(IntranetUserJS) and the staff interface's look ("Apply color theme to
Staff Client": IntranetUserCSS, with the OPAC's materials (textures, blur,
opacity, corners) and colour pickers, its own type size, contrast and table
density, never the OPAC's widgets). "Copy OPAC preset" fills the staff
fields with the OPAC's material, colours and pictures in one click.

"Sync current OPAC settings" reads what is live in Koha (OpacUserCSS,
OpacUserJS, the staff preferences, OpacMainUserBlock) into the fields and
shows what it found; nothing is written until Apply.

Pictures: a file on this server (copied to Koha's public images folder), a
file sent to an image host (ImgBB with an API key, Cloudinary with an
unsigned upload preset; the keys stay in the panel's private file) or a
direct https address (Postimages and any other host).
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, Static, Switch, TextArea

from .. import opac_theme as ot
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, TextScreen
from ..tasks import Reporter, TaskFailed
from ..widgets.colorpick import ColorPicker
from ..widgets.linkrow import LinkRow
from ..widgets.slider import Slider
from .base import SectionView

ASSET_LABELS = {"background": "Wallpaper", "logo": "Logo", "favicon": "Favicon", "login": "Login banner",
                "header": "Header picture"}
FILE_SOURCES = ("local", "imgbb", "cloudinary")
# The login pages: settings side -> (box id, title, picture name).
LOGIN_BOXES = {"opac": ("o-login-opac", "OPAC login page"), "staff": ("o-login-staff", "Staff login page")}
# The panel's own news item of each side: settings side -> (box id, title).
NEWS_BOXES = {"opac": ("o-newsitem-opac", "OPAC news"), "staff": ("o-newsitem-staff", "Staff news")}
# The credits text: field -> (label, example, max length). One text area,
# "Label: value" lines (the label in English or in the panel's language)
# and "text | address" lines for the other links.
CREDIT_FIELDS = {
    "name": ("Library name", "Biblioteca Municipal", ot.CREDITS_TEXT_MAX),
    "address": ("Address", "Rua Exemplo, 123", ot.CREDITS_TEXT_MAX),
    "phone": ("Phone", "(00) 0000-0000", 40), "whatsapp": ("WhatsApp", "(00) 00000-0000", 30),
    "email": ("E-mail", "contato@biblioteca.gov.br", 120), "website": ("Website", "https://biblioteca.gov.br", 300),
    "hours": ("Opening hours", "", ot.CREDITS_TEXT_MAX), "instagram": ("Instagram", "https://instagram.com/biblioteca", 300),
    "facebook": ("Facebook", "https://facebook.com/biblioteca", 300),
    "youtube": ("YouTube", "https://youtube.com/@biblioteca", 300), "cnpj": ("CNPJ", "00.000.000/0000-00", 30),
    "note": ("Note", "", ot.CREDITS_TEXT_MAX),
}
CREDITS_NOTE = ("One line per item, in the order the footer shows them: Field: value for the fields below, "
                "other links as text | address (at most 6), and any other line as it is. No HTML to type: "
                "the footer is built from these lines.")


def _picture(raw: dict, name: str) -> dict:
    """The settings entry of a picture: raw[name], raw["staff"][...] for
    staff-*, the login banners' raw["login"][side]["image"]."""
    for side, role in ot.LOGIN_ASSETS.items():
        if name == role:
            return raw["login"][side]["image"]
    return raw["staff"][name.removeprefix("staff-")] if name.startswith("staff-") else raw[name]


SLIDERS = {   # id: (label, unit, step)
    "blur": ("Blur", "px", 1),
    "opacity": ("Opacity", "%", 1),
    "radius_block": ("Blocks", "px", 1),
    "radius_input": ("Inputs", "px", 1),
    "radius_button": ("Buttons", "px", 1),
    "film": ("Legibility film", "%", 5),
}
# The staff content card: where the readable backdrop sits. Its opacity is
# the Opacity slider and its corners the Blocks slider, as on every card.
CARD_HELP = ("One card per section: each of Koha's boxes is a card. One card for the whole page: the content "
             "and its sidebar sit on one card and the boxes inside it are clear. The Opacity and Blocks sliders "
             "set its transparency and corners.")
# The staff glass top bar: id: (label, unit).
STAFF_HEADER_SLIDERS = {"header_opacity": ("Top bar opacity", "%"), "header_blur": ("Top bar blur", "px")}
# The three corner sliders: what each one rounds (border-radius).
PAINT_NOTE = ("The block background takes the texture and opacity above. Each of the other colours has a "
              "texture and an opacity of its own (0% clear, 100% solid).")
PAINT_HELP = {
    "accent": "The highlight: main buttons (search, place hold, the news buttons), active tabs and the focus "
              "ring. Text keeps its own colours; links take the accent only when it is a real colour (not black, "
              "grey or white).",
    "accent2": "Secondary buttons in the second colour. As the Material: the second colour only tints the page "
               "and the secondary buttons keep the block background.",
    "page": "The page under the blocks (without a wallpaper). A lower opacity makes the colour paler.",
}
GATE_NOTE = ("The fields show what Koha holds now: OpacUserCSS, OpacUserJS, IntranetUserCSS, IntranetUserJS, "
             "the news and the HTML customizations. Sync with the instance to read them; the fields appear after "
             "it, filled from Koha.")
# The view's own parts that stay while the fields wait for the instance.
GATE_KEEP = ("o-intro", "o-gate")
RADIUS_HELP = {
    "radius_block": "Rounded corners (border-radius) of the blocks: header, panels, cards and boxes. More "
                    "pixels make the corners rounder; 0 makes them square.",
    "radius_input": "Rounded corners (border-radius) of the fields: search bar, text boxes and lists. More "
                    "pixels make the corners rounder; 0 makes them square.",
    "radius_button": "Rounded corners (border-radius) of the buttons. More pixels make the corners rounder; "
                     "0 makes them square.",
}
RADIUS_NOTE = ("Blocks, Inputs and Buttons set the rounded corners (border-radius) of those elements: raising "
               "the value in px curves the corners more, lowering it makes them straighter, 0 makes them square.")
GHOST = {"rss": "RSS icons", "cart_badge": "Cart badge", "cart": "Cart (menu and Add to cart)",
         "community": "Community links", "empty_columns": "Empty table columns"}
POSTIMAGES_URL = "https://postimages.org/"
POSTIMAGES_NOTE = ("Free picture hosting, no account needed: send the picture at Postimages, copy its Direct link "
                   "(ends in .png or .jpg) and paste it here with the source Direct URL.")
ICON_EXAMPLES = "📖 📜 💬 📧 📷 🔐 📅 ❓ fa-book"
# The two sets of quick access buttons: settings key -> id prefix of their fields.
LINK_SETS = {"links": "o-link", "staff_links": "o-slink"}


STYLE_NOTE = ("Style details: the cards' shadow, the room around the content, outline or filled icons, a "
              "faint pattern on the page (without a wallpaper), tables and menus in the texture, the login page "
              "and the hover animations. The first choice of each list is the look as it was.")


def _style_rows(prefix: str, values: dict):
    """The style detail lists (ot.STYLE) of one side, ids prefix-<key>."""
    yield Static(t(STYLE_NOTE), classes="ai-note", markup=False)
    for key, (label, choices) in ot.STYLE.items():
        yield from _row(t(label), Select([(t(v), k) for k, v in choices.items()], value=values[key],
                                         allow_blank=False, id=f"{prefix}-{key}"))


class OpacView(SectionView):
    loaded = False
    restores_seen = 0

    def __init__(self, section):
        super().__init__(section)
        self.cfg = ot.normalize({})
        self.carousel_on = False
        self.feed_items = ""
        self.link_rows = 0

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
        yield Static(t("The look of the public catalogue (OPAC): textures, rounded corners, wallpaper, logo, a "
                       "light/dark switch for the readers, a New arrivals carousel with the Amazon covers and the "
                       "clean-up of empty parts. Apply writes it into Koha after a backup; Remove brings Koha's own "
                       "look back. Your own OpacUserCSS and OpacUserJS are kept."),
                     classes="view-prompt", markup=False, id="o-intro")
        # The gate: the fields only after reading the instance. What Koha
        # holds (OpacUserCSS, OpacUserJS, IntranetUserCSS, IntranetUserJS,
        # the news and HTML customizations) is the base of every field,
        # never the panel's own copy or its factory settings (Paulo, 2026-10-31).
        with Vertical(id="o-gate", classes="opac-box"):
            yield Static(t(GATE_NOTE), classes="ai-note", markup=False)
            with Horizontal(classes="quick-actions"):
                yield Button(t("Sync with the instance"), id="o-gate-sync", variant="primary")
            yield Static("", id="o-gate-report", markup=False)
        with Horizontal(classes="quick-actions"):
            yield Button(t("Apply"), id="o-apply", classes="small", variant="success")
            yield Button(t("Preview"), id="o-preview", classes="small")
            yield Button(t("Sync current OPAC settings"), id="o-sync", classes="small")
            yield Button(t("Refresh carousel"), id="o-refresh", classes="small")
            yield Button(t("Image host keys"), id="o-keys", classes="small")
            yield Button(t("Remove"), id="o-remove", classes="small", variant="error")
        yield Label("", id="o-summary", classes="view-prompt")
        c = self.cfg
        with Vertical(id="o-material", classes="opac-box"):
            yield Static(t("Ready-made looks: colours, texture, opacity, blur and corners chosen to go together, "
                           "for the OPAC and the staff interface at once. Pictures, texts and buttons stay. "
                           "Fine-tune the fields after; Apply writes it into Koha."), classes="ai-note", markup=False)
            yield from _row(t("Ready-made look"),
                            Select(self._preset_options(), value=next(iter(ot.PRESETS)),
                                   allow_blank=False, id="o-preset"))
            with Horizontal(classes="quick-actions"):
                yield Button(t("Use this look"), id="o-preset-use", classes="small")
                yield Button(t("Save current look"), id="o-preset-save", classes="small",
                             tooltip=t("Keep the fields as they are now as one of your looks (up to ${n}).",
                                       n=ot.MAX_USER_PRESETS))
                yield Button(t("Delete saved look"), id="o-preset-delete", classes="small")
            yield from _row(t("Texture"), Select([(t(v), k) for k, v in ot.TEXTURES.items()], value=c["texture"],
                                                 allow_blank=False, id="o-texture"))
            for key in ("blur", "opacity"):
                yield from self._slider(key)
            bars = (t("Hue"), t("Saturation"), t("Lightness"))
            # The block background's texture and opacity are the two above.
            yield ColorPicker(t("Block background"), c["surface"], "o-surface", bars, id="o-pick-surface")
            yield Static(t(PAINT_NOTE), classes="ai-note", markup=False)
            yield ColorPicker(t("Accent colour"), c["accent"], "o-accent", bars, id="o-pick-accent")
            yield from self._paint_rows("accent")
            yield ColorPicker(t("Second colour"), c["accent2"], "o-accent2", bars, id="o-pick-accent2")
            yield from self._paint_rows("accent2")
            yield from _row(t("Page colour"), Switch(bool(c["page"]), id="o-page-on"))
            yield ColorPicker(t("Page background"), c["page"] or "#f3f4f6", "o-page", bars, id="o-pick-page")
            yield from self._paint_rows("page")
            yield Static(t(RADIUS_NOTE), classes="ai-note", markup=False)
            for key in RADIUS_HELP:
                yield from self._slider(key)
            yield from _style_rows("o-style", c)
        with Vertical(id="o-images", classes="opac-box"):
            yield Static(t("A file on this server (PNG, JPEG, GIF, WebP or ICO; SVG is refused), a file sent to "
                           "ImgBB or Cloudinary, or a direct https address (Postimages and other hosts)."),
                         classes="ai-note", markup=False)
            yield LinkRow(POSTIMAGES_URL, t(POSTIMAGES_NOTE), "Postimages", id="o-postimages")
            for name in ot.ASSETS:
                yield from self._asset_row(name, c[name])
        with Vertical(id="o-dark", classes="opac-box"):
            yield from self._slider("film")
            yield from _row(t("Light/dark switch"), Switch(c["dark_switch"], id="o-dark_switch"))
            yield from _row(t("Default theme"), Select([(t(v), k) for k, v in ot.THEMES.items()],
                                                       value=c["default_theme"], allow_blank=False,
                                                       id="o-default_theme"))
        with Vertical(id="o-header", classes="opac-box"):
            yield Static(t("The header at the top of every OPAC page: the top bar (logo, cart, lists and "
                           "login), then the search bar. Large: a taller header with the Header picture "
                           "covering all of it (without a picture, the two colours), the bar and the search "
                           "over it in white."), classes="ai-note", markup=False)
            yield from _row(t("Top bar"), Switch(c["header_bar"], id="o-header_bar"))
            yield from _row(t("Header style"), Select([(t(v), k) for k, v in ot.HEADER_STYLES.items()],
                                                      value=c["header_style"], allow_blank=False,
                                                      id="o-header_style"))
            yield from _row(t("Header height"), Slider(*ot.RANGES["header_height"], c["header_height"], step=10,
                                                       unit="px", id="o-header_height"))
        car = c["carousel"]
        with Vertical(id="o-carousel", classes="opac-box"):
            yield Static(t("The newest titles with a copy on the shelf and a real cover, or a Koha list, rebuilt "
                           "every night. Each cover opens the record. Turns on OPACAmazonCoverImages."),
                         classes="ai-note", markup=False)
            yield from _row(t("Show"), Switch(car["enabled"], id="o-car-enabled"))
            yield from _row(t("Source"), Select([(t(v), k) for k, v in ot.CAROUSEL_SOURCES.items()],
                                                value=car["source"], allow_blank=False, id="o-car-source"))
            yield from _row(t("List number"), Input(str(car["shelf"] or ""), id="o-car-shelf", max_length=9,
                                                    restrict=r"[0-9]*", placeholder="shelfnumber="))
            yield Static(t("A public list made in Lists (Koha's virtual shelves), in its own order. Covers: "
                           "the one uploaded in Koha, else OpenLibrary, else Amazon. Any page can also show "
                           "a list: <div data-kei-list=\"7\"></div> in a news item, or "
                           "KEI.listCarousel(7, \"#box\") in OpacUserJS."), classes="ai-note", markup=False)
            yield from _row(t("List feeds with the carousel off"), Switch(car["lists"], id="o-car-lists"))
            yield from _row(t("Style"), Select([(t(v), k) for k, v in ot.CAROUSEL_MODES.items()], value=car["mode"],
                                               allow_blank=False, id="o-car-mode"))
            yield from _row(t("Reflection"), Switch(car["reflect"], id="o-car-reflect"))
            yield from _row(t("Titles with no cover"),
                            Select([(t(v), k) for k, v in ot.CAROUSEL_MISSING.items()], value=car["missing"],
                                   allow_blank=False, id="o-car-missing"))
            yield Static(t("Reflection: a mirror image under each cover (not on the bookshelf, the fan or the "
                           "spotlight). A title with no cover can be left out or get a cover drawn in the accent "
                           "colours, with its title and author."), classes="ai-note", markup=False)
            yield from _row(t("Title"), Input(car["title"], id="o-car-title", max_length=60))
            yield from _row(t("Autoplay"), Switch(car["autoplay"], id="o-car-autoplay"))
            yield from _row(t("Speed"), Slider(*ot.CAROUSEL_RANGES["speed"], car["speed"], step=500, unit=" ms",
                                               id="o-speed"))
            yield from _row(t("Titles"), Slider(*ot.CAROUSEL_RANGES["count"], car["count"], id="o-count"))
            yield from _row(t("Hover effect"), Select([(t(v), k) for k, v in ot.HOVERS.items()], value=car["hover"],
                                                      allow_blank=False, id="o-car-hover"))
            yield from _row(t("Details"), Switch(car["overlay"], id="o-car-overlay"))
            yield from _row(t("Amazon tag"), Input(car["amazon_tag"], id="o-car-tag", max_length=40,
                                                   placeholder=t("optional")))
        with Vertical(id="o-links", classes="opac-box"):
            yield Static(t("Buttons at the top of the home page, like a link tree: an icon or emoji, the text, "
                           "the address, where it opens and its place in the list (1 comes first).") + "  "
                         + ICON_EXAMPLES, classes="ai-note", markup=False)
            yield from self._link_set("links")
        with Vertical(id="o-slinks", classes="opac-box"):
            yield Static(t("The same buttons on the staff interface's home page, above the module tiles: "
                           "shortcuts to the library's own workflows (IntranetUserJS), in the staff colours."),
                         classes="ai-note", markup=False)
            yield from self._link_set("staff_links")
        st = c["staff"]
        with Vertical(id="o-staff", classes="opac-box"):
            yield Static(t("The staff interface's own look (IntranetUserCSS), set apart from the public "
                           "catalogue: the OPAC's textures, blur, opacity and rounded corners, its own colours for "
                           "the top bar, the quick search bar and the buttons, the home page modules as cards, the "
                           "news column, the text size, contrast and table density. Copy OPAC preset brings the "
                           "OPAC's look here in one click."), classes="ai-note", markup=False)
            yield from _row(t("Apply color theme to Staff Client"), Switch(st["enabled"], id="o-staff-enabled"))
            with Horizontal(classes="quick-actions"):
                yield Button(t("Copy OPAC preset"), id="o-staff-copy", classes="small",
                             tooltip=t("The OPAC's texture, sliders, colours and pictures into the staff fields; "
                                       "Apply writes them."))
            yield from _row(t("Texture"), Select([(t(v), k) for k, v in ot.TEXTURES.items()], value=st["texture"],
                                                 allow_blank=False, id="o-staff-texture"))
            for key in ot.STAFF_MATERIAL:
                label, unit, step = SLIDERS[key]
                if key == next(iter(RADIUS_HELP)):
                    yield Static(t(RADIUS_NOTE), classes="ai-note", markup=False)
                yield from _row(t(label), _tip(Slider(*ot.RANGES[key], st[key], step=step, unit=unit,
                                                      id=f"o-staff-{key}"), RADIUS_HELP.get(key, "")))
            yield from _row(t("Top bar opacity of its own"),
                            _tip(Switch(st["header_glass"], id="o-staff-header_glass"),
                                 "Off: the top bar and the quick search bar follow the blocks' opacity and blur. "
                                 "On: the two sliders below set them apart. The links, the search field and the "
                                 "menus always stay fully opaque."))
            for key, (label, unit) in STAFF_HEADER_SLIDERS.items():
                yield from _row(t(label), Slider(*ot.STAFF_HEADER[key], st[key], unit=unit, id=f"o-staff-{key}"))
            yield from _row(t("Top bar colour"),
                            _tip(Switch(bool(st["bar"]), id="o-staff-bar-on"),
                                 "Off: a dark bar that goes with any accent colour. On: the colour below. "
                                 "The bar's text turns light or dark to stay readable."))
            yield ColorPicker(t("Top bar"), st["bar"] or ot.staff_bar(st), "o-staff-bar", bars,
                              id="o-pick-staff-bar")
            yield ColorPicker(t("Block background"), st["surface"], "o-staff-surface", bars,
                              id="o-pick-staff-surface")
            yield Static(t(PAINT_NOTE), classes="ai-note", markup=False)
            yield ColorPicker(t("Accent colour"), st["accent"], "o-staff-accent", bars, id="o-pick-staff-accent")
            yield from self._paint_rows("accent", staff=True)
            yield ColorPicker(t("Second colour"), st["accent2"], "o-staff-accent2", bars, id="o-pick-staff-accent2")
            yield from self._paint_rows("accent2", staff=True)
            yield from _row(t("Page colour"), Switch(bool(st["page"]), id="o-staff-page-on"))
            yield ColorPicker(t("Page background"), st["page"] or "#f3f4f6", "o-staff-page", bars,
                              id="o-pick-staff-page")
            yield from self._paint_rows("page", staff=True)
            for name in ot.STAFF_ASSETS:
                yield from self._asset_row(f"staff-{name}", st[name])
            yield from _row(t("Legibility film"), Slider(*ot.STAFF_FILM, st["film"], step=5, unit="%",
                                                         id="o-staff-film"))
            yield from _row(t("Content card"), _tip(Select([(t(v), k) for k, v in ot.STAFF_CARD.items()],
                                                           value=st["card"], allow_blank=False, id="o-staff-card"),
                                                    CARD_HELP))
            yield from _row(t("Card padding"), Slider(*ot.STAFF_CARD_PADDING, st["card_padding"], unit="px",
                                                      id="o-staff-card_padding"))
            yield from _row(t("Table density"), Select([(t(v), k) for k, v in ot.STAFF_DENSITY.items()],
                                                       value=st["density"], allow_blank=False, id="o-staff-density"))
            yield from _row(t("Contrast"), Select([(t(v), k) for k, v in ot.STAFF_CONTRAST.items()],
                                                  value=st["contrast"], allow_blank=False, id="o-staff-contrast"))
            yield from _row(t("Text size"), Slider(*ot.STAFF_FONT, st["font"], unit="%", id="o-staff-font"))
            yield from _row(t("Light/dark switch"),
                            _tip(Switch(st["dark_switch"], id="o-staff-dark_switch"),
                                 "A light/dark button in the staff top bar; each person's choice is kept in "
                                 "their browser."))
            yield from _style_rows("o-staff-style", st)
        for side, (box, _title) in LOGIN_BOXES.items():
            lg = c["login"][side]
            with Vertical(id=box, classes="opac-box"):
                yield Static(t("Shown on the login page (${where}), next to the login form: a banner picture "
                               "(it shrinks with the screen) and your text. HTML is allowed: paragraphs, bold, "
                               "italics, lists, headings, links and pictures; scripts, styles and event handlers "
                               "are taken out.", where=ot.LOGIN_SIDES[side]),
                             classes="ai-note", markup=False)
                yield from _row(t("Show"), Switch(lg["enabled"], id=f"{box}-enabled"))
                yield from self._asset_row(ot.LOGIN_ASSETS[side], lg["image"])
                yield from _row(t("Picture description"), Input(lg["alt"], id=f"{box}-alt", max_length=120,
                                                                 placeholder=t("for screen readers")))
                yield from _row(t("Text (HTML)"), TextArea(lg["html"], id=f"{box}-html", classes="o-html"))
        cr = c["credits"]
        with Vertical(id="o-credits", classes="opac-box"):
            yield Static(t("The footer of every OPAC page (opaccredits), built from these fields: no HTML to "
                           "type. While it is on, the library's own footer entries are set to expired, and come "
                           "back when it is turned off or the look is removed."), classes="ai-note", markup=False)
            yield from _row(t("Show"), Switch(cr["enabled"], id="o-cr-enabled"))
            yield Static(t(CREDITS_NOTE) + "\n" + t("Fields: ${names}.", names=", ".join(
                t(v[0]) for v in CREDIT_FIELDS.values())), classes="ai-note", markup=False)
            yield TextArea(_credits_text(cr), id="o-cr-text", classes="o-html o-credits-text")
            yield Static(t("Example:") + "\n" + _credits_example(), classes="ai-note", markup=False)
        for side, (box, _title) in NEWS_BOXES.items():
            nw = c["news"][side]
            with Vertical(id=box, classes="opac-box"):
                yield Static(t("A news item of your own on ${where} (Koha's News): a title, the text and "
                               "buttons that open an address. HTML is allowed as in the login text. Apply "
                               "publishes it; switching it off takes it down. The library's own news in Tools > "
                               "News stay as they are.",
                               where=t("the OPAC home page") if side == "opac" else t("the staff home page")),
                             classes="ai-note", markup=False)
                yield from _row(t("Publish"), Switch(nw["enabled"], id=f"{box}-enabled"))
                yield from _row(t("Title"), Input(nw["title"], id=f"{box}-title", max_length=120,
                                                  placeholder=t("Library news")))
                yield from _row(t("Text (HTML)"), TextArea(nw["html"], id=f"{box}-html", classes="o-html"))
                yield Static(t("Buttons under the text: the text on the button and the address it "
                               "opens. Add as many as you need; ✕ removes one."), classes="ai-note", markup=False)
                yield Vertical(id=f"{box}-btns", classes="link-rows")
                with Horizontal(classes="quick-actions"):
                    yield Button(t("Add a button"), id=f"{box}-badd", classes="small")
        with Vertical(id="o-ghost", classes="opac-box"):
            for key, label in GHOST.items():
                yield from _row(t(label), Switch(c["ghost"][key], id=f"o-g-{key}"))

    def _asset_row(self, name: str, current: dict) -> ComposeResult:
        """A picture: where it comes from and the file or address. name is
        background/logo/favicon, or staff-* for the staff interface's own."""
        with Horizontal(classes="form-row"):
            yield Label(t(ASSET_LABELS[name.removeprefix("staff-")]), classes="form-label")
            yield Select([(t(v), k) for k, v in ot.SOURCES.items()], value=current["source"],
                         allow_blank=False, id=f"o-src-{name}", classes="opac-source")
            yield Input(current["url"], id=f"o-val-{name}", placeholder=t("File or address"))

    def _link_set(self, key: str) -> ComposeResult:
        lk, p = self.cfg[key], LINK_SETS[key]
        yield from _row(t("Show"), Switch(lk["enabled"], id=f"{p}s-enabled"))
        yield from _row(t("Style"), Select([(t(v), k) for k, v in ot.LINK_STYLES.items()], value=lk["style"],
                                           allow_blank=False, id=f"{p}s-style"))
        yield from _row(t("Layout"), Select([(t(v), k) for k, v in ot.LINK_LAYOUTS.items()], value=lk["layout"],
                                            allow_blank=False, id=f"{p}s-layout"))
        yield Vertical(id=f"{p}s-rows", classes="link-rows")
        with Horizontal(classes="quick-actions"):
            yield Button(t("Add a button"), id=f"{p}-add", classes="small")

    def _paint_rows(self, key: str, staff: bool = False) -> ComposeResult:
        """The texture and opacity of one colour of the palette (the OPAC's,
        or the staff interface's with staff)."""
        p = (self.cfg["staff"] if staff else self.cfg)["paint"][key]
        box = "o-staff-paint" if staff else "o-paint"
        yield from _row(t("Its texture"), _tip(Select([(t(v), k) for k, v in ot.PAINTS.items()], value=p["texture"],
                                                      allow_blank=False, id=f"{box}-{key}-texture"),
                                               PAINT_HELP[key]))
        yield from _row(t("Its opacity"), _tip(Slider(0, 100, p["opacity"], unit="%", id=f"{box}-{key}-opacity"),
                                               PAINT_HELP[key]))

    def _slider(self, key: str) -> ComposeResult:
        label, unit, step = SLIDERS[key]
        lo, hi = ot.RANGES[key]
        yield from _row(t(label), _tip(Slider(lo, hi, self.cfg[key], step=step, unit=unit, id=f"o-{key}"),
                                       RADIUS_HELP.get(key, "")))

    def on_mount(self) -> None:
        titles = {"o-material": "Material", "o-images": "Pictures", "o-dark": "Legibility and dark mode",
                  "o-carousel": "New arrivals carousel", "o-links": "Quick access buttons",
                  "o-slinks": "Staff home page buttons",
                  "o-staff": "Staff interface", "o-ghost": "Hide",
                  "o-credits": "Footer credits",
                  **{box: title for box, title in NEWS_BOXES.values()},
                  **{box: title for box, title in LOGIN_BOXES.values()}}
        titles["o-gate"] = "Instance"
        for wid, title in titles.items():
            self.query_one(f"#{wid}").border_title = t(title)
        self.show_fields(False)
        for key in LINK_SETS:
            self.set_links(self.cfg[key]["items"], key)
        for side, (box, _title) in NEWS_BOXES.items():
            self.set_news_buttons(box, self.cfg["news"][side]["buttons"])

    # ------------------------------------------------------------------
    # News buttons (o-newsitem-<side>-b-<n>): text and address, one row
    # each, added and removed like the quick access buttons
    # ------------------------------------------------------------------
    def set_news_buttons(self, box: str, items: list[dict]) -> None:
        self.query_one(f"#{box}-btns", Vertical).remove_children()
        for item in items:
            self.add_news_button(box, item)

    def add_news_button(self, box: str, item: dict | None = None) -> None:
        rows = self.query_one(f"#{box}-btns", Vertical)
        item = item or {"text": "", "url": ""}
        self.link_rows += 1
        n = self.link_rows
        rows.mount(Horizontal(
            Input(item["text"], placeholder=t("Learn more"), max_length=60, id=f"{box}-bt-{n}",
                  classes="link-text", tooltip=t("Button text")),
            Input(item["url"], placeholder="https://...", id=f"{box}-bu-{n}", classes="link-url",
                  tooltip=t("Button address")),
            Button("✕", id=f"{box}-bdel-{n}", classes="small link-del", tooltip=t("Remove")),
            classes="form-row news-button-row", id=f"{box}-b-{n}"))

    def collect_news_buttons(self, box: str) -> list[dict]:
        out = []
        for row in self.query_one(f"#{box}-btns", Vertical).children:
            n = (row.id or "").rsplit("-", 1)[-1]
            text = row.query_one(f"#{box}-bt-{n}", Input).value.strip()
            url = row.query_one(f"#{box}-bu-{n}", Input).value.strip()
            if text or url:
                out.append({"text": text, "url": url})
        return out

    # ------------------------------------------------------------------
    # Quick access buttons (OPAC: o-link-*, staff: o-slink-*): one row of
    # fields per button
    # ------------------------------------------------------------------
    def set_links(self, items: list[dict], key: str = "links") -> None:
        box = self.query_one(f"#{LINK_SETS[key]}s-rows", Vertical)
        box.remove_children()
        for item in items:
            self.add_link(item, key)

    def add_link(self, item: dict | None = None, key: str = "links") -> None:
        p = LINK_SETS[key]
        box = self.query_one(f"#{p}s-rows", Vertical)
        if len(box.children) >= ot.MAX_LINKS:
            self.app.notify(t("At most ${n} buttons.", n=str(ot.MAX_LINKS)), severity="warning")
            return
        if item is None:     # a new button goes last
            orders = [_order(i.value) for i in box.query(".link-order").results(Input)]
            item = {"icon": "", "text": "", "url": "", "target": "_self",
                    "sort_order": min(max([o for o in orders if o] + [len(orders)]) + 1, ot.MAX_ORDER)}
        self.link_rows += 1
        n = self.link_rows
        box.mount(Horizontal(
            Input(str(item.get("sort_order") or len(box.children) + 1), placeholder="#", max_length=3, restrict=r"[0-9]*",
                  id=f"{p}-order-{n}", classes="link-order", tooltip=t("Order (1 comes first)")),
            Input(item["icon"], placeholder="📖", max_length=24, id=f"{p}-icon-{n}", classes="link-icon"),
            Input(item["text"], placeholder=t("Text"), max_length=60, id=f"{p}-text-{n}", classes="link-text"),
            Input(item["url"], placeholder="https://...", id=f"{p}-url-{n}", classes="link-url"),
            Select([(t(v), k) for k, v in ot.LINK_TARGETS.items()], value=item["target"], allow_blank=False,
                   id=f"{p}-target-{n}", classes="link-target"),
            Button("✕", id=f"{p}-del-{n}", classes="small link-del", tooltip=t("Remove")),
            classes="form-row " + ("link-row" if key == "links" else "slink-row"), id=f"{p}-{n}"))

    def collect_links(self, key: str = "links") -> tuple[list[dict], str]:
        p = LINK_SETS[key]
        items = []
        for pos, row in enumerate(self.query_one(f"#{p}s-rows", Vertical).children, 1):
            n = (row.id or "").rsplit("-", 1)[-1]
            raw = {"icon": row.query_one(f"#{p}-icon-{n}", Input).value.strip(),
                   "text": row.query_one(f"#{p}-text-{n}", Input).value.strip(),
                   "url": row.query_one(f"#{p}-url-{n}", Input).value.strip(),
                   "target": row.query_one(f"#{p}-target-{n}", Select).value,
                   "sort_order": _order(row.query_one(f"#{p}-order-{n}", Input).value) or pos}
            if not raw["text"] and not raw["url"]:
                continue
            if not raw["text"]:
                return items, t("A button needs its text.")
            if not ot.safe_link(raw["url"]):
                return items, t("${name}: the address must start with https://, http://, / , mailto: or tel:.",
                                name=raw["text"])
            items.append(raw)
        return items, ""

    def on_show(self) -> None:
        # Every time the card is opened: the fields wait behind the gate
        # until the instance is read again (Sync with the instance). A
        # restore, an edit in Koha's own tools or another panel may have
        # changed it, and the screen never shows what it held before.
        self.loaded = True
        self.restores_seen = getattr(self.app, "restores", 0)
        self.show_fields(False)
        self.query_one("#o-gate-report", Static).update("")

    def show_fields(self, on: bool) -> None:
        """The fields and actions (on), or only the gate (off)."""
        for child in self.children:
            if child.id not in GATE_KEEP and "view-head" not in child.classes:
                child.display = on

    def gate_sync(self) -> None:
        self.run_worker(self._gate_sync(), exclusive=True, group="opac-load", exit_on_error=False)

    async def _gate_sync(self) -> None:
        """Sync with the instance: read Koha, fill every field from it and
        show them, with what was read where; on any failure the fields stay
        hidden and the reason is shown (never the factory settings)."""
        report = self.query_one("#o-gate-report", Static)
        report.update(t("Reading the instance..."))
        try:
            out = await self.app.bridge.task("opac-theme-sync")
            if out.rc:
                raise RuntimeError(t("the installer could not read Koha (code ${rc}).", rc=str(out.rc)))
            notes = self.from_koha(out.results)
        except Exception as e:     # noqa: BLE001 (said on the card, the fields stay hidden)
            report.update(t("Could not read the instance: ${error}", error=str(e)))
            self.show_fields(False)
            return
        report.update("\n".join("• " + t(text, **values) for text, values in notes))
        self.show_fields(True)

    # ------------------------------------------------------------------
    # Settings <-> fields
    # ------------------------------------------------------------------
    def fill(self, cfg: dict) -> None:
        self.cfg = cfg = ot.normalize(cfg)
        q = self.query_one
        q("#o-texture", Select).value = cfg["texture"]
        for key in ot.STYLE:
            q(f"#o-style-{key}", Select).value = cfg[key]
        for key in SLIDERS:
            q(f"#o-{key}", Slider).value = cfg[key]
        q("#o-accent", Input).value = cfg["accent"]
        q("#o-accent2", Input).value = cfg["accent2"]
        q("#o-surface", Input).value = cfg["surface"]
        for key in ot.PAINTED:
            q(f"#o-paint-{key}-texture", Select).value = cfg["paint"][key]["texture"]
            q(f"#o-paint-{key}-opacity", Slider).value = cfg["paint"][key]["opacity"]
        q("#o-page-on", Switch).value = bool(cfg["page"])
        if cfg["page"]:
            q("#o-page", Input).value = cfg["page"]
        for name in ot.ASSETS:
            q(f"#o-src-{name}", Select).value = cfg[name]["source"]
            q(f"#o-val-{name}", Input).value = cfg[name]["url"]
        q("#o-header_bar", Switch).value = cfg["header_bar"]
        q("#o-header_style", Select).value = cfg["header_style"]
        q("#o-header_height", Slider).value = cfg["header_height"]
        q("#o-dark_switch", Switch).value = cfg["dark_switch"]
        q("#o-default_theme", Select).value = cfg["default_theme"]
        car = cfg["carousel"]
        q("#o-car-enabled", Switch).value = car["enabled"]
        q("#o-car-source", Select).value = car["source"]
        q("#o-car-shelf", Input).value = str(car["shelf"] or "")
        q("#o-car-lists", Switch).value = car["lists"]
        q("#o-car-mode", Select).value = car["mode"]
        q("#o-car-title", Input).value = car["title"]
        q("#o-car-autoplay", Switch).value = car["autoplay"]
        q("#o-speed", Slider).value = car["speed"]
        q("#o-count", Slider).value = car["count"]
        q("#o-car-hover", Select).value = car["hover"]
        q("#o-car-overlay", Switch).value = car["overlay"]
        q("#o-car-tag", Input).value = car["amazon_tag"]
        for key in GHOST:
            q(f"#o-g-{key}", Switch).value = cfg["ghost"][key]
        for key, p in LINK_SETS.items():
            q(f"#{p}s-enabled", Switch).value = cfg[key]["enabled"]
            q(f"#{p}s-style", Select).value = cfg[key]["style"]
            q(f"#{p}s-layout", Select).value = cfg[key]["layout"]
            self.set_links(cfg[key]["items"], key)
        self.fill_staff(cfg["staff"])
        self.fill_contents(cfg)

    def fill_contents(self, cfg: dict) -> None:
        q = self.query_one
        for side, (box, _title) in LOGIN_BOXES.items():
            lg = cfg["login"][side]
            q(f"#{box}-enabled", Switch).value = lg["enabled"]
            q(f"#{box}-alt", Input).value = lg["alt"]
            q(f"#{box}-html", TextArea).text = lg["html"]
            name = ot.LOGIN_ASSETS[side]
            q(f"#o-src-{name}", Select).value = lg["image"]["source"]
            q(f"#o-val-{name}", Input).value = lg["image"]["url"]
        for side, (box, _title) in NEWS_BOXES.items():
            nw = cfg["news"][side]
            q(f"#{box}-enabled", Switch).value = nw["enabled"]
            q(f"#{box}-title", Input).value = nw["title"]
            q(f"#{box}-html", TextArea).text = nw["html"]
            self.set_news_buttons(box, nw["buttons"])
        cr = cfg["credits"]
        q("#o-cr-enabled", Switch).value = cr["enabled"]
        q("#o-cr-text", TextArea).text = _credits_text(cr)

    def fill_staff(self, st: dict) -> None:
        q = self.query_one
        q("#o-staff-enabled", Switch).value = st["enabled"]
        for key in ("accent", "accent2", "surface"):
            q(f"#o-staff-{key}", Input).value = st[key]
        q("#o-staff-texture", Select).value = st["texture"]
        for key in ot.STYLE:
            q(f"#o-staff-style-{key}", Select).value = st[key]
        for key in ot.STAFF_MATERIAL:
            q(f"#o-staff-{key}", Slider).value = st[key]
        for key in ot.PAINTED:
            q(f"#o-staff-paint-{key}-texture", Select).value = st["paint"][key]["texture"]
            q(f"#o-staff-paint-{key}-opacity", Slider).value = st["paint"][key]["opacity"]
        q("#o-staff-page-on", Switch).value = bool(st["page"])
        q("#o-staff-bar-on", Switch).value = bool(st["bar"])
        q("#o-staff-bar", Input).value = st["bar"] or ot.staff_bar(st)
        if st["page"]:
            q("#o-staff-page", Input).value = st["page"]
        for name in ot.STAFF_ASSETS:
            q(f"#o-src-staff-{name}", Select).value = st[name]["source"]
            q(f"#o-val-staff-{name}", Input).value = st[name]["url"]
        q("#o-staff-film", Slider).value = st["film"]
        q("#o-staff-card", Select).value = st["card"]
        q("#o-staff-card_padding", Slider).value = st["card_padding"]
        q("#o-staff-density", Select).value = st["density"]
        q("#o-staff-contrast", Select).value = st["contrast"]
        q("#o-staff-font", Slider).value = st["font"]
        q("#o-staff-header_glass", Switch).value = st["header_glass"]
        q("#o-staff-dark_switch", Switch).value = st["dark_switch"]
        for key in ot.STAFF_HEADER:
            q(f"#o-staff-{key}", Slider).value = st[key]

    def collect(self) -> tuple[dict, dict[str, tuple[str, Path]], str]:
        """(settings, pictures still to publish {name: (source, file)}, problem)."""
        q = self.query_one
        raw = {"texture": q("#o-texture", Select).value,
               **{key: q(f"#o-style-{key}", Select).value for key in ot.STYLE},
               "accent": q("#o-accent", Input).value, "accent2": q("#o-accent2", Input).value,
               "surface": q("#o-surface", Input).value,
               "page": q("#o-page", Input).value if q("#o-page-on", Switch).value else "",
               "paint": {key: {"texture": q(f"#o-paint-{key}-texture", Select).value,
                               "opacity": q(f"#o-paint-{key}-opacity", Slider).value} for key in ot.PAINTED},
               "dark_switch": q("#o-dark_switch", Switch).value,
               "header_bar": q("#o-header_bar", Switch).value,
               "header_style": q("#o-header_style", Select).value,
               "header_height": q("#o-header_height", Slider).value,
               "default_theme": q("#o-default_theme", Select).value,
               "carousel": {"enabled": q("#o-car-enabled", Switch).value, "title": q("#o-car-title", Input).value,
                            "autoplay": q("#o-car-autoplay", Switch).value, "speed": q("#o-speed", Slider).value,
                            "count": q("#o-count", Slider).value, "hover": q("#o-car-hover", Select).value,
                            "overlay": q("#o-car-overlay", Switch).value, "mode": q("#o-car-mode", Select).value,
                            "reflect": q("#o-car-reflect", Switch).value,
                            "missing": q("#o-car-missing", Select).value,
                            "amazon_tag": q("#o-car-tag", Input).value.strip(),
                            "source": q("#o-car-source", Select).value, "lists": q("#o-car-lists", Switch).value,
                            "shelf": q("#o-car-shelf", Input).value.strip() or 0},
               "ghost": {key: q(f"#o-g-{key}", Switch).value for key in GHOST},
               # No switch of its own any more (Paulo, 2026-10-15): the news
               # boxes above make the buttons, and [kei-button] markers in
               # Koha's own news always become buttons.
               "news_buttons": True,
               "staff": {"enabled": q("#o-staff-enabled", Switch).value,
                         "accent": q("#o-staff-accent", Input).value, "accent2": q("#o-staff-accent2", Input).value,
                         "surface": q("#o-staff-surface", Input).value, "film": q("#o-staff-film", Slider).value,
                         "density": q("#o-staff-density", Select).value,
                         "contrast": q("#o-staff-contrast", Select).value, "font": q("#o-staff-font", Slider).value,
                         "texture": q("#o-staff-texture", Select).value,
                         "card": q("#o-staff-card", Select).value,
                         "card_padding": q("#o-staff-card_padding", Slider).value,
                         "page": q("#o-staff-page", Input).value if q("#o-staff-page-on", Switch).value else "",
                         "bar": q("#o-staff-bar", Input).value if q("#o-staff-bar-on", Switch).value else "",
                         "header_glass": q("#o-staff-header_glass", Switch).value,
                         "dark_switch": q("#o-staff-dark_switch", Switch).value,
                         "paint": {key: {"texture": q(f"#o-staff-paint-{key}-texture", Select).value,
                                         "opacity": q(f"#o-staff-paint-{key}-opacity", Slider).value}
                                   for key in ot.PAINTED},
                         **{key: q(f"#o-staff-style-{key}", Select).value for key in ot.STYLE},
                         **{key: q(f"#o-staff-{key}", Slider).value for key in (*ot.STAFF_MATERIAL, *ot.STAFF_HEADER)}}}
        for key in SLIDERS:
            raw[key] = q(f"#o-{key}", Slider).value
        raw["login"] = {side: {"enabled": q(f"#{box}-enabled", Switch).value, "alt": q(f"#{box}-alt", Input).value,
                               "html": q(f"#{box}-html", TextArea).text, "image": {"source": "none", "url": ""}}
                        for side, (box, _title) in LOGIN_BOXES.items()}
        raw["news"] = {side: {"enabled": q(f"#{box}-enabled", Switch).value,
                              "title": q(f"#{box}-title", Input).value.strip(),
                              "html": q(f"#{box}-html", TextArea).text,
                              "buttons": self.collect_news_buttons(box),
                              # The library's own news item the box shows (0: the panel's own).
                              "koha_id": self.cfg["news"][side]["koha_id"]}
                       for side, (box, _title) in NEWS_BOXES.items()}
        for side, (_box, title) in NEWS_BOXES.items():
            problem = _news_problem(raw["news"][side])
            if problem:
                return raw, {}, f"{t(title)}: {problem}"
        fields, links, problem = _credits_parse(q("#o-cr-text", TextArea).text)
        raw["credits"] = {"enabled": q("#o-cr-enabled", Switch).value, **fields, "links": links}
        if problem:
            return raw, {}, f"{t('Footer credits')}: {problem}"
        problem = _credits_problem(raw["credits"])
        if problem:
            return raw, {}, f"{t('Footer credits')}: {problem}"
        for key, p in LINK_SETS.items():
            items, problem = self.collect_links(key)
            raw[key] = {"enabled": q(f"#{p}s-enabled", Switch).value, "style": q(f"#{p}s-style", Select).value,
                        "layout": q(f"#{p}s-layout", Select).value, "items": items}
            if problem:
                where = t("Staff home page buttons") if key == "staff_links" else t("Quick access buttons")
                return raw, {}, f"{where}: {problem}"
        if raw["carousel"]["source"] == "list" and not ot.normalize(raw)["carousel"]["shelf"]:
            return raw, {}, t("Carousel: type the number of the Koha list (shelfnumber= in its address).")
        if raw["carousel"]["amazon_tag"] and not ot.normalize(raw)["carousel"]["amazon_tag"]:
            return raw, {}, t("The Amazon tag has only letters, digits and hyphens.")
        pending: dict[str, tuple[str, Path]] = {}
        pictures = [(name, self.cfg[name], t(ASSET_LABELS[name])) for name in ot.ASSETS]
        pictures += [(f"staff-{name}", self.cfg["staff"][name],
                      f"{t('Staff interface')}: {t(ASSET_LABELS[name])}") for name in ot.STAFF_ASSETS]
        pictures += [(ot.LOGIN_ASSETS[side], self.cfg["login"][side]["image"],
                      f"{t(LOGIN_BOXES[side][1])}: {t(ASSET_LABELS['login'])}") for side in ot.LOGIN_SIDES]
        for name, current, label in pictures:
            source = q(f"#o-src-{name}", Select).value
            value = q(f"#o-val-{name}", Input).value.strip()
            pic = {"source": source, "url": ""}
            if name.startswith("staff-") and name not in ot.LOGIN_ASSETS.values():
                raw["staff"][name.removeprefix("staff-")] = pic
            elif name in ot.LOGIN_ASSETS.values():
                _picture(raw, name).update(pic)
                pic = _picture(raw, name)
            else:
                raw[name] = pic
            if source == "none":
                continue
            if not value:
                return raw, {}, t("${name}: choose a file or type an address.", name=label)
            if value == current["url"] and source == current["source"]:
                pic["url"] = value                              # already published
            elif source == "url":
                if not ot.safe_url(value):
                    return raw, {}, t("${name}: the address must start with https://.", name=label)
                pic["url"] = value
            else:
                path = Path(value).expanduser()
                problem = ot.image_problem(path)
                if problem:
                    return raw, {}, f"{label}: {t(problem)}"
                pending[name] = (source, path)
        return raw, pending, ""

    def js_text(self) -> dict:
        """The words written into Koha, in the panel's language: the
        script's labels and the credits' ones."""
        return {k: t(v) for k, v in {**ot.JS_TEXT, **ot.CREDITS_TEXT}.items()}

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {"o-gate-sync": self.gate_sync, "o-apply": self.apply, "o-preview": self.preview, "o-sync": self.sync,
                   "o-refresh": self.refresh_carousel, "o-keys": self.keys, "o-remove": self.remove_look,
                   "o-staff-copy": self.copy_opac_preset, "o-preset-use": self.use_preset,
                   "o-preset-save": self.save_preset, "o-preset-delete": self.delete_preset,
                   "o-link-add": lambda: self.add_link(None, "links"),
                   "o-slink-add": lambda: self.add_link(None, "staff_links")}
        bid = event.button.id or ""
        gone = re.fullmatch(r"(o-s?link)-del-(\d+)", bid)
        if gone:
            event.stop()
            self.query_one(f"#{gone.group(1)}-{gone.group(2)}").remove()
            return
        news = re.fullmatch(r"(o-newsitem-(?:opac|staff))-(badd|bdel-(\d+))", bid)
        if news:
            event.stop()
            if news.group(3):
                self.query_one(f"#{news.group(1)}-b-{news.group(3)}").remove()
            else:
                self.add_news_button(news.group(1))
            return
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    def reload(self) -> None:
        self.run_worker(self._reload(), exclusive=True, group="opac-load", exit_on_error=False)

    async def _reload(self) -> None:
        """The look now in Koha into the fields, quietly. Koha decides: what
        a restore or an edit in Koha's own tools left there is what the
        screen shows. Quiet and unchanged when there is no Koha to ask."""
        try:
            out = await self.app.bridge.task("opac-theme-sync")
        except Exception:     # noqa: BLE001 (no installer, no database: the fields stay)
            self.summary()
            return
        try:
            self.from_koha(out.results)
        except Exception as e:     # noqa: BLE001 (said, never a silent screen of defaults)
            self.app.notify(t("Sync current OPAC settings") + f": {e}", severity="error", timeout=15)

    def from_koha(self, found: dict[str, str]) -> list[tuple[str, dict]]:
        """The fields and the summary from what opac-theme-sync read in Koha;
        the report's notes back."""
        self.restores_seen = getattr(self.app, "restores", 0)
        cfg, notes, in_koha = ot.sync_settings(found, self.js_text())
        self.carousel_on = found.get("carousel") == "on"
        self.feed_items = found.get("feed_items", "")
        self.fill(cfg)
        self.summary(applied=in_koha)
        return ot.source_notes(found) + notes

    def sync(self) -> None:
        self.run_worker(self._sync(), exclusive=True, group="opac-load", exit_on_error=False)

    async def _sync(self) -> None:
        """Sync current OPAC settings: what is live in Koha (the blocks of
        OpacUserCSS / OpacUserJS / IntranetUserCSS / IntranetUserJS and the
        panel's login instructions, credits and news with their buttons)
        into the fields, and a report of what was found. The fields not
        saved are replaced; nothing is written to Koha."""
        title = t("Sync current OPAC settings")
        try:
            out = await self.app.bridge.task("opac-theme-sync")
        except Exception as e:   # noqa: BLE001 (no installer, no database)
            self.app.notify(f"{title}: {e}", severity="error")
            return
        if out.rc:
            self.app.notify(t("${title}: the installer could not read Koha (code ${rc}).", title=title,
                              rc=str(out.rc)), severity="error", timeout=15)
        try:
            notes = self.from_koha(out.results)
        except Exception as e:     # noqa: BLE001 (said, never a silent screen of defaults)
            self.app.notify(f"{title}: {e}", severity="error", timeout=15)
            return
        report = "\n".join("• " + t(text, **values) for text, values in notes)
        report += "\n\n" + t("The fields now show what is in Koha. Nothing was written to Koha: Apply "
                               "writes the fields.")
        self.app.push_screen(TextScreen(title, report))

    def summary(self, applied: bool = False) -> None:
        text = t("Applied in Koha.") if applied else t("Not applied yet: Koha shows its own look.")
        if self.carousel_on:
            text += " · " + t("Carousel: ${n} titles with a cover.", n=self.feed_items or "0")
        self.query_one("#o-summary", Label).update(text)

    # ------------------------------------------------------------------
    # Looks: the ready-made ones (ot.PRESETS) and up to five of the
    # library's own (ot.load_user_presets), saved in the panel's folder.
    # ------------------------------------------------------------------
    def _preset_options(self) -> list[tuple[str, str]]:
        own = [(f"★ {item['name']}", f"user:{n}") for n, item in enumerate(ot.load_user_presets())]
        return [(t(p["label"]), k) for k, p in ot.PRESETS.items()] + own

    def _refresh_presets(self, value: str | None = None) -> None:
        box = self.query_one("#o-preset", Select)
        options = self._preset_options()
        box.set_options(options)
        keys = [k for _label, k in options]
        box.value = value if value in keys else keys[0]

    def _fill_look(self, cfg: dict) -> None:
        """The look fields of both sides from cfg (nothing else changes)."""
        q = self.query_one
        q("#o-texture", Select).value = cfg["texture"]
        for key in ot.STYLE:
            q(f"#o-style-{key}", Select).value = cfg[key]
        for key in SLIDERS:
            q(f"#o-{key}", Slider).value = cfg[key]
        for key in ("accent", "accent2", "surface"):
            q(f"#o-{key}", Input).value = cfg[key]
        for key in ot.PAINTED:
            q(f"#o-paint-{key}-texture", Select).value = cfg["paint"][key]["texture"]
            q(f"#o-paint-{key}-opacity", Slider).value = cfg["paint"][key]["opacity"]
        q("#o-page-on", Switch).value = bool(cfg["page"])
        if cfg["page"]:
            q("#o-page", Input).value = cfg["page"]
        self.fill_staff(cfg["staff"])

    def use_preset(self) -> None:
        self.app.run_worker(self._use_preset(), group="opac-preset", exclusive=True, exit_on_error=False)

    async def _use_preset(self) -> None:
        """A look into the OPAC and staff fields; first, when the fields hold
        a look that is not saved anywhere, the offer to save it (Paulo,
        2026-10-31: "para não perder as mudanças"). Nothing is written to
        Koha until Apply."""
        raw, _pending, problem = self.collect()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        key = self.query_one("#o-preset", Select).value
        own = ot.load_user_presets()
        if key.startswith("user:"):
            item = own[int(key[5:])] if int(key[5:]) < len(own) else None
            if item is None:
                self._refresh_presets()
                return
            name, cfg = item["name"], ot.apply_look(raw, item["look"])
        else:
            name, cfg = t(ot.PRESETS[key]["label"]), ot.apply_preset(raw, key)
        title = t("Ready-made look")
        if not ot.look_saved(raw, own):
            choice = await self.app.push_screen_wait(ChoiceScreen(
                title, t("The fields have changes that are not saved as a look. Save them before switching "
                         "to \"${name}\"?", name=name),
                [("save", t("Save the current look first")), ("switch", t("Switch without saving")),
                 ("cancel", t("Cancel"))], default="save"))
            if choice in (None, "cancel"):
                return
            if choice == "save" and not await self._save_look(raw):
                return
        self._fill_look(cfg)
        self.app.notify(t("Look \"${name}\" in the fields. Apply writes it into Koha.", name=name), timeout=8)

    def save_preset(self) -> None:
        self.app.run_worker(self._save_preset(), group="opac-preset", exclusive=True, exit_on_error=False)

    async def _save_preset(self) -> None:
        raw, _pending, problem = self.collect()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        await self._save_look(raw)

    async def _save_look(self, raw: dict) -> bool:
        """The look of raw as one of the library's own: a name; the same name
        replaces that look; with five saved, one of them to replace. True
        when it was saved."""
        title = t("Save current look")
        own = ot.load_user_presets()
        names = [item["name"] for item in own]
        name = await self.app.push_screen_wait(InputScreen(
            title, t("A name for this look (colours, texture, opacity, blur, corners and style details of the "
                     "OPAC and the staff interface). Up to ${n} looks; the same name replaces that one.",
                     n=ot.MAX_USER_PRESETS),
            t("Name"), value=f"{t('My look')} {len(own) + 1}" if len(own) < ot.MAX_USER_PRESETS else "",
            validate=lambda v: "" if 0 < len(v.strip()) <= 40 else t("Between 1 and 40 characters.")))
        if name is None:
            return False
        item = {"name": name.strip(), "look": ot.look_of(raw)}
        if item["name"] in names:
            own[names.index(item["name"])] = item
        elif len(own) < ot.MAX_USER_PRESETS:
            own.append(item)
        else:
            slot = await self.app.push_screen_wait(ChoiceScreen(
                title, t("${n} looks are saved already. Which one should this replace?", n=ot.MAX_USER_PRESETS),
                [(str(n), f"★ {old}") for n, old in enumerate(names)]))
            if slot is None:
                return False
            own[int(slot)] = item
        try:
            ot.save_user_presets(own)
        except (OSError, ValueError) as e:
            self.app.notify(str(e), severity="error")
            return False
        self._refresh_presets(f"user:{[i['name'] for i in own].index(item['name'])}")
        self.app.notify(t("Look \"${name}\" saved.", name=item["name"]))
        return True

    def delete_preset(self) -> None:
        self.app.run_worker(self._delete_preset(), group="opac-preset", exclusive=True, exit_on_error=False)

    async def _delete_preset(self) -> None:
        key = self.query_one("#o-preset", Select).value
        own = ot.load_user_presets()
        if not key.startswith("user:") or int(key[5:]) >= len(own):
            self.app.notify(t("Only your own looks (★) can be deleted."), severity="warning")
            return
        name = own[int(key[5:])]["name"]
        if not await self.app.push_screen_wait(ConfirmScreen(
                t("Delete saved look"), t("Delete the look \"${name}\"? The fields and Koha do not change.",
                                          name=name))):
            return
        del own[int(key[5:])]
        try:
            ot.save_user_presets(own)
        except OSError as e:
            self.app.notify(str(e), severity="error")
            return
        self._refresh_presets()
        self.app.notify(t("Look \"${name}\" deleted.", name=name))

    def copy_opac_preset(self) -> None:
        """Copy OPAC preset: the OPAC fields as they are now (saved or not)
        into the staff fields. Nothing is written to Koha until Apply."""
        raw, _pending, problem = self.collect()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        # A picture still to publish has no address yet: the staff keeps its own.
        cfg, skipped = ot.copy_opac_to_staff(raw)
        self.fill_staff(cfg["staff"])
        msg = t("OPAC preset copied to the staff interface. Apply writes it into Koha.")
        if skipped:
            msg += " " + t("Files of this server stay on the OPAC side, choose them again for the staff: ${names}.",
                           names=", ".join(t(ASSET_LABELS[n]) for n in skipped))
        self.app.notify(msg, timeout=8)

    def preview(self) -> None:
        raw, _pending, problem = self.collect()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        text = ("OpacUserCSS\n\n" + ot.css_block(raw) + "\n\nOpacUserJS\n\n" + ot.js_block(raw, self.js_text()))
        cfg = ot.normalize(raw)
        for location, markup in ot.contents(cfg, self.js_text()).items():
            if markup:
                text += f"\n\n{location} ({t('HTML customizations')})\n\n" + markup
        if ot.staff_active(cfg):
            text += "\n\nIntranetUserCSS\n\n" + ot.staff_css_block(cfg)
        if ot.links_on(cfg["staff_links"]):
            text += "\n\nIntranetUserJS\n\n" + ot.staff_js_block(cfg, self.js_text())
        self.app.push_screen(TextScreen(t("What goes into Koha"), text))

    def apply(self) -> None:
        raw, pending, problem = self.collect()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        self.app.run_worker(self._apply(raw, pending), group="routine", exclusive=True, exit_on_error=False)

    async def _apply(self, raw: dict, pending: dict[str, tuple[str, Path]]) -> None:
        from ..routines.common import run_task, show_done
        title = t("OPAC and Staff Appearance")
        uploads = {n: p for n, p in pending.items() if p[0] != "local"}
        if uploads:
            result = await self.app.push_screen_wait(_loader(t("Sending the pictures"), self._upload_job(uploads)))
            if not result.ok:
                self.app.task_failed(t("Sending the pictures"), result)
                return
            for name, url in result.value.items():
                _picture(raw, name)["url"] = url
        files = {n: p for n, (s, p) in pending.items() if s == "local"}
        for name, path in files.items():
            _picture(raw, name)["url"] = ot.local_url(name, path)
        cfg = ot.normalize(raw)
        car = cfg["carousel"]
        lines = [f"{t('Texture')}: {t(ot.TEXTURES[cfg['texture']])}",
                 f"{t('New arrivals carousel')}: "
                 + (f"{t('on')} ({t(ot.CAROUSEL_MODES[car['mode']])})" if car["enabled"] else t("off")),
                 f"{t('Quick access buttons')}: {len(cfg['links']['items']) if cfg['links']['enabled'] else t('off')}",
                 f"{t('Staff home page buttons')}: "
                 f"{len(cfg['staff_links']['items']) if cfg['staff_links']['enabled'] else t('off')}",
                 f"{t('Staff interface')}: {t('on') if cfg['staff']['enabled'] else t('off')}",
                 f"{t('OPAC login page')}: {t('on') if ot.login_on(cfg['login']['opac']) else t('off')}",
                 f"{t('Staff login page')}: {t('on') if ot.login_on(cfg['login']['staff']) else t('off')}",
                 f"{t('Footer credits')}: {t('on') if ot.credits_on(cfg['credits']) else t('off')}"]
        lines += [f"{t(title)}: {t('on') if ot.news_on(cfg['news'][side]) else t('off')}"
                  for side, (_box, title) in NEWS_BOXES.items()]
        lines += [f"{t(ASSET_LABELS[n])}: {cfg[n]['url']}" for n in ot.ASSETS if cfg[n]["url"]]
        if cfg["staff"]["enabled"]:
            lines += [f"{t('Staff interface')}: {t(ASSET_LABELS[n])}: {cfg['staff'][n]['url']}"
                      for n in ot.STAFF_ASSETS if cfg["staff"][n]["url"]]
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Write this look into Koha's OPAC? A backup of the database is taken first."),
                preview="\n".join(lines))):
            return
        work = ot.write_apply_dir(cfg, files, self.js_text())
        try:
            result = await run_task(self.app, title, "opac-theme-apply", str(work))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        await show_done(self.app, title, result)
        await self._reload()

    def _upload_job(self, uploads: dict[str, tuple[str, Path]]):
        demo = self.app.env.demo
        keys = ot.load_keys()

        def job(reporter: Reporter) -> dict[str, str]:
            out = {}
            for i, (name, (source, path)) in enumerate(uploads.items()):
                reporter.progress(i, len(uploads))
                reporter.status(f"{ot.SOURCES[source]}: {path.name}")
                if demo:
                    out[name] = f"https://i.ibb.co/demo/{ot.local_name(name, path)}"
                    continue
                try:
                    if source == "imgbb":
                        out[name] = ot.upload_imgbb(path, keys.get("imgbb_key", ""))
                    else:
                        out[name] = ot.upload_cloudinary(path, keys.get("cloudinary_cloud", ""),
                                                         keys.get("cloudinary_preset", ""))
                except (OSError, ValueError) as e:
                    raise TaskFailed(f"{ot.SOURCES[source]}: {e}") from None
                reporter.log(f"{name}: {out[name]}")
            return out
        return job

    def refresh_carousel(self) -> None:
        self.app.run_worker(self._routine(t("New arrivals carousel"), "opac-carousel-refresh"),
                            group="routine", exclusive=True, exit_on_error=False)

    def remove_look(self) -> None:
        self.app.run_worker(self._remove(), group="routine", exclusive=True, exit_on_error=False)

    async def _remove(self) -> None:
        title = t("OPAC and Staff Appearance")
        if await self.app.push_screen_wait(ConfirmScreen(
                title, t("Remove this look from the OPAC and go back to Koha's own? A backup of the database is "
                         "taken first; your own OpacUserCSS and OpacUserJS are kept."))):
            await self._routine(title, "opac-theme-remove")

    async def _routine(self, title: str, name: str) -> None:
        from ..routines.common import run_task, show_done
        result = await run_task(self.app, title, name)
        await show_done(self.app, title, result)
        await self._reload()

    def keys(self) -> None:
        self.app.run_worker(self._keys(), group="opac-keys", exclusive=True, exit_on_error=False)

    async def _keys(self) -> None:
        """ImgBB API key and Cloudinary cloud/preset, kept in the panel's
        private file; never in Koha, never shown again."""
        title = t("Image host keys")
        keys = ot.load_keys()
        imgbb = await self.app.push_screen_wait(InputScreen(
            title, t("ImgBB: the API key of your account (api.imgbb.com). Leave empty to keep the saved one."),
            t("ImgBB API key"), password=True, validate=lambda v: ""))
        if imgbb is None:
            return
        cloud = await self.app.push_screen_wait(InputScreen(
            title, t("Cloudinary: the cloud name and an unsigned upload preset (Settings > Upload). No API "
                     "secret is needed."), t("Cloud name"), value=keys.get("cloudinary_cloud", ""),
            validate=_name_problem))
        if cloud is None:
            return
        preset = await self.app.push_screen_wait(InputScreen(
            title, "", t("Upload preset"), value=keys.get("cloudinary_preset", ""), validate=_name_problem))
        if preset is None:
            return
        keys.update({"cloudinary_cloud": cloud, "cloudinary_preset": preset})
        if imgbb:
            keys["imgbb_key"] = imgbb
        try:
            ot.save_keys(keys)
        except OSError as e:
            self.app.notify(str(e), severity="error")
            return
        self.app.notify(t("Image host keys saved."))


def _credits_text(cr: dict) -> str:
    """The credits as the text area shows them, one line each in the order
    of the footer (credits from before the order: the filled fields, then
    the links; a note joined with " · " by 1.5.141 back on its own lines)."""
    def field(key: str) -> list[str]:
        if key == "links":
            return [f"{x['text']} | {x['url']}" for x in cr.get("links") or []]
        return [f"{t(CREDIT_FIELDS[key][0])}: {cr[key]}"] if cr.get(key) else []

    order = cr.get("order") or []
    if not order:
        lines = [ln for key in CREDIT_FIELDS if key != "note" for ln in field(key)]
        lines += [part.strip() for part in (cr.get("note") or "").split(" · ") if part.strip()]
        return "\n".join(lines + field("links"))
    lines = []
    for key in order + [k for k in ot.CREDITS_ORDER_KEYS if cr.get(k) and k not in order]:
        lines += [key[5:]] if key.startswith("text:") else field(key)
    return "\n".join(lines)


def _credits_example() -> str:
    lines = [f"{t(label)}: {hint}" for label, hint, _size in CREDIT_FIELDS.values() if hint]
    return "\n".join(lines + [t("Catalogue guide") + " | https://biblioteca.gov.br/guia"])


def _fold(text: str) -> str:
    """A field name compared without case or accents (Endereço = endereco)."""
    plain = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in plain if not unicodedata.combining(c))


def _credits_parse(text: str) -> tuple[dict, list[dict], str]:
    """(fields, other links, problem) from the credits text: "Field: value"
    lines (the label in English, in the panel's language or the key),
    "text | address" lines, and plain lines shown as they are. The footer
    keeps the order of the lines (fields["order"]); a plain first line is the
    library's name when no line names it."""
    names = {}
    for key, (label, _hint, _size) in CREDIT_FIELDS.items():
        for name in (key, label, t(label)):
            names[_fold(name)] = key
    fields: dict = {key: "" for key in CREDIT_FIELDS}
    order: list[str] = []
    link_lines: list[str] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def known(line: str) -> str | None:
        name, sep, _value = line.partition(":")
        return names.get(_fold(name)) if sep else None

    named = any(known(ln) == "name" for ln in lines)
    for i, line in enumerate(lines):
        key = known(line)
        if key:
            label, _hint, size = CREDIT_FIELDS[key]
            value = line.partition(":")[2].strip()
            if len(value) > size:
                return fields, [], t("${name}: at most ${n} characters.", name=t(label), n=str(size))
            fields[key] = value
            if key not in order:
                order.append(key)
        elif "|" in line:
            link_lines.append(line)
            if "links" not in order:
                order.append("links")
        elif i == 0 and not named:
            fields["name"] = line[:CREDIT_FIELDS["name"][2]]
            order.append("name")
        else:
            order.append("text:" + line)
    if len(order) > ot.MAX_CREDIT_LINES:
        return fields, [], t("At most ${n} lines.", n=str(ot.MAX_CREDIT_LINES))
    links, problem = _credit_links("\n".join(link_lines))
    fields["order"] = order
    return fields, links, problem


def _credit_links(text: str) -> tuple[list[dict], str]:
    """The credits' other links, one "text | address" per line."""
    links = []
    for line in text.splitlines():
        if not line.strip():
            continue
        label, sep, url = line.rpartition("|")
        label, url = label.strip(), url.strip()
        if not sep or not label:
            return links, t("${line}: write the text, a | and the address.", line=line.strip())
        if not ot.safe_link(url):
            return links, t("${name}: the address must start with https://, http://, / , mailto: or tel:.", name=label)
        links.append({"text": label, "url": url})
    if len(links) > ot.MAX_CREDIT_LINKS:
        return links, t("At most ${n} links.", n=str(ot.MAX_CREDIT_LINKS))
    return links, ""


def _news_problem(raw: dict) -> str:
    """Why a news item switched on cannot be published, said plainly."""
    for b in raw["buttons"]:
        if b["url"] and not ot.safe_link(b["url"]):
            return t("${name}: the address must start with https://, http://, / , mailto: or tel:.",
                     name=b["text"] or t("Button address"))
        if bool(b["text"]) != bool(b["url"]):
            return t("A button needs its text and its address.")
    if raw["enabled"] and not raw["title"]:
        return t("A news item needs its title.")
    if raw["enabled"] and not (raw["html"].strip() or raw["buttons"]):
        return t("Write the text of the news item or add a button.")
    return ""


def _credits_problem(raw: dict) -> str:
    """The first credits field that would be dropped, said plainly."""
    clean = ot.normalize({"credits": raw})["credits"]
    checks = (("email", "E-mail", t("an address like name@library.org")),
              ("whatsapp", "WhatsApp", t("the number with country and area code, digits only")),
              ("website", "Website", t("an address starting with https://")),
              ("facebook", "Facebook", t("an address starting with https://")),
              ("youtube", "YouTube", t("an address starting with https://")),
              ("instagram", "Instagram", t("@name or an address starting with https://")))
    for key, label, hint in checks:
        if str(raw.get(key) or "").strip() and not clean[key]:
            return f"{t(label)}: {hint}"
    return ""


def _row(label: str, widget) -> ComposeResult:
    with Horizontal(classes="form-row"):
        tag = Label(label, classes="form-label")
        tag.tooltip = widget.tooltip       # the field's tooltip on its label too
        yield tag
        yield widget


def _tip(widget, text: str):
    """widget with text (translated) as its tooltip, when there is one."""
    if text:
        widget.tooltip = t(text)
    return widget


def _order(value: str) -> int:
    """A button's place in the list as typed (0: none)."""
    return int(value) if value.isdigit() else 0


def _name_problem(value: str) -> str:
    return "" if re.fullmatch(r"[A-Za-z0-9_-]{0,64}", value) else t("Only letters, digits, _ and -.")


def _loader(title: str, job):
    from ..screens.loading import LoadingScreen
    return LoadingScreen(title, job)

