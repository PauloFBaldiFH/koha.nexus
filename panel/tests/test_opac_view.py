"""The OPAC appearance screen, driven headless in demo mode."""

import asyncio
import time

from conftest import INSTALLER
from textual.widgets import Button, Input, Select, Switch

from kei_panel import opac_theme as ot
from kei_panel.env import PanelEnv
from kei_panel.screens.dialogs import ConfirmScreen, InputScreen, MessageScreen, TextScreen
from kei_panel.widgets.colorpick import ColorPicker, GradientBar, hex_to_hsl, hsl_to_hex
from kei_panel.widgets.slider import Slider

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40


async def _until(pilot, cond, wait=8.0):
    deadline = time.monotonic() + wait
    while not cond() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert cond()


def test_colour_picker_bars_and_code():
    from textual.app import App

    class One(App):
        def compose(self):
            yield ColorPicker("Accent", "#2563eb", "acc", ("Hue", "Saturation", "Lightness"))

    assert hsl_to_hex(*hex_to_hsl("#ff0066")) == "#ff0066" and hex_to_hsl("2563eb") is None

    async def main():
        app = One()
        async with app.run_test(size=(80, 14)) as pilot:
            field = app.query_one("#acc", Input)
            hue, light = app.query_one(".cp-h", GradientBar), app.query_one(".cp-l", GradientBar)
            assert (hue.value, light.value) == hex_to_hsl("#2563eb")[::2]
            # Typing a code moves the bars and keeps the code as typed.
            field.value = "#ff0066"
            await _until(pilot, lambda: hue.value == 336)
            await pilot.pause(0.1)
            assert field.value == "#ff0066"
            # Moving a bar writes the code.
            light.focus()
            await pilot.press("end")
            await _until(pilot, lambda: field.value == "#ffffff")
            await pilot.press("home")
            await _until(pilot, lambda: field.value == "#000000")
            await pilot.press("pagedown", "pagedown", "pagedown", "pagedown", "pagedown")
            hue.focus()
            await pilot.press("home")
            await _until(pilot, lambda: field.value == hsl_to_hex(0, 100, 50))
            # A click on the hue bar picks the colour under the mouse.
            await pilot.click(hue, offset=(hue.size.width - 1, 0))
            await _until(pilot, lambda: hue.value == 359)

    asyncio.run(main())


def test_slider_keys_and_range():
    from textual.app import App

    class One(App):
        def compose(self):
            yield Slider(0, 30, 14, unit="px", id="s")

    async def main():
        app = One()
        async with app.run_test(size=(60, 5)) as pilot:
            s = app.query_one("#s", Slider)
            s.focus()
            await pilot.press("right", "right")
            assert s.value == 16
            await pilot.press("end")
            assert s.value == 30 and "30px" in str(s.render())
            await pilot.press("right", "home")
            assert s.value == 0
            s.value = 99
            assert s.value == 30
    asyncio.run(main())


