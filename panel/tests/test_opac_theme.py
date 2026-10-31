"""opac_theme: the settings, the CSS/JS blocks Koha receives, the pictures."""

import base64
import json
import re
import shutil
import subprocess
import urllib.parse

import pytest

from kei_panel import opac_theme as ot

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40
JPG = b"\xff\xd8\xff\xe0" + b"\0" * 40


def test_normalize_clamps_and_drops():
    cfg = ot.normalize({"texture": "neon", "blur": 99, "opacity": "5", "radius_block": -3, "radius_input": "x",
                        "accent": "abc", "accent2": "red", "film": 200, "default_theme": "pink",
                        "background": {"source": "url", "url": "javascript:alert(1)"},
                        "logo": {"source": "url", "url": "https://i.postimg.cc/x/logo.png"},
                        "favicon": {"source": "none", "url": "https://a.org/f.ico"},
                        "carousel": {"speed": 1, "count": 99, "hover": "spin", "title": "<b>New</b>\n",
                                     "amazon_tag": "bad tag!"},
                        "ghost": {"rss": False, "unknown": True}, "extra": 1})
    assert cfg["texture"] == "frosted" and cfg["blur"] == 30 and cfg["opacity"] == 5   # free from 0 to 100
    assert cfg["radius_block"] == 0 and cfg["radius_input"] == ot.DEFAULTS["radius_input"]
    assert cfg["accent"] == "#aabbcc" and cfg["accent2"] == ot.DEFAULTS["accent2"]
    assert cfg["film"] == 90 and cfg["default_theme"] == "light"
    assert cfg["background"] == {"source": "url", "url": ""}
    assert cfg["logo"]["url"] == "https://i.postimg.cc/x/logo.png"
    assert cfg["favicon"] == {"source": "none", "url": ""}
    car = cfg["carousel"]
    assert (car["speed"], car["count"], car["hover"]) == (2000, 24, "lift")
    assert car["title"] == "bNew/b" and car["amazon_tag"] == ""
    assert cfg["ghost"] == {"rss": False, "cart_badge": True, "cart": False, "community": True, "empty_columns": True}
    assert "extra" not in cfg


@pytest.mark.parametrize("url, ok", [
    ("https://i.ibb.co/abc/kei-logo.png", True),
    ("/images/custom/kei-logo.png?v=1a2b", True),
    ("http://example.org/a.png", False),
    ("javascript:alert(1)", False),
    ("https://a.org/x.png');}body{x:url(", False),
    ("https://a.org/a b.png", False),
    ("//evil.org/a.png", False),  # another host, without a scheme
])
def test_safe_url(url, ok):
    assert bool(ot.safe_url(url)) is ok


def test_settings_travel_in_the_css_and_come_back():
    cfg = ot.normalize({"texture": "metal", "carousel": {"title": "Novidades */ </style>"}})
    block = ot.css_block(cfg)
    assert ot.check_block(block, ot.CSS_BEGIN, ot.CSS_END) == ""
    assert block.splitlines()[1].startswith("/* KEI-THEME-DATA: ")
    assert ot.parse_theme_data("#mine { }\n" + block) == cfg
    assert ot.parse_theme_data("nothing here") is None
    assert ot.parse_theme_data("/* KEI-THEME-DATA: {broken */") is None


@pytest.mark.parametrize("texture, needle", [
    ("frosted", "backdrop-filter: blur(var(--koha-glass-blur))"),
    ("metal", "feTurbulence"),
    ("anodized", "rgba(var(--kei-accent-rgb), .26)"),
    ("wood", "rgba(176, 116, 58, .34)"),
    ("paper", "rgba(250, 242, 222, .30)"),
    ("gradient", "linear-gradient(135deg"),
    ("flat", "--koha-glass-blur: 0px;"),
])
def test_textures(texture, needle):
    css = ot.css_body(ot.normalize({"texture": texture}))
    assert needle in css
    assert "#opac-main-search" in css and ".main" in css and ".navbar" in css


def test_css_variables_ghosts_and_wallpaper():
    cfg = ot.normalize({"radius_block": 22, "radius_input": 4, "radius_button": 30, "accent": "#112233",
                        "background": {"source": "url", "url": "https://i.ibb.co/x/wall.jpg"},
                        "logo": {"source": "local", "url": "/images/custom/kei-logo.png?v=1"},
                        "ghost": {"rss": True, "cart_badge": False, "community": True, "empty_columns": True}})
    css = ot.css_body(cfg)
    for var in ("--koha-card-radius: 22px", "--kei-r-input: 4px", "--kei-r-btn: 30px", "--kei-accent: #112233"):
        assert var in css
    assert 'url("https://i.ibb.co/x/wall.jpg")' in css and "--kei-film" in css
    assert 'url("/images/custom/kei-logo.png?v=1")' in css
    assert "#rssnews" in css and "koha-community.org" in css and "#cartmenulink .badge" not in css
    assert '[data-kei-theme="dark"]' in css
    off = ot.css_body(ot.normalize({"ghost": {"rss": False, "cart_badge": False, "community": False,
                                              "empty_columns": False}}))
    assert "#rssnews" not in off and "koha-community.org" not in off and ".kei-empty-col {" not in off


def test_js_block_config():
    cfg = ot.normalize({"default_theme": "auto", "carousel": {"enabled": True, "count": 8, "hover": "tilt"}})
    block = ot.js_block(cfg, {"available": "Disponível"})
    assert ot.check_block(block, ot.JS_BEGIN, ot.JS_END) == ""
    conf = ot.js_config(cfg, {"available": "Disponível"})
    assert conf["carousel"]["feed"] == ot.FEED_URL and conf["carousel"]["count"] == 8
    assert conf["text"]["available"] == "Disponível" and conf["text"]["next"] == "Next"
    assert "kei_theme" in block and "opac-detail.pl?biblionumber=" in block and "kei-button" in block
    assert ot.js_config(ot.normalize({"carousel": {"enabled": False}}))["carousel"] is None
    # A title cannot close Koha's <script>.
    evil = ot.js_block(ot.normalize({"carousel": {"title": "</script>x"}}))
    assert "</script" not in evil.lower()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_is_valid_javascript(tmp_path):
    js = tmp_path / "user.js"
    js.write_text(ot.js_block(ot.DEFAULTS), encoding="utf-8")
    subprocess.run(["node", "--check", str(js)], check=True)


def test_check_block():
    good = f"{ot.CSS_BEGIN}\na {{ }}\n{ot.CSS_END}\n"
    assert ot.check_block(good, ot.CSS_BEGIN, ot.CSS_END) == ""
    assert ot.check_block("a { }", ot.CSS_BEGIN, ot.CSS_END)
    assert ot.check_block(f"{ot.CSS_BEGIN}\n</style>\n{ot.CSS_END}", ot.CSS_BEGIN, ot.CSS_END)
    assert ot.check_block(f"{ot.CSS_BEGIN}\n{ot.CSS_END}\n{ot.CSS_END}", ot.CSS_BEGIN, ot.CSS_END)


def test_image_problem(tmp_path):
    (tmp_path / "a.png").write_bytes(PNG)
    (tmp_path / "b.jpeg").write_bytes(JPG)
    (tmp_path / "c.png").write_bytes(JPG)
    (tmp_path / "d.svg").write_text("<svg onload='alert(1)'/>")
    (tmp_path / "e.gif").write_bytes(b"")
    assert ot.image_problem(tmp_path / "a.png") == ""
    assert ot.image_problem(tmp_path / "b.jpeg") == ""
    assert "not the picture" in ot.image_problem(tmp_path / "c.png")
    assert "PNG" in ot.image_problem(tmp_path / "d.svg")
    assert ot.image_problem(tmp_path / "e.gif")
    assert ot.image_problem(tmp_path / "missing.png")
    assert ot.local_name("logo", tmp_path / "b.jpeg") == "kei-logo.jpg"
    assert ot.local_url("logo", tmp_path / "a.png").startswith("/images/custom/kei-logo.png?v=")


