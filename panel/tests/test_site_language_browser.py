"""Real DOM regression: the page body is not a language-selector link."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import shutil
import threading

import pytest
from conftest import REPO

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
import playwright.sync_api as playwright
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




def test_english_choice_is_not_overwritten_by_the_portuguese_body(browser, site_url):
    context = browser.new_context(locale='pt-BR')
    page = context.new_page()
    try:
        page.goto(site_url + '/')
        expect(page.locator('body')).to_have_attribute('data-language', 'pt')
        page.locator('a[data-language="en"]').click()
        expect(page.locator('body')).to_have_attribute('data-language', 'en')
        assert page.evaluate("localStorage.getItem('koha_lang')") == 'en'
        page.goto(site_url + '/')
        expect(page.locator('body')).to_have_attribute('data-language', 'en')
        page.locator('a[data-language="es"]').click()
        expect(page.locator('body')).to_have_attribute('data-language', 'es')
        assert page.evaluate("localStorage.getItem('koha_lang')") == 'es'
        page.locator('#main-nav a[href="#features"]').click()
        expect(page).to_have_url(site_url + '/languages/es/index.html#features')
        # Ordinary links must not overwrite the language preference either.
        assert page.evaluate("localStorage.getItem('koha_lang')") == 'es'
    finally:
        context.close()


def test_explicit_english_index_survives_a_portuguese_browser_and_blocked_storage(browser, site_url):
    context = browser.new_context(locale='pt-BR')
    context.add_init_script("Object.defineProperty(window, 'localStorage', {get() {throw Error('blocked')}})")
    page = context.new_page()
    try:
        page.goto(site_url + '/index.html')
        expect(page.locator('body')).to_have_attribute('data-language', 'en')
        page.goto(site_url + '/languages/pt/')
        page.locator('a[data-language="en"]').click()
        expect(page.locator('body')).to_have_attribute('data-language', 'en')
        page.goto(site_url + '/?lang=en')
        expect(page.locator('body')).to_have_attribute('data-language', 'en')
    finally:
        context.close()


@pytest.mark.parametrize('method', ['clipboard', 'fallback', 'failure'])
def test_donation_copy_feedback(browser, site_url, method):
    context = browser.new_context(locale='pt-BR', reduced_motion='reduce')
    context.add_init_script("""(method => {
      window.copiedDonationValues = [];
      Object.defineProperty(navigator, 'clipboard', {value: {
        writeText: async value => {
          if (method !== 'clipboard') throw Error('blocked');
          window.copiedDonationValues.push(value);
        }
      }});
      document.execCommand = command => {
        if (method !== 'fallback') return false;
        window.copiedDonationValues.push(document.querySelector('textarea[readonly]').value);
        return command === 'copy';
      };
    })(%s);""" % repr(method))
    page = context.new_page()
    try:
        page.goto(site_url + '/languages/pt/')
        for button in page.locator('#support button[data-copy]').all():
            original = button.inner_text()
            value = button.get_attribute('data-copy')
            status = page.locator('#' + button.get_attribute('data-copy-status'))
            button.click()
            expect(status).to_have_text('Não foi possível copiar.' if method == 'failure' else 'Copiado!')
            if method != 'failure':
                assert page.evaluate('window.copiedDonationValues.at(-1)') == value
                # A second click must still restore the original label.
                button.click()
            expect(button).to_have_text(original)
            expect(status).to_be_empty()
        expect(page.locator('#support .support-share a')).to_have_attribute(
            'href', 'https://github.com/PauloFBaldiFH/koha.nexus')
        assert page.locator('textarea[readonly]').count() == 0
    finally:
        context.close()
