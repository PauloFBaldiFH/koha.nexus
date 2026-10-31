#!/usr/bin/env python3
"""Z39 Atlas: passive, public Z39.50 discovery + MARC verification.

Active tests go only to endpoints in an operator allowlist (`probe`), or,
with `auto-discover --published`, to the complete host:port/database
endpoints that public HTTPS documents themselves publish (recorded in the
auto_allowed table for audit). No Internet-wide network sweeping, port
guessing on published hosts, authentication guessing, or access-control
bypass. Python >= 3.10, standard library. Optional dependency: yaz-client.

The koha.nexus panel ships an identical copy as panel/kei_panel/z39atlas.py
(a panel test compares them): edit both.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

LOG = logging.getLogger('z39atlas')
UA = 'Z39Atlas/2.0 (+public bibliographic endpoint metadata; respectful crawler)'
DEFAULT_SOURCES = [
    'https://wiki.koha-community.org/wiki/Koha_Open_Z39.50_Sources',
    'https://wiki.koha-community.org/wiki/Configure_Z39.50/SRU_targets',
    'https://www.z-brary.com/',
    *[f'https://www.z-brary.com/{chr(i)}' for i in range(ord('a'), ord('z')+1)],
    'https://irspy.indexdata.com/',
    'https://www.loc.gov/standards/z3950/lcserver.html',
    'https://decti.bu.ufsc.br/catalogacao/dados-abertos/',
    'https://www.bne.es/es/perfiles/bibliotecarios/suministro-registros/descarga-z3950',
]
HOST_RX = r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}|(?:\d{1,3}\.){3}\d{1,3}'
ENDPOINT_RX = re.compile(rf'(?<![\w.@/])(?P<host>(?:{HOST_RX}))\s*:\s*(?P<port>\d{{2,5}})\s*/\s*(?P<base>[A-Za-z0-9_+.-]{{1,90}})', re.I)
HOSTPORT_RX = re.compile(rf'(?<![\w.@/])(?P<host>(?:{HOST_RX}))\s*:\s*(?P<port>\d{{2,5}})(?!\d)', re.I)
HOST_RX_COMPILED = re.compile(rf'^(?:{HOST_RX})$', re.I)
FIELD_RX = {
    'host': re.compile(r'(?i)(?:host(?:name)?|servidor|endereço|address)\s*[:=]\s*([a-z0-9._-]+)'),
    'port': re.compile(r'(?i)(?:port(?:a)?|porta)\s*[:=]\s*(\d{2,5})'),
    'database': re.compile(r'(?i)(?:database(?:\s*name)?|base\s*(?:de\s*dados)?|db\s*name)\s*[:=]\s*([a-z0-9_.+-]+)'),
}
ISO_MARC_TYPES_BIB = set('acdefgijkmoprt')
YAZ_MISSING = ('yaz-client is not installed, so no server can be tested. Install it first '
               '(Debian/Ubuntu: sudo apt install yaz), then start again.')
# Exit codes of auto-discover the panel tells apart.
EXIT_NO_YAZ = 3
EXIT_ALREADY_RUNNING = 4
LOCK = threading.Lock()


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def valid_host(host: str) -> bool:
    host = host.strip().rstrip('.').lower()
    if not HOST_RX_COMPILED.fullmatch(host):
        return False
    if host in {'localhost', 'localhost.localdomain'}:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        return not host.endswith(('.local', '.lan', '.internal', '.test', '.invalid', '.example'))


def parse_endpoint(host: str, port: int | str | None, database: str | None):
    host = (host or '').strip().lower().rstrip('.')
    if not valid_host(host):
        return None
    try:
        p = int(port) if port not in (None, '') else None
    except (ValueError, TypeError):
        return None
    if p is not None and not 1 <= p <= 65535:
        return None
    db = (database or '').strip().strip('/').strip()
    if db and not re.fullmatch(r'[A-Za-z0-9_.+-]{1,90}', db):
        return None
    return host, p, db


def key_for(host: str, port: int | None, database: str) -> str:
    return f'{host.lower()}|{port or ""}|{database.lower()}'


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Probe workers write from their threads, always under one lock.
    con = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=10000')
    con.executescript('''
        CREATE TABLE IF NOT EXISTS candidates (
            key TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', host TEXT NOT NULL,
            port INTEGER, database TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'unverified',
            checked_at TEXT, latency_ms INTEGER, hits INTEGER, marc_type TEXT,
            marc_bytes INTEGER, leader TEXT, error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_candidates_host ON candidates(host);
        CREATE INDEX IF NOT EXISTS ix_candidates_status ON candidates(status);
        CREATE TABLE IF NOT EXISTS provenance (
            candidate_key TEXT NOT NULL, source TEXT NOT NULL, excerpt TEXT NOT NULL,
            found_at TEXT NOT NULL, PRIMARY KEY(candidate_key, source),
            FOREIGN KEY(candidate_key) REFERENCES candidates(key)
        );
        CREATE TABLE IF NOT EXISTS fetch_history (
            url TEXT PRIMARY KEY, status TEXT NOT NULL, checked_at TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
        );
        -- The one background run (auto-discover): what the panel shows.
        CREATE TABLE IF NOT EXISTS run_state (
            id INTEGER PRIMARY KEY CHECK (id = 1), run_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'idle', phase TEXT NOT NULL DEFAULT '', pid INTEGER,
            started_at TEXT, updated_at TEXT, finished_at TEXT,
            pages_done INTEGER NOT NULL DEFAULT 0, pages_total INTEGER NOT NULL DEFAULT 0,
            new_candidates INTEGER NOT NULL DEFAULT 0,
            targets_done INTEGER NOT NULL DEFAULT 0, targets_total INTEGER NOT NULL DEFAULT 0,
            approved INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', options TEXT NOT NULL DEFAULT ''
        );
        -- Endpoints auto-discover --published tested without an allowlist line:
        -- each one was published, complete, in the public document named here.
        CREATE TABLE IF NOT EXISTS auto_allowed (
            candidate_key TEXT PRIMARY KEY, host TEXT NOT NULL, source TEXT NOT NULL, added_at TEXT NOT NULL
        );
    ''')
    con.commit()
    return con


def save_candidate(con: sqlite3.Connection, host: str, port, database, name='', source='', excerpt='') -> bool:
    parsed = parse_endpoint(host, port, database)
    if parsed is None:
        return False
    host, port, database = parsed
    key = key_for(host, port, database)
    now = utcnow()
    before = con.total_changes
    con.execute('''INSERT OR IGNORE INTO candidates(key,name,host,port,database,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)''', (key, (name or '')[:200], host, port, database, now, now))
    new = con.total_changes > before
    if source:
        con.execute('''INSERT INTO provenance(candidate_key,source,excerpt,found_at) VALUES(?,?,?,?)
                       ON CONFLICT(candidate_key,source) DO UPDATE SET excerpt=excluded.excerpt,
                       found_at=excluded.found_at''', (key, source[:1024], (excerpt or '')[:500], now))
    return new


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts = []
        self.links = []
        self._hidden = 0
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {'script', 'style', 'noscript'}:
            self._hidden += 1
        if tag in {'p', 'div', 'li', 'br', 'tr', 'td', 'th', 'h1', 'h2', 'h3'}:
            self.text_parts.append('\n' if tag in {'p', 'div', 'li', 'br', 'tr', 'h1', 'h2', 'h3'} else ' ')
        if tag == 'a':
            target = dict(attrs).get('href', '')
            if target:
                self.links.append(target)
        if tag == 'tr':
            self._row = []
        if tag in {'td', 'th'} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {'script', 'style', 'noscript'}:
            self._hidden = max(0, self._hidden - 1)
        if tag in {'td', 'th'} and self._cell is not None:
            self._row.append(''.join(self._cell).strip())
            self._cell = None
        if tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if not self._hidden:
            self.text_parts.append(data)
            if self._cell is not None:
                self._cell.append(data)


def extract_endpoints(document: str, is_html=True):
    """Derive only explicitly published endpoints; no host enumeration."""
    # Normalize explicitly published z3950:// URIs for the host:port/base parser.
    document = re.sub(r'(?i)z39(?:\.50|50|5\.0)?:\/\/', ' ', document)
    parser = DocumentParser()
    if is_html:
        parser.feed(document)
        text = html.unescape(''.join(parser.text_parts))
        rows = parser.rows
        links = parser.links
    else:
        text, rows, links = document, [], []
    found = {}

    def add(host, port, database, excerpt):
        parsed = parse_endpoint(host, port, database)
        if parsed is not None:
            found[key_for(*parsed)] = (*parsed, excerpt[:320])

    for m in ENDPOINT_RX.finditer(text):
        add(m['host'], m['port'], m['base'], text[max(0,m.start()-60):m.end()+60])
    for m in HOSTPORT_RX.finditer(text):
        # A partial endpoint is useful evidence; only explicit allowlisted probes may fill its DB.
        add(m['host'], m['port'], '', text[max(0,m.start()-60):m.end()+60])
    for row in rows:
        values = [x.strip().strip('`') for x in row]
        for idx, value in enumerate(values):
            if valid_host(value) and idx + 2 < len(values) and values[idx + 1].isdigit():
                add(value, values[idx + 1], values[idx + 2], ' | '.join(values))
            if len(values) >= 4 and valid_host(value) and idx + 2 < len(values):
                add(value, values[idx + 1], values[idx + 2], ' | '.join(values))
    # Detect structured config blocks spanning nearby lines. Limit context to avoid cross-pairing unrelated data.
    lines = [re.sub(r'\s+', ' ', x).strip() for x in text.splitlines()]
    lines = [x for x in lines if x][:50000]
    for i, line in enumerate(lines):
        if re.search(r'(?i)host(?:name)?\s*[:=]|servidor\s*[:=]', line):
            window = ' '.join(lines[i:i+5])[:500]
            h = FIELD_RX['host'].search(window)
            p = FIELD_RX['port'].search(window)
            b = FIELD_RX['database'].search(window)
            if h and p:
                add(h[1], p[1], b[1] if b else '', window)
    return list(found.values()), links


def public_ip(host: str) -> str:
    """Resolve and pin only globally routable addresses to prevent redirects to local networks."""
    if not valid_host(host):
        raise ValueError('hostname/IP not public')
    try:
        addrs = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError('DNS resolution failure') from exc
    ips = list(dict.fromkeys(info[4][0] for info in addrs))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('DNS returned nonpublic or reserved IP')
    # prefer IPv4 for maximum YAZ compatibility
    ips.sort(key=lambda ip: ':' in ip)
    return ips[0]


class SafeRedirect(HTTPRedirectHandler):
    def __init__(self, domains):
        self.domains = domains

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urlparse(newurl).hostname or ''
        if urlparse(newurl).scheme != 'https' or host.lower() not in self.domains:
            raise URLError('redirect outside HTTPS public-source allowlist')
        public_ip(host)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def public_url_ok(url: str, allowed_domains: set[str]) -> bool:
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname is not None and p.hostname.lower() in allowed_domains and not p.username and not p.password


def read_public_page(url: str, domains: set[str], robots: dict, max_bytes=4_000_000):
    if not public_url_ok(url, domains):
        raise ValueError('URL outside source allowlist (HTTPS only)')
    host = urlparse(url).hostname
    public_ip(host)
    robots_url = f'https://{host}/robots.txt'
    if host not in robots:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        # Fetch through the same restricted HTTPS redirect handler. This prevents
        # arbitrary robots.txt redirects outside the documentation-source domain.
        try:
            rob_op = build_opener(SafeRedirect(domains))
            with rob_op.open(Request(robots_url, headers={'User-Agent':UA}), timeout=12) as rob_resp:
                content = rob_resp.read(120_001)
                if len(content) > 120_000:
                    raise ValueError('oversized robots.txt')
            rp.parse(content.decode('utf-8', errors='replace').splitlines())
            robots[host] = rp
        except HTTPError as exc:
            if exc.code in (404,410):
                rp.parse([])  # Absent robots.txt permits fetching per RFC 9309.
                robots[host] = rp
            else:
                raise ValueError('robots.txt access denied/unavailable: source skipped') from exc
        except Exception as exc:
            raise ValueError('robots.txt unavailable: source skipped') from exc
    if not robots[host].can_fetch(UA, url):
        raise ValueError('robots.txt disallows this URL')
    op = build_opener(SafeRedirect(domains))
    with op.open(Request(url, headers={'User-Agent':UA,'Accept':'text/html,text/plain;q=0.9'}), timeout=15) as resp:
        content_type = resp.headers.get('content-type','').lower()
        if not any(x in content_type for x in ('text/html','text/plain','application/xhtml+xml')):
            raise ValueError('unsupported non-text format')
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError('page exceeds max_bytes')
        final_url = resp.geturl()
        if not public_url_ok(final_url, domains):
            raise ValueError('unapproved response URL')
        encoding = resp.headers.get_content_charset() or 'utf-8'
        try:
            text = data.decode(encoding, errors='replace')
        except LookupError:
            text = data.decode('utf-8', errors='replace')
        return text, 'html' in content_type, final_url


def harvest_sources(no_defaults=False, urls_file=None, urls=None) -> list[str]:
    sources = list(DEFAULT_SOURCES) if not no_defaults else []
    if urls_file:
        sources.extend(x.strip() for x in Path(urls_file).read_text(encoding='utf-8').splitlines()
                       if x.strip() and not x.lstrip().startswith('#'))
    sources.extend(urls or [])
    return sources


def recently_fetched(con, url: str, hours: float | None) -> bool:
    """True when url was read successfully within `hours` (resume after a crash)."""
    if not hours:
        return False
    row = con.execute("SELECT checked_at FROM fetch_history WHERE url=? AND status='ok'", (url,)).fetchone()
    if not row:
        return False
    try:
        return dt.datetime.fromisoformat(row[0]) >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    except ValueError:
        return False


def harvest(con, sources, *, max_pages=60, delay=2.0, max_bytes=4_000_000, follow_links=False,
            refetch_hours=None, progress=None, should_stop=None, reader=None) -> dict:
    """Read public HTTPS documentation pages and save the endpoints they publish.

    One request at a time, `delay` seconds between two requests to the same
    host, robots.txt respected. With refetch_hours, a page read successfully
    that recently is not read again (a restarted run continues).
    progress(pages_done, pages_total, new_candidates) is called after each page.
    """
    reader = reader or read_public_page
    domains = set()
    for u in sources:
        p = urlparse(u)
        if p.scheme == 'https' and p.hostname and valid_host(p.hostname):
            domains.add(p.hostname.lower())
    if not domains:
        raise SystemExit('No valid HTTPS public sources supplied')
    queue = list(dict.fromkeys(sources))
    seen = set()
    robots = {}
    found = skipped_recent = 0
    last_request = {}
    while queue and len(seen) < max_pages:
        if should_stop and should_stop():
            break
        u = queue.pop(0)
        if u in seen or not public_url_ok(u, domains):
            continue
        if not follow_links and recently_fetched(con, u, refetch_hours):
            skipped_recent += 1
            seen.add(u)
            if progress:
                progress(len(seen), min(max_pages, len(seen) + len(queue)), found)
            continue
        seen.add(u)
        host = urlparse(u).hostname.lower()
        wait = max(0, delay - (time.monotonic() - last_request.get(host, 0)))
        if wait: time.sleep(wait)
        last_request[host] = time.monotonic()
        try:
            raw, is_html, final = reader(u, domains, robots, max_bytes=max_bytes)
            matches, links = extract_endpoints(raw, is_html)
            with con:
                for target_host, port, base, excerpt in matches:
                    if save_candidate(con,target_host,port,base, source=final,excerpt=excerpt):
                        found += 1
                con.execute('''INSERT INTO fetch_history(url,status,checked_at,detail) VALUES(?,?,?,?)
                               ON CONFLICT(url) DO UPDATE SET status=excluded.status,checked_at=excluded.checked_at,detail=excluded.detail''',
                            (u,'ok',utcnow(),f'endpoints={len(matches)}'))
            LOG.info('Public source %s: %d parsed, %d new total', u, len(matches), found)
            if follow_links:
                for href in links:
                    newurl = urljoin(final, href).split('#')[0]
                    if public_url_ok(newurl, domains) and newurl not in seen and newurl not in queue:
                        queue.append(newurl)
        except (OSError, URLError, ValueError, HTTPError) as exc:
            LOG.warning('Skipped %s: %s',u,exc)
            with con:
                con.execute('''INSERT INTO fetch_history(url,status,checked_at,detail) VALUES(?,?,?,?)
                               ON CONFLICT(url) DO UPDATE SET status=excluded.status, checked_at=excluded.checked_at,detail=excluded.detail''',
                            (u,'skipped',utcnow(),str(exc)[:300]))
        if progress:
            progress(len(seen), min(max_pages, len(seen) + len(queue)), found)
    return {'pages_visited':len(seen), 'pages_resumed':skipped_recent, 'new_candidates':found,
            'total_candidates':con.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]}


def cmd_harvest(args):
    con = init_db(Path(args.db))
    sources = harvest_sources(args.no_defaults, args.urls_file, args.url)
    result = harvest(con, sources, max_pages=args.max_pages, delay=args.delay, max_bytes=args.max_bytes,
                     follow_links=args.follow_links)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def cmd_import(args):
    con = init_db(Path(args.db))
    total = accepted = new = 0
    with open(args.file, newline='', encoding='utf-8-sig') as fp:
        reader = csv.DictReader(fp, delimiter='\t' if args.file.endswith('.tsv') else ',')
        for row in reader:
            total += 1
            host = row.get('host') or row.get('hostname') or ''
            port = row.get('port') or row.get('porta') or ''
            base = row.get('database') or row.get('db') or row.get('base') or ''
            if parse_endpoint(host,port,base) is None:
                continue
            accepted += 1
            with con:
                new += bool(save_candidate(con,host,port,base,row.get('name',''),row.get('source','imported:'+args.file),''))
    print(json.dumps({'rows':total,'accepted':accepted,'new':new,'total_candidates':con.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]},ensure_ascii=False,indent=2))


def check_marc(data: bytes):
    """Return first valid MARC ISO2709 record metadata (strict basic structural checks)."""
    pos = 0
    while pos + 25 <= len(data):
        leader = data[pos:pos+24]
        if not leader[:5].isdigit() or not leader[12:17].isdigit():
            pos += 1
            continue
        n, base = int(leader[:5]), int(leader[12:17])
        if n < 26 or n > 1_000_000 or base < 25 or base > n or (base - 25) % 12:
            pos += 1
            continue
        if pos + n > len(data) or data[pos+n-1:pos+n] != b'\x1d' or data[pos+base-1:pos+base] != b'\x1e':
            pos += 1
            continue
        kind = 'authority' if chr(leader[6]) == 'z' else ('bibliographic' if chr(leader[6]) in ISO_MARC_TYPES_BIB else 'other')
        return kind, n, leader.decode('ascii', errors='replace')
    return None


def extract_hit_count(output: str) -> int | None:
    for pat in [r'(?im)\bnumber of hits\s*:\s*(\d+)', r'(?im)\bresult count\s*:\s*(\d+)',
                r'(?im)\bhits\s*:\s*(\d+)', r'(?im)\bsearch response\s*:\s*(\d+)']:
        match = re.search(pat, output)
        if match:
            return int(match.group(1))
    return None


def yaz_probe(host: str, port: int, base: str, timeout: int):
    if shutil.which('yaz-client') is None:
        raise RuntimeError('yaz-client not installed: sudo apt install yaz')
    resolved = public_ip(host)  # pin public IP; never pass unchecked hostname to YAZ.
    addr = f'[{resolved}]' if ':' in resolved else resolved
    # Two small fixed title queries. No credentials, brute force, Scan, or enumeration.
    commands = '\n'.join([
        'format usmarc',
        f'open {addr}:{port}/{base}',
        'elements F',
        'find @attr 1=4 history',
        'show 1',
        'find @attr 1=4 biblioteca',
        'show 1',
        'quit',
        ''
    ])
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='z39atlas_') as td:
        cmdfile = Path(td) / 'commands.txt'
        marcfile = Path(td) / 'record.mrc'
        cmdfile.write_text(commands, encoding='utf-8')
        try:
            result = subprocess.run(['yaz-client','-f',str(cmdfile),'-m',str(marcfile)],
                                    capture_output=True,text=True,errors='replace',timeout=timeout,
                                    cwd=td, env={**os.environ,'HOME':td})
        except subprocess.TimeoutExpired:
            return ('timeout', None, None, None, None, 'command timed out',round((time.monotonic()-started)*1000))
        output = result.stdout[-15000:] + '\n' + result.stderr[-3000:]
        ms = round((time.monotonic()-started)*1000)
        hits = extract_hit_count(output)
        if marcfile.exists():
            marc = check_marc(marcfile.read_bytes()[:1_000_000])
            if marc:
                kind, size, leader = marc
                return ('marc_'+kind,hits,kind,size,leader,'',ms)
        if re.search(r'(?i)connection refused|connect failed|unable to connect|failed to connect|no route to host',output):
            status = 'unreachable'
        elif re.search(r'(?i)authentication|access denied|not authorized|permission denied',output):
            status = 'restricted'
        elif hits is not None:
            status = 'search_without_marc'
        elif re.search(r'(?i)init response|init ok|initialized', output):
            status = 'init_only'
        else:
            status = 'unverified'
        return (status,hits,None,None,None,re.sub(r'\s+',' ',output)[-240:],ms)


def load_allowlist(path: str) -> set[str]:
    hosts = set()
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip().lower()
        if not line:
            continue
        if not valid_host(line):
            raise ValueError(f'allowlist must contain one public hostname or IP per line: {line!r}')
        hosts.add(line)
    if not hosts:
        raise ValueError('allowlist empty')
    return hosts


def candidates_to_probe(con, allowlist, recheck_hours, infer_missing=False, max_targets=5000):
    min_time = dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=recheck_hours)
    rows = con.execute('SELECT host,port,database,checked_at FROM candidates WHERE host IN ('+
                       ','.join('?' for _ in allowlist)+') ORDER BY COALESCE(checked_at,\'\'),host,port,database',
                       sorted(allowlist)).fetchall()
    targets = {}
    for host,port,base,checked in rows:
        if checked:
            try:
                if dt.datetime.fromisoformat(checked) >= min_time:
                    continue
            except ValueError: pass
        if port is not None and base:
            targets[key_for(host,port,base)] = (host,port,base)
        elif infer_missing:
            # Only small conventional values on explicitly allowlisted hosts.
            # Does not fabricate hostnames, scan ports, or guess login credentials.
            for b in ([base] if base else ['Default','innopac','voyager']):
                p = port or 210
                targets[key_for(host,p,b)] = (host,p,b)
        if len(targets) >= max_targets:
            break
    return list(targets.values())[:max_targets]


def run_probe(con, targets, *, workers=2, host_interval=10.0, timeout=25, max_hours=24.0,
              source_tag='', progress=None, should_stop=None) -> dict:
    """Test targets with yaz_probe: at most `workers` at a time, one at a time
    per host, `host_interval` seconds between two tests of the same host.
    Each result is saved as soon as it arrives (checked_at), so a run that
    stops is continued by candidates_to_probe/published_targets without
    testing those again. progress(done, total, approved) after each target."""
    deadline = time.monotonic() + max_hours*3600
    last_host_access = {}
    host_lock = {}
    host_lock_mutex = threading.Lock()
    db_lock = threading.Lock()

    def do_one(item):
        host,port,base = item
        with host_lock_mutex:
            lock = host_lock.setdefault(host,threading.Lock())
        with lock:
            pause = max(0,host_interval - (time.monotonic()-last_host_access.get(host,0)))
            if pause: time.sleep(pause)
            last_host_access[host] = time.monotonic()
            try:
                result = yaz_probe(host,port,base,timeout)
            except (ValueError, RuntimeError, OSError) as exc:
                result = ('error',None,None,None,None,str(exc)[:240],0)
            with db_lock:
                now = utcnow()
                with con:
                    save_candidate(con,host,port,base,source=source_tag)
                    con.execute('''UPDATE candidates SET status=?,hits=?,marc_type=?,marc_bytes=?,leader=?,error=?,
                                   latency_ms=?,checked_at=?,updated_at=? WHERE key=?''',
                                (*result, now, now,key_for(host,port,base)))
            LOG.info('%s %s:%s/%s (%sms)',result[0],host,port,base,result[-1])
            return result[0]

    results = {}
    total = len(targets)
    # At most `workers` outstanding tasks. Stops scheduling at the time budget
    # (or a stop request) instead of enqueuing the entire backlog on day one.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        pending = set()
        items = iter(targets)
        exhausted = False
        while pending or not exhausted:
            while (not exhausted and len(pending) < workers and time.monotonic() < deadline
                   and not (should_stop and should_stop())):
                item = next(items, None)
                if item is None:
                    exhausted = True
                    break
                pending.add(executor.submit(do_one,item))
            if not pending:
                break
            completed, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in completed:
                status = future.result()
                results[status] = results.get(status,0)+1
            if progress:
                progress(sum(results.values()), total, results.get('marc_bibliographic', 0))
            if time.monotonic() >= deadline or (should_stop and should_stop()):
                exhausted = True
    return {'tested':sum(results.values()),'statuses':results}


def cmd_probe(args):
    if not args.ack_authorized:
        raise SystemExit('Active tests require --ack-authorized and a host allowlist you control/are permitted to test.')
    hosts = load_allowlist(args.allowlist)
    con = init_db(Path(args.db))
    targets = candidates_to_probe(con,hosts,args.recheck_hours,args.infer_missing,args.max_targets)
    if not targets:
        print('No eligible explicitly allowlisted endpoints to test.'); return
    if not shutil.which('yaz-client'):
        raise SystemExit(YAZ_MISSING)
    LOG.info('Active testing: %d allowlisted endpoints, max workers=%d',len(targets),args.workers)
    result = run_probe(con, targets, workers=args.workers, host_interval=args.host_interval, timeout=args.timeout,
                       max_hours=args.max_hours, source_tag='inference:allowlisted' if args.infer_missing else '')
    print(json.dumps(result,ensure_ascii=False,indent=2))


# ----------------------------------------------------------------------
# Published-endpoint targets (auto-discover --published)
# ----------------------------------------------------------------------
def norm_key(host, port, database) -> str:
    """One spelling for comparing lists: host|port|database, all lower case,
    https:// and a trailing dot dropped."""
    host = re.sub(r'^[a-z0-9+]+://', '', str(host or '').strip().lower()).rstrip('.').split('/')[0]
    try:
        port = int(port) if port not in (None, '') else ''
    except (TypeError, ValueError):
        port = ''
    return f'{host}|{port}|{str(database or "").strip().strip("/").lower()}'


