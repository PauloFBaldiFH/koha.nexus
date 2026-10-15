# SRU bridges: Zeus (UFSC), Rede Pergamum (PUCPR) and the SRU gateway

## Zeus SRU bridge

A small FastAPI service that lets Koha copy-catalogue from **Catálogo Zeus**
(BU/UFSC, `https://catalogo.bu.ufsc.br/zeus/`) as if it were an ordinary
SRU 1.1 server. Most Brazilian university catalogues block Z39.50 (port 210)
at the border, but Zeus searches them over HTTP and puts each full ISO 2709
record in the result page as a `rawRecord` field. This service reads those
records and hands them to Koha as MARCXML.

```
Koha ──SRU 1.1 GET──▶ 127.0.0.1:5000/sru ──HTTPS, targets[0]──▶ Zeus
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
3. Only Zeus target 0 is asked by default: tested on a live server, it
   answers in under a second while the other federated targets often hang
   until the request times out. `ZEUS_SRU_TARGETS` adds others; they are
   split into groups of at most 15 (Zeus's limit) fetched at once with
   `httpx`. One group failing still returns the others' records; all failing
   returns SRU diagnostic 1.
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
| Timeout | 15 |
| SRU search fields | `title=dc.title,isbn=dc.isbn,srchany=cql.serverChoice` |

## Settings

All optional, read from the environment:

| Variable | Default | |
|---|---|---|
| `ZEUS_SRU_HOST` / `ZEUS_SRU_PORT` | `127.0.0.1` / `5000` | where to listen |
| `ZEUS_SRU_BASE_URL` | `https://catalogo.bu.ufsc.br/zeus/` | |
| `ZEUS_SRU_TARGETS` | `0` | Zeus target ids, comma-separated |
| `ZEUS_SRU_CHUNK_SIZE` | `15` | capped at 15, Zeus's limit |
| `ZEUS_SRU_TIMEOUT` | `15` | seconds per Zeus request |
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
| `PERGAMUM_SRU_TIMEOUT` | `30` | seconds per Pergamum request (the search spans every campus) |
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

## SRU gateway (one address, many catalogues)

