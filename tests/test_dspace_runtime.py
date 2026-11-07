"""Lifecycle failure tests with explicit doubles; real services run in CI separately."""
import contextlib
import hashlib
import io
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime', REPO / 'platforms/dspace/runtime.py')
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)


class LabRuntime(ds.Runtime):
    """In-memory Docker/core double, deliberately not presented as system validation."""
    def __init__(self, root, catalog):
        super().__init__(root, catalog, lab=True, driver='/test/installer')
        self.calls = []
        self.volumes = {}
        self.failure = None
        self.running = False

    @contextlib.contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        yield

    def core(self, action, *args):
        self.calls.append(('core', action, *args))
        if action == self.failure:
            raise ds.Refused('Injected failure: ' + action)
        if action == 'proxy':
            return 'apache-configured'
        return 'apache-nexus'

    def docker(self, *args, **kwargs):
        self.calls.append(('docker', *args))
        if args[:2] == ('volume', 'ls'):
            return '\n'.join(self.volumes)
        if args[:2] == ('volume', 'inspect'):
            return json.dumps([self.volumes[args[2]]])
        if args[:2] == ('volume', 'create'):
            self.volumes[args[-1]] = {'Labels': dict(ds.LABELS)}
        if args[0] == 'ps':
            return ''
        if args[:2] == ('network', 'inspect'):
            return json.dumps([{'Labels': dict(ds.LABELS), 'IPAM': {'Config': [{'Gateway': '172.30.10.1', 'Subnet': '172.30.10.0/24'}]}}])
        return ''

    def plan(self, url=None):
        old = self.state()
        url = ds.canonical_url(url or old.get('url', ''))
        if old and (old['url'] != url or old['release_sha256'] != self.release_hash):
            raise ds.Refused('Existing configuration')
        self.existing_resources()
        return {'url': url, 'api': url + '/server', 'ports': {'ui': 18100, 'backend': 18101}, 'images': self.images()}

    def check_images(self, images):
        self.calls.append(('images',))
        if self.failure == 'images':
            raise ds.Refused('Injected image failure')

    def compose(self, *args, **kwargs):
        self.calls.append(('compose', *args))
        if args[0] == 'run' and self.failure == 'migration':
            raise ds.Refused('Injected migration failure')
        if args[0] == 'up':
            self.running = True
        if args[0] == 'stop':
            self.running = False
        return 'ready'

    def dependencies(self):
        if self.failure == 'dependencies':
            raise ds.Refused('Dependencies are not ready')

    def health(self):
        if self.failure == 'health':
            raise ds.Refused('API not ready')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'dspace'
        self.catalog = Path(self.tmp.name) / 'images.json'
        self.catalog.write_text(json.dumps({'schema': 1, 'release_sha256': ds.digest(ds.BASE / 'release.json'),
                                           'images': {n: 'sha256:' + str(i) * 64 for i, n in enumerate(('backend', 'ui', 'solr'), 1)}}))
        self.rt = LabRuntime(self.root, self.catalog)
        original = ds.atomic
        # Unit tests do not require root; ownership is checked by real CI installation.
        self.atomic = patch.object(ds, 'atomic', side_effect=lambda p, d, mode=0o600, gid=None: original(p, d, mode))
        self.atomic.start()
        self.addCleanup(self.atomic.stop)

    def install(self):
        return self.rt.install('http://192.168.1.20:8100')

    def test_origin_validation_rejects_injection_and_credentials(self):
        for value in ('http://user:secret@x.org', 'http://x.org/path', 'http://x.org?secret=x', 'http://x.org/#x',
                      'http://x.org\nListen 25', 'http://[::1]:8100', 'http://bad..org', 'http://999.999.0.1',
                      'http://x.org:0', 'http://x.org:65536', 'ftp://x.org'):
            with self.subTest(value=value), self.assertRaises(ds.Refused):
                ds.canonical_url(value)
        self.assertEqual(ds.canonical_url('http://192.168.1.20:8100/'), 'http://192.168.1.20:8100')

    def test_local_addresses_do_not_take_over_existing_default_sites(self):
        for value in ('http://192.168.1.20', 'http://127.0.0.1:80', 'http://localhost', 'https://192.168.1.20'):
            with self.subTest(value=value), self.assertRaisesRegex(ds.Refused, 'own port'):
                ds.canonical_url(value)

    def test_public_port_cannot_conflict_with_private_listeners(self):
        rt = ds.Runtime(self.root, self.catalog, lab=True)
        for port in (18100, 18101):
            with patch.object(rt, 'docker', side_effect=lambda *a, **kw: json.dumps({'OSType': 'linux'}) if a[0] == 'info' else ''), \
                    patch.object(ds.platform, 'machine', return_value='x86_64'), \
                    self.assertRaisesRegex(ds.Refused, 'loopback port'):
                rt.plan('http://192.168.1.20:' + str(port))

    def test_missing_catalog_refuses_without_writes(self):
        self.catalog.unlink()
        with self.assertRaises(ds.Refused):
            self.install()
        self.assertFalse(self.root.exists())

    def test_unregistered_existing_configuration_is_never_overwritten(self):
        self.root.mkdir()
        file = self.root / 'local.cfg'
        file.write_text('existing institutional configuration\n')
        with self.assertRaisesRegex(ds.Refused, 'unregistered'):
            self.install()
        self.assertEqual(file.read_text(), 'existing institutional configuration\n')
        self.assertFalse((self.root / 'state.json').exists())
        self.assertEqual(self.rt.calls, [])

    def test_system_directories_cannot_be_used_as_platform_root(self):
        for root in ('/', '/etc', '/var/lib/koha-nexus'):
            with self.subTest(root=root), self.assertRaisesRegex(ds.Refused, 'dedicated'):
                ds.Runtime(root, self.catalog, lab=True).state()

    def test_group_writable_state_directory_is_not_promoted_to_trusted(self):
        self.root.mkdir()
        self.root.chmod(0o777)
        with self.assertRaisesRegex(ds.Refused, 'untrusted owner'):
            self.install()
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o777)
        self.assertFalse((self.root / 'state.json').exists())

    def test_catalog_rejects_floating_tags_even_in_lab(self):
        doc = json.loads(self.catalog.read_text())
        doc['images']['ui'] = 'nexus-dspace-ui:latest'
        self.catalog.write_text(json.dumps(doc))
        with self.assertRaises(ds.Refused):
            self.rt.images()

    def test_catalog_is_bound_to_release_and_rejects_extra_components(self):
        doc = json.loads(self.catalog.read_text())
        for update in ({'release_sha256': 'a' * 64}, {'images': dict(doc['images'], other='sha256:' + '1' * 64)}):
            self.catalog.write_text(json.dumps(dict(doc, **update)))
            with self.assertRaises(ds.Refused):
                self.rt.images()

    def test_local_image_ids_require_explicit_lab(self):
        with self.assertRaises(ds.Refused):
            ds.Runtime(self.root, self.catalog).images()
        self.assertEqual(set(self.rt.images()), {'postgres', 'solr', 'backend', 'ui'})

    def test_collision_does_not_adopt_even_labelled_foreign_volume(self):
        self.rt.volumes['kn-dspace-postgres'] = {'Labels': dict(ds.LABELS)}
        with self.assertRaises(ds.Refused):
            self.install()
        self.assertFalse(self.root.exists())

    def test_compose_keeps_database_and_solr_private_and_password_out(self):
        plan = self.rt.plan('https://repository.example.org')
        cfg, compose = self.rt.render(plan, 'private-test-secret', '172.30.10.1')
        self.assertNotIn('private-test-secret', json.dumps(compose))
        self.assertIn('private-test-secret', cfg)
        self.assertIn('dspace.server.ssr.url = http://backend:8080/server', cfg)
        for name in ds.SERVICES:
            svc = compose['services'][name]
            self.assertIn('no-new-privileges:true', svc['security_opt'])
            self.assertIn('platform', svc['networks'])
            for port in svc.get('ports', []):
                self.assertTrue(port.startswith('127.0.0.1:'))
        self.assertNotIn('ports', compose['services']['postgres'])
        self.assertNotIn('ports', compose['services']['solr'])
        self.assertTrue(compose['networks']['platform']['external'])
        self.assertEqual(compose['services']['ui']['environment']['DSPACE_REST_SSL'], 'true')
        self.assertEqual(compose['services']['ui']['networks']['platform']['ipv4_address'], '172.30.10.10')
        self.assertIn('proxies.trusted.include_ui_ip = false', cfg)
        self.assertIn('proxies.trusted.ipranges = 127.0.0.1, 172.30.10.1, 172.30.10.10', cfg)

    def test_completed_install_uses_migration_once_and_keeps_secret_private(self):
        self.assertEqual(self.install()['status'], 'installed')
        self.assertEqual(self.rt.state()['migration'], 'done')
        self.assertEqual((self.root / 'db-password').stat().st_mode & 0o777, 0o600)
        self.assertNotIn((self.root / 'db-password').read_text().strip(), json.dumps(self.rt.status()))
        self.assertEqual(sum(x[:2] == ('compose', 'run') and 'migrate' in x for x in self.rt.calls), 1)

    def test_failure_preserves_volumes_and_records_phase(self):
        self.rt.failure = 'health'
        with self.assertRaises(ds.Refused):
            self.install()
        self.assertEqual(self.rt.state()['phase'], 'application')
        self.assertEqual(self.rt.state()['status'], 'failed')
        self.assertEqual(len(self.rt.volumes), len(ds.VOLUMES))
        self.assertFalse(any('rm' in x or 'down' in x for x in self.rt.calls))

    def test_resume_after_health_failure_never_repeats_migration_or_changes_password(self):
        self.rt.failure = 'health'
        with self.assertRaises(ds.Refused):
            self.install()
        secret = (self.root / 'db-password').read_bytes()
        self.rt.failure = None
        self.install()
        self.assertEqual(secret, (self.root / 'db-password').read_bytes())
        self.assertEqual(sum(x[:2] == ('compose', 'run') and 'migrate' in x for x in self.rt.calls), 1)

    def test_interrupted_migration_requires_deliberate_retry(self):
        self.rt.failure = 'migration'
        with self.assertRaises(ds.Refused):
            self.install()
        self.assertEqual(self.rt.state()['migration'], 'failed')
        self.rt.failure = None
        with self.assertRaisesRegex(ds.Refused, 'retry-migration'):
            self.install()
        self.rt.install(retry_migration=True)
        self.assertEqual(self.rt.state()['migration'], 'done')

    def test_user_edited_configuration_is_not_overwritten(self):
        self.rt.failure = 'health'
        with self.assertRaises(ds.Refused):
            self.install()
        path = self.root / 'local.cfg'
        path.write_text(path.read_text() + '# edited\n')
        self.rt.failure = None
        with self.assertRaisesRegex(ds.Refused, 'changed'):
            self.install()
        self.assertTrue(path.read_text().endswith('# edited\n'))

    def test_install_cannot_retarget_existing_repository(self):
        self.install()
        with self.assertRaises(ds.Refused):
            self.rt.install('http://other.example.org')

    def test_stop_start_has_no_migration_or_volume_removal(self):
        self.install()
        hashes = {p.name: ds.digest(p) for p in self.root.iterdir() if p.name != 'state.json'}
        self.rt.calls.clear()
        self.rt.control(False)
        self.assertEqual(self.rt.state()['intended'], 'stopped')
        self.rt.control(True)
        self.assertFalse(any(x[:2] == ('compose', 'run') for x in self.rt.calls))
        self.assertEqual(hashes, {name: ds.digest(self.root / name) for name in hashes})
        self.assertEqual(self.rt.state()['intended'], 'running')

    def test_start_on_absent_or_unmigrated_repository_refuses(self):
        with self.assertRaises(ds.Refused):
            self.rt.control(True)
        self.assertFalse(self.root.exists())

    def test_start_cannot_bypass_failed_install_proxy(self):
        self.rt.failure = 'proxy'
        with self.assertRaises(ds.Refused):
            self.install()
        self.rt.failure = None
        with self.assertRaisesRegex(ds.Refused, 'resume'):
            self.rt.control(True)

    def test_failed_migration_can_be_stopped_without_erasing_data(self):
        self.rt.failure = 'migration'
        with self.assertRaises(ds.Refused):
            self.install()
        self.rt.control(False)
        self.assertEqual(self.rt.state()['intended'], 'stopped')
        self.assertEqual(len(self.rt.volumes), len(ds.VOLUMES))

    def test_private_failure_log_redacts_credentials_and_is_not_in_status(self):
        import subprocess
        self.install()
        rt = ds.Runtime(self.root, self.catalog, lab=True)
        rt._mutating = True
        password = (self.root / 'db-password').read_text().strip()
        failed = ds.OperationFailed('docker', subprocess.CompletedProcess([], 1, 'Safe detail\n' + password, 'password=other\nhttp://operator:credvalue@proxy.example.org\n'))
        with patch.object(ds, 'command', side_effect=failed), self.assertRaises(ds.Refused):
            rt.docker('compose', 'run')
        log = (self.root / 'last-error.log').read_text()
        self.assertIn('Safe detail', log)
        self.assertNotIn(password, log)
        self.assertNotIn('password=other', log)
        self.assertNotIn('credvalue', log)
        self.assertEqual((self.root / 'last-error.log').stat().st_mode & 0o777, 0o600)
        with patch.object(rt, 'docker', side_effect=ds.Refused('offline')):
            self.assertNotIn('Safe detail', json.dumps(rt.status()))

    def test_health_uses_canonical_host_for_angular_ssrf_protection(self):
        self.install()
        rt = ds.Runtime(self.root, self.catalog, lab=True)
        rt.mark(url='https://repository.example.org')
        requests = []
        def response(request, **kwargs):
            requests.append(request)
            body = b'<ds-app>DSpace</ds-app>' if request.full_url.endswith('/') else json.dumps(
                {'dspaceVersion': 'DSpace 10.1', '_links': {'communities': {'href': 'http://backend:8080/server/api/core/communities'}}}).encode()
            return io.BytesIO(body)
        # RootRestResourceControllerIT in the pinned upstream checks _links.communities.
        # A stale/invented contract must fail immediately, not poll for ten minutes.
        with patch.object(ds.HTTP, 'open', side_effect=response), \
                patch.object(ds.time, 'sleep', side_effect=AssertionError('Known upstream Root contract was rejected')):
            rt.health()
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].get_header('Accept'), 'application/hal+json')
        self.assertTrue(all(r.get_header('Host') == 'repository.example.org' for r in requests))
        self.assertTrue(all(r.get_header('X-forwarded-proto') == 'https' for r in requests))
        self.assertTrue(all(r.full_url.startswith('http://127.0.0.1:') for r in requests))

    def test_disconnected_running_migration_blocks_another_operation(self):
        self.install()
        labels = dict(ds.LABELS, **{'com.docker.compose.oneoff': 'True'})
        def docker(*args, **kwargs):
            if args[0] == 'ps':
                return 'unfinished-migration'
            if args[0] == 'inspect':
                return json.dumps([{'Config': {'Labels': labels}, 'State': {'Running': True}}])
            return ''
        with patch.object(self.rt, 'docker', side_effect=docker), self.assertRaisesRegex(ds.Refused, 'still running'):
            self.rt.control(False)

    def test_proxy_api_rule_precedes_interface_and_operational_paths_are_denied(self):
        self.install()
        config = self.rt.proxy_config()
        self.assertLess(config.index('ProxyPass /server '), config.index('ProxyPass / '))
        self.assertIn('Require all denied', config)
        self.assertIn('Listen 8100', config)

    def test_absent_status_neither_contacts_docker_nor_creates_files(self):
        self.assertEqual(self.rt.status()['status'], 'absent')
        self.assertEqual(self.rt.calls, [])
        self.assertFalse(self.root.exists())

    def test_real_preflight_is_read_only_with_mocked_host_resources(self):
        rt = ds.Runtime(self.root, self.catalog, lab=True)
        with patch.object(rt, 'docker', side_effect=lambda *a, **kw: json.dumps({'OSType': 'linux'}) if a[0] == 'info' else ''), \
                patch.object(rt, 'core', return_value='apache-nexus'), \
                patch.object(ds.platform, 'machine', return_value='x86_64'), \
                patch.object(ds, 'free_port', return_value=True), \
                patch.object(ds.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 100 * 1024**3})()):
            result = rt.plan('http://192.168.1.20:8100')
        self.assertEqual(result['project'], 'kn-dspace')
        self.assertFalse(self.root.exists())

    def test_python_and_bash_resources_use_local_daemon_without_changing_caller(self):
        rt = ds.Runtime(self.root, self.catalog, lab=True, driver='/test/installer')
        remote = {'DOCKER_HOST': 'tcp://remote.example:2376', 'DOCKER_CONTEXT': 'remote',
                  'DOCKER_TLS': '1', 'DOCKER_TLS_VERIFY': '1', 'DOCKER_CERT_PATH': '/remote/certs'}
        with patch.dict(os.environ, remote), patch.object(ds, 'command', return_value='') as run:
            rt.docker('info')
            rt.core('plan')
            self.assertEqual(len(run.call_args_list), 2)
            for call in run.call_args_list:
                env = call.kwargs['env']
                self.assertEqual(env['DOCKER_HOST'], 'unix:///var/run/docker.sock')
                for key in remote:
                    if key != 'DOCKER_HOST':
                        self.assertNotIn(key, env)
            self.assertEqual({key: os.environ[key] for key in remote}, remote)

    def test_unvalidated_user_namespace_or_rootless_engine_is_refused(self):
        rt = ds.Runtime(self.root, self.catalog, lab=True)
        for option in ('name=rootless', 'name=userns'):
            with patch.object(rt, 'docker', return_value=json.dumps({'OSType': 'linux', 'SecurityOptions': [option]})), \
                    patch.object(ds.platform, 'machine', return_value='x86_64'), \
                    self.assertRaisesRegex(ds.Refused, 'Rootless'):
                rt.plan('http://192.168.1.20:8100')
        self.assertFalse(self.root.exists())

    def test_cached_immutable_images_can_resume_without_registry_access(self):
        rt = ds.Runtime(self.root, self.catalog, lab=True)
        obj = {'Architecture': 'amd64', 'Os': 'linux', 'Config': {'User': '10001:10001', 'Labels': {
            'org.opencontainers.image.revision': rt.release['sources']['backend']['commit'],
            'org.koha-nexus.dspace.release-lock': rt.release_hash}}}
        def docker(*args, **kwargs):
            self.assertEqual(args[:2], ('image', 'inspect'), 'No pull/network access with an already cached digest')
            return json.dumps([obj])
        with patch.object(rt, 'docker', side_effect=docker):
            rt.check_images({'backend': 'ghcr.io/paulofbaldifh/koha.nexus/dspace-backend@sha256:' + '1'*64})

    def test_external_proxy_stays_explicitly_pending(self):
        original = self.rt.core
        with patch.object(self.rt, 'core', side_effect=lambda action, *a: 'external' if action == 'proxy' else original(action, *a)):
            result = self.install()
        self.assertEqual(result['proxy_status'], 'external-configuration-required')
        self.assertIn('Configure the external proxy', result['note'])
        self.assertEqual(self.rt.status()['public_access'], 'not-checked')

    def test_installer_adapter_hashes_match_and_task_is_present(self):
        text = (REPO / 'installer').read_text()
        for var, file in (('RUNTIME', 'runtime.py'), ('RELEASE', 'release.json')):
            self.assertIn('KEI_DSPACE_' + var + '_SHA="' + ds.digest(ds.BASE / file) + '"', text)
        self.assertIn('dspace) kei_dspace_runtime "$@"', text)

    def bridge_script(self, tail):
        text = (REPO / 'installer').read_text()
        section = text[text.index('# DSPACE: experimental lifecycle'):text.index('# TAINACAN (WordPress')]
        fragment = Path(self.tmp.name) / 'bridge.sh'
        fragment.write_text(section)
        env = dict(os.environ, KEI_DSPACE_ADAPTER_DIR=str(Path(self.tmp.name) / 'adapter'),
                   KEI_DSPACE_DIR=str(self.root), _SCRIPT_DIR=str(REPO), _SCRIPT_PATH=str(REPO / 'installer'))
        return subprocess.run(['bash', '-c', 'source "$1"; python3() { echo adapter-loaded; }; '
                               'id() { echo 0; }; curl() { return 88; }; ' + tail,
                               'bridge-test', str(fragment)], env=env, text=True, capture_output=True)

    def test_installed_adapter_works_offline_without_checkout(self):
        result = self.bridge_script('kei_dspace_runtime install --confirm || exit; '
                                    '_SCRIPT_DIR=/missing-checkout; kei_dspace_runtime status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('adapter-loaded'), 2)

    def test_tampered_offline_adapter_never_executes(self):
        result = self.bridge_script('kei_dspace_runtime install --confirm || exit; '
                                    '_SCRIPT_DIR=/missing-checkout; '
                                    'file="$KEI_DSPACE_ADAPTER_DIR/$KEI_DSPACE_RUNTIME_SHA-$KEI_DSPACE_RELEASE_SHA/runtime.py"; '
                                    'chmod 600 "$file"; echo tampered > "$file"; kei_dspace_runtime status')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count('adapter-loaded'), 1)

    def test_atomic_write_replaces_and_has_no_leftover_temp_file(self):
        p = Path(self.tmp.name) / 'state.json'
        ds.atomic(p, '{"phase":"one"}')
        ds.atomic(p, '{"phase":"two"}')
        self.assertEqual(json.loads(p.read_text())['phase'], 'two')
        self.assertFalse(list(p.parent.glob('.state.json-*')))


if __name__ == '__main__':
    unittest.main()
