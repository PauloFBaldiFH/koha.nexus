"""Koha's z3950servers rows for the gateway, generated from targets.json.

    python -m sru_gateway.koha_sql            # prints the SQL
    python -m sru_gateway.koha_sql --write    # rewrites deploy/koha-z3950servers.sql
                                              # and the koha.nexus panel's list

The panel's list (panel/kei_panel/data/z3950_targets.json) is the same
targets, under the same four headings, each one sru.koha.nexus:443/sru/<id>.

Run the file on a Koha server (INSTANCE = the Koha instance's name):

    sudo koha-mysql INSTANCE < deploy/koha-z3950servers.sql

Every target becomes one SRU row: host https://sru.koha.nexus, port 443,
database sru/<id>. Running it again changes nothing. It only touches the
gateway's own rows (database sru/..., on the gateway's current or older
addresses), so the librarian's other servers are never changed:

  1. rows on the gateway's older addresses (137.131.205.31:5000, the VPS's
     private 10.0.0.60 on any port, 5001 included, with or without http(s)://,
     sru.koha.nexus without https) move to the new one; their database is
     read as sru/<id> whether it was written sru/<id>, /sru/<id> or a bare <id>;
  2. renamed ids follow their new name, and a row left twice is kept once;
  3. ids the gateway no longer serves are removed;
  4. each target's name and settings are refreshed, keeping the librarian's
     "checked" and rank, and a missing target is added.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import targets as tg
from .config import TARGETS_FILE

OUT = Path(__file__).resolve().parents[1] / "deploy" / "koha-z3950servers.sql"
PANEL_LIST = Path(__file__).resolve().parents[2] / "panel" / "kei_panel" / "data" / "z3950_targets.json"
HOST = "https://sru.koha.nexus"
PORT = 443
# The gateway's older addresses. 10.0.0.60 is the VPS's private address: rows
# on it (port 5000 or the 5001 of the old Zeus spec) time out from any other
# machine. Every port counts, since no other server lives on these hosts.
OLD_IPS = ("137.131.205.31", "10.0.0.60")
OLD_HOSTS = (*OLD_IPS, *(f"{s}://{ip}" for s in ("http", "https") for ip in OLD_IPS),
             "sru.koha.nexus", "http://sru.koha.nexus", HOST)
# An SRU server answers MARCXML: Koha's syntax must say MARC21 (USMARC makes
# Koha expect ISO 2709 and show no record; tested live, see PR #62).
SYNTAX = "MARC21"
ENCODING = "utf8"
TIMEOUT = 30
SRU_OPTIONS = "sru=get,sru_version=1.1"
SRU_FIELDS = ("title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,"
              "srchany=cql.serverChoice")
CHECKED = ("bn", "ufsc", "usp", "senado")
# Ids of the 2026-10-11 list that the 2026-10-15 list renamed.
RENAMED = {
    "uw_madison": "wisconsin", "psu": "pennstate", "utoronto": "toronto", "bcl": "castilla-leon",
    "sbn_it": "italia", "abes_fr": "abes-franca", "swb_de": "swb-alemanha", "uhamburg": "tuhh-alemanha",
    "bn_polonia": "polonia", "slsp": "suica", "nkc": "tchequia", "rsl": "russia-state",
    "bashkir": "bashkir-russia", "bna": "argentina", "pucp": "pucp-peru", "upc_peru": "upc-peru",
    "juac_julac": "hong-kong", "pergamum": "all", "biblored": "colombia", "monash_sa": "africa-do-sul",
    "aladi": "barcelona",
}


def q(value) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def render(table: dict[str, tg.Target]) -> str:
    ids = list(table)
    mine = f"recordtype = 'biblio' AND servertype = 'sru' AND host = {q(HOST)} AND port = {PORT}"
    old_rows = (f"recordtype = 'biblio' AND servertype = 'sru' "
                f"AND host IN ({', '.join(q(h) for h in OLD_HOSTS)})")
    out = [
        "-- Koha's z3950servers rows for the koha.nexus SRU gateway (sru.koha.nexus).",
        "-- Generated from sru-bridge/sru_gateway/targets.json by",
        "-- python -m sru_gateway.koha_sql --write: edit targets.json, not this file.",
        "--   sudo koha-mysql INSTANCE < koha-z3950servers.sql",
        "-- Only the gateway's own rows (database sru/...) are touched; re-runnable.",
        "",
        "SET NAMES utf8mb4;",
        "START TRANSACTION;",
        "",
        "-- 1. Older addresses of the gateway (any port, 10.0.0.60:5001 included) move to",
        "--    https://sru.koha.nexus:443, the database written sru/<id>.",
        f"UPDATE z3950servers SET db = CONCAT('sru/', TRIM(LEADING '/' FROM db))",
        f" WHERE {old_rows} AND db <> '' AND db NOT LIKE 'sru/%' AND db NOT LIKE '/sru/%'",
        "   AND TRIM(LEADING '/' FROM db) NOT LIKE '%/%';",
        f"UPDATE z3950servers SET db = TRIM(LEADING '/' FROM db) WHERE {old_rows} AND db LIKE '/sru/%';",
        f"UPDATE z3950servers SET host = {q(HOST)}, port = {PORT}",
        f" WHERE {old_rows} AND db LIKE 'sru/%';",
        "",
        "-- 2. Renamed ids, then one row per id.",
    ]
    for old, new in RENAMED.items():
        if new in table:
            out.append(f"UPDATE z3950servers SET db = {q('sru/' + new)} WHERE {mine} AND db = {q('sru/' + old)};")
    out += [
        "DELETE a FROM z3950servers a JOIN z3950servers b",
        "    ON a.db = b.db AND a.host = b.host AND a.port = b.port AND a.recordtype = b.recordtype",
        "   AND a.servertype = b.servertype AND a.id > b.id",
        f" WHERE a.recordtype = 'biblio' AND a.servertype = 'sru' AND a.host = {q(HOST)} AND a.port = {PORT};",
        "",
        "-- 3. Ids the gateway no longer serves.",
        f"DELETE FROM z3950servers WHERE {mine} AND db LIKE 'sru/%'",
        f"   AND db NOT IN ({', '.join(q('sru/' + i) for i in ids)});",
        "",
        "-- 4. Each target: settings refreshed (checked and rank kept), added when missing.",
    ]
    group = None
    for rank, t in enumerate(table.values(), 1):
        if t.group != group:
            group = t.group
            n = list(tg.GROUPS).index(group) + 1
            out += ["", f"-- [{n}] {tg.GROUPS[group]}"]
        db = q("sru/" + t.id)
        out.append(f"UPDATE z3950servers SET servername = {q(t.name)}, syntax = {q(SYNTAX)}, "
                   f"encoding = {q(ENCODING)}, timeout = {TIMEOUT}, sru_options = {q(SRU_OPTIONS)}, "
                   f"sru_fields = {q(SRU_FIELDS)} WHERE {mine} AND db = {db};")
        out.append("INSERT INTO z3950servers (host, port, db, servername, checked, `rank`, syntax, encoding, "
                   "timeout, servertype, recordtype, sru_options, sru_fields, add_xslt) "
                   f"SELECT {q(HOST)}, {PORT}, {db}, {q(t.name)}, {1 if t.id in CHECKED else 0}, {rank}, "
                   f"{q(SYNTAX)}, {q(ENCODING)}, {TIMEOUT}, 'sru', 'biblio', {q(SRU_OPTIONS)}, {q(SRU_FIELDS)}, '' "
                   f"FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM z3950servers WHERE {mine} AND db = {db});")
    out += ["", "COMMIT;", ""]
    return "\n".join(out)


def panel_list(table: dict[str, tg.Target], updated: str) -> str:
    """The koha.nexus panel's curated list: one SRU row per target."""
    items = []
    for t in table.values():
        items.append({
            "name": t.name, "host": HOST.split("://", 1)[1], "port": PORT, "db": f"sru/{t.id}", "kind": "sru",
            "syntax": SYNTAX, "encoding": ENCODING, "schema": "marcxml", "sru_fields": SRU_FIELDS,
            "sru_options": SRU_OPTIONS, "region": t.group, "preselect": t.id in CHECKED,
            "verified": t.verified, "source": "koha.nexus SRU gateway (sru-bridge/sru_gateway/targets.json)",
            "notes": f"Gateway status: {t.status}." + (f" {t.note}" if t.note else ""),
        })
    data = {"schema": 1, "updated": updated,
            "about": ("koha.nexus SRU gateway targets, generated from sru-bridge/sru_gateway/targets.json by "
                      "python -m sru_gateway.koha_sql --write: every one is sru.koha.nexus:443/sru/<id>. "
                      "verified=true: searched live through the gateway. The panel's scan on your server "
                      "tells which ones answer today."),
            "targets": items}
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sru_gateway.koha_sql")
    ap.add_argument("--write", action="store_true", help=f"rewrite {OUT.name}")
    args = ap.parse_args(argv)
    table = tg.load(TARGETS_FILE)
    text = render(table)
    if args.write:
        OUT.write_text(text, encoding="utf-8")
        updated = json.loads(TARGETS_FILE.read_text(encoding="utf-8")).get("updated", "")
        PANEL_LIST.write_text(panel_list(table, updated), encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