def test_edit_preview_apply_and_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_OPAC_KEYS", str(tmp_path / "opac-theme.conf"))
    logo = tmp_path / "logo.png"
    logo.write_bytes(PNG)
    seen = {}
    real = ot.write_apply_dir

    def spy(cfg, files, text=None):
        work = real(cfg, files, text)
        seen["work"], seen["css"], seen["files"] = work, (work / "user.css").read_text(), sorted(
            p.name for p in (work / "assets").iterdir())
        return work
    monkeypatch.setattr(ot, "write_apply_dir", spy)
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            await pilot.pause(0.3)
            view = app.screen.query_one("#view-opac")
            await _until(pilot, lambda: "Not applied" in str(view.query_one("#o-summary").render()))

            view.query_one("#o-texture", Select).value = "metal"
            view.query_one("#o-radius_block", Slider).value = 24
            view.query_one("#o-src-logo", Select).value = "local"
            view.query_one("#o-val-logo", Input).value = str(logo)
            view.query_one("#o-src-background", Select).value = "url"
            view.query_one("#o-val-background", Input).value = "javascript:alert(1)"
            cfg, pending, problem = view.collect()
            assert "https://" in problem
            view.query_one("#o-val-background", Input).value = "https://i.postimg.cc/abc/wall.jpg"
            view.query_one("#o-src-favicon", Select).value = "imgbb"
            view.query_one("#o-val-favicon", Input).value = str(logo)
            view.query_one("#o-g-rss", Switch).value = False
            cfg, pending, problem = view.collect()
            assert problem == "" and set(pending) == {"logo", "favicon"}

            view.preview()
            await _until(pilot, lambda: isinstance(app.screen, TextScreen))
            assert "repeating-linear-gradient" in app.screen._text and "--kei-r-block: 24px" in app.screen._text
            await pilot.press("escape")

            view.apply()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "https://i.ibb.co/demo/kei-favicon.png" in app.screen._preview
            await pilot.pause(0.1)
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert "new look is in the OPAC" in app.screen._body
            assert not seen["work"].exists()                     # the folder handed to Koha is gone
            assert seen["files"] == ["kei-logo.png"]             # the ImgBB one went to the host
            sent = ot.parse_theme_data(seen["css"])
            assert sent["texture"] == "metal" and sent["radius_block"] == 24 and not sent["ghost"]["rss"]
            assert sent["logo"]["url"].startswith("/images/custom/kei-logo.png?v=")
            assert sent["background"]["url"] == "https://i.postimg.cc/abc/wall.jpg"
            await pilot.press("escape")

            # Image host keys: kept privately, the key never shown again.
            view.keys()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen) and app.screen.query("#ok"))
            assert app.screen._password
            app.screen.query_one("#value").value = "imgbb-S3CRET"
            app.screen.query_one("#ok").press()
            await _until(pilot, lambda: isinstance(app.screen, InputScreen) and not app.screen._password and app.screen.query("#ok"))
            app.screen.query_one("#value").value = "democloud"
            app.screen.query_one("#ok").press()
            await pilot.pause(0.2)
            app.screen.query_one("#value").value = "kei_unsigned"
            app.screen.query_one("#ok").press()
            await _until(pilot, lambda: (tmp_path / "opac-theme.conf").exists())
            assert ot.load_keys() == {"imgbb_key": "imgbb-S3CRET", "cloudinary_cloud": "democloud",
                                      "cloudinary_preset": "kei_unsigned"}
            assert (tmp_path / "opac-theme.conf").stat().st_mode & 0o777 == 0o600

            view.remove_look()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.pause(0.1)
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            assert "back to Koha's own look" in app.screen._body
            await pilot.press("escape")
            await _until(pilot, lambda: view.query_one("#o-texture", Select).value == "frosted")

    asyncio.run(main())


def test_settings_come_back_from_koha(monkeypatch):
    """The screen opens with the settings of the block in OpacUserCSS."""
    from kei_panel import demo
    cfg = ot.normalize({"texture": "gradient", "accent": "#ff0066", "carousel": {"count": 20, "hover": "tilt"}})
    monkeypatch.setitem(demo._SCRIPTS, "opac-theme-get", [f"@@result data={ot.data_line(cfg)}",
                                                          "@@result carousel=on", "@@result feed_items=17"])
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            view = app.screen.query_one("#view-opac")
            await _until(pilot, lambda: view.query_one("#o-texture", Select).value == "gradient")
            assert view.query_one("#o-accent", Input).value == "#ff0066"
            assert view.query_one("#o-count", Slider).value == 20
            assert view.query_one("#o-car-hover", Select).value == "tilt"
            assert "17 titles" in str(view.query_one("#o-summary").render())

    asyncio.run(main())


