# Magic Import: operator and architecture guide

**Library tools > Magic Import Tool** prepares bibliographic records,
physical items, patrons and authorities for Koha's import tools. Analysis,
mapping and building do not write the library database. Final writes use
Koha's staging/commit and patron import routines, with their own checks,
confirmations and verified backups.

See [Edit & Map Fields](field-mapping.md) for screen controls and mapping
JSON. The established [ISIS](isis-format.md) and
[Biblioteca Fácil](biblioteca-facil-format.md) readers remain separate.

## Importing a file

1. Put the export in the panel user's `importar` directory, or choose it
   with the file picker. Windows also offers `C:\Koha\Importar`.
2. Read the detected source inventory. The tool inspects containers before
   looking for embedded MARC/XML: SQL containing an XML value remains SQL.
   Needed Debian reader packages are reported.
3. In the Textual panel, review modes and mappings before answering remaining
   questions. A file may contain several tables or both bibliographic and
   authority MARC streams. Automatic detection is the starting point; use
   the mode switch if it is wrong. Check proposed fields against the source.
4. Confirm SQL relationships, fallback codes and the missing-barcode policy.
   For patrons, choose a fallback category and whether existing patrons may
   be updated before the validated build.
5. Check the first-three preview and full validation report. Correct errors
   before continuing. Warnings are displayed for review and do not
   automatically block the import. Skipping the mapper does not bypass
   validation.
6. Confirm the import. Bibliographic matching can keep an existing title,
   replace it, or import each title as new. Patron updates require an
   explicit policy. Each output stream has its own Koha check and backup.
7. Compare the final counts and open linked logs if a stream fails.
   A failure can follow earlier successful streams; see recovery below.

A complete Koha database backup is routed to **Restore database**. Partial
catalog exports containing `biblio_metadata` and `items` can instead become
records and copies. Restoring a database and migrating selected records
are different operations.

## Formats and inference

| Input | Handling |
|---|---|
| MARC ISO 2709, MARCXML, MarcEdit `.mrk` and recognized MARC text | Decode to canonical records, preserve repeated fields and indicators, then apply the selected mode and holdings normalization. MARC-8 conversion uses `yaz-marcdump` when required. |
| CSV/TSV, `.xlsx`, supported `.xls`, `.ods`, `.dbf` | Inspect every column's content and available header; sheets/tables retain separate identities. Reader dependencies remain format-specific. |
| Plain SQL dumps | Parse supported `CREATE`, `INSERT` and PostgreSQL `COPY` forms as data, including quoted identifiers, escaped text, multiline XML and INSERT blocks with different declared column orders. Exports are not executed against Koha. |
| Headerless SQL/spreadsheets | Infer from distributions and cross-table evidence, then ask about uncertain fields and relationships. No built-in rule says column 0 is an ID or column 3 is a barcode. |
| Archives/directories | Inspect members with the existing extraction limits and path/link checks; identify each member by content. |
| ISIS/Biblioteca Fácil exports | Use the existing dedicated Perl readers and preserve their specialized transformations. |

The heuristic engine combines normalized header evidence, regex masks,
check digits, data types, uniqueness/entropy, lengths, null distributions
and contextual evidence across columns. It recognizes common names,
emails, phones, CPF/CEP formats, addresses, UF/country values, dates,
identifiers and bibliographic fields. A numeric sequence alone cannot
distinguish a source key from a barcode or card number. Two plausible date
columns may remain ambiguous. Every official patron destination can be
reviewed manually when the target supports it; automatic recognition of
every field is not promised.

## SQL metadata, copies and relationships

Named Koha metadata and item tables can join on their declared source
`biblionumber`. That key identifies a relationship inside the export; it
is not assigned as the destination's database primary key.

For anonymous tables, the engine proposes relationships from uniqueness,
value overlap, coverage and metadata evidence. The draft displays proposals
separately from the mapping's approved `relationships` list, which starts
empty. Ties or unexplained joins remain blocking review issues until the
operator chooses the source tables and columns.

Use relationship `kind: "items"` for physical copies. A
`kind: "bibliographic"` relationship identifies a bibliographic/accounting
row already represented by metadata; it must not create a second title or
a copy merely because its key overlaps. Unknown SQL tables are not treated
as item inventories solely from a successful join.

## Holdings to Koha 952

Normalization is per field occurrence, so repeated holdings stay separate.
Bibliographic metadata and unconverted source fields remain available.

| Source evidence | Result |
|---|---|
| Existing Koha `952` | Preserve native subfields, including branch, barcode, call number, type, location and acquisition date; validate destination codes. |
| Pergamum/Biblivre or supported legacy `949`/`852` patterns | Use context and value evidence, plus reviewed mappings, to construct a `952` for a real copy. Layouts vary; uncertain interpretations require review. |
| Descriptive `852`, or a BN legal-deposit `949$a` containing a number followed by `DL` and a date | Keep the source description without inventing a local item. |
| A real local barcode/item with a legal-deposit phrase in another note | Keep the real copy when independent inventory evidence identifies it. A note containing `DL` does not by itself discard the copy. |
| Related SQL item row | Synthesize a `952` on the matching metadata record after validating the relationship and required fields. |

