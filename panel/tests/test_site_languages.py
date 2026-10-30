"""Static language pages, shared assets and translation contracts for the website."""
from collections import Counter
from html.parser import HTMLParser
import importlib.util
import json
import re
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
    assert next(l for l in langs if l['dict'] == 'pt')['folder'] == 'languages/pt'
    for lang in langs:
        if lang['dict'] != 'en':
            assert lang['folder'] == 'languages/' + lang['dict']
            assert not (REPO / lang['dict']).exists(), 'obsolete root language directory'


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
    for rel, generated in site.render_files().items():
        assert (REPO / rel).read_text(encoding='utf-8') == generated, rel
    run = subprocess.run([sys.executable, str(REPO / 'export_site.py'), '--check'],
                         cwd=REPO, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr


def test_every_page_has_unique_search_tags_and_only_homepages_carry_app_data():
    titles, descriptions, canonicals = Counter(), Counter(), []
    for lang in site.languages():
        for kind in ['home', 'preview']:
            path = REPO / site.page_path(lang, kind)
            text = path.read_text(encoding='utf-8')
            page = Page(text)
            title = text.split('<title', 1)[1].split('>', 1)[1].split('</title>', 1)[0]
            assert title.strip(), path
            titles[title] += 1
            meta = {a.get('name') or a.get('property'): a.get('content') for tag, a in page.nodes if tag == 'meta'}
            assert meta['description'] and meta['og:description'] == meta['description'], path
            descriptions[(lang['dict'], meta['description'])] += 1
            canonical = [a['href'] for tag, a in page.nodes if tag == 'link' and a.get('rel') == 'canonical']
            assert canonical == [site.public_url(lang, kind)] == [meta['og:url']], path
            assert target(path, canonical[0]) == path.resolve()
            canonicals.append(canonical[0])
            assert meta['og:title'] and meta['og:image'].startswith('https://koha.nexus/')
            assert target(path, meta['og:image']).is_file()
            ld = [a for tag, a in page.nodes if tag == 'script' and a.get('type') == 'application/ld+json']
            if kind == 'home':
                data = json.loads(text.split('<script type="application/ld+json">', 1)[1].split('</script>', 1)[0])
                assert data['@type'] == 'SoftwareApplication' and data['offers']['price'] == '0'
                assert 'Windows' in data['operatingSystem'] and data['url'] == canonical[0]
                assert data['license'] == site.LICENSE_URL and 'GNU GENERAL PUBLIC LICENSE' in (REPO / 'LICENSE').read_text()
            else:
                assert not ld, path
                download = next(a for tag, a in page.nodes if tag == 'a' and 'kp-download' in a.get('class', ''))
                assert download['href'].endswith('index.html#windows')
                assert target(path, download['href'].split('#')[0]) == (REPO / site.page_path(lang, 'home')).resolve()
    assert max(titles.values()) == 1, [t for t, n in titles.items() if n > 1]
    assert max(descriptions.values()) == 1
    for code, words in {'pt': ['Koha no Windows', 'Z39.50', 'importação MARC'], 'en': ['Koha on Windows', 'Z39.50', 'MARC import']}.items():
        lang = next(l for l in site.languages() if l['dict'] == code)
        text = (REPO / site.page_path(lang, 'home')).read_text(encoding='utf-8')
        head = text.split('</head>', 1)[0]
        assert all(w in head for w in words), (code, words)
    sitemap = (REPO / 'sitemap.xml').read_text(encoding='utf-8')
    assert sorted(re.findall(r'<loc>([^<]+)</loc>', sitemap)) == sorted(canonicals)
    robots = (REPO / 'robots.txt').read_text(encoding='utf-8')
    assert 'Sitemap: https://koha.nexus/sitemap.xml' in robots and 'Disallow: /\n' not in robots


def test_home_browser_language_detection_and_manual_override():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to exercise browser language selection')
    # Execute the actual routing/listener code with a minimal browser adapter.
    script = (REPO / 'site/assets/home.js').read_text().split('    function copyFallback', 1)[0]
    harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = SOURCE;
function visit(path, languages, saved, blocked = false) {
  let redirect = null;
  const links = ['en','pt','es','fr','de','tl'].map(code => ({
    dataset: {language: code}, href: 'https://example.org/project/' + (code === 'en' ? '' : 'languages/' + code + '/'),
    addEventListener(event, callback) { this.click = callback; }
  }));
  const url = new URL(path, 'https://example.org/project/');
  const context = {
    URL, navigator: {languages, language: languages[0]},
    location: {href: url.href, hash: url.hash, replace(value) { redirect = value; }},
    localStorage: {
      getItem() { if (blocked) throw Error('blocked'); return saved; },
      setItem(key, value) { if (blocked) throw Error('blocked'); saved = value; }
    },
    document: {
      currentScript: {src: 'https://example.org/project/site/assets/home.js'},
      body: {dataset: {language: path.includes('/languages/es/') ? 'es' : 'en'}},
      getElementById() { return {textContent: '{}'}; },
      querySelectorAll() { return links; }
    }
  };
  vm.runInNewContext(source, context);
  return {redirect, links, saved: () => saved};
}
assert.equal(visit('./', ['pt-BR']).redirect, 'https://example.org/project/languages/pt/');
assert.equal(visit('./', ['xx', 'fr-CA']).redirect, 'https://example.org/project/languages/fr/');
assert.equal(visit('index.html', ['pt-BR'], 'pt').redirect, null);
assert.equal(visit('./', ['fil-PH']).redirect, 'https://example.org/project/languages/tl/');
assert.equal(visit('./', ['xx']).redirect, null);
assert.equal(visit('./', ['en-US', 'pt']).redirect, null);
assert.equal(visit('./', ['pt'], 'en').redirect, null);
assert.equal(visit('./', ['pt'], 'de').redirect, 'https://example.org/project/languages/de/');
assert.equal(visit('./', ['fr'], null, true).redirect, 'https://example.org/project/languages/fr/');
assert.equal(visit('languages/es/', ['pt'], 'de').redirect, null);
assert.equal(visit('./?lang=en', ['pt'], 'de').redirect, null);
assert.equal(visit('./?lang=br&ref=demo#features', ['en']).redirect,
             'https://example.org/project/languages/pt/?ref=demo#features');
assert.equal(visit('./#pt', ['en']).redirect, 'https://example.org/project/languages/pt/');
const manual = visit('./', ['en']);
manual.links.find(a => a.dataset.language === 'en').click();
assert.equal(manual.saved(), 'en');
const blocked = visit('./', ['en'], null, true);
assert.doesNotThrow(() => blocked.links[0].click());
'''
    result = subprocess.run([node, '-e', harness.replace('SOURCE', json.dumps(script), 1)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
