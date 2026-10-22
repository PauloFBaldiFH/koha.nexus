"""Static language pages, shared assets and translation contracts for the website."""
from collections import Counter
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import pytest
from conftest import REPO

spec = importlib.util.spec_from_file_location('export_site_under_test', REPO / 'export_site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def target(page, href):
    url = urlsplit(href)
    if url.netloc:
        assert url.netloc == 'koha.nexus'
        path = REPO / unquote(url.path).lstrip('/')
    else:
        path = page.parent / unquote(url.path)
    if path.is_dir() or href.endswith('/'):
        path /= 'index.html'
    path = path.resolve()
    assert path.is_relative_to(REPO), href
    return path


def test_languages_come_from_existing_panel_dictionaries():
    langs = site.languages()
    assert {l['dict'] for l in langs} == {'en'} | {p.stem for p in (REPO / 'lang').glob('*.cache')}
    assert len(langs) == 23
    assert langs[0]['dict'] == 'en' and langs[0]['folder'] == ''
    assert next(l for l in langs if l['dict'] == 'pt')['folder'] == 'pt'


@pytest.mark.parametrize('kind', ['home', 'preview'])
def test_all_static_pages_have_working_language_links_and_alternates(kind):
    langs = site.languages()
    expected = {l['dict']: (REPO / site.page_path(l, kind)).resolve() for l in langs}
    for lang in langs:
        path = expected[lang['dict']]
        assert path.is_file(), path
        page = Page(path.read_text(encoding='utf-8'))
        html = next(attrs for tag, attrs in page.nodes if tag == 'html')
        assert html['lang'] == lang['html']
        assert html['dir'] == ('rtl' if lang['dict'] in {'ar', 'fa'} else 'ltr')
        links = [a for tag, a in page.nodes if tag == 'a' and 'data-language' in a]
        assert len(links) == len(langs)
        assert {a['data-language']: target(path, a['href']) for a in links} == expected
        assert [a['data-language'] for a in links if a.get('aria-current') == 'page'] == [lang['dict']]
        alternate = [a for tag, a in page.nodes if tag == 'link' and a.get('rel') == 'alternate']
        assert Counter(a['hreflang'] for a in alternate) == Counter([l['html'] for l in langs] + ['x-default'])
        expected_hrefs = {l['html']: expected[l['dict']] for l in langs}
        expected_hrefs['x-default'] = expected['en']
        assert {a['hreflang']: target(path, a['href']) for a in alternate} == expected_hrefs
        assert all(p.is_file() for p in expected.values())
        if kind == 'preview':
            home = next(a for tag, a in page.nodes if 'data-home' in a)
            assert target(path, home['href']) == (REPO / site.page_path(lang, 'home')).resolve()


def test_root_is_rendered_in_english_without_javascript():
    text = (REPO / 'index.html').read_text(encoding='utf-8')
    assert '<html lang="en"' in text
    assert 'Talk to the project.' in text
    assert 'Your name or the library' in text
    assert 'Fale com o projeto.' not in text
    assert 'const translations' not in text
    assert 'onclick="setLanguage' not in text


def test_pages_share_existing_assets_and_protect_install_commands():
    commands = [
        'wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer\nsudo bash installer',
        'git clone https://github.com/PauloFBaldiFH/koha.nexus.git\ncd koha.nexus\nsudo bash installer',
        'irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex',
    ]
    for lang in site.languages():
        for kind in ['home', 'preview']:
            path = REPO / site.page_path(lang, kind)
            text = path.read_text(encoding='utf-8')
            page = Page(text)
            for tag, attrs in page.nodes:
                for name in ['src', 'href']:
                    href = attrs.get(name, '')
                    if not href or href.startswith(('#', 'mailto:', 'https:', 'http:')):
                        continue
                    if name == 'src' or (tag == 'link' and attrs.get('rel') == 'stylesheet'):
                        assert target(path, href).is_file(), (path, href)
            if kind == 'home':
                for command in commands:
                    assert command in text, (lang['dict'], command)


def test_locale_keys_and_placeholder_counts_match_english():
    locales = site.read_locales()
    for lang, data in locales.items():
        for group in ['home', 'manual_ui']:
            assert set(data[group]) == set(locales['en'][group])
            for key, value in data[group].items():
                assert site.placeholder_counts(value) == site.placeholder_counts(locales['en'][group][key]), (lang, key)
    assert site.placeholder_counts('{0} {name} %s %s') == Counter({'{0}': 1, '{name}': 1, '%s': 2})


def test_generator_rejects_a_placeholder_mismatch(tmp_path):
    shutil.copytree(REPO / 'site/locales', tmp_path / 'site/locales')
    path = tmp_path / 'site/locales/fr.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['home']['page_description'] += ' {name}'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(AssertionError, match='placeholder mismatch'):
        site.read_locales(tmp_path)


def test_generator_output_is_committed_and_reproducible():
    for rel, generated in site.render_pages().items():
        assert (REPO / rel).read_text(encoding='utf-8') == generated, rel
    run = subprocess.run([sys.executable, str(REPO / 'export_site.py'), '--check'],
                         cwd=REPO, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