def test_keys_file_is_private(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_OPAC_KEYS", str(tmp_path / "k" / "opac-theme.conf"))
    assert ot.load_keys() == {}
    ot.save_keys({"imgbb_key": "secret", "cloudinary_cloud": ""})
    path = tmp_path / "k" / "opac-theme.conf"
    assert path.stat().st_mode & 0o777 == 0o600
    assert ot.load_keys() == {"imgbb_key": "secret"}


def test_upload_imgbb(tmp_path):
    pic = tmp_path / "logo.png"
    pic.write_bytes(PNG)
    seen = {}

    def post(url, body, ctype):
        seen.update(url=url, body=urllib.parse.parse_qs(body.decode()), ctype=ctype)
        return {"success": True, "data": {"url": "https://i.ibb.co/Ab1/logo.png"}}
    assert ot.upload_imgbb(pic, "K3Y", post=post) == "https://i.ibb.co/Ab1/logo.png"
    assert seen["url"] == "https://api.imgbb.com/1/upload" and seen["body"]["key"] == ["K3Y"]
    with pytest.raises(ValueError, match="Invalid API"):
        ot.upload_imgbb(pic, "bad", post=lambda *a: {"success": False, "error": {"message": "Invalid API v1 key."}})
    with pytest.raises(ValueError):
        ot.upload_imgbb(pic, "", post=post)
    with pytest.raises(ValueError):   # a link the stylesheet could not carry
        ot.upload_imgbb(pic, "K", post=lambda *a: {"success": True, "data": {"url": "http://x/a.png"}})


def test_upload_cloudinary(tmp_path):
    pic = tmp_path / "wall.jpg"
    pic.write_bytes(JPG)
    seen = {}

    def post(url, body, ctype):
        seen.update(url=url, body=body, ctype=ctype)
        return {"secure_url": "https://res.cloudinary.com/demo/image/upload/v1/wall.jpg"}
    url = ot.upload_cloudinary(pic, "demo", "unsigned_kei", post=post)
    assert url.startswith("https://res.cloudinary.com/")
    assert seen["url"] == "https://api.cloudinary.com/v1_1/demo/image/upload"
    assert seen["ctype"].startswith("multipart/form-data; boundary=") and b"unsigned_kei" in seen["body"]
    assert JPG in seen["body"]
    with pytest.raises(ValueError):
        ot.upload_cloudinary(pic, "demo/../x", "p", post=post)


def test_carousel_from_a_koha_list(tmp_path):
    """Source "list": the home carousel reads that list's feed; the list
    feeds (KEI.listCarousel, data-kei-list) follow the carousel or their own
    switch, and both come back from the script's config."""
    cfg = ot.normalize({"carousel": {"enabled": True, "source": "list", "shelf": "7", "mode": "coverflow"}})
    car = cfg["carousel"]
    assert car["source"] == "list" and car["shelf"] == 7 and not car["lists"]
    conf = ot.js_config(cfg)
    assert conf["carousel"]["feed"] == "/images/custom/kei-list-7.json" and conf["carousel"]["shelf"] == 7
    assert conf["lists"] == {"feed": ot.LIST_FEED, "always": False, "count": 12, "autoplay": True, "speed": 3500,
                             "hover": "lift", "overlay": True, "mode": "coverflow"}
    # No list number: back to the new arrivals.
    assert ot.normalize({"carousel": {"source": "list", "shelf": "x"}})["carousel"]["source"] == "new"
    assert ot.normalize({"carousel": {"source": "list", "shelf": -3}})["carousel"]["shelf"] == 0
    block = ot.js_block(cfg)
    assert "KEI.listCarousel = function" in block and "[data-kei-list]" in block and "opac-image\\.pl" in block
    # Home carousel off, list feeds kept: the job stays, the CSS too, no home carousel.
    only = ot.normalize({"carousel": {"enabled": False, "lists": True, "count": 9}})
    conf = ot.js_config(only)
    assert conf["carousel"] is None and conf["lists"]["always"] and conf["lists"]["count"] == 9
    assert ".kei-carousel {" in ot.css_body(only)
    work = ot.write_apply_dir(only, {})
    try:
        assert (work / "carousel").read_text() == "on 9\n"
    finally:
        shutil.rmtree(work)
    both_off = ot.normalize({"carousel": {"enabled": False}})
    assert ot.js_config(both_off)["lists"] is None and ".kei-carousel {" not in ot.css_body(both_off)
    # The script's config tells the settings again (Sync current settings).
    back = ot.normalize(ot._from_script(ot.js_config(cfg)))["carousel"]
    assert back["source"] == "list" and back["shelf"] == 7 and back["enabled"] and not back["lists"]
    back = ot.normalize(ot._from_script(ot.js_config(only)))["carousel"]
    assert not back["enabled"] and back["lists"] and back["count"] == 9
    if shutil.which("node"):
        f = tmp_path / "list.js"
        f.write_text(block.split("\n", 1)[1].rsplit("\n", 2)[0], encoding="utf-8")
        subprocess.run(["node", "--check", str(f)], check=True)


def test_write_apply_dir(tmp_path):
    pic = tmp_path / "fav.png"
    pic.write_bytes(PNG)
    cfg = ot.normalize({"favicon": {"source": "local", "url": ot.local_url("favicon", pic)},
                        "carousel": {"enabled": True, "count": 16, "amazon_tag": "lib-20"}})
    work = ot.write_apply_dir(cfg, {"favicon": pic})
    try:
        assert work.stat().st_mode & 0o777 == 0o700
        assert ot.parse_theme_data((work / "user.css").read_text()) == cfg
        assert ot.check_block((work / "user.js").read_text(), ot.JS_BEGIN, ot.JS_END) == ""
        prefs = (work / "prefs").read_text().splitlines()
        assert prefs[:2] == ["OPACAmazonCoverImages\t1", "AmazonAssocTag\tlib-20"]
        assert prefs[2].startswith("OpacFavicon\t/images/custom/kei-favicon.png?v=")
        assert (work / "carousel").read_text() == "on 16\n"
        assert (work / "assets" / "kei-favicon.png").read_bytes() == PNG
    finally:
        shutil.rmtree(work)
    off = ot.write_apply_dir(ot.normalize({"carousel": {"enabled": False}}), {})
    try:
        assert (off / "carousel").read_text() == "off\n" and (off / "prefs").read_text() == ""
        assert json.loads(json.dumps(ot.js_config({}))) is not None
    finally:
        shutil.rmtree(off)


def test_block_colours_links_coverflow_and_staff(tmp_path):
    cfg = ot.normalize({
        "accent": "#123456", "surface": "#1a1a1a",
        "carousel": {"enabled": True, "mode": "coverflow", "speed": 99999},
        "links": {"enabled": True, "style": "neon", "items": [
            {"icon": "📚", "text": "Catalogue", "url": "https://example.org", "target": "_blank"},
            {"icon": "x", "text": "Bad", "url": "javascript:alert(1)"}]},
        "staff": {"enabled": True, "density": "compact", "contrast": "high", "font": 300}})
    assert cfg["carousel"]["mode"] == "coverflow" and cfg["links"]["style"] == "glass"
    assert [i["text"] for i in cfg["links"]["items"]] == ["Catalogue"]
    assert cfg["staff"]["font"] == ot.STAFF_FONT[1]
    css = ot.css_body(cfg)
    assert "--nexus-primary: #123456" in css and "#opacmainblock" in css and ".mastheadsearch" in css
    assert "html body" in css and "kei-mode-coverflow" in css and "#kei-links" in css
    conf = ot.js_config(cfg)
    assert conf["carousel"]["mode"] == "coverflow" and conf["links"]["items"][0]["target"] == "_blank"
    assert ot.normalize({"carousel": {"mode": "spiral"}})["carousel"]["mode"] == "flat"
    assert ot.normalize({})["carousel"]["speed"] == 3500
    work = ot.write_apply_dir(cfg, {})
    try:
        staff = (work / "staff.css").read_text()
        assert ot.check_block(staff, ot.CSS_BEGIN, ot.CSS_END) == "" and "#123456" in staff
        cfg["staff"]["enabled"] = False
        again = ot.write_apply_dir(cfg, {})
        assert not (again / "staff.css").exists()
        shutil.rmtree(again)
    finally:
        shutil.rmtree(work)


def test_depth_and_buttons():
    # No wallpaper: a canvas with depth under the blocks, the library's page colour kept as its base.
    plain = ot.css_body(ot.normalize({"surface": "#ffffff", "opacity": 100}))
    assert "radial-gradient" in plain and "#e8ecf2" in plain and "0 12px 32px -10px" in plain
    page = ot.css_body(ot.normalize({"page": "#f5f0e6"}))
    assert "#f5f0e6 !important" in page and "#e8ecf2" not in page
    wall = ot.css_body(ot.normalize({"page": "#f5f0e6",
                                     "background": {"source": "url", "url": "https://i.ibb.co/x/w.jpg"}}))
    assert "radial-gradient" not in wall and "background-color: #f5f0e6 !important" in wall
    # Every kind of button, and full-width touch targets in the news and the home page block.
    for sel in ("html body #searchsubmit", "html body .btn-default", 'html body input[type="submit"]:not(.btn)',
                "html body #backtotop", "html body .newsitem .btn", "html body #opacmainuserblock .btn",
                'html body #opacmainuserblock input[type="submit"]'):
        assert sel in plain, sel
    assert "width: 100% !important" in plain and "min-height: 44px" in plain
    assert "#cdd2d8" in ot.css_body(ot.normalize({"texture": "metal"})) and "#cdd2d8" not in plain
    # The settings line is untouched by the new rules.
    assert ot.parse_theme_data(ot.css_block(ot.normalize({"texture": "metal"})))["texture"] == "metal"


def test_blocks_take_the_chosen_colours():
    css = ot.css_body(ot.normalize({"accent": "#7c3aed", "accent2": "#db2777", "surface": "#ffffff"}))
    card = ot.mix("#ffffff", "#7c3aed", .03)
    assert card != "#ffffff" and f"--koha-card-rgb: {ot._rgb(card).replace(',', ', ')};" in css
    assert f"--koha-ink: {ot.mix('#7c3aed', '#000000', .30)}" in css and "--kei-ink: var(--koha-ink);" in css
    assert ot.mix("#000000", "#ffffff", .5) == "#808080"


def test_staff_has_its_own_palette():
    # Settings saved before the staff palette existed start from the OPAC's colours...
    old = ot.normalize({"accent": "#123456", "accent2": "#654321", "staff": {"enabled": True}})
    assert (old["staff"]["accent"], old["staff"]["accent2"]) == ("#123456", "#654321")
    # ...and after that the two are independent.
    cfg = ot.normalize({"accent": "#123456", "staff": {"enabled": True, "accent": "#0f766e", "accent2": "#f59e0b",
                                                       "surface": "zzz"}})
    assert cfg["staff"]["surface"] == "#ffffff"
    staff = ot.staff_css_body(cfg)
    assert "--nexus-staff-primary: #0f766e" in staff and "#123456" not in staff
    for sel in ("nav.navbar.bg-dark", "#header_search .form-content", "ul.biglinks-list li a.icon_general",
                "#area-news .newsitem .btn-acesso", "--nexus-staff-bar: " + ot.mix("#0f766e", "#000000", .22)):
        assert sel in staff, sel
    assert ot.parse_theme_data(ot.css_block(cfg))["staff"]["accent"] == "#0f766e"
    assert "#0f766e" not in ot.css_body(cfg)


def test_opac_header_menu_and_quick_links():
    css = ot.css_body(ot.normalize({"links": {"enabled": True, "items": [{"text": "A", "url": "/x"}]}}))
    assert "#header-region .dropdown-menu { z-index: 1060; }" in css and "overflow: visible !important" in css
    assert "flex-direction: column" in css and "auto-fill" not in css
    assert "html body .newsitem .btn-acesso" in css


def test_staff_content_card_one_layer():
    # Settings saved before the option: a card per section, Koha's 1rem padding.
    old = ot.normalize({"staff": {"enabled": True}})["staff"]
    assert (old["card"], old["card_padding"]) == ("sections", 16)
    bad = ot.normalize({"staff": {"card": "solid", "card_padding": 99}})["staff"]
    assert (bad["card"], bad["card_padding"]) == ("sections", ot.STAFF_CARD_PADDING[1])
    sections = ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "card_padding": 24}}))
    assert "--nexus-staff-card-pad: 24px" in sections and "html body .main .page-section" not in sections
    assert "html body #container-main, html body .main, html body main" in sections
    for texture in ot.TEXTURES:
        cfg = ot.normalize({"staff": {"enabled": True, "card": "page", "texture": texture, "opacity": 92,
                                      "background": {"source": "url", "url": "https://example.org/w.jpg"}}})
        css = ot.staff_css_body(cfg)
        # .main is the card: not in the transparent wrappers, and no !important on it,
        # so the texture and the wallpaper give it the surface at the opacity slider.
        assert "html body .main," not in css.split("background-color: transparent !important")[0]
        assert "html body .main {\n    background-color: var(--nexus-staff-card);" in css
        assert "--nexus-staff-surface-a: 0.92" in css
        # ... and the sections inside it are clear: never a card inside a card.
        inner = css.index("html body .main .page-section, html body .main fieldset.rows")
        assert inner > css.index("rgba(var(--nexus-staff-surface-rgb), var(--nexus-staff-surface-a))")
        assert "background: transparent;" in css[inner:]
        if texture == "frosted":
            assert "html body .main { isolation: auto; }" in css and "html body .main::before" in css
