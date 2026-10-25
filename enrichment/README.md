# koha.nexus enrichment

Three packages for the offline-first enrichment design
(`design.md`, revision 3, approved 2026-10-17):

- **`enrich_build`** builds `static.db`, the prebuilt database every library
  downloads, from the harvest dumps. It runs on the release machine, never on
  the production VPS and never on a library's computer.
- **`nexus_enrich`** is the match and merge engine: it classifies candidate
  records against a local one (M0 / M1 / W / R) and adds, never replaces, the
  fields the local record lacks. Pure Python, standard library only (reading
  `static.db` needs `zstandard`).
- **`nexus_gateway`** is the local SRU server Koha searches
  (`127.0.0.1:5000`, `/sru/_union` and `/sru/<id>`): `static.db` first, then
  live Z39.50/SRU within 6 s, late answers kept in `learned.db`.

Not here yet: installing the gateway and downloading `static.db` (installer),
the throttled worker, the panel screens and Magic Import options. Those are
the next steps of the design.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests
```

## Building `static.db`

Describe the dumps in a `sources.json` (paths are relative to that file;
globs work):

```json
{"sources": [
  {"id": "zeus", "name": "Catálogo Zeus (harvest)", "paths": ["catalogo_zeus_enriquecimento.jsonl.zst"],
   "mode": "pointer", "brazilian": true, "weight": 0.7, "source_field": "fonte",
   "overrides": {"fundacentro": {"mode": "full"}}},
  {"id": "usp", "name": "USP (Aleph)", "paths": ["data_usp/*.mrc"], "mode": "pointer", "brazilian": true},
  {"id": "loc", "name": "Library of Congress", "paths": ["loc/*.xml.gz"], "mode": "full", "weight": 1.0},
  {"id": "pool", "name": "Rede koha.nexus", "paths": ["catalog.db"], "brazilian": true, "headings": false}
]}
```

| Key | | |
|---|---|---|
| `id` | required | the source id stored with every record |
| `paths` | required | files or globs; `.zst`, `.gz`, `.xz`, `.bz2` are read compressed |
| `format` | `auto` | `jsonl`, `marcxml`, `iso2709` or `pool` (catalog-network's SQLite); `auto` goes by extension, then by the first bytes |
| `mode` | `full` | `full` ships the record; `pointer` ships only its keys and `remote_id` (sources whose terms do not allow redistribution) |
| `brazilian` | `false` | a Brazilian source: its subject headings may go on Portuguese records |
| `weight` | `0.5` | 0–1 authority of the source, the third tie-breaker after class and completeness |
| `headings` | `true` | gather the 1XX/6XX/7XX headings of its bibliographic records into `auth_headings` |
| `source_field` | | a JSON key naming the source per line (one Zeus dump holding several catalogues, e.g. `fonte`); its value becomes the source's name, and its id is the acronym in final parentheses ("… (Fundacentro)" -> `fundacentro`) or the folded words joined by `-` |
| `source_map` | | `{"value of source_field": "id"}` for names whose derived id is not the one wanted |
| `overrides` | | `{"id": {"mode", "brazilian", "weight", "name", "headings"}}` per derived source; the rest comes from the entry itself |

A JSON line may hold the record as ISO 2709 text (`raw_iso2709`, `iso2709`,
`mrc`, `raw`; tried first, and a line whose raw record is broken falls back
to the other forms), as MARCXML (`marcxml`, `marc_xml`, `xml`, `record`,
`marc`), as MARC-in-JSON (`{"leader", "fields"}`) or as the Zeus harvest's
dict under `marc` (`{"LDR", "001": "…", "650": [{"ind": "07", "subcampos":
{"$a": "…", "$x": ["…", "…"]}}]}`, a list being a repeated subfield). Its
id is read from `remote_id`, `id`, `control_number`, `recid` or `source_id`,
else 001, else `_id` or `id_hash`. `resumo` and other extra keys are
ignored. Lines the builder cannot read are counted in the report with the
keys they had.

```sh
python -m enrich_build build sources.json --out static.db --report report.json
python -m enrich_build inspect static.db
python -m enrich_build release static.db --month 2026.11     # nexus-enrich-2026.11.db.zst + .sha256
python -m enrich_build verify nexus-enrich-2026.11.db.zst     # hash, decompress, integrity check
```

Then publish it (a token with `contents: write` on the repository, from the
environment, never in a file):

```sh
GITHUB_TOKEN=... python -m enrich_build publish nexus-enrich-2026.11.db.zst
```

This creates the release `enrich-2026.11` (not marked latest, so the panel's
self-update is not affected), uploads the asset and its `.sha256`, and writes
`latest.txt` next to them. For the R2 mirror copy all three files to the
bucket root, e.g. `rclone copy nexus-enrich-2026.11.db.zst* latest.txt r2:BUCKET/`. The asset is compressed at level 19 without `--long`, so a client
decompresses it with a window of a few MB.

What the builder does:
- reads every file as a stream (memory stays flat; about 35 MB for 20 000
  records in a local test);
- trains a zstd dictionary on the first 2 000 records and stores each body
  as compressed UTF-8 ISO 2709 (`body` is NULL for a pointer);
- clusters versions by ISBN-13 with a title check (≥ 0.60), so a reused
  ISBN starts its own cluster, and by work key when there is no ISBN;
- keeps the last version when one source repeats a record id;
- turns authority records (leader/06 `z`, e.g. LoC NAF/LCSH MARCXML or BN)
  into established headings with their 4XX variants, LCCN and URI, and gathers
  the headings of bibliographic records as preliminary entries with an
  occurrence count.

## The local gateway

```sh
NEXUS_GATEWAY_STATIC_DB=static.db NEXUS_GATEWAY_LEARNED_DB=learned.db python -m nexus_gateway serve
python -m nexus_gateway check                       # targets and static.db as the gateway sees them
python -m nexus_gateway koha-sql | sudo koha-mysql INSTANCE
```

| Database | Answers from |
|---|---|
| `sru/_union` | every source in `static.db`; on a miss, every native target live |
| `sru/<id>` (a target in `nexus_gateway/targets.json`) | its `static.db` sources (`static`, default its id); on a miss, the target live if it is `z3950` or `sru` |
| `sru/<source>` (a `static.db` source with no target) | `static.db` only |

- A search answers from `static.db` whenever it has a record (the whole CQL
  query: ISBN/ISSN, title, author, keywords, and/or/not).
- Only when it has none are the native targets asked (Z39.50 or SRU, never
  scraping; `broken` targets are skipped), with one clause of the query (the
  ISBN, else the title, author or keywords). The reply waits 6 s
  (`NEXUS_GATEWAY_LIVE_TIMEOUT`); slower targets run on for 30 s and their
  answer goes to `learned.db`, which answers the same search for 30 days (an
  error for 10 minutes).
- Records go out without 9XX fields and `$9` subfields (the source Koha's
  items and authority ids).
- `static.db` is reopened by itself when the file is replaced.
- `koha-sql` points Koha's rows at the gateway behind the Cloudflare tunnel,
  `https://sru.koha.nexus` port 443: rows on older addresses (`127.0.0.1:5000`,
  the VPS's IPs) move there; it adds `sru/_union` and leaves it as the
  gateway's only ticked row. Of the authority rows only `sru/_union-aut` is
  touched.
