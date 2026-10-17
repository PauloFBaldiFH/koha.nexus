"""The Apply and Revert steps' bookkeeping. Koha itself is driven by the
installer (as root, through koha-shell); this module decides what goes in
each batch file and checks what Koha did.

Apply, per chunk of at most 500 records:
1. the installer reads each record's current 005 from Koha;
2. chunk_file() writes the enriched records whose 005 is still the one
   exported (a record edited since the report is left out, never
   overwritten);
3. Koha stages the file (stage_file.pl, matching on 999 $c, no new
   records, items ignored);
4. check_matches() compares each staged record's match with its own
   biblionumber; any other match is marked so that commit_file.pl skips it;
5. Koha commits (commit_file.pl); committed() records each record's new 005.

Revert, per applied chunk, newest first: revert_plan() lists the records a
librarian edited after Apply; they are kept (their import record is marked
reverted, which commit_file.pl --revert skips) unless --all is given.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from nexus_enrich import marc

from .store import Store, now, unpack


def read_tsv(path: Path | str) -> dict[int, str]:
    """biblionumber<TAB>005 lines (as the installer's SQL prints them)."""
    out: dict[int, str] = {}
    text = Path(path).read_text(encoding="utf-8", errors="replace") if path else ""
    for line in text.splitlines():
        parts = line.split("\t")
        if parts and parts[0].strip().isdigit():
            out[int(parts[0])] = parts[1].strip() if len(parts) > 1 and parts[1].strip() != "NULL" else ""
    return out


def record_xml(rec: marc.Record) -> str:
    """MARCXML with the default namespace (no prefix), as MARC::File::XML
    reads it."""
    out = [f"<record>\n  <leader>{escape(rec.leader)}</leader>\n"]
    for f in rec.fields:
        if f.is_control:
            out.append(f"  <controlfield tag={quoteattr(f.tag)}>{escape(f.data or '')}</controlfield>\n")
            continue
        out.append(f"  <datafield tag={quoteattr(f.tag)} ind1={quoteattr(f.ind1 or ' ')} "
                   f"ind2={quoteattr(f.ind2 or ' ')}>\n")
        for code, value in f.subfields:
            out.append(f"    <subfield code={quoteattr(code)}>{escape(value)}</subfield>\n")
        out.append("  </datafield>\n")
    out.append("</record>\n")
    return "".join(out)


def chunk_ids(store: Store, job_id: int, chunk: int) -> list[int]:
    return [r[0] for r in store.conn.execute(
        "SELECT biblionumber FROM items WHERE job_id = ? AND chunk = ? AND biblionumber IS NOT NULL ORDER BY seq",
        (job_id, chunk))]


def pending_chunks(store: Store, job_id: int) -> list[int]:
    return [r["chunk"] for r in store.chunks(job_id) if r["state"] in ("pending", "failed")]


def chunk_file(store: Store, job_id: int, chunk: int, current: dict[int, str], out: Path) -> list[int]:
    """Writes the batch file; returns the biblionumbers in it, in order."""
    rows, manifest = [], []
    with open(out, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">\n')
        for item in store.conn.execute(
                "SELECT biblionumber, f005, after FROM items WHERE job_id = ? AND chunk = ? ORDER BY seq",
                (job_id, chunk)):
            bn = item["biblionumber"]
            if bn is None:
                continue
            if bn not in current:
                rows.append((bn, "skipped-deleted", ""))
            elif current[bn] != item["f005"]:
                rows.append((bn, "skipped-changed", current[bn]))
            else:
                fh.write(record_xml(unpack(item["after"])))
                rows.append((bn, "staged", item["f005"]))
                manifest.append(bn)
        fh.write("</collection>\n")
    store.conn.execute("DELETE FROM applied WHERE job_id = ? AND chunk = ?", (job_id, chunk))
    store.set_applied(job_id, chunk, rows)
    store.set_chunk(job_id, chunk, staged=len(manifest), note="")
    store.set(job_id, state="applying")
    return manifest


def check_matches(store: Store, job_id: int, chunk: int, batch: int, staged_rows: str) -> list[int]:
    """staged_rows: record_sequence<TAB>import_record_id<TAB>matched_biblionumber
    <TAB>overlay_status per staged record. Returns the import_record_ids
    that must not be committed (no match, or a match on another record)."""
    manifest = [r[0] for r in store.conn.execute(
        "SELECT a.biblionumber FROM applied a JOIN items i ON i.job_id = a.job_id AND i.biblionumber = a.biblionumber "
        "AND i.chunk = a.chunk WHERE a.job_id = ? AND a.chunk = ? AND a.state = 'staged' ORDER BY i.seq",
        (job_id, chunk))]
    seen: dict[int, tuple[int, str, str]] = {}
    for line in staged_rows.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            seen[int(parts[0])] = (int(parts[1]), parts[2].strip(), parts[3].strip())
    bad_ids, bad_bibs = [], []
    for pos, bn in enumerate(manifest, start=1):
        got = seen.get(pos)
        if got is None:
            bad_bibs.append(bn)
            continue
        import_id, matched, overlay = got
        if overlay != "auto_match" or matched != str(bn):
            bad_ids.append(import_id)
            bad_bibs.append(bn)
    for bn in bad_bibs:
        store.conn.execute("UPDATE applied SET state = 'skipped-match' WHERE job_id = ? AND chunk = ? "
                           "AND biblionumber = ?", (job_id, chunk, bn))
    store.set_chunk(job_id, chunk, batch=batch)
    return bad_ids


def committed(store: Store, job_id: int, chunk: int, after: dict[int, str]) -> dict:
    rows = store.applied(job_id, chunk)
    n = 0
    for r in rows:
        if r["state"] == "staged":
            store.conn.execute("UPDATE applied SET state = 'applied', f005 = ? WHERE job_id = ? AND chunk = ? "
                               "AND biblionumber = ?", (after.get(r["biblionumber"], ""), job_id, chunk,
                                                        r["biblionumber"]))
            n += 1
    store.set_chunk(job_id, chunk, state="applied", applied=now())
    _settle(store, job_id)
    states = [r["state"] for r in store.applied(job_id, chunk)]
    return {"applied": n, "skipped_changed": states.count("skipped-changed"),
            "skipped_deleted": states.count("skipped-deleted"), "skipped_match": states.count("skipped-match")}


def failed(store: Store, job_id: int, chunk: int, note: str) -> None:
    store.set_chunk(job_id, chunk, state="failed", note=note[:300])
    _settle(store, job_id)


def _settle(store: Store, job_id: int) -> None:
    states = [c["state"] for c in store.chunks(job_id)]
    if states and all(s == "applied" for s in states):
        store.set(job_id, state="applied")
    elif any(s == "applied" for s in states):
        store.set(job_id, state="partly-applied")
    else:
        store.set(job_id, state="ready")


def applied_ids(store: Store, job_id: int) -> list[int]:
    return [r["biblionumber"] for r in store.applied(job_id) if r["state"] == "applied"]


def revert_plan(store: Store, job_id: int, current: dict[int, str], everything: bool = False
                ) -> list[tuple[int, int, list[int]]]:
    """(chunk, Koha batch, biblionumbers to keep) per applied chunk, newest
    first. Kept: edited after Apply (005 changed) or deleted since."""
    out = []
    for c in reversed(store.chunks(job_id)):
        if c["state"] != "applied" or not c["batch"]:
            continue
        keep = []
        if not everything:
            for r in store.applied(job_id, c["chunk"]):
                if r["state"] == "applied" and current.get(r["biblionumber"]) != r["f005"]:
                    keep.append(r["biblionumber"])
        out.append((c["chunk"], c["batch"], keep))
    if out:
        store.set(job_id, state="reverting")
    return out


def reverted(store: Store, job_id: int, chunk: int, kept: list[int]) -> None:
    keep = set(kept)
    for r in store.applied(job_id, chunk):
        if r["state"] == "applied":
            store.conn.execute("UPDATE applied SET state = ? WHERE job_id = ? AND chunk = ? AND biblionumber = ?",
                               ("kept" if r["biblionumber"] in keep else "reverted", job_id, chunk,
                                r["biblionumber"]))
    store.set_chunk(job_id, chunk, state="reverted")
    states = [c["state"] for c in store.chunks(job_id)]
    store.set(job_id, state="reverted" if "applied" not in states else "partly-applied")