def load_known(path) -> set[str]:
    """Endpoint keys (norm_key) from a list Koha already has or the panel ships:
    z3950_direct.json (servers, their alternates, excluded), z3950_targets.json
    (targets), a CSV/TSV with host/port/db columns, the rows of
    `config.sh --task z3950-list` (host TAB port TAB db ...), or lines of
    host:port/db."""
    text = Path(path).read_text(encoding='utf-8-sig')
    keys = set()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if data is not None:
        items = data if isinstance(data, list) else [
            *data.get('servers', []), *data.get('targets', []), *data.get('excluded', [])]
        for item in items:
            if not isinstance(item, dict):
                continue
            for d in [item, *(item.get('alternates') or [])]:
                if isinstance(d, dict) and d.get('host'):
                    keys.add(norm_key(d.get('host'), d.get('port') or 210, d.get('db', d.get('database', ''))))
        return keys
    lines = [x for x in text.splitlines() if x.strip() and not x.lstrip().startswith('#')]
    if lines and re.search(r'(?i)\bhost\b', lines[0]) and (',' in lines[0] or '\t' in lines[0]):
        for row in csv.DictReader(lines, delimiter='\t' if '\t' in lines[0] else ','):
            row = {(k or '').strip().lower(): v for k, v in row.items()}
            if row.get('host'):
                keys.add(norm_key(row['host'], row.get('port') or 210,
                                  row.get('db') or row.get('database') or row.get('base') or ''))
        return keys
    for line in lines:
        line = line.strip()
        if '\t' in line:
            parts = line.split('\t')
            if len(parts) >= 3:
                keys.add(norm_key(parts[0], parts[1], parts[2]))
            continue
        m = re.match(r'^(?:[a-z0-9+]+://)?([^\s:/]+):(\d{1,5})/?(\S*)$', line, re.I)
        if m:
            keys.add(norm_key(m[1], m[2], m[3]))
    return keys


