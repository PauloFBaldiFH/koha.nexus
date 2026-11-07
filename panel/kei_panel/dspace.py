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


class DSpaceSummary(Grid):
    def __init__(self, **kwargs):
        super().__init__(classes='status-grid', **kwargs)

    def compose(self) -> ComposeResult:
        yield LinkCard(t('Repository (public site)'), id='ds-site')
        yield LinkCard(t('DSpace sign in'), id='ds-login')
        for key, title in (('state', 'DSpace'), ('phase', 'Installation phase'), ('version', 'Versions'),
                           ('postgres', 'PostgreSQL'), ('solr', 'Solr'), ('backend', 'DSpace API'), ('ui', 'Public interface')):
            yield StatusCard(t(title), id='ds-' + key)

    def show(self, data: dict) -> None:
        url = origin(data.get('url'))
        for key, link in (('site', url), ('login', url + '/login' if url else '')):
            self.query_one('#ds-' + key, LinkCard).set_url(link, t('Experimental DSpace'), '')
        self.query_one('#ds-state', StatusCard).set(
            t(str(data.get('status', 'Unknown'))), t('Process state; health is checked only by Diagnosis'), '')
        self.query_one('#ds-phase', StatusCard).set(str(data.get('phase', '-')), t('Data are preserved after an interrupted operation'), '')
        self.query_one('#ds-version', StatusCard).set('DSpace 10.1', t('Experimental; amd64 only'), 'warn')
        services = data.get('services') if isinstance(data.get('services'), dict) else {}
        for name in ('postgres', 'solr', 'backend', 'ui'):
            state = services.get(name, 'unknown')
            self.query_one('#ds-' + name, StatusCard).set(t(str(state)), t('Local container state'),
                                                                        'ok' if state == 'running' else 'warn')
