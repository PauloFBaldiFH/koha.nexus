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
