"""The staged report of a job: what Apply would change, before anything
reaches Koha.

    report.json   counts: records read, enriched / unchanged / review /
                  no match / error, records with M0, M1, W and R candidates,
                  fields added by group and by source
    report.tsv    one line per record with a change or a review
    report.html   the same counts, then each changed record before/after
                  (added lines marked), then the review list with the local
                  record and the candidate side by side

The HTML shows at most HTML_LIMIT records of each list; the TSV has all.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from nexus_enrich import marc

from .store import Store, detail, unpack

HTML_LIMIT = 1000


def field_text(f: marc.Field) -> str:
    if f.is_control:
        return f"{f.tag}    {f.data}"
    ind = (f.ind1 or " ").replace(" ", "_") + (f.ind2 or " ").replace(" ", "_")
    return f"{f.tag} {ind} " + " ".join(f"${c} {v}" for c, v in f.subfields)


def record_lines(rec: marc.Record) -> list[str]:
    return [f"LDR    {rec.leader}"] + [field_text(f) for f in rec.fields]


def diff_lines(before: marc.Record, after: marc.Record) -> list[tuple[str, str]]:
    """(mark, line) of the two records in order: " " for a line both have,
    "-" for a line only BEFORE has, "+" for a line only AFTER has, a
    replaced field showing its old line just above its new one."""
    a, b = record_lines(before), record_lines(after)
    out: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out += [(" ", line) for line in a[i1:i2]]
        else:
            out += [("-", line) for line in a[i1:i2]]
            out += [("+", line) for line in b[j1:j2]]
    return out


def text_diff(store: Store, job_id: int, biblionumber: int) -> str:
    item = store.item(job_id, biblionumber)
    if item is None:
        return f"biblionumber {biblionumber} is not in job {job_id}\n"
    info = detail(item)
    head = f"# job {job_id}, biblionumber {biblionumber}: {item['status']}\n"
    before, after, other = unpack(item["before"]), unpack(item["after"]), unpack(item["other"])
    if before is not None and after is not None:
        return head + "".join(f"{m} {line}\n" for m, line in diff_lines(before, after))
    out = head + "".join(f"  review: {r}\n" for r in info.get("review", []))
    if before is not None:
        out += "".join(f"  {line}\n" for line in record_lines(before))
    if other is not None:
        out += "# candidate\n" + "".join(f"  {line}\n" for line in record_lines(other))
    return out


def auth_summary(store: Store, job_id: int) -> dict:
    """An authority job's counts: records, then headings by what happens
    to them, the new authorities and where their forms come from."""
    job = store.job(job_id)
    counts = store.counts(job_id)
    actions: Counter = Counter()
    by_source: Counter = Counter()
    standardized = fuzzy = 0
    for row in store.conn.execute("SELECT detail FROM items WHERE job_id = ? AND status != 'error'", (job_id,)):
        for h in json.loads(row[0]).get("headings", []):
            actions[h["action"]] += 1
            standardized += bool(h.get("standardized"))
            fuzzy += bool(h.get("fuzzy")) and h["action"] in ("koha", "new")
    new = store.new_authorities(job_id)
    for a in new:
        by_source[a["source"] or "?"] += 1
    return {
        "kind": "auth", "mode": job.mode or "exact", "job": job_id, "scope": job.scope, "release": job.release,
        "records": job.done, "changed": counts["enriched"], "unchanged": counts["unchanged"],
        "review": counts["review"], "errors": counts["error"],
        "headings": {"read": sum(actions.values()), "linked_before": actions["linked"], "koha": actions["koha"],
                     "new": actions["new"], "review": actions["review"], "no_match": actions["none"],
                     "skipped": actions["skipped"], "standardized": standardized, "fuzzy": fuzzy},
        "new_authorities": len(new), "preliminary": sum(1 for a in new if a["preliminary"]),
        "new_by_source": dict(by_source.most_common()),
        "koha_batches": len(store.chunks(job_id)),
    }


def summary(store: Store, job_id: int) -> dict:
    job = store.job(job_id)
    if job.kind == "auth":
        return auth_summary(store, job_id)
    counts = store.counts(job_id)
    by_group: Counter = Counter()
    by_source: Counter = Counter()
    by_class: Counter = Counter()
    for row in store.conn.execute("SELECT detail FROM items WHERE job_id = ? AND status = 'enriched'", (job_id,)):
        for a in json.loads(row[0]).get("additions", []):
            by_group[a["group"]] += 1
            by_source[a["source"]] += 1
            by_class[a["cls"]] += 1
    return {
        "job": job_id, "scope": job.scope, "release": job.release, "records": job.done,
        "enriched": counts["enriched"], "unchanged": counts["unchanged"], "review": counts["review"],
        "no_match": counts["no-match"], "errors": counts["error"],
        "records_with": counts["records_with"], "pointer_only": counts["pointer_only"],
        "fields_added": counts["fields_added"], "fields_by_class": dict(by_class),
        "fields_by_group": dict(by_group.most_common()), "fields_by_source": dict(by_source.most_common()),
        "koha_batches": len(store.chunks(job_id)),
    }


CSS = """
:root{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--line:#dcdcd6;--card:#fff;--add:#e3f4e1;--addfg:#1d5b1a;
--del:#fbe3e1;--delfg:#8a1c12;--accent:#2f5d8a}
@media (prefers-color-scheme:dark){:root{--bg:#191917;--fg:#ecece8;--muted:#a3a39c;--line:#3a3a36;--card:#232320;
--add:#1f3a1e;--addfg:#bfe8b9;--del:#43201d;--delfg:#f3c2bc;--accent:#8cb6e0}}
*{box-sizing:border-box}body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}main{max-width:1100px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}.muted{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.card b{display:block;font-size:22px}table{border-collapse:collapse;width:100%;background:var(--card)}
td,th{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
details{background:var(--card);border:1px solid var(--line);border-radius:8px;margin:6px 0;padding:6px 10px}
summary{cursor:pointer}pre{margin:8px 0 4px;overflow-x:auto;font:13px/1.45 ui-monospace,Consolas,monospace}
pre span{display:block;padding:0 6px;white-space:pre}.add{background:var(--add);color:var(--addfg)}
.del{background:var(--del);color:var(--delfg)}.side{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media (max-width:700px){.side{grid-template-columns:1fr}}.tag{font-size:12px;border:1px solid var(--line);
border-radius:4px;padding:0 5px;margin-left:4px;color:var(--accent)}
"""


def _pre(lines: list[tuple[str, str]]) -> str:
    cls = {"+": ' class="add"', "-": ' class="del"', " ": ""}
    return "<pre>" + "".join(f"<span{cls[m]}>{m} {html.escape(line)}</span>" for m, line in lines) + "</pre>"


def _cards(s: dict) -> str:
    items = [("Records read", s["records"]), ("Enriched", s["enriched"]), ("Unchanged", s["unchanged"]),
             ("Review", s["review"]), ("No match", s["no_match"]), ("Errors", s["errors"]),
             ("Fields added", s["fields_added"]), ("Koha batches", s["koha_batches"])]
    items += [(f"Records with {k}", v) for k, v in s["records_with"].items()]
    return '<div class="grid">' + "".join(
        f'<div class="card"><b>{v}</b><span class="muted">{html.escape(k)}</span></div>' for k, v in items) + "</div>"


def _table(title: str, data: dict) -> str:
    if not data:
        return ""
    rows = "".join(f"<tr><td>{html.escape(str(k))}</td><td>{v}</td></tr>" for k, v in data.items())
    return f"<h2>{html.escape(title)}</h2><table>{rows}</table>"


def _head(title: str) -> str:
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>")


def write_auth(store: Store, job_id: int, out_dir: Path) -> dict:
    s = auth_summary(store, job_id)
    (out_dir / "report.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out_dir / "report.tsv", "w", encoding="utf-8") as tsv:
        tsv.write("biblionumber\ttag\taction\tbefore\tafter\tsource\tnote\ttitle\n")
        for item in store.items(job_id, "enriched", "review"):
            for h in detail(item).get("headings", []):
                if h["action"] not in ("koha", "new", "review"):
                    continue
                note = h.get("reason", "") or (f"authority {h['authid']}" if h.get("authid") else
                                               f"new authority {h.get('new', '')}")
                tsv.write("\t".join(x.replace("\t", " ") for x in (
                    str(item["biblionumber"] or ""), h["tag"], h["action"], h["before"], h.get("after", ""),
                    h.get("source", ""), note, item["title"])) + "\n")
    with open(out_dir / "authorities.tsv", "w", encoding="utf-8") as tsv:
        tsv.write("id\tkind\theading\tsource\tpreliminary\tfuzzy\n")
        for a in store.new_authorities(job_id):
            tsv.write(f"{a['id']}\t{a['kind']}\t{a['heading']}\t{a['source']}\t{a['preliminary']}\t{a['fuzzy']}\n")

    h = s["headings"]
    cards = [("Records read", s["records"]), ("Records changed", s["changed"]), ("Review", s["review"]),
             ("Headings read", h["read"]), ("Already linked", h["linked_before"]),
             ("Linked to Koha authorities", h["koha"]), ("Linked to new authorities", h["new"]),
             ("Standardised forms", h["standardized"]), ("Headings to review", h["review"]),
             ("No match", h["no_match"]), ("New authorities", s["new_authorities"]),
             ("Koha batches", s["koha_batches"])]
    parts = [_head("Authority report"), f"<h1>Authority job {job_id}: staged report</h1>",
             f"<p class=\"muted\">Scope: {html.escape(s['scope'])}. Mode: {html.escape(s['mode'])}. "
             f"Database: {html.escape(s['release'] or '?')}. Nothing has been written to Koha. Apply makes a "
             f"safety backup first, creates the new authorities, then links the records; Revert undoes both.</p>",
             '<div class="grid">' + "".join(f'<div class="card"><b>{v}</b><span class="muted">{html.escape(k)}'
                                            f'</span></div>' for k, v in cards) + "</div>",
             _table("New authorities by source", s["new_by_source"])]
    new = store.new_authorities(job_id)
    parts.append(f"<h2>New authorities ({len(new)})</h2><p class=\"muted\">Preliminary records (008/33 d, "
                 f"with a 667 note) come from headings gathered from catalogue records or from a close form.</p>")
    for i, a in enumerate(new):
        if i >= HTML_LIMIT:
            parts.append(f"<p class=\"muted\">… {len(new) - HTML_LIMIT} more in authorities.tsv.</p>")
            break
        rec = unpack(a["record"])
        tag = '<span class="tag">preliminary</span>' if a["preliminary"] else ""
        parts.append(f"<details><summary>{html.escape(a['heading'])} · {html.escape(a['source'] or '?')}{tag}"
                     f"</summary>{_pre([(' ', line) for line in record_lines(rec)]) if rec else ''}</details>")
    parts.append(f"<h2>Records changed ({s['changed']})</h2>")
    for i, item in enumerate(store.items(job_id, "enriched")):
        if i >= HTML_LIMIT:
            parts.append(f"<p class=\"muted\">… {s['changed'] - HTML_LIMIT} more in report.tsv.</p>")
            break
        before, after = unpack(item["before"]), unpack(item["after"])
        parts.append(f"<details><summary>{item['biblionumber']} · {html.escape(item['title'])} "
                     f"({item['m0'] + item['m1']} linked, {item['w']} standardised)</summary>"
                     f"{_pre(diff_lines(before, after))}</details>")
    parts.append(f"<h2>Review ({h['review']})</h2><p class=\"muted\">Nothing in this list is applied.</p><table>")
    n = 0
    for item in store.items(job_id, "enriched", "review"):
        for r in detail(item).get("review", []):
            n += 1
            if n <= HTML_LIMIT:
                parts.append(f"<tr><td>{item['biblionumber']}</td><td>{html.escape(r)}</td></tr>")
    parts.append("</table></main></body></html>")
    (out_dir / "report.html").write_text("".join(parts), encoding="utf-8")
    return s


def write(store: Store, job_id: int, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if store.job(job_id).kind == "auth":
        return write_auth(store, job_id, out_dir)
    s = summary(store, job_id)
    (out_dir / "report.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out_dir / "report.tsv", "w", encoding="utf-8") as tsv:
        tsv.write("biblionumber\tstatus\tM0\tM1\tW\tR\tsources\tfields\ttitle\treview\n")
        for item in store.items(job_id, "enriched", "review"):
            info = detail(item)
            adds = info.get("additions", [])
            tsv.write("\t".join([
                str(item["biblionumber"] or ""), item["status"], str(item["m0"]), str(item["m1"]), str(item["w"]),
                str(item["r"]), ",".join(sorted({a["source"] for a in adds})),
                " ".join(a["tag"] for a in adds), item["title"].replace("\t", " "),
                " | ".join(info.get("review", [])).replace("\t", " ")]) + "\n")

    parts = [_head("Enrichment report"),
             f"<h1>Enrichment job {job_id}: staged report</h1>",
             f"<p class=\"muted\">Scope: {html.escape(s['scope'])}. Database: {html.escape(s['release'] or '?')}. "
             f"Nothing has been written to Koha. Apply makes a safety backup first and can be reverted.</p>",
             _cards(s),
             _table("Fields added by class", s["fields_by_class"]),
             _table("Fields added by group", s["fields_by_group"]),
             _table("Fields added by source", s["fields_by_source"])]

    parts.append(f"<h2>Changes ({s['enriched']})</h2>")
    for i, item in enumerate(store.items(job_id, "enriched")):
        if i >= HTML_LIMIT:
            parts.append(f"<p class=\"muted\">… {s['enriched'] - HTML_LIMIT} more in report.tsv.</p>")
            break
        before, after = unpack(item["before"]), unpack(item["after"])
        adds = detail(item).get("additions", [])
        tags = "".join(f'<span class="tag">{c}</span>' for c in ("M0", "M1", "W") if item[c.lower()])
        parts.append(f"<details><summary>{item['biblionumber']} · {html.escape(item['title'])} "
                     f"({len(adds)} added){tags}</summary>{_pre(diff_lines(before, after))}</details>")

    parts.append(f"<h2>Review ({s['review']})</h2><p class=\"muted\">Nothing in this list is applied.</p>")
    for i, item in enumerate(store.items(job_id, "review")):
        if i >= HTML_LIMIT:
            parts.append(f"<p class=\"muted\">… {s['review'] - HTML_LIMIT} more in report.tsv.</p>")
            break
        info = detail(item)
        before, other = unpack(item["before"]), unpack(item["other"])
        reasons = "".join(f"<li>{html.escape(r)}</li>" for r in info.get("review", []))
        left = _pre([(" ", line) for line in record_lines(before)]) if before else ""
        right = _pre([(" ", line) for line in record_lines(other)]) if other else ""
        parts.append(f"<details><summary>{item['biblionumber']} · {html.escape(item['title'])}</summary>"
                     f"<ul>{reasons}</ul><div class=\"side\"><div><b>This catalogue</b>{left}</div>"
                     f"<div><b>Candidate</b>{right}</div></div></details>")
    parts.append("</main></body></html>")
    (out_dir / "report.html").write_text("".join(parts), encoding="utf-8")
    return s
