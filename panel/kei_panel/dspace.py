"""Read-only DSpace status and safe decoding of the panel task protocol."""
from __future__ import annotations

import base64
import json
from urllib.parse import urlsplit

from textual.app import ComposeResult
from textual.containers import Grid

from .i18n import t
from .widgets.cards import LinkCard, StatusCard


def payload(out) -> dict:
    try:
        raw = base64.b64decode(out.results['payload'], validate=True) if 'payload' in out.results else out.results.get('json', '{}')
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def origin(value) -> str:
    try:
        u = urlsplit(value if isinstance(value, str) else '')
        if (u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or
                u.path not in ('', '/') or u.query or u.fragment or any(ord(c) < 33 for c in value)):
            return ''
        _ = u.port
        return value.rstrip('/')
    except ValueError:
        return ''


# Raw values from the DSpace runtime are protocol words. Each one is shown with
# a sentence-case English label that has its own translation, never as is.
STATE_LABELS = {
    'absent': 'Not installed', 'installing': 'Installing', 'installed': 'Installed and running',
    'starting': 'Starting', 'stopped': 'Stopped', 'degraded': 'Some services stopped',
    'unavailable': 'Docker unavailable', 'failed': 'Installation failed', 'data-kept': 'Removed, data kept',
}
PHASE_LABELS = {
    'images': 'Preparing images', 'network': 'Preparing the network', 'dependencies': 'Starting database and search',
    'migration': 'Preparing the database', 'application': 'Starting DSpace', 'proxy': 'Publishing the address',
    'ready': 'Installation complete',
}
SERVICE_LABELS = {
    'running': 'Running', 'exited': 'Stopped', 'created': 'Created, not started', 'restarting': 'Restarting',
    'paused': 'Paused', 'dead': 'Failed', 'removing': 'Being removed', 'missing': 'Not found',
}
BUILD_NOTE = 'Images built on this server from a pinned, verified recipe; amd64 processor'


def label(table: dict[str, str], value) -> str:
    """Translated label for a runtime value; unknown values say so plainly."""
    if value in (None, ''):
        return t('Unknown')
    return t(table[value]) if isinstance(value, str) and value in table else t('Unknown') + ' (' + str(value) + ')'