def test_staff_pictures_and_single_icon(tmp_path):
    cfg = ot.normalize({"favicon": {"source": "url", "url": "https://example.org/opac.ico"},
                        "staff": {"enabled": True, "film": 5,
                                  "logo": {"source": "local", "url": "/intranet-tmpl/kei-custom/kei-staff-logo.png?v=1"},
                                  "favicon": {"source": "url", "url": "https://example.org/staff.ico"},
                                  "background": {"source": "url", "url": "javascript:alert(1)"}}})
    st = cfg["staff"]
    assert st["film"] == 5 and st["background"]["url"] == ""
    staff = ot.staff_css_body(cfg)
    assert 'url("/intranet-tmpl/kei-custom/kei-staff-logo.png?v=1")' in staff and "#logo.navbar-brand img { display: none; }" in staff
    assert ".fa-stack .fa-stack-1x {{ display: none; }}".replace("{{", "{").replace("}}", "}") in staff
    assert "html body::before" not in staff                     # no wallpaper, no film
    with_bg = ot.staff_css_body(ot.normalize({"staff": {"background": {"source": "url",
                                                                       "url": "https://i.ibb.co/x/s.jpg"}}}))
    assert 'url("https://i.ibb.co/x/s.jpg")' in with_bg and "html body::before" in with_bg
    # Over the wallpaper only the cards have a surface, at the opacity slider; the wrappers stay clear.
    assert "background-color: transparent !important" in with_bg and "html body .main, html body main" in with_bg
    assert "html body .main, html body .page-section" not in with_bg       # no solid sheet over the whole content area
    assert "background-color: rgba(var(--nexus-staff-surface-rgb), var(--nexus-staff-surface-a))" in with_bg
    assert "html body .page-section .dataTables_wrapper" in with_bg
    # The staff pictures stay out of the OPAC's stylesheet.
    assert "kei-staff-logo" not in ot.css_body(cfg)
    pic = tmp_path / "logo.png"
    pic.write_bytes(b"\x89PNG\r\n\x1a\nx")
    assert ot.local_url("staff-logo", pic).startswith("/intranet-tmpl/kei-custom/kei-staff-logo.png?v=")
    assert ot.local_url("logo", pic).startswith("/images/custom/kei-logo.png?v=")
    work = ot.write_apply_dir(cfg, {"staff-logo": pic})
    try:
        prefs = (work / "prefs").read_text()
        assert "OpacFavicon\thttps://example.org/opac.ico" in prefs and "IntranetFavicon\thttps://example.org/staff.ico" in prefs
        assert (work / "assets" / "kei-staff-logo.png").exists()
    finally:
        shutil.rmtree(work)
    cfg["staff"]["enabled"] = False
    work = ot.write_apply_dir(cfg, {})
    try:
        assert "IntranetFavicon" not in (work / "prefs").read_text()
    finally:
        shutil.rmtree(work)


def test_button_order_layout_and_metal():
    # Saved before buttons had a place: 1..n as listed, nothing moves.
    old = ot.normalize({"links": {"enabled": True, "items": [{"text": "A", "url": "/a"}, {"text": "B", "url": "/b"},
                                                              {"text": "C", "url": "/c"}]}})
    assert [(i["text"], i["sort_order"]) for i in old["links"]["items"]] == [("A", 1), ("B", 2), ("C", 3)]
    assert old["links"]["layout"] == "list" and old["staff_links"]["enabled"] is False
    cfg = ot.normalize({"links": {"enabled": True, "style": "metal", "layout": "grid2", "items": [
        {"text": "A", "url": "/a", "sort_order": 9}, {"text": "B", "url": "/b", "sort_order": "x"},
        {"text": "C", "url": "/c", "sort_order": -4}, {"text": "D", "url": "/d", "sort_order": 9}]}})
    assert [(i["text"], i["sort_order"]) for i in cfg["links"]["items"]] == [("C", 1), ("B", 2), ("A", 9), ("D", 9)]
    assert ot.normalize({"links": {"layout": "grid9"}})["links"]["layout"] == "list"
    css = ot.css_body(cfg)
    assert "html body #kei-links.kei-layout-grid2" in css and "repeat(2, minmax(0, 1fr))" in css
    assert "@media (max-width: 340px)" in css
    assert "kei-links-metal a.kei-link::after" in css and "translateX(120%)" in css
    assert 'html[data-kei-theme="dark"] body #kei-links.kei-links-metal' in css
    conf = ot.js_config(cfg)["links"]
    assert conf["layout"] == "grid2" and [i["text"] for i in conf["items"]] == ["C", "B", "A", "D"]
    # The texture's own brushed metal is untouched, and glass stays the default.
    assert ot.normalize({})["links"]["style"] == "glass" and ot.normalize({})["texture"] == "frosted"


def test_staff_home_buttons(tmp_path):
    cfg = ot.normalize({"staff": {"accent": "#0f766e"}, "staff_links": {"enabled": True, "style": "solid", "items": [
        {"icon": "fa-exchange", "text": "Circulação", "url": "/cgi-bin/koha/circ/circulation-home.pl"},
        {"text": "Bad", "url": "javascript:alert(1)"}]}})
    assert [i["text"] for i in cfg["staff_links"]["items"]] == ["Circulação"]
    assert ot.staff_active(cfg) and not cfg["staff"]["enabled"]
    css = ot.staff_css_block(cfg)
    assert ot.check_block(css, ot.CSS_BEGIN, ot.CSS_END) == ""
    assert "--nexus-primary: #0f766e" in css and "#kei-staff-links.kei-links-solid" in css
    assert "nexus-staff-page" not in css                     # the colour theme stays off
    js = ot.staff_js_block(cfg, {"links": "Acesso rápido"})
    assert ot.check_block(js, ot.JS_BEGIN, ot.JS_END) == "" and "main_intranet-main" in js
    assert ot.staff_js_config(cfg)["links"]["items"][0]["icon"] == "fa-exchange"
    assert '"label": "Acesso r\\u00e1pido"' in js
    if shutil.which("node"):
        f = tmp_path / "staff.js"
        f.write_text(js, encoding="utf-8")
        subprocess.run(["node", "--check", str(f)], check=True)
    work = ot.write_apply_dir(cfg, {})
    try:
        assert (work / "staff.js").read_text() == ot.staff_js_block(cfg)
        assert "#kei-staff-links" in (work / "staff.css").read_text()
    finally:
        shutil.rmtree(work)
    cfg["staff_links"]["enabled"] = False
    work = ot.write_apply_dir(cfg, {})
    try:
        assert not (work / "staff.js").exists() and not (work / "staff.css").exists()
    finally:
        shutil.rmtree(work)
    # Colours on and buttons on: both in IntranetUserCSS.
    both = ot.staff_css_block(ot.normalize({"staff": {"enabled": True}, "staff_links": cfg["staff_links"] | {"enabled": True}}))
    assert "nexus-staff-page" in both and "#kei-staff-links" in both