Branch/type defaults fill absent values. An existing valid `MAIN` stays
`MAIN` even if the fallback is `CA`. To change it, explicitly remap both
`952$a` and `952$b` as appropriate. Unknown nonempty codes require review;
they are not silently replaced by a fallback.

Missing and duplicate MARC/SQL holdings barcodes are reviewed by default.
The existing spreadsheet grouper retains its renumbering behavior and emits
a review warning; specialized ISIS/Biblioteca Fácil fallback rules remain
unchanged. Explicit
`barcode_policy: "generate"` can produce deterministic migration barcodes
when stable migration and source-record identities are available. Results
are checked against the complete import and destination snapshot;
generation is not an overwrite policy. The private audit records the
correspondence. Retain it and the migration identity for repeatability.

Source `952$9` item IDs and Koha-local `999$c/$d` identifiers are removed
from the prepared target record and recorded in the private source-ID audit.
The destination creates its own primary keys. Source record identifiers
remain available for correlation and diagnostics.

## Patrons and authorities

Patron output uses official importer/`borrowers` names, including extended
address, contact, date and preference fields. The destination snapshot
filters the catalog by the actual schema and supported importer extensions.
Guarantor source IDs need explicit source-to-target identity resolution;
they cannot be reused as destination borrower numbers.

The wide mapper preserves mapped fields instead of reducing every patron
to surname, email and phone. Required fields, dates, category/branch codes,
duplicate card numbers/usernames, destination collisions and selected
numeric fields are validated. Invalid CPF check digits produce a warning.
CPF is an optional patron attribute, not a universal `borrowers` column;
RG and other documents need a suitable reviewed destination.

Restricted fields are excluded from automatic mapping. Enable **Review
sensitive patron fields** to assign them deliberately. Recognized source
password hashes cannot become new passwords, including hashes introduced
by transforms/defaults/remaps. Saved profiles cannot contain literal
restricted-field assignments or sensitive remap tables. An update policy
does not authorize a guessed identity match.

Authorities have their own manifest stream and staged authority loader.
Automatic MARC classification uses the authority leader record type; a
manual override remains subject to validation. The engine checks exactly
one established heading, compatible authority type and the target's actual
type field (`152$b` or a configured `942$a`). Bibliographic `245` and item
`952` do not become authority fields. Authority-only imports participate in
readiness checks and final counts.

Koha 24.11's stock batch committer guesses fixed authority type codes from
heading tags and can ignore a mapped local type. The authority adapter
preflights every staged record against the live framework, calls Koha's
`BatchCommitRecords` API with a process-local type resolver, and verifies
the saved types before its transaction completes. It creates new authorities
without replacement matching and retains Koha's batch and undo bookkeeping.
It does not modify installed Koha modules.

## Preview, validation and logs

The live preview calls `review.preview_document` in an isolated work
directory, invokes the import's build adapters and displays three mapped
records. Work runs in the background and edits are debounced. The backend
still validates the complete output; three good examples do not clear the
remaining records.

Every build writes `out/validation.json`. The shell requires a readable,
consistent structured report before staging any stream. A build exit code
alone does not establish permission to import. Errors block all streams
before staging; warnings stay visible. Checks cover required patron fields,
supported destinations, codes, dates, identifiers, ISBN check digits, item
barcodes and authority structure. Common destination identifier collation
rules are considered; unusual language-specific collations still receive
Koha's own database checks.

Runs are logged under `/var/log/koha-easy-install/tools/`. The parent
`magic-import-*.log` links child MARC/patron logs. A nonzero staging exit
cannot be hidden by a partial success line. After commit, per-record and
per-item statuses in Koha's import tables are checked, including errors
where the process returned zero. The concrete Koha error is retained in
the child log and linked from the parent. Filenames with spaces and
parentheses are passed as complete arguments; printed commands are
diagnostics, not unquoted command text assembled from filenames.

Capabilities and existing identity snapshots are private work files. The
work directory is restricted to migration users; retained validation,
normalization/source-ID audits and eligible mapping decisions use `0600`.
These files can contain library identifiers or sensitive error text. Share
only redacted copies when reporting a problem. Profiles store statistical
signatures instead of source rows; sensitive runtime assignments are not
retained as a profile audit.

## Recovery and transaction limits

Before each writing step, the existing verified `PRE-*` backup is required.
MARC batches retain their Koha batch identity and can be handled through
**Undo a MARC import**; use the normal restore workflow when a database
backup is the appropriate recovery point.

