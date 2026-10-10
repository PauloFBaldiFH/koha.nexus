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
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, Static, Switch

from .. import opac_theme as ot
from ..i18n import t
from ..screens.dialogs import ConfirmScreen, InputScreen, TextScreen
from ..tasks import Reporter, TaskFailed
from ..widgets.colorpick import ColorPicker
from ..widgets.slider import Slider
from .base import SectionView

ASSET_LABELS = {"background": "Wallpaper", "logo": "Logo", "favicon": "Favicon"}
FILE_SOURCES = ("local", "imgbb", "cloudinary")
def _picture(raw: dict, name: str) -> dict:
    """The settings entry of a picture: raw[name], or raw["staff"][...] for staff-*."""
    return raw["staff"][name.removeprefix("staff-")] if name.startswith("staff-") else raw[name]


SLIDERS = {   # id: (label, unit, step)
    "blur": ("Blur", "px", 1),
    "opacity": ("Opacity", "%", 1),
    "radius_block": ("Blocks", "px", 1),
    "radius_input": ("Inputs", "px", 1),
    "radius_button": ("Buttons", "px", 1),
    "film": ("Legibility film", "%", 5),
}
GHOST = {"rss": "RSS icons", "cart_badge": "Cart badge", "community": "Community links",
         "empty_columns": "Empty table columns"}
ICON_EXAMPLES = "📖 📜 💬 📧 📷 🔐 📅 ❓ fa-book"
# The two sets of quick access buttons: settings key -> id prefix of their fields.
LINK_SETS = {"links": "o-link", "staff_links": "o-slink"}