def test_sync_settings():
    cfg = ot.normalize({"texture": "gradient", "news_buttons": False})
    got, notes, in_koha = ot.sync_settings({"data": ot.data_line(cfg), "block_OpacUserCSS": "yes",
                                            "block_OpacUserJS": "yes", "mainblock": "yes",
                                            "mainblock_buttons": "2", "own_IntranetUserJS": "40"})
    text = [n for n, _v in notes]
    assert got["texture"] == "gradient" and got["news_buttons"] is True and in_koha
    assert "Settings: read from OpacUserCSS." in text
    assert not any("missing" in n for n in text)
    assert ("${pref}: ${n} lines of the library's own, kept as they are.", {"pref": "IntranetUserJS", "n": "40"}) in notes
    # No settings line, our block still there: the copy of the last apply.
    got, notes, _in = ot.sync_settings({"state": json.dumps({"accent": "#ff0066"}), "block_OpacUserCSS": "yes"})
    assert got["accent"] == "#ff0066" and "theme-settings.json" in notes[0][0]
    assert any(v.get("prefs") == "OpacUserJS" for _n, v in notes)
    # Only our scripts left: what their config tells.
    opac = ot.js_config(ot.normalize({"default_theme": "dark", "carousel": {"enabled": False},
                                      "links": {"enabled": True, "style": "metal", "layout": "grid2",
                                                "items": [{"text": "A", "url": "/a", "sort_order": 3}]}}))
    staff = ot.staff_js_config(ot.normalize({"staff_links": {"items": [{"text": "S", "url": "/s"}]}}))
    got, notes, _in = ot.sync_settings({"config_OpacUserJS": json.dumps(opac),
                                        "config_IntranetUserJS": json.dumps(staff),
                                        "block_OpacUserJS": "yes", "block_IntranetUserJS": "yes"})
    assert got["default_theme"] == "dark" and not got["carousel"]["enabled"]
    assert got["links"]["style"] == "metal" and got["links"]["items"][0]["sort_order"] == 3
    assert got["staff_links"]["enabled"] and got["staff_links"]["items"][0]["text"] == "S"
    assert "rebuilt" in notes[0][0]
    # Nothing of ours in Koha: the defaults (Koha's own look), never the
    # panel's own copy.
    got, notes, in_koha = ot.sync_settings({"data": "/* KEI-THEME-DATA: {broken */", "state": "[]"})
    assert got == ot.normalize({}) and not in_koha and "Nothing of the panel" in notes[0][0]


def _applied_contents(cfg: dict, text: dict | None = None) -> dict:
    """live_contents as opac-theme-get hands back what an apply of cfg wrote
    (the news title goes to Koha's own field, not into the content)."""
    live = {}
    for place, markup in ot.contents(cfg, text).items():
        if not markup:
            continue
        title = ""
        if place.startswith("news-"):
            first, markup = markup.split("\n", 1)
            title = re.fullmatch(r"<!-- kei-news-title: (.*) -->", first).group(1)
        live[place] = {"title": title, "content": markup}
    return live


def test_restore_then_sync_shows_what_koha_holds():
    """Paulo, 2026-10-31: after a backup restore, Sync shows the look of the
    restored Koha (its OpacUserCSS / IntranetUserJS and its news with their
    buttons), never the panel's copy of the last apply."""
    mine = ot.normalize({"texture": "frosted", "accent": "#112233",
                         "links": {"enabled": True, "items": [{"text": "Old", "url": "/old"}]},
                         "credits": {"enabled": True, "name": "Biblioteca Antiga", "phone": "(00) 0000-0000"},
                         "news": {"opac": {"enabled": True, "title": "Antiga", "html": "<p>Velha</p>",
                                           "buttons": [{"text": "Velho", "url": "/velho"}]}}})
    saved = json.dumps(ot.contents_settings(mine))
    backup = ot.normalize({"texture": "metal", "accent": "#aa0000",
                           "staff": {"enabled": True, "accent": "#00aa00"},
                           "staff_links": {"enabled": True, "items": [{"text": "Circ", "url": "/circ"}]},
                           "news": {"opac": {"enabled": True, "title": "Julho", "html": "<p>Aberto</p>",
                                             "buttons": [{"text": "Agenda", "url": "/agenda"},
                                                         {"text": "Site", "url": "https://example.org/"}]},
                                    "staff": {"enabled": True, "title": "Equipe", "html": "<p>Reunião</p>",
                                              "buttons": []}},
                           "login": {"opac": {"enabled": True, "html": "<p>Use seu CPF</p>",
                                              "image": {"source": "url", "url": "https://example.org/b.png"},
                                              "alt": "Banner"}}})
    found = {"data": ot.data_line(backup), "state": json.dumps(ot.normalize(mine)), "contents_settings": saved,
             "live_contents": json.dumps(_applied_contents(backup)),
             "block_OpacUserCSS": "yes", "block_OpacUserJS": "yes", "block_IntranetUserCSS": "yes",
             "block_IntranetUserJS": "yes"}
    got, notes, in_koha = ot.sync_settings(found)
    # As the installer sends it: base64, so no "\\n" of the HTML is lost.
    b64 = base64.b64encode(found["live_contents"].encode()).decode()
    assert ot.sync_settings({**found, "live_contents": b64})[0] == got
    assert in_koha
    assert got["texture"] == "metal" and got["accent"] == "#aa0000"
    assert got["staff"]["enabled"] and got["staff"]["accent"] == "#00aa00"
    assert got["staff_links"]["items"][0]["text"] == "Circ"
    assert got["links"]["items"] == [] or not got["links"]["enabled"]
    # The news of the restored Koha, with their buttons; no credits there.
    assert got["news"]["opac"] == backup["news"]["opac"]
    assert got["news"]["staff"] == backup["news"]["staff"]
    assert got["login"]["opac"] == backup["login"]["opac"]
    assert not ot.credits_on(got["credits"])
    assert ot.contents(got) == ot.contents(backup)
    text = " ".join(n for n, _v in notes)
    assert "read from Koha" in text and "News buttons in Koha" in text


def test_sync_keeps_the_form_while_koha_holds_the_same_html():
    cfg = ot.normalize({"credits": {"enabled": True, "name": "Biblioteca", "address": "Rua Exemplo, 123",
                                    "phone": "(00) 0000-0000", "whatsapp": "5500000000000",
                                    "email": "contato@biblioteca.gov.br", "website": "https://biblioteca.gov.br/",
                                    "hours": "8h-18h", "instagram": "@biblioteca",
                                    "facebook": "https://facebook.com/biblioteca",
                                    "links": [{"text": "Regras", "url": "/regras"}], "note": "Aberta ao público",
                                    "cnpj": "00000000000000"}})
    found = {"live_contents": json.dumps(_applied_contents(cfg)),
             "contents_settings": json.dumps(ot.contents_settings(cfg))}
    got, notes, in_koha = ot.sync_settings(found)
    assert got["credits"] == cfg["credits"] and in_koha
    assert not any("Changed in Koha" in n for n, _v in notes)
    # Without the saved form (restored on another machine): the same fields
    # read back from the HTML.
    got, notes, _in = ot.sync_settings({"live_contents": found["live_contents"]})
    assert got["credits"] == cfg["credits"]
    assert any("Changed in Koha" in n for n, _v in notes)


def test_news_edited_in_koha_comes_back():
    """A news item of ours changed in Koha's own News tool: its title, text
    and buttons are what the fields show."""
    content = ('<div class="kei-news">\n<p>Horário <strong>novo</strong></p>\n<p class="kei-news-cta">'
               '<a class="btn btn-primary kei-news-button" style="margin:0 .4em .4em 0" href="/novo">Ver</a>\n'
               '<a class="btn btn-primary kei-news-button" href="https://example.org/x" target="_blank">Mais</a>'
               '</p>\n</div>')
    old = ot.normalize({"news": {"opac": {"enabled": True, "title": "Antigo", "html": "<p>x</p>"}}})
    got, _notes, _in = ot.sync_settings({"live_contents": json.dumps({"news-opac": {"title": "Novo",
                                                                                    "content": content}}),
                                         "contents_settings": json.dumps(ot.contents_settings(old))})
    nw = got["news"]["opac"]
    assert nw["enabled"] and nw["title"] == "Novo"
    assert nw["html"] == "<p>Horário <strong>novo</strong></p>"
    assert nw["buttons"] == [{"text": "Ver", "url": "/novo"}, {"text": "Mais", "url": "https://example.org/x"}]
    # A side with nothing of ours in Koha is off, whatever the old copy said.
    assert not got["news"]["staff"]["enabled"]
    # Script or handlers typed in Koha never reach the fields.
    bad = '<div class="kei-news"><p onclick="x()">Oi</p><script>alert(1)</script></div>'
    got, _n, _i = ot.sync_settings({"live_contents": json.dumps({"news-staff": {"title": "T", "content": bad}})})
    assert got["news"]["staff"]["html"] == "<p>Oi</p>"