def published_targets(con, recheck_hours, max_targets=5000, known=frozenset()):
    """The endpoints auto-discover --published may test without an allowlist:
    host, port AND database all published together in a public HTTPS document
    (provenance), public host, not already known, not tested within
    recheck_hours. Nothing is guessed: no default ports or database names,
    no other hosts. Each one is recorded in auto_allowed with its source."""
    min_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=recheck_hours)
    rows = con.execute("""SELECT c.key,c.host,c.port,c.database,c.checked_at,MIN(p.source)
                          FROM candidates c JOIN provenance p ON p.candidate_key=c.key
                          WHERE c.port IS NOT NULL AND c.database<>'' AND p.source LIKE 'https://%'
                          GROUP BY c.key ORDER BY COALESCE(c.checked_at,''),c.host,c.port,c.database""").fetchall()
    targets = []
    now = utcnow()
    for key, host, port, base, checked, source in rows:
        if norm_key(host, port, base) in known or not valid_host(host):
            continue
        if checked:
            try:
                if dt.datetime.fromisoformat(checked) >= min_time:
                    continue
            except ValueError:
                pass
        targets.append((host, port, base))
        con.execute('INSERT OR IGNORE INTO auto_allowed(candidate_key,host,source,added_at) VALUES(?,?,?,?)',
                    (key, host, source[:1024], now))
        if len(targets) >= max_targets:
            break
    con.commit()
    return targets


