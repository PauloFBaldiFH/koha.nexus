#!/usr/bin/env python3
"""Experimental DSpace lifecycle adapter; Python 3.9+, no third-party modules.

The installer supplies the existing resource driver (network/proxy/registry).
No operation builds images, changes another platform, or deletes a data volume.
Production installation fails closed until an operator supplies the reviewed
immutable image catalog. Local image IDs require the explicit laboratory flag.
"""

import argparse
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

BASE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('KEI_DSPACE_DIR', '/var/lib/koha-nexus/platforms/dspace'))
PROJECT = 'kn-dspace'
LABELS = {'com.koha-nexus.managed': 'true', 'com.koha-nexus.platform': 'dspace'}
SERVICES = ('postgres', 'solr', 'backend', 'ui')
BACKEND_DIRS = ('assetstore', 'log', 'var', 'upload', 'reports', 'exports', 'imports', 'handle-server')
VOLUMES = ('postgres', 'solr', 'discovery-state') + BACKEND_DIRS
CORES = ('authority', 'oai', 'search', 'statistics', 'qaevent', 'suggestion', 'audit')
HTTP = build_opener(ProxyHandler({}))  # probes are local, never an environment proxy


class Refused(Exception):
    pass


class OperationFailed(Refused):
    def __init__(self, program, result):
        super().__init__('Operation failed (exit %s): %s. Private details: last-error.log.' %
                         (result.returncode, program))
        self.output = result.stdout + '\n' + result.stderr


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def redact(output, password=''):
    if password:
        output = output.replace(password, '[redacted]')
    output = re.sub(r'([a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^@\s/]+@', r'\1[redacted]@', output)
    return re.sub(r'(?im)^.*(?:password|secret|token|authorization).*$','[sensitive line omitted]', output)


def atomic(path, data, mode=0o600, gid=None):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), mode)
            if gid is not None:
                os.fchown(stream.fileno(), 0, gid)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def canonical_url(value):
    """One origin only: no credentials, paths, controls or Apache interpolation."""
    try:
        u = urlsplit(value)
        host = u.hostname or ''
        port = u.port if u.port is not None else (443 if u.scheme == 'https' else 80)
        if (u.scheme not in ('http', 'https') or u.username or u.password or
                u.query or u.fragment or u.path not in ('', '/') or
                not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}', host) or
                not 1 <= port <= 65535 or value != value.strip() or
                any(ord(c) < 33 for c in value)):
            raise ValueError()
        # IPv6 requires matching bind/proxy support; do not silently misconfigure it.
        if re.fullmatch(r'[0-9.]+', host):
            ipaddress.IPv4Address(host)
        elif any(not label or len(label) > 63 or label[0] == '-' or label[-1] == '-'
                 for label in host.split('.')):
            raise ValueError()
        if (host == 'localhost' or re.fullmatch(r'[0-9.]+', host)) and port in (80, 443):
            raise Refused('A local/IP address needs its own port, such as 8100; use a DNS name for 80/443 to preserve existing default sites.')
        suffix = '' if port == (443 if u.scheme == 'https' else 80) else ':' + str(port)
        return u.scheme + '://' + host + suffix
    except ValueError:
        raise Refused('Provide one HTTP(S) origin, without credentials, path or query (IPv4 or DNS).')


