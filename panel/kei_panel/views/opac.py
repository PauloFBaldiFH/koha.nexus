"""OpacView: the public catalogue's look, written into Koha in one click.

Every setting is a field of this screen; opac_theme.py turns them into the
marked blocks of OpacUserCSS and OpacUserJS, and
`config.sh --task opac-theme-apply` puts them in Koha (backup first, the
rest of both preferences kept). The settings travel inside the CSS block
(/* KEI-THEME-DATA */): opening the screen reads them back from Koha.

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


class OpacView(SectionView):
    loaded = False

    def __init__(self, section):
        super().__init__(section)
        self.cfg = ot.normalize({})
        self.carousel_on = False
        self.feed_items = ""

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
            yield Button(t("Reload"), id="o-reload", classes="small")
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
        with Vertical(id="o-images", classes="opac-box"):
            yield Static(t("A file on this server (PNG, JPEG, GIF, WebP or ICO; SVG is refused), a file sent to "
                           "ImgBB or Cloudinary, or a direct https address (Postimages and other hosts)."),
                         classes="ai-note", markup=False)
            for name in ot.ASSETS:
                with Horizontal(classes="form-row"):
                    yield Label(t(ASSET_LABELS[name]), classes="form-label")
                    yield Select([(t(v), k) for k, v in ot.SOURCES.items()], value=c[name]["source"],
                                 allow_blank=False, id=f"o-src-{name}", classes="opac-source")
                    yield Input(c[name]["url"], id=f"o-val-{name}", placeholder=t("File or address"))
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
        with Vertical(id="o-ghost", classes="opac-box"):
            for key, label in GHOST.items():
                yield from _row(t(label), Switch(c["ghost"][key], id=f"o-g-{key}"))
        with Vertical(id="o-news", classes="opac-box"):
            yield from _row(t("Buttons"), Switch(c["news_buttons"], id="o-news_buttons"))
            yield Static(t("In a news item (Tools > News), this marker becomes a button:") + "\n  "
                         + '[kei-button url="https://..." icon="fa-book"]' + t("Text") + "[/kei-button]",
                         classes="ai-note", markup=False)

    def _slider(self, key: str) -> ComposeResult:
        label, unit, step = SLIDERS[key]
        lo, hi = ot.RANGES[key]
        yield from _row(t(label), Slider(lo, hi, self.cfg[key], step=step, unit=unit, id=f"o-{key}"))

    def on_mount(self) -> None:
        titles = {"o-material": "Material", "o-images": "Pictures", "o-dark": "Legibility and dark mode",
                  "o-carousel": "New arrivals carousel", "o-ghost": "Hide", "o-news": "News action buttons"}
        for wid, title in titles.items():
            self.query_one(f"#{wid}").border_title = t(title)

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
        for name in ot.ASSETS:
            q(f"#o-src-{name}", Select).value = cfg[name]["source"]
            q(f"#o-val-{name}", Input).value = cfg[name]["url"]
        q("#o-dark_switch", Switch).value = cfg["dark_switch"]
        q("#o-default_theme", Select).value = cfg["default_theme"]
        car = cfg["carousel"]
        q("#o-car-enabled", Switch).value = car["enabled"]
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

    def collect(self) -> tuple[dict, dict[str, tuple[str, Path]], str]:
        """(settings, pictures still to publish {name: (source, file)}, problem)."""
        q = self.query_one
        raw = {"texture": q("#o-texture", Select).value,
               "accent": q("#o-accent", Input).value, "accent2": q("#o-accent2", Input).value,
               "dark_switch": q("#o-dark_switch", Switch).value,
               "default_theme": q("#o-default_theme", Select).value,
               "carousel": {"enabled": q("#o-car-enabled", Switch).value, "title": q("#o-car-title", Input).value,
                            "autoplay": q("#o-car-autoplay", Switch).value, "speed": q("#o-speed", Slider).value,
                            "count": q("#o-count", Slider).value, "hover": q("#o-car-hover", Select).value,
                            "overlay": q("#o-car-overlay", Switch).value,
                            "amazon_tag": q("#o-car-tag", Input).value.strip()},
               "ghost": {key: q(f"#o-g-{key}", Switch).value for key in GHOST},
               "news_buttons": q("#o-news_buttons", Switch).value}
        for key in SLIDERS:
            raw[key] = q(f"#o-{key}", Slider).value
        if raw["carousel"]["amazon_tag"] and not ot.normalize(raw)["carousel"]["amazon_tag"]:
            return raw, {}, t("The Amazon tag has only letters, digits and hyphens.")
        pending: dict[str, tuple[str, Path]] = {}
        for name in ot.ASSETS:
            source = q(f"#o-src-{name}", Select).value
            value = q(f"#o-val-{name}", Input).value.strip()
            label = t(ASSET_LABELS[name])
            raw[name] = {"source": source, "url": ""}
            if source == "none":
                continue
            if not value:
                return raw, {}, t("${name}: choose a file or type an address.", name=label)
            if value == self.cfg[name]["url"] and source == self.cfg[name]["source"]:
                raw[name]["url"] = value                      # already published
            elif source == "url":
                if not ot.safe_url(value):
                    return raw, {}, t("${name}: the address must start with https://.", name=label)
                raw[name]["url"] = value
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
        actions = {"o-apply": self.apply, "o-preview": self.preview, "o-reload": self.reload,
                   "o-refresh": self.refresh_carousel, "o-keys": self.keys, "o-remove": self.remove_look}
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

    def summary(self, applied: bool = False) -> None:
        text = t("Applied in Koha.") if applied else t("Not applied yet: Koha shows its own look.")
        if self.carousel_on:
            text += " · " + t("Carousel: ${n} titles with a cover.", n=self.feed_items or "0")
        self.query_one("#o-summary", Label).update(text)

    def preview(self) -> None:
        raw, _pending, problem = self.collect()
        if problem:
            self.app.notify(problem, severity="warning")
            return
        text = ("OpacUserCSS\n\n" + ot.css_block(raw) + "\n\nOpacUserJS\n\n" + ot.js_block(raw, self.js_text()))
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
                raw[name]["url"] = url
        files = {n: p for n, (s, p) in pending.items() if s == "local"}
        for name, path in files.items():
            raw[name]["url"] = ot.local_url(name, path)
        cfg = ot.normalize(raw)
        lines = [f"{t('Texture')}: {t(ot.TEXTURES[cfg['texture']])}",
                 f"{t('New arrivals carousel')}: {t('on') if cfg['carousel']['enabled'] else t('off')}"]
        lines += [f"{t(ASSET_LABELS[n])}: {cfg[n]['url']}" for n in ot.ASSETS if cfg[n]["url"]]
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


def _name_problem(value: str) -> str:
    return "" if re.fullmatch(r"[A-Za-z0-9_-]{0,64}", value) else t("Only letters, digits, _ and -.")


def _loader(title: str, job):
    from ..screens.loading import LoadingScreen
    return LoadingScreen(title, job)

