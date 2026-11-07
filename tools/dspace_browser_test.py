#!/usr/bin/env python3
"""Real account, browser deposit and public/private acceptance on the disposable CI stack.

Called only by dspace_install_test.py after its explicit disposable-machine gate.
No traces, cookies, authorization headers, passwords or browser storage are saved.
"""
import hashlib
import base64
import subprocess
import http.cookiejar
import json
import re
from pathlib import Path
import secrets
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPHandler, HTTPCookieProcessor, ProxyHandler, Request, build_opener


class API:
    def __init__(self, origin):
        self.origin = origin
        self.host = urlsplit(origin).netloc
        self.csrf = ''
        self.bearer = ''
        self.opener = build_opener(ProxyHandler({}), HTTPHandler(), HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, method='GET', data=None, content_type='application/json', allowed=(200, 201, 204), raw=False):
        if path.startswith('http'):
            parts = urlsplit(path)
            if parts.netloc != self.host:
                raise RuntimeError('Unexpected API destination.')
            path = parts.path + ('?' + parts.query if parts.query else '')
        if not path.startswith('/server/'):
            path = '/server/api' + path
        headers = {'Host': self.host, 'Origin': self.origin, 'Accept': '*/*' if raw else 'application/hal+json', 'Content-Type': content_type}
        if self.csrf: headers['X-XSRF-TOKEN'] = self.csrf
        if self.bearer: headers['Authorization'] = self.bearer
        if data is not None and not isinstance(data, bytes):
            data = json.dumps(data).encode()
        request = Request('http://127.0.0.1:8100' + path, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=60)
        except HTTPError as error:
            response = error
        with response:
            code = response.code
            self.csrf = response.headers.get('DSPACE-XSRF-TOKEN', self.csrf)
            self.bearer = response.headers.get('Authorization', self.bearer)
            body = response.read()
        if code not in allowed:
            # Never include a request, response body or auth headers in a failure.
            raise RuntimeError('API refused %s %s (HTTP %s)' % (method, urlsplit(path).path, code))
        if raw: return body
        return json.loads(body) if body else {}

    def login(self, email, password):
        self.request('/authn/status')
        self.request('/authn/login', 'POST', urlencode({'user': email, 'password': password}).encode(), 'application/x-www-form-urlencoded', (200,))
        if not self.bearer.startswith('Bearer '):
            raise RuntimeError('Authentication returned no bearer token.')


