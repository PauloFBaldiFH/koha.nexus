# koha.nexus Catalog Network

The shared catalogue of the koha.nexus libraries: one small service, run on
the project's Oracle VPS, that keeps a pool of MARC21 records and answers
Koha's copy-cataloguing searches as an ordinary SRU server. Each library
sends the records it catalogues; every library can copy them back.

```
Koha (any library) ──SRU GET, HTTPS──▶ Cloudflare ──Tunnel──▶ 127.0.0.1:8088/sru
koha.nexus library ──POST /api/records/sync (Bearer token)──▶       │
                                                        SQLite + FTS5 (one file)
```

- **Python** (FastAPI + Uvicorn), **SQLite** with an FTS5 full-text index;
  MARCXML is read and written with the standard library (no pymarc).
- Listens on `127.0.0.1:8088` only. The Cloudflare Tunnel publishes it
  (no open port on the VPS).

## Endpoints

| | |
|---|---|
| `GET /sru` | SRU 1.1 and 1.2, `operation=searchRetrieve` and `explain`. POST forms and SRW SOAP are read too (YAZ, Koha's client, may send them). Records go out as MARCXML with `recordSchema` `marcxml`, the name YAZ keeps (it drops records labelled with the full `info:srw/...` URI). `recordPacking` xml or string; paging with `startRecord` / `maximumRecords` (at most 50). |
| `POST /api/records/sync` | `Authorization: Bearer TOKEN`. Body: a MARCXML `<collection>` (or one `<record>`), or JSON `{"records": ["<record>…</record>", …]}`. At most 1000 records and 20 MB a request. Answers `{"library", "received", "inserted", "updated", "unchanged", "rejected": [{"index", "error"}]}`. |
| `GET /health` | `{"status": "ok", "version", "records": N, "sync": true}` |

### Searches (CQL)

Koha writes the query from the target's *SRU search fields*. The server reads:

| Index | Searches |
|---|---|
| `isbn`, `dc.isbn`, `bath.isbn`, `issn`, `dc.identifier` | the ISBN as ISBN-13 **and** ISBN-10, hyphens or not, and ISSNs (exact) |
| `title`, `dc.title` | title (245 $a $b $n $p) |
| `author`, `dc.creator`, `dc.author`, `name` | every name of the record (1XX and 7XX) |
| anything else, a bare term, `cql.serverChoice` | keywords: title, names, subjects (6XX), edition, publisher, series, notes, year, numbers |
| `cql.allRecords=1` | everything |

`and`, `or`, `not` and parentheses work (left to right, as CQL says).
`=` and `all` want every word, `any` one of them, `==` / `adj` / `exact` the
phrase; `casm*` is a prefix. Accents do not matter: `memorias` finds
*Memórias*. Results are newest first.

### What the pool keeps

A record must have a leader and a title (245). Its **9XX fields are removed**
on the way in (Koha's 942 item type, 952 items, 999 biblionumber): they
describe one library's copies, not the work. A record replaces the one in
the pool that shares one of its ISBNs/ISSNs, else the one with the same
title, main author and year: the newest version of a work wins, whoever
sends it. Sending the same record again changes nothing (`unchanged`).

## Install on the VPS

Ubuntu or Debian, as root (`sudo -i`). Python 3.9 or newer with SQLite's
FTS5 (Ubuntu 20.04 and later, Debian 11 and later have both). On Oracle
Linux use `dnf install -y python3.11 git` and `python3.11` instead of `python3`.

```sh
# 1. Packages and the code
apt-get update && apt-get install -y python3 python3-venv git curl openssl
git clone --depth 1 https://github.com/PauloFBaldiFH/koha.nexus.git /usr/local/src/koha.nexus
install -d /opt/koha-nexus-catalog
cp -r /usr/local/src/koha.nexus/catalog-network/nexus_catalog \
      /usr/local/src/koha.nexus/catalog-network/requirements.txt \
      /usr/local/src/koha.nexus/catalog-network/deploy /opt/koha-nexus-catalog/

# 2. Its own Python, and the FTS5 check
python3 -m venv /opt/koha-nexus-catalog/.venv
/opt/koha-nexus-catalog/.venv/bin/pip install -r /opt/koha-nexus-catalog/requirements.txt
/opt/koha-nexus-catalog/.venv/bin/python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print('FTS5 ok')"

# 3. A user of its own, the settings and the first library's token
useradd --system --home-dir /var/lib/koha-nexus-catalog --shell /usr/sbin/nologin nexus-catalog
install -d -m 750 -o root -g nexus-catalog /etc/koha-nexus-catalog
install -m 640 -o root -g nexus-catalog /opt/koha-nexus-catalog/deploy/catalog.env.example \
        /etc/koha-nexus-catalog/catalog.env
( umask 027; echo "biblioteca-1 $(openssl rand -hex 32)" > /etc/koha-nexus-catalog/tokens )
chgrp nexus-catalog /etc/koha-nexus-catalog/tokens

# 4. The service
cp /opt/koha-nexus-catalog/deploy/koha-nexus-catalog.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now koha-nexus-catalog
curl -s http://127.0.0.1:8088/health; echo
```

`systemctl status koha-nexus-catalog` and `journalctl -u koha-nexus-catalog`
show it running; the database is `/var/lib/koha-nexus-catalog/catalog.db`.
The unit is [`deploy/koha-nexus-catalog.service`](deploy/koha-nexus-catalog.service)
(own user, writes only its state directory, restarted on failure).

**Update** later: `git -C /usr/local/src/koha.nexus pull`, copy `nexus_catalog`
again as in step 1 (and `requirements.txt`, then step 2's `pip install`),
`systemctl restart koha-nexus-catalog`.

**Tokens**: one line per library in `/etc/koha-nexus-catalog/tokens`
(`name token`, see [`deploy/tokens.example`](deploy/tokens.example)). The
file is read again when it changes, so adding or removing a library needs
no restart. The name is recorded as the source of the records it sends.

### Cloudflare Tunnel

Add the hostname to the tunnel that already runs on the VPS, pointing at
`http://127.0.0.1:8088` ([`deploy/cloudflared-ingress.yml`](deploy/cloudflared-ingress.yml)):

```yaml
  - hostname: catalog.koha.nexus
    service: http://127.0.0.1:8088
```

above the final `- service: http_status:404`, then `systemctl restart
cloudflared` (or *Public Hostname › Add* in the dashboard for a
dashboard-managed tunnel). Check from anywhere:
`curl -s https://catalog.koha.nexus/health`.

Koha's client is not a browser: if Cloudflare's *Bot Fight Mode* or a
challenge is on for the zone, add a WAF skip rule for this hostname, or
Koha's searches get an HTML challenge page instead of SRU.

## Add it to Koha

The koha.nexus panel does it: **Z39.50 / SRU servers › Rede koha.nexus
(Catalogação Compartilhada)**. By hand, on the Koha server
([`deploy/koha-z3950servers.sql`](deploy/koha-z3950servers.sql)):

```sh
sudo koha-mysql INSTANCE <<'SQL'
DELETE FROM z3950servers
 WHERE recordtype = 'biblio' AND servername = 'Rede koha.nexus (Catalogação Compartilhada)';
INSERT INTO z3950servers (host, port, db, servername, checked, `rank`, syntax, encoding, timeout,
                          servertype, recordtype, sru_fields, sru_options, add_xslt)
VALUES ('https://catalog.koha.nexus', 443, 'sru', 'Rede koha.nexus (Catalogação Compartilhada)', 1, 1,
        'MARC21', 'utf8', 15, 'sru', 'biblio',
        'title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice',
        'sru=get,sru_version=1.1', '');
SQL
```

SRU mode, syntax **MARC21** (USMARC makes Koha expect ISO 2709 and show no
record), encoding **utf8** (Koha's name for UTF-8). A host starting with
`https://` makes Koha connect over HTTPS on port 443.

## Send records to the pool

From a koha.nexus library (the token in the environment, never on the
command line). Only the standard library is needed, so the system Python
runs it:

```sh
sudo koha-shell -c "/usr/share/koha/bin/export_records.pl --record-type=bibs --format=xml --filename=/tmp/bibs.xml" INSTANCE
read -rs NEXUS_CATALOG_TOKEN && export NEXUS_CATALOG_TOKEN   # paste the library's token
PYTHONPATH=/path/to/koha.nexus/catalog-network \
  python3 -m nexus_catalog push https://catalog.koha.nexus /tmp/bibs.xml
```

Or with curl: `curl -H "Authorization: Bearer $NEXUS_CATALOG_TOKEN" -H
"Content-Type: application/marcxml+xml" --data-binary @bibs.xml
https://catalog.koha.nexus/api/records/sync` (1000 records a request).

To seed the pool on the VPS itself, without HTTP:
`sudo -u nexus-catalog NEXUS_CATALOG_DB=/var/lib/koha-nexus-catalog/catalog.db
/opt/koha-nexus-catalog/.venv/bin/python -m nexus_catalog import FILE.xml --source NAME`
(run from `/opt/koha-nexus-catalog`).

## Settings

Read from the environment (`/etc/koha-nexus-catalog/catalog.env`):

| Variable | Default | |
|---|---|---|
| `NEXUS_CATALOG_HOST` / `NEXUS_CATALOG_PORT` | `127.0.0.1` / `8088` | where to listen |
| `NEXUS_CATALOG_DB` | `/var/lib/koha-nexus-catalog/catalog.db` | |
| `NEXUS_CATALOG_TOKENS_FILE` | (unit: `/etc/koha-nexus-catalog/tokens`) | `name token` lines |
| `NEXUS_CATALOG_TOKENS` | | `name:token,name2:token2`, besides the file |
| `NEXUS_CATALOG_MAX_RECORDS` | `50` | SRU page ceiling |
| `NEXUS_CATALOG_MAX_BODY` / `NEXUS_CATALOG_MAX_SYNC_RECORDS` | `20000000` / `1000` | one sync request |
| `NEXUS_CATALOG_TITLE` | Rede koha.nexus (Catalogação Compartilhada) | explain's title |
| `NEXUS_CATALOG_WORKERS` | `1` | uvicorn workers (SQLite WAL: readers run side by side) |
| `NEXUS_CATALOG_LOG_LEVEL` | `INFO` | |

## Tests

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests
```

The records in `tests/fixtures/collection.xml` were written for the tests.
The SRU answers were also read by `yaz-client` (YAZ 5, the library under
Koha's search) with `sru get 1.1` and `sru post 1.1`, `format marc21`.