def test_older_installer_without_live_contents_keeps_the_saved_forms():
    cfg = ot.normalize({"texture": "metal"})
    extra = {"credits": {"enabled": True, "name": "Biblioteca"}}
    got, notes, _in = ot.sync_settings({"data": ot.data_line(cfg), "contents_settings": json.dumps(extra)})
    assert got["credits"]["name"] == "Biblioteca"
    assert any("theme-settings.json" in n for n, _v in notes)


def test_staff_material_like_the_opac():
    # Saved before the staff had a material: flat, its old corners, no new blocks.
    old = ot.normalize({"staff": {"enabled": True, "accent": "#0f766e"}})["staff"]
    assert (old["texture"], old["radius_block"], old["opacity"]) == ("flat", 12, 100)
    flat = ot.staff_css_body(ot.normalize({"staff": {"enabled": True}}))
    assert "backdrop-filter" not in flat and "--nexus-staff-radius: 12px" in flat
    st = {"enabled": True, "texture": "frosted", "blur": 99, "opacity": 10, "radius_block": 4,
          "radius_input": 2, "radius_button": 30, "page": "#0b1220"}
    cfg = ot.normalize({"staff": st})
    assert cfg["staff"]["blur"] == ot.RANGES["blur"][1] and cfg["staff"]["opacity"] == 10
    css = ot.staff_css_body(cfg)
    for part in ("--nexus-staff-blur: 30px", "--nexus-staff-surface-a: 0.10", "--nexus-staff-radius: 4px",
                 "--nexus-staff-r-input: 2px", "--nexus-staff-r-btn: 30px", "--nexus-staff-page: #0b1220",
                 "html body .page-section::before", "backdrop-filter: blur(var(--nexus-staff-blur))",
                 "border-radius: var(--nexus-staff-r-input) 0 0 var(--nexus-staff-r-input)"):
        assert part in css, part
    # The blur is on a layer behind the content, never on a block itself
    # (it would trap Koha's position: fixed modals).
    block_rule = css.split("html body .page-section, html body #area-news, html body fieldset.rows {", 1)[1].split("}", 1)[0]
    assert "backdrop-filter" not in block_rule and "isolation: isolate" in block_rule
    metal = ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "texture": "metal"}}))
    assert "#f8f9fa 0%, #e3e6ea 47%" in metal and "nav.navbar.bg-dark" in metal
    for tex in ot.TEXTURES:     # every texture is accepted and builds
        assert ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "texture": tex}}))
    assert ot.parse_theme_data(ot.css_block(cfg))["staff"]["texture"] == "frosted"


def test_staff_translucent_header():
    # Off by default: the bars stay solid, nothing of the glass bar is written.
    off = ot.normalize({"staff": {"enabled": True}})["staff"]
    assert (off["header_glass"], off["header_opacity"], off["header_blur"]) == (False, 85, 8)
    assert "--nexus-staff-header-a" not in ot.staff_css_body(ot.normalize({"staff": {"enabled": True}}))
    cfg = ot.normalize({"staff": {"enabled": True, "accent": "#408540", "texture": "metal",
                                  "header_glass": True, "header_opacity": 140, "header_blur": -3}})
    assert (cfg["staff"]["header_opacity"], cfg["staff"]["header_blur"]) == (100, 0)
    cfg["staff"].update(header_opacity=60, header_blur=8)
    css = ot.staff_css_body(cfg)
    for part in ("--nexus-staff-header-a: 0.60", "--nexus-staff-header-blur: 8px",
                 "rgba(64,133,64, var(--nexus-staff-header-a))",
                 "html body #header_search::before", "backdrop-filter: blur(var(--nexus-staff-header-blur))",
                 "-webkit-backdrop-filter: blur(var(--nexus-staff-header-blur))",
                 "prefers-reduced-transparency", "@supports not"):
        assert part in css, part
    # Translucent backgrounds, never opacity: the children keep full contrast,
    # and the blur is on a layer behind the bar, not on the bar.
    glass = css.split("--nexus-staff-header-a: 0.60", 1)[1]
    assert "opacity: ." not in glass and "opacity: 0" not in glass
    nav_rule = glass.split("html body nav.navbar.bg-dark, html body nav.navbar.navbar-dark {", 1)[1].split("}", 1)[0]
    assert "backdrop-filter" not in nav_rule and "!important" in nav_rule
    # After the texture: the glass bar wins over the brushed metal one.
    assert css.rindex("rgba(64,133,64, var(--nexus-staff-header-a))") > css.rindex("feTurbulence")
    assert ot.parse_theme_data(ot.css_block(cfg))["staff"]["header_glass"] is True


def test_copy_opac_preset():
    raw = {"texture": "smooth", "blur": 7, "opacity": 64, "radius_block": 20, "radius_input": 5, "radius_button": 9,
           "accent": "#aa0000", "accent2": "#00aa00", "surface": "#fafafa", "page": "#e0e0e0", "film": 10,
           "background": {"source": "local", "url": "/images/custom/kei-background.png?v=1"},
           "logo": {"source": "imgbb", "url": "https://i.ibb.co/x/logo.png"},
           "staff": {"font": 115, "density": "compact", "favicon": {"source": "url", "url": "https://e.org/s.ico"}}}
    cfg, skipped = ot.copy_opac_to_staff(raw)
    st = cfg["staff"]
    assert st["enabled"] and (st["texture"], st["blur"], st["opacity"]) == ("smooth", 7, 64)
    assert (st["radius_block"], st["radius_input"], st["radius_button"]) == (20, 5, 9)
    assert (st["accent"], st["accent2"], st["surface"], st["page"]) == ("#aa0000", "#00aa00", "#fafafa", "#e0e0e0")
    assert st["film"] == 10                                        # the OPAC's film, no floor: the cards keep tables readable
    assert st["logo"] == {"source": "url", "url": "https://i.ibb.co/x/logo.png"}
    assert skipped == ["background"] and st["background"]["source"] == "none"   # an OPAC file: not served on staff
    assert st["favicon"]["url"] == "https://e.org/s.ico"          # nothing to copy: the staff's own kept
    assert (st["font"], st["density"]) == (115, "compact")
    assert cfg["texture"] == "smooth" and cfg["accent"] == "#aa0000"   # the OPAC untouched


# ----------------------------------------------------------------------
# OPAC and Staff Appearance: readable panels, login instructions, credits
# ----------------------------------------------------------------------
def test_panels_reach_wcag_aa_in_light_and_dark():
    for accent in ("#2563eb", "#facc15", "#ffffff", "#000000", "#7c3aed", "#10b981"):
        for surface in ("#ffffff", "#333844", "#0b0b0b", "#fde68a"):
            cfg = ot.normalize({"accent": accent, "surface": surface})
            for dark, opacity in ((False, 76), (True, 76), (False, 78), (True, 78), (False, 100), (True, 100)):
                c = ot.panel_colors({**cfg, "opacity": opacity}, dark)
                assert len(c["grounds"]) == 2
                for bg in c["grounds"]:
                    assert ot.contrast(c["text"], bg) >= 7, (accent, surface, dark)
                    for key in ("muted", "link", "ink"):
                        assert ot.contrast(c[key], bg) >= 4.5, (accent, surface, dark, key)
            # More see-through: the text still reaches AA (4.5:1) on any wallpaper down to 60%.
            for dark in (False, True):
                c = ot.panel_colors({**cfg, "opacity": 60}, dark)
                assert min(ot.contrast(c["text"], bg) for bg in c["grounds"]) >= 4.5, (accent, surface, dark)
            # Fully clear is allowed: the colours fall back to black or white, no error.
            assert ot.panel_colors({**cfg, "opacity": 0}, True)["text"] == "#ffffff"
    # Light mode reads dark on light even when the block background is dark (the screenshots' case).
    light = ot.panel_colors(ot.normalize({"surface": "#333844"}), False)
    assert ot.luminance(light["card"]) > .8 and light["text"] == "#1a1a1a"
    dark = ot.panel_colors(ot.normalize({}), True)
    assert dark["card"] == "#161b22" and dark["text"].startswith("#e")


