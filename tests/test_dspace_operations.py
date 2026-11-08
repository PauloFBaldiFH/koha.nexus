"""Operation policy/failure tests; Docker and cloud doubles are explicit."""
import contextlib
import copy
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'platforms/dspace'))
import runtime
import operations as ops

class Policies(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.root=self.base/'platforms/dspace';self.root.mkdir(parents=True,mode=0o700)
        self.dest=self.base/'backups';self.dest.mkdir(mode=0o700)
        self.rt=Mock();self.rt.root=self.root;self.rt.driver='/usr/local/bin/config.sh'
        self.o=ops.Operations(self.rt)
        self.plan=dict(id='nightly',members=['dspace'],time='02:30',keep=7,destination=str(self.dest),remote='')
    def test_legacy_participants_are_not_implicitly_widened(self):
        for bad in ([],['koha'],['tainacan','koha'],['dspace','dspace'],['dspace','other']):
            with self.subTest(bad=bad),self.assertRaises(runtime.Refused):ops.members(bad)
        self.assertEqual(ops.members(['dspace','koha']),['koha','dspace'])
    def test_invalid_ids_times_retention_and_symlinks_refused(self):
        link=self.base/'linked';link.symlink_to(self.dest)
        for key,value in [('id','../other'),('time','24:00'),('time','2:30'),('keep',0),('keep',True),('destination',str(link)),('remote','r:path/../secret')]:
            with self.subTest(key=key,value=value),self.assertRaises(runtime.Refused):self.o.check_plan(dict(self.plan,**{key:value}))
    def test_writable_backup_parent_is_refused_without_chmod(self):
        self.dest.chmod(0o777)
        with self.assertRaises(runtime.Refused):self.o.check_plan(self.plan)
        self.assertEqual(self.dest.stat().st_mode&0o777,0o777)
    def test_readable_backup_parent_gets_a_private_plan_subfolder(self):
        self.dest.chmod(0o755)
        result=self.o.check_plan(self.plan)
        folder=ops.private(Path(result['destination'])/'nexus-nightly',create=True)
        self.assertEqual(folder.stat().st_mode&0o777,0o700)
        self.assertEqual(self.dest.stat().st_mode&0o777,0o755)
    def test_preview_never_writes_a_plan_or_cron(self):
        with patch.object(ops.Recovery,'crypto'):
            result=self.o.save_plan(self.plan)
        self.assertEqual(result['plan']['members'],['dspace']);self.assertFalse(self.o.home.exists());self.rt.core.assert_not_called()
    def test_plan_locks_refuse_concurrent_writer(self):
        with self.o.plan_lock('nightly'):
            with self.assertRaises(runtime.Refused):
                with self.o.plan_lock('nightly'):pass
    def test_unknown_file_permissions_refused(self):
        self.o.home.mkdir(mode=0o700);path=self.o.plan_path('nightly');path.write_text('{}');path.chmod(0o666)
        with self.assertRaises(runtime.Refused):self.o.plans()
    def test_cloud_connection_must_already_exist(self):
        with patch.object(ops,'command',return_value='other:\n'),self.assertRaises(runtime.Refused):self.o.check_plan(dict(self.plan,remote='drive:DSpace'))
    def test_disable_preview_does_not_need_the_cloud_connection_destination_or_key(self):
        self.o.home.mkdir(mode=0o700)
        data=dict(self.plan,schema=1,destination='/missing/offline-volume',remote='lost:folder')
        runtime.atomic(self.o.plan_path('nightly'),json.dumps(data))
        with patch.object(ops.Recovery,'crypto') as crypto,patch.object(ops,'command') as command:
            result=self.o.disable_plan('nightly')
        self.assertEqual(result['plan']['time'],'');crypto.assert_not_called();command.assert_not_called()
        self.rt.core.assert_not_called()
    def test_reading_absent_plans_creates_nothing(self):
        self.assertEqual(self.o.plans(),{'plans':[]});self.assertFalse(self.o.home.exists())
    def test_retention_leaves_other_folders_and_changed_content(self):
        folder=self.dest/'nexus-nightly';folder.mkdir();a=folder/'knx-dspace-old.tar.gpg';a.write_text('one')
        foreign=self.dest/'knx-dspace-foreign.tar.gpg';foreign.write_text('foreign')
        history=[dict(capture='ok',copy='ok',file=str(a),sha256=runtime.digest(a)),dict(capture='ok',copy='ok',file=str(foreign),sha256=runtime.digest(foreign))]
        self.o.retention(dict(self.plan,keep=1),history)
        self.assertFalse(a.exists());self.assertTrue(foreign.exists())
    def test_failed_cloud_copy_is_not_a_retention_candidate(self):
        folder=self.dest/'nexus-nightly';folder.mkdir();a=folder/'knx-dspace-old.tar.gpg';a.write_text('one')
        history=[dict(capture='ok',copy='failed',file=str(a),sha256=runtime.digest(a)),dict(capture='ok',copy='ok',file=str(a),sha256=runtime.digest(a))]
        self.o.retention(dict(self.plan,keep=1),history);self.assertTrue(a.exists())
    def test_changed_backup_blocks_retention(self):
        folder=self.dest/'nexus-nightly';folder.mkdir();a=folder/'knx-dspace-old.tar.gpg';a.write_text('one')
        history=[dict(capture='ok',copy='ok',file=str(a),sha256='0'*64),dict(capture='ok',copy='ok',file=str(a),sha256='0'*64)]
        with self.assertRaises(runtime.Refused):self.o.retention(dict(self.plan,keep=1),history)
        self.assertTrue(a.exists())
    def test_interrupted_transaction_refuses_unrelated_mutation(self):
        runtime.atomic(self.o.journal,json.dumps({'phase':'prepared'}))
        with self.assertRaises(runtime.Refused):self.o.pending()
    def test_cleartext_secrets_never_appear_in_preview(self):
        self.rt.state.return_value={'url':'http://repo.local:8100','ports':{'backend':18101,'ui':18100}}
        with patch.object(ops.Recovery,'checked'):
            plan=self.o.address_plan({'url':'https://repo.example.org','mode':'external'})
        self.assertTrue(plan['safety_backup']);self.assertNotIn('db-password',json.dumps(plan))
    def test_tunnel_origin_is_distinct_from_canonical_https(self):
        self.rt.state.return_value={'url':'http://repo.local:8100','ports':{'backend':18101,'ui':18100}}
        with patch.object(ops.Recovery,'checked'):
            plan=self.o.address_plan({'url':'https://repo.example.org','mode':'tunnel','origin_port':18102})
        self.assertEqual(plan['origin_port'],18102);self.assertEqual(plan['url'],'https://repo.example.org')
    def test_cannot_reuse_koha_tainacan_or_backend_port(self):
        with patch.object(ops.Recovery,'checked'):
            for port in (8080,8090,18100,18101,True):
                with self.subTest(port=port),self.assertRaises(runtime.Refused):self.o.address_plan({'url':'https://repo.test','mode':'tunnel','origin_port':port})
    def test_https_requires_explicit_termination_mode(self):
        with patch.object(ops.Recovery,'checked'),self.assertRaises(runtime.Refused):self.o.address_plan({'url':'https://repo.test'})
    def test_unknown_upgrade_refused_before_pull_or_capture(self):
        self.rt.release_hash='not-reviewed'
        with patch.object(ops.Recovery,'checked',return_value=({},{})),self.assertRaises(runtime.Refused):self.o.upgrade({'catalog':'/tmp/catalog'})
        self.rt.docker.assert_not_called()
    def test_protocol_values_are_never_executed(self):
        self.assertEqual(ops.fields('@@result file=/tmp/a\nignore\n@@result complete=yes\n'),{'file':'/tmp/a','complete':'yes'})



class AddressTransaction(unittest.TestCase):
    """Real private files/journal; explicit service and encryption doubles."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'dspace';self.root.mkdir(mode=0o700)
        self.rt=runtime.Runtime(self.root,Path(self.temp.name)/'catalog.json',lab=True,driver='/test/installer')
        self.cfg='dspace.ui.url = http://repo.test:8100\ndspace.server.url = http://repo.test:8100/server\nrest.cors.allowed-origins = http://repo.test:8100\ninstitution.custom = preserved\n'
        compose={'services':{'ui':{'environment':{}}},'volumes':{'assetstore':{'name':'original-owned-assets'}}}
        for name,text in [('local.cfg',self.cfg),('db-password','not-exported'),('compose.json',json.dumps(compose))]:runtime.atomic(self.root/name,text)
        runtime.atomic(self.root/'state.json',json.dumps(dict(phase='ready',migration='done',prepared=True,url='http://repo.test:8100',ports={'backend':18101,'ui':18100},release_sha256=self.rt.release_hash,files={n:runtime.digest(self.root/n) for n in ('local.cfg','db-password','compose.json')})))
        self.rt.existing_resources=Mock();self.rt.core=Mock(return_value='apache-nexus')
        self.rt.compose=Mock();self.rt.dependencies=Mock();self.rt.health=Mock()
        self.op=ops.Operations(self.rt,'test-only phrase')
        # UID/GID mechanics are exercised on the root CI runner; this test runs unprivileged.
        self.atomic_patch=patch.object(ops,'atomic',side_effect=lambda p,text,mode=0o600,gid=None:runtime.atomic(p,text,mode))
        self.atomic_patch.start();self.addCleanup(self.atomic_patch.stop)
        for name,value in [('capture',{'package':'test-only-encrypted-package'}),('test',{'verified':True})]:
            patcher=patch.object(ops.Recovery,name,return_value=value);patcher.start();self.addCleanup(patcher.stop)
    def test_success_preserves_custom_config_volume_refs_and_records_only_completion(self):
        result=self.op.address({'url':'http://repo.test:8101'},True)
        self.assertTrue(result['changed']);self.assertIn('institution.custom = preserved',(self.root/'local.cfg').read_text())
        self.assertEqual(json.loads((self.root/'compose.json').read_text())['volumes']['assetstore']['name'],'original-owned-assets')
        self.assertEqual(json.loads(self.op.journal.read_text())['phase'],'complete')
        self.assertEqual(self.rt.state()['files']['local.cfg'],runtime.digest(self.root/'local.cfg'))
    def test_failed_health_check_rolls_back_actual_files_before_reporting_failure(self):
        self.rt.health.side_effect=[runtime.Refused('Injected failed health'),None]
        with self.assertRaises(runtime.Refused):self.op.address({'url':'http://repo.test:8101'},True)
        self.assertEqual((self.root/'local.cfg').read_text(),self.cfg)
        self.assertEqual(self.rt.state()['url'],'http://repo.test:8100')
        self.assertEqual(json.loads(self.op.journal.read_text())['phase'],'rolled-back')
    def test_failed_rollback_keeps_recovery_journal_and_blocks_other_mutation(self):
        self.rt.health.side_effect=runtime.Refused('Service unavailable')
        with self.assertRaises(runtime.Refused):self.op.address({'url':'http://repo.test:8101'},True)
        self.assertEqual(json.loads(self.op.journal.read_text())['phase'],'prepared')
        with self.assertRaises(runtime.Refused):self.op.pending()
    def test_no_recovery_phrase_stops_before_capture_or_mutation(self):
        self.op.phrase=None
        with self.assertRaises(runtime.Refused):self.op.address({'url':'http://repo.test:8101'},True)
        self.assertEqual((self.root/'local.cfg').read_text(),self.cfg);self.assertFalse(self.op.journal.exists())
    def test_interrupted_restore_is_not_overwritten_by_a_new_address_backup(self):
        journal=self.root/'backup-operation.json'
        runtime.atomic(journal,json.dumps({'phase':'promoting','safety':'protected'}))
        with self.assertRaises(ops.Error):self.op.address({'url':'http://repo.test:8101'},True)
        self.assertEqual(json.loads(journal.read_text())['safety'],'protected')
        self.assertEqual((self.root/'local.cfg').read_text(),self.cfg)
        self.assertFalse(self.op.journal.exists())
    def test_external_proxy_preview_never_writes_any_file(self):
        self.rt.core.return_value='external'
        before=runtime.digest(self.root/'local.cfg')
        result=self.op.address_plan({'url':'https://repo.example.org','mode':'external','proxy':'nginx'})
        self.assertIn('127.0.0.1:18101',result['external_proxy_snippet'])
        self.assertEqual(runtime.digest(self.root/'local.cfg'),before);self.assertFalse(self.op.journal.exists())
    def test_foreign_web_server_never_gets_an_apache_site(self):
        self.rt.core.return_value='external'
        with self.assertRaises(runtime.Refused):self.op.address_plan({'url':'http://repo.test:8101','mode':'apache'})
        self.rt.compose.assert_not_called()


if __name__=='__main__':unittest.main()