# ----------------------------------------------------------------------
# Run state (the background run the panel starts and watches)
# ----------------------------------------------------------------------
STATE_FIELDS = ('run_id', 'status', 'phase', 'pid', 'started_at', 'updated_at', 'finished_at', 'pages_done',
                'pages_total', 'new_candidates', 'targets_done', 'targets_total', 'approved', 'error', 'options')


def set_state(con, **fields) -> None:
    bad = set(fields) - set(STATE_FIELDS)
    if bad:
        raise ValueError(f'unknown state fields: {sorted(bad)}')
    fields['updated_at'] = utcnow()
    with con:
        con.execute('INSERT OR IGNORE INTO run_state(id) VALUES(1)')
        con.execute('UPDATE run_state SET ' + ','.join(f'{k}=?' for k in fields) + ' WHERE id=1',
                    list(fields.values()))


def pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False
    return True


def read_status(db) -> dict:
    """The last run's state as a dict ('status': idle when none ran yet).
    A run still marked running whose process is gone (power cut, kill -9)
    reads as 'interrupted': starting again continues it."""
    if not Path(db).exists():
        return {'status': 'idle'}
    con = init_db(Path(db))
    try:
        row = con.execute('SELECT ' + ','.join(STATE_FIELDS) + ' FROM run_state WHERE id=1').fetchone()
        confirmed = con.execute("SELECT COUNT(*) FROM candidates WHERE status='marc_bibliographic'").fetchone()[0]
    finally:
        con.close()
    if not row:
        return {'status': 'idle', 'confirmed_total': confirmed}
    state = dict(zip(STATE_FIELDS, row))
    if state['status'] == 'running' and not pid_alive(state['pid']):
        state['status'] = 'interrupted'
    state['confirmed_total'] = confirmed
    pages = state['pages_done'] / state['pages_total'] if state['pages_total'] else 0
    targets = state['targets_done'] / state['targets_total'] if state['targets_total'] else 0
    # Harvest is the first 20 %, the tests the other 80 %.
    state['percent'] = (100 if state['status'] == 'finished' else
                        round(20 * min(pages, 1) + (80 * min(targets, 1) if state['phase'] == 'probe' else 0)))
    return state


