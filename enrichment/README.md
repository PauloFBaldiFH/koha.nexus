# koha.nexus enrichment

Two packages for the offline-first enrichment design
(`design.md`, revision 3, approved 2026-10-17):

- **`enrich_build`** builds `static.db`, the prebuilt database every library
  downloads, from the harvest dumps. It runs on the release machine, never on
  the production VPS and never on a library's computer.
- **`nexus_enrich`** is the match and merge engine: it classifies candidate
  records against a local one (M0 / M1 / W / R) and adds, never replaces, the
  fields the local record lacks. Pure Python, standard library only (reading
  `static.db` needs `zstandard`).

Not here yet: the local gateway (`/sru/_union` on 127.0.0.1:5000), the
throttled worker, the panel screens and Magic Import options. Those are the
next steps of the design.

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
   "mode": "pointer", "brazilian": true, "weight": 0.7, "source_field": "target"},
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
| `source_field` | | a JSON key whose value becomes the source id per line (one Zeus dump holding several catalogues) |

A JSON line may hold the record as MARCXML (`marcxml`, `marc_xml`, `xml`,
`record`, `marc`), as ISO 2709 text (`iso2709`, `mrc`, `raw`) or as
MARC-in-JSON (`{"leader", "fields"}`); its id is read from `remote_id`, `id`,
`_id`, `control_number`, `recid` or `source_id`, else 001. Lines the builder
cannot read are counted in the report with the keys they had.

```sh
python -m enrich_build build sources.json --out static.db --report report.json
python -m enrich_build inspect static.db
python -m enrich_build release static.db --month 2026.11     # nexus-enrich-2026.11.db.zst + .sha256
python -m enrich_build verify nexus-enrich-2026.11.db.zst     # hash, decompress, integrity check
```

Upload the `.db.zst` and `.sha256` to the month's GitHub Release (R2 as
mirror). The asset is compressed at level 19 without `--long`, so a client
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