`sru_gateway` serves every catalogue of
[`sru_gateway/targets.json`](sru_gateway/targets.json) from one port, one SRU
database per catalogue: `/sru/bn`, `/sru/ufsc`, `/sru/pergamum` and so on. It
is meant for the central server (the project's Oracle VPS), so Koha servers
need nothing installed: each catalogue is an ordinary SRU row in Koha.

```
Koha ──SRU 1.1──▶ <vps>:5000/sru/{id} ──▶ Zeus | Pergamum | Z39.50 | SRU
```

Each entry of `targets.json` has an `id`, a `name` and a `kind`:

| kind | goes to | needs |
|---|---|---|
| `zeus` | Catálogo Zeus (the `zeus_sru` client, `ZEUS_SRU_*` settings) | |
| `pergamum` | Rede Pergamum (the `pergamum_sru` client, `PERGAMUM_SRU_*` settings) | |
| `z3950` | a Z39.50 server (Init, Search, Present; the panel's BER client) | `host`, `port`, `db`, `syntax` USMARC/MARC21, `encoding` |
| `sru` | another SRU server | `url`; optional `version`, `schema`, `indexes` |
| `missing` | nothing yet | a search answers SRU diagnostic 1, "no catalogue address configured yet" |

Each entry also has a `status`: `verified` (searched live, MARC came back),
`untested` (an address nobody has searched through the gateway yet), `broken`
(its address does not answer) or `missing` (no address yet; kind `missing`).
This list replaces the old `STATUS_ALVOS.md`. Fill a `missing` entry with its
catalogue's published Z39.50 or SRU address and restart the service; never
guess one. UNIMARC servers are refused when the file is loaded, because
Koha's rows say MARC21 and the gateway does not convert. Discarded and not
listed: DNB (its SRU gives only RDF/XML, not MARC21) and Cambridge
(`44CAM_INST` is not a valid Alma institution).

<!-- targets:begin (generated by python -m sru_gateway.status_table --write) -->
22 verified, 3 untested, 2 broken, 26 missing (53 in all).

| id | Catalogue | Status | Kind | Address | Note |
|---|---|---|---|---|---|
| `bn` | Fundação Biblioteca Nacional (BN) | verified | zeus | Zeus `targets[0]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufsc` | Universidade Federal de Santa Catarina (UFSC) | verified | zeus | Zeus `targets[11]` | target_index to confirm with sru_gateway.zeus_labels. |
| `unicamp` | Universidade Estadual de Campinas (UNICAMP) | verified | zeus | Zeus `targets[6]` | target_index to confirm with sru_gateway.zeus_labels. |
| `usp` | Universidade de São Paulo (USP) | verified | zeus | Zeus `targets[4]` | target_index to confirm with sru_gateway.zeus_labels. |
| `uerj` | Universidade do Estado do Rio de Janeiro (UERJ) | verified | zeus | Zeus `targets[5]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufg` | Universidade Federal de Goiás (UFG) | verified | zeus | Zeus `targets[8]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufmg` | Universidade Federal de Minas Gerais (UFMG) | verified | zeus | Zeus `targets[9]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufpe` | Universidade Federal de Pernambuco (UFPE) | verified | zeus | Zeus `targets[10]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufscar` | Universidade Federal de São Carlos (UFSCar) | verified | zeus | Zeus `targets[12]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufu` | Universidade Federal de Uberlândia (UFU) | verified | zeus | Zeus `targets[14]` | target_index to confirm with sru_gateway.zeus_labels. |
| `ufrgs` | Universidade Federal do Rio Grande do Sul (UFRGS) | verified | zeus | Zeus `targets[16]` | target_index to confirm with sru_gateway.zeus_labels. |
| `uff` | Universidade Federal Fluminense (UFF) | verified | zeus | Zeus `targets[17]` | target_index to confirm with sru_gateway.zeus_labels. |
| `senado` | Rede Virtual de Bibliotecas (RVBI), Senado Federal | verified | zeus | Zeus `targets[2]` | target_index to confirm with sru_gateway.zeus_labels. |
| `mit` | Massachusetts Institute of Technology (MIT), EUA | verified | sru | `https://mit.alma.exlibrisgroup.com/view/sru/01MIT_INST` | Alma SRU, native MARCXML. |
| `upenn` | University of Pennsylvania (UPenn), EUA | verified | sru | `https://upenn.alma.exlibrisgroup.com/view/sru/01UPENN_INST` | Alma SRU, native MARCXML. |
| `oxford` | University of Oxford, Reino Unido | verified | sru | `https://oxford.alma.exlibrisgroup.com/view/sru/44OXF_INST` | Alma SRU, native MARCXML. |
| `pergamum` | Rede Pergamum | verified | pergamum | Rede Pergamum (CRP) | Dedicated Python backend (pergamum_sru). |
| `loc` | Library of Congress, EUA | verified | z3950 | `lx2.loc.gov:210/LCDB` |  |
| `yale` | Yale University, EUA | verified | sru | `https://yale.alma.exlibrisgroup.com/view/sru/01YALE_INST` | Alma SRU, native MARCXML. |
| `umich` | University of Michigan (UMich), EUA | verified | sru | `https://umich.alma.exlibrisgroup.com/view/sru/01UMICH_INST` | Alma SRU, native MARCXML. |
| `manchester` | University of Manchester, Reino Unido | verified | sru | `https://manchester.alma.exlibrisgroup.com/view/sru/44MAN_INST` | Alma SRU, native MARCXML. |
| `kcl` | King's College London, Reino Unido | verified | sru | `https://kcl.alma.exlibrisgroup.com/view/sru/44KCL_INST` | Alma SRU, native MARCXML. |
| `harvard` | Harvard University, EUA | untested | sru | `https://harvard-primo.hosted.exlibrisgroup.com/view/sru/01HVD_INST` | Listed as pending parameters in the 2026-10-11 status list; this Primo address has not been searched through the gateway. |
| `sbn_it` | Servizio Bibliotecario Nazionale, Itália | untested | z3950 | `opac.sbn.it:3950/nopac` | Port open from the VPS; no search tried yet. |
| `swb_de` | SWB-Online-Katalog, Alemanha | untested | z3950 | `z3950.k10plus.de:210/opac-de-627` | Port open from the VPS; no search tried yet. SWB is part of K10plus today. |
| `nlm` | National Library of Medicine, EUA | broken | z3950 | `locatorplus.nlm.nih.gov:7090/voyager` | LocatorPlus (Voyager) was retired when NLM moved to Alma; needs the Alma SRU address. |
| `bl` | British Library, UK | broken | z3950 | `z3950cat.bl.uk:9909/BLAC` | Port 9909 refused; needs a current SRU or Z39.50 address. |
| `uw_madison` | University of Wisconsin-Madison, EUA | missing | missing |  |  |
| `psu` | Penn State University, EUA | missing | missing |  |  |
| `tufts` | Tufts University Libraries, EUA | missing | missing |  |  |
| `fsu` | Florida State University, EUA | missing | missing |  |  |
| `ubc` | University of British Columbia, Canadá | missing | missing |  |  |
| `trent` | Trent University Library & Archives, Canadá | missing | missing |  |  |
| `sfu` | Simon Fraser University, Canadá | missing | missing |  |  |
| `utoronto` | University of Toronto, Canadá | missing | missing |  |  |
| `bne` | Biblioteca Nacional de España, Espanha | missing | missing |  |  |
| `bcl` | Biblioteca de Castilla y León, Espanha | missing | missing |  |  |
| `bizkaia` | Biblioteca Foral de Bizkaia, Espanha | missing | missing |  |  |
| `aladi` | Aladí: Barcelona Municipal Libraries Network, Espanha | missing | missing |  |  |
| `abes_fr` | Agence Bibliographique de l'Enseignement Supérieur, França | missing | missing |  |  |
| `uhamburg` | Hamburg University of Technology (TUHH), Alemanha | missing | missing |  |  |
| `bn_polonia` | National Library of Poland, Polônia | missing | missing |  |  |
| `slsp` | Swiss Library Service Platform, Suíça | missing | missing |  |  |
| `nkc` | National Library of the Czech Republic, Tchéquia | missing | missing |  |  |
| `rsl` | Russian State Library, Rússia | missing | missing |  |  |
| `bashkir` | Bashkir State University, Rússia | missing | missing |  |  |
| `bna` | Biblioteca Nacional da Argentina | missing | missing |  |  |
| `biblored` | Red Distrital de Bibliotecas Públicas (BibloRed), Colômbia | missing | missing |  |  |
| `pucp` | Pontificia Universidad Católica del Perú, Peru | missing | missing |  |  |
| `upc_peru` | Universidad Peruana de Ciencias Aplicadas, Peru | missing | missing |  |  |
| `christchurch` | Christchurch City Libraries, Nova Zelândia | missing | missing |  |  |
| `juac_julac` | Joint University Librarians Advisory Committee, Hong Kong | missing | missing |  |  |
| `monash_sa` | Monash South Africa, África do Sul | missing | missing |  |  |
<!-- targets:end -->

The table is generated from `targets.json`
(`python -m sru_gateway.status_table --write`); the tests fail when it falls
behind the file.

**Zeus target numbers.** A `zeus` entry asks Zeus for its own `targets[n]`
(`target_index`). The numbers come from the 2026-10-11 status list and are
still to be confirmed against Zeus's search page, which labels each target.
On a machine that reaches Zeus:

```sh
.venv/bin/python -m sru_gateway.zeus_labels               # fetches the page
.venv/bin/python -m sru_gateway.zeus_labels --page zeus.html   # a page saved from a browser
```

It prints each `zeus` entry next to the label Zeus shows for its number and
exits 1 when one does not match. `tests/fixtures/zeus_search_form.html` is a
stand-in, not the live page.

How a search goes: Koha's CQL is read like the other bridges read it (ISBN,
then title, then author, else any field). A Z39.50 target gets one session per
request with Bib-1 use 7, 4, 1003 or 1016 and a Present of the page Koha asked
for (Koha's first call, `maximumRecords=0`, only searches). An SRU target is
asked `<index>="<term>"` with its own index names (default `bath.isbn`,
`dc.title`, `dc.creator`, `cql.serverChoice`); its records, prefixed or
string-packed, go back as MARC21/slim. An unknown id answers diagnostic 235.
A path with two slashes (`//sru/bn`, what Koha asks for when the database is
written `/sru/bn`) is read as `/sru/bn`.

Run it: `.venv/bin/python -m sru_gateway` (127.0.0.1:5000), or on the VPS
[`deploy/sru-gateway.service`](deploy/sru-gateway.service), which listens on
0.0.0.0:5000 until `sru.koha.nexus` is served through the same Cloudflare
Tunnel as `catalog.koha.nexus`; port 5000 is then closed in the firewall.
`GET /health` lists the configured and missing ids.

**Ports.** 5000: this gateway (central server) or the Zeus bridge (a Koha
server, `koha-zeus-sru`). 5006: the Pergamum bridge (a Koha server,
`koha-pergamum-sru`). 8088: the Catalog Network (`catalog-network/`). The
central server runs only the gateway, which embeds the Zeus and Pergamum
clients; nothing listens on 5001 or 5002.

| Variable | Default | |
|---|---|---|
| `SRU_GATEWAY_HOST` / `SRU_GATEWAY_PORT` | `127.0.0.1` / `5000` | where to listen |
| `SRU_GATEWAY_TARGETS` | `sru_gateway/targets.json` | another targets file |
| `SRU_GATEWAY_TIMEOUT` | `25` | seconds per remote catalogue (Koha's rows wait 30) |
| `SRU_GATEWAY_MAX_RECORDS` | `50` | ceiling on `maximumRecords` |
| `SRU_GATEWAY_LOGIN_<ID>` | | `user:password` for a catalogue that needs a login |

Koha's row for a catalogue: host the VPS address, port `5000`, database
`sru/<id>`, SRU, MARC21, utf8, `sru=get,sru_version=1.1`, SRU search fields
`title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice`.
Its tests (`tests/test_gateway.py`) use a fake Z39.50 server and mocked SRU
answers; none of the remote catalogues was reached from the tests.
