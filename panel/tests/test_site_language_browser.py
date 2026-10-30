"""Real DOM regression: the page body is not a language-selector link."""
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from test_staff_manual_browser import browser, site_url


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
        page.get_by_role('link', name='Koha staff manual (English)', exact=True).click()
        expect(page.locator('#staff-options button').first).to_be_visible()
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