def free_port(port):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def command(args, timeout=60, input_text=None, env=None):
    """Never print subprocess output: it can include configuration/credentials."""
    try:
        result = subprocess.run([str(x) for x in args], input=input_text, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise Refused('Operation unavailable or timed out: ' + str(args[0]))
    if result.returncode:
        raise OperationFailed(str(args[0]), result)
    return result.stdout


def local_docker_env():
    """Keep Python and the existing Bash resource helpers on the same daemon."""
    env = dict(os.environ)
    for key in ('DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
        env.pop(key, None)
    env['DOCKER_HOST'] = 'unix:///var/run/docker.sock'
    return env


class Runtime:
    def __init__(self, root=ROOT, catalog=None, lab=False, driver=None, progress=None):
        self.root = Path(root).absolute()
        self.release = read_json(BASE / 'release.json')
        self.release_hash = digest(BASE / 'release.json')
        self.catalog_path = Path(catalog or '/etc/koha-nexus/dspace-images.json')
        self.lab = lab
        self.driver = driver
        self.progress = progress

    def docker(self, *args, timeout=60, input_text=None, log_failure=True):
        # Do not inherit an unrelated remote Docker context / DOCKER_HOST.
        try:
            return command(['docker', '--host=unix:///var/run/docker.sock', *args], timeout, input_text, env=local_docker_env())
        except OperationFailed as error:
            if log_failure:
                self.save_error(error)
            raise

    def save_error(self, error):
        # Read-only preflight/status do not create a log. Operational errors
        # are kept privately, with generated secrets and sensitive lines removed.
        if getattr(self, '_mutating', False):
            output = error.output
            password = self.root / 'db-password'
            output = redact(output, password.read_text().strip() if password.exists() else '')
            atomic(self.root / 'last-error.log', output[-32768:])

    def compose(self, *args, timeout=120):
        return self.docker('compose', '--project-name', PROJECT, '--project-directory', str(self.root),
                           '-f', str(self.root / 'compose.json'), *args, timeout=timeout)

    def core(self, action, *args):
        if not self.driver:
            raise Refused('The existing installer resource driver is required; use config.sh --task dspace.')
        env = dict(local_docker_env(), KEI_DSPACE_DIR=str(self.root))
        try:
            return command(['bash', self.driver, '--task', 'dspace-resource', action, *args], timeout=300, env=env)
        except OperationFailed as error:
            self.save_error(error)
            raise

    def state(self):
        if self.root.name != 'dspace' or self.root.is_symlink():
            raise Refused('Use a dedicated directory named dspace, not a system directory or symbolic link.')
        expected_uid = os.geteuid() if self.lab else 0
        if self.root.exists():
            info = self.root.stat()
            if info.st_uid != expected_uid or info.st_mode & 0o022:
                raise Refused('The platform directory has an untrusted owner or writable group/world permissions.')
        path = self.root / 'state.json'
        if path.is_symlink():
            raise Refused('The DSpace state file cannot be a symbolic link.')
        if path.exists():
            info = path.stat()
            if not path.is_file() or info.st_uid != expected_uid or info.st_mode & 0o022:
                raise Refused('The DSpace state file is not trusted; it was not adopted.')
            data = read_json(path)
            if not isinstance(data, dict) or not data:
                raise Refused('The existing DSpace state is invalid/incomplete; inspect it before resuming.')
            return data
        if self.root.exists() and any(self.root.iterdir()):
            raise Refused('The directory contains unregistered files without a DSpace journal; nothing was overwritten.')
        return {}

    def mark(self, **changes):
        state = self.state()
        state.update(changes)
        state['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        atomic(self.root / 'state.json', json.dumps(state, indent=2) + '\n')
        if changes.get('phase') and self.progress:
            self.progress(changes['phase'])

    @contextlib.contextmanager
    def lock(self):
        if os.geteuid() != 0:
            raise Refused('Run this operation locally as root.')
        self.state()  # validate the dedicated destination before mkdir/chmod
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_uid != 0:
            raise Refused('The DSpace directory must be owned by root and not a symbolic link.')
        self.root.chmod(0o700)
        # Same per-platform flock as _kei_bk_lock: future backup/restore must
        # serialize with install/start/stop, not introduce a second lock domain.
        owned = Path(os.environ.get('KEI_OWNED_DIR', '/var/lib/koha-nexus'))
        lock_dir = Path(os.environ.get('KEI_BK_DIR', str(owned / 'backup')))
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_info = lock_dir.stat()
        if lock_dir.is_symlink() or lock_info.st_uid != 0 or lock_info.st_mode & 0o022:
            raise Refused('The common backup lock directory must be private and owned by root.')
        lock_dir.chmod(0o700)
        fd = os.open(lock_dir / 'dspace.lock', os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022:
                raise Refused('The existing platform lock is not trusted; it was not changed.')
            os.fchmod(stream.fileno(), 0o600)
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('Another DSpace operation is running.')
            self._mutating = True
            try:
                yield
            finally:
                self._mutating = False

    def images(self):
        if not self.catalog_path.is_file():
            raise Refused('Reviewed DSpace images are not published/configured yet; no installation was started.')
        data = read_json(self.catalog_path)
        if data.get('schema') != 1 or data.get('release_sha256') != self.release_hash:
            raise Refused('The image catalog does not match this exact DSpace release lock.')
        images = data.get('images', {})
        if set(images) != {'backend', 'ui', 'solr'}:
            raise Refused('The catalog must contain exactly backend, ui and solr.')
        for name, ref in images.items():
            published = isinstance(ref, str) and re.fullmatch(
                r'ghcr\.io/paulofbaldifh/koha\.nexus/dspace-' + name + r'@sha256:[a-f0-9]{64}', ref)
            local = self.lab and isinstance(ref, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', ref)
            if not (published or local):
                raise Refused('An immutable reviewed image is required for ' + name)
        return dict(images, postgres=self.release['bases']['postgres'])

    def existing_resources(self):
        """Refuse collisions before any pull, network, file or database change."""
        names = self.docker('volume', 'ls', '--format', '{{.Name}}').splitlines()
        for name in VOLUMES:
            if PROJECT + '-' + name in names:
                obj = json.loads(self.docker('volume', 'inspect', PROJECT + '-' + name))[0]
                if not self.state().get('prepared') or any((obj.get('Labels') or {}).get(k) != v for k, v in LABELS.items()):
                    raise Refused('An existing data volume is not owned by this installation: ' + name)
        ids = self.docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT).split()
        if ids:
            for obj in json.loads(self.docker('inspect', *ids)):
                labels = obj['Config'].get('Labels') or {}
                if not self.state().get('prepared') or any(labels.get(k) != v for k, v in LABELS.items()):
                    raise Refused('The Compose project already belongs to another installation.')
                if str(labels.get('com.docker.compose.oneoff', '')).lower() == 'true' and obj['State'].get('Running'):
                    # A timed-out/disconnected docker CLI can leave its migration
                    # container alive. Never start another operation over it.
                    raise Refused('A DSpace administrative container is still running; inspect it before resuming.')

    def plan(self, url=None):
        old = self.state()
        url = canonical_url(url or old.get('url', ''))
        if old and (old.get('url') != url or old.get('release_sha256') != self.release_hash):
            raise Refused('Existing data/configuration requires a deliberate update or address change, not installation.')
        images = self.images()
        if platform.machine() not in ('x86_64', 'amd64'):
            raise Refused('Only linux/amd64 has been built and tested; ARM installation is not supported yet.')
        if not self.lab:
            os_release = Path('/etc/os-release').read_text()
            if not any(x in os_release for x in ('ID=debian', 'ID=ubuntu')):
                raise Refused('Only Debian/Ubuntu are supported by the existing installer.')
        info = json.loads(self.docker('info', '--format', '{{json .}}'))
        if info.get('OSType') != 'linux':
            raise Refused('A local Linux Docker engine is required.')
        if any('rootless' in x or 'userns' in x for x in info.get('SecurityOptions', [])):
            raise Refused('Rootless/user-remapped Docker has not been validated for these private mounts and isolation rules; nothing was installed.')
        self.docker('compose', 'version')
        self.existing_resources()
        ports = old.get('ports') or {'ui': 18100, 'backend': 18101}
        if urlsplit(url).port in ports.values():
            raise Refused('The public URL port collides with a reserved loopback port (18100/18101); choose a separate public port.')
        if not old.get('prepared') and any(not free_port(p) for p in ports.values()):
            raise Refused('A reserved loopback port is occupied (18100/18101); nothing was changed.')
        # Conservative engineering gate; explicitly not an upstream sizing guarantee.
        mem = {}
        if Path('/proc/meminfo').exists():
            mem = {x.split(':')[0]: int(x.split()[1]) * 1024 for x in Path('/proc/meminfo').read_text().splitlines()}
        if mem.get('MemAvailable', 0) < 4 * 1024**3:
            raise Refused('Less than 4 GiB of currently available host RAM; cannot reserve this laboratory profile safely.')
        parent = self.root
        while not parent.exists():
            parent = parent.parent
        if shutil.disk_usage(parent).free < 8 * 1024**3:
            raise Refused('Less than 8 GiB of free staging space; collection storage needs additional capacity.')
        proxy = self.core('plan', url).strip()
        return {'schema': 1, 'experimental': True, 'url': url, 'api': url + '/server',
                'images': images, 'release_sha256': self.release_hash, 'ports': ports,
                'project': PROJECT, 'volumes': [PROJECT + '-' + n for n in VOLUMES],
                'proxy': proxy, 'migration': old.get('migration', 'not-started'),
                'notes': ['No administrator is created in this PR.', 'No backup/restore adapter is available yet.',
                          'Mail and self-registration stay disabled until explicitly configured.',
                          'Memory budget: backend 2 GiB, Solr 1 GiB, UI 1.5 GiB, PostgreSQL 1 GiB.',
                          'A reboot test is distinct from restarting containers.']}

    def render(self, plan, password, gateway):
        u = urlsplit(plan['url'])
        # The existing network allocator owns /24s with gateway .1. Give only
        # the managed UI a stable proxy identity; never trust the whole subnet
        # or depend on resolving the public DNS name from inside the backend.
        ui_ip = str(ipaddress.IPv4Address(int(ipaddress.IPv4Address(gateway)) + 9))
        cfg = '\n'.join([
            '# Managed by Koha.Nexus: dspace. Private; never include in diagnostics.',
            'dspace.dir = /dspace', 'dspace.name = DSpace',
            'dspace.ui.url = ' + plan['url'], 'dspace.server.url = ' + plan['api'],
            'dspace.server.ssr.url = http://backend:8080/server',
            'db.url = jdbc:postgresql://postgres:5432/dspace', 'db.username = dspace',
            'db.password = ' + password, 'solr.server = http://solr:8983/solr',
            'proxies.trusted.ipranges = 127.0.0.1, ' + gateway + ', ' + ui_ip,
            'proxies.trusted.include_ui_ip = false',
            'rest.cors.allowed-origins = ' + plan['url'],
            'mail.server.disabled = true', 'user.registration = false', ''])
        services = {}
        for name in SERVICES:
            services[name] = {'image': plan['images'][name], 'restart': 'unless-stopped',
                              'labels': dict(LABELS), 'security_opt': ['no-new-privileges:true'],
                              'networks': ['platform'], 'stop_grace_period': '90s'}
        services['postgres'].update({
            'environment': {'POSTGRES_DB': 'dspace', 'POSTGRES_USER': 'dspace',
                            'POSTGRES_PASSWORD_FILE': '/run/secrets/db-password'},
            'volumes': ['postgres:/var/lib/postgresql/data',
                        {'type': 'bind', 'source': str(self.root / 'db-password'),
                         'target': '/run/secrets/db-password', 'read_only': True}],
            'mem_limit': '1g', 'shm_size': '256m',
            'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U dspace -d dspace'], 'interval': '10s', 'timeout': '5s', 'retries': 30}})
        services['solr'].update({'volumes': ['solr:/var/solr'], 'mem_limit': '1g',
                                'environment': {'SOLR_HEAP': '512m'}})
        config_mount = {'type': 'bind', 'source': str(self.root / 'local.cfg'),
                        'target': '/dspace/config/local.cfg', 'read_only': True}
        services['backend'].update({
            'volumes': [config_mount, 'discovery-state:/dspace/solr/search/conf'] + [n + ':/dspace/' + n for n in BACKEND_DIRS],
            'ports': ['127.0.0.1:%s:8080' % plan['ports']['backend']], 'mem_limit': '2g',
            'environment': {'JAVA_TOOL_OPTIONS': '-Xms256m -Xmx1408m -Dfile.encoding=UTF-8'},
            'depends_on': {'postgres': {'condition': 'service_healthy'}, 'solr': {'condition': 'service_started'}}})
        services['ui'].update({
            'networks': {'platform': {'ipv4_address': ui_ip}},
            'ports': ['127.0.0.1:%s:4000' % plan['ports']['ui']], 'mem_limit': '1536m',
            'environment': {'DSPACE_UI_BASEURL': plan['url'], 'DSPACE_UI_HOST': '0.0.0.0',
                            'DSPACE_UI_PORT': '4000', 'DSPACE_UI_SSL': 'false',
                            'DSPACE_REST_HOST': u.hostname, 'DSPACE_REST_PORT': str(u.port or (443 if u.scheme == 'https' else 80)),
                            'DSPACE_REST_SSL': str(u.scheme == 'https').lower(), 'DSPACE_REST_NAMESPACE': '/server',
                            'DSPACE_REST_SSRBASEURL': 'http://backend:8080/server',
                            'NODE_OPTIONS': '--max-old-space-size=1024'},
            'depends_on': {'backend': {'condition': 'service_started'}}})
        compose = {'name': PROJECT, 'services': services,
                   'networks': {'platform': {'name': PROJECT, 'external': True}},
                   'volumes': {n: {'name': PROJECT + '-' + n, 'external': True} for n in VOLUMES}}
        return cfg, compose

    def check_images(self, images):
        for name, ref in images.items():
            try:
                raw = self.docker('image', 'inspect', ref, log_failure=False)
            except OperationFailed as error:
                if ref.startswith('sha256:'):
                    self.save_error(error)
                    raise  # laboratory IDs are never resolved through a registry
                print('Downloading locked image: ' + name, flush=True)
                self.docker('pull', ref, timeout=1200)
                raw = self.docker('image', 'inspect', ref)
            # A cached immutable image is fully checked but does not need a
            # registry round trip when resuming an interrupted installation.
            obj = json.loads(raw)[0]
            if obj.get('Architecture') != 'amd64' or obj.get('Os') != 'linux':
                raise Refused('Image architecture mismatch: ' + name)
            if name != 'postgres':
                source = self.release['sources']['ui' if name == 'ui' else 'backend']
                labels = obj['Config'].get('Labels') or {}
                if labels.get('org.opencontainers.image.revision') != source['commit']:
                    raise Refused('Image source revision mismatch: ' + name)
                if labels.get('org.koha-nexus.dspace.release-lock') != self.release_hash:
                    raise Refused('Image recipe/release identity mismatch: ' + name)
                expected_user = {'backend': '10001:10001', 'ui': 'node', 'solr': '8983:8983'}[name]
                if obj['Config'].get('User') != expected_user:
                    raise Refused('Unexpected runtime user: ' + name)

    def wait(self, label, fn, seconds=300):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if fn():
                    return
            except (Refused, OSError, ValueError):
                pass
            time.sleep(3)
        raise Refused(label + ' did not become ready. Data were kept; inspect the diagnostic before resuming.')

    def dependencies(self):
        self.wait('PostgreSQL', lambda: self.compose('exec', '-T', 'postgres', 'pg_isready', '-U', 'dspace', '-d', 'dspace'))
        # A server replying is insufficient: require every real core to load successfully.
        def solr_ready():
            data = json.loads(self.compose('exec', '-T', 'solr', 'curl', '-fsS', '--max-time', '10',
                                           'http://127.0.0.1:8983/solr/admin/cores?action=STATUS&wt=json'))
            return not data.get('initFailures') and set(CORES) <= set(data.get('status', {}))
        self.wait('All seven Solr cores', solr_ready)

    def probe(self, path, port):
        origin = urlsplit(canonical_url(self.state()['url']))
        return Request('http://127.0.0.1:%s%s' % (port, path),
                       headers={'Accept': 'application/hal+json' if path.startswith('/server/api') else 'text/html',
                                'Host': origin.netloc, 'X-Forwarded-Proto': origin.scheme})

    def http_json(self, path, port):
        with HTTP.open(self.probe(path, port), timeout=15) as stream:
            return json.load(stream)

    def health(self):
        state = self.state()
        ports = state['ports']
        def api():
            doc = self.http_json('/server/api', ports['backend'])
            return (bool(doc.get('_links', {}).get('communities', {}).get('href')) and
                    doc.get('dspaceVersion', '').startswith('DSpace 10.1'))
        self.wait('DSpace REST API', api, 600)
        def ui():
            # The real canonical Host is essential for Angular's allowedHosts
            # SSR protection; a loopback Host would falsely fail a DNS install.
            with HTTP.open(self.probe('/', ports['ui']), timeout=30) as response:
                page = response.read(4 * 1024 * 1024).decode('utf8', errors='replace')
            return '<ds-app' in page and 'DSpace' in page
        self.wait('DSpace production interface', ui, 300)

    def install(self, url=None, retry_migration=False):
        # Preflight first: a missing catalog never creates even the platform directory.
        plan = self.plan(url)
        with self.lock():
            plan = self.plan(plan['url'])  # re-check after acquiring the operation lock
            state = self.state()
            if state.get('status') == 'installed':
                raise Refused('DSpace is already installed; use start or diagnosis, not reinstall.')
            if state.get('migration') in ('running', 'failed') and not retry_migration:
                raise Refused('A previous migration was interrupted/failed; review it, then explicitly use --retry-migration.')
            try:
                self.mark(status='installing', phase='images', url=plan['url'], ports=plan['ports'],
                          release_sha256=self.release_hash)
                self.check_images(plan['images'])
                self.mark(phase='network')
                self.core('network')
                net = json.loads(self.docker('network', 'inspect', PROJECT))[0]
                if any((net.get('Labels') or {}).get(k) != v for k, v in LABELS.items()):
                    raise Refused('The platform network is not owned by Koha.Nexus.')
                gateway = str(ipaddress.IPv4Address(net['IPAM']['Config'][0]['Gateway']))
                subnet = ipaddress.IPv4Network(net['IPAM']['Config'][0]['Subnet'])
                if subnet.prefixlen != 24 or ipaddress.IPv4Address(gateway) != subnet.network_address + 1:
                    raise Refused('The existing platform network has an unvalidated custom subnet/gateway; it was kept unchanged.')
                password_path = self.root / 'db-password'
                if state.get('prepared'):
                    # Do not silently rotate an existing database password or rewrite edited config.
                    for file, hash_value in state['files'].items():
                        if digest(self.root / file) != hash_value:
                            raise Refused('Private configuration was changed; installation will not overwrite it: ' + file)
                else:
                    # An incomplete preparation with no volumes can be safely retried using the same password.
                    password = password_path.read_text().strip() if password_path.exists() else secrets.token_hex(32)
                    if not re.fullmatch(r'[a-f0-9]{64}', password):
                        raise Refused('Unexpected password file; refusing to overwrite it.')
                    cfg, compose = self.render(plan, password, gateway)
                    atomic(password_path, password + '\n')
                    atomic(self.root / 'local.cfg', cfg, 0o640, 10001)
                    atomic(self.root / 'compose.json', json.dumps(compose, indent=2) + '\n')
                    self.mark(prepared=True, files={f: digest(self.root / f) for f in ('db-password', 'local.cfg', 'compose.json')})
                for name in VOLUMES:
                    v = PROJECT + '-' + name
                    self.docker('volume', 'create', '--label', 'com.koha-nexus.managed=true',
                                '--label', 'com.koha-nexus.platform=dspace', v)
                    obj = json.loads(self.docker('volume', 'inspect', v))[0]
                    if any((obj.get('Labels') or {}).get(k) != value for k, value in LABELS.items()):
                        raise Refused('A data volume collision occurred; it was not mounted or adopted: ' + v)
                    self.core('volume', v)
                self.mark(phase='dependencies')
                self.compose('up', '-d', '--pull', 'never', 'postgres', 'solr')
                self.dependencies()
                if self.state().get('migration') != 'done':
                    self.mark(phase='migration', migration='running')
                    try:
                        self.compose('run', '--rm', '--no-deps', '-T', 'backend', 'cli', 'database', 'migrate', timeout=1200)
                        self.compose('run', '--rm', '--no-deps', '-T', 'backend', 'schema-record', timeout=90)
                    except BaseException:
                        self.mark(migration='failed')
                        raise
                    self.mark(migration='done')
                self.mark(phase='application')
                self.compose('up', '-d', '--pull', 'never', 'backend', 'ui')
                self.health()
                self.core('audit')
                self.mark(phase='proxy')
                proxy_output = self.core('proxy').strip().splitlines()
                proxy = proxy_output[-1] if proxy_output else ''
                if proxy not in ('external', 'apache-configured'):
                    raise Refused('The proxy driver returned an unknown result; public access was not assumed.')
                publication = 'external-configuration-required' if proxy == 'external' else 'apache-configured'
                self.mark(status='installed', phase='ready', intended='running', proxy_status=publication)
                result = {'status': 'installed', 'url': plan['url'], 'experimental': True, 'proxy_status': publication}
                if proxy == 'external':
                    result['note'] = 'Configure the external proxy /server and / routes; the public address has not been verified. See docs/dspace/PR2-installer.md.'
                return result
            except BaseException:
                self.mark(status='failed')
                raise

    def control(self, start):
        state = self.state()
        if not state.get('prepared'):
            raise Refused('DSpace has not been prepared; use the installation procedure.')
        if start and (state.get('migration') != 'done' or state.get('phase') != 'ready'):
            raise Refused('Installation has not completed its migration; use the installation resume procedure.')
        with self.lock():
            self.existing_resources()
            for file, hash_value in self.state()['files'].items():
                if digest(self.root / file) != hash_value:
                    raise Refused('Private configuration was changed; review it before starting/stopping: ' + file)
            if start:
                self.mark(status='starting', intended='running')
                self.core('network')  # reapply isolation before starting any service
                self.compose('up', '-d', '--pull', 'never', 'postgres', 'solr')
                self.dependencies()
                self.compose('up', '-d', '--pull', 'never', 'backend', 'ui')
                try:
                    self.health()
                    self.core('audit')
                except BaseException:
                    self.mark(status='degraded', intended='running')
                    raise
                self.mark(status='installed', intended='running')
            else:
                # Graceful reverse order, keep all containers, volumes, configuration and proxy.
                self.compose('stop', '--timeout', '90', 'ui', 'backend', 'solr', 'postgres', timeout=420)
                self.mark(status='stopped', intended='stopped')
            return self.status()

    def status(self):
        state = self.state()
        if not state:
            return {'schema': 1, 'platform': 'dspace', 'status': 'absent', 'experimental': True}
        result = {k: state.get(k) for k in ('status', 'phase', 'url', 'migration', 'intended', 'updated_at', 'proxy_status')}
        result.update(schema=1, platform='dspace', experimental=True, health='not-checked')
        result['public_access'] = 'not-checked'
        try:
            ids = self.docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT).split()
            observed = {}
            if ids:
                for obj in json.loads(self.docker('inspect', *ids)):
                    label = obj['Config'].get('Labels') or {}
                    if all(label.get(k) == v for k, v in LABELS.items()) and label.get('com.docker.compose.oneoff') != 'True':
                        observed[label.get('com.docker.compose.service')] = obj['State']['Status']
            result['services'] = {s: observed.get(s, 'missing') for s in SERVICES}
            if (not all(x == 'running' for x in result['services'].values()) and
                    state.get('status') not in ('failed', 'installing')):
                result['status'] = 'stopped' if state.get('intended') == 'stopped' else 'degraded'
        except Refused:
            result['status'] = 'unavailable'
            result['reason'] = 'Local Docker is unavailable; no restoration is implied.'
        return result

    def diagnostic(self):
        result = self.status()
        if result.get('status') == 'installed':
            try:
                self.dependencies()
                self.health()
                self.core('audit')
                result['health'] = 'api-ui-dependencies'
            except Refused as error:
                result['health'] = 'failed'
                result['reason'] = str(error)
        # Never output docker inspect/config, command output, local.cfg, password or environment.
        return result

    def proxy_config(self):
        state = self.state()
        u = urlsplit(canonical_url(state['url']))
        port = u.port or (443 if u.scheme == 'https' else 80)
        if u.scheme != 'http':
            raise Refused('HTTPS must terminate at a configured external proxy in this experimental stage.')
        listen = '' if port == 80 else 'Listen %s\n' % port
        return (listen + '<VirtualHost *:%s>\n' % port +
                '  ServerName %s\n  ProxyRequests Off\n  ProxyPreserveHost On\n' % u.hostname +
                '  RequestHeader unset Forwarded\n  RequestHeader unset X-Forwarded-For\n' +
                '  RequestHeader unset X-Forwarded-Host\n  RequestHeader unset X-Forwarded-Port\n' +
                '  RequestHeader set X-Forwarded-Proto "http"\n' +
                '  ProxyPass /server http://127.0.0.1:%s/server timeout=300\n' % int(state['ports']['backend']) +
                '  ProxyPassReverse /server http://127.0.0.1:%s/server\n' % int(state['ports']['backend']) +
                '  ProxyPass / http://127.0.0.1:%s/ timeout=300\n' % int(state['ports']['ui']) +
                '  ProxyPassReverse / http://127.0.0.1:%s/\n' % int(state['ports']['ui']) +
                '  <LocationMatch "^/server/(actuator|config)(/|$)">\n    Require all denied\n  </LocationMatch>\n' +
                '</VirtualHost>\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--lab', action='store_true', help='Explicit engineering-only local immutable image IDs')
    parser.add_argument('--driver', help='Existing config.sh/installer resource driver')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('plan', 'install'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--url')
        if name == 'install':
            cmd.add_argument('--confirm', action='store_true')
            cmd.add_argument('--retry-migration', action='store_true')
    for name in ('start', 'stop'):
        sub.add_parser(name).add_argument('--confirm', action='store_true')
    for name in ('status', 'diagnose', 'proxy-config'):
        sub.add_parser(name)
    args = parser.parse_args()
    runtime = Runtime(args.root, args.catalog, args.lab, args.driver,
                      progress=lambda phase: print('DSpace: ' + phase, file=sys.stderr, flush=True))
    def interrupted(signum, _frame):
        raise Refused('Interrupted; data were preserved. Review the saved phase before resuming.')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        if args.command in ('install', 'start', 'stop') and not args.confirm:
            raise Refused('Explicit --confirm is required after reviewing the plan.')
        if args.command == 'plan':
            result = runtime.plan(args.url)
        elif args.command == 'install':
            result = runtime.install(args.url, args.retry_migration)
        elif args.command in ('start', 'stop'):
            result = runtime.control(args.command == 'start')
        elif args.command == 'proxy-config':
            print(runtime.proxy_config(), end='')
            return 0
        elif args.command == 'diagnose':
            result = runtime.diagnostic()
        else:
            result = runtime.status()
        print(json.dumps(result, indent=2))
        return 0
    except (Refused, OSError, ValueError, KeyError, KeyboardInterrupt) as error:
        # ValueErrors can include input; inputs never contain credentials on this CLI.
        print('DSpace: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
