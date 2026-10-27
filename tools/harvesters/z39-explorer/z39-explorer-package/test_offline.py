#!/usr/bin/env python3
"""Pure offline smoke tests; do not contact any remote service."""
import tempfile
from pathlib import Path
import z39_explorer as m


def record(rectype, tag, contents):
    field = contents + b'\x1e'
    base = 24 + 12 + 1
    length = base + len(field) + 1
    leader = bytearray(b' ' * 24)
    leader[:5] = f'{length:05d}'.encode()
    leader[5] = ord('n')
    leader[6] = ord(rectype)
    leader[10] = ord('2')
    leader[11] = ord('2')
    leader[12:17] = f'{base:05d}'.encode()
    leader[20:24] = b'4500'
    directory = (tag + f'{len(field):04d}' + '00000').encode()
    return bytes(leader) + directory + b'\x1e' + field + b'\x1d'


def main():
    auth = record('z', '100', b'1 \x1faShakespeare, William')
    bib = record('a', '245', b'10\x1faA short history')
    uni = record('a', '200', b'10\x1faA title')
    assert m.marc_record(auth) == ('authority', len(auth))
    assert m.marc_record(bib) == ('bibliographic', len(bib))
    assert m.marc_record(uni) == ('other', len(uni))
    assert m.marc_record(b'not marc') == ('', 0)
    assert m.normalize({'host': '127.0.0.1', 'port': '210', 'database': 'lcdb'}) is None
    assert m.normalize({'host': 'lx2.loc.gov', 'port': '210', 'database': 'NAF'}) is not None
    with tempfile.TemporaryDirectory() as tmp:
        db = m.connect_db(Path(tmp) / 'db.sqlite3')
        n = m.insert_many(db, m.read_seeds(m.BASE / 'seeds.tsv'), 500)
        assert n >= 15, n
        m.export(db, Path(tmp) / 'reports')
        assert (Path(tmp) / 'reports' / 'resumo.json').exists()
        db.close()
    print('All offline smoke tests passed.')


if __name__ == '__main__':
    main()
