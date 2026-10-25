"""Print the authority seed SQL, optionally applying the managed rank policy.

Pipe the output to `sudo koha-mysql INSTANCE`. No credentials are read here.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def render(enforce: bool = False) -> str:
    path = Path(__file__).resolve().parents[1] / 'docs/sql/koha-authority-servers.sql'
    sql = path.read_text(encoding='utf-8')
    if not enforce:
        return sql
    # Explicit opt-in migration: ordinary seeds keep librarian choices.
    sql += "\nSTART TRANSACTION;\n"
    for host, db, name, rank in (
        ('https://sru.koha.nexus', 'sru/_union-aut', 'Nexus Autoridades (Cloud)', 1),
        ('lx2.loc.gov', 'NAF', 'BIBLIOTECA DOS NOMES DO CONGRESSO', 2),
        ('lx2.loc.gov', 'SAF', 'BIBLIOTECA DOS ASSUNTOS DO CONGRESSO', 2),
        ('https://sru.koha.nexus', 'sru/bn-aut', 'BIBLIOTECA NACIONAL (AUTORIDADES)', 3),
    ):
        port = 210 if host == 'lx2.loc.gov' else 443
        where = f"recordtype = 'authority' AND host = '{host}' AND port = {port} AND db = '{db}'"
        sql += f"SET @keep := (SELECT MIN(id) FROM z3950servers WHERE {where});\n"
        sql += f"UPDATE z3950servers SET checked = 0 WHERE {where} AND id <> @keep;\n"
        sql += f"UPDATE z3950servers SET checked = 1, `rank` = {rank}, servername = '{name}' WHERE id = @keep;\n"
    sql += "UPDATE z3950servers SET checked = 0 WHERE recordtype = 'authority' " \
           "AND host IN ('lx2.loc.gov', 'http://lx2.loc.gov', 'https://lx2.loc.gov') " \
           "AND servertype = 'sru';\nCOMMIT;\n"
    return sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enforce-defaults', action='store_true',
                        help='Reset the four managed ranks/ticks and disable duplicate/legacy LoC authority rows')
    print(render(parser.parse_args().enforce_defaults), end='')


if __name__ == '__main__':
    main()
