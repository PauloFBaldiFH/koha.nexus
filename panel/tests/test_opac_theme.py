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