def test_buttons_carousel_mode_colours_and_staff(monkeypatch):
    """Quick access buttons (rows of fields), the 3D carousel, the block and
    page colours and the staff interface travel to Koha and come back."""
    seen = {}
    real = ot.write_apply_dir

    def spy(cfg, files, text=None):
        work = real(cfg, files, text)
        seen["css"] = (work / "user.css").read_text()
        seen["js"] = (work / "user.js").read_text()
        seen["staff"] = (work / "staff.css").read_text() if (work / "staff.css").exists() else ""
        return work
    monkeypatch.setattr(ot, "write_apply_dir", spy)
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            view = app.screen.query_one("#view-opac")
            await _until(pilot, lambda: "Not applied" in str(view.query_one("#o-summary").render()))
            view.query_one("#o-car-mode", Select).value = "coverflow"
            view.query_one("#o-surface", Input).value = "#1e293b"
            view.query_one("#o-page-on", Switch).value = True
            view.query_one("#o-page", Input).value = "#0f172a"
            view.query_one("#o-links-enabled", Switch).value = True
            view.query_one("#o-links-style", Select).value = "gradient"
            for _ in range(2):
                view.query_one("#o-link-add").press()
                await pilot.pause(0.1)
            rows = list(view.query(".link-row"))
            assert len(rows) == 2
            fields = lambda row: (row.query(Input).results(), row.query_one(Select))   # noqa: E731
            (order, icon, text, url), target = list(fields(rows[0])[0]), fields(rows[0])[1]
            assert order.value == "1"
            icon.value, text.value, url.value, target.value = "📖", "Catálogo", "javascript:alert(1)", "_blank"
            _cfg, _p, problem = view.collect()
            assert "https://" in problem
            url.value = "https://biblioteca.example.org/acervo"
            (order2, icon2, text2, url2) = list(rows[1].query(Input).results())
            assert order2.value == "2"
            icon2.value, text2.value, url2.value = "📧", "Contato", "mailto:biblioteca@example.org"
            view.query_one("#o-staff-enabled", Switch).value = True
            view.query_one("#o-staff-density", Select).value = "compact"
            view.query_one("#o-staff-contrast", Select).value = "high"
            cfg, _p, problem = view.collect()
            assert problem == ""
            # Removing a row drops its button.
            view.query_one(f"#{rows[1].id.replace('o-link-', 'o-link-del-')}").press()
            await pilot.pause(0.1)
            assert len(view.query(".link-row")) == 1
            rows[1] = None
            view.add_link({"icon": "📧", "text": "Contato", "url": "mailto:biblioteca@example.org", "target": "_self"})
            await pilot.pause(0.1)

            view.apply()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "3D coverflow" in app.screen._preview and "Quick access buttons: 2" in app.screen._preview
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            await pilot.press("escape")
            sent = ot.parse_theme_data(seen["css"])
            assert sent["carousel"]["mode"] == "coverflow"
            assert sent["surface"] == "#1e293b" and sent["page"] == "#0f172a"
            assert [i["text"] for i in sent["links"]["items"]] == ["Catálogo", "Contato"]
            assert sent["links"]["items"][0]["target"] == "_blank"
            assert '"mode": "coverflow"' in seen["js"] and "kei-links" in seen["js"]
            assert "--kei-text: #f1f5f9" in seen["css"]           # light text on the dark blocks
            assert "padding: .2rem .45rem" in seen["staff"] and "kei-carousel" not in seen["staff"]

            # The same settings fill the screen again.
            view.fill({})
            await pilot.pause(0.1)
            assert len(view.query(".link-row")) == 0
            view.fill(sent)
            await pilot.pause(0.2)
            assert len(view.query(".link-row")) == 2
            assert view.query_one("#o-staff-density", Select).value == "compact"

    asyncio.run(main())


def test_order_layout_metal_and_staff_buttons(monkeypatch):
    """Each button has its place in the list; two columns, brushed metal and
    the staff home page's own buttons travel to Koha (IntranetUserJS)."""
    seen = {}
    real = ot.write_apply_dir

    def spy(cfg, files, text=None):
        work = real(cfg, files, text)
        seen["css"] = (work / "user.css").read_text()
        seen["staff_css"] = (work / "staff.css").read_text() if (work / "staff.css").exists() else ""
        seen["staff_js"] = (work / "staff.js").read_text() if (work / "staff.js").exists() else ""
        return work
    monkeypatch.setattr(ot, "write_apply_dir", spy)
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            view = app.screen.query_one("#view-opac")
            await _until(pilot, lambda: "Not applied" in str(view.query_one("#o-summary").render()))
            view.query_one("#o-links-enabled", Switch).value = True
            view.query_one("#o-links-style", Select).value = "metal"
            view.query_one("#o-links-layout", Select).value = "grid2"
            view.add_link({"icon": "📖", "text": "Catálogo", "url": "/cgi-bin/koha/opac-search.pl",
                           "target": "_self", "sort_order": 1})
            view.add_link({"icon": "📧", "text": "Contato", "url": "mailto:b@example.org", "target": "_self",
                           "sort_order": 2})
            await pilot.pause(0.1)
            # Contato first: its number goes below Catálogo's.
            first, second = list(view.query(".link-row"))
            first.query_one(".link-order", Input).value = "5"
            # A new button is numbered after the last one.
            view.query_one("#o-link-add").press()
            await pilot.pause(0.1)
            assert list(view.query(".link-row"))[-1].query_one(".link-order", Input).value == "6"

            view.query_one("#o-slinks-enabled", Switch).value = True
            view.query_one("#o-slinks-layout", Select).value = "grid2"
            view.query_one("#o-slink-add").press()
            await pilot.pause(0.1)
            srow = view.query_one(".slink-row")
            assert srow.query_one(".link-order", Input).value == "1"
            order, icon, text, url = list(srow.query(Input).results())
            icon.value, text.value, url.value = "fa-exchange", "Circulação", "javascript:alert(1)"
            _cfg, _p, problem = view.collect()
            assert problem.startswith("Staff home page buttons:")
            url.value = "/cgi-bin/koha/circ/circulation-home.pl"
            cfg, _p, problem = view.collect()
            assert problem == ""

            view.apply()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert "Staff home page buttons: 1" in app.screen._preview
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            await pilot.press("escape")
            sent = ot.parse_theme_data(seen["css"])
            assert [(i["text"], i["sort_order"]) for i in sent["links"]["items"]] == [("Contato", 2), ("Catálogo", 5)]
            assert sent["links"]["style"] == "metal" and sent["links"]["layout"] == "grid2"
            assert "kei-links-metal" in seen["css"] and "kei-layout-grid2" in seen["css"]
            assert sent["staff_links"]["items"][0]["url"] == "/cgi-bin/koha/circ/circulation-home.pl"
            assert "kei-staff-links" in seen["staff_js"] and "Circula" in seen["staff_js"]
            assert "#kei-staff-links" in seen["staff_css"] and "nexus-staff-page" not in seen["staff_css"]

            # Back on the screen in the order they are shown.
            view.fill(sent)
            await pilot.pause(0.2)
            assert [r.query_one(".link-text", Input).value for r in view.query(".link-row")] == ["Contato", "Catálogo"]
            assert len(view.query(".slink-row")) == 1

    asyncio.run(main())