class DSpaceSummary(Grid):
    def __init__(self, **kwargs):
        super().__init__(classes='status-grid', **kwargs)

    def compose(self) -> ComposeResult:
        yield LinkCard(t('Repository (public site)'), id='ds-site')
        yield LinkCard(t('DSpace sign in'), id='ds-login')
        for key, title in (('state', 'DSpace'), ('phase', 'Installation phase'), ('version', 'Versions'),
                           ('postgres', 'PostgreSQL'), ('solr', 'Solr'), ('backend', 'DSpace API'), ('ui', 'Public interface')):
            yield StatusCard(t(title), id='ds-' + key)

    def on_resize(self, event) -> None:
        # Each link needs space for both Open and Copy. Preserve the shared
        # look while letting this summary fit terminals with a narrow sidebar.
        columns = max(1, min(3, event.size.width // 30))
        if self.styles.grid_size_columns != columns:
            self.styles.grid_size_columns = columns

    def show(self, data: dict) -> None:
        url = origin(data.get('url'))
        external = data.get('proxy_status') == 'external-configuration-required'
        note = t('External proxy: verify both routes; the public address has not been checked.') if external else ''
        for key, link in (('site', url), ('login', url + '/login' if url else '')):
            self.query_one('#ds-' + key, LinkCard).set_url(link, note, 'warn' if external else '')
        self.query_one('#ds-state', StatusCard).set(
            label(STATE_LABELS, data.get('status')), t('Process state; health is checked only by Diagnosis'), '')
        self.query_one('#ds-phase', StatusCard).set(label(PHASE_LABELS, data.get('phase')), t('Data are preserved after an interrupted operation'), '')
        self.query_one('#ds-version', StatusCard).set('DSpace 10.1', t(BUILD_NOTE), '')
        services = data.get('services') if isinstance(data.get('services'), dict) else {}
        for name in ('postgres', 'solr', 'backend', 'ui'):
            state = services.get(name, 'unknown')
            self.query_one('#ds-' + name, StatusCard).set(label(SERVICE_LABELS, state), t('Local container state'),
                                                                        'ok' if state == 'running' else 'warn')


# ----------------------------------------------------------------------
# Installation (U3): the runtime's answers as the shared screens' rows.
# Labels stay in English here and are translated where they are shown.
# ----------------------------------------------------------------------
def where(url: str) -> str:
    """Who can open an address: this computer, the institution's network or a name."""
    import ipaddress
    host = urlsplit(url).hostname or ''
    if host == 'localhost' or host.startswith('127.'):
        return 'this computer'
    try:
        return "the institution's network" if ipaddress.ip_address(host).is_private else 'the internet'
    except ValueError:
        return 'a name (domain)'


def preflight_rows(data: dict, deps: dict) -> list[tuple[str, str, str]]:
    """runtime preflight + dspace-prerequisites plan -> (state, label, detail)."""
    rows = []
    for row in data.get('checks') or []:
        if isinstance(row, dict) and row.get('state') in ('ok', 'warn', 'fail') and isinstance(row.get('label'), str):
            rows.append((row['state'], row['label'], t(str(row.get('detail') or ''))))
    if deps.get('docker_stopped'):
        rows.append(('warn', 'Docker service started', t('stopped: started with your confirmation')))
    if deps.get('apache_missing'):
        rows.append(('warn', 'Web server (Apache)', t('not installed: installed with your confirmation')))
    elif deps:
        rows.append(('ok', 'Web server (Apache)', str(deps.get('proxy_mode') or '')))
    return rows


def plan_rows(plan: dict) -> list[tuple[str, str]]:
    """The technical plan (runtime plan()) in plain lines; the plan itself is unchanged."""
    url = origin(plan.get('url')) or str(plan.get('url') or '')
    port = urlsplit(url).port or (443 if url.startswith('https') else 80)
    language = plan.get('language')
    rows = [
        (t('Will be installed'), t('DSpace (institutional repository)')),
        (t('Address'), f"{url} ({t(where(url))})"),
        (t('Initial language'), str(language) if language else t('Kept from the earlier preparation')),
        (t('Form'), t('Docker containers prepared on this server')),
        (t('Expected time'), t('10 to 30 minutes; the database preparation is the longest stage')),
        (t('Uses'), t('up to 5.5 GB of memory when in use; about 8 GB of disk')),
        (t('Changes on this server'),
         t('Another web server answers: Koha.Nexus shows the routes to add to it') if plan.get('proxy') == 'external'
         else t('An Apache site on port ${port}', port=port)),
        (t('Other systems'), t('Koha and Tainacan are not changed')),
        (t('Administrator account'), t('created afterwards, by you')),
    ]
    if plan.get('migration') in ('running', 'failed'):
        rows.append((t('Earlier attempt'), t('The database preparation stopped before; its data were kept')))
    return rows


def diagnosis_rows(data: dict) -> list[tuple[str, str, str]]:
    """runtime diagnose -> rows of the final diagnosis (and of Diagnosis)."""
    services = data.get('services') if isinstance(data.get('services'), dict) else {}
    rows = []
    for name, text in (('postgres', 'Database (PostgreSQL)'), ('solr', 'Search (Solr)'),
                       ('backend', 'DSpace API'), ('ui', 'Public interface')):
        state = services.get(name)
        rows.append(('ok' if state == 'running' else 'fail', text, label(SERVICE_LABELS, state)))
    health = data.get('health')
    if health == 'api-ui-dependencies':
        rows.append(('ok', 'API, interface and login page checked', ''))
    elif health == 'failed':
        rows.append(('fail', 'API, interface and login page checked', t(str(data.get('reason') or ''))))
    else:
        rows.append(('warn', 'API, interface and login page checked', label(STATE_LABELS, data.get('status'))))
    access = data.get('public_access')
    url = origin(data.get('url'))
    if access == 'verified-local-proxy':
        rows.append(('ok', 'Address verified from this server', url))
    elif access in ('external-configuration-required', 'external-proxy-required'):
        rows.append(('warn', 'Address verified from this server', t('external web server: check its routes')))
    elif access == 'external-tls-check-required':
        rows.append(('warn', 'Address verified from this server', t('HTTPS is checked by the external server')))
    elif access == 'failed':
        rows.append(('fail', 'Address verified from this server', url))
    else:
        rows.append(('warn', 'Address verified from this server', t('not checked')))
    return rows


# ----------------------------------------------------------------------
# Completion and operations (U4): results summed up in plain lines. The
# runtime's JSON stays whole behind "Technical details", never in front.
# ----------------------------------------------------------------------
def size_text(n) -> str:
    if not isinstance(n, (int, float)) or isinstance(n, bool) or n < 0:
        return t('Unknown')
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} GB'


def yes_no(value) -> str:
    return t('Yes') if value is True else t('No') if value is False else t('Unknown')


def codec(value) -> str:
    from .backup_center import DSPACE_CODECS
    return t(DSPACE_CODECS[value]) if value in DSPACE_CODECS else label({}, value)


def admin_emails(data: dict | None) -> list[str]:
    import re
    email = re.compile(r'[^@\s|=]+@[^@\s|=]+\.[^@\s|=]+')
    return [v for v in (data or {}).get('admins', []) if isinstance(v, str) and len(v) <= 254 and email.fullmatch(v)]


def admin_fact(data: dict | None) -> tuple[str, str, str]:
    """The administrator line of the completion: pending until one exists."""
    if data is None:
        return ('warn', t('Administrator account'), t('could not be read; see Administrative access'))
    emails = admin_emails(data)
    if not emails:
        return ('warn', t('Administrator account'), t('not created yet'))
    return ('ok', t('Administrator account'), ', '.join(emails))


def backup_rows(data: dict) -> list[tuple[str, str]]:
    package = str(data.get('package') or '')
    return [(t('File'), package.rsplit('/', 1)[-1] or t('Unknown')),
            (t('Folder'), package.rsplit('/', 1)[0] if '/' in package else t('Unknown')),
            (t('Size'), size_text(data.get('bytes'))),
            (t('Compression'), codec(data.get('compression'))),
            (t('Encrypted'), yes_no(data.get('encrypted'))),
            (t('Repository paused for'), t('${n} s', n=data['window_seconds'])
             if isinstance(data.get('window_seconds'), (int, float)) else t('Unknown'))]


def restore_plan_rows(plan: dict, package: str = '') -> list[tuple[str, str]]:
    rows = []
    if package:
        rows.append((t('Backup'), package.rsplit('/', 1)[-1]))
    rows += [(t('Made from'), origin(plan.get('source_url')) or t('Unknown')),
             (t('Restored into'), origin(plan.get('destination_url')) or t('Unknown')),
             (t('Files'), str(plan['files']) if isinstance(plan.get('files'), int) else t('Unknown')),
             (t('Size'), size_text(plan.get('uncompressed_bytes'))),
             (t('Compression'), codec(plan.get('compression'))),
             (t('Safety backup first'), yes_no(plan.get('safety_backup_required'))),
             (t('Current data kept'), t('Yes, in the old volumes') if plan.get('old_volumes_preserved') else t('No')),
             (t('Repository pauses'), yes_no(plan.get('repository_will_pause')))]
    return rows


def test_rows(result: dict) -> list[tuple[str, str]]:
    return [(t('Recovery verified'), yes_no(result.get('verified'))),
            (t('Database'), t('all records read') if result.get('database') else t('Unknown')),
            (t('Files'), t('all checksums match') if result.get('files') else t('Unknown')),
            (t('Search (Solr)'), t('all cores read') if result.get('solr') else t('Unknown')),
            (t('Network used'), t('none; nothing was published') if result.get('public_ports') is False else t('Unknown')),
            (t('Active repository'), t('not changed'))]


def restore_rows(result: dict) -> list[tuple[str, str]]:
    safety = str(result.get('safety_backup') or '')
    return [(t('Restored'), yes_no(result.get('restored'))),
            (t('Safety backup'), safety.rsplit('/', 1)[-1] or t('Unknown')),
            (t('Previous data'), t('kept in the old volumes') if result.get('old_volumes_preserved') else t('Unknown'))]


def repair_rows(plan: dict) -> list[tuple[str, str]]:
    url = origin(plan.get('url')) or str(plan.get('url') or '')
    rows = [(t('New address'), f"{url} ({t(where(url))})" if url else t('Unknown')),
            (t('Current address'), origin(plan.get('previous_url')) or t('Unknown')),
            (t('Changes'), t('DSpace address and its Apache site; a copy is kept to undo')),
            (t('Repository data'), t('kept') if plan.get('data_volumes_preserved') else t('Unknown')),
            (t('Database migration'), t('none') if plan.get('database_migration') is False else t('Unknown'))]
    if isinstance(plan.get('note'), str) and plan['note']:
        rows.append((t('Note'), t(plan['note'])))
    return rows
