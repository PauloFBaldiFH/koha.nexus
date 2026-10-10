"""opac_theme: the settings, the CSS/JS blocks Koha receives, the pictures."""

import json
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
    assert cfg["texture"] == "frosted" and cfg["blur"] == 30 and cfg["opacity"] == 30
    assert cfg["radius_block"] == 0 and cfg["radius_input"] == ot.DEFAULTS["radius_input"]
    assert cfg["accent"] == "#aabbcc" and cfg["accent2"] == ot.DEFAULTS["accent2"]
    assert cfg["film"] == 90 and cfg["default_theme"] == "light"
    assert cfg["background"] == {"source": "url", "url": ""}
    assert cfg["logo"]["url"] == "https://i.postimg.cc/x/logo.png"
    assert cfg["favicon"] == {"source": "none", "url": ""}
    car = cfg["carousel"]
    assert (car["speed"], car["count"], car["hover"]) == (2000, 24, "lift")
    assert car["title"] == "bNew/b" and car["amazon_tag"] == ""
    assert cfg["ghost"] == {"rss": False, "cart_badge": True, "community": True, "empty_columns": True}
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
    ("frosted", "backdrop-filter: blur(var(--kei-blur))"),
    ("metal", "repeating-linear-gradient"),
    ("gradient", "linear-gradient(135deg"),
    ("flat", "background: rgba(var(--kei-surface-rgb)"),
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
    for var in ("--kei-r-block: 22px", "--kei-r-input: 4px", "--kei-r-btn: 30px", "--kei-accent: #112233"):
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
    assert "#c9c9c9" in ot.css_body(ot.normalize({"texture": "metal"})) and "#c9c9c9" not in plain
    # The settings line is untouched by the new rules.
    assert ot.parse_theme_data(ot.css_block(ot.normalize({"texture": "metal"})))["texture"] == "metal"


def test_blocks_take_the_chosen_colours():
    css = ot.css_body(ot.normalize({"accent": "#7c3aed", "accent2": "#db2777", "surface": "#ffffff"}))
    tint = ot.mix("#ffffff", "#7c3aed", .12)
    assert tint != "#ffffff" and f"--kei-surface-rgb: {ot._rgb(tint)};" in css
    assert "--kei-surface-rgb: 255,255,255;" not in css
    # The news and home page blocks: the accent wash over the readable inner panel.
    assert "rgba(var(--kei-accent-rgb), .14) 0%, rgba(var(--kei-accent2-rgb), .10) 100%),\n        var(--kei-panel-2)" in css
    assert f"--kei-ink: {ot.mix('#7c3aed', '#000000', .30)}" in css
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


