"""Exercise the bundled installer in an already isolated test container only."""
import json
import subprocess
import sys
import os
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

fixture = json.loads(Path(sys.argv[1]).read_text())
assert os.environ.get('NXEV_TEST_RUN') == 'disposable', 'Use a disposable test site only'
def wp(*args):
    return subprocess.run(['docker', 'exec', 'nexus-events-wp', 'php', '/tmp/wp-cli.phar', '--allow-root', *args], check=True, capture_output=True, text=True)

wp('plugin', 'deactivate', 'events-manager')
subprocess.run(['docker', 'exec', 'nexus-events-wp', 'mv', '/var/www/html/wp-content/plugins/events-manager', '/tmp/events-manager-original-' + uuid.uuid4().hex], check=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    context = browser.new_context()
    context.add_cookies([
        {'name': fixture['auth_cookie_name'], 'value': fixture['auth_cookie'], 'url': 'http://localhost:18791'},
        {'name': fixture['login_cookie_name'], 'value': fixture['login_cookie'], 'url': 'http://localhost:18791'},
    ])
    page = context.new_page()
    page.goto('http://localhost:18791/wp-admin/plugins.php')
    button = page.get_by_role('button', name='Preparar base gratuita: instalar se ausente e ativar Events Manager')
    assert button.count() == 1, 'explicit setup notice missing'
    nonce = page.locator('form:has(input[value="nxev_prepare"]) input[name="_wpnonce"]').input_value()
    with page.expect_navigation():
        button.click()
    assert page.get_by_role('heading', name='Nexus Eventos', exact=True).count() == 1, page.locator('body').inner_text()[:500]
    assert 'events-manager' in wp('plugin', 'list', '--status=active', '--field=name').stdout
    print('PASS: bundled dependency installed and activated only after nonce-bearing confirmation')
    # A second preparation must not replace a preexisting installation.
    subprocess.run(['docker', 'exec', 'nexus-events-wp', 'touch', '/var/www/html/wp-content/plugins/events-manager/nxev-test-preserve.txt'], check=True)
    response = context.request.post('http://localhost:18791/wp-admin/admin-post.php', form={'action': 'nxev_prepare', '_wpnonce': nonce})
    assert response.ok
    subprocess.run(['docker', 'exec', 'nexus-events-wp', 'test', '-f', '/var/www/html/wp-content/plugins/events-manager/nxev-test-preserve.txt'], check=True)
    print('PASS: repeated preparation preserves preexisting plugin files')
    browser.close()
print('DEPENDENCY: setup without preinstalled Events Manager passed')
