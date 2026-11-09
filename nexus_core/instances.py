"""Private instance identity and explicit legacy adoption (standard library only).

Discovery and reads never create files or contact an application. Adoption records
references to an existing installation; it neither moves data nor grants ownership
of resources. Drivers must still verify ownership immediately before a mutation.
This registry does not by itself make the existing singleton drivers multi-instance.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from dataclasses import dataclass, field, replace
from typing import Iterator, Mapping
from urllib.parse import urlsplit
from uuid import UUID, uuid4

DEFAULT_REGISTRY = Path('/var/lib/koha-nexus/instances')
SCHEMA = 1
DRIVERS = {'koha': 'koha-native', 'tainacan': 'tainacan-docker', 'dspace': 'dspace-docker'}
MAX_RECORD = 128 * 1024
SITE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z')


class RegistryError(ValueError):
    """No trustworthy, unambiguous target is available; nothing was changed."""


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise RegistryError('Provide a name of 1 to 120 printable characters.')
    return value.strip()


def _identifier(value: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise RegistryError('Select an explicit, valid instance ID.') from None
    return value


def _mapping(value: object, *, paths: bool = False) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 64:
        raise RegistryError('Invalid instance references.')
    for key, item in value.items():
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', key):
            raise RegistryError('Invalid instance reference name.')
        if not isinstance(item, str) or len(item) > 4096 or any(ord(c) < 32 for c in item):
            raise RegistryError('Invalid instance reference value.')
        if paths and (not Path(item).is_absolute() or '..' in Path(item).parts):
            raise RegistryError('Instance paths must be absolute and cannot traverse directories.')
    return dict(value)


def _url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
            return ''
        _ = parsed.port
    except ValueError:
        return ''
    return value.rstrip('/')


@dataclass(frozen=True)
class LegacyCandidate:
    """A discovered installation, not yet a managed or healthy application."""
    source_key: str
    application: str
    driver: str
    name: str
    paths: Mapping[str, str] = field(default_factory=dict)
    resources: Mapping[str, str] = field(default_factory=dict)
    endpoints: Mapping[str, str] = field(default_factory=dict)
    observed_status: str = 'unknown'
    problem: str = ''


@dataclass(frozen=True)
class InstanceContext:
    id: str
    name: str
    application: str
    driver: str
    source_key: str
    paths: Mapping[str, str]
    resources: Mapping[str, str]
    endpoints: Mapping[str, str]
    lifecycle: str = 'adopted'
    observed_status: str = 'unknown'
    health: str = 'not-checked'
    created_at: int = 0
    updated_at: int = 0
    schema: int = SCHEMA

    def as_dict(self) -> dict:
        return dict(schema=self.schema, id=self.id, name=self.name, application=self.application,
                    driver=self.driver, source_key=self.source_key, paths=dict(self.paths),
                    resources=dict(self.resources), endpoints=dict(self.endpoints), lifecycle=self.lifecycle,
                    observed_status=self.observed_status, health=self.health,
                    created_at=self.created_at, updated_at=self.updated_at)

    @classmethod
    def from_dict(cls, data: object) -> 'InstanceContext':
        if not isinstance(data, dict) or type(data.get('schema')) is not int or data.get('schema') != SCHEMA:
            raise RegistryError('Unsupported instance record schema.')
        app = data.get('application')
        if app not in DRIVERS or data.get('driver') != DRIVERS[app]:
            raise RegistryError('Unsupported application or driver.')
        source = data.get('source_key')
        if not isinstance(source, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9:_-]{0,127}', source):
            raise RegistryError('Invalid legacy source identity.')
        endpoints = _mapping(data.get('endpoints', {}))
        if any(not _url(value) or _url(value) != value for value in endpoints.values()):
            raise RegistryError('Invalid instance endpoint.')
        lifecycle = data.get('lifecycle', 'adopted')
        if lifecycle not in ('adopted', 'data-kept', 'removed'):
            raise RegistryError('Invalid instance lifecycle.')
        observed = data.get('observed_status', 'unknown')
        if not isinstance(observed, str) or not re.fullmatch(r'[a-z-]{1,48}', observed):
            raise RegistryError('Invalid observed state.')
        timestamps = [data.get(k, 0) for k in ('created_at', 'updated_at')]
        if any(type(x) is not int or x < 0 for x in timestamps):
            raise RegistryError('Invalid instance timestamps.')
        if data.get('health', 'not-checked') != 'not-checked':
            raise RegistryError('A registry record cannot assert application health.')
        return cls(_identifier(data.get('id')), _name(data.get('name')), app, data['driver'], source,
                   _mapping(data.get('paths', {}), paths=True), _mapping(data.get('resources', {})),
                   endpoints, lifecycle, observed, 'not-checked', *timestamps)


class Registry:
    """One private atomic JSON file per ID, with a Linux writer lock.

    expected_uid defaults to the process owner. A privileged installer therefore
    rejects files supplied by an unprivileged user. The directory is not created
    merely by constructing or reading this object.
    """
    def __init__(self, root: Path = DEFAULT_REGISTRY, *, expected_uid: int | None = None):
        self.root = Path(root).absolute()
        self.expected_uid = os.geteuid() if expected_uid is None else expected_uid

    def _directory(self, create: bool = False) -> bool:
        if self.root.resolve() != self.root:
            raise RegistryError('The instance registry cannot use symbolic links.')
        # The visible root owner can be remapped in a user namespace. It is
        # still the owner of trusted system ancestors in that namespace.
        system_owner = Path('/').stat().st_uid
        for parent in self.root.parents:
            if not parent.exists():
                continue
            info = parent.stat()
            sticky_system_directory = info.st_uid == system_owner and bool(info.st_mode & stat.S_ISVTX)
            if info.st_uid not in (system_owner, self.expected_uid) or (info.st_mode & 0o022 and not sticky_system_directory):
                raise RegistryError('The registry has an untrusted writable parent directory.')
        if not self.root.exists():
            if not create:
                return False
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != self.expected_uid or info.st_mode & 0o077:
            raise RegistryError('The instance registry requires a private directory owned by its operator.')
        return True

    def _trusted_fd(self, path: Path, flags: int) -> int:
        try:
            fd = os.open(path, flags | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except OSError as error:
            raise RegistryError('Cannot open a trusted instance record: ' + path.name) from error
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != self.expected_uid or info.st_mode & 0o077 or info.st_nlink != 1:
            os.close(fd)
            raise RegistryError('Instance files must be private regular files owned by their operator.')
        return fd

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        import fcntl  # Writers run on the Linux host; read-only discovery is portable.
        self._directory(create=True)
        fd = self._trusted_fd(self.root / '.lock', os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def get(self, instance_id: str) -> InstanceContext:
        ident = _identifier(instance_id)
        if not self._directory():
            raise RegistryError('The selected instance is not registered.')
        fd = self._trusted_fd(self.root / (ident + '.json'), os.O_RDONLY)
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            raw = stream.read(MAX_RECORD + 1)
        if len(raw) > MAX_RECORD:
            raise RegistryError('The instance record exceeds the supported size.')
        try:
            record = InstanceContext.from_dict(json.loads(raw))
        except (ValueError, TypeError, KeyError) as error:
            raise RegistryError('Invalid instance record: ' + ident) from error
        if record.id != ident:
            raise RegistryError('The instance ID does not match its record filename.')
        return record

    def list(self) -> list[InstanceContext]:
        if not self._directory():
            return []
        rows = [self.get(path.stem) for path in sorted(self.root.glob('*.json'))]
        sources = [row.source_key for row in rows]
        if len(set(sources)) != len(sources):
            raise RegistryError('Two records claim the same legacy installation; reconcile the registry.')
        return sorted(rows, key=lambda row: (row.name.casefold(), row.id))

    def resolve(self, instance_id: str, *, application: str | None = None) -> InstanceContext:
        record = self.get(instance_id)
        if application is not None and record.application != application:
            raise RegistryError('The selected instance belongs to a different application.')
        if record.lifecycle == 'removed':
            raise RegistryError('The selected instance was removed; choose a recovery destination explicitly.')
        return record

    def _write(self, record: InstanceContext) -> None:
        # Validate through the same contract as readers before creating the temp file.
        record = InstanceContext.from_dict(record.as_dict())
        fd, temp = tempfile.mkstemp(prefix='.instance-', dir=self.root)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(record.as_dict(), stream, ensure_ascii=False, sort_keys=True)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, self.root / (record.id + '.json'))
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def adopt(self, candidate: LegacyCandidate, *, name: str | None = None) -> InstanceContext:
        """Explicitly record a discovered installation. Repeating adoption is idempotent.

        Resource references are inventory only, not authority to delete them.
        A conflicting path/driver for the same source must be reconciled instead
        of overwriting an existing registry entry.
        """
        proposed = InstanceContext.from_dict(InstanceContext(
            str(uuid4()), name if name is not None else candidate.name,
            candidate.application, candidate.driver, candidate.source_key,
            dict(candidate.paths), dict(candidate.resources), dict(candidate.endpoints),
            observed_status=candidate.observed_status,
            created_at=int(time.time()), updated_at=int(time.time())).as_dict())
        if not proposed.paths or any(not Path(value).exists() or Path(value).resolve() != Path(value) for value in proposed.paths.values()):
            raise RegistryError('The installation references are missing or use symbolic links; discover it again.')
        with self._locked():
            for existing in self.list():
                if existing.source_key == proposed.source_key:
                    if (existing.application, existing.driver, existing.paths, existing.resources) != (
                            proposed.application, proposed.driver, proposed.paths, proposed.resources):
                        raise RegistryError('This legacy installation is already registered with different references.')
                    return existing
            self._write(proposed)
        return proposed

    def rename(self, instance_id: str, name: str) -> InstanceContext:
        name = _name(name)
        with self._locked():
            existing = self.get(instance_id)
            record = replace(existing, name=name, updated_at=int(time.time()))
            self._write(record)
        return record

    def mark_removed(self, instance_id: str, *, keep_data: bool) -> InstanceContext:
        """Record a completed driver removal; never performs removal itself."""
        if type(keep_data) is not bool:
            raise RegistryError('Choose explicitly whether data were preserved.')
        with self._locked():
            existing = self.get(instance_id)
            if existing.lifecycle == 'removed' and keep_data:
                raise RegistryError('Removed data cannot be marked as preserved without explicit recovery.')
            record = replace(existing, lifecycle='data-kept' if keep_data else 'removed',
                             observed_status='stopped' if keep_data else 'absent', updated_at=int(time.time()))
            self._write(record)
        return record


def _small_text(path: Path) -> str:
    if path.is_symlink():
        raise OSError('Symlink state is not adopted automatically')
    with path.open(encoding='utf-8') as stream:
        result = stream.read(MAX_RECORD + 1)
    if len(result) > MAX_RECORD:
        raise OSError('State too large')
    return result


def discover_legacy(system_root: Path = Path('/')) -> list[LegacyCandidate]:
    """Read existing installation markers without reading secrets or writing files.

    system_root supports disposable fixture filesystems. No installed marker
    means absent; unreadable/malformed markers remain visible as unknown.
    These candidates are not proof that any application is healthy.
    """
    system_root = Path(system_root).absolute()
    rows = []
    sites = system_root / 'etc/koha/sites'
    try:
        configs = sorted(sites.glob('*/koha-conf.xml'))
    except OSError:
        configs = []
    for config in configs:
        site = config.parent.name
        if SITE.fullmatch(site) and config.is_file():
            rows.append(LegacyCandidate('koha-native:' + site, 'koha', DRIVERS['koha'], site,
                {'root': str(config.parent), 'configuration': str(config)}, {'native_site': site}))
    for application, filename, project in (('tainacan', 'state', 'kn-tainacan'), ('dspace', 'state.json', 'kn-dspace')):
        root = system_root / 'var/lib/koha-nexus/platforms' / application
        state = root / filename
        if not state.exists() and not state.is_symlink():
            continue
        data: dict = {}
        problem = ''
        try:
            content = _small_text(state)
            if application == 'dspace':
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError('Object required')
                data = {key: parsed.get(key) for key in ('status', 'url')}
            else:
                for line in content.splitlines():
                    key, sep, value = line.partition('=')
                    if sep and key in ('status', 'url'):
                        data[key] = value
        except (OSError, ValueError, UnicodeError):
            problem = 'The existing state could not be read; use diagnosis before changing services.'
        status_value = data.get('status')
        if not isinstance(status_value, str) or not re.fullmatch(r'[a-z-]{1,48}', status_value):
            status_value = 'unknown'
        if status_value == 'kept':
            status_value = 'data-kept'
        url = _url(data.get('url'))
        rows.append(LegacyCandidate(application + '-docker:legacy', application, DRIVERS[application],
                    'Tainacan' if application == 'tainacan' else 'DSpace',
                    {'root': str(root), 'state': str(state)}, {'compose_project': project},
                    {'public': url} if url else {}, status_value, problem))
    return rows
