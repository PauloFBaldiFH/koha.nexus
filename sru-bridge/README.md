# SRU bridges: Zeus (UFSC) and Rede Pergamum (PUCPR)

## Zeus SRU bridge

A small FastAPI service that lets Koha copy-catalogue from **Catálogo Zeus**
(BU/UFSC, `https://catalogo.bu.ufsc.br/zbib/`) as if it were an ordinary
SRU 1.1 server. Most Brazilian university catalogues block Z39.50 (port 210)
at the border, but Zeus searches them over HTTP and puts each full ISO 2709
record in the result page as a `rawRecord` field. This service reads those
records and hands them to Koha as MARCXML.

```
Koha ──SRU 1.1 GET──▶ 127.0.0.1:5000/sru ──HTTPS, 15 targets a request──▶ Zeus
     ◀─searchRetrieveResponse (MARCXML)──              ◀─HTML with rawRecord─
```

## What a search does

1. Koha sends `GET /sru?version=1.1&operation=searchRetrieve&query=dc.isbn=…`.
   YAZ, Koha's ZOOM client, may send the same as a POST instead: a form
   (`application/x-www-form-urlencoded`) or an SRW SOAP envelope holding a
   `searchRetrieveRequest`. All three are read, and a SOAP request gets its
   answer back inside a SOAP envelope. Without a `query` or an `operation`
   the request is an `explain`.
2. The CQL query becomes one Zeus search: an ISBN clause (`isbn`,
   `dc.isbn`, `bath.isbn`, `dc.identifier`) is searched with `searchType=7`;
   anything else with `searchType=4` (title). A bare term that looks like an
   ISBN is searched as one. Zeus takes a single search string, so when Koha
   sends several clauses the ISBN wins, then the title.
3. The 16 targets (0, 1, 3, 5–14, 16–18) are split into groups of at most 15
   and all groups are fetched at once with `httpx`. One group failing still
   returns the others' records; all failing returns SRU diagnostic 1.
4. Every `rawRecord` in the pages is URL-decoded to ISO 2709 bytes and read
   with `pymarc` (MARC-8 records are converted to UTF-8). A record whose
   directory offsets don't match its bytes is rebuilt from its fields rather
   than dropped. The same record coming back twice is kept once.
5. The records are wrapped in an SRU 1.1 `searchRetrieveResponse`
   (`recordSchema` `marcxml`, `recordPacking` xml or string), paged with
   `startRecord` / `maximumRecords`. The short name matters: YAZ drops
   records whose `recordSchema` is the full `info:srw/schema/1/marcxml-v1.1`
   URI. Requests may still ask for either.

Results are cached in memory for 10 minutes, so Koha paging through a result
set does not search Zeus again. `GET /sru` with no query answers an SRU
`explain`; `GET /health` returns a small JSON status.

## Install

```sh
cd sru-bridge
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m zeus_sru          # listens on 127.0.0.1:5000
```

On a koha.nexus server the installer does all of this: adding the Zeus
target to Koha from the panel (or `config.sh --task sru-bridge`) installs the
bridge under `/usr/local/lib/koha-easy-installer/sru-bridge` and runs it as
the systemd unit `koha-zeus-sru`, enabled at boot. Check it with
`systemctl status koha-zeus-sru` and `ss -ltnp 'sport = :5000'`.

To run it as a service by hand, see [`deploy/zeus-sru.service`](deploy/zeus-sru.service).
Keep it on 127.0.0.1: it is meant for the Koha server only.

## Register it in Koha

*Administration › Z39.50/SRU servers › New SRU server*:

| Field | Value |
|---|---|
| Server name | Catálogo Zeus (UFSC) |
| Hostname | `127.0.0.1` |
| Port | `5000` |
| Database | `sru` |
| Record syntax | MARC21/USMARC |
| Encoding | utf8 |
| Timeout | 60 (Zeus can be slow) |
| SRU search fields | `title=dc.title,isbn=dc.isbn,srchany=cql.serverChoice` |

## Settings

All optional, read from the environment:

| Variable | Default | |
|---|---|---|
| `ZEUS_SRU_HOST` / `ZEUS_SRU_PORT` | `127.0.0.1` / `5000` | where to listen |
| `ZEUS_SRU_BASE_URL` | `https://catalogo.bu.ufsc.br/zbib/` | |
| `ZEUS_SRU_TARGETS` | `0,1,3,5,6,7,8,9,10,11,12,13,14,16,17,18` | Zeus target ids |
| `ZEUS_SRU_CHUNK_SIZE` | `15` | capped at 15, Zeus's limit |
| `ZEUS_SRU_TIMEOUT` | `30` | seconds per Zeus request |
| `ZEUS_SRU_CACHE_TTL` / `ZEUS_SRU_CACHE_SIZE` | `600` / `256` | `0` turns the cache off |
| `ZEUS_SRU_MAX_RECORDS` | `50` | ceiling on `maximumRecords` |
| `ZEUS_SRU_WORKERS` | `1` | uvicorn workers (each has its own cache) |
| `ZEUS_SRU_LOG_LEVEL` | `INFO` | |