def test_one_glass_card_for_every_surface():
    # The opacity slider is free from 0 to 100; the old second slider is gone.
    assert ot.normalize({"opacity": 0})["opacity"] == 0 and ot.normalize({"opacity": 100})["opacity"] == 100
    assert ot.normalize({"opacity": -5})["opacity"] == 0 and "panel_opacity" not in ot.normalize({"panel_opacity": 90})
    css = ot.css_body(ot.normalize({"opacity": 35, "blur": 11, "surface": "#333844"}))
    for token in ("--koha-card-alpha: 0.35;", "--koha-card-bg: rgba(var(--koha-card-rgb), var(--koha-card-alpha));",
                  "--koha-glass-blur: 11px;", "--koha-card-border: rgba(255, 255, 255, .2);",
                  "--koha-card-border: rgba(255, 255, 255, .08);", "--kei-surface-a: var(--koha-card-alpha);",
                  "--koha-pane-border: rgba(15, 23, 42, .12);"):
        assert token in css, token
    # Header, search bar and content: one rule, the same background, border, radius.
    head = css[css.index("/* One glass card"):]
    first = head[:head.index("}")]
    for sel in ("html body #header-region .navbar", "html body #opac-main-search", "html body .main {"):
        assert sel in first, sel
    assert "background: var(--koha-card-sheen), var(--koha-card-bg) !important;" in first
    assert "-webkit-backdrop-filter: blur(var(--koha-glass-blur));" in css and "backdrop-filter: blur(var(--koha-glass-blur));" in css
    assert "html body .main::before {" in css
    # Koha's boxes outside .main are the same card, never a card in a card.
    assert "html body #ulactioncontainer:not(.main *):not(.modal *)" in css and ":not(:is(#catalogue_detail_biblio" in css
    # Inside .main they show the card's glass: no fills of their own, no white or grey anywhere.
    for sel in ("html body .main .breadcrumb", "html body .main #breadcrumbs", "html body .main #ulactioncontainer",
                "html body .main .searchresults-sidebar", "html body .main .nav-pills", "html body .main #usermenu",
                "html body .main #facets", "html body .main .tab-content", "html body .main #notes",
                "html body .main #catalogue_detail_biblio", "html body .main .nav_results ul",
                "html body .main .pg_menu", "html body .main .l_Results", "html body .main #didyoumean"):
        assert sel in css, sel
    assert "background: transparent !important;" in css
    glass = (css[css.index("/* One glass card"):css.index("/* The header and its menus")]
             + css[css.index("/* Inside the card"):css.index(".term {")])
    assert not re.search(r"background(-color)?:\s*(#[0-9a-f]{3,6}|white|rgb\()", glass, re.I)
    # The footer credits: no box behind them, only a halo around the letters.
    assert "#opaccredits::before" not in css and "html body .main, html body #opaccredits" not in css
    assert 'html[data-kei-theme="dark"] body #opaccredits {' in css
    # Flat: no blur; metal: its sheen on every card.
    assert "--koha-glass-blur: 0px;" in ot.css_body(ot.normalize({"texture": "flat"}))
    assert "--koha-card-sheen: url(\"data:image/svg+xml," in ot.css_body(ot.normalize({"texture": "metal"}))
    assert ot.check_block(ot.css_block(ot.normalize({})), ot.CSS_BEGIN, ot.CSS_END) == ""


def test_staff_panels_and_dark_surface():
    light = ot.staff_css_body(ot.normalize({"staff": {"enabled": True}}))
    assert "html body #breadcrumbs .breadcrumb {" in light and "html body #login #StaffLoginInstructions" in light
    assert "A dark block background" not in light
    dark = ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "surface": "#1e222a"}}))
    assert "html body table.dataTable tbody tr" in dark and "--nexus-staff-text: #e6edf3" in dark


def test_sanitize_html_keeps_an_allow_list():
    dirty = ('<p onclick="x()">Hi <b>there</b><script>alert(1)</script><a href="javascript:alert(1)">x</a>'
             '<img src="https://a.b/c.png" onerror="y" width="300"><iframe src=x>t</iframe><style>p{}</style>'
             '<form><input name=a></form><p style="background:url(x)">s</p><ul><li>a<li>b</ul>'
             '<a href="https://koha.nexus" target="_blank">k</a><SCRIPT SRC=//x></SCRIPT><!-- c -->&lt;b&gt;')
    out = ot.sanitize_html(dirty)
    for bad in ("script", "onclick", "onerror", "javascript", "iframe", "<style", "<form", "<input",
                "background:url", "<!--"):
        assert bad not in out.lower(), bad
    assert '<img src="https://a.b/c.png" width="300" loading="lazy" style="max-width:100%;height:auto">' in out
    assert '<a href="https://koha.nexus" target="_blank" rel="noopener noreferrer">k</a>' in out
    assert "<ul><li>a</li><li>b</li></ul>" in out and "&lt;b&gt;" in out
    assert ot.sanitize_html(out) == out
    assert ot.sanitize_html("<b>open") == "<b>open</b>" and ot.sanitize_html("  ") == ""


def test_login_instructions_markup():
    cfg = ot.normalize({"login": {"opac": {"enabled": True, "html": "<h2>Welcome</h2><script>x</script>",
                                           "image": {"source": "url", "url": "https://i.ibb.co/a/b.png"},
                                           "alt": 'Front "door"'},
                                  "staff": {"enabled": True, "html": ""}}})
    html = ot.login_html(cfg["login"]["opac"])
    assert html.startswith('<div class="kei-login">') and "<h2>Welcome</h2>" in html and "script" not in html
    assert 'src="https://i.ibb.co/a/b.png" alt="Front &quot;door&quot;"' in html and "max-width:100%" in html
    assert not ot.login_on(cfg["login"]["staff"])
    c = ot.contents(cfg)
    assert c["OpacLoginInstructions"] == html and c["StaffLoginInstructions"] == "" and c["opaccredits"] == ""
    assert ot.normalize({"login": {"opac": {"image": {"source": "url", "url": "javascript:x"}}}})[
        "login"]["opac"]["image"]["url"] == ""


def test_credits_form_to_markup():
    raw = {"enabled": True, "name": "Biblioteca <Municipal>", "address": "Rua Exemplo, 123",
           "phone": "(00) 0000-0000", "whatsapp": "+55 00 00000-0000", "email": "contato@biblioteca.gov.br",
           "website": "https://biblioteca.gov.br/", "instagram": "@biblioteca", "facebook": "javascript:x",
           "cnpj": "00000000000000", "links": [{"text": "Portal", "url": "https://biblioteca.gov.br/portal"},
                                               {"text": "bad", "url": "javascript:alert(1)"}]}
    cr = ot.normalize({"credits": raw})["credits"]
    assert cr["cnpj"] == "00.000.000/0000-00" and cr["facebook"] == "" and len(cr["links"]) == 1
    html = ot.credits_html(cr, {"phone": "Telefone"})
    assert "<strong>Biblioteca Municipal</strong>" in html                # <> taken out
    assert 'Telefone: <a href="tel:0000000000">(00) 0000-0000</a>' in html
    assert 'href="https://wa.me/5500000000000"' in html and 'href="mailto:contato@biblioteca.gov.br"' in html
    assert 'href="https://www.instagram.com/biblioteca/"' in html and "CNPJ: 00.000.000/0000-00" in html
    assert "javascript" not in html and ot.credits_on(cr)
    assert not ot.credits_on(ot.normalize({"credits": {"enabled": True}})["credits"])


def test_contents_stay_out_of_the_public_stylesheet(tmp_path):
    cfg = ot.normalize({"login": {"staff": {"enabled": True, "html": "<p>Internal extension 123</p>"}},
                        "credits": {"enabled": True, "name": "Biblioteca"}})
    line = ot.data_line(cfg)
    assert "Internal extension" not in line and "credits" not in line
    back = ot.parse_theme_data(ot.css_block(cfg))
    assert back["credits"]["name"] == "" and not back["login"]["staff"]["enabled"]
    extra = ot.parse_contents(json.dumps(ot.contents_settings(cfg)))
    assert extra["credits"]["name"] == "Biblioteca" and ot.parse_contents("nope") == {}
    work = ot.write_apply_dir(cfg, {})
    try:
        assert (work / "contents.list").read_text() == ("OpacLoginInstructions\toff\nStaffLoginInstructions\ton\n"
                                                        "opaccredits\ton\nnews-opac\toff\nnews-staff\toff\n")
        assert "Internal extension 123" in (work / "contents" / "StaffLoginInstructions.html").read_text()
        assert not (work / "contents" / "OpacLoginInstructions.html").exists()
        assert json.loads((work / "contents.json").read_text())["credits"]["name"] == "Biblioteca"
    finally:
        shutil.rmtree(work)
    # sync: the contents settings join the settings read from Koha.
    found = {"data": ot.data_line(ot.normalize({})), "contents_settings": json.dumps(ot.contents_settings(cfg))}
    synced, notes, _in = ot.sync_settings(found)
    assert synced["credits"]["name"] == "Biblioteca" and any("theme-settings.json" in n for n, _ in notes)


def test_news_single_button_of_1_5_53_is_kept():
    cfg = ot.normalize({"news": {"opac": {"enabled": True, "title": "T", "button_text": "Ir",
                                          "button_url": "https://example.org"}}})
    assert cfg["news"]["opac"]["buttons"] == [{"text": "Ir", "url": "https://example.org"}]
    # No limit on the number of buttons (Paulo, 2026-10-31).
    many = [{"text": f"B{i}", "url": "https://example.org"} for i in range(15)]
    assert len(ot.normalize({"news": {"opac": {"buttons": many}}})["news"]["opac"]["buttons"]) == 15


