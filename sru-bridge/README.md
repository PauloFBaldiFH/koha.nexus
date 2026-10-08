# Zeus SRU bridge

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
   (`recordSchema` `info:srw/schema/1/marcxml-v1.1`, `recordPacking` xml or
   string), paged with `startRecord` / `maximumRecords`.

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

To run it as a service, see [`deploy/zeus-sru.service`](deploy/zeus-sru.service).
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
