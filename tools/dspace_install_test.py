#!/usr/bin/env python3
"""Real isolated DSpace lifecycle acceptance, only on a DISPOSABLE root runner.

Requires the three built images and the existing installer resource driver.
No mocks; PostgreSQL, seven Solr cores, backend and SSR all run together.
The --disposable flag authorizes removal ONLY of this test's labelled resources.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'platforms/dspace'))
import runtime as module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable', action='store_true')
    args = parser.parse_args()
    if not args.disposable or os.geteuid() != 0:
        parser.error('Only run as root on a disposable CI machine with --disposable.')
    root = Path('/var/lib/koha-nexus/platforms/dspace')
    if root.exists():
        parser.error('An installation directory already exists; this machine is not empty.')
    output = Path(os.environ['RUNNER_TEMP'])
    # Exercise the normal root-owned destination. RUNNER_TEMP belongs to the
    # unprivileged runner and must not become a root-executed catalog directory.
    catalog = Path('/etc/koha-nexus/dspace-images.json')
    if catalog.exists():
        parser.error('An image catalog already exists; this machine is not empty.')
    rt = module.Runtime(root, catalog, driver=str(REPO / 'installer'),
                        progress=lambda phase: print('::notice title=DSpace phase::' + phase, flush=True))
    def check(cond, message):
        if not cond:
            raise AssertionError(message)
        print('PASS: ' + message, flush=True)
    check(not root.exists(), 'initially absent')
    check(rt.availability().get('prepare_required'), 'normal installer offers automatic preparation without a catalog')
    check(not root.exists(), 'checking availability does not prepare or install anything')
    rt.prepare_images()
    check(json.loads(catalog.read_text()).get('origin') == 'local-build', 'normal assistant prepares immutable local images without laboratory mode')
    # Core network, isolation, registry and Apache are the real installer functions.
    origin = 'http://repository.kei.test:8100'
    rt.plan(origin)
    check(not rt.state(), 'plan does not initialize platform data')
    try:
        rt.install(origin)
        check(rt.status()['status'] == 'installed', 'all services running')
        check(rt.diagnostic()['health'] == 'api-ui-dependencies', 'real API, SSR and seven cores')
        def public(path):
            return module.Request('http://127.0.0.1:8100' + path, headers={'Host': 'repository.kei.test:8100'})
        with module.HTTP.open(public('/server/api'), timeout=20) as response:
            api = json.load(response)
        check(api['_links']['communities']['href'].startswith(origin + '/server/'), 'public API canonical URL through Apache')
        with module.HTTP.open(public('/'), timeout=60) as response:
            page = response.read().decode()
        check('<ds-app' in page and 'DSpace' in page, 'public production interface through Apache')
        with module.HTTP.open(public('/server/api/core/communities'), timeout=20) as response:
            page = json.load(response)
        # HAL omits _embedded for an empty collection. Require its real
        # pagination metadata and canonical self link instead of inventing it.
        count = page.get('page', {}).get('totalElements')
        href = page.get('_links', {}).get('self', {}).get('href', '')
        check(count == 0 and href.startswith(origin + '/server/api/core/communities'),
              'anonymous empty community API: total=%r, self=%r' % (count, href))
        status_json = json.loads(module.command(['bash', str(REPO / 'installer'), '--status-json'], timeout=90))
        ds_status = next(p for p in status_json['platforms'] if p['id'] == 'dspace')
        check(ds_status['detected'] and ds_status['services'] == 'active', 'real shared status reports DSpace without requiring Koha')
        check((root / 'db-password').read_text().strip() not in json.dumps(status_json), 'shared dashboard status never contains the database password')
        from dspace_browser_test import exercise
        from dspace_recovery_test import prepare, verify
        prepared, fixture = exercise(rt, output, recovery_capture=prepare)
        verify(rt, prepared, fixture)
        # Simulate a disconnected client: its administrative container can live
        # on. Do not overlap a new install/start/stop with that still-running job.
        pending = rt.compose('run', '--rm', '--no-deps', '-d', '--entrypoint', 'sh', 'backend', '-c', 'sleep 60').strip()
        try:
            blocked = False
            try:
                rt.control(False)
            except module.Refused as error:
                blocked = 'still running' in str(error)
            check(blocked, 'unfinished administrative container blocks conflicting operation')
        finally:
            rt.docker('rm', '-f', pending)
        before = {name: module.digest(root / name) for name in ('db-password', 'local.cfg', 'compose.json')}
        schema = rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                            'SELECT installed_rank,version,checksum,success FROM schema_version ORDER BY installed_rank')
        persistent_files = [('backend', '/dspace/assetstore/nexus-lifecycle-test'),
                            ('solr', '/var/solr/nexus-lifecycle-test')]
        for service, path in persistent_files:
            rt.compose('exec', '-T', service, 'sh', '-ec', 'printf "%s" persistent-file > "$1"', 'nexus-ci', path)
        def check_files(label):
            for service, path in persistent_files:
                check(rt.compose('exec', '-T', service, 'cat', path) == 'persistent-file', label + ': ' + service)
        # A sentinel proves the database is kept; it is a lab-only table, not a fake repository item.
        rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-v', 'ON_ERROR_STOP=1',
                   '-c', 'CREATE TABLE nexus_lifecycle_test(value text); INSERT INTO nexus_lifecycle_test VALUES (\'persistent\');')
        rt.control(False)
        check(rt.status()['status'] == 'stopped', 'intentional stop distinguished from failure')
        # Replace containers as an update would. Stop/start alone would also
        # preserve an accidentally used writable container layer.
        rt.compose('up', '-d', '--pull', 'never', '--force-recreate', '--renew-anon-volumes', 'postgres', 'solr')
        rt.dependencies()
        rt.compose('rm', '-f', 'backend', 'ui')  # stopped containers only; no volume deletion
        rt.control(True)
        check('persistent' in rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                                         'SELECT value FROM nexus_lifecycle_test'), 'database persists across stop/start')
        check_files('files persist across container recreation')
        check(before == {name: module.digest(root / name) for name in before}, 'start neither rewrites secrets nor configuration')
        check(rt.state()['migration'] == 'done', 'start preserves completed migration marker')
        check(schema == rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                                    'SELECT installed_rank,version,checksum,success FROM schema_version ORDER BY installed_rank'),
              'normal restart does not change real Flyway history')
        # Force a mismatched receipt. The entrypoint must refuse BEFORE DSpace
        # loads its Context (which would itself try to migrate).
        rt.control(False)
        rt.compose('up', '-d', '--pull', 'never', 'postgres', 'solr')
        rt.dependencies()
        rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-v', 'ON_ERROR_STOP=1', '-c',
                   "UPDATE schema_version SET description=description||'-nexus-guard-test' "
                   "WHERE installed_rank=(SELECT MAX(installed_rank) FROM schema_version)")
        refused = False
        try:
            rt.compose('run', '--rm', '--no-deps', '-T', 'backend', timeout=120)
        except module.Refused:
            refused = True
        check(refused, 'schema mismatch prevents backend startup')
        check('nexus-guard-test' in rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                                              'SELECT description FROM schema_version ORDER BY installed_rank DESC LIMIT 1'),
              'refused startup leaves migration history untouched')
        rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-v', 'ON_ERROR_STOP=1', '-c',
                   "UPDATE schema_version SET description=regexp_replace(description,'-nexus-guard-test$','') "
                   "WHERE installed_rank=(SELECT MAX(installed_rank) FROM schema_version)")
        rt.control(True)
        # Restart Docker itself: not a VM reboot, and report it as such.
        module.command(['systemctl', 'restart', 'docker'], timeout=120)
        rt.dependencies()
        rt.health()
        check(rt.status()['status'] == 'installed', 'containers recover after Docker service restart')
        check('persistent' in rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                                         'SELECT value FROM nexus_lifecycle_test'), 'data persist after Docker restart')
        check_files('files persist after Docker service restart')
        from dspace_operations_test import exercise as operations_exercise
        operations_exercise(rt,prepared,output)
        # Reproduce the desktop recovery path using the real configuration,
        # containers and browser. Changing an unreachable LAN origin to local
        # access must preserve the installed image matrix, volumes and schema.
        from operations import Operations
        from dspace_browser_test import wait_for_client
        from playwright.sync_api import sync_playwright
        old_compose = json.loads((root / 'compose.json').read_text())
        database_password = module.digest(root / 'db-password')
        history_before = rt.compose('exec','-T','postgres','psql','-U','dspace','-d','dspace','-Atc',
                                    'SELECT installed_rank,version,checksum,success FROM schema_version ORDER BY installed_rank')
        repair = Operations(rt).dispatch('repair-web', {'local_only': True}, True)
        check(repair['url'] == 'http://localhost:8100', 'web repair selects a coherent localhost UI/API origin')
        new_compose = json.loads((root / 'compose.json').read_text())
        check(old_compose['volumes'] == new_compose['volumes'] and
              {k:v['image'] for k,v in old_compose['services'].items()} == {k:v['image'] for k,v in new_compose['services'].items()} and
              database_password == module.digest(root / 'db-password'), 'web repair preserves volumes, images and database credentials')
        check(history_before == rt.compose('exec','-T','postgres','psql','-U','dspace','-d','dspace','-Atc',
                                           'SELECT installed_rank,version,checksum,success FROM schema_version ORDER BY installed_rank'),
              'web repair does not migrate or change Flyway history')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto('http://localhost:8100/login', wait_until='domcontentloaded')
                wait_for_client(page)
                page.screenshot(path=str(output / 'dspace-local-repair-login.png'))
                page.locator('input[type=email]').fill(fixture['email'])
                page.locator('input[type=password]').fill(fixture['password'])
                with page.expect_response(lambda response: response.request.method == 'POST' and
                                          module.urlsplit(response.url).path == '/server/api/authn/login', timeout=60000) as login:
                    page.locator('[data-test=login-button]').click()
                check(login.value.status == 200, 'authentication API accepts the existing account after web repair')
                page.wait_for_url(lambda url: '/login' not in url and '/500' not in url, timeout=60000)
            except Exception:
                raise AssertionError('The real browser could not sign in after local web repair. Inspect the sanitized UI/API diagnostics.') from None
            finally:
                browser.close()
        check(True, 'real browser signs in after local web repair')
        backend_id = rt.compose('ps','-q','backend').strip()
        selected_languages = ['en','pt-BR','fr','ja']
        Operations(rt).dispatch('language-save', {'active':selected_languages,'fallback':'pt-BR'}, True)
        check(backend_id == rt.compose('ps','-q','backend').strip(), 'changing interface languages restarts only the interface')
        config = rt.http_json('/assets/config.json', rt.state()['ports']['ui'])
        check(config['fallbackLanguage']=='pt-BR' and
              {row['code'] for row in config['languages'] if row['active']} == set(selected_languages),
              'real browser configuration contains the selected languages and fallback')
        language_email='language-acceptance@example.org'; language_password=__import__('secrets').token_urlsafe(24)
        rt.admin('create',dict(email=language_email,first='Language',last='Acceptance',language='fr',password=language_password))
        from dspace_browser_test import API
        french=API(rt.state()['url']);french.login(language_email,language_password)
        person=french.request(french.request('/authn/status')['_links']['eperson']['href'])
        check(person['metadata']['eperson.language'][0]['value']=='fr', 'the real administrator helper saves the selected account language')
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            try:
                context=browser.new_context(locale='zz-ZZ');page=context.new_page()
                page.goto('http://localhost:8100/login',wait_until='domcontentloaded');wait_for_client(page)
                page.wait_for_function("document.documentElement.lang === 'pt-BR'")
                page.screenshot(path=str(output/'dspace-portuguese-login.png'))
                context.add_cookies([{'name':'dsLanguage','value':'fr','url':'http://localhost:8100'}])
                page.reload(wait_until='domcontentloaded');wait_for_client(page)
                page.wait_for_function("document.documentElement.lang === 'fr'")
            finally:
                browser.close()
        check(True, 'real browser uses the Portuguese fallback and a saved French preference')
        (output / 'dspace-acceptance.json').write_text(json.dumps(rt.diagnostic(), indent=2))
    except BaseException as error:
        # Only this disposable lab's generated credentials; never export raw inspect/config.
        password = (root / 'db-password').read_text().strip() if (root / 'db-password').exists() else ''
        primary = None
        if not isinstance(error, module.OperationFailed):
            message = str(error).lower()
            primary = ('backend' if 'api' in message else 'ui' if 'interface' in message else
                       'solr' if 'solr' in message else 'postgres' if 'postgresql' in message else None)
        if (root / 'last-error.log').exists():
            print('Sanitized disposable operation error:\n' + (root / 'last-error.log').read_text(), flush=True)
        for service in module.SERVICES:
            try:
                logs = rt.compose('logs', '--no-color', '--tail', '100', service)
                logs = module.redact(logs, password)
                print('Disposable CI logs: ' + service + '\n' + logs, flush=True)
                if service == primary:
                    excerpt = logs[-5000:].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
                    print('::error title=DSpace ' + service + ' startup::' + excerpt, flush=True)
            except module.Refused:
                pass
        raise
    finally:
        # This script requires an empty disposable machine; never expose cleanup as a user task.
        if (root / 'compose.json').exists():
            try:
                rt.compose('down', '--timeout', '90', timeout=420)  # never --volumes
            except module.Refused:
                pass
        for name in module.VOLUMES:
            try:
                obj = json.loads(rt.docker('volume', 'inspect', module.PROJECT + '-' + name))[0]
                if all((obj.get('Labels') or {}).get(k) == v for k, v in module.LABELS.items()):
                    rt.docker('volume', 'rm', module.PROJECT + '-' + name)
            except module.Refused:
                pass
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Public sanitized annotation makes the exact failing phase reviewable
        # without publishing raw root logs or relying on a maintainer's login.
        root = Path('/var/lib/koha-nexus/platforms/dspace')
        phase = module.read_json(root / 'state.json').get('phase', 'preflight') if (root / 'state.json').exists() else 'preflight'
        detail = 'phase=' + phase + ': ' + str(error)
        if isinstance(error, module.OperationFailed):
            detail += '\n' + error.output[-4500:]
        password = (root / 'db-password').read_text().strip() if (root / 'db-password').exists() else ''
        detail = module.redact(detail, password)
        detail = detail.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title=DSpace integrated acceptance::' + detail, flush=True)
        raise
