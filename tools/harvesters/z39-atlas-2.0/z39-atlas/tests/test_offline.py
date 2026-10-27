#!/usr/bin/env python3
"""Run: python3 -m unittest discover -s tests -v"""
import csv
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import z39atlas as z


def sample_marc(kind='a'):
    # One control field 001 with content '123' (terminator included)
    field = b'123\x1e'
    directory = b'001000400000'
    base = 24 + len(directory) + 1
    size = base + len(field) + 1
    leader = (f'{size:05d}' + 'n' + kind + 'm a22' + f'{base:05d}' + '   4500').encode('ascii')
    assert len(leader) == 24
    return leader + directory + b'\x1e' + field + b'\x1d'


class ParsingTests(unittest.TestCase):
    def test_explicit_endpoints_and_partials(self):
        page = '<div>UFSC z3950.ufsc.br:210/Default</div><p>example.org:9921/BOOKS</p>'
        matches, _ = z.extract_endpoints(page)
        got = {(h,p,d) for h,p,d,_ in matches}
        self.assertIn(('z3950.ufsc.br',210,'Default'),got)
        self.assertIn(('example.org',9921,'BOOKS'),got)
        self.assertIn(('z3950.ufsc.br',210,''),got)

    def test_do_not_parse_private_ips(self):
        self.assertIsNone(z.parse_endpoint('127.0.0.1',210,'Default'))
        self.assertIsNone(z.parse_endpoint('10.0.0.20',210,'Default'))
        self.assertIsNone(z.parse_endpoint('192.168.1.4',210,'Default'))
        self.assertIsNone(z.parse_endpoint('localhost',210,'Default'))
        self.assertIsNotNone(z.parse_endpoint('lx2.loc.gov',210,'LCDB'))

    def test_csv_ingest_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            c = z.init_db(Path(td)/'test.sqlite3')
            self.assertTrue(z.save_candidate(c,'Z3950.UFSC.BR',210,'Default',source='source-A'))
            self.assertFalse(z.save_candidate(c,'z3950.ufsc.br',210,'default',source='source-B'))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM provenance').fetchone()[0],2)

    def test_marc_types(self):
        self.assertEqual(z.check_marc(sample_marc('a'))[0], 'bibliographic')
        self.assertEqual(z.check_marc(sample_marc('z'))[0], 'authority')
        self.assertIsNone(z.check_marc(b'000000000000000000000000'))
        damaged = sample_marc('a')[:-1] + b'0'
        self.assertIsNone(z.check_marc(damaged))

    def test_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            filepath = Path(td)/'allowed.txt'
            filepath.write_text('z3950.ufsc.br\n# comment\nlx2.loc.gov\n',encoding='utf-8')
            self.assertEqual(z.load_allowlist(str(filepath)), {'z3950.ufsc.br','lx2.loc.gov'})
            filepath.write_text('192.168.1.25\n',encoding='utf-8')
            with self.assertRaises(ValueError):
                z.load_allowlist(str(filepath))

    def test_inference_only_for_allowlisted_hosts(self):
        with tempfile.TemporaryDirectory() as td:
            con = z.init_db(Path(td)/'test.db')
            z.save_candidate(con,'z3950.ufsc.br',210,'Default')
            z.save_candidate(con,'lx2.loc.gov',None,'')
            rows = z.candidates_to_probe(con,{'lx2.loc.gov'},168,True)
            self.assertEqual(len(rows),3)
            self.assertTrue(all(x[0]=='lx2.loc.gov' and x[1]==210 for x in rows))

    def test_mocked_yaz_marc_recovery(self):
        from subprocess import CompletedProcess
        def fake_run(cmd, **kwargs):
            # writes a valid ISO2709 record to -m destination
            Path(cmd[cmd.index('-m')+1]).write_bytes(sample_marc('a'))
            return CompletedProcess(cmd,0,'Number of hits: 4','')
        with patch.object(z.shutil,'which',return_value='/usr/bin/yaz-client'), \
             patch.object(z,'public_ip',return_value='8.8.8.8'), \
             patch.object(z.subprocess,'run',side_effect=fake_run):
            result = z.yaz_probe('z3950.ufsc.br',210,'Default',20)
            self.assertEqual(result[0], 'marc_bibliographic')
            self.assertEqual(result[1],4)
            self.assertEqual(result[3],len(sample_marc('a')))


if __name__ == '__main__':
    unittest.main()
