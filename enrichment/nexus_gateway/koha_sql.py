"""Koha's z3950servers rows for the koha.nexus gateway, from targets.json.

    python -m nexus_gateway koha-sql | sudo koha-mysql INSTANCE

One SRU row per target (database sru/<id>) plus sru/_union, all on the
gateway behind the Cloudflare tunnel, https://sru.koha.nexus port 443
(Koha speaks HTTPS when the host starts with https://). Running it again
changes nothing. Only the gateway's own rows are touched (database
sru/..., on this address or an older one of the gateway's), so the
librarian's other servers are never changed:

  0. the rows of the retired local bridges go: the Zeus bridge's
     (127.0.0.1:5000, database "sru") and the Pergamum bridge's
     (127.0.0.1:5006); sru/_union and sru/all answer for them;
  1. rows on the gateway's older addresses (the local gateway
     127.0.0.1:5000, the VPS's 137.131.205.31 and 10.0.0.60, sru.koha.nexus
     without https or on another port) move to the tunnel;
  2. renamed ids follow their new name, and a row left twice is kept once;
  3. ids no longer served are removed;
  4. each target's name and settings are refreshed (rank kept), and a
     missing one is added;
  5. sru/_union and sru/all (Rede Pergamum, served by the gateway on
     Paulo's server) are the gateway's only ticked rows: sru/_union
     searches every catalogue at once, and Koha waits for the slowest
     ticked row;
  6. the authority row sru/_union-aut (record type authority) for Koha's
     authority search in cataloguing: moved from an older address, added
     ticked, then refreshed, its tick and rank left to the librarian;
  7. the local-first catalogues (targets.json "local_first": UNESP, UFPR,
     UNIFESP, UnB, UFU, which static.db holds nearly whole) are ticked and
     ranked 1 to 5, first in Koha's search after sru/_union (rank 0);
  8. a row of the library's own for one of those institutions (another
     server whose host is one of the target's "legacy_hosts" or a subdomain
     of one, e.g. z3950.unifesp.br or unesp.alma.exlibrisgroup.com) is kept
     as the fallback: unticked, so Koha's search no longer waits on it, and
     ranked after the gateway's rows (LEGACY_RANK). Its rank and tick are
     saved first in LEGACY_TABLE, once: a row the librarian ticks again
     afterwards stays ticked.

Steps 7 and 8 are undone with

    python -m nexus_gateway koha-sql --undo-local-first | sudo koha-mysql INSTANCE

which gives the saved rows their rank and tick back, unticks the five
gateway rows and leaves a mark (LEGACY_TABLE id 0) so that later runs
(the installer runs koha-sql at every update) skip steps 7 and 8;
--redo-local-first removes the mark and runs them again.

Other authority rows (the Library of Congress, the Biblioteca Nacional)
are left alone.
"""

from __future__ import annotations

import json
from pathlib import Path

from .targets import AUTH_UNION, GROUPS, UNION, Target, local_first

# The panel's curated list (written by panel_list()); in a checkout only.
PANEL_LIST = Path(__file__).resolve().parents[2] / "panel" / "kei_panel" / "data" / "z3950_targets.json"
# The direct Z39.50 servers, the panel's primary targets (read by panel_list()).
DIRECT_LIST = PANEL_LIST.with_name("z3950_direct.json")
DIRECT_SOURCE = "koha.nexus direct Z39.50 servers (panel/kei_panel/data/z3950_direct.json)"
FALLBACK_RANK = 500          # Koha rank of the first gateway row: after every direct server
PERGAMUM_BRIDGE_PORT = 5006

# Where Koha reaches the gateway: the Cloudflare tunnel (Paulo, 2026-10-18).
GATEWAY_HOST = "sru.koha.nexus"
GATEWAY_PORT = 443
KOHA_HOST = "https://" + GATEWAY_HOST     # Koha's row: the https:// prefix makes it speak HTTPS
LOCAL_HOST, LOCAL_PORT = "127.0.0.1", 5000
OLD_IPS = ("137.131.205.31", "10.0.0.60")
OLD_HOSTS = (GATEWAY_HOST, *OLD_IPS,
             *(f"{s}://{h}" for s in ("http", "https") for h in (GATEWAY_HOST, *OLD_IPS)))