def test_sync_reads_what_is_live_in_koha(monkeypatch):
    """Sync current OPAC settings: the fields take what Koha has, and a report
    says what was found; [kei-button] markers turn the news buttons on."""
    from kei_panel import demo
    cfg = ot.normalize({"texture": "smooth", "news_buttons": False,
                        "links": {"enabled": True, "items": [{"text": "A", "url": "/a"}, {"text": "B", "url": "/b"}]}})
    monkeypatch.setitem(demo._SCRIPTS, "opac-theme-sync", [
        f"@@result data={ot.data_line(cfg)}", "@@result block_OpacUserCSS=yes", "@@result block_OpacUserJS=no",
        "@@result own_OpacUserCSS=4", "@@result mainblock=yes", "@@result mainblock_buttons=3"])
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            view = app.screen.query_one("#view-opac")
            await _until(pilot, lambda: "Not applied" in str(view.query_one("#o-summary").render()))
            view.query_one("#o-sync").press()
            await _until(pilot, lambda: isinstance(app.screen, TextScreen))
            report = app.screen._text
            assert "read from OpacUserCSS" in report and "missing from OpacUserJS" in report
            assert "3 [kei-button] markers" in report and "News action buttons turned on" in report
            assert "OpacUserCSS: 4 lines" in report and "Nothing was written to Koha" in report
            await pilot.press("escape")
            assert view.query_one("#o-texture", Select).value == "smooth"
            assert view.query_one("#o-news_buttons", Switch).value is True
            assert len(view.query(".link-row")) == 2

    asyncio.run(main())


def test_staff_material_and_copy_opac_preset(monkeypatch):
    """The staff box has the OPAC's material (texture, blur, opacity, corners,
    page colour); Copy OPAC preset fills it from the OPAC fields in one click,
    the staff's own text size and density kept, and Apply sends it."""
    seen = {}
    real = ot.write_apply_dir

    def spy(cfg, files, text=None):
        work = real(cfg, files, text)
        seen["staff"] = (work / "staff.css").read_text() if (work / "staff.css").exists() else ""
        return work
    monkeypatch.setattr(ot, "write_apply_dir", spy)
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            view = app.screen.query_one("#view-opac")
            q = view.query_one
            await _until(pilot, lambda: "Not applied" in str(q("#o-summary").render()))
            assert q("#o-staff-texture", Select).value == "flat"         # nothing changes until chosen
            q("#o-texture", Select).value = "metal"
            q("#o-blur", Slider).value = 21
            q("#o-radius_input", Slider).value = 3
            q("#o-accent", Input).value = "#0f766e"
            q("#o-val-logo", Input).value = "https://img.example.org/logo.png"
            q("#o-src-logo", Select).value = "url"
            q("#o-staff-font", Slider).value = 110
            await pilot.pause(0.1)
            q("#o-staff-copy", Button).press()
            await pilot.pause(0.2)
            assert q("#o-staff-enabled", Switch).value is True
            assert q("#o-staff-texture", Select).value == "metal"
            assert q("#o-staff-blur", Slider).value == 21 and q("#o-staff-radius_input", Slider).value == 3
            assert q("#o-staff-accent", Input).value == "#0f766e"
            assert q("#o-val-staff-logo", Input).value == "https://img.example.org/logo.png"
            assert q("#o-staff-font", Slider).value == 110                # the staff's own, kept
            q("#o-staff-page-on", Switch).value = True
            q("#o-staff-page", Input).value = "#101820"
            cfg, _p, problem = view.collect()
            assert problem == "" and cfg["staff"]["page"] == "#101820"

            view.apply()
            await _until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            app.screen.query_one("#yes").press()
            await _until(pilot, lambda: isinstance(app.screen, MessageScreen))
            await pilot.press("escape")
            assert "--nexus-staff-r-input: 3px" in seen["staff"] and "--nexus-staff-blur: 21px" in seen["staff"]
            assert "repeating-linear-gradient" in seen["staff"]          # brushed metal on the staff blocks
            assert "html { font-size: 110%; }" in seen["staff"]

    asyncio.run(main())