def test_news_items_for_each_side():
    cfg = ot.normalize({"news": {
        "opac": {"enabled": True, "title": "Férias <b>--</b>", "html": "<p>Fechado</p><script>x()</script>",
                 "buttons": [{"text": "Ver horários", "url": "https://biblioteca.gov.br/horarios"},
                             {"text": "Contato", "url": "mailto:bib@example.org"},
                             {"text": "Sem endereço", "url": "javascript:x()"}]},
        "staff": {"enabled": True, "title": "", "html": "<p>no title</p>"}}})
    opac, staff = cfg["news"]["opac"], cfg["news"]["staff"]
    assert opac["title"] == "Férias b-/b" and "<script>" not in opac["html"]
    assert ot.news_on(opac) and not ot.news_on(staff)           # a news item needs a title
    out = ot.contents(cfg)
    assert out["news-staff"] == ""
    first, *rest = out["news-opac"].splitlines()
    assert first == "<!-- kei-news-title: Férias b-/b -->"
    assert 'href="https://biblioteca.gov.br/horarios" target="_blank"' in out["news-opac"]
    assert "Ver horários</a>" in out["news-opac"] and "<p>Fechado</p>" in out["news-opac"]
    assert [b["text"] for b in opac["buttons"]] == ["Ver horários", "Contato"]     # unsafe address dropped
    assert out["news-opac"].count("kei-news-button") == 2 and 'href="mailto:bib@example.org">' in out["news-opac"]
    assert "Fechado" not in ot.data_line(cfg) and '"news":' not in ot.data_line(cfg)   # not public
    assert ot.parse_contents(json.dumps(ot.contents_settings(cfg)))["news"] == cfg["news"]
    work = ot.write_apply_dir(cfg, {})
    try:
        listing = (work / "contents.list").read_text()
        assert "news-opac\ton\n" in listing and "news-staff\toff\n" in listing
        assert (work / "contents" / "news-opac.html").read_text().startswith("<!-- kei-news-title:")
    finally:
        __import__("shutil").rmtree(work)


def test_material_textures():
    """Metal, anodised aluminium, wood and paper: drawn in the CSS (SVG
    noise, no picture file), the same on the OPAC and the staff blocks, the
    two metals with brushed buttons, the old settings untouched."""
    assert ot.normalize({})["texture"] == "frosted" and ot.normalize({})["staff"]["texture"] == "flat"
    for tex in ot.MATERIALS:
        css = ot.css_body(ot.normalize({"texture": tex}))
        block = ot.css_block(ot.normalize({"texture": tex}))
        assert ot.check_block(block, ot.CSS_BEGIN, ot.CSS_END) == ""
        assert "data:image/svg+xml,%3Csvg" in css and "<svg" not in css and "url(%23n)" in css
        # The streaks sit above .main's blur layer, so the blur never smears them.
        assert "html body .main::after" in css and "background: var(--koha-card-sheen);" in css
        assert ot.parse_theme_data(block)["texture"] == tex
        staff = ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "texture": tex}}))
        assert "data:image/svg+xml" in staff and "<svg" not in staff
        assert ("nav.navbar.navbar-dark {\n    background: url(" in staff) == (tex in ot.METALS)
        assert ("#cdd2d8" in css) == (tex in ot.METALS)
    # The anodised metal takes the accent colour, on each side its own.
    assert "rgba(var(--nexus-staff-primary-rgb), .26)" in ot.staff_css_body(
        ot.normalize({"staff": {"enabled": True, "texture": "anodized"}}))
    for tex in ("frosted", "smooth", "flat", "gradient"):
        css = ot.css_body(ot.normalize({"texture": tex}))
        assert "html body .main::after" not in css and "data:image/svg+xml" not in css


def test_style_details():
    """Card shadow, spacing, icons, pattern, tables and menus, login page and
    hover animations: on each side its own, the defaults add nothing, and
    unknown values fall back to them."""
    cfg = ot.normalize({})
    assert all(cfg[k] == cfg["staff"][k] == ot.STYLE_DEFAULTS[k] for k in ot.STYLE)
    assert ot.style_css(cfg, "opac") == "" and ot.style_css(ot.normalize({"staff": {"enabled": True}}), "staff") == ""
    # login_style never touches the login banners (cfg["login"]).
    bad = ot.normalize({"shadow": "huge", "login_style": {"x": 1}, "staff": {"motion": "fast"}})
    assert bad["shadow"] == "texture" and bad["login_style"] == "koha" and bad["staff"]["motion"] == "subtle"
    assert set(bad["login"]) == set(ot.LOGIN_SIDES)
    picks = {"shadow": "strong", "spacing": "compact", "icons": "outline", "pattern": "dots", "chrome": "texture",
             "login_style": "accent", "motion": "lively"}
    cfg = ot.normalize({**picks, "texture": "metal", "staff": {"enabled": True, "texture": "wood", "pattern": "grain",
                                                                "login_style": "card", "motion": "off"}})
    opac, staff = ot.css_body(cfg), ot.staff_css_body(cfg)
    assert ot.check_block(ot.css_block(cfg), ot.CSS_BEGIN, ot.CSS_END) == ""
    assert {k: ot.parse_theme_data(ot.css_block(cfg))[k] for k in picks} == picks
    # Shadow: the metal keeps its bevel under the chosen drop shadow.
    assert ":root { --koha-card-shadow: inset 0 1px 0 rgba(255, 255, 255, .85)" in opac
    assert "-webkit-text-stroke: .9px currentColor" in opac and "-webkit-text-stroke" not in staff
    assert "radial-gradient(circle, rgba(var(--kei-accent-rgb), .13)" in opac
    assert "html body .dropdown-menu {" in opac and "html body .main #menu" in opac
    assert "html body#opac-login-page #opac-auth {" in opac and "linear-gradient(135deg, rgb(var(--kei-accent-rgb))" in opac
    assert "prefers-reduced-motion: no-preference" in opac and "translateY(-4px)" in opac
    assert "html body .main { padding: .7rem;" in opac
    # Staff: its own choices, its own variables and markup.
    assert "html body#main_auth #login {" in staff and "max-width: 26rem" in staff and "135deg, rgb(" not in staff
    assert "transition: none !important" in staff and "translateY(-4px)" not in staff
    assert "data:image/svg+xml" in staff and "html body::before" in staff
    # A wallpaper: no pattern over it.
    wall = ot.normalize({"pattern": "grid", "background": {"source": "url", "url": "https://example.org/w.jpg"}})
    assert "28px 28px" not in ot.css_body(wall)
    # Copy OPAC preset brings the style details along.
    copied, _ = ot.copy_opac_to_staff(cfg)
    assert {k: copied["staff"][k] for k in picks} == picks


def test_paulo_1031_header_cart_motion_shadow_staff_dark():
    """Paulo, 2026-10-31: top bar on/off and a large header under a picture,
    the whole cart hidden, only the buttons move on hover (not the news
    block), short carousel shadows, and a light/dark switch on the staff side."""
    plain = ot.css_body(ot.normalize({}))
    assert "#header-region > nav.navbar { display: none" not in plain and "Large header" not in plain
    cfg = ot.normalize({"header_bar": False, "header_style": "large", "header_height": 9999,
                        "header": {"source": "url", "url": "https://example.org/h.jpg"},
                        "ghost": {"cart": True}, "motion": "lively"})
    assert cfg["header_height"] == 520
    css = ot.css_body(cfg)
    assert "#header-region > nav.navbar { display: none !important; }" in css
    assert 'url("https://example.org/h.jpg") center / cover no-repeat' in css and "min-height: 520px" in css
    assert "#cartmenulink" in css and ".addtocart" in css
    # Without a picture the large header takes the two colours.
    assert "linear-gradient(135deg, var(--kei-accent), var(--kei-accent2))" in ot.css_body(
        ot.normalize({"header_style": "large"}))
    lively = ot.style_css(cfg, "opac")
    assert ".newsitem:hover" not in lively and "#opacmainuserblock:hover" not in lively
    assert "a.btn-acesso:hover" in lively and ".btn:hover" in lively
    car = ot.css_block(ot.normalize({"carousel": {"mode": "coverflow"}}))
    assert "0 24px 40px" not in car and "0 18px 30px" not in car and "0 18px 36px" not in car
    # The staff switch: CSS and script only with the staff colours on.
    off = ot.normalize({"staff": {"dark_switch": True}})
    assert not ot.staff_dark(off) and not ot.staff_js_on(off)
    on = ot.normalize({"staff": {"enabled": True, "dark_switch": True}})
    assert ot.staff_dark(on) and ot.staff_js_on(on)
    assert 'html[data-kei-theme="dark"]' in ot.staff_css_block(on)
    js = ot.staff_js_block(on)
    assert "kei-theme-switch" in js and '"dark_switch": true' in js and "kei_staff_theme" in js
    work = ot.write_apply_dir(on, {})
    try:
        assert (work / "staff.js").exists()
    finally:
        shutil.rmtree(work)


