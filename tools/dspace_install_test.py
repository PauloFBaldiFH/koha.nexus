#!/usr/bin/env python3
"""Real isolated DSpace lifecycle acceptance, only on a DISPOSABLE root runner.

Requires the three built images and the existing installer resource driver.
No mocks; PostgreSQL, seven Solr cores, backend and SSR all run together.
The --disposable flag authorizes removal ONLY of this test's labelled resources.
"""
import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dspace_runtime', REPO / 'platforms/dspace/runtime.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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
    catalog = output / 'dspace-test-images.json'
    catalog.write_text(subprocess.check_output([sys.executable, str(REPO / 'tools/dspace_catalog.py')], text=True))
    rt = module.Runtime(root, catalog, lab=True, driver=str(REPO / 'installer'))
    def check(cond, message):
        if not cond:
            raise AssertionError(message)
        print('PASS: ' + message, flush=True)
    check(not root.exists(), 'initially absent')
    # Core network, isolation, registry and Apache are the real installer functions.
    rt.plan('http://127.0.0.1:8100')
    check(not root.exists(), 'plan has no persistent platform changes')
    try:
        rt.install('http://127.0.0.1:8100')
        check(rt.status()['status'] == 'installed', 'all services running')
        check(rt.diagnostic()['health'] == 'api-ui-dependencies', 'real API, SSR and seven cores')
        with module.HTTP.open('http://127.0.0.1:8100/server/api', timeout=20) as response:
            api = json.load(response)
        check(api['_links']['core.communities']['href'].startswith('http://127.0.0.1:8100/server/'), 'public API canonical URL through Apache')
        with module.HTTP.open('http://127.0.0.1:8100/', timeout=60) as response:
            page = response.read().decode()
        check('<ds-app' in page and 'DSpace' in page, 'public production interface through Apache')
        with module.HTTP.open('http://127.0.0.1:8100/server/api/core/communities', timeout=20) as response:
            check('_embedded' in json.load(response), 'anonymous real community API')
        before = {name: module.digest(root / name) for name in ('db-password', 'local.cfg', 'compose.json')}
        # A sentinel proves the database is kept; it is a lab-only table, not a fake repository item.
        rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-v', 'ON_ERROR_STOP=1',
                   '-c', 'CREATE TABLE nexus_lifecycle_test(value text); INSERT INTO nexus_lifecycle_test VALUES (\'persistent\');')
        rt.control(False)
        check(rt.status()['status'] == 'stopped', 'intentional stop distinguished from failure')
        rt.control(True)
        check('persistent' in rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                                         'SELECT value FROM nexus_lifecycle_test'), 'database persists across stop/start')
        check(before == {name: module.digest(root / name) for name in before}, 'start neither rewrites secrets nor configuration')
        check(rt.state()['migration'] == 'done', 'start preserves completed migration marker')
        # Restart Docker itself: not a VM reboot, and report it as such.
        module.command(['systemctl', 'restart', 'docker'], timeout=120)
        rt.dependencies()
        rt.health()
        check(rt.status()['status'] == 'installed', 'containers recover after Docker service restart')
        check('persistent' in rt.compose('exec', '-T', 'postgres', 'psql', '-U', 'dspace', '-d', 'dspace', '-Atc',
                                         'SELECT value FROM nexus_lifecycle_test'), 'data persist after Docker restart')
        (output / 'dspace-acceptance.json').write_text(json.dumps(rt.diagnostic(), indent=2))
    except BaseException:
        # Only this disposable lab's generated credentials; never export raw inspect/config.
        password = (root / 'db-password').read_text().strip() if (root / 'db-password').exists() else ''
        if (root / 'last-error.log').exists():
            print('Sanitized disposable operation error:\n' + (root / 'last-error.log').read_text(), flush=True)
        for service in module.SERVICES:
            try:
                logs = rt.compose('logs', '--no-color', '--tail', '100', service)
                if password:
                    logs = logs.replace(password, '[redacted]')
                logs = re.sub(r'(?im)^.*(?:password|secret|token).*$','[sensitive log line omitted]', logs)
                print('Disposable CI logs: ' + service + '\n' + logs, flush=True)
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
    sys.exit(main())
