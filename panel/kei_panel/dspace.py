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
