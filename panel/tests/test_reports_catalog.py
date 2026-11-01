"""Report inventory, stable identities, SQL duplication and translation contracts."""
import base64
from pathlib import Path
import re
import subprocess

from conftest import REPO


def reports():
    source = (REPO / 'installer').read_text()
    helper = source[source.index('_rp() {'):source.index('\n# Query of a report', source.index('_rp() {'))]
    script = 't() { printf "%s" "$1"; }\n' + helper + '''
reports_define
for i in "${!RP_KEY[@]}"; do
  printf '%s\\t%s\\t%s\\t%s\\n' "${RP_KEY[i]}" "${RP_GROUP[i]}" "${RP_NAME[i]}" "${RP_SQL[i]}"
done
'''
    result = subprocess.run(['bash'], input=script, capture_output=True, text=True, check=True)
    return [line.split('\t', 3) for line in result.stdout.splitlines()]


def test_one_hundred_distinct_reports_preserve_original_keys():
    rows = reports()
    assert len(rows) == 100
    assert len({r[0] for r in rows}) == 100
    assert len({r[2] for r in rows}) == 100
    normalized = [re.sub(r'\s+', ' ', r[3]).strip().lower() for r in rows]
    assert len(set(normalized)) == 100
    assert {r[0] for r in rows[:22]} == {
        'top-loans', 'overdue', 'never-borrowed', 'new-items', 'expiring', 'loans-month',
        'missing-data', 'lost-items', 'acquisitions', 'zero-loans', 'ddc-classes',
        'patrons-district', 'patrons-new', 'inventory-out', 'loans-type', 'children-new',
        'fines-debarred', 'orphan-authorities', 'active-patrons', 'holds-waiting',
        'collection-type', 'circ-daily'}
    for _, group, _, sql in rows:
        assert group in {'CIRC', 'CAT', 'PAT', 'ACQ'}
        assert sql.startswith('SELECT ')
        assert not re.search(r'\b(UPDATE|DELETE|DROP|INSERT|SHOW|CREATE|OUTFILE|DUMPFILE|SLEEP|BENCHMARK)\b',sql,re.I)
        assert ';' not in sql


def test_new_report_names_exist_in_every_language_cache():
    names = {row[2] for row in reports()[22:]}
    for path in (REPO / 'lang').glob('*.cache'):
        entries = {}
        for line in path.read_text().splitlines():
            if '|' in line and not line.startswith('#'):
                a,b = line.split('|',1)
                entries[base64.b64decode(a).decode()] = base64.b64decode(b).decode()
        assert names <= entries.keys(), path.name
        assert all(entries[name].strip() for name in names)
        if path.stem == 'pt':
            assert all(entries[name] != name for name in names)