def test_staff_pictures_and_single_icon(tmp_path):
    cfg = ot.normalize({"favicon": {"source": "url", "url": "https://example.org/opac.ico"},
                        "staff": {"enabled": True, "film": 5,
                                  "logo": {"source": "local", "url": "/intranet-tmpl/kei-custom/kei-staff-logo.png?v=1"},
                                  "favicon": {"source": "url", "url": "https://example.org/staff.ico"},
                                  "background": {"source": "url", "url": "javascript:alert(1)"}}})
    st = cfg["staff"]
    assert st["film"] == ot.STAFF_FILM[0] and st["background"]["url"] == ""
    staff = ot.staff_css_body(cfg)
    assert 'url("/intranet-tmpl/kei-custom/kei-staff-logo.png?v=1")' in staff and "#logo.navbar-brand img { display: none; }" in staff
    assert ".fa-stack .fa-stack-1x {{ display: none; }}".replace("{{", "{").replace("}}", "}") in staff
    assert "html body::before" not in staff                     # no wallpaper, no film
    with_bg = ot.staff_css_body(ot.normalize({"staff": {"background": {"source": "url",
                                                                       "url": "https://i.ibb.co/x/s.jpg"}}}))
    assert 'url("https://i.ibb.co/x/s.jpg")' in with_bg and "html body::before" in with_bg
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
    got, notes = ot.sync_settings({"data": ot.data_line(cfg), "block_OpacUserCSS": "yes", "block_OpacUserJS": "yes",
                                   "mainblock": "yes", "mainblock_buttons": "2", "own_IntranetUserJS": "40"})
    text = [n for n, _v in notes]
    assert got["texture"] == "gradient" and got["news_buttons"] is True
    assert "Settings: read from OpacUserCSS." in text
    assert not any("missing" in n for n in text)
    assert ("${pref}: ${n} lines of the library's own, kept as they are.", {"pref": "IntranetUserJS", "n": "40"}) in notes
    # No settings line: the copy of the last apply.
    got, notes = ot.sync_settings({"state": json.dumps({"accent": "#ff0066"}), "block_OpacUserCSS": "no"})
    assert got["accent"] == "#ff0066" and "theme-settings.json" in notes[0][0]
    assert any(v.get("prefs") == "OpacUserCSS, OpacUserJS" for _n, v in notes)
    # Only our scripts left: what their config tells.
    opac = ot.js_config(ot.normalize({"default_theme": "dark", "carousel": {"enabled": False},
                                      "links": {"enabled": True, "style": "metal", "layout": "grid2",
                                                "items": [{"text": "A", "url": "/a", "sort_order": 3}]}}))
    staff = ot.staff_js_config(ot.normalize({"staff_links": {"items": [{"text": "S", "url": "/s"}]}}))
    got, notes = ot.sync_settings({"config_OpacUserJS": json.dumps(opac), "config_IntranetUserJS": json.dumps(staff),
                                   "block_OpacUserJS": "yes", "block_IntranetUserJS": "yes"})
    assert got["default_theme"] == "dark" and not got["carousel"]["enabled"]
    assert got["links"]["style"] == "metal" and got["links"]["items"][0]["sort_order"] == 3
    assert got["staff_links"]["enabled"] and got["staff_links"]["items"][0]["text"] == "S"
    assert "rebuilt" in notes[0][0]
    # Nothing at all: None, the screen keeps its fields.
    got, notes = ot.sync_settings({"data": "/* KEI-THEME-DATA: {broken */", "state": "[]"})
    assert got is None and "Nothing of the panel" in notes[0][0]


def test_staff_material_like_the_opac():
    # Saved before the staff had a material: flat, its old corners, no new blocks.
    old = ot.normalize({"staff": {"enabled": True, "accent": "#0f766e"}})["staff"]
    assert (old["texture"], old["radius_block"], old["opacity"]) == ("flat", 12, 100)
    flat = ot.staff_css_body(ot.normalize({"staff": {"enabled": True}}))
    assert "backdrop-filter" not in flat and "--nexus-staff-radius: 12px" in flat
    st = {"enabled": True, "texture": "frosted", "blur": 99, "opacity": 10, "radius_block": 4,
          "radius_input": 2, "radius_button": 30, "page": "#0b1220"}
    cfg = ot.normalize({"staff": st})
    assert cfg["staff"]["blur"] == ot.RANGES["blur"][1] and cfg["staff"]["opacity"] == ot.RANGES["opacity"][0]
    css = ot.staff_css_body(cfg)
    for part in ("--nexus-staff-blur: 30px", "--nexus-staff-surface-a: 0.30", "--nexus-staff-radius: 4px",
                 "--nexus-staff-r-input: 2px", "--nexus-staff-r-btn: 30px", "--nexus-staff-page: #0b1220",
                 "html body .page-section::before", "backdrop-filter: blur(var(--nexus-staff-blur))",
                 "border-radius: var(--nexus-staff-r-input) 0 0 var(--nexus-staff-r-input)"):
        assert part in css, part
    # The blur is on a layer behind the content, never on a block itself
    # (it would trap Koha's position: fixed modals).
    block_rule = css.split("html body .page-section, html body #area-news, html body fieldset.rows {", 1)[1].split("}", 1)[0]
    assert "backdrop-filter" not in block_rule and "isolation: isolate" in block_rule
    metal = ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "texture": "metal"}}))
    assert "#f0f0f0 0%, #dcdcdc 50%" in metal and "nav.navbar.bg-dark" in metal
    for tex in ot.TEXTURES:     # every texture is accepted and builds
        assert ot.staff_css_body(ot.normalize({"staff": {"enabled": True, "texture": tex}}))
    assert ot.parse_theme_data(ot.css_block(cfg))["staff"]["texture"] == "frosted"


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
    assert st["film"] == ot.STAFF_FILM[0]                          # the staff film keeps tables readable
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
            for dark, opacity in ((False, 76), (True, 76), (False, 100), (True, 100)):
                c = ot.panel_colors({**cfg, "panel_opacity": opacity}, dark)
                assert len(c["grounds"]) == 4
                for bg in c["grounds"]:
                    assert ot.contrast(c["text"], bg) >= 7, (accent, surface, dark)
                    for key in ("muted", "link", "ink"):
                        assert ot.contrast(c[key], bg) >= 4.5, (accent, surface, dark, key)
            # More see-through than the default: the text still reaches AA (4.5:1) on any wallpaper.
            for dark in (False, True):
                c = ot.panel_colors({**cfg, "panel_opacity": 60}, dark)
                assert min(ot.contrast(c["text"], bg) for bg in c["grounds"]) >= 4.5, (accent, surface, dark)
    # Light mode reads dark on light even when the block background is dark (the screenshots' case).
    light = ot.panel_colors(ot.normalize({"surface": "#333844"}), False)
    assert ot.luminance(light["panel"]) > .8 and light["text"] == "#1a1a1a"
    dark = ot.panel_colors(ot.normalize({}), True)
    assert (dark["panel"], dark["inner"]) == ("#161b22", "#0d1117") and dark["text"].startswith("#e")


