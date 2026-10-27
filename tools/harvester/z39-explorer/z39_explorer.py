#!/usr/bin/env python3
"""Z39.50 Explorer: discovery from public catalogues + non-invasive protocol verification.
Python 3.9+, Debian/Ubuntu packages: yaz, python3-requests, python3-bs4.
No arbitrary CIDR scan; only explicitly published endpoints are queried.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import ipaddress
import json
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
DEFAULT_STATE = Path(os.getenv('Z39_STATE_DIR', '/var/lib/z39-explorer'))
USER_AGENT = 'Z39Explorer/1.0 (library interoperability research; publicly listed targets; 2026)'
HEADERS = {'User-Agent': USER_AGENT}
KOHA_WIKI = 'https://wiki.koha-community.org/wiki/Koha_Open_Z39.50_Sources'
ZBRARY = 'https://www.z-brary.com/'
IRSPY = 'http://irspy.indexdata.com:8018/IR-Explain---1'
MAX_DOWNLOAD = 5_000_000
MAX_TARGETS = 12000  # failsafe against accidental unbounded source injection
MAX_OUTPUT = 150_000
DNS_CACHE = {}
DNS_LOCK = threading.Lock()
HOST_LOCKS = {}
LOCK_LOCK = threading.Lock()
HOST_LAST = {}
HITS_RE = re.compile(r'Number of hits:\s*(\d+)', re.I)
HOST_RE = re.compile(r'^[a-z0-9][a-z0-9.-]{0,252}$', re.I)
DB_RE = re.compile(r'^[A-Za-z0-9_+.-]{1,110}$')
STATUS_PRIORITY = {'marc_authority': 0, 'marc_bibliographic': 0, 'marc_other': 1,
                   'search_positive': 2, 'search_zero': 3, 'init_only': 4,
                   'denied': 5, 'timed_out': 6, 'unreachable': 7, 'not_tested': 8}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def clean(value, limit=250):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def normalize(row):
    host = clean(row.get('host', ''), 255).strip('.').lower()
    host = host.removeprefix('tcp:')
    host = host.strip('[]')
    try:
        port = int(row.get('port', 0))
    except (ValueError, TypeError):
        return None
    base = clean(row.get('database', ''), 110).strip('/')
    if not host or not HOST_RE.fullmatch(host) or not DB_RE.fullmatch(base):
        return None
    if not 1 <= port <= 65535:
        return None
    if host in {'localhost', '0.0.0.0'} or host.endswith(('.localhost', '.local', '.internal')):
        return None
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            return None
    except ValueError:
        pass
    kind = clean(row.get('kind', 'unknown'), 30).lower()
    if kind not in ('bibliographic', 'authority', 'unknown'):
        kind = 'unknown'
    name = clean(row.get('name', host), 150) or host
    src = clean(row.get('source', 'manual'), 400)
    username = clean(row.get('username', ''), 80)
    password = clean(row.get('password', ''), 80)
    # YAZ command file is line oriented. Only allow simple non-space public guest strings.
    if (username or password) and not all(re.fullmatch(r'[A-Za-z0-9._@-]{1,80}', x) for x in (username, password)):
        username = password = ''
    return dict(host=host, port=port, database=base, name=name, kind=kind,
                source=src, username=username, password=password)


def connect_db(dbfile):
    dbfile.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(dbfile), timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=30000')
    db.execute('''CREATE TABLE IF NOT EXISTS targets (
      id INTEGER PRIMARY KEY, host TEXT NOT NULL, port INTEGER NOT NULL,
      database TEXT NOT NULL, name TEXT, kind TEXT, source TEXT,
      username TEXT DEFAULT '', password TEXT DEFAULT '',
      discovered_at TEXT, checked_at TEXT, status TEXT DEFAULT 'not_tested',
      initialized INTEGER DEFAULT 0, search_success INTEGER DEFAULT 0,
      hit_count INTEGER DEFAULT 0, marc_type TEXT DEFAULT '',
      marc_size INTEGER DEFAULT 0, latency_ms INTEGER DEFAULT 0, error TEXT DEFAULT '',
      UNIQUE(host,port,database))''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_targets_status ON targets(status)')
    db.commit()
    return db


def insert_many(db, rows, limit):
    count = 0
    for item in rows:
        target = normalize(item)
        if not target:
            continue
        if db.execute('SELECT COUNT(*) FROM targets').fetchone()[0] >= limit:
            break
        # Keep better curated seed metadata. The first source wins, unknown gets upgraded.
        db.execute('''INSERT INTO targets(host,port,database,name,kind,source,username,password,discovered_at)
                      VALUES (:host,:port,:database,:name,:kind,:source,:username,:password,:now)
                      ON CONFLICT(host,port,database) DO UPDATE SET
                        kind=CASE WHEN targets.kind='unknown' THEN excluded.kind ELSE targets.kind END,
                        source=CASE WHEN targets.source='' THEN excluded.source ELSE targets.source END''',
                   {**target, 'now': utc()})
        count += 1
    db.commit()
    return count


def read_seeds(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row.get('host') and not row['host'].lstrip().startswith('#'):
                yield row


def fetch_html(url, timeout=18):
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=True)
    r.raise_for_status()
    if urlparse(r.url).scheme not in ('http', 'https'):
        raise RuntimeError('unexpected redirect')
    total, chunks = 0, []
    for part in r.iter_content(chunk_size=65536):
        total += len(part)
        if total > MAX_DOWNLOAD:
            raise RuntimeError('page too large')
        chunks.append(part)
    r.close()
    return BeautifulSoup(b''.join(chunks), 'html.parser')


def tr_cells(table):
    for tr in table.select('tr'):
        cells = tr.find_all(['th', 'td'], recursive=False)
        if cells:
            yield [clean(x.get_text(' ', strip=True), 400) for x in cells]


def source_koha():
    soup = fetch_html(KOHA_WIKI)
    rows = []
    for table in soup.select('table'):
        for cells in tr_cells(table):
            if len(cells) < 4 or cells[1].lower() in ('address', 'hostname'):
                continue
            rows.append(dict(name=cells[0], host=cells[1], port=cells[2],
                             database=cells[3], kind='bibliographic', source=KOHA_WIKI))
    logging.info('Koha wiki: %d raw candidates', len(rows))
    return rows


def source_zbrary():
    start = fetch_html(ZBRARY)
    urls = {ZBRARY}
    for link in start.select('a[href]'):
        href = link.get('href', '')
        u = urljoin(ZBRARY, href)
        parsed = urlparse(u)
        slug = parsed.path.strip('/').lower()
        if parsed.netloc.lower() in ('www.z-brary.com', 'z-brary.com') and re.fullmatch(r'[a-z](-[a-z])?', slug):
            urls.add('https://www.z-brary.com/' + slug)
    # If navigation is JS-rendered, the explicit A-Z section URLs still work in this directory.
    if len(urls) < 6:
        urls.update('https://www.z-brary.com/' + c for c in 'bcdefghijklmnopqrstuvw')
        urls.add('https://www.z-brary.com/x-z')
    rows = []
    failures = 0
    for i, url in enumerate(sorted(urls)):
        try:
            soup = start if url == ZBRARY else fetch_html(url)
            for table in soup.select('table'):
                for cells in tr_cells(table):
                    # Site columns: Host, Target, Address, Port, Database, Documentation, Notes
                    if len(cells) < 5 or cells[2].lower() in ('address', 'hostname'):
                        continue
                    hints = ' '.join(cells[:2]).lower()
                    kind = 'authority' if any(k in hints for k in ('authorit', 'autoridad', 'autoridade', 'normdatei')) else 'bibliographic'
                    rows.append(dict(name=f'{cells[0]} - {cells[1]}', host=cells[2],
                                     port=cells[3], database=cells[4], kind=kind, source=url))
        except Exception as e:
            failures += 1
            logging.warning('Directory unavailable (%s): %s', url, clean(e, 140))
        if i % 4 == 0:
            logging.info('Z-BRARY pages %d/%d; extracted %d entries', i+1, len(urls), len(rows))
        time.sleep(0.6)
    logging.info('Z-BRARY: %d raw candidates, %d failed pages', len(rows), failures)
    return rows



def source_irspy():
    """Optional public SRU registry (port 8018 is commonly firewall-blocked).
    Reference: https://metacpan.org/dist/ZOOM-IRSpy/view/lib/ZOOM/IRSpy/WebService.pod
    """
    rows = []
    first = 1
    seen = set()
    for page in range(0, 80):  # <= 4000 entries, server-side 50 records per page
        params = dict(version='1.1', operation='searchRetrieve',
                      query='cql.allRecords=1', startRecord=first,
                      maximumRecords=50, recordSchema='zeerex')
        response = requests.get(IRSPY, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        if len(response.content) > MAX_DOWNLOAD:
            raise RuntimeError('IRSpy page too large')
        root = ET.fromstring(response.content)
        counter = root.find('.//{*}numberOfRecords')
        maximum = int(counter.text) if counter is not None and (counter.text or '').isdigit() else 4000
        records = root.findall('.//{*}recordData')
        if not records:
            break
        for rec in records:
            server = rec.find('.//{*}serverInfo')
            if server is None or server.attrib.get('protocol', '').lower() not in ('z39.50', 'z3950'):
                continue
            host, port, base = [server.find('./{*}' + x) for x in ('host', 'port', 'database')]
            if any(x is None for x in (host, port, base)):
                continue
            hostname = clean(host.text)
            porttext = clean(port.text)
            dbname = clean(base.text)
            key = (hostname, porttext, dbname)
            if key in seen:
                continue
            seen.add(key)
            title = rec.find('.//{*}databaseInfo/{*}title')
            name = clean(title.text if title is not None else hostname)
            hint = ' '.join((name, dbname)).lower()
            kind = 'authority' if re.search(r'authorit|autoridad|autoridade|normdatei', hint) else 'unknown'
            rows.append(dict(name=name, host=hostname, port=porttext,
                             database=dbname, kind=kind, source=IRSPY))
        first += len(records)
        logging.info('IRSpy: %d/%d SRU records (Z39.50 candidates %d)', first - 1, maximum, len(rows))
        if first > maximum:
            break
        time.sleep(0.7)
    return rows


def public_dns(host):
    with DNS_LOCK:
        if host in DNS_CACHE:
            return DNS_CACHE[host]
    try:
        items = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        ips = {item[4][0] for item in items}
        ok = bool(ips) and all(ipaddress.ip_address(x).is_global for x in ips)
        result = (ok, 'public DNS' if ok else 'DNS resolves to non-public IP')
    except OSError as e:
        result = (False, f'DNS error: {e}')
    with DNS_LOCK:
        DNS_CACHE[host] = result
    return result


def host_semaphore(host):
    with LOCK_LOCK:
        if host not in HOST_LOCKS:
            HOST_LOCKS[host] = threading.Lock()
        return HOST_LOCKS[host]


def marc_record(blob):
    """Verify ISO2709 record boundaries AND MARC21 directory tags before classification.

    A valid MARC21 bibliographic record normally contains 245 (title statement).
    A MARC21 authority record has leader/06=z plus an authorized 1XX heading.
    Uncertain formats, including possible UNIMARC, remain 'other'.
    """
    offset = 0
    kinds = set()
    max_size = 0
    auth_1xx = {'100', '110', '111', '130', '148', '150', '151', '155',
                '180', '181', '182', '185'}
    while offset + 25 <= len(blob):
        leader = blob[offset:offset + 24]
        if not leader[:5].isdigit() or not leader[12:17].isdigit():
            break
        length, base = int(leader[:5]), int(leader[12:17])
        if not (30 <= length <= 150000 and 25 <= base < length and offset + length <= len(blob)):
            break
        one = blob[offset:offset + length]
        if one[-1:] != b'\x1d' or one[base-1:base] != b'\x1e':
            break
        directory = one[24:base - 1]
        if not directory or len(directory) % 12:
            break
        tags = set()
        valid = True
        for i in range(0, len(directory), 12):
            entry = directory[i:i + 12]
            if not (entry[:3].isdigit() and entry[3:7].isdigit() and entry[7:12].isdigit()):
                valid = False
                break
            start, size = int(entry[7:12]), int(entry[3:7])
            if size < 1 or base + start + size > length - 1:
                valid = False
                break
            if one[base + start + size - 1:base + start + size] != b'\x1e':
                valid = False
                break
            tags.add(entry[:3].decode('ascii'))
        if not valid:
            break
        rectype = chr(leader[6]).lower()
        if rectype == 'z' and (tags & auth_1xx):
            kind = 'authority'
        elif rectype in 'acdefgijkmoprt' and '245' in tags:
            kind = 'bibliographic'
        else:
            kind = 'other'
        kinds.add(kind)
        max_size = max(max_size, length)
        offset += length
    if not kinds:
        return '', 0
    if len(kinds) == 1:
        return kinds.pop(), max_size
    return 'other', max_size


def probe(target, timeout, host_pause):
    result = dict(status='unreachable', initialized=0, search_success=0, hit_count=0,
                  marc_type='', marc_size=0, latency_ms=0, error='')
    started = time.monotonic()
    host = target['host']
    ok, desc = public_dns(host)
    if not ok:
        result['status'], result['error'] = 'unreachable', clean(desc, 180)
        return result
    # One active probe per physical host; avoids hammering shared catalog gateways.
    with host_semaphore(host):
        since = time.monotonic() - HOST_LAST.get(host, 0)
        if since < host_pause:
            time.sleep(host_pause - since)
        HOST_LAST[host] = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix='z39-probe-') as tmp:
                commands = []
                if target.get('username') and target.get('password'):
                    commands.append('authentication ' + target['username'] + '/' + target['password'])
                commands += [f"open tcp:{host}:{target['port']}/{target['database']}",
                             'format usmarc', 'elements F', 'lslb 0', 'ssub 0',
                             'find @attr 1=4 history', 'show 1',
                             'find @attr 1=1003 shakespeare', 'show 1',
                             'find @attr 1=4 brasil', 'show 1', 'quit']
                cmds = Path(tmp) / 'commands.txt'
                output = Path(tmp) / 'records.mrc'
                cmds.write_text('\n'.join(commands) + '\n', encoding='utf-8')
                proc = subprocess.run(['yaz-client', '-f', str(cmds), '-m', str(output)],
                                      cwd=tmp, capture_output=True, timeout=timeout, check=False)
                display = (proc.stdout + b'\n' + proc.stderr)[:MAX_OUTPUT].decode('utf-8', 'replace')
                connected = bool(re.search(r'Connection accepted|Connecting\.\.\.OK', display, re.I))
                hits = [int(x) for x in HITS_RE.findall(display)]
                search_ok = 'Search was a success' in display
                record_kind, record_size = marc_record(output.read_bytes()) if output.exists() else ('', 0)
                result.update(initialized=int(connected), search_success=int(search_ok),
                              hit_count=max(hits, default=0), marc_type=record_kind,
                              marc_size=record_size)
                if record_kind:
                    result['status'] = 'marc_' + record_kind
                elif any(x > 0 for x in hits):
                    result['status'] = 'search_positive'
                elif search_ok:
                    result['status'] = 'search_zero'
                elif connected:
                    result['status'] = 'init_only'
                elif re.search(r'Authentication|Access denied|not authorized|auth required', display, re.I):
                    result['status'] = 'denied'
                else:
                    result['status'] = 'unreachable'
                if result['status'] in ('unreachable', 'denied', 'init_only'):
                    # Never expose public guest credentials or the command file.
                    safe = re.sub(r'(?i)(user|password|auth)[^\n]{0,70}', r'\1 [redacted]', display)
                    result['error'] = clean(safe[-400:], 200)
        except subprocess.TimeoutExpired:
            result['status'], result['error'] = 'timed_out', f'YAZ timed out after {timeout}s'
        except Exception as exc:
            result['status'], result['error'] = 'unreachable', clean(exc, 180)
        finally:
            HOST_LAST[host] = time.monotonic()
    result['latency_ms'] = int((time.monotonic() - started) * 1000)
    return result


def export(db, directory):
    directory.mkdir(parents=True, exist_ok=True)
    db.row_factory = sqlite3.Row
    all_rows = [dict(x) for x in db.execute('''SELECT name, host, port, database, kind,
        source, status, initialized, search_success, hit_count, marc_type, marc_size,
        latency_ms, checked_at, error FROM targets
        ORDER BY CASE status WHEN 'marc_authority' THEN 0 WHEN 'marc_bibliographic' THEN 1
        WHEN 'marc_other' THEN 2 WHEN 'search_positive' THEN 3 WHEN 'search_zero' THEN 4
        ELSE 5 END, host, database''')]
    safe_cols = ('name', 'host', 'port', 'database', 'kind', 'source', 'status',
                 'initialized', 'search_success', 'hit_count', 'marc_type', 'marc_size',
                 'latency_ms', 'checked_at', 'error')

    def excel_safe(v):
        if isinstance(v, str) and v[:1] in ('=', '+', '-', '@'):
            return "'" + v
        return v

    def write(name, rows, cols=safe_cols):
        with open(directory / name, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            for r in rows:
                w.writerow({c: excel_safe(r.get(c, '')) for c in cols})

    write('todos_candidatos.csv', all_rows)
    write('bibliograficos_confirmados.csv', [r for r in all_rows if r['marc_type'] == 'bibliographic'])
    write('autoridades_confirmadas.csv', [r for r in all_rows if r['marc_type'] == 'authority'])
    write('pesquisa_sem_marc.csv', [r for r in all_rows if r['status'] in ('search_positive', 'search_zero', 'init_only')])
    write('nao_validados.csv', [r for r in all_rows if r['status'] in ('not_tested', 'unreachable', 'timed_out', 'denied')])
    ready = []
    for r in all_rows:
        if r['status'] in ('marc_bibliographic', 'marc_authority'):
            ready.append({'name': r['name'], 'host': r['host'], 'port': r['port'],
                          'database': r['database'], 'syntax': 'USMARC',
                          'encoding': 'utf8 (check source metadata)',
                          'record_type': r['marc_type'], 'source': r['source'],
                          'checked_at': r['checked_at']})
    write('koha_para_revisao.csv', ready,
          ('name', 'host', 'port', 'database', 'syntax', 'encoding', 'record_type', 'source', 'checked_at'))
    summary = {'generated_at': utc(), 'candidates': len(all_rows),
               'statuses': {s: sum(1 for r in all_rows if r['status'] == s)
                            for s in sorted({r['status'] for r in all_rows})},
               'confirmed_bibliographic': sum(r['marc_type'] == 'bibliographic' for r in all_rows),
               'confirmed_authority': sum(r['marc_type'] == 'authority' for r in all_rows),
               'note': 'Only valid ISO2709 MARC leader is evidence for confirmed type; do not bulk import automatically.'}
    (directory / 'resumo.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    logging.info('Report: %s', json.dumps(summary, ensure_ascii=False))
    return summary


def scan(args, db):
    logging.info('Discovering curated seed endpoints: %s', args.seeds)
    insert_many(db, read_seeds(args.seeds), args.limit)
    if not args.no_web:
        for source in (source_koha, source_zbrary, source_irspy):
            try:
                records = source()
                num = insert_many(db, records, args.limit)
                logging.info('%s: processed %d rows', source.__name__, num)
            except Exception as exc:
                logging.warning('%s discovery failed: %s', source.__name__, clean(exc, 200))
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.recheck_days)).isoformat()
    db.row_factory = sqlite3.Row
    todo = [dict(r) for r in db.execute('''SELECT * FROM targets
       WHERE checked_at IS NULL OR checked_at < ?
       ORDER BY CASE WHEN source LIKE '%loc.gov%' THEN 0
                     WHEN source LIKE '%bn.gov.ar%' THEN 1
                     WHEN source LIKE '%koha-community.org%' THEN 2 ELSE 3 END, id LIMIT ?''',
        (cutoff, args.limit))]
    export(db, args.output)  # initial inventory is immediately visible to users
    logging.info('Queued %d targets (concurrency=%d, time limit=%ds each, one host at a time)',
                 len(todo), args.workers, args.timeout)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, x, args.timeout, args.host_pause): x for x in todo}
        try:
            for task in concurrent.futures.as_completed(futures):
                item = futures[task]
                try:
                    outcome = task.result()
                except Exception as exc:
                    outcome = dict(status='unreachable', initialized=0, search_success=0,
                                   hit_count=0, marc_type='', marc_size=0,
                                   latency_ms=0, error=clean(exc, 180))
                db.execute('''UPDATE targets SET checked_at=?, status=?, initialized=?,
                    search_success=?, hit_count=?, marc_type=?, marc_size=?, latency_ms=?, error=?
                    WHERE id=?''', (utc(), outcome['status'], outcome['initialized'],
                                   outcome['search_success'], outcome['hit_count'], outcome['marc_type'],
                                   outcome['marc_size'], outcome['latency_ms'], outcome['error'], item['id']))
                db.commit()  # preserve after each target even on interruption
                done += 1
                if done % 10 == 0 or outcome['status'].startswith('marc_'):
                    logging.info('%d/%d | %-18s | %s:%s/%s', done, len(todo), outcome['status'],
                                 item['host'], item['port'], item['database'])
                if done % 25 == 0:
                    export(db, args.output)
        except KeyboardInterrupt:
            logging.warning('Interrupted. Results remain in SQLite. Re-run to resume.')
            for fut in futures:
                fut.cancel()
            raise
    return export(db, args.output)


def main():
    p = argparse.ArgumentParser(description='Public Z39.50 server discovery and MARC validation for Koha')
    p.add_argument('action', nargs='?', default='scan', choices=('scan', 'report', 'discover'))
    p.add_argument('--state', type=Path, default=DEFAULT_STATE)
    p.add_argument('--seeds', type=Path, default=BASE / 'seeds.tsv')
    p.add_argument('--no-web', action='store_true', help='use only local seeds')
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--timeout', type=int, default=22)
    p.add_argument('--host-pause', type=float, default=3.0)
    p.add_argument('--recheck-days', type=int, default=30)
    p.add_argument('--limit', type=int, default=MAX_TARGETS)
    args = p.parse_args()
    if not (1 <= args.workers <= 16 and 6 <= args.timeout <= 120 and 1 <= args.host_pause <= 120
            and 1 <= args.recheck_days <= 3650 and 1 <= args.limit <= MAX_TARGETS):
        p.error('Invalid limits (workers 1-16, timeout 6-120, host pause 1-120, recheck 1-3650, limit 1-12000)')
    args.output = args.state / 'reports'
    args.state.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)])
    db = connect_db(args.state / 'candidates.sqlite3')
    if args.action == 'report':
        export(db, args.output)
    elif args.action == 'discover':
        insert_many(db, read_seeds(args.seeds), args.limit)
        if not args.no_web:
            for source in (source_koha, source_zbrary, source_irspy):
                try:
                    insert_many(db, source(), args.limit)
                except Exception as exc:
                    logging.warning('%s failed: %s', source.__name__, clean(exc, 200))
        export(db, args.output)
    else:
        scan(args, db)
    db.close()


if __name__ == '__main__':
    main()
