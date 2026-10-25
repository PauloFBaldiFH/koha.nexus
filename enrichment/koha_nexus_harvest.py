"""Bounded, on-demand Wikidata harvest for the central authority gateway.

Identifiers link to LoC/BN; labels remain preliminary, not official headings.
No scheduler or daemon is installed by this command.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from nexus_enrich.normalize import fold

COUNTRIES = ('Q155', 'Q45', 'Q142', 'Q183', 'Q38', 'Q29', 'Q145', 'Q30')
PROPERTIES = {'loc': 'P244', 'bn': 'P4619'}
ENDPOINT = 'https://query.wikidata.org/sparql'
MAX_RESPONSE = 16 * 1024 * 1024


def query(source: str, country: str) -> str:
    prop = PROPERTIES[source]
    if country not in COUNTRIES:
        raise ValueError('Unsupported country')
    return f'''SELECT DISTINCT ?person ?personLabel ?identifier WHERE {{
  ?person wdt:P31 wd:Q5; wdt:P27 wd:{country}; wdt:{prop} ?identifier.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "pt,en". }}
}} ORDER BY ?person ?identifier LIMIT 3000'''


def fetch(source: str, country: str) -> list[dict]:
    url = ENDPOINT + '?' + urllib.parse.urlencode({'query': query(source, country), 'format': 'json'})
    req = urllib.request.Request(url, headers={'Accept': 'application/sparql-results+json',
                                             'User-Agent': 'Koha.Nexus-authority-harvest/1.0'})
    with urllib.request.urlopen(req, timeout=90) as response:
        data = response.read(MAX_RESPONSE + 1)
    if len(data) > MAX_RESPONSE:
        raise ValueError('Harvest response exceeds size limit')
    return json.loads(data)['results']['bindings']


def apply(conn: sqlite3.Connection, source: str, bindings: list[dict]) -> int:
    """Upsert this provenance only; never replace official authority sources."""
    sid = 'wikidata-' + source
    conn.execute('INSERT OR IGNORE INTO sources (id, name, mode, brazilian) VALUES (?, ?, ?, ?)',
                 (sid, 'Wikidata / ' + source.upper() + ' identifiers', 'pointer', int(source == 'bn')))
    changed = 0
    for b in bindings:
        uri = b['person']['value']
        if not re.fullmatch(r'https?://www\.wikidata\.org/entity/Q\d+', uri):
            raise ValueError('Invalid Wikidata entity URI')
        label, identifier = b['personLabel']['value'].strip(), b['identifier']['value'].strip()
        if not label or re.fullmatch(r'Q\d+', label) or not identifier:
            continue
        key = fold(label)
        row = conn.execute('SELECT id FROM auth_headings WHERE kind = ? AND key = ? AND dates = ? '
                           'AND thesaurus = ? AND source = ?', ('personal', key, '', '', sid)).fetchone()
        if row:
            continue  # Stable reruns; preserve curator edits and existing FTS entries.
        hid = conn.execute('INSERT INTO auth_headings '
                           '(kind, heading, key, source, source_id, lccn, uri, preliminary) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?, 1)',
                           ('personal', label, key, sid, identifier,
                            identifier if source == 'loc' else '', uri)).lastrowid
        conn.execute('INSERT INTO auth_fts (rowid, heading, variants) VALUES (?, ?, ?)', (hid, label, ''))
        changed += 1
    conn.execute('UPDATE sources SET headings = (SELECT COUNT(*) FROM auth_headings WHERE source = ?) '
                 'WHERE id = ?', (sid, sid))
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('loc', 'bn', 'all'), required=True)
    parser.add_argument('--db', type=Path, required=True, help='Existing central gateway static.db')
    parser.add_argument('--reload-service', default='koha-nexus-sru.service',
                        help='Reload/restart this central unit after a successful change')
    parser.add_argument('--no-reload', action='store_true', help='Do not call systemctl')
    args = parser.parse_args(argv)
    try:
        # mode=rw prevents silently creating a wrong/empty database.
        conn = sqlite3.connect(args.db.resolve().as_uri() + '?mode=rw', uri=True, timeout=30)
        try:
            conn.execute('SELECT id FROM auth_headings LIMIT 1')
            sources = tuple(PROPERTIES) if args.source == 'all' else (args.source,)
            batches = [(s, fetch(s, c)) for s in sources for c in COUNTRIES]
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                changed = sum(apply(conn, s, rows) for s, rows in batches)
        finally:
            conn.close()
        print(json.dumps({'added': changed, 'partitions': len(batches)}))
        if changed and not args.no_reload:
            # The existing unit has no ExecReload; systemd falls back to restart.
            subprocess.run(['systemctl', 'reload-or-restart', args.reload_service], check=True, timeout=60)
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f'Harvest failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