def test_panels_css_covers_koha_panels():
    assert ot.normalize({})["panel_opacity"] == 76
    css = ot.css_body(ot.normalize({"panel_opacity": 72, "surface": "#333844"}))
    assert "--kei-panel-a: 0.72;" in css and "--kei-panel-rgb: 22, 27, 34;" in css
    for sel in ("html body .breadcrumb", "html body .main .tab-content", "html body .main #search-facets",
                "html body .main #menu li a", "html body .main #usermenu li a", "html body .main #action",
                "html body .main .nav_results", "html body .main .selections-toolbar", "html body #opaccredits",
                "html body .main .results_summary", "html body .main .note", "html body .main p.details"):
        assert sel in css, sel
    # The main area left the glass blocks: header and search keep the texture, .main is a panel.
    texture = css[:css.index("Content panels")]
    assert "html body .main," not in texture and "html body .main {" in css
    # Frosted glass: translucent panels with a 12px blur (WebKit too), inner panels translucent as well.
    assert "html body .main::before {" in css and "-webkit-backdrop-filter: blur(12px);" in css
    assert "    backdrop-filter: blur(12px);" in css and "--kei-panel-2: rgba(" in css
    assert "text-shadow: var(--kei-p-shadow);" in css and "font-weight: 600;" in css
    # The footer credits: no box behind them, only a halo around the letters.
    assert "#opaccredits::before" not in css and "html body .main, html body #opaccredits" not in css
    assert "background: transparent !important; }" in css and 'html[data-kei-theme="dark"] body #opaccredits {' in css
    assert 'html[data-kei-theme="dark"] body .main .alert {' in css
    assert ot.normalize({"panel_opacity": 10})["panel_opacity"] == 50
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
                                                        "opaccredits\ton\n")
        assert "Internal extension 123" in (work / "contents" / "StaffLoginInstructions.html").read_text()
        assert not (work / "contents" / "OpacLoginInstructions.html").exists()
        assert json.loads((work / "contents.json").read_text())["credits"]["name"] == "Biblioteca"
    finally:
        shutil.rmtree(work)
    # sync: the contents settings join the settings read from Koha.
    found = {"data": ot.data_line(ot.normalize({})), "contents_settings": json.dumps(ot.contents_settings(cfg))}
    synced, notes = ot.sync_settings(found)
    assert synced["credits"]["name"] == "Biblioteca" and any("theme-settings.json" in n for n, _ in notes)