Several streams are **not one database transaction**. A later failure does
not automatically undo earlier successful streams. The final report states
what completed before the failed step. Read parent and child logs and
inspect Koha before retrying, replacing records or restoring a backup;
otherwise a retry could duplicate a completed part. Authority batch
reversal uses its authority type, not a bibliographic loader or count.
The batch adapter calls Koha's `BatchRevertRecords` API in system-job
context, retaining its loan/hold checks. This avoids the stock 24.11 CLI's
nonexistent dummy borrower while deleting imported items. Reported reversal
errors fail the operation; the verified backup remains available.

## Implementation map

The installer embeds and writes the Python package. Tests extract these
same module bodies instead of testing a separate development copy.

| Module / boundary | Responsibility |
|---|---|
| `detect.py`, `intake.py`, `readers.py`, `marc.py` | Container-first recognition, safe intake, table/SQL/MARC decoding and canonical records. |
| `heuristics.py`, `classify.py`, `relational.py` | Column evidence, classification and reviewed source relationships. |
| `mapping.py`, `patrons.py`, `authority_import.py` | Versioned/scoped mappings, schema-aware patron rows and authority preparation. |
| `normalizer.py`, `remap952.pl` | Native/legacy holdings, legal-deposit distinction, codes, barcodes and source-ID handling. |
| `review.py`, `validation.py`, `engine.py` | Pre-build draft, shared previews, full-output validation and manifest construction. |
| `screens/importmap.py`, `routines/common.py` | Version 2 review UI and existing prompt dispatch; the v1 screen remains available. |
| Installer orchestration | Target snapshots, mandatory validation gate, backups, Koha loaders, exact errors and per-stream totals. |

## Synthetic fixtures and validation stages

Committed fixtures are synthetic. They exercise file structures and failure
patterns observed during private sample review; uploaded catalog/patron
rows, real CPFs, addresses, dumps and credentials are not copied into the
repository. Test emails use `example.invalid`, and names/IDs identify
synthetic data. Frozen-source checks also verify that the specialized ISIS
and Biblioteca Fácil readers were not overwritten.

The upgrade followed these gates in order:

| Stage | Validation and outcome |
|---|---|
| 1. Contracts and fixtures | Synthetic reader, mapping, pipeline and failure contracts preceded implementation; existing reader behavior was recorded. Passed. |
| 2. Readers | MARC text, SQL containers, escapes, declared column reordering and repeated data were checked. Passed. |
| 3. Heuristics and relationships | Shuffled/headless columns, ambiguous dates/IDs, reviewed joins and orphan/duplicate keys were checked. Passed. |
| 4. Holdings normalization | Native 952, legacy holdings, mixed DL notes, code maps, missing/colliding barcodes and standalone Perl normalization were checked. Passed. |
| 5. Patron and authority adapters | Wide fields, required/restricted destinations, password guards, profiles, authority structure and streams were checked. Passed. |
| 6. UI and shared previews | Modes, opaque IDs, first-three preview parity, recurring profiles and explicit sensitive-field review were checked with Textual. Passed. |
| 7. Failure boundaries | Python/CLI and MariaDB-backed Bats tests checked staging/commit errors, validation gates, quoted filenames, backups, authorities and truthful partial results. Passed. |
| 8. Final regression and real Koha smoke | Import/UI regression: 288 Python tests passed on each of Python 3.9.25 and 3.13.5; 46 Bash/MariaDB integration tests passed. Actual Koha 24.11.20.000 imports and reversals passed in a separate disposable database; see the scope below. The CI also runs the isolated Bash integration suite. |

The real-Koha smoke used official 24.11.x source at
`af0165219fddc27b8e76a2bba0c3f2375deaf529`, its database schema and MARC21
frameworks, and synthetic records only. It checked four bibliographic
records, three items, three authorities (100, 155 and 180, including a
custom target type), and one patron with 16 fields round-tripped. Native
branch remapping, legal-deposit exclusion, source-ID replacement, filenames
with spaces/parentheses, patron dry run and password-hash exclusion passed.
Bibliographic/item and authority batches were reversed and the test patron
was removed. A separate unknown-type batch was rejected before any authority
was written. This is version-specific evidence, not certification of every
Koha release or local framework.

The broader panel regression finished with **678 passed, 5 skipped and 3
failed** on Python 3.12/Textual 8.2.8. The failures concerned animation frame
timing, dialog error recovery and VPN widget mounting, outside the import
mapper. Failures varied between whole-suite runs; the dialog recovery
failure was also reproduced against unchanged `origin/main`. The broader
suite is therefore not fully green, despite the passing import-specific
checks. These assertions were not weakened to hide the failures.
Focused reruns passed the animation and VPN tests; dialog recovery failed
on both this branch and unchanged `origin/main`.

Run repository checks with `bash tests/run.sh`; see
[the test harness guide](../tests/README.md) for dependencies and isolated
MariaDB/Bats execution. Tests do not connect to an installed library database.

Remaining limits include unsupported SQL/MARC grammar, ambiguous semantics,
site-specific authority frameworks and differences between Koha releases.
Validate representative migrations against the destination configuration;
synthetic fixtures cannot certify every ILS layout or live dataset.
