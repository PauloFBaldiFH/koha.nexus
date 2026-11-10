"""A timed-out or failed acceptance must leave useful, secret-free evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[1]/'tools/dspace_acceptance.py'
spec=importlib.util.spec_from_file_location('dspace_acceptance',path)
acceptance=importlib.util.module_from_spec(spec);spec.loader.exec_module(acceptance)


class PhaseEvidence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.tracker=acceptance.Timings(self.temp.name,'lifecycle')
    def read(self):return json.loads(self.tracker.path.read_text())['phases']
    def test_running_phase_is_persisted_before_slow_work_begins(self):
        with patch.object(acceptance.time,'monotonic',side_effect=[100,142.5]):
            with self.tracker.phase('installation'):
                row=self.read()[0]
                self.assertEqual(row['status'],'running');self.assertIn('started_at',row)
                with self.assertRaisesRegex(RuntimeError,'did not complete'):self.tracker.require_complete()
        self.assertEqual(self.read()[0]['status'],'passed')
        self.assertEqual(self.read()[0]['seconds'],42.5)
        self.assertEqual(self.tracker.path.stat().st_mode&0o777,0o644)
    def test_failure_is_propagated_without_exporting_its_private_message(self):
        with self.assertRaisesRegex(RuntimeError,'synthetic-private-password'):
            with self.tracker.phase('native-recovery'):
                raise RuntimeError('synthetic-private-password, private account and token')
        row=self.read()[0]
        self.assertEqual(row['status'],'failed');self.assertEqual(row['error_type'],'RuntimeError')
        self.assertNotIn('synthetic-private',self.tracker.path.read_text())
    def test_process_interruption_remains_failed_and_cannot_claim_completion(self):
        with self.assertRaises(KeyboardInterrupt):
            with self.tracker.phase('nexus-full-recovery'):raise KeyboardInterrupt()
        self.assertEqual(self.read()[0]['status'],'failed')
        with self.assertRaises(RuntimeError):self.tracker.require_complete()
    def test_nested_phases_keep_both_durations_and_results(self):
        with self.tracker.phase('backup-operations'):
            with self.tracker.phase('operations-set-and-recovery'):pass
        rows=self.read()
        self.assertEqual([row['status'] for row in rows],['passed','passed'])
        self.assertGreaterEqual(rows[0]['seconds'],rows[1]['seconds'])
    def test_each_selected_suite_requires_its_own_tests_to_finish(self):
        for suite in acceptance.SUITES:
            tracker=acceptance.Timings(self.temp.name,suite)
            stages=acceptance.required(suite)
            for name in stages[:-1]:
                with tracker.phase(name):pass
            with self.assertRaises(RuntimeError):tracker.require_complete()
            with tracker.phase(stages[-1]):pass
            tracker.require_complete()
    def test_unknown_suite_does_not_silently_skip_the_validation(self):
        with self.assertRaises(ValueError):acceptance.Timings(self.temp.name,'typo')
        with self.assertRaises(ValueError):acceptance.includes('typo','lifecycle')
