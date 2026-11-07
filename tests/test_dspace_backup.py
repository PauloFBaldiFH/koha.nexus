"""Recovery package validation: real files, no Docker or root required."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'platforms/dspace'
sys.path.insert(0, str(MODULE))
import backup as b


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.dest = self.root / 'out'; self.dest.mkdir()

    def archive(self, names):
        path = self.root / 'data.tar'
        with tarfile.open(path, 'w') as out:
            for name, kind in names:
                info = tarfile.TarInfo(name); info.type = kind
                if kind == tarfile.REGTYPE:
                    info.size = 4; out.addfile(info, io.BytesIO(b'data'))
                else: info.linkname = '/etc/passwd'; out.addfile(info)
        return path

    def test_regular_file_roundtrip(self):
        path = self.archive([('volumes/assetstore/document', tarfile.REGTYPE)])
        self.assertEqual(b.extract(path, self.dest, 4), 4)
        self.assertEqual((self.dest/'volumes/assetstore/document').read_bytes(), b'data')

    def test_unsafe_paths_and_types_never_extract(self):
        for name, kind in [('/etc/test',tarfile.REGTYPE),('../escape',tarfile.REGTYPE),
                           ('x/../escape',tarfile.REGTYPE),('x\\y',tarfile.REGTYPE),
                           ('x',tarfile.SYMTYPE),('x',tarfile.LNKTYPE),('x',tarfile.CHRTYPE),
                           ('a//b',tarfile.REGTYPE),('./file',tarfile.REGTYPE)]:
            with self.subTest(name=name,kind=kind):
                with self.assertRaises(b.Error): b.extract(self.archive([(name,kind)]), self.dest, 100)
                self.assertEqual(list(self.dest.iterdir()), [])

    def test_duplicate_names_rejected_before_first_write(self):
        path = self.archive([('x',tarfile.REGTYPE),('x',tarfile.REGTYPE)])
        with self.assertRaises(b.Error): b.extract(path,self.dest,100)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_expansion_limited_before_writing(self):
        path = self.archive([('x',tarfile.REGTYPE)])
        with self.assertRaises(b.Error): b.extract(path,self.dest,3)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_inventory_rejects_symlinks(self):
        (self.dest/'link').symlink_to('/etc/passwd')
        with self.assertRaises(b.Error): b.entries(self.dest)

    def test_inventory_detects_same_size_corruption(self):
        p=self.dest/'doc'; p.write_text('abcd'); first=b.entries(self.dest)
        p.write_text('abce'); self.assertNotEqual(first,b.entries(self.dest))

    def test_dump_fingerprint_ignores_only_random_session_markers(self):
        p=self.root/'a'; q=self.root/'b'
        p.write_text('-- header\n\\restrict randomA\nINSERT INTO t VALUES (1);\n\\unrestrict randomA\n')
        q.write_text('-- header\n\\restrict randomB\nINSERT INTO t VALUES (1);\n\\unrestrict randomB\n')
        self.assertEqual(b.normalized_dump(p),b.normalized_dump(q))
        q.write_text('INSERT INTO t VALUES (2);\n'); self.assertNotEqual(b.normalized_dump(p),b.normalized_dump(q))

    def test_sql_string_lines_that_look_like_comments_are_still_compared(self):
        p=self.root/'a'; q=self.root/'b'
        p.write_text("INSERT INTO t VALUES ('first\n-- original data\nlast');\n")
        q.write_text("INSERT INTO t VALUES ('first\n-- changed data\nlast');\n")
        self.assertNotEqual(b.normalized_dump(p), b.normalized_dump(q))

    def test_corrupt_ciphertext_refused_before_decryption(self):
        class RT: root=self.root
        recovery=b.Recovery(RT()); package=self.root/'pack.gpg'; package.write_bytes(b'x')
        package.with_suffix('.sha256').write_text('0'*64)
        with self.assertRaises(b.Error):
            with recovery.opened(package): self.fail('must not open')



class CaptureFailures(unittest.TestCase):
    """Fault injection tests; crypto/Docker are explicit doubles, not homologation."""
    def setUp(self):
        from unittest.mock import Mock
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); (self.root/'source').mkdir()
        (self.root/'source/data').write_text('persistent')
        for n in ('local.cfg','db-password','state.json'): (self.root/n).write_text('private')
        self.rt=Mock(); self.rt.root=self.root; self.rt.release_hash='release'
        self.rt.compose.return_value='postgres-container'
        self.r=b.Recovery(self.rt); self.r.home=self.root/'backups'
        self.r.checked=Mock(return_value=({'url':'http://repo.test'}, {'services':{'postgres':{'image':'exact'}}}))
        self.r.volumes=Mock(return_value={'postgres':self.root/'source'})
        self.r.running=Mock(return_value=['postgres','backend'])
        def binary(args,path,write): path.write_bytes(b'PGDMP' if path.name=='database.dump' else b'INSERT INTO t VALUES(1);\n')
        self.r.binary=Mock(side_effect=binary)
        self.r.crypto=Mock()

    def test_missing_key_does_not_stop_services(self):
        self.r.crypto.side_effect=b.Error('No key')
        with self.assertRaises(b.Error): self.r.capture()
        self.r.checked.assert_not_called(); self.rt.compose.assert_not_called()

    def test_dump_failure_resumes_exact_previous_services(self):
        self.r.binary.side_effect=b.Error('Failed dump')
        with self.assertRaises(b.Error): self.r.capture()
        self.assertIn((('start','postgres','backend'), {'timeout':420}),
            [(c.args,c.kwargs) for c in self.rt.compose.call_args_list])
        data=json.loads(self.r.journal.read_text()); self.assertEqual(data['phase'],'writes-resumed')
        self.assertEqual(list(self.r.home.glob('*.gpg')), [])

    def test_failed_restart_never_records_writes_resumed(self):
        def compose(*args,**kwargs):
            if args[0]=='start': raise b.Error('Cannot restart')
            return 'postgres-container'
        self.rt.compose.side_effect=compose
        with self.assertRaises(b.Error): self.r.capture()
        self.assertEqual(json.loads(self.r.journal.read_text())['phase'],'capture')
        self.assertEqual(list(self.r.home.glob('*.gpg')), [])
        self.rt.compose.side_effect=None
        self.r.recover_capture()
        self.assertEqual(json.loads(self.r.journal.read_text())['phase'],'writes-resumed')

    def test_stop_failure_still_attempts_resume(self):
        def compose(*args,**kwargs):
            if args[0]=='stop': raise b.Error('Partially stopped')
            return 'postgres-container'
        self.rt.compose.side_effect=compose
        with self.assertRaises(b.Error): self.r.capture()
        self.assertEqual(self.rt.compose.call_args_list[-1].args,('start','postgres','backend'))

    def test_encryption_failure_publishes_no_complete_package(self):
        def crypto(op,*args):
            if op=='encrypt': raise b.Error('Cannot encrypt')
        self.r.crypto.side_effect=crypto
        with self.assertRaises(b.Error): self.r.capture()
        self.assertEqual(list(self.r.home.iterdir()), [])
        self.assertEqual(json.loads(self.r.journal.read_text())['phase'],'writes-resumed')

    def test_interrupted_promotion_is_not_auto_resumed_as_capture(self):
        self.r.record(phase='promoting',services=['postgres'])
        with self.assertRaises(b.Error): self.r.recover_capture()
        self.rt.compose.assert_not_called()


class PromotionFailures(unittest.TestCase):
    """Exercise actual on-disk configuration rollback with simulated services."""
    def test_failed_promotion_restores_old_configuration(self):
        self.exercise(False)

    def test_failed_rollback_keeps_recovery_material(self):
        self.exercise(True)

    def exercise(self, fail_rollback):
        import contextlib
        from unittest.mock import Mock, patch
        import runtime
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'dspace'; root.mkdir()
            tree=Path(temporary)/'tree'; (tree/'private').mkdir(parents=True)
            for name,value in [('local.cfg','old config\nproxies.trusted.ipranges = 127.0.0.1\nproxies.trusted.include_ui_ip = false'),('db-password','old password'),('compose.json','{"volumes":{}}')]:
                (root/name).write_text(value)
            state={'phase':'ready','url':'http://repo.test','status':'installed',
                   'files':{n:b.sha(root/n) for n in ('local.cfg','db-password','compose.json')}}
            (root/'state.json').write_text(json.dumps(state))
            original={p.name:p.read_bytes() for p in root.iterdir()}
            (tree/'private/local.cfg').write_text('recovered config')
            (tree/'private/db-password').write_text('recovered password')
            rt=Mock(); rt.root=root; rt.driver='installer'
            rt.state.side_effect=lambda:json.loads((root/'state.json').read_text())
            def mark(**changes):
                data=rt.state(); data.update(changes); (root/'state.json').write_text(json.dumps(data))
            rt.mark.side_effect=mark
            rt.dependencies.side_effect=[b.Error('Failed new services'),b.Error('Failed previous services') if fail_rollback else None]
            recovery=b.Recovery(rt)
            recovery.checked=Mock(return_value=(state,{'volumes':{}}))
            recovery.capture=Mock(return_value={'package':'safety.tar.gpg'})
            recovery.running=Mock(return_value=['postgres','solr','backend','ui'])
            @contextlib.contextmanager
            def opened(package): yield tree,{'url':state['url']}
            @contextlib.contextmanager
            def clone(*args):
                yield {'area':root/'copy','project':'copy','compose':{'volumes':{'assetstore':{'name':'new-owned-volume'}}},'promoted':{'value':False}}
            recovery.opened=opened; recovery.clone=clone
            atomic=runtime.atomic
            with patch.object(runtime,'atomic',side_effect=lambda p,d,mode=0o600,gid=None:atomic(p,d,mode)):
                with self.assertRaises(b.Error): recovery.restore('source.tar.gpg')
            for name,value in original.items(): self.assertEqual((root/name).read_bytes(),value)
            self.assertEqual((root/'recovery-rollback').exists(),fail_rollback)
            self.assertEqual(json.loads(recovery.journal.read_text())['phase'],'promoting' if fail_rollback else 'complete')
            self.assertFalse(any(c.args[:2]==('volume','rm') for c in rt.docker.call_args_list))


class DecryptionLimit(unittest.TestCase):
    @unittest.skipUnless(__import__('shutil').which('gpg'), 'GPG is not installed')
    def test_gpg_stops_expansion_before_extracting_archive(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); home=root/'gpg'; home.mkdir(mode=0o700)
            plain=root/'large'; plain.write_bytes(b'0'*1048576)
            base=['gpg','--homedir',str(home),'--batch','--pinentry-mode','loopback','--passphrase-fd','0']
            try:
                encrypted=root/'encrypted'
                subprocess.run([*base,'--symmetric','--output',str(encrypted),str(plain)],input=b'test-only',capture_output=True,check=True,timeout=30)
                result=subprocess.run([*base,'--max-output','4096','--decrypt',str(encrypted)],input=b'test-only',capture_output=True,timeout=30)
                self.assertNotEqual(result.returncode,0)
                self.assertLess(len(result.stdout),plain.stat().st_size)
            finally:
                subprocess.run(['gpgconf','--homedir',str(home),'--kill','gpg-agent'],capture_output=True,timeout=10)


class DestinationConfig(unittest.TestCase):
    def test_destination_trust_is_kept_but_source_keys_are_recovered(self):
        source='db.password = recovered\nproxies.trusted.ipranges = 172.30.10.1\nproxies.trusted.include_ui_ip = false\n'
        target='db.password = old\nproxies.trusted.ipranges = 172.30.20.1\nproxies.trusted.include_ui_ip = false\n'
        actual=b.destination_config(source,target)
        self.assertIn('db.password = recovered',actual)
        self.assertIn('172.30.20.1',actual)
        self.assertNotIn('172.30.10.1',actual)

    def test_missing_destination_trust_refuses_promotion(self):
        with self.assertRaises(b.Error): b.destination_config('db.password = source','')


class IsolatedConfiguration(unittest.TestCase):
    def test_overrides_do_not_leave_conflicting_properties(self):
        source='db.url = jdbc:postgresql://postgres/dspace\nsolr.server = http://solr:8983/solr\nmail.server.disabled = false\nuser.registration = true\ndb.password = recovered\n'
        result=b.isolated_config(source)
        for key in ('db.url','solr.server','mail.server.disabled','user.registration'):
            self.assertEqual(sum(line.startswith(key+' =') for line in result.splitlines()),1)
        self.assertNotIn('//postgres/',result)
        self.assertIn('db.password = recovered',result)
        self.assertIn('127.0.0.1:5432',result)
        self.assertIn('mail.server.disabled = true',result)



class RecoveryPlan(unittest.TestCase):
    def test_plan_reports_scope_without_stopping_services(self):
        import contextlib
        from unittest.mock import Mock
        rt=Mock(); rt.root=Path('/unused/dspace')
        recovery=b.Recovery(rt)
        recovery.checked=Mock(return_value=({'url':'http://repo.test'},{'services':{'postgres':{'image':'pinned'}}}))
        @contextlib.contextmanager
        def opened(package):
            yield Path('/unused'),{'images':{'postgres':'pinned'},'url':'http://repo.test','release_sha256':'release','files':{'file':{'bytes':123}}}
        recovery.opened=opened
        plan=recovery.plan('package')
        self.assertEqual(plan['uncompressed_bytes'],123)
        self.assertTrue(plan['safety_backup_required'])
        self.assertTrue(plan['old_volumes_preserved'])
        rt.compose.assert_not_called(); rt.docker.assert_not_called()

    def test_plan_rejects_another_image_matrix(self):
        import contextlib
        from unittest.mock import Mock
        rt=Mock(); rt.root=Path('/unused/dspace'); recovery=b.Recovery(rt)
        recovery.checked=Mock(return_value=({'url':'http://repo.test'},{'services':{'postgres':{'image':'pinned'}}}))
        @contextlib.contextmanager
        def opened(package): yield Path('/unused'),{'images':{'postgres':'different'}}
        recovery.opened=opened
        with self.assertRaises(b.Error): recovery.plan('package')
        rt.compose.assert_not_called(); rt.docker.assert_not_called()

if __name__ == '__main__': unittest.main()
