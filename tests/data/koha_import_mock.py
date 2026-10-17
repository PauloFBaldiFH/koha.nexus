"""Stand-in for Koha's export_records.pl, stage_file.pl and commit_file.pl
in tests/enrichment_jobs.bats, on the test database, following
C4::ImportBatch:
- stage_file.pl --match: each record matches the biblio whose biblionumber
  is its 999 $c (a mismatch can be forced: MOCK_MISMATCH_FILE lines BN=OTHER),
  overlay_status auto_match, record_sequence from 1;
- commit_file.pl: replace overlay (marcxml_old keeps the record), 005 set to
  now, records whose status is error are skipped;
- commit_file.pl --revert: marcxml_old put back, records whose status is
  error or reverted skipped.

    koha_import_mock.py DB SCRIPT [ARGS...]
"""

import os
import re
import subprocess
import sys
import time
from xml.etree import ElementTree as ET

M = "{http://www.loc.gov/MARC21/slim}"
ET.register_namespace("", M[1:-1])
DB, NAME, ARGS = sys.argv[1], sys.argv[2], sys.argv[3:]


def sql(query: str) -> list[list[str]]:
    out = subprocess.run(["mysql", "-N", "-B", "--default-character-set=utf8mb4", DB, "-e", query],
                         check=True, capture_output=True, text=True).stdout
    # Batch mode escapes tabs, newlines and backslashes in values.
    unescape = {"n": "\n", "t": "\t", "\\": "\\", "0": "\0"}
    return [[re.sub(r"\\(.)", lambda m: unescape.get(m.group(1), m.group(1)), v) for v in line.split("\t")]
            for line in out.splitlines()]


def q(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def opt(name: str) -> str | None:
    for i, a in enumerate(ARGS):
        if a == f"--{name}" and i + 1 < len(ARGS):
            return ARGS[i + 1]
        if a.startswith(f"--{name}="):
            return a.split("=", 1)[1]
    return None


if NAME == "export_records.pl":
    wanted = None
    if opt("id_list_file"):
        wanted = {line.strip() for line in open(opt("id_list_file")) if line.strip()}
    print('<?xml version="1.0" encoding="UTF-8"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">')
    for bn, xml in sql("SELECT biblionumber, metadata FROM biblio_metadata ORDER BY biblionumber"):
        if wanted is None or bn in wanted:
            print(xml)
    print("</collection>")

elif NAME == "stage_file.pl":
    root = ET.parse(opt("file")).getroot()
    sql(f"INSERT INTO import_batches (matcher_id, import_status, comments) VALUES ({opt('match')}, 'staged', "
        f"{q(opt('comment') or '')})")
    batch = sql("SELECT MAX(import_batch_id) FROM import_batches")[0][0]
    mismatch = {}
    if os.environ.get("MOCK_MISMATCH_FILE"):
        for line in open(os.environ["MOCK_MISMATCH_FILE"]):
            if "=" in line:
                a, b = line.strip().split("=")
                mismatch[a] = b
    records = root.findall(f"{M}record")
    for seq, rec in enumerate(records, 1):
        bn = ""
        for df in rec.findall(f"{M}datafield[@tag='999']"):
            for sf in df.findall(f"{M}subfield[@code='c']"):
                bn = sf.text
        bn = mismatch.get(bn, bn)
        xml = ET.tostring(rec, encoding="unicode")
        sql(f"INSERT INTO import_records (import_batch_id, record_sequence, marcxml, overlay_status) VALUES "
            f"({batch}, {seq}, {q(xml)}, 'auto_match'); INSERT INTO import_biblios VALUES (LAST_INSERT_ID(), {bn});")
    print(f"MARC record staging report\nNumber of valid records:    {len(records)}\n"
          f"Number of records matched:  {len(records)}\n\nBatch number assigned:  {batch}\n")

elif NAME == "commit_file.pl":
    batch = opt("batch-number")
    if "--revert" in ARGS:
        n = 0
        for rid, bn, old, status in sql(
                f"SELECT ir.import_record_id, ib.matched_biblionumber, ir.marcxml_old, ir.status FROM import_records ir "
                f"JOIN import_biblios ib ON ib.import_record_id = ir.import_record_id WHERE import_batch_id = {batch}"):
            if status in ("error", "reverted"):
                continue
            sql(f"UPDATE biblio_metadata SET metadata = {q(old)} WHERE biblionumber = {bn}; "
                f"UPDATE import_records SET status = 'reverted' WHERE import_record_id = {rid}")
            n += 1
        sql(f"UPDATE import_batches SET import_status = 'reverted' WHERE import_batch_id = {batch}")
        print(f"Number of records deleted:       0\nNumber of records reverted:      {n}\nNumber of errors:                0")
    else:
        if os.environ.get("MOCK_FAIL_COMMIT") and os.path.exists(os.environ["MOCK_FAIL_COMMIT"]):
            os.remove(os.environ["MOCK_FAIL_COMMIT"])
            sys.exit("commit_file.pl: simulated failure")
        stamp = time.strftime("%Y%m%d%H%M%S.0")
        n = 0
        for rid, bn, xml, status in sql(
                f"SELECT ir.import_record_id, ib.matched_biblionumber, ir.marcxml, ir.status FROM import_records ir "
                f"JOIN import_biblios ib ON ib.import_record_id = ir.import_record_id WHERE import_batch_id = {batch}"):
            if status == "error":
                continue
            old = sql(f"SELECT metadata FROM biblio_metadata WHERE biblionumber = {bn}")[0][0]
            new = re.sub(r'(<controlfield tag="005">)[^<]*', r"\g<1>" + stamp, xml)
            sql(f"UPDATE import_records SET marcxml_old = {q(old)}, status = 'imported' WHERE import_record_id = {rid}; "
                f"UPDATE biblio_metadata SET metadata = {q(new)} WHERE biblionumber = {bn}")
            n += 1
        sql(f"UPDATE import_batches SET import_status = 'imported' WHERE import_batch_id = {batch}")
        print(f"Number of new records added:     0\nNumber of records replaced:      {n}")
