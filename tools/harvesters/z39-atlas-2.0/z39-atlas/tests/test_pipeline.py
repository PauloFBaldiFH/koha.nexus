#!/usr/bin/env python3
"""auto-discover, run state, resume and the comparison with Koha's list.

Offline: pages and yaz-client are mocked. Run:
python3 -m unittest discover -s tests -v
"""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import z39atlas as z

PAGE = '''<html><body>
<p>UFSC catalogue: z3950.ufsc.br:210/Default</p>
<p>New library: z3950.biblioteca-nova.org:210/BIBLIO</p>
<p>Another one: catalog.newlib.edu:2100/MAIN</p>
<p>Partial only: partial.example-lib.org:210</p>
</body></html>'''
SOURCE = 'https://wiki.koha-community.org/wiki/Koha_Open_Z39.50_Sources'


READS = []


def fake_reader(url, domains, robots, max_bytes=0):
    READS.append(url)
    return PAGE, True, url


class Signals:
    """auto-discover installs its own handlers; give the test runner its own back."""

    def __enter__(self):
        self.saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}

    def __exit__(self, *exc):
        for s, h in self.saved.items():
            signal.signal(s, h)


class KnownListTests(unittest.TestCase):
    def test_direct_json_with_alternates_and_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / 'direct.json'
            f.write_text(json.dumps({'servers': [
                {'host': 'Z3950.UFSC.BR', 'port': 210, 'db': 'Default',
                 'alternates': [{'host': 'alt.ufsc.br', 'port': 2100, 'db': 'Default'}]}],
                'excluded': [{'host': 'z3950.indexdata.com', 'port': 210, 'db': 'marc'}]}))
            self.assertEqual(z.load_known(f), {'z3950.ufsc.br|210|default', 'alt.ufsc.br|2100|default',
                                               'z3950.indexdata.com|210|marc'})

    def test_panel_targets_json_tsv_rows_and_lines(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / 'targets.json'
            f.write_text(json.dumps({'targets': [{'host': 'catalog.koha.nexus', 'port': 443, 'db': 'sru'}]}))
            self.assertEqual(z.load_known(f), {'catalog.koha.nexus|443|sru'})
            f = Path(td) / 'koha.tsv'
            f.write_text('https://sru.example.org\t443\tsru/x\tName\t1\t1\nlx2.loc.gov\t210\tLCDB\n')
            self.assertEqual(z.load_known(f), {'sru.example.org|443|sru/x', 'lx2.loc.gov|210|lcdb'})
            f = Path(td) / 'keys.txt'
            f.write_text('# panel keys\nlx2.loc.gov:210/LCDB\nz3950.ufsc.br:210/Default\n')
            self.assertEqual(z.load_known(f), {'lx2.loc.gov|210|lcdb', 'z3950.ufsc.br|210|default'})
            f = Path(td) / 'list.csv'
            f.write_text('name,host,port,database\nX,lx2.loc.gov,210,LCDB\n')
            self.assertEqual(z.load_known(f), {'lx2.loc.gov|210|lcdb'})


class PublishedTargetTests(unittest.TestCase):
    def test_only_complete_endpoints_from_public_documents(self):
        with tempfile.TemporaryDirectory() as td:
            con = z.init_db(Path(td) / 'a.db')
            with con:
                z.save_candidate(con, 'z3950.ufsc.br', 210, 'Default', source=SOURCE)
                z.save_candidate(con, 'partial.example-lib.org', 210, '', source=SOURCE)   # no database
                z.save_candidate(con, 'imported.example-lib.org', 210, 'X', source='imported:old.csv')
                z.save_candidate(con, 'known.example-lib.org', 210, 'K', source=SOURCE)
            targets = z.published_targets(con, 168, known={'known.example-lib.org|210|k'})
            self.assertEqual(targets, [('z3950.ufsc.br', 210, 'Default')])
            audit = con.execute('SELECT candidate_key, source FROM auto_allowed').fetchall()
            self.assertEqual(audit, [('z3950.ufsc.br|210|default', SOURCE)])

    def test_recently_tested_endpoints_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            con = z.init_db(Path(td) / 'a.db')
            with con:
                z.save_candidate(con, 'z3950.ufsc.br', 210, 'Default', source=SOURCE)
                con.execute('UPDATE candidates SET checked_at=?', (z.utcnow(),))
            self.assertEqual(z.published_targets(con, 168), [])


class StateTests(unittest.TestCase):
    def test_idle_running_and_interrupted(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'a.db'
            self.assertEqual(z.read_status(db)['status'], 'idle')
            con = z.init_db(db)
            z.set_state(con, status='running', phase='probe', pid=os.getpid(), pages_done=10, pages_total=10,
                        targets_done=5, targets_total=10)
            state = z.read_status(db)
            self.assertEqual(state['status'], 'running')
            self.assertEqual(state['percent'], 60)
            z.set_state(con, pid=2 ** 22 + 12345)          # no such process: the run died
            self.assertEqual(z.read_status(db)['status'], 'interrupted')
            with self.assertRaises(ValueError):
                z.set_state(con, nonsense=1)

    def test_stop_signals_the_running_process(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'a.db'
            z.set_state(z.init_db(db), status='running', pid=os.getppid())
            with patch.object(z.os, 'kill') as kill:
                self.assertTrue(z.stop_run(db))
            kill.assert_called_with(os.getppid(), signal.SIGTERM)
            z.set_state(z.init_db(db), status='finished')
            self.assertFalse(z.stop_run(db))


class AutoDiscoverTests(unittest.TestCase):
    def run_cli(self, db, *extra, probe=None):
        calls = []

        def fake_probe(host, port, base, timeout):
            calls.append((host, port, base))
            if probe:
                return probe(host, port, base)
            return ('marc_bibliographic', 3, 'bibliographic', 200, '00200nam a2200037   4500', '', 12)
        with Signals(), \
             patch.object(z.shutil, 'which', return_value='/usr/bin/yaz-client'), \
             patch.object(z, 'read_public_page', side_effect=fake_reader), \
             patch.object(z, 'yaz_probe', side_effect=fake_probe), \
             patch.object(z.time, 'sleep'):
            z.main(['--db', str(db), 'auto-discover', '--published', '--no-defaults', '--url', SOURCE,
                    '--max-pages', '5', *extra])
        return calls

    def test_pipeline_end_to_end_then_resume_and_compare(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'
            known = Path(td) / 'known.txt'
            known.write_text('z3950.ufsc.br:210/Default\n')
            calls = self.run_cli(db, '--known', str(known))
            # UFSC is known to Koha: not tested; the partial endpoint is never guessed.
            self.assertEqual(sorted(calls), [('catalog.newlib.edu', 2100, 'MAIN'),
                                             ('z3950.biblioteca-nova.org', 210, 'BIBLIO')])
            state = z.read_status(db)
            self.assertEqual((state['status'], state['phase'], state['percent']), ('finished', 'done', 100))
            self.assertEqual((state['targets_done'], state['targets_total'], state['approved']), (2, 2, 2))
            self.assertEqual(state['pages_done'], 1)
            self.assertEqual(json.loads(state['options'])['mode'], 'published')
            # A second run continues: the page and the tested endpoints are not done again.
            READS.clear()
            calls = self.run_cli(db)
            self.assertEqual(READS, [])
            self.assertIn(('z3950.ufsc.br', 210, 'Default'), calls)      # no --known this time
            self.assertNotIn(('catalog.newlib.edu', 2100, 'MAIN'), calls)
            # Only the confirmed servers Koha does not have.
            new = z.new_servers(db, z.load_known(known))
            self.assertEqual({(r['host'], r['port'], r['database']) for r in new},
                             {('catalog.newlib.edu', 2100, 'MAIN'), ('z3950.biblioteca-nova.org', 210, 'BIBLIO')})
            self.assertEqual(new[0]['sources'], [SOURCE])

    def test_refetch_window_skips_a_page_read_recently(self):
        with tempfile.TemporaryDirectory() as td:
            con = z.init_db(Path(td) / 'a.db')
            reads = []

            def reader(url, domains, robots, max_bytes=0):
                reads.append(url)
                return PAGE, True, url
            with patch.object(z.time, 'sleep'):
                z.harvest(con, [SOURCE], reader=reader, refetch_hours=24)
                z.harvest(con, [SOURCE], reader=reader, refetch_hours=24)
                self.assertEqual(len(reads), 1)
                z.harvest(con, [SOURCE], reader=reader, refetch_hours=None)
                self.assertEqual(len(reads), 2)

    def test_failed_and_negative_results_are_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'
            self.run_cli(db, probe=lambda h, p, b: ('init_only', None, None, None, None, 'x', 5))
            state = z.read_status(db)
            self.assertEqual((state['status'], state['approved']), ('finished', 0))
            self.assertEqual(z.new_servers(db), [])

    def test_crash_marks_failed(self):
        # A yaz error on one target is that target's result ('error'); a fault
        # outside the tests ends the whole run as failed, with the reason.
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'
            with patch.object(z, 'published_targets', side_effect=RuntimeError('disk')):
                with self.assertRaises(RuntimeError):
                    self.run_cli(db)
            state = z.read_status(db)
            self.assertEqual(state['status'], 'failed')
            self.assertIn('disk', state['error'])

    def test_stop_request_keeps_finished_tests(self):
        with tempfile.TemporaryDirectory() as td:
            con = z.init_db(Path(td) / 'a.db')
            done = []
            with patch.object(z, 'yaz_probe', side_effect=lambda *a: (done.append(a), ('unverified', None, None,
                                                                                         None, None, '', 1))[1]):
                stop = {'now': False}

                def progress(n, total, ok):
                    stop['now'] = True
                out = z.run_probe(con, [('a.example-lib.org', 210, 'A'), ('b.example-lib.org', 210, 'B'),
                                        ('c.example-lib.org', 210, 'C')], workers=1, host_interval=0,
                                  progress=progress, should_stop=lambda: stop['now'])
            self.assertEqual(out['tested'], 1)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM candidates WHERE checked_at IS NOT NULL')
                             .fetchone()[0], 1)

    def test_yaz_missing_aborts_before_anything_starts(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'
            with Signals(), patch.object(z.shutil, 'which', return_value=None), \
                 patch.object(z, 'read_public_page', side_effect=AssertionError('no harvest')), \
                 patch.object(z.subprocess, 'Popen', side_effect=AssertionError('no background')):
                with self.assertRaises(SystemExit) as cm:
                    z.main(['--db', str(db), 'auto-discover', '--published', '--background'])
            self.assertEqual(cm.exception.code, z.EXIT_NO_YAZ)
            self.assertEqual(z.read_status(db)['status'], 'idle')

    def test_a_second_run_is_refused_while_one_runs(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'
            z.set_state(z.init_db(db), status='running', pid=os.getppid())
            with Signals(), patch.object(z.shutil, 'which', return_value='/usr/bin/yaz-client'):
                with self.assertRaises(SystemExit) as cm:
                    z.main(['--db', str(db), 'auto-discover', '--published'])
            self.assertEqual(cm.exception.code, z.EXIT_ALREADY_RUNNING)

    def test_background_detaches_with_the_same_options(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'

            class P:
                pid = 4242
            with Signals(), patch.object(z.shutil, 'which', return_value='/usr/bin/yaz-client'), \
                 patch.object(z.subprocess, 'Popen', return_value=P()) as popen:
                z.main(['--db', str(db), 'pipeline', '--published', '--background', '--delay', '5'])
            cmd = popen.call_args.args[0]
            kw = popen.call_args.kwargs
            self.assertEqual(cmd[-4:], ['auto-discover', '--published', '--delay', '5'])
            self.assertTrue(kw['start_new_session'])
            self.assertTrue((Path(td) / 'atlas.log').exists())

    def test_allowlist_gate_is_kept(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'atlas.sqlite3'
            allow = Path(td) / 'allowed.txt'
            allow.write_text('z3950.biblioteca-nova.org\n')
            with Signals(), patch.object(z.shutil, 'which', return_value='/usr/bin/yaz-client'):
                with self.assertRaises(SystemExit):
                    z.main(['--db', str(db), 'auto-discover', '--allowlist', str(allow)])
                with self.assertRaises(SystemExit):     # one of --published / --allowlist is required
                    z.main(['--db', str(db), 'auto-discover'])
            calls = []
            with Signals(), patch.object(z.shutil, 'which', return_value='/usr/bin/yaz-client'), \
                 patch.object(z, 'read_public_page', side_effect=fake_reader), \
                 patch.object(z, 'yaz_probe', side_effect=lambda *a: (calls.append(a[:3]),
                                                                       ('unverified',) + (None,) * 4 + ('', 1))[1]), \
                 patch.object(z.time, 'sleep'):
                z.main(['--db', str(db), 'auto-discover', '--allowlist', str(allow), '--ack-authorized',
                        '--no-defaults', '--url', SOURCE])
            self.assertEqual(calls, [('z3950.biblioteca-nova.org', 210, 'BIBLIO')])

    def test_polite_limits_are_enforced(self):
        for bad in (['--delay', '0.5'], ['--host-interval', '1'], ['--workers', '9']):
            with self.assertRaises(SystemExit), patch('sys.stderr'):
                z.main(['--db', 'x.db', 'auto-discover', '--published', *bad])


if __name__ == '__main__':
    unittest.main()
