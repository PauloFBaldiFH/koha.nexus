"""DSpace format-1 encrypted recovery packages. No archived code is executed."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time


class Error(Exception):
    pass


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def entries(root):
    """No links, sockets or devices. Fail instead of silently omitting data."""
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise Error('A data tree contains a link or special file; capture refused.')
            if stat.S_ISREG(info.st_mode):
                result[path.relative_to(root).as_posix()] = {'bytes': info.st_size, 'sha256': sha(path)}
    return result


def extract(archive, dest, budget):
    """Validate the entire archive before writing anything, including duplicates."""
    seen = set(); total = 0
    with tarfile.open(archive, 'r:') as source:
        members = []
        for member in source:
            members.append(member)
            if len(members) > 1000000: raise Error('Too many archive entries.')
        for member in members:
            p = PurePosixPath(member.name)
            if (member.name in seen or not p.parts or not member.name or p.is_absolute() or
                    '..' in p.parts or '\\' in member.name or str(p) != member.name or
                    not (member.isfile() or member.isdir())):
                raise Error('Unsafe or ambiguous archive entry.')
            if len(p.parts) > 80: raise Error('Archive path is too deep.')
            seen.add(member.name); total += member.size
            if total > budget: raise Error('Archive exceeds available recovery space.')
        for member in members:
            target = dest / member.name
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.chmod(member.mode & 0o777)
                if os.geteuid() == 0: os.chown(target, member.uid, member.gid)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with source.extractfile(member) as src, open(target, 'xb') as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
                target.chmod(member.mode & 0o777)
                if os.geteuid() == 0: os.chown(target, member.uid, member.gid)
        return total


class Recovery:
    def __init__(self, rt, phrase=None):
        self.rt = rt
        self.phrase = phrase
        self.home = Path(os.environ.get('KEI_DSPACE_BACKUPS', '/var/backups/koha-nexus/dspace'))
        self.journal = rt.root / 'backup-operation.json'

    def record(self, **data):
        from runtime import atomic
        atomic(self.journal, json.dumps(data) + '\n')

    def crypto(self, operation, source=None, target=None):
        from runtime import command, local_docker_env
        if not self.rt.driver: raise Error('The existing backup key service is required.')
        env = local_docker_env()
        if self.phrase is not None: env['KEI_BACKUP_PHRASE'] = self.phrase
        return command(['bash', self.rt.driver, '--task', 'dspace-backup-crypto', operation,
                        *([str(source), str(target)] if source is not None else [])],
                       timeout=21600, env=env)

    def checked(self):
        state = self.rt.state()
        if state.get('phase') != 'ready' or state.get('migration') != 'done':
            raise Error('DSpace must have completed installation before recovery operations.')
        if state.get('release_sha256') != self.rt.release_hash:
            raise Error('Backup requires the same reviewed release.')
        for name, value in state['files'].items():
            if sha(self.rt.root / name) != value: raise Error('Private configuration changed; review it first.')
        self.rt.existing_resources()
        return state, json.loads((self.rt.root / 'compose.json').read_text())

    def volumes(self, compose):
        from runtime import LABELS
        result = {}
        for key, value in compose['volumes'].items():
            name = value['name']
            obj = json.loads(self.rt.docker('volume', 'inspect', name))[0]
            if any((obj.get('Labels') or {}).get(k) != v for k, v in LABELS.items()):
                raise Error('A volume is not owned by DSpace.')
            path = Path(obj['Mountpoint'])
            if not path.is_absolute() or path.is_symlink() or not path.is_dir():
                raise Error('Local volume storage is unavailable.')
            result[key] = path
        return result

    def running(self):
        raw = self.rt.compose('ps', '--format', 'json', '--all')
        try: rows = json.loads(raw or '[]'); rows = rows if isinstance(rows, list) else [rows]
        except ValueError: rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return [r['Service'] for r in rows if r.get('State') == 'running']

    def binary(self, args, path, write):
        from runtime import local_docker_env
        with open(path, 'wb' if write else 'rb') as stream:
            result = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', *args],
                stdin=subprocess.DEVNULL if write else stream,
                stdout=stream if write else subprocess.DEVNULL, stderr=subprocess.PIPE,
                env=local_docker_env(), timeout=7200)
        if result.returncode: raise Error('PostgreSQL dump/restore failed; private output was not exported.')

    def dc_args(self, root, project):
        return ['compose', '--project-name', project, '--project-directory', str(root), '-f', str(root / 'compose.json')]

    def resume(self, running):
        if running:
            self.rt.compose('start', *running, timeout=420)
            if set(running) == {'postgres', 'solr', 'backend', 'ui'}:
                self.rt.dependencies(); self.rt.health()
        self.record(phase='writes-resumed', services=running)

    def recover_capture(self):
        if self.journal.exists():
            data = json.loads(self.journal.read_text())
            if data.get('phase') == 'capture': self.resume(data['services'])
            elif data.get('phase') not in ('writes-resumed', 'complete'):
                raise Error('Interrupted restoration: inspect the recovery journal before continuing.')

    def capture(self):
        from runtime import atomic
        self.crypto('check')  # no data copied or stopped without an encryption key
        state, compose = self.checked()
        paths = self.volumes(compose)
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.home.is_symlink() or self.home.stat().st_mode & 0o077:
            raise Error('Backup directory must be private, without symbolic links.')
        size = sum(sum(x['bytes'] for x in entries(path).values()) for path in paths.values())
        if shutil.disk_usage(self.home).free < size * 3 + 256 * 1024**2:
            raise Error('Insufficient staging space; reserve three times the uncompressed data.')
        running = self.running()
        if 'postgres' not in running: raise Error('PostgreSQL must be running for a logical backup.')
        name = 'knx-dspace-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(4)
        destination = self.home / (name + '.tar.gpg')
        with tempfile.TemporaryDirectory(prefix='.capture-', dir=self.home) as temporary:
            work = Path(temporary); tree = work / 'data'; tree.mkdir(mode=0o700)
            self.record(phase='capture', services=running, package=str(destination))
            start = time.time()
            try:
                self.rt.compose('stop', '--timeout', '90', 'ui', 'backend', 'solr', timeout=420)
                cid = self.rt.compose('ps', '-q', 'postgres').strip()
                self.binary(['exec', cid, 'pg_dump', '-U', 'dspace', '-d', 'dspace', '-Fc'], tree / 'database.dump', True)
                logical = work / 'logical.sql'
                self.binary(['exec',cid,'pg_dump','-U','dspace','-d','dspace','--data-only','--inserts'], logical, True)
                (tree / 'database-data.sha256').write_text(normalized_dump(logical) + '\n')
                logical.unlink()
                self.rt.compose('stop', '--timeout', '90', 'postgres', timeout=180)
                for key, path in paths.items():
                    if key != 'postgres':
                        from runtime import command
                        target = tree / 'volumes' / key; target.parent.mkdir(exist_ok=True)
                        command(['cp','-a','--',str(path),str(target)], timeout=14400)
                private = tree / 'private'; private.mkdir(mode=0o700)
                for name in ('local.cfg', 'db-password', 'state.json'):
                    shutil.copyfile(self.rt.root / name, private / name)
                manifest = dict(format=1, platform='dspace', complete=True, created=time.time(),
                    release_sha256=self.rt.release_hash, images={k:v['image'] for k,v in compose['services'].items()},
                    url=state['url'], files=entries(tree), volumes=sorted(k for k in paths if k != 'postgres'),
                    cores=['authority','oai','search','statistics','qaevent','suggestion','audit'])
            finally:
                self.resume(running)  # failure propagates; never claim successful resumption
            manifest['window_seconds'] = round(time.time() - start, 3)
            atomic(tree / 'manifest.json', json.dumps(manifest, sort_keys=True))
            archive = work / 'capture.tar'
            with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as out:
                for path in sorted(tree.rglob('*')):
                    out.add(path, arcname=path.relative_to(tree).as_posix(), recursive=False)
            partial = destination.with_suffix('.part')
            try:
                self.crypto('encrypt', archive, partial)
                os.replace(partial, destination); destination.chmod(0o600)
                atomic(destination.with_suffix('.sha256'), sha(destination) + '\n')
            finally:
                partial.unlink(missing_ok=True)
        self.record(phase='complete', package=str(destination))
        return {'package':str(destination), 'encrypted':True, 'window_seconds':manifest['window_seconds']}

    @contextlib.contextmanager
    def opened(self, package):
        package = Path(package).absolute()
        if package.is_symlink() or not package.is_file(): raise Error('Choose a regular encrypted package.')
        checksum = package.with_suffix('.sha256')
        if checksum.exists() and (checksum.is_symlink() or not checksum.is_file() or checksum.read_text().strip() != sha(package)):
            raise Error('Encrypted package checksum mismatch.')
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.recovery-', dir=self.home) as temporary:
            stage = Path(temporary); archive = stage / 'data.tar'; tree = stage / 'data'
            self.crypto('decrypt', package, archive)
            tree.mkdir(mode=0o700)
            extract(archive, tree, shutil.disk_usage(stage).free // 2)
            manifest = json.loads((tree / 'manifest.json').read_text())
            if (manifest.get('format') != 1 or manifest.get('platform') != 'dspace' or
                    manifest.get('complete') is not True or manifest.get('release_sha256') != self.rt.release_hash):
                raise Error('Unknown format or incompatible DSpace release.')
            actual = entries(tree); actual.pop('manifest.json', None)
            if actual != manifest.get('files'): raise Error('Recovery file inventory does not match.')
            from runtime import VOLUMES
            if manifest.get('volumes') != sorted(v for v in VOLUMES if v != 'postgres'):
                raise Error('Missing persistent volume in package.')
            with open(tree / 'database.dump', 'rb') as stream: signature = stream.read(5)
            if signature != b'PGDMP':
                raise Error('The package does not contain a PostgreSQL custom dump.')
            yield tree, manifest

    @contextlib.contextmanager
    def clone(self, tree, manifest):
        """Empty independent volumes, internal network, no host ports or proxy."""
        from runtime import LABELS, atomic
        _, original = self.checked()
        if manifest['images'] != {k:v['image'] for k,v in original['services'].items()}:
            raise Error('Recovery requires the exact installed image matrix.')
        project = 'kn-dspace-rt-' + secrets.token_hex(10)
        area = tree.parent / 'runtime'; area.mkdir(mode=0o700)
        cfg = (tree / 'private/local.cfg').read_text()
        cfg += '\nmail.server.disabled = true\nuser.registration = false\ndb.url = jdbc:postgresql://127.0.0.1:5432/dspace\nsolr.server = http://127.0.0.1:8983/solr\n'
        atomic(area / 'local.cfg', cfg, 0o640, gid=10001)
        atomic(area / 'db-password', (tree / 'private/db-password').read_text(), 0o644)
        # Ancestors must permit the container's nonroot backend to reach bind mounts.
        # The daemon mounts files by inode; no host directory traversal is exposed.
        compose = copy.deepcopy(original); compose['name'] = project
        compose.pop('networks', None)
        for key in compose['volumes']:
            compose['volumes'][key] = {'name':project + '-' + key, 'external':True}
        for key, service in compose['services'].items():
            service.pop('ports', None); service['restart'] = 'no'
            service.pop('networks', None)
            service['network_mode'] = 'none' if key == 'postgres' else 'service:postgres'
            for volume in service.get('volumes', []):
                if isinstance(volume, dict) and volume.get('type') == 'bind':
                    filename = Path(volume['source']).name
                    if filename not in ('local.cfg', 'db-password'): raise Error('Unknown bind mount.')
                    volume['source'] = str(area / filename)
        atomic(area / 'compose.json', json.dumps(compose))
        args = self.dc_args(area, project)
        owned = []; promoted = {'value':False}
        def dc(*parts, timeout=420): return self.rt.docker(*args, *parts, timeout=timeout, log_failure=False)
        try:
            for key in compose['volumes']:
                name = project + '-' + key
                self.rt.docker('volume', 'create', '--label', 'com.koha-nexus.managed=true',
                    '--label', 'com.koha-nexus.platform=dspace', '--label', 'com.koha-nexus.recovery=' + project, name)
                owned.append(name)
                if key != 'postgres':
                    obj = json.loads(self.rt.docker('volume', 'inspect', name))[0]
                    dest = Path(obj['Mountpoint'])
                    # Preserve UID/GID and all bytes from the already validated tree.
                    self.rt.docker('run', '--rm', '--network', 'none', '--user', '0:0',
                        '--security-opt', 'no-new-privileges', '--label','com.koha-nexus.platform=dspace', '--entrypoint', 'cp',
                        '--mount', 'type=bind,src=' + str(tree / 'volumes' / key) + ',dst=/source,readonly',
                        '--mount', 'type=volume,src=' + name + ',dst=/target',
                        manifest['images']['backend'], '-a', '/source/.', '/target/', timeout=3600)
            for key in manifest['volumes']:
                obj = json.loads(self.rt.docker('volume','inspect',project + '-' + key))[0]
                actual = entries(Path(obj['Mountpoint']))
                expected = entries(tree / 'volumes' / key)
                if actual != expected: raise Error('Restored file/Solr data mismatch: ' + key)
            dc('up', '-d', '--pull', 'never', 'postgres', 'solr')
            self.rt.wait('Recovery PostgreSQL', lambda: dc('exec','-T','postgres','pg_isready','-U','dspace','-d','dspace'))
            self.binary([*args, 'exec', '-T', 'postgres', 'pg_restore', '-U', 'dspace', '-d', 'dspace',
                         '--exit-on-error', '--no-owner'], tree / 'database.dump', False)
            # Compare all logical PostgreSQL data, including UUIDs, policies and handles.
            after = tree.parent / 'logical-after.sql'
            self.binary([*args, 'exec', '-T', 'postgres', 'pg_dump', '-U','dspace','-d','dspace', '--data-only', '--inserts'], after, True)
            # A deterministic source data fingerprint was saved while writes were stopped.
            if normalized_dump(after) != (tree / 'database-data.sha256').read_text().strip():
                raise Error('Restored database records differ from the captured database.')
            # Run only the schema/admin check, never a persistent REST worker in
            # the isolated verification copy.
            dc('run','--rm','--no-deps','-T','backend','admin','status', timeout=240)
            cores = json.loads(dc('exec','-T','solr','curl','-fsS','--max-time','10',
                'http://127.0.0.1:8983/solr/admin/cores?action=STATUS&wt=json'))
            if cores.get('initFailures') or not set(manifest['cores']) <= set(cores.get('status',{})):
                raise Error('Not all restored Solr cores loaded.')
            yield dict(area=area, project=project, compose=compose, manifest=manifest, promoted=promoted)
        finally:
            dc('down', '--timeout','90')
            for name in owned:
                obj = json.loads(self.rt.docker('volume','inspect',name))[0]
                labels = obj.get('Labels') or {}
                if not promoted['value'] and labels.get('com.koha-nexus.recovery') == project:
                    self.rt.docker('volume','rm',name)

    def test(self, package):
        self.checked()
        with self.opened(package) as (tree, manifest):
            with self.clone(tree, manifest):
                return {'verified':True, 'database':'all logical records', 'files':'all checksums',
                        'solr':'all cold cores', 'network':'none; shared loopback only', 'public_ports':False}

    def restore(self, package):
        from runtime import atomic, digest
        state, original = self.checked()
        with self.opened(package) as (tree, manifest):
            if manifest['url'] != state['url']:
                raise Error('Cross-address restore requires a separate migration; current address was preserved.')
            safety = self.capture()
            with self.opened(safety['package']):
                pass  # Verify that the safety copy can actually be decrypted before promotion.
            with self.clone(tree, manifest) as clone:
                # Persist rollback material outside temporary decrypted staging.
                rollback = self.rt.root / 'recovery-rollback'
                if rollback.exists(): raise Error('An earlier rollback directory requires review.')
                rollback.mkdir(mode=0o700)
                names = ('local.cfg','db-password','compose.json','state.json')
                for name in names: shutil.copy2(self.rt.root / name, rollback / name)
                running = self.running()
                self.record(phase='promoting', services=running, safety=safety['package'])
                self.rt.mark(phase='restoring')
                self.rt.compose('stop','--timeout','90', timeout=420)
                promoted = copy.deepcopy(original)
                promoted['volumes'] = clone['compose']['volumes']
                try:
                    # Stop the verification project before any production mounts.
                    self.rt.docker(*self.dc_args(clone['area'], clone['project']), 'down','--timeout','90', timeout=420)
                    atomic(self.rt.root / 'local.cfg', (tree / 'private/local.cfg').read_text(), 0o640, gid=10001)
                    atomic(self.rt.root / 'db-password', (tree / 'private/db-password').read_text(), 0o644)
                    atomic(self.rt.root / 'compose.json', json.dumps(promoted))
                    self.rt.compose('up','-d','--pull','never','--force-recreate', timeout=420)
                    self.rt.dependencies(); self.rt.health(); self.rt.core('audit')
                    self.rt.mark(phase='ready', status='installed', intended='running',
                        files={n:digest(self.rt.root / n) for n in state['files']})
                    for volume in promoted['volumes'].values(): self.rt.core('recovered-volume',volume['name'])
                    clone['promoted']['value'] = True
                    self.record(phase='complete', safety=safety['package'], restored=str(package))
                except BaseException:
                    self.rollback()
                    raise
                finally:
                    if self.rt.state().get('phase') == 'ready': shutil.rmtree(rollback)
                return {'restored':True, 'safety_backup':safety['package'], 'old_volumes_preserved':True}

    def rollback(self):
        from runtime import atomic
        if not self.journal.exists(): raise Error('No interrupted recovery journal.')
        data = json.loads(self.journal.read_text())
        if data.get('phase') != 'promoting': raise Error('No interrupted promotion to roll back.')
        rollback = self.rt.root / 'recovery-rollback'
        names = ('local.cfg','db-password','compose.json','state.json')
        if not all((rollback / n).is_file() and not (rollback / n).is_symlink() for n in names):
            raise Error('Rollback configuration is incomplete; all data volumes were preserved.')
        self.rt.compose('stop','--timeout','90',timeout=420)
        for name in names:
            atomic(self.rt.root / name, (rollback / name).read_text(),
                0o640 if name == 'local.cfg' else 0o644 if name == 'db-password' else 0o600,
                gid=10001 if name == 'local.cfg' else None)
        if data['services']:
            self.rt.compose('up','-d','--pull','never','--force-recreate',*data['services'],timeout=420)
            if set(data['services']) == {'postgres','solr','backend','ui'}:
                self.rt.dependencies(); self.rt.health()
        self.record(phase='complete', rollback=True)
        return {'rolled_back':True, 'data_volumes_preserved':True}


def normalized_dump(path):
    """Ignore pg_dump comments/session boilerplate; compare actual SQL data."""
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for line in stream:
            if line.startswith((b'--', b'\\restrict ', b'\\unrestrict ')) or not line.strip(): continue
            h.update(line)
    return h.hexdigest()