def new_servers(db, known=frozenset(), recordtype='bibliographic') -> list[dict]:
    """The candidates this tool confirmed (marc_bibliographic: a structurally
    valid ISO 2709 record retrieved by its own test) that are not in `known`."""
    con = init_db(Path(db))
    try:
        rows = con.execute("""SELECT c.name,c.host,c.port,c.database,c.hits,c.latency_ms,c.checked_at,c.leader,
                                     group_concat(p.source,' | ')
                              FROM candidates c LEFT JOIN provenance p ON p.candidate_key=c.key
                              WHERE c.status=? GROUP BY c.key ORDER BY c.host,c.port,c.database""",
                           ('marc_' + recordtype,)).fetchall()
    finally:
        con.close()
    out = []
    for name, host, port, base, hits, ms, checked, leader, sources in rows:
        if norm_key(host, port, base) in known:
            continue
        out.append({'name': name or host, 'host': host, 'port': port, 'database': base, 'hits': hits,
                    'latency_ms': ms, 'checked_at': checked, 'leader': leader or '',
                    'sources': [x for x in (sources or '').split(' | ') if x]})
    return out


def background_command(script, db, args) -> list[str]:
    return [sys.executable, str(script), '--db', str(db), 'auto-discover', *args]


def start_background(db, args, log_path, script=None) -> int:
    """Start auto-discover detached from the caller (its own session: closing
    the panel or the terminal does not stop it). Returns the process id; its
    output goes to log_path. The run's own state goes to the database."""
    script = Path(script or __file__).resolve()
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'ab') as log:
        proc = subprocess.Popen(background_command(script, db, args), stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    return proc.pid


def stop_run(db) -> bool:
    """Ask a running auto-discover to stop (SIGTERM): it finishes the tests
    already started, saves them and ends as 'stopped'."""
    state = read_status(db)
    if state.get('status') != 'running':
        return False
    try:
        os.kill(int(state['pid']), signal.SIGTERM)
    except (OSError, ValueError, TypeError):
        return False
    return True


def cmd_auto_discover(args):
    """harvest -> published (or allowlisted) targets -> yaz MARC test -> SQLite,
    with its progress in run_state."""
    if not args.published and not args.ack_authorized:
        raise SystemExit('With --allowlist, active tests also require --ack-authorized.')
    if shutil.which('yaz-client') is None:
        print(YAZ_MISSING, file=sys.stderr)
        raise SystemExit(EXIT_NO_YAZ)
    db = Path(args.db)
    state = read_status(db)
    if state.get('status') == 'running' and int(state.get('pid') or 0) != os.getpid():
        print(f"A discovery run is already running (process {state['pid']}).", file=sys.stderr)
        raise SystemExit(EXIT_ALREADY_RUNNING)
    if args.background:
        rest = [a for a in argv_after_command(args.argv, ('auto-discover', 'pipeline')) if a != '--background']
        pid = start_background(db, rest, args.log or db.with_suffix('.log'))
        print(json.dumps({'started': True, 'pid': pid, 'db': str(db), 'log': str(args.log or db.with_suffix('.log'))}))
        return
    allow = None if args.published else load_allowlist(args.allowlist)
    known = set()
    for path in args.known or []:
        known |= load_known(path)
    con = init_db(db)
    stop = threading.Event()

    def on_term(signum, frame):
        LOG.warning('Stop requested: finishing the tests already started.')
        stop.set()
    for sig in (signal.SIGTERM, signal.SIGINT, getattr(signal, 'SIGHUP', None)):
        if sig is not None:
            signal.signal(sig, on_term)
    mode = 'published' if args.published else 'allowlist'
    set_state(con, run_id=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'), status='running',
              phase='harvest', pid=os.getpid(), started_at=utcnow(), finished_at=None, pages_done=0,
              pages_total=0 if args.skip_harvest else args.max_pages, new_candidates=0, targets_done=0,
              targets_total=0, approved=0, error='',
              options=json.dumps({'mode': mode, 'max_pages': args.max_pages, 'delay': args.delay,
                                  'workers': args.workers, 'host_interval': args.host_interval,
                                  'timeout': args.timeout, 'recheck_hours': args.recheck_hours,
                                  'known_lists': len(args.known or []), 'known_endpoints': len(known)}))
    try:
        summary = {'mode': mode}
        if not args.skip_harvest:
            sources = harvest_sources(args.no_defaults, args.urls_file, args.url)
            summary['harvest'] = harvest(
                con, sources, max_pages=args.max_pages, delay=args.delay, max_bytes=args.max_bytes,
                refetch_hours=args.refetch_hours, should_stop=stop.is_set,
                progress=lambda done, total, new: set_state(con, pages_done=done, pages_total=total,
                                                            new_candidates=new))
        if stop.is_set():
            raise KeyboardInterrupt
        if allow is None:
            targets = published_targets(con, args.recheck_hours, args.max_targets, known)
        else:
            targets = [x for x in candidates_to_probe(con, allow, args.recheck_hours, False, args.max_targets)
                       if norm_key(*x) not in known]
        set_state(con, phase='probe', targets_total=len(targets), targets_done=0)
        LOG.info('Testing %d endpoints (%s), workers=%d, %ss between tests of one host',
                 len(targets), mode, args.workers, args.host_interval)
        summary['probe'] = run_probe(
            con, targets, workers=args.workers, host_interval=args.host_interval, timeout=args.timeout,
            max_hours=args.max_hours, source_tag='', should_stop=stop.is_set,
            progress=lambda done, total, ok: set_state(con, targets_done=done, approved=ok))
        set_state(con, status='stopped' if stop.is_set() else 'finished', phase='done', finished_at=utcnow())
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        set_state(con, status='stopped', finished_at=utcnow())
        raise SystemExit(130)
    except BaseException as exc:
        if isinstance(exc, SystemExit) and exc.code in (0, None):
            raise
        set_state(con, status='failed', finished_at=utcnow(), error=f'{type(exc).__name__}: {exc}'[:500])
        raise
    finally:
        con.close()


def argv_after_command(argv, commands) -> list[str]:
    for i, a in enumerate(argv):
        if a in commands:
            return list(argv[i + 1:])
    return []


def cmd_status(args):
    print(json.dumps(read_status(args.db), ensure_ascii=False, indent=2))


def cmd_stop(args):
    print('Stop requested.' if stop_run(args.db) else 'No discovery run is running.')


def cmd_new_servers(args):
    known = set()
    for path in args.known or []:
        known |= load_known(path)
    rows = new_servers(args.db, known)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', newline='', encoding='utf-8-sig') as fp:
            writer = csv.writer(fp)
            writer.writerow(['name', 'host', 'port', 'database', 'hits', 'latency_ms', 'checked_at', 'sources'])
            for r in rows:
                writer.writerow([r['name'], r['host'], r['port'], r['database'], r['hits'], r['latency_ms'],
                                 r['checked_at'], ' | '.join(r['sources'])])
        print(f'{len(rows)} new confirmed servers written to {args.output}')
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_search_docs(args):
    """Find public *documents* via an official search API. Does not probe servers."""
    token = os.environ.get('BRAVE_SEARCH_API_KEY', '').strip()
    if not token:
        raise SystemExit('Set BRAVE_SEARCH_API_KEY in the environment; do not put API keys in command history.')
    queries = list(args.query or [])
    if args.queries_file:
        queries.extend(x.strip() for x in Path(args.queries_file).read_text(encoding='utf-8').splitlines()
                       if x.strip() and not x.strip().startswith('#'))
    if not queries:
        queries = [
            'Z39.50 servidor porta base biblioteca site:edu.br',
            'Z39.50 catálogo biblioteca site:gov.br',
            'Z39.50 hostname database library catalog',
            'Z39.50 Koha source server database configuration',
            'SRU Z39.50 bibliotecas Brasil documentação',
        ]
    if len(queries) > 20:
        raise SystemExit('Maximum 20 search queries per invocation')
    found = {}
    op = build_opener(SafeRedirect({'api.search.brave.com'}))
    from urllib.parse import urlencode
    for query in queries:
        params = urlencode({'q':query,'count':min(args.count,20),'search_lang':'en'})
        url = 'https://api.search.brave.com/res/v1/web/search?' + params
        try:
            public_ip('api.search.brave.com')
            req = Request(url, headers={'Accept':'application/json','X-Subscription-Token':token,'User-Agent':UA})
            with op.open(req,timeout=20) as response:
                body = json.loads(response.read(1_000_000).decode('utf-8'))
            for item in body.get('web',{}).get('results',[]):
                u = item.get('url','')
                p = urlparse(u)
                if p.scheme=='https' and p.hostname and valid_host(p.hostname) and not p.username and not p.password:
                    found[u] = {'query':query,'title':item.get('title','')[:180]}
            LOG.info('Search %r: %d cumulative public URLs',query,len(found))
        except (OSError, URLError, ValueError, HTTPError, json.JSONDecodeError) as exc:
            LOG.warning('Search skipped: %s',type(exc).__name__)
        time.sleep(args.delay)
    target = Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('\n'.join(sorted(found))+'\n',encoding='utf-8')
    print(json.dumps({'discovered_public_document_urls':len(found), 'file':str(target),
                      'next_step':'Review URLs, then run harvest --urls-file ...'},ensure_ascii=False,indent=2))


def cmd_export(args):
    con = init_db(Path(args.db))
    query = '''SELECT c.name,c.host,c.port,c.database,c.status,c.hits,c.marc_type,c.marc_bytes,c.latency_ms,
                      c.checked_at,c.error,group_concat(p.source,' | ') FROM candidates c
                      LEFT JOIN provenance p ON p.candidate_key=c.key'''
    conditions = []
    params = []
    if args.confirmed_only:
        conditions.append("c.status IN ('marc_bibliographic','marc_authority','marc_other')")
    if args.host:
        conditions.append('c.host = ?')
        params.append(args.host.lower())
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY c.key ORDER BY c.status,c.host,c.port,c.database'
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    with open(args.output,'w',newline='',encoding='utf-8-sig') as fp:
        writer = csv.writer(fp)
        writer.writerow(['name','host','port','database','status','hits','marc_type','marc_bytes','latency_ms','checked_at','error','sources'])
        rows = con.execute(query,params).fetchall()
        writer.writerows(rows)
    print(f'Exported {len(rows)} rows to {args.output}')


def cmd_stats(args):
    con = init_db(Path(args.db))
    data = con.execute('SELECT status,COUNT(*) FROM candidates GROUP BY status ORDER BY COUNT(*) DESC').fetchall()
    print(json.dumps({'candidates':sum(n for _,n in data),'statuses':dict(data),
                      'source_urls':con.execute('SELECT COUNT(*) FROM fetch_history').fetchone()[0],
                      'evidences':con.execute('SELECT COUNT(*) FROM provenance').fetchone()[0]},
                     indent=2,ensure_ascii=False))


def main(argv=None):
    p = argparse.ArgumentParser(description='Z39 Atlas 2.0: passive endpoint discovery + MARC checks')
    p.add_argument('--db',default='z39-atlas.sqlite3',help='SQLite database path')
    p.add_argument('-v','--verbose',action='store_true')
    subs = p.add_subparsers(dest='command',required=True)
    h = subs.add_parser('harvest',help='respectfully harvest published public endpoint metadata')
    h.add_argument('--url',action='append',help='Public HTTPS documentation URLs (repeatable)')
    h.add_argument('--urls-file',help='Text file with approved public HTTPS documentation URLs')
    h.add_argument('--no-defaults',action='store_true')
    h.add_argument('--follow-links',action='store_true',help='Follow links only on approved source domains')
    h.add_argument('--max-pages',type=int,default=60)
    h.add_argument('--max-bytes',type=int,default=4_000_000)
    h.add_argument('--delay',type=float,default=2.0)
    h.set_defaults(func=cmd_harvest)
    i = subs.add_parser('import-csv',help='Import existing explorer CSV or seed TSV')
    i.add_argument('file')
    i.set_defaults(func=cmd_import)
    pr = subs.add_parser('probe',help='Run limited MARC checks on explicit allowlisted endpoints')
    pr.add_argument('--allowlist',required=True,help='File: one explicitly authorized hostname per line')
    pr.add_argument('--ack-authorized',action='store_true',help='Affirm permission for each target')
    pr.add_argument('--infer-missing',action='store_true',help='Fill missing port/base only for allowlisted hosts')
    pr.add_argument('--workers',type=int,default=2)
    pr.add_argument('--host-interval',type=float,default=10.0)
    pr.add_argument('--timeout',type=int,default=25)
    pr.add_argument('--max-hours',type=float,default=24.0)
    pr.add_argument('--max-targets',type=int,default=5000)
    pr.add_argument('--recheck-hours',type=float,default=168.0)
    pr.set_defaults(func=cmd_probe)
    sd = subs.add_parser('search-docs',help='Find public documentation via Brave Search API (no probing)')
    sd.add_argument('--query',action='append',help='Search query (repeatable; max 20)')
    sd.add_argument('--queries-file',help='Optional text file with search queries')
    sd.add_argument('--count',type=int,default=10)
    sd.add_argument('--delay',type=float,default=2.0)
    sd.add_argument('--output',required=True,help='Text file of publicly found document URLs')
    sd.set_defaults(func=cmd_search_docs)
    ex = subs.add_parser('export',help='Export current candidates and validation status to CSV')
    ex.add_argument('--output',required=True)
    ex.add_argument('--confirmed-only',action='store_true')
    ex.add_argument('--host')
    ex.set_defaults(func=cmd_export)
    st = subs.add_parser('stats',help='Print database statistics')
    st.set_defaults(func=cmd_stats)
    ad = subs.add_parser('auto-discover', aliases=['pipeline'],
                         help='harvest + MARC tests + SQLite in one run, with its progress in run_state')
    who = ad.add_mutually_exclusive_group(required=True)
    who.add_argument('--published', action='store_true',
                     help='test the complete host:port/database endpoints that public HTTPS documents publish '
                          '(no allowlist; recorded in auto_allowed; nothing guessed)')
    who.add_argument('--allowlist', help='test only these hosts, as probe does (needs --ack-authorized)')
    ad.add_argument('--ack-authorized', action='store_true')
    ad.add_argument('--known', action='append', help='list of endpoints already in Koha / the panel: not tested '
                                                     '(z3950_direct.json, z3950_targets.json, CSV, TSV, host:port/db)')
    ad.add_argument('--background', action='store_true', help='detach and return at once (log next to the DB)')
    ad.add_argument('--log', help='log file for --background (default: the DB name with .log)')
    ad.add_argument('--skip-harvest', action='store_true', help='only test what the database already has')
    ad.add_argument('--url', action='append')
    ad.add_argument('--urls-file')
    ad.add_argument('--no-defaults', action='store_true')
    ad.add_argument('--max-pages', type=int, default=60)
    ad.add_argument('--max-bytes', type=int, default=4_000_000)
    ad.add_argument('--delay', type=float, default=3.0)
    ad.add_argument('--refetch-hours', type=float, default=24.0,
                    help='a page read in the last N hours is not read again (resume)')
    ad.add_argument('--workers', type=int, default=2)
    ad.add_argument('--host-interval', type=float, default=10.0)
    ad.add_argument('--timeout', type=int, default=25)
    ad.add_argument('--max-hours', type=float, default=24.0)
    ad.add_argument('--max-targets', type=int, default=5000)
    ad.add_argument('--recheck-hours', type=float, default=168.0)
    ad.set_defaults(func=cmd_auto_discover)
    ss = subs.add_parser('status', help='Print the background run state as JSON')
    ss.set_defaults(func=cmd_status)
    sp = subs.add_parser('stop', help='Ask the running auto-discover to stop')
    sp.set_defaults(func=cmd_stop)
    ns = subs.add_parser('new-servers', help='Confirmed marc_bibliographic servers not in the known lists')
    ns.add_argument('--known', action='append', help='z3950_direct.json, z3950_targets.json, CSV, TSV or host:port/db lines')
    ns.add_argument('--output', help='CSV file (default: JSON on stdout)')
    ns.set_defaults(func=cmd_new_servers)
    args = p.parse_args(argv)
    args.argv = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.command == 'harvest' and (args.max_pages < 1 or args.max_pages > 1000 or args.delay < 1 or args.max_bytes < 4096):
        p.error('harvest limits: 1 <= max-pages <= 1000, delay >= 1 second, max-bytes >= 4096')
    if args.command == 'search-docs' and (not 1 <= args.count <= 20 or args.delay < 1):
        p.error('search-docs limits: count 1..20, delay >= 1 second')
    if args.command == 'probe' and (not 1 <= args.workers <= 4 or args.host_interval < 5 or not 5 <= args.timeout <= 120 or not 1 <= args.max_targets <= 5000 or not 0 < args.max_hours <= 168 or args.recheck_hours < 1):
        p.error('probe limits: workers 1..4, host-interval >=5s, timeout 5..120s, max-targets 1..5000, max-hours <=168, recheck-hours >=1')
    if args.command in ('auto-discover', 'pipeline'):
        if args.max_pages < 1 or args.max_pages > 1000 or args.delay < 1 or args.max_bytes < 4096:
            p.error('harvest limits: 1 <= max-pages <= 1000, delay >= 1 second, max-bytes >= 4096')
        if (not 1 <= args.workers <= 4 or args.host_interval < 5 or not 5 <= args.timeout <= 120
                or not 1 <= args.max_targets <= 5000 or not 0 < args.max_hours <= 168 or args.recheck_hours < 1):
            p.error('probe limits: workers 1..4, host-interval >=5s, timeout 5..120s, max-targets 1..5000, '
                    'max-hours <=168, recheck-hours >=1')
    args.func(args)


if __name__ == '__main__':
    main()