SYNTAX = "MARC21"            # an SRU server answers MARCXML: Koha's syntax must say MARC21
ENCODING = "utf8"
TIMEOUT = 15                 # the gateway answers within its 6 s budget
SRU_OPTIONS = "sru=get,sru_version=1.1"
SRU_FIELDS = ("title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,"
              "srchany=cql.serverChoice")
UNION_NAME = "KOHA.NEXUS (TODOS OS CATÁLOGOS)"
# The library's own rows for a local-first institution: saved here, then
# unticked and ranked after the gateway's rows (steps 7 and 8).
LEGACY_TABLE = "koha_nexus_legacy_z3950"
LEGACY_RANK = 900
OFF_ID = 0                   # LEGACY_TABLE's mark: --undo-local-first was run
# Gateway ids that are primary targets, not fallback: Rede Pergamum, which
# the gateway on Paulo's server answers (Paulo, 2026-10-18). Ticked in Koha
# and preselected in the panel, in the "koha.nexus" heading.
PRIMARY_IDS = ("all",)
# The koha.nexus Catalog Network, the shared catalogue (catalog-network/),
# behind its own tunnel hostname; the installer's catalog-network task puts
# it in Koha.
CATALOG_HOST = "catalog.koha.nexus"
CATALOG_DB = "sru"
CATALOG_NAME = "Rede koha.nexus (Catalogação Compartilhada)"
# Koha's authority search form (cataloguing) through the row's SRU search
# fields; authorities.py reads these indexes.
AUTH_SRU_FIELDS = ("nameany=bath.name,authorany=bath.name,authorpersonal=bath.personalName,"
                   "authorcorp=bath.corporateName,authormeetingcon=bath.conferenceName,subject=dc.subject,"
                   "subjectsubdiv=dc.subject,title=bath.uniformTitle,uniformtitle=bath.uniformTitle,"
                   "srchany=cql.serverChoice")
AUTH_NAME = "Nexus Autoridades (Cloud)"
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


def _upsert(mine: str, host: str, port: int, db: str, name: str, checked: int, rank: int,
            recordtype: str = "biblio", fields: str = SRU_FIELDS) -> list[str]:
    return [
        f"UPDATE z3950servers SET servername = {q(name)}, syntax = {q(SYNTAX)}, encoding = {q(ENCODING)}, "
        f"timeout = {TIMEOUT}, sru_options = {q(SRU_OPTIONS)}, sru_fields = {q(fields)} "
        f"WHERE {mine} AND db = {q(db)};",
        "INSERT INTO z3950servers (host, port, db, servername, checked, `rank`, syntax, encoding, timeout, "
        "servertype, recordtype, sru_options, sru_fields, add_xslt) "
        f"SELECT {q(host)}, {port}, {q(db)}, {q(name)}, {checked}, {rank}, {q(SYNTAX)}, {q(ENCODING)}, {TIMEOUT}, "
        f"'sru', {q(recordtype)}, {q(SRU_OPTIONS)}, {q(fields)}, '' "
        f"FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM z3950servers WHERE {mine} AND db = {q(db)});",
    ]