## Tests

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests
```

The tests use a fake Zeus built from a real `rawRecord` (UNICAMP's
*Tabamex*, `tests/fixtures/rawrecord_tabamex.txt`); they never touch the
network. The HTML around it in `tests/fixtures/zeus_results.html` is a
stand-in: if Zeus's real page puts `rawRecord` somewhere the extractor
(`zeus_sru/zeus.py`) misses, save a real result page over that fixture and
adjust the patterns there.

## Rede Pergamum SRU bridge

The same directory holds a second bridge, `pergamum_sru`, for the **Rede
Pergamum** shared catalogue (PUCPR, site CRP,
`https://www.pergamum.pucpr.br/redepergamum/consultas/site_CRP/pesquisa.php`).
It uses the same SRU endpoint code as the Zeus bridge (`zeus_sru.app.sru_app`:
GET, form and SOAP requests, diagnostics, explain), the same venv and the same
requirements; only the catalogue behind it differs.

```
Koha ──SRU 1.1 GET──▶ 127.0.0.1:5006/sru ──Sajax GET──▶ pesquisa.php
     ◀─searchRetrieveResponse (MARCXML)──   ◀─result list, then one MARC text a record─
```

1. The CQL query becomes a Pergamum search: `ISBN`, `AUTOR`, else `TITULO`
   (same CQL reading as Zeus).
2. `rs=ajax_resultados` returns the hit list; the `mostrar_marc(<id>)` links
   give the acervo ids of the first 50 hits, which is the count Koha is told.
   That list is cached for 10 minutes, so Koha's first call
   (`maximumRecords=0`, the count only) and the page that follows cost one
   search, and the count call fetches no record.
3. For each record of the page, `rs=ajax_conteudo_pastas` returns its tabs;
   the MARC text between `<inicio>` and `<fim>` becomes MARCXML. Five records
   are fetched at once.
4. The MARC text is cleaned the way Koha needs it: bare `\r` line ends (left
   in, Koha stops with `Tag "\r0" is not a valid tag`), `&nbsp;` and other
   entities decoded (never with `unicode_escape`, which breaks accents),
   `\u001e` and characters XML cannot carry removed, and a datafield without a
   subfield, such as Pergamum's empty `852    $`, dropped (Koha stops with
   `Field 852 must have at least one subfield`).
5. Records go out with `recordSchema` `info:srw/schema/1/marcxml-v1.1`,
   `recordPacking` xml and `recordPosition`. If Koha shows hits but no
   records, set `PERGAMUM_SRU_RECORD_SCHEMA=marcxml` (what the Zeus bridge
   sends).

On a koha.nexus server, adding the "Catálogo Rede Pergamum" target from the
panel (or `config.sh --task pergamum-bridge`) installs it under
`/usr/local/lib/koha-easy-installer/sru-bridge` as the systemd unit
`koha-pergamum-sru`, enabled at boot, and writes Koha's row: host
`127.0.0.1`, port `5006`, database `sru`, SRU, MARC21, utf8, timeout 15,
`sru=get,sru_version=1.1`, `title=dc.title,isbn=dc.isbn,srchany=cql.serverChoice`.
By hand: `.venv/bin/python -m pergamum_sru`, or
[`deploy/pergamum-sru.service`](deploy/pergamum-sru.service).

| Variable | Default | |
|---|---|---|
| `PERGAMUM_SRU_HOST` / `PERGAMUM_SRU_PORT` | `127.0.0.1` / `5006` | where to listen |
| `PERGAMUM_SRU_BASE_URL` | the CRP `pesquisa.php` above | |
| `PERGAMUM_SRU_TIMEOUT` | `12` | seconds per Pergamum request |
| `PERGAMUM_SRU_PAGE_SIZE` | `50` | ids asked of Pergamum per search |
| `PERGAMUM_SRU_CONCURRENCY` | `5` | records fetched at once |
| `PERGAMUM_SRU_CACHE_TTL` / `PERGAMUM_SRU_CACHE_SIZE` | `600` / `512` | `0` turns the cache off |
| `PERGAMUM_SRU_MAX_RECORDS` | `50` | ceiling on `maximumRecords` |
| `PERGAMUM_SRU_RECORD_SCHEMA` | `info:srw/schema/1/marcxml-v1.1` | |
| `PERGAMUM_SRU_USER_AGENT` | a desktop Chrome string | |

Its tests (`tests/test_pergamum.py`) use stand-in pages built from the
working script's description (`tests/fixtures/pergamum_*.html`); they were
not captured from the live site. If a real search finds nothing, save a real
`ajax_resultados` and `ajax_conteudo_pastas` answer over those fixtures and
adjust the patterns in `pergamum_sru/pergamum.py`.