def test_library_news_item_comes_back_with_its_buttons():
    content = ('<style>.btn-acesso{display:block}</style>\n'
               '<p>Olá</p><a href="/cgi-bin/koha/opac-page.pl?page_id=5" class="btn-acesso">📖 Sobre</a> '
               '<a href="https://example.org/x" class="btn-acesso" target="_blank">Site</a> '
               '<a href="/plain">plain link</a>')
    live = {"news-opac": {"id": 9, "own": True, "title": "Bem-vindo", "content": content}}
    got, notes, in_koha = ot.sync_settings({"live_contents": json.dumps(live)})
    nw = got["news"]["opac"]
    assert in_koha and nw["koha_id"] == 9 and nw["title"] == "Bem-vindo"
    assert [b["text"] for b in nw["buttons"]] == ["📖 Sobre", "Site"]
    assert "Olá" in nw["html"] and "plain link" in nw["html"] and "btn-acesso" not in nw["html"]
    assert any("news item ${id}" in n for n, _v in notes)
    # Apply writes the id so the installer updates item 9 in place.
    markup = ot.contents(got)["news-opac"]
    assert markup.splitlines()[:2] == ["<!-- kei-news-title: Bem-vindo -->", "<!-- kei-news-id: 9 -->"]


def test_paulo_1031_colour_paints_and_phone_layout():
    """Paulo, 2026-10-31 (17:01): each colour with its own texture and
    opacity; on a phone the holdings readable, the logo at a real size, the
    cover above the text of a result; the results toolbar that sticks to the
    top no longer lets the results show through it."""
    plain = ot.css_body(ot.normalize({}))
    assert "Each colour in its own texture" not in plain and "--kei-page-rgb" not in plain
    assert ot.normalize({"paint": {"accent": {"texture": "lava", "opacity": 500}}})["paint"]["accent"] == {
        "texture": "auto", "opacity": 100}
    cfg = ot.normalize({"accent": "#112233", "page": "#ffeedd",
                        "paint": {"accent": {"texture": "wood", "opacity": 60},
                                  "accent2": {"texture": "frosted", "opacity": 50},
                                  "page": {"texture": "paper", "opacity": 80}}})
    css = ot.css_body(cfg)
    painted = css[css.index("Each colour in its own texture"):]
    main = painted[painted.index("html body .btn-primary"):]
    main = main[:main.index("}")]
    assert "rgba(var(--kei-accent-rgb), 0.60)" in main and ".0015 .5" in main      # wood grain
    soft = painted[painted.index("html body .btn-default"):]
    soft = soft[:soft.index("}")]
    assert "rgba(var(--kei-accent2-rgb), 0.50)" in soft and "backdrop-filter" in soft
    assert "var(--nexus-on-secondary)" in soft and "--nexus-on-secondary: " in css
    assert "--kei-page-rgb: 255,238,221;" in css
    assert "rgba(var(--kei-page-rgb), 0.80)" in css
    # Only the opacity of the accent: the buttons keep their look, in rgba.
    only = ot.css_body(ot.normalize({"paint": {"accent": {"opacity": 50}}}))
    assert "rgba(var(--kei-accent-rgb), 0.50)" in only
    # The second colour on "As the Material": its opacity scales its glow.
    glow = ot.css_body(ot.normalize({"paint": {"accent2": {"opacity": 50}}}))
    assert "rgba(var(--kei-accent2-rgb), 0.07)" in glow and "Each colour" not in glow
    # Round trip through the stylesheet's settings line.
    assert ot.parse_theme_data(ot.data_line(cfg))["paint"] == cfg["paint"]

    # The sticky toolbar: a near solid card above the results.
    sticky = plain[plain.index("html body #floating"):]
    sticky = sticky[:sticky.index("}")]
    assert "rgba(var(--koha-card-rgb), .96)" in sticky and "z-index: 1020 !important" in sticky
    # Phone: cover above the text, Koha's hidden number column kept hidden.
    assert "html body .searchresults td.covercol { flex: 1 1 100%" in plain
    assert "td:not(.hidden):not(.d-none)" in plain
    # Phone: holdings stacked with their headings, every column shown.
    assert "table.kei-stack > tbody > tr > td[data-kei-label]::before" in plain
    assert "content: attr(data-kei-label)" in plain
    js = ot._JS
    assert "#holdingst, #otherholdingst" in js and "data-kei-label" in js and "draw.dt" in js
    # Phone: the library's logo instead of Koha's 14 px house icon.
    assert "width: 132px !important" not in plain
    logo = ot.css_body(ot.normalize({"logo": {"source": "url", "url": "https://i.postimg.cc/a/logo.png"}}))
    assert "max-width: 700px" in logo and "width: 132px !important" in logo


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def test_paulo_1031_koha_stylesheet_is_the_base():
    """Paulo, 2026-10-31 (18:04): what is written in the instance is always
    the base. The values of the panel's stylesheets in Koha (edited there by
    hand) win over the settings line; a block without its settings line is
    read from its CSS; one unreadable part never costs the rest."""
    cfg = ot.normalize({"accent": "#2563eb", "texture": "metal",
                        "logo": {"source": "url", "url": "https://i.postimg.cc/a/logo.png"},
                        "staff": {"enabled": True, "accent": "#112233"}})
    css = ot.css_block(cfg) if hasattr(ot, "css_block") else ot.data_line(cfg) + "\n" + ot.css_body(cfg)
    edited = css.replace("--nexus-primary: #2563eb;", "--nexus-primary: #aa0000;").replace(
        "https://i.postimg.cc/a/logo.png", "/images/custom/kei-logo.png?v=1")
    staff = ot.staff_css_body(cfg).replace("--nexus-staff-radius: 12px;", "--nexus-staff-radius: 20px;")
    found = {"data": ot.data_line(cfg), "block_OpacUserCSS": "yes", "block_IntranetUserCSS": "yes",
             "css_OpacUserCSS": _b64(edited), "css_IntranetUserCSS": _b64(staff)}
    got, notes, in_koha = ot.sync_settings(found)
    assert in_koha and got["accent"] == "#aa0000" and got["texture"] == "metal"
    assert got["logo"] == {"source": "local", "url": "/images/custom/kei-logo.png?v=1"}
    assert got["staff"]["radius_block"] == 20 and got["staff"]["accent"] == "#112233"
    assert any("Edited in Koha's stylesheets" in n for n, _ in notes)
    # Untouched: the same settings, no note.
    same, notes, _ = ot.sync_settings({**found, "css_OpacUserCSS": _b64(css),
                                       "css_IntranetUserCSS": _b64(ot.staff_css_body(cfg))})
    assert same["accent"] == "#2563eb" and not any("Edited in Koha" in n for n, _ in notes)
    # The settings line gone (edited by hand): rebuilt from the CSS.
    no_line, notes, in_koha = ot.sync_settings({"block_OpacUserCSS": "yes", "css_OpacUserCSS": _b64(edited)})
    assert in_koha and no_line["accent"] == "#aa0000" and no_line["opacity"] == cfg["opacity"]
    assert any("rebuilt from the panel's stylesheet" in n for n, _ in notes)


def test_unreadable_news_never_costs_the_look(monkeypatch):
    cfg = ot.normalize({"accent": "#123456"})

    def boom(*_a, **_k):
        raise ValueError("bad news")
    monkeypatch.setattr(ot, "live_contents", boom)
    got, notes, in_koha = ot.sync_settings({"data": ot.data_line(cfg), "block_OpacUserCSS": "yes"})
    assert in_koha and got["accent"] == "#123456"
    assert any("could not be read" in n and v.get("error") == "bad news" for n, v in notes)


def test_paulo_1031_credits_without_the_300_limit():
    long = "Horário estendido nas férias " * 40
    assert len(long) > 1000
    assert ot.normalize({"credits": {"enabled": True, "note": long}})["credits"]["note"] == long.strip()
    assert ot.credits_from_html(f"<p>{long}</p>")["note"] == long.strip()


def test_paulo_1031_staff_colour_paints():
    """The staff's four colours with their own texture and opacity, as on the OPAC."""
    plain = ot.staff_css_body(ot.normalize({"staff": {"enabled": True}}))
    assert "Each staff colour" not in plain
    cfg = ot.normalize({"staff": {"enabled": True, "page": "#eeeeee",
                                  "paint": {"accent": {"texture": "wood", "opacity": 70},
                                            "accent2": {"texture": "metal", "opacity": 90},
                                            "page": {"texture": "paper", "opacity": 60}}}})
    css = ot.staff_css_body(cfg)
    painted = css[css.index("Each staff colour"):]
    assert "rgba(var(--nexus-staff-primary-rgb), 0.70)" in painted and ".0015 .5" in painted
    assert "rgba(var(--nexus-staff-secondary-rgb), 0.90)" in painted
    assert "--nexus-staff-page-rgb: 238,238,238;" in painted and "rgba(var(--nexus-staff-page-rgb), 0.60)" in painted
    assert ot.parse_theme_data(ot.data_line(cfg))["staff"]["paint"] == cfg["staff"]["paint"]
    # Copy OPAC preset brings the OPAC's paints.
    copied, _ = ot.copy_opac_to_staff({"paint": {"accent": {"texture": "paper", "opacity": 40}}})
    assert copied["staff"]["paint"]["accent"] == {"texture": "paper", "opacity": 40}
