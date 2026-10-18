"""Stand-in for Koha's export_records.pl, stage_file.pl and commit_file.pl
in tests/enrichment_jobs.bats, on the test database, following
C4::ImportBatch:
- stage_file.pl --match: each record matches the biblio whose biblionumber
  is its 999 $c (a mismatch can be forced: MOCK_MISMATCH_FILE lines BN=OTHER),
  overlay_status auto_match, record_sequence from 1; a record with no
  999 $c (an import as new) matches the biblio with the same 020 $a, if
  any: with --no-replace it is ignored (status ignored), else no match;
- commit_file.pl: replace overlay (marcxml_old keeps the record), 005 set to
  now, records whose status is error or ignored are skipped; a no_match
  record is added as a new biblio (next biblionumber, 999 $c $d set);
- commit_file.pl --revert: marcxml_old put back (a new record deleted),
  records whose status is error, ignored or reverted skipped;
- authorities (export_records.pl --record-type=auths, stage_file.pl
  --authorities): staged without matching (no_match), committed as new
  rows of auth_header with 001 = authid and import_auths.matched_authid
  set; a revert deletes them (DelAuthority), skipping error and reverted.

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


def isbns(rec) -> set[str]:
    return {re.sub(r"[^0-9Xx]", "", (sf.text or "").split(" ")[0])
            for df in rec.findall(f"{M}datafield[@tag='020']") for sf in df.findall(f"{M}subfield[@code='a']")} - {""}


def with_999(xml: str, bn: str) -> str:
    rec = ET.fromstring(xml)
    for df in rec.findall(f"{M}datafield[@tag='999']"):
        rec.remove(df)
    df = ET.SubElement(rec, f"{M}datafield", tag="999", ind1=" ", ind2=" ")
    for code in "cd":
        ET.SubElement(df, f"{M}subfield", code=code).text = bn
    return ET.tostring(rec, encoding="unicode")


def with_001(xml: str, authid: str) -> str:
    rec = ET.fromstring(xml)
    for cf in rec.findall(f"{M}controlfield[@tag='001']"):
        rec.remove(cf)
    cf = ET.Element(f"{M}controlfield", tag="001")
    cf.text = authid
    pos = 1 if rec.find(f"{M}leader") is not None else 0
    rec.insert(pos, cf)
    return ET.tostring(rec, encoding="unicode")


AUTH_BATCH = NAME == "commit_file.pl" and sql(
    f"SELECT record_type FROM import_batches WHERE import_batch_id = {opt('batch-number')}")[0][0] == "auth"

if NAME == "export_records.pl" and "--record-type=auths" in ARGS:
    print('<?xml version="1.0" encoding="UTF-8"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">')
    for (xml,) in sql("SELECT marcxml FROM auth_header ORDER BY authid"):
        print(xml)
    print("</collection>")

elif NAME == "stage_file.pl" and "--authorities" in ARGS:
    root = ET.parse(opt("file")).getroot()
    sql(f"INSERT INTO import_batches (import_status, record_type, comments) VALUES ('staged', 'auth', "
        f"{q(opt('comment') or '')})")
    batch = sql("SELECT MAX(import_batch_id) FROM import_batches")[0][0]
    records = root.findall(f"{M}record")
    for seq, rec in enumerate(records, 1):
        sql(f"INSERT INTO import_records (import_batch_id, record_sequence, marcxml, overlay_status) VALUES "
            f"({batch}, {seq}, {q(ET.tostring(rec, encoding='unicode'))}, 'no_match'); "
            f"INSERT INTO import_auths VALUES (LAST_INSERT_ID(), NULL);")
    print(f"MARC record staging report\nNumber of valid records:    {len(records)}\n"
          f"Number of records matched:  0\n\nBatch number assigned:  {batch}\n")

elif AUTH_BATCH:
    batch = opt("batch-number")
    rows = sql(f"SELECT ir.import_record_id, ir.marcxml, ir.status, IFNULL(ia.matched_authid, '') FROM import_records ir "
               f"JOIN import_auths ia ON ia.import_record_id = ir.import_record_id WHERE import_batch_id = {batch}")
    n = 0
    if "--revert" in ARGS:
        for rid, _, status, authid in rows:
            if status in ("error", "reverted"):
                continue
            sql(f"DELETE FROM auth_header WHERE authid = {authid}; "
                f"UPDATE import_records SET status = 'reverted' WHERE import_record_id = {rid}")
            n += 1
        sql(f"UPDATE import_batches SET import_status = 'reverted' WHERE import_batch_id = {batch}")
        print(f"Number of records deleted:       {n}\nNumber of records reverted:      {n}\nNumber of errors:                0")
    else:
        for rid, xml, status, _ in rows:
            if status == "error":
                continue
            authid = sql(f"INSERT INTO auth_header (marcxml) VALUES ('<record/>'); SELECT LAST_INSERT_ID()")[0][0]
            sql(f"UPDATE auth_header SET marcxml = {q(with_001(xml, authid))} WHERE authid = {authid}; "
                f"UPDATE import_auths SET matched_authid = {authid} WHERE import_record_id = {rid}; "
                f"UPDATE import_records SET status = 'imported' WHERE import_record_id = {rid}")
            n += 1
        sql(f"UPDATE import_batches SET import_status = 'imported' WHERE import_batch_id = {batch}")
        print(f"Number of new records added:     {n}\nNumber of records replaced:      0")

elif NAME == "export_records.pl":
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
    matched = 0
    for seq, rec in enumerate(records, 1):
        bn = ""
        for df in rec.findall(f"{M}datafield[@tag='999']"):
            for sf in df.findall(f"{M}subfield[@code='c']"):
                bn = sf.text
        bn = mismatch.get(bn, bn)
        overlay, status = "auto_match", "staged"
        if not bn:
            mine = isbns(rec)
            bn = next((b for b, x in sql("SELECT biblionumber, metadata FROM biblio_metadata ORDER BY biblionumber")
                       if mine & isbns(ET.fromstring(x))), "")
            if bn and "--no-replace" in ARGS:
                status = "ignored"
            elif not bn:
                overlay, bn = "no_match", "NULL"
        else:
            matched += 1
        if status == "ignored":
            matched += 1
        xml = ET.tostring(rec, encoding="unicode")
        sql(f"INSERT INTO import_records (import_batch_id, record_sequence, marcxml, overlay_status, status) VALUES "
            f"({batch}, {seq}, {q(xml)}, '{overlay}', '{status}'); INSERT INTO import_biblios VALUES (LAST_INSERT_ID(), {bn});")
    print(f"MARC record staging report\nNumber of valid records:    {len(records)}\n"
          f"Number of records matched:  {matched}\n\nBatch number assigned:  {batch}\n")

elif NAME == "commit_file.pl":
    batch = opt("batch-number")
    if "--revert" in ARGS:
        n = 0
        deleted = 0
        for rid, bn, old, status, overlay in sql(
                f"SELECT ir.import_record_id, ib.matched_biblionumber, IFNULL(ir.marcxml_old, ''), ir.status, "
                f"ir.overlay_status FROM import_records ir "
                f"JOIN import_biblios ib ON ib.import_record_id = ir.import_record_id WHERE import_batch_id = {batch}"):
            if status in ("error", "ignored", "reverted"):
                continue
            if overlay == "no_match":
                sql(f"DELETE FROM biblio_metadata WHERE biblionumber = {bn}")
                deleted += 1
            else:
                sql(f"UPDATE biblio_metadata SET metadata = {q(old)} WHERE biblionumber = {bn}")
                n += 1
            sql(f"UPDATE import_records SET status = 'reverted' WHERE import_record_id = {rid}")
        sql(f"UPDATE import_batches SET import_status = 'reverted' WHERE import_batch_id = {batch}")
        print(f"Number of records deleted:       {deleted}\nNumber of records reverted:      {n}\nNumber of errors:                0")
    else:
        if os.environ.get("MOCK_FAIL_COMMIT") and os.path.exists(os.environ["MOCK_FAIL_COMMIT"]):
            os.remove(os.environ["MOCK_FAIL_COMMIT"])
            sys.exit("commit_file.pl: simulated failure")
        stamp = time.strftime("%Y%m%d%H%M%S.0")
        n = added = 0
        for rid, bn, xml, status, overlay in sql(
                f"SELECT ir.import_record_id, IFNULL(ib.matched_biblionumber, ''), ir.marcxml, ir.status, ir.overlay_status "
                f"FROM import_records ir "
                f"JOIN import_biblios ib ON ib.import_record_id = ir.import_record_id WHERE import_batch_id = {batch}"):
            if status in ("error", "ignored"):
                continue
            if overlay == "no_match":
                bn = str(int(sql("SELECT IFNULL(MAX(biblionumber), 0) FROM biblio_metadata")[0][0]) + 1)
                sql(f"INSERT INTO biblio_metadata (biblionumber, format, `schema`, metadata) VALUES "
                    f"({bn}, 'marcxml', 'MARC21', {q(with_999(xml, bn))}); "
                    f"UPDATE import_biblios SET matched_biblionumber = {bn} WHERE import_record_id = {rid}; "
                    f"UPDATE import_records SET status = 'imported' WHERE import_record_id = {rid}")
                added += 1
                continue
            old = sql(f"SELECT metadata FROM biblio_metadata WHERE biblionumber = {bn}")[0][0]
            new = re.sub(r'(<controlfield tag="005">)[^<]*', r"\g<1>" + stamp, xml)
            sql(f"UPDATE import_records SET marcxml_old = {q(old)}, status = 'imported' WHERE import_record_id = {rid}; "
                f"UPDATE biblio_metadata SET metadata = {q(new)} WHERE biblionumber = {bn}")
            n += 1
        sql(f"UPDATE import_batches SET import_status = 'imported' WHERE import_batch_id = {batch}")
        print(f"Number of new records added:     {added}\nNumber of records replaced:      {n}")