def render(table: dict[str, Target], host: str = KOHA_HOST, port: int = GATEWAY_PORT) -> str:
    dbs = ["sru/" + UNION] + ["sru/" + i for i in table]
    mine = f"recordtype = 'biblio' AND servertype = 'sru' AND host = {q(host)} AND port = {port}"
    elsewhere = (f"servertype = 'sru' AND NOT (host = {q(host)} AND port = {port})"
                 f" AND (host IN ({', '.join(q(h) for h in (*OLD_HOSTS, LOCAL_HOST))}))"
                 f" AND NOT (host = {q(LOCAL_HOST)} AND port <> {LOCAL_PORT})")
    old = f"recordtype = 'biblio' AND {elsewhere}"
    local = f"recordtype = 'biblio' AND servertype = 'sru' AND host = {q(LOCAL_HOST)}"
    out = [
        "-- Koha's z3950servers rows for the koha.nexus gateway "
        f"({host}:{port}).",
        "-- Generated by python -m nexus_gateway koha-sql from targets.json; re-runnable.",
        "-- Only the gateway's own rows (database sru/...) are touched, and (step 8) the library's",
        "-- rows for the local-first institutions, whose rank and tick are saved first.",
        "",
        "SET NAMES utf8mb4;",
        LEGACY_DDL,
        "START TRANSACTION;",
        "",
        "-- 0. The retired local bridges (Zeus on this port, database sru; Pergamum on 5006).",
        f"DELETE FROM z3950servers WHERE {local} AND port = {LOCAL_PORT} AND IFNULL(db, '') IN ('', 'sru', '/sru');",
        f"DELETE FROM z3950servers WHERE {local} AND port = {PERGAMUM_BRIDGE_PORT};",
        "",
        "-- 1. Rows on the gateway's older addresses move here.",
        "UPDATE z3950servers SET db = CONCAT('sru/', TRIM(LEADING '/' FROM db))",
        f" WHERE {old} AND db <> '' AND db NOT LIKE 'sru/%' AND db NOT LIKE '/sru/%'",
        "   AND TRIM(LEADING '/' FROM db) NOT LIKE '%/%';",
        f"UPDATE z3950servers SET db = TRIM(LEADING '/' FROM db) WHERE {old} AND db LIKE '/sru/%';",
        f"UPDATE z3950servers SET host = {q(host)}, port = {port} WHERE {old} AND db LIKE 'sru/%';",
        "",
        "-- 2. Renamed ids, then one row per id.",
    ]
    for was, now in RENAMED.items():
        if now in table:
            out.append(f"UPDATE z3950servers SET db = {q('sru/' + now)} WHERE {mine} AND db = {q('sru/' + was)};")
    out += [
        "DELETE a FROM z3950servers a JOIN z3950servers b",
        "    ON a.db = b.db AND a.host = b.host AND a.port = b.port AND a.recordtype = b.recordtype",
        "   AND a.servertype = b.servertype AND a.id > b.id",
        f" WHERE a.recordtype = 'biblio' AND a.servertype = 'sru' AND a.host = {q(host)} AND a.port = {port};",
        "",
        "-- 3. Ids no longer served.",
        f"DELETE FROM z3950servers WHERE {mine} AND db LIKE 'sru/%'",
        f"   AND db NOT IN ({', '.join(q(d) for d in dbs)});",
        "",
        "-- 4. Every catalogue (sru/_union first).",
    ]
    out += _upsert(mine, host, port, "sru/" + UNION, UNION_NAME, 1, 0)
    group = None
    for rank, t in enumerate(table.values(), 1):
        if t.group != group:
            group = t.group
            out += ["", f"-- [{list(GROUPS).index(group) + 1}] {GROUPS[group]}"]
        out += _upsert(mine, host, port, "sru/" + t.id, t.name, 0, rank)
    ticked = ", ".join(q("sru/" + i) for i in (UNION, *PRIMARY_IDS))
    out += ["", "-- 5. sru/_union and the primary catalogues (Rede Pergamum) are the gateway's only ticked rows.",
            f"UPDATE z3950servers SET checked = IF(db IN ({ticked}), 1, 0) WHERE {mine} AND db LIKE 'sru/%';",
            "", "-- 6. Authority headings, for Koha's authority search in cataloguing (one row)."]
    auth = f"recordtype = 'authority' AND servertype = 'sru' AND host = {q(host)} AND port = {port}"
    out += [f"UPDATE z3950servers SET host = {q(host)}, port = {port}"
            f" WHERE recordtype = 'authority' AND {elsewhere} AND db = {q('sru/' + AUTH_UNION)};",
            "DELETE a FROM z3950servers a JOIN z3950servers b",
            "    ON a.db = b.db AND a.host = b.host AND a.port = b.port AND a.recordtype = b.recordtype",
            "   AND a.servertype = b.servertype AND a.id > b.id",
            f" WHERE a.recordtype = 'authority' AND a.servertype = 'sru' AND a.host = {q(host)} AND a.port = {port}"
            f" AND a.db = {q('sru/' + AUTH_UNION)};"]
    out += _upsert(auth, host, port, "sru/" + AUTH_UNION, AUTH_NAME, 1, 1, "authority", AUTH_SRU_FIELDS)
    out += _local_first(table, mine)
    out += ["", "COMMIT;", ""]
    return "\n".join(out)


LEGACY_DDL = (f"CREATE TABLE IF NOT EXISTS {LEGACY_TABLE} (id INT NOT NULL PRIMARY KEY, "
              "target VARCHAR(40) NOT NULL, rank_before INT NULL, checked_before SMALLINT NULL, "
              "state VARCHAR(10) NOT NULL DEFAULT 'saved', saved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);")
