"""HTTP and browser tests against a disposable WordPress, never a production site.

Usage: python tests/browser.py /tmp/nxev-fixtures.json /tmp/nxev-browser-output
The fixture contains temporary session cookies and must not be distributed.
"""
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from io import BytesIO
from PIL import Image
import zxingcpp

from playwright.sync_api import sync_playwright

fixtures = json.loads(Path(sys.argv[1]).read_text())
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
checks = 0


def check(condition, message):
    global checks
    assert condition, message
    checks += 1
    print('PASS:', message)


def with_query(url, **values):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(values)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    context = browser.new_context()
    context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname in ('localhost', '127.0.0.1') else route.abort())
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    response = page.goto(fixtures['pass_url'])
    check(response.status == 200, 'valid guest pass opens over HTTP')
    check('no-store' in response.headers.get('cache-control', ''), 'pass is not cacheable')
    check(response.headers.get('referrer-policy') == 'no-referrer', 'bearer link not sent as referrer')
    check(page.locator('.nxev-qr svg').count() == 1, 'QR rendered locally')
    decoded = zxingcpp.read_barcode(Image.open(BytesIO(page.locator('.nxev-qr').screenshot())))
    check(decoded and decoded.text == fixtures['pass_url'], 'displayed QR decodes to the exact pass URL')
    check(page.get_by_role('button', name='Confirmar presença', exact=True).count() == 0, 'guest cannot check themselves in')
    page.screenshot(path=str(output / 'passe-desktop.png'), full_page=True)
    response = context.request.get(with_query(fixtures['pass_url'], nxev_key='0' * 64))
    check(response.status == 404, 'wrong pass token returns 404')
    response = context.request.get(with_query(fixtures['pass_url'], nxev_key=''))
    check(response.status == 404, 'sequential booking id alone does not authorize')
    verify_url = 'http://localhost:18791/?' + urlencode({'nxev_verify': fixtures['cert_code']})
    page.goto(verify_url)
    check(page.get_by_role('heading', name='Comprovante válido', exact=True).count() == 1, 'public verification succeeds')
    check('Érica da Conceição' not in page.locator('body').inner_text(), 'public verification does not publish participant name')
    page.goto(with_query(fixtures['pass_url'], nxev_document='1'))
    check(page.get_by_role('heading', name='Érica da Conceição').count() == 1, 'private printable document preserves accents')
    page.screenshot(path=str(output / 'comprovante.png'), full_page=True)
    for width in (1280, 390):
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(fixtures['agenda_url'])
        check(page.locator('.nxev-card').count() > 0, f'agenda renders real event cards at {width}px')
        check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'no page overflow at {width}px')
        page.screenshot(path=str(output / f'agenda-{width}.png'), full_page=True)
    response = context.request.get(fixtures['member_url'])
    check('no-store' in response.headers.get('cache-control', ''), 'participant page not cached')
    response = context.request.post('http://localhost:18791/wp-admin/admin-post.php', form={
        'action': 'nxev_action', 'booking_id': str(fixtures['booking_id']), 'operation': 'checkin', '_wpnonce': 'invalid'})
    check(response.status == 403, 'unauthorized state-changing request with invalid nonce rejected')
    context.add_cookies([
        {'name': fixtures['auth_cookie_name'], 'value': fixtures['auth_cookie'], 'url': 'http://localhost:18791'},
        {'name': fixtures['login_cookie_name'], 'value': fixtures['login_cookie'], 'url': 'http://localhost:18791'},
    ])
    page.goto(f'http://localhost:18791/wp-admin/admin.php?page=nexus-eventos&event_id={fixtures["event_id"]}')
    check(page.get_by_role('heading', name='Nexus Eventos', exact=True).count() == 1, 'authorized administrative dashboard opens')
    check(page.get_by_role('link', name='Exportar participantes e presença (CSV)').count() == 1, 'authorized CSV export available')
    csv_url = page.get_by_role('link', name='Exportar participantes e presença (CSV)').get_attribute('href')
    exported = context.request.get(csv_url)
    check(exported.status == 200 and 'text/csv' in exported.headers.get('content-type', ''), 'CSV endpoint streams download')
    check('Érica da Conceição' in exported.text(), 'CSV export preserves names')
    page.set_viewport_size({'width': 1280, 'height': 900})
    page.screenshot(path=str(output / 'gestao-presenca.png'), full_page=True)
    page.goto(f'http://localhost:18791/wp-admin/post.php?post={fixtures["future_post"]}&action=edit')
    check(page.locator('#nxev-integration').count() == 1, 'event editor includes Tainacan and certificate metabox')
    page.goto(fixtures['pass_url'])
    check(page.get_by_role('button', name='Confirmar presença', exact=True).count() == 1, 'staff sees attendance confirmation')
    # GET/scanning never changes the attendance state. A nonce-bearing POST is required.
    undo = page.locator('form').filter(has=page.get_by_role('button', name='Desfazer presença e revogar comprovante', exact=True))
    with page.expect_navigation():
        undo.get_by_role('button').click()
    page.goto(verify_url)
    check(page.get_by_role('heading', name='Comprovante não encontrado ou inválido').count() == 1, 'undo revokes document and public verification')
    check(not errors, 'no JavaScript errors in addon pages: ' + repr(errors))
    browser.close()
print(f'BROWSER: {checks} checks passed')