def exercise(rt, output):
    from playwright.sync_api import sync_playwright, expect
    origin = rt.state()['url']
    email = 'nexus-acceptance@example.org'
    password = secrets.token_urlsafe(24)
    replacement = secrets.token_urlsafe(24)
    def check(value, message):
        if not value: raise AssertionError(message)
        print('PASS: ' + message, flush=True)
    def administrator(operation, request=None):
        # Exercise the normal installer/checksum loader and protected stdin,
        # not only the Python adapter called directly by this disposable test.
        args = ['bash', str(Path(__file__).resolve().parents[1] / 'installer'), '--task', 'dspace-panel', 'admin-' + operation]
        if operation != 'status': args.append('--confirm')
        result = subprocess.run(args, input=json.dumps(request) if request is not None else None,
                                text=True, capture_output=True, timeout=240)
        if result.returncode:
            raise RuntimeError('Administrator task refused (' + operation + ')')
        lines = [line.split('=',1)[1] for line in result.stdout.splitlines() if line.startswith('@@result payload=')]
        if len(lines) != 1: raise RuntimeError('Administrator task returned no valid protocol result.')
        return json.loads(base64.b64decode(lines[0], validate=True))
    check(administrator('status')['state'] == 'missing', 'no default DSpace administrator')
    request = dict(email=email, first='Nexus', last='Acceptance', language='en', password=password)
    administrator('create', request)
    check(email in administrator('status')['admins'], 'administrator created with official DSpace services')
    try:
        administrator('create', dict(request, password=replacement))
    except Exception as error:
        if not isinstance(error, RuntimeError): raise
    else:
        raise AssertionError('Existing account was overwritten.')
    api = API(origin); api.login(email, password)
    # Reset is explicit, scoped to this administrator; old password must stop working.
    administrator('password', dict(email=email, password=replacement))
    try:
        API(origin).login(email, password)
    except RuntimeError as error:
        check('(HTTP 401)' in str(error), 'old password is rejected by authentication, not by an unrelated failure')
    else:
        raise AssertionError('Old password remains valid.')
    api = API(origin); api.login(email, replacement)
    check(True, 'password reset preserves the account and invalidates the old password')
    for path in rt.root.iterdir():
        if path.is_file():
            text = path.read_text(errors='replace')
            check(password not in text and replacement not in text, 'administrator password absent from ' + path.name)
    community = api.request('/core/communities', 'POST', {'metadata': {'dc.title': [{'value': 'Nexus acceptance community'}]}})
    collection = api.request('/core/collections?parent=' + community['uuid'], 'POST', {'metadata': {'dc.title': [{'value': 'Nexus acceptance collection'}]}})
    workspace = api.request('/submission/workspaceitems?owningCollection=' + collection['uuid'], 'POST')
    wid = str(workspace['id'])
    embedded = workspace.get('_embedded', {})
    item = embedded.get('item') or api.request(workspace['_links']['item']['href'])
    itemid = item['uuid']
    api.request('/submission/workspaceitems/' + wid, 'PATCH', [
        {'op': 'add', 'path': '/sections/traditionalpageone/dc.title', 'value': [{'value': 'Nexus draft title'}]},
        {'op': 'add', 'path': '/sections/traditionalpageone/dc.date.issued', 'value': [{'value': '2026'}]},
        {'op': 'add', 'path': '/sections/traditionalpageone/dc.type', 'value': [{'value': 'Article'}]},
        {'op': 'add', 'path': '/sections/license/granted', 'value': True},
    ], 'application/json-patch+json')
    fixture = Path(output) / 'nexus-acceptance.txt'
    fixture.write_bytes(b'Nexus repository acceptance document. Public, then restricted.\n')
    expected = hashlib.sha256(fixture.read_bytes()).hexdigest()
    title = 'Nexus browser acceptance document'
    stage = 'browser launch'
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--host-resolver-rules=MAP repository.kei.test 127.0.0.1'])
        context = browser.new_context(locale='en-US')
        context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname in ('repository.kei.test', '127.0.0.1') else route.abort())
        page = context.new_page(); page.set_default_timeout(60000)
        try:
            stage = 'browser login'
            page.goto(origin + '/login', wait_until='domcontentloaded')
            page.locator('input[type=email]').fill(email)
            page.locator('input[type=password]').fill(replacement)
            page.locator('[data-test=login-button]').click()
            page.wait_for_url(lambda url: '/login' not in url, timeout=60000)
            check(True, 'real browser signs in with the chosen password')
            stage = 'browser deposit form'
            page.goto(origin + '/workspaceitems/' + wid + '/edit', wait_until='domcontentloaded')
            # Upstream adds a literal ' *' to required field labels.
            title_input = page.get_by_label(re.compile(r'^Title\s*\*?$'))
            agreement = page.locator('#user-agreement-accept')
            expect(agreement.or_(title_input).first).to_be_visible(timeout=90000)
            consent = page.get_by_role('button', name="That's ok", exact=True)
            if consent.is_visible(): consent.click()
            if agreement.is_visible():
                stage = 'disposable account user agreement'
                agreement.check()
                page.locator('#button-save').click()
                expect(agreement).not_to_be_visible(timeout=60000)
                page.goto(origin + '/workspaceitems/' + wid + '/edit', wait_until='domcontentloaded')
            stage = 'browser deposit form'
            title_input.fill(title); title_input.press('Tab')
            page.locator('input[type=file]').first.set_input_files(str(fixture))
            expect(page.get_by_text(fixture.name, exact=False).first).to_be_visible(timeout=90000)
            page.locator('#save').click()
            # Saving must actually reach the REST API before final deposit.
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                updated = api.request('/core/items/' + itemid)
                if updated.get('name') == title: break
                time.sleep(1)
            check(updated.get('name') == title, 'metadata edited in the browser is persisted')
            stage = 'browser deposit'
            with page.expect_response(lambda r: '/api/workflow/workflowitems' in r.url and r.request.method == 'POST', timeout=90000) as submitted:
                page.locator('#deposit').click()
            check(submitted.value.status == 201, 'real browser completes the deposit')
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                archived = api.request('/core/items/' + itemid)
                if archived.get('inArchive'): break
                time.sleep(2)
            check(archived.get('inArchive') is True, 'deposited item is archived')
            bundles = api.request('/core/items/' + itemid + '/bundles').get('_embedded', {}).get('bundles', [])
            bundle = next(b for b in bundles if b['name'] == 'ORIGINAL')
            streams = api.request('/core/bundles/' + bundle['uuid'] + '/bitstreams').get('_embedded', {}).get('bitstreams', [])
            stream = next(b for b in streams if b['name'] == fixture.name)
            content = '/core/bitstreams/' + stream['uuid'] + '/content'
            anonymous = API(origin)
            check(hashlib.sha256(anonymous.request(content, raw=True)).hexdigest() == expected, 'anonymous download has the original checksum')
            stage = 'anonymous public page'
            public = browser.new_context(locale='en-US'); anon_page = public.new_page()
            anon_page.goto(origin + '/items/' + itemid, wait_until='domcontentloaded')
            expect(anon_page.get_by_text(title, exact=True).first).to_be_visible(timeout=60000)
            anon_page.screenshot(path=str(Path(output) / 'dspace-public-item.png'), full_page=True)
            public.close()
            stage = 'restricting published content'
            for uuid in (stream['uuid'], bundle['uuid'], itemid):
                policies = api.request('/authz/resourcepolicies/search/resource?' + urlencode({'uuid': uuid, 'action': 'READ', 'size': 100})).get('_embedded', {}).get('resourcepolicies', [])
                check(bool(policies), 'fixture has explicit read policies: ' + uuid)
                for policy in policies:
                    api.request('/authz/resourcepolicies/' + str(policy['id']), 'DELETE')
            rt.compose('run', '--rm', '--no-deps', '-T', 'backend', 'cli', 'index-discovery', '-i', itemid, timeout=180)
            API(origin).request(content, allowed=(401, 403, 404), raw=True)
            API(origin).request('/core/items/' + itemid, allowed=(401, 403, 404), raw=True)
            check(hashlib.sha256(api.request(content, raw=True)).hexdigest() == expected, 'administrator still downloads the restricted file with its original checksum')
            stage = 'anonymous restricted page'
            private = browser.new_context(locale='en-US'); private_page = private.new_page()
            initial_response = private_page.goto(origin + '/items/' + itemid, wait_until='networkidle')
            initial_html = initial_response.text() if initial_response else ''
            check(title not in initial_html and title not in private_page.content(), 'anonymous browser and initial SSR payload omit private item metadata')
            search = API(origin).request('/discover/search/objects?' + urlencode({'query': title}))
            check(itemid not in json.dumps(search), 'private item absent from anonymous discovery')
            private.close()
            (Path(output) / 'dspace-browser-acceptance.json').write_text(json.dumps({'browser_deposit': True, 'private_access_denied': True, 'download_sha256': expected, 'item_uuid': itemid}, indent=2))
        except Exception as error:
            # Only control names/types, never values, cookies or page storage.
            try:
                controls = page.locator('input').evaluate_all('(nodes) => nodes.map(n => ({type:n.type,id:n.id,name:n.name,label:n.getAttribute("aria-label")}))')
                buttons = page.locator('button').all_text_contents()
                detail = json.dumps({'stage':stage,'inputs':controls,'buttons':buttons})[:4500]
                print('::notice title=DSpace browser controls::' + detail.replace('%','%25').replace('\n','%0A').replace('\r','%0D'), flush=True)
            except Exception:
                pass
            # A Playwright fill error can echo its input in the exception text.
            raise RuntimeError('DSpace browser acceptance failed at %s (%s)' % (stage, type(error).__name__)) from None
        finally:
            context.close(); browser.close()