_ON = f"NOT EXISTS (SELECT 1 FROM {LEGACY_TABLE} WHERE id = {OFF_ID})"


def legacy_match(t: Target) -> str:
    """SQL: a z3950servers row whose host is one of T's legacy hosts or a
    subdomain of one (any http(s):// prefix, port or path after it)."""
    res = [r"(^|[/.])" + h.replace(".", "[.]") + r"([:/]|$)" for h in t.legacy_hosts]
    return "(" + " OR ".join(f"host REGEXP {q(r)}" for r in res) + ")"


def _local_first(table: dict[str, Target], mine: str) -> list[str]:
    firsts = local_first(table)
    if not firsts:
        return []
    out = ["", "-- 7. The local-first catalogues (static.db holds them nearly whole): ticked, first after sru/_union.",
           "--    Skipped after --undo-local-first."]
    for t in firsts:
        out.append(f"UPDATE z3950servers SET checked = 1, `rank` = {t.local_first}"
                   f" WHERE {mine} AND db = {q('sru/' + t.id)} AND {_ON};")
    out += ["", "-- 8. The library's own rows for those institutions: saved once, then unticked and ranked",
            f"--    after the gateway's rows ({LEGACY_RANK}); a row ticked again later is the librarian's.",
            f"DELETE b FROM {LEGACY_TABLE} b LEFT JOIN z3950servers z ON z.id = b.id"
            f" WHERE b.id <> {OFF_ID} AND z.id IS NULL;"]
    for t in firsts:
        if not t.legacy_hosts:
            continue
        out.append(f"INSERT IGNORE INTO {LEGACY_TABLE} (id, target, rank_before, checked_before)"
                   f" SELECT id, {q(t.id)}, `rank`, checked FROM z3950servers"
                   f" WHERE recordtype = 'biblio' AND {legacy_match(t)} AND {_ON};")
    out.append(f"UPDATE z3950servers z JOIN {LEGACY_TABLE} b ON b.id = z.id AND b.state = 'saved'"
               f" SET z.checked = 0, z.`rank` = GREATEST(IFNULL(z.`rank`, 0), {LEGACY_RANK}), b.state = 'demoted';")
    return out


def render_undo(table: dict[str, Target], host: str = KOHA_HOST, port: int = GATEWAY_PORT) -> str:
    """Steps 7 and 8 undone, and kept undone by later runs (the mark)."""
    mine = f"recordtype = 'biblio' AND servertype = 'sru' AND host = {q(host)} AND port = {port}"
    out = ["-- Undo koha-sql's local-first steps (7 and 8): the library's rows get their rank and tick back,",
           "-- the five gateway rows are unticked, and the mark keeps later koha-sql runs from redoing it.",
           "", "SET NAMES utf8mb4;", LEGACY_DDL, "START TRANSACTION;",
           f"UPDATE z3950servers z JOIN {LEGACY_TABLE} b ON b.id = z.id AND b.state = 'demoted'"
           " SET z.`rank` = b.rank_before, z.checked = b.checked_before, b.state = 'restored';",
           f"UPDATE {LEGACY_TABLE} SET state = 'restored' WHERE state = 'saved';",
           f"INSERT IGNORE INTO {LEGACY_TABLE} (id, target, state) VALUES ({OFF_ID}, '_off', 'off');"]
    ranks = {t.id: n for n, t in enumerate(table.values(), 1)}
    for t in local_first(table):
        out.append(f"UPDATE z3950servers SET checked = 0, `rank` = {ranks[t.id]}"
                   f" WHERE {mine} AND db = {q('sru/' + t.id)};")
    out += ["COMMIT;", ""]
    return "\n".join(out)


def render_redo(table: dict[str, Target], host: str = KOHA_HOST, port: int = GATEWAY_PORT) -> str:
    """The mark and the saved rows forgotten, then the whole of render():
    the library's rows are saved and moved behind again as they are now."""
    return ("-- Redo koha-sql's local-first steps: forget the undo mark and the saved rows, then run them.\n"
            f"{LEGACY_DDL}\nDELETE FROM {LEGACY_TABLE};\n\n" + render(table, host, port))


def flag(country: str) -> str:
    """The flag emoji of an ISO 3166 code; the globe for none (several
    countries, or a catalogue of catalogues)."""
    cc = (country or "").upper()
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc) if len(cc) == 2 and cc.isalpha() else "\U0001F310"