class OpacView(SectionView):
    loaded = False

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
                     classes="view-prompt", markup=False)
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
            yield from _row(t("Texture"), Select([(t(v), k) for k, v in ot.TEXTURES.items()], value=c["texture"],
                                                 allow_blank=False, id="o-texture"))
            for key in ("blur", "opacity", "radius_block", "radius_input", "radius_button"):
                yield from self._slider(key)
            bars = (t("Hue"), t("Saturation"), t("Lightness"))
            yield ColorPicker(t("Accent colour"), c["accent"], "o-accent", bars, id="o-pick-accent")
            yield ColorPicker(t("Second colour"), c["accent2"], "o-accent2", bars, id="o-pick-accent2")
            yield ColorPicker(t("Block background"), c["surface"], "o-surface", bars, id="o-pick-surface")
            yield from _row(t("Page colour"), Switch(bool(c["page"]), id="o-page-on"))
            yield ColorPicker(t("Page background"), c["page"] or "#f3f4f6", "o-page", bars, id="o-pick-page")
        with Vertical(id="o-images", classes="opac-box"):
            yield Static(t("A file on this server (PNG, JPEG, GIF, WebP or ICO; SVG is refused), a file sent to "
                           "ImgBB or Cloudinary, or a direct https address (Postimages and other hosts)."),
                         classes="ai-note", markup=False)
            for name in ot.ASSETS:
                yield from self._asset_row(name, c[name])
        with Vertical(id="o-dark", classes="opac-box"):
            yield from self._slider("film")
            yield from _row(t("Light/dark switch"), Switch(c["dark_switch"], id="o-dark_switch"))
            yield from _row(t("Default theme"), Select([(t(v), k) for k, v in ot.THEMES.items()],
                                                       value=c["default_theme"], allow_blank=False,
                                                       id="o-default_theme"))
        car = c["carousel"]
        with Vertical(id="o-carousel", classes="opac-box"):
            yield Static(t("The newest titles with a copy on the shelf and a real Amazon cover, rebuilt every "
                           "night. Each cover opens the record. Turns on OPACAmazonCoverImages."),
                         classes="ai-note", markup=False)
            yield from _row(t("Show"), Switch(car["enabled"], id="o-car-enabled"))
            yield from _row(t("Style"), Select([(t(v), k) for k, v in ot.CAROUSEL_MODES.items()], value=car["mode"],
                                               allow_blank=False, id="o-car-mode"))
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
                yield from _row(t(label), Slider(*ot.RANGES[key], st[key], step=step, unit=unit,
                                                 id=f"o-staff-{key}"))
            yield ColorPicker(t("Accent colour"), st["accent"], "o-staff-accent", bars, id="o-pick-staff-accent")
            yield ColorPicker(t("Second colour"), st["accent2"], "o-staff-accent2", bars, id="o-pick-staff-accent2")
            yield ColorPicker(t("Block background"), st["surface"], "o-staff-surface", bars,
                              id="o-pick-staff-surface")
            yield from _row(t("Page colour"), Switch(bool(st["page"]), id="o-staff-page-on"))
            yield ColorPicker(t("Page background"), st["page"] or "#f3f4f6", "o-staff-page", bars,
                              id="o-pick-staff-page")
            for name in ot.STAFF_ASSETS:
                yield from self._asset_row(f"staff-{name}", st[name])
            yield from _row(t("Legibility film"), Slider(*ot.STAFF_FILM, st["film"], step=5, unit="%",
                                                         id="o-staff-film"))
            yield from _row(t("Table density"), Select([(t(v), k) for k, v in ot.STAFF_DENSITY.items()],
                                                       value=st["density"], allow_blank=False, id="o-staff-density"))
            yield from _row(t("Contrast"), Select([(t(v), k) for k, v in ot.STAFF_CONTRAST.items()],
                                                  value=st["contrast"], allow_blank=False, id="o-staff-contrast"))
            yield from _row(t("Text size"), Slider(*ot.STAFF_FONT, st["font"], unit="%", id="o-staff-font"))
        with Vertical(id="o-ghost", classes="opac-box"):
            for key, label in GHOST.items():
                yield from _row(t(label), Switch(c["ghost"][key], id=f"o-g-{key}"))
        with Vertical(id="o-news", classes="opac-box"):
            yield from _row(t("Buttons"), Switch(c["news_buttons"], id="o-news_buttons"))
            yield Static(t("In a news item (Tools > News), this marker becomes a button:") + "\n  "
                         + '[kei-button url="https://..." icon="fa-book"]' + t("Text") + "[/kei-button]",
                         classes="ai-note", markup=False)

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

    def _slider(self, key: str) -> ComposeResult:
        label, unit, step = SLIDERS[key]
        lo, hi = ot.RANGES[key]
        yield from _row(t(label), Slider(lo, hi, self.cfg[key], step=step, unit=unit, id=f"o-{key}"))

    def on_mount(self) -> None:
        titles = {"o-material": "Material", "o-images": "Pictures", "o-dark": "Legibility and dark mode",
                  "o-carousel": "New arrivals carousel", "o-links": "Quick access buttons",
                  "o-slinks": "Staff home page buttons",
                  "o-staff": "Staff interface", "o-ghost": "Hide", "o-news": "News action buttons"}
        for wid, title in titles.items():
            self.query_one(f"#{wid}").border_title = t(title)
        for key in LINK_SETS:
            self.set_links(self.cfg[key]["items"], key)

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
        if not self.loaded:
            self.loaded = True
            self.reload()

    # ------------------------------------------------------------------
    # Settings <-> fields
    # ------------------------------------------------------------------
    def fill(self, cfg: dict) -> None:
        self.cfg = cfg = ot.normalize(cfg)
        q = self.query_one
        q("#o-texture", Select).value = cfg["texture"]
        for key in SLIDERS:
            q(f"#o-{key}", Slider).value = cfg[key]
        q("#o-accent", Input).value = cfg["accent"]
        q("#o-accent2", Input).value = cfg["accent2"]
        q("#o-surface", Input).value = cfg["surface"]
        q("#o-page-on", Switch).value = bool(cfg["page"])
        if cfg["page"]:
            q("#o-page", Input).value = cfg["page"]
        for name in ot.ASSETS:
            q(f"#o-src-{name}", Select).value = cfg[name]["source"]
            q(f"#o-val-{name}", Input).value = cfg[name]["url"]
        q("#o-dark_switch", Switch).value = cfg["dark_switch"]
        q("#o-default_theme", Select).value = cfg["default_theme"]
        car = cfg["carousel"]
        q("#o-car-enabled", Switch).value = car["enabled"]
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
        q("#o-news_buttons", Switch).value = cfg["news_buttons"]
        for key, p in LINK_SETS.items():
            q(f"#{p}s-enabled", Switch).value = cfg[key]["enabled"]
            q(f"#{p}s-style", Select).value = cfg[key]["style"]
            q(f"#{p}s-layout", Select).value = cfg[key]["layout"]
            self.set_links(cfg[key]["items"], key)
        self.fill_staff(cfg["staff"])

    def fill_staff(self, st: dict) -> None:
        q = self.query_one
        q("#o-staff-enabled", Switch).value = st["enabled"]
        for key in ("accent", "accent2", "surface"):
            q(f"#o-staff-{key}", Input).value = st[key]
        q("#o-staff-texture", Select).value = st["texture"]
        for key in ot.STAFF_MATERIAL:
            q(f"#o-staff-{key}", Slider).value = st[key]
        q("#o-staff-page-on", Switch).value = bool(st["page"])
        if st["page"]:
            q("#o-staff-page", Input).value = st["page"]
        for name in ot.STAFF_ASSETS:
            q(f"#o-src-staff-{name}", Select).value = st[name]["source"]
            q(f"#o-val-staff-{name}", Input).value = st[name]["url"]
        q("#o-staff-film", Slider).value = st["film"]
        q("#o-staff-density", Select).value = st["density"]
        q("#o-staff-contrast", Select).value = st["contrast"]
        q("#o-staff-font", Slider).value = st["font"]

    def collect(self) -> tuple[dict, dict[str, tuple[str, Path]], str]:
        """(settings, pictures still to publish {name: (source, file)}, problem)."""
        q = self.query_one
        raw = {"texture": q("#o-texture", Select).value,
               "accent": q("#o-accent", Input).value, "accent2": q("#o-accent2", Input).value,
               "surface": q("#o-surface", Input).value,
               "page": q("#o-page", Input).value if q("#o-page-on", Switch).value else "",
               "dark_switch": q("#o-dark_switch", Switch).value,
               "default_theme": q("#o-default_theme", Select).value,
               "carousel": {"enabled": q("#o-car-enabled", Switch).value, "title": q("#o-car-title", Input).value,
                            "autoplay": q("#o-car-autoplay", Switch).value, "speed": q("#o-speed", Slider).value,
                            "count": q("#o-count", Slider).value, "hover": q("#o-car-hover", Select).value,
                            "overlay": q("#o-car-overlay", Switch).value, "mode": q("#o-car-mode", Select).value,
                            "amazon_tag": q("#o-car-tag", Input).value.strip()},
               "ghost": {key: q(f"#o-g-{key}", Switch).value for key in GHOST},
               "news_buttons": q("#o-news_buttons", Switch).value,
               "staff": {"enabled": q("#o-staff-enabled", Switch).value,
                         "accent": q("#o-staff-accent", Input).value, "accent2": q("#o-staff-accent2", Input).value,
                         "surface": q("#o-staff-surface", Input).value, "film": q("#o-staff-film", Slider).value,
                         "density": q("#o-staff-density", Select).value,
                         "contrast": q("#o-staff-contrast", Select).value, "font": q("#o-staff-font", Slider).value,
                         "texture": q("#o-staff-texture", Select).value,
                         "page": q("#o-staff-page", Input).value if q("#o-staff-page-on", Switch).value else "",
                         **{key: q(f"#o-staff-{key}", Slider).value for key in ot.STAFF_MATERIAL}}}
        for key in SLIDERS:
            raw[key] = q(f"#o-{key}", Slider).value
        for key, p in LINK_SETS.items():
            items, problem = self.collect_links(key)
            raw[key] = {"enabled": q(f"#{p}s-enabled", Switch).value, "style": q(f"#{p}s-style", Select).value,
                        "layout": q(f"#{p}s-layout", Select).value, "items": items}
            if problem:
                where = t("Staff home page buttons") if key == "staff_links" else t("Quick access buttons")
                return raw, {}, f"{where}: {problem}"
        if raw["carousel"]["amazon_tag"] and not ot.normalize(raw)["carousel"]["amazon_tag"]:
            return raw, {}, t("The Amazon tag has only letters, digits and hyphens.")
        pending: dict[str, tuple[str, Path]] = {}
        pictures = [(name, raw, self.cfg[name], t(ASSET_LABELS[name])) for name in ot.ASSETS]
        pictures += [(f"staff-{name}", raw["staff"], self.cfg["staff"][name],
                      f"{t('Staff interface')}: {t(ASSET_LABELS[name])}") for name in ot.STAFF_ASSETS]
        for name, holder, current, label in pictures:
            key = name.removeprefix("staff-")
            source = q(f"#o-src-{name}", Select).value
            value = q(f"#o-val-{name}", Input).value.strip()
            holder[key] = {"source": source, "url": ""}
            if source == "none":
                continue
            if not value:
                return raw, {}, t("${name}: choose a file or type an address.", name=label)
            if value == current["url"] and source == current["source"]:
                holder[key]["url"] = value                      # already published
            elif source == "url":
                if not ot.safe_url(value):
                    return raw, {}, t("${name}: the address must start with https://.", name=label)
                holder[key]["url"] = value
            else:
                path = Path(value).expanduser()
                problem = ot.image_problem(path)
                if problem:
                    return raw, {}, f"{label}: {t(problem)}"
                pending[name] = (source, path)
        return raw, pending, ""

    def js_text(self) -> dict:
        return {k: t(v) for k, v in ot.JS_TEXT.items()}

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {"o-apply": self.apply, "o-preview": self.preview, "o-sync": self.sync,
                   "o-refresh": self.refresh_carousel, "o-keys": self.keys, "o-remove": self.remove_look,
                   "o-staff-copy": self.copy_opac_preset,
                   "o-link-add": lambda: self.add_link(None, "links"),
                   "o-slink-add": lambda: self.add_link(None, "staff_links")}
        bid = event.button.id or ""
        gone = re.fullmatch(r"(o-s?link)-del-(\d+)", bid)
        if gone:
            event.stop()
            self.query_one(f"#{gone.group(1)}-{gone.group(2)}").remove()
            return
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    def reload(self) -> None:
        self.run_worker(self._reload(), exclusive=True, group="opac-load", exit_on_error=False)

    async def _reload(self) -> None:
        """The settings now in Koha; quiet when there is no Koha to ask."""
        try:
            out = await self.app.bridge.task("opac-theme-get")
        except Exception:     # noqa: BLE001 (no installer, no database: the defaults stay)
            self.summary()
            return
        cfg = ot.parse_theme_data(out.results.get("data", ""))
        self.carousel_on = out.results.get("carousel") == "on"
        self.feed_items = out.results.get("feed_items", "")
        if cfg:
            self.fill(cfg)
        self.summary(applied=bool(cfg))

    def sync(self) -> None:
        self.run_worker(self._sync(), exclusive=True, group="opac-load", exit_on_error=False)

    async def _sync(self) -> None:
        """Sync current OPAC settings: what is live in Koha into the fields,
        and a report of what was found. Nothing is written to Koha."""
        title = t("Sync current OPAC settings")
        try:
            out = await self.app.bridge.task("opac-theme-sync")
        except Exception as e:   # noqa: BLE001 (no installer, no database)
            self.app.notify(f"{title}: {e}", severity="error")
            return
        cfg, notes = ot.sync_settings(out.results)
        self.carousel_on = out.results.get("carousel") == "on"
        self.feed_items = out.results.get("feed_items", "")
        if cfg:
            self.fill(cfg)
        self.summary(applied=cfg is not None)
        report = "\n".join("• " + t(text, **values) for text, values in notes)
        if cfg:
            report += "\n\n" + t("The fields now show these settings. Nothing was written to Koha: Apply "
                                   "writes them.")
        self.app.push_screen(TextScreen(title, report))

    def summary(self, applied: bool = False) -> None:
        text = t("Applied in Koha.") if applied else t("Not applied yet: Koha shows its own look.")
        if self.carousel_on:
            text += " · " + t("Carousel: ${n} titles with a cover.", n=self.feed_items or "0")
        self.query_one("#o-summary", Label).update(text)

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
        title = t("OPAC appearance")
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
                 f"{t('Staff interface')}: {t('on') if cfg['staff']['enabled'] else t('off')}"]
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
        title = t("OPAC appearance")
        if await self.app.push_screen_wait(ConfirmScreen(
                title, t("Remove this look from the OPAC and go back to Koha's own? A backup of the database is "
                         "taken first; your own OpacUserCSS and OpacUserJS are kept."))):
            await self._routine(title, "opac-theme-remove")
            self.fill({})

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


def _row(label: str, widget) -> ComposeResult:
    with Horizontal(classes="form-row"):
        yield Label(label, classes="form-label")
        yield widget


def _order(value: str) -> int:
    """A button's place in the list as typed (0: none)."""
    return int(value) if value.isdigit() else 0


def _name_problem(value: str) -> str:
    return "" if re.fullmatch(r"[A-Za-z0-9_-]{0,64}", value) else t("Only letters, digits, _ and -.")


def _loader(title: str, job):
    from ..screens.loading import LoadingScreen
    return LoadingScreen(title, job)

