"""Browser checks use only the local static site and fictional training data."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import shutil
import threading

import pytest
from conftest import REPO

playwright = pytest.importorskip('playwright.sync_api')


@pytest.fixture(scope='module')
def site_url():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(REPO)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture(scope='module')
def browser():
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    if not executable:
        pytest.skip('System Chromium is required')
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])
        yield browser
        browser.close()


def test_all_guides_complete_in_a_real_browser(browser, site_url):
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(site_url + '/staff-manual/')
        page.locator('#lesson').wait_for(state='visible')
        links = page.locator('#guide-nav a').evaluate_all('(links) => links.map(a => a.hash)')
        assert len(links) == 20
        for index, link in enumerate(links, 1):
            page.goto(site_url + '/staff-manual/' + link)
            page.locator('#practice-next').click()
            page.locator('#practice-next').click()
            assert 'Use the fictional example' in page.locator('#practice-message').inner_text()
            page.locator('#fill-example').click()
            page.locator('#practice-next').click()
            assert page.locator('#review').is_visible()
            page.locator('#practice-next').click()
            assert page.locator('#practice-next').is_hidden()
            assert page.locator('#practice-message').inner_text()
            assert page.locator('#progress').inner_text().startswith(f'{index} / 20')
        page.reload()
        page.locator('#lesson').wait_for(state='visible')
        assert page.locator('#progress').inner_text().startswith('20 / 20')
        page.locator('#guide-search').fill('nothing-matches-this')
        assert page.locator('#guide-nav').inner_text() == 'No matching guides. Try another task.'
        page.locator('#guide-search').fill('inventory')
        assert page.locator('#guide-nav a').count() >= 1
        page.locator('#clear-progress').click()
        assert page.locator('#progress').inner_text().startswith('0 / 20')
        assert not errors
    finally:
        page.close()


def test_mobile_layout_and_localized_home_link(browser, site_url):
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    try:
        page.goto(site_url + '/languages/pt/')
        page.locator('#menu-toggle').click()
        page.get_by_role('link', name='Koha staff manual (English)', exact=True).click()
        page.locator('#lesson').wait_for(state='visible')
        assert '/staff-manual/' in page.url
        assert page.locator('html').get_attribute('lang') == 'en'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.goto(site_url + '/staff-manual/#inventory')
        assert page.locator('#lesson-title').inner_text() == 'Inventory'
        page.locator('#practice-next').click()
        page.locator('#fill-example').click()
        page.locator('#practice-reset').click()
        assert page.locator('#practice-next').inner_text() == 'Open training task'
    finally:
        page.close()


def test_storage_blocked_and_load_error(browser, site_url):
    context = browser.new_context()
    context.add_init_script("Object.defineProperty(window, 'localStorage', {get() {throw Error('blocked')}})")
    page = context.new_page()
    try:
        page.goto(site_url + '/staff-manual/#reports')
        page.locator('#lesson').wait_for(state='visible')
        page.locator('#practice-next').click()
        page.locator('#fill-example').click()
        page.locator('#practice-next').click()
        page.locator('#practice-next').click()
        assert page.locator('#progress').inner_text().startswith('1 / 20')
        page.route('**/staff-manual/lessons.json', lambda route: route.abort())
        page.reload()
        playwright.expect(page.locator('#load-status')).to_contain_text('could not be loaded')
        assert page.locator('#lesson').is_hidden()
    finally:
        context.close()