def _direct_rows(path: Path) -> tuple[list[dict], dict[str, str], dict[str, list[str]]]:
    """The panel rows of the direct Z39.50 servers (DIRECT_LIST): Koha
    syntax USMARC for MARC21 over Z39.50, the login only by its .env name;
    the gateway ids they cover (their "sru_fallback"), with their name; and
    for each such id the panel keys (host:port/db) of the direct rows that
    cover it, the servers its backup row stands in for."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    out, covered, keys = [], {}, {}
    for s in data.get("servers", []):
        row = {"name": s["name"], "host": s["host"], "port": s["port"], "db": s["db"], "kind": "zed",
               "syntax": "UNIMARC" if s.get("syntax") == "UNIMARC" else "USMARC",
               "encoding": s.get("encoding", "utf8"), "region": s["category"], "country": s.get("country", ""),
               "flag": s.get("flag") or flag(s.get("country", "")), "priority": "primary",
               "preselect": bool(s.get("preselect")), "verified": True,
               "source": DIRECT_SOURCE, "notes": s.get("notes", "")}
        if s.get("recordtype") == "authority":
            row["recordtype"] = "authority"
        if s.get("login_env"):
            row["login_env"] = s["login_env"]
            row["login"] = True
        if s.get("sru_fallback"):
            covered[s["sru_fallback"]] = s["name"]
            keys.setdefault(s["sru_fallback"], []).append(f"{s['host'].lower()}:{s['port']}/{s['db']}")
        out.append(row)
    return out, covered, keys


def panel_list(table: dict[str, Target], keep_from: str | Path | None = None, host: str = GATEWAY_HOST,
               port: int = GATEWAY_PORT, updated: str = "", direct: str | Path | None = None) -> str:
    """The koha.nexus panel's curated list. First the koha.nexus servers
    (the shared catalogue, Rede Pergamum and the local-first catalogues),
    preselected; then the direct Z39.50 servers
    (DIRECT, default the checkout's z3950_direct.json), the primary targets
    (a local-first library's own server as its gateway row's backup),
    by region, then the authority files: the other authority files of the
    current list (KEEP_FROM, default the checkout's), kept as they are, the
    direct ones and sru/_union-aut. Last, the fallback: sru/_union and
    one row per gateway target, never preselected and ranked after every
    direct server (FALLBACK_RANK on), for the libraries and regions no
    direct server covers."""
    keep_path = Path(keep_from) if keep_from else PANEL_LIST
    old = json.loads(keep_path.read_text(encoding="utf-8")) if keep_path.exists() else {}
    authorities = [t for t in old.get("targets", []) if t.get("recordtype") == "authority"
                   and t.get("db") != "sru/" + AUTH_UNION and t.get("source") != DIRECT_SOURCE]
    rows, covered, backup_for = _direct_rows(Path(direct) if direct else DIRECT_LIST)
    rank = iter(range(FALLBACK_RANK, 10000))

    def row(db: str, name: str, region: str, verified: bool, notes: str, country: str = "",
            at: int = 0) -> dict:
        return {"name": name, "host": host, "port": port, "db": db, "kind": "sru", "syntax": SYNTAX,
                "encoding": ENCODING, "schema": "marcxml", "sru_fields": SRU_FIELDS, "sru_options": SRU_OPTIONS,
                "timeout": TIMEOUT, "rank": at or next(rank), "region": region, "country": country,
                "flag": flag(country), "priority": "fallback", "preselect": False, "verified": verified,
                "source": "koha.nexus gateway (enrichment/nexus_gateway/targets.json)", "notes": notes}

    # The koha.nexus servers, first and preselected: the shared catalogue
    # and the gateway's primary catalogues (Rede Pergamum).
    own = [{"name": CATALOG_NAME, "host": CATALOG_HOST, "port": port, "db": CATALOG_DB, "kind": "sru",
            "syntax": SYNTAX, "encoding": ENCODING, "schema": "marcxml", "sru_fields": SRU_FIELDS,
            "sru_options": SRU_OPTIONS, "timeout": TIMEOUT, "rank": 1, "region": "koha_nexus", "country": "BR",
            "flag": flag("BR"), "priority": "primary", "preselect": True, "verified": True,
            "source": "koha.nexus Catalog Network (catalog-network/)",
            "notes": ("The shared catalogue of the koha.nexus libraries (catalog.koha.nexus). The panel's "
                      "Community network switch adds or removes the same row.")}]
    for i in PRIMARY_IDS:
        if i in table:
            t = table[i]
            r = row("sru/" + i, t.name, "koha_nexus", True,
                    "On the koha.nexus gateway (sru.koha.nexus)." + (f" {t.note}" if t.note else ""), t.country,
                    len(own) + 1)
            r.update(priority="primary", preselect=True)
            own.append(r)
    # The local-first catalogues: static.db holds them nearly whole, so
    # they answer at once; a direct server of the same library becomes
    # their backup (shown only when the gateway row returns nothing).
    firsts = {t.id for t in local_first(table)}
    for t in local_first(table):
        how = ("static.db, then live " + t.kind.upper()) if t.live else "static.db only"
        r = row("sru/" + t.id, t.name, "koha_nexus", True,
                f"Local first: static.db holds this catalogue; answers from {how}." + (
                    f" Its direct Z39.50 row {covered[t.id]} is the backup." if t.id in covered else ""),
                t.country, t.local_first)
        r.update(priority="primary", preselect=True)
        own.append(r)
    for r in rows:
        fid = next((i for i, keys in backup_for.items() if i in firsts
                    and f"{r['host'].lower()}:{r['port']}/{r['db']}" in keys), None)
        if fid is not None:
            r.update(priority="fallback", preselect=False, backup_for=[f"{host.lower()}:{port}/sru/{fid}"])
    fallback = [row("sru/" + UNION, UNION_NAME, "sru_national", True,
                    "Fallback: every gateway catalogue at once (static.db, then the Z39.50/SRU catalogues live).")]
    for t in table.values():
        if t.id in PRIMARY_IDS or t.id in firsts:
            continue
        how = ("static.db, then live " + t.kind.upper()) if t.live else "static.db only"
        cover = f" Fallback: the direct Z39.50 row {covered[t.id]} covers this library." if t.id in covered else ""
        fallback.append(row("sru/" + t.id, t.name, "sru_" + t.group, t.status == "verified",
                            f"Status: {t.status}; answers from {how}." + (f" {t.note}" if t.note else "") + cover,
                            t.country))
        if t.id in backup_for:
            # The panel shows this backup only when these direct servers return no record.
            fallback[-1]["backup_for"] = backup_for[t.id]
    own_auth = {"name": AUTH_NAME, "host": host, "port": port, "db": "sru/" + AUTH_UNION, "kind": "sru",
                "syntax": SYNTAX, "encoding": ENCODING, "schema": "marcxml", "sru_fields": AUTH_SRU_FIELDS,
                "sru_options": SRU_OPTIONS, "recordtype": "authority", "timeout": TIMEOUT,
                "region": "authorities", "country": "BR", "flag": flag(""), "verified": True,
                "source": "koha.nexus gateway (enrichment/nexus_gateway/authorities.py)",
                "notes": ("Authority headings of static.db (Biblioteca Nacional first, then the Brazilian catalogues, "
                          "then the Library of Congress; subjects never from LCSH), as MARC21 authority records, "
                          "for Koha's authority search in cataloguing.")}
    for t in authorities:
        t.setdefault("flag", flag(t.get("country") or ("US" if t.get("host") == "lx2.loc.gov" else "")))
    biblio = [r for r in rows if r.get("recordtype") != "authority"]
    direct_auth = [r for r in rows if r.get("recordtype") == "authority"]
    data = {"schema": 1, "updated": updated or old.get("updated", ""),
            "about": ("koha.nexus panel targets, generated by python -m nexus_gateway panel-list. First the "
                      "koha.nexus servers (the shared catalogue catalog.koha.nexus, Rede Pergamum and the "
                      "local-first catalogues UNESP, UFPR, UNIFESP, UnB and UFU on the gateway), preselected; "
                      "then the direct "
                      "Z39.50 servers of panel/kei_panel/data/z3950_direct.json, the primary targets, by region "
                      "(those of the local-first libraries as their backup); then the authority files (recordtype authority) for Koha's authority search; last the "
                      "fallback, the koha.nexus gateway behind the Cloudflare tunnel (sru.koha.nexus:443/sru/<id>, from "
                      "enrichment/nexus_gateway/targets.json), for libraries and regions no direct server covers: "
                      "never preselected and ranked after every direct server."),
            "targets": own + biblio + authorities + direct_auth + [own_auth] + fallback}
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"