- The local-first catalogues (`"local_first"` in `targets.json`: `sru/unesp`,
  `sru/ufpr`, `sru/unifesp`, `sru/unb`, `sru/ufu`, the five that hold 99% of
  `static.db`'s records) are ticked too and ranked 1 to 5, right after
  `sru/_union` (rank 0). A row of the library's own for one of those
  institutions (a host in the target's `"legacy_hosts"`, or a subdomain:
  `z3950.unifesp.br`, `unesp.alma.exlibrisgroup.com`, `*.ufpr.br`, `*.unb.br`,
  `*.ufu.br`) is kept as the fallback: unticked, so Koha's search no longer
  waits on it, and ranked 900. Its old rank and tick are saved once in the
  table `koha_nexus_legacy_z3950`, so a row the librarian ticks again stays
  ticked. To undo it, for good (later runs leave it undone):
  `python -m nexus_gateway koha-sql --undo-local-first | sudo koha-mysql INSTANCE`;
  `--redo-local-first` does it again.
- Logins: `NEXUS_GATEWAY_LOGIN_<ID>=user:password` in the unit's environment
  file, never in `targets.json`. The unit is `deploy/koha-nexus-sru.service`.

So that a harvested source lands on its Koha row, its `static.db` id should be
the target id: `fonte` slugs already match most (`ufpr`, `unb`, `fundacentro`,
`bn-portugal`, `porbase`); for others use the build's `source_map` or the
target's `static` list.

## Monthly updates on a library's computer

```sh
python -m nexus_gateway update --check     # what is installed, what is published
python -m nexus_gateway update             # download, verify, swap in
python -m nexus_gateway update --force     # install the newest even if it is the same month
```

- The newest month is taken from the GitHub releases (an asset
  `nexus-enrich-YYYY.MM.db.zst` with its `.sha256`) and, if
  `NEXUS_GATEWAY_MIRROR` is set, from the mirror's `latest.txt`; GitHub wins
  a tie, the mirror covers GitHub being down.
- The download goes to a `.part` file, its size and SHA-256 must match, then it
  is decompressed next to `static.db`, checked (`quick_check`, schema version,
  at least one record) and moved over `static.db` with one `os.replace`. The
  running gateway notices the new file on its next search; a search already
  running finishes on the old one. A failure leaves the old `static.db`.
- The downloaded `.zst` is deleted afterwards; `static.release` records the
  installed month and hash.

The installer (`config.sh enrich-install`, also run at the end of a Koha
install) puts the sources in `/usr/local/lib/koha-easy-installer/enrichment`
with their own venv and creates:

| Unit | What |
|---|---|
| `koha-nexus-sru` | the gateway on 127.0.0.1:5000 (user `nexus-enrich`, MemoryMax 192M) |
| `koha-nexus-enrich-update` | `update` as a oneshot at the lowest priority (Nice 19, idle I/O, 25% CPU, MemoryMax 256M) |
| `koha-nexus-enrich-update.timer` | 20 min after boot, then weekly with up to 6 h random delay |
| `koha-nexus-enrich` | the batch worker for enrichment jobs (below); exits when no job waits |

Data is in `/var/lib/koha-nexus-enrich`, settings in
`/etc/koha-nexus-enrich/gateway.env` (`NEXUS_GATEWAY_MIRROR`, logins). The
install retires the old Zeus and Pergamum bridges (`koha-zeus-sru`,
`koha-pergamum-sru`, ports 5000 and 5006) and runs `koha-sql` on Koha's
database. Panel tasks: `enrich-install`, `enrich-update [--force]`,
`enrich-status`.

On Windows, `.wslconfig` gets `[experimental] autoMemoryReclaim=gradual`, so
the memory WSL used for the decompression goes back to Windows instead of
staying with the VM.

## Enrichment jobs (worker, staged report, Apply, Revert)

```sh
config.sh --task enrich-job-add "101, 102, 500-550"   # or "all"; exports, queues, starts the worker
config.sh --task enrich-jobs                          # jobs and the worker's status (JSON)
config.sh --task enrich-job-show 3                    # counts, report path, Koha batches
config.sh --task enrich-job-diff 3 101                # one record, before/after
config.sh --task enrich-job-apply 3                   # the explicit Apply
config.sh --task enrich-job-revert 3 [--all]          # undo it
config.sh --task enrich-pause on|off                  # hold the worker between batches
```

1. **Export** (installer, as root): `export_records.pl --format=xml
   --dont_export_items` for the scope, under `systemd-run -p CPUQuota=25%`
   with nice 19 and idle I/O, into `jobs/ID/export.xml` in the state folder.
2. **Match** (`koha-nexus-enrich`, `python -m nexus_jobs worker`): 20
   records, then a 1.5 s sleep; each record is matched against `static.db`
   with `nexus_enrich` and its result kept in `jobs.db` (checkpoint after
   every batch, so a shutdown resumes where it stopped). It waits while a
   `pause` file exists or while the load average is above the number of
   CPUs. The unit has `CPUQuota=25%`, `MemoryMax=256M`, idle I/O, no network
   (`PrivateNetwork=yes`), a read-only system and no access to Koha.
3. **Staged report** (`jobs/ID/report.html`, `.json`, `.tsv`): records
   read, enriched / unchanged / review / no match, records with M0, M1, W
   and R candidates, fields added by class, group and source; each changed
   record before/after with the added lines marked; the review list with
   the local record and the candidate side by side. Nothing has reached
   Koha.
4. **Apply** (only when asked): a verified `PRE-ENRICH` backup, then
   batches of at most 500 records through Koha's staged import:
   `stage_file.pl --match NEXUSBIB --no-create --item-action ignore`
   (matcher `NEXUSBIB`: index `local-number` on 999 $c, created once), a
   check that each staged record matched its own biblionumber (any other
   match is set to `error`, which `commit_file.pl` skips), `commit_file.pl`,
   then a wait for Koha's index queue. A record whose 005 changed since the
   report is left out, never overwritten. Items are never touched.
5. **Revert**: a `PRE-UNDO-ENRICH` backup, then `commit_file.pl --revert`
   per batch, newest first. A record edited in Koha after Apply (its 005
   changed) is kept, by marking its import record `reverted` (which the
   revert skips), unless `--all`.

Pointer-only matches (sources shipped without the full record) are counted
in the report but not fetched yet.

## On-demand enrichment (direct Z39.50 servers, now)

```sh
config.sh --task enrich-od-add "101, 102"             # any number, or all; exports, queues, starts the service
config.sh --task enrich-od-add --isbn 9788535902778   # or --title T [--author A] [--year Y]: records to import as new
config.sh --task enrich-od-status 7                   # the service's progress (per server) and job 7
config.sh --task enrich-od-more 7                     # "Search more servers": the next ones, never the same
config.sh --task enrich-od-donor 7 101 subjects z3950:loc   # the donor of a field group (merged again, no network)
config.sh --task enrich-job-apply 7                   # the batch Apply, with a copy of the records, not a full backup
config.sh --task enrich-od-import 8 1 2               # job 8's typed query, its 2nd record found: imported as new
config.sh --task z3950-health                         # each direct server's breaker state (JSON)
config.sh --task z3950-health-reset loc               # or --all
```

The `koha-nexus-ondemand` unit (`python -m nexus_ondemand serve`) asks only
the direct servers of `panel/kei_panel/data/z3950_direct.json`, which
`enrich_install` copies next to the packages; the policy refuses
`sru.koha.nexus`, `catalog.koha.nexus` and every local address whatever
the list says. It takes the jobs of origin `ondemand` (the batch worker
never does), keeps what each server did in `jobs.db` (`od_attempts`) and
the records found in `jobs/ID/candidates/`, merges each server's best
record with the batch rules, and writes the same report. It has network
but no access to Koha, no port, `CPUQuota=25%`, `MemoryMax=160M`, and exits
after 5 idle minutes. `python -m nexus_ondemand once ID` runs one job from
a terminal.

There is no record limit: `all` exports the whole catalogue, and the service
reads export.xml one record at a time (memory stays flat), so a large job
runs for hours. A job the service left half way (a shutdown) goes on after
its last finished record; the unit restarts after a crash; the `pause` file
(the tray's or the batch screen's Pause) holds it between records. Apply and
Revert save a copy of the records for a job of up to 50
(`ENRICH_OD_SNAPSHOT_MAX`), and the verified full backup above that.

A typed query's records are imported one at a time: `python -m
nexus_ondemand import-file JOB SEQ N --out FILE` writes the Nth record found
(as `show` lists them) as MARCXML without the donor's 9XX fields and with an
`883 0_ $a koha.nexus on-demand $q SOURCE $w ID`; the installer stages it
with the ISBN matcher and `--no-replace` (a record Koha already has is
ignored, never overlaid), commits it, and leaves `jobs/ID/imported-SEQ-N`
with the new biblionumber. Library tools > Undo a MARC import takes it out.
The panel's "On-demand enrichment" screen (Library tools, key `n`) drives
all of this; the Z39.50 screen lists the direct servers whose breaker is
open or that failed in the last 7 days, with Reset.

## The engine

```python
from nexus_enrich import Candidate, Policy, enrich
from nexus_enrich.static import StaticDB

db = StaticDB("static.db")
candidates, pointers = db.candidates_for(local_record)     # pointers: records to fetch from their source
result = enrich(local_record, candidates, Policy())
result.status          # enriched / unchanged / review / no-match
result.additions       # group, field, source, class, score
result.record          # a copy of the local record with the additions
result.review          # why something went to review
```

Classes (thresholds in `classify.Thresholds`, to be calibrated on the
labelled sample):

| Class | When | May add |
|---|---|---|
| M0 | shared valid ISBN, title ≥ 0.85, same year, compatible edition | 6XX, 082, 080, 505, 520, 300, 024 |
| M1 | as M0 with a 1-year gap, same edition and same publisher | as M0 without 300 |
| W | same work (title ≥ 0.85, author ≥ 0.80), another year or edition | 6XX, 082, 080, 505, 520 (6XX and notes only in the same language) |
| R | ISBN reuse, shared ISBN with another edition, 2-year gap, missing year, two different works tied | nothing; listed for review |

Donors are ranked by class, then completeness (encoding level, controlled
subjects, 082/080, 520/505, national agency in 040), then source weight. Only
missing fields are added, one donor per field group, each linked by `$8 N\p`
to an `883` naming class, score, date, source and record id. 1XX, 245, 250,
260/264, 008, 020 and 9XX are never touched. Portuguese records take 6XX only
from Portuguese or Brazilian donors and never with a foreign `$2` (lcsh,
rameau, gnd…). A stub record gets a replacement *proposal* for review, never
an automatic replacement. Nothing here writes to Koha: the result feeds a
staged batch that a librarian applies.

## Central authority gateway and on-demand harvesting

Library clients can search `https://sru.koha.nexus/sru/_union-aut` using SRU
1.1, port 443 and `recordSchema=marcxml`. They do not need to build or host
`static.db` for this authority endpoint. The database lives on the central
server. Its contents and record count depend on the deployed harvest; the
repository does not guarantee a fixed count or the availability of the cloud
endpoint. Existing bibliographic search and enrichment services are unchanged.

New authority seeds include these defaults:

| Rank | Target | Protocol / database |
| --- | --- | --- |
| 1 | Nexus Autoridades (Cloud) | SRU, `https://sru.koha.nexus:443/sru/_union-aut` |
| 2 | BIBLIOTECA DOS NOMES DO CONGRESSO | Z39.50, `lx2.loc.gov:210/NAF`, attributes `1=1016` |
| 2 | BIBLIOTECA DOS ASSUNTOS DO CONGRESSO | Z39.50, `lx2.loc.gov:210/SAF`, attributes `1=1016` |
| 3 | BIBLIOTECA NACIONAL (AUTORIDADES) | SRU, `https://sru.koha.nexus:443/sru/bn-aut` |

Normal seeding preserves existing rank and checked choices. To explicitly
apply this hierarchy to an existing installation, from the repository root:

```sh
python enrichment/setup_z3950_authorities.py --enforce-defaults | sudo koha-mysql INSTANCE
```

Replace `INSTANCE` with the actual Koha instance. This migration disables
additional rows at the four managed addresses and legacy LoC authority SRU
rows; it does not delete them or modify bibliographic targets. Back up the
configuration and review the generated SQL before applying it. Without
`--enforce-defaults`, the utility prints the ordinary idempotent seed only.

On the **central gateway server only**, using its Python environment:

```sh
python enrichment/koha_nexus_harvest.py --source loc --db /var/lib/koha-nexus-enrich/static.db
python enrichment/koha_nexus_harvest.py --source bn --db /var/lib/koha-nexus-enrich/static.db
python enrichment/koha_nexus_harvest.py --source all --db /var/lib/koha-nexus-enrich/static.db
```

The CLI installs no daemon or schedule. It queries Wikidata for humans with
LoC (`P244`) or BN (`P4619`) identifiers, partitioned by citizenship (`P27`)
for Brazil, Portugal, France, Germany, Italy, Spain, the UK and the US.
Each partition is capped at 3,000 rows. This is a bounded collection, not an
exhaustive harvest: large partitions and other countries are not covered.
Labels are stored with separate Wikidata provenance and marked preliminary;
they are not presented as verified official LoC/BN preferred headings.
Existing official authority sources are preserved.

All requests finish before a single database transaction inserts the batches.
A failed request leaves the database untouched. Reruns skip existing keys.
After changes the CLI calls `systemctl reload-or-restart` on the existing
`koha-nexus-sru.service`, because that unit has no `ExecReload`. Use
`--reload-service koha-nexus-gateway.service` if that is the unit name in your
central deployment, or `--no-reload` when managing the service separately.
The operator needs database write permission and permission to manage that
unit. A reload failure returns an error but does not undo committed data.
Back up the central database before harvesting; replacing it with a monthly
release also replaces these additions, so preserve/reapply the harvest when
publishing a new central database.
