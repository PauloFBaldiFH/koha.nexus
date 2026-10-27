#!/usr/bin/env python3
"""Z39 Atlas: passive, public Z39.50 discovery + allowlisted MARC verification.

No Internet-wide network sweeping, authentication guessing, or access-control bypass.
Python >= 3.10, standard library. Optional dependency: yaz-client.
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
    con = sqlite3.connect(str(path), timeout=30)
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


def cmd_harvest(args):
    sources = list(DEFAULT_SOURCES) if not args.no_defaults else []
    if args.urls_file:
        sources.extend(x.strip() for x in Path(args.urls_file).read_text(encoding='utf-8').splitlines()
                       if x.strip() and not x.lstrip().startswith('#'))
    sources.extend(args.url or [])
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
    found = 0
    con = init_db(Path(args.db))
    last_request = {}
    while queue and len(seen) < args.max_pages:
        u = queue.pop(0)
        if u in seen or not public_url_ok(u, domains):
            continue
        seen.add(u)
        host = urlparse(u).hostname.lower()
        delay = max(0, args.delay - (time.monotonic() - last_request.get(host, 0)))
        if delay: time.sleep(delay)
        last_request[host] = time.monotonic()
        try:
            raw, is_html, final = read_public_page(u, domains, robots, max_bytes=args.max_bytes)
            matches, links = extract_endpoints(raw, is_html)
            with con:
                for target_host, port, base, excerpt in matches:
                    if save_candidate(con,target_host,port,base, source=final,excerpt=excerpt):
                        found += 1
                con.execute('''INSERT INTO fetch_history(url,status,checked_at,detail) VALUES(?,?,?,?)
                               ON CONFLICT(url) DO UPDATE SET status=excluded.status,checked_at=excluded.checked_at,detail=excluded.detail''',
                            (u,'ok',utcnow(),f'endpoints={len(matches)}'))
            LOG.info('Public source %s: %d parsed, %d new total', u, len(matches), found)
            if args.follow_links:
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
    print(json.dumps({'pages_visited':len(seen), 'new_candidates':found, 'total_candidates':con.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]},ensure_ascii=False,indent=2))


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


def cmd_probe(args):
    if not args.ack_authorized:
        raise SystemExit('Active tests require --ack-authorized and a host allowlist you control/are permitted to test.')
    hosts = load_allowlist(args.allowlist)
    con = init_db(Path(args.db))
    targets = candidates_to_probe(con,hosts,args.recheck_hours,args.infer_missing,args.max_targets)
    if not targets:
        print('No eligible explicitly allowlisted endpoints to test.'); return
    if not shutil.which('yaz-client'):
        raise SystemExit('Install YAZ first: sudo apt install yaz')
    LOG.info('Active testing: %d allowlisted endpoints, max workers=%d',len(targets),args.workers)
    deadline = time.monotonic() + args.max_hours*3600
    last_host_access = {}
    host_lock = {}
    host_lock_mutex = threading.Lock()
    db_lock = threading.Lock()

    def do_one(item):
        host,port,base = item
        with host_lock_mutex:
            lock = host_lock.setdefault(host,threading.Lock())
        with lock:
            pause = max(0,args.host_interval - (time.monotonic()-last_host_access.get(host,0)))
            if pause: time.sleep(pause)
            last_host_access[host] = time.monotonic()
            try:
                result = yaz_probe(host,port,base,args.timeout)
            except (ValueError, RuntimeError, OSError) as exc:
                result = ('error',None,None,None,None,str(exc)[:240],0)
            with db_lock:
                now = utcnow()
                with con:
                    save_candidate(con,host,port,base,source='inference:allowlisted' if args.infer_missing else '')
                    con.execute('''UPDATE candidates SET status=?,hits=?,marc_type=?,marc_bytes=?,leader=?,error=?,
                                   latency_ms=?,checked_at=?,updated_at=? WHERE key=?''',
                                (*result, now, now,key_for(host,port,base)))
            LOG.info('%s %s:%s/%s (%sms)',result[0],host,port,base,result[-1])
            return result[0]

    results = {}
    # At most `workers` outstanding tasks. Stops scheduling at the time budget
    # instead of enqueuing the entire backlog on day one.
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending = set()
        items = iter(targets)
        exhausted = False
        while pending or not exhausted:
            while not exhausted and len(pending) < args.workers and time.monotonic() < deadline:
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
            if time.monotonic() >= deadline:
                exhausted = True
    print(json.dumps({'tested':sum(results.values()),'statuses':results},ensure_ascii=False,indent=2))



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
    p = argparse.ArgumentParser(description='Z39 Atlas 2.0: passive endpoint discovery + allowlisted MARC checks')
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
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.command == 'harvest' and (args.max_pages < 1 or args.max_pages > 1000 or args.delay < 1 or args.max_bytes < 4096):
        p.error('harvest limits: 1 <= max-pages <= 1000, delay >= 1 second, max-bytes >= 4096')
    if args.command == 'search-docs' and (not 1 <= args.count <= 20 or args.delay < 1):
        p.error('search-docs limits: count 1..20, delay >= 1 second')
    if args.command == 'probe' and (not 1 <= args.workers <= 4 or args.host_interval < 5 or not 5 <= args.timeout <= 120 or not 1 <= args.max_targets <= 5000 or not 0 < args.max_hours <= 168 or args.recheck_hours < 1):
        p.error('probe limits: workers 1..4, host-interval >=5s, timeout 5..120s, max-targets 1..5000, max-hours <=168, recheck-hours >=1')
    args.func(args)


if __name__ == '__main__':
    main()