def test_login_instructions_and_credits(tmp_path, monkeypatch):
    """The login pages and footer credits boxes: checked fields, a banner file
    for each side's folder, and the forms come back from theme-settings.json."""
    from kei_panel import demo
    banner = tmp_path / "banner.png"
    banner.write_bytes(PNG)
    saved = ot.normalize({"credits": {"enabled": True, "name": "Biblioteca Municipal", "cnpj": "00000000000000"}})
    monkeypatch.setitem(demo._SCRIPTS, "opac-theme-get", [
        f"@@result data={ot.data_line(saved)}",
        "@@result contents_settings=" + __import__("json").dumps(ot.contents_settings(saved))])
    from textual.widgets import TextArea
    from kei_panel.app import KohaPanelApp

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("o")
            view = app.screen.query_one("#view-opac")
            await _until(pilot, lambda: view.query_one("#o-cr-name", Input).value == "Biblioteca Municipal")
            assert view.query_one("#o-cr-cnpj", Input).value == "00.000.000/0000-00"
            assert view.query_one("#o-credits").border_title == "Footer credits"
            view.query_one("#o-cr-email", Input).value = "not-an-email"
            _cfg, _pending, problem = view.collect()
            assert problem.startswith("Footer credits: E-mail")
            view.query_one("#o-cr-email", Input).value = "contato@biblioteca.gov.br"
            view.query_one("#o-cr-links", TextArea).text = "Portal | https://biblioteca.gov.br\nno bar here"
            _cfg, _pending, problem = view.collect()
            assert "write the text, a | and the address" in problem
            view.query_one("#o-cr-links", TextArea).text = "Portal | https://biblioteca.gov.br"
            view.query_one("#o-login-opac-enabled", Switch).value = True
            view.query_one("#o-login-opac-html", TextArea).text = "<h2>Ask at the desk</h2><script>x()</script>"
            view.query_one("#o-src-login", Select).value = "local"
            view.query_one("#o-val-login", Input).value = str(banner)
            view.query_one("#o-login-staff-enabled", Switch).value = True
            view.query_one("#o-src-staff-login", Select).value = "url"
            view.query_one("#o-val-staff-login", Input).value = "https://i.ibb.co/x/staff.png"
            raw, pending, problem = view.collect()
            assert problem == "" and set(pending) == {"login"}
            cfg = ot.normalize(raw)
            assert cfg["credits"]["links"] == [{"text": "Portal", "url": "https://biblioteca.gov.br"}]
            assert cfg["login"]["opac"]["html"] == "<h2>Ask at the desk</h2>"
            assert cfg["login"]["staff"]["image"]["url"] == "https://i.ibb.co/x/staff.png"
            assert ot.local_url("login", banner).startswith("/images/custom/kei-login.png?v=")
            assert ot.local_url("staff-login", banner).startswith("/intranet-tmpl/kei-custom/kei-staff-login.png")
            view.preview()
            await _until(pilot, lambda: isinstance(app.screen, TextScreen))
            assert "opaccredits (HTML customizations)" in app.screen._text
            assert "StaffLoginInstructions (HTML customizations)" in app.screen._text
            await pilot.pause(0.2)
            await pilot.press("escape")

    asyncio.run(main())
