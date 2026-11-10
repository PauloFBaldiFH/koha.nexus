"""Full envelope uses real OpenPGP; application and Docker drivers are explicit doubles."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('nexus_recovery',REPO/'platforms/nexus/recovery.py')
full=importlib.util.module_from_spec(spec);spec.loader.exec_module(full)
PHRASE='synthetic-full-recovery-test-phrase'

class Envelope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('gpg'):raise unittest.SkipTest('requires GnuPG')
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name);cls.home=cls.base/'source-key'
        cls.crypto=full.Crypto(cls.home)
        cls.crypto.call('--quick-generate-key','Nexus Test <nexus@example.invalid>','future-default','default','never',phrase=PHRASE)
        cls.fpr=next(line.split(':')[9] for line in cls.crypto.call('--with-colons','--list-keys').decode().splitlines() if line.startswith('fpr:'))
        cls.key=cls.crypto.call('--armor','--export-secret-keys',cls.fpr,phrase=PHRASE)
        cls.check=cls.crypto.call('--armor','--trust-model','always','--encrypt','--recipient',cls.fpr,input=b'koha-nexus-recovery-kit-check')
    @classmethod
    def tearDownClass(cls):
        cls.crypto.close();cls.temp.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.settings=self.root/'source-settings';self.settings.mkdir(mode=0o700)
        (self.settings/'preferences.json').write_text('{"language":"pt"}');(self.settings/'preferences.json').chmod(0o600)
        self.keyfile=self.root/'key.asc';self.keyfile.write_bytes(self.key);self.keyfile.chmod(0o600)
        self.keycheck=self.root/'check.asc';self.keycheck.write_bytes(self.check);self.keycheck.chmod(0o600)
        self.kit=self.root/'kit.txt';self.kit.write_text('fingerprint='+self.fpr+'\n@@begin secret-key\n'+self.key.decode()+'@@end\n@@begin check\n'+self.check.decode()+'@@end\n');self.kit.chmod(0o600)
        self.driver=self.root/'installer';self.driver.write_text('source program fixture; never execute from archive');self.driver.chmod(0o600)
        self.destination=self.root/'backups';self.state=self.root/'state'
        fixture={'applications':['koha'],'unknown':[],'images':[],'settings':{'panel-settings':str(self.settings),'backup-secret-key-asc':str(self.keyfile),'backup-check-asc':str(self.keycheck),'backup-recovery-kit-txt':str(self.kit)},
            'fingerprint':self.fpr,'key_file':str(self.keyfile),'panel_version':'test-only','system':{'ID':'test','VERSION_ID':'1','architecture':'test'},'requirements':{}}
        owner=self
        self.operations=[];self.fail_app=None
        class Driver(full.Recovery):
            def driver_json(self,action,*args):
                if action=='inventory':return copy.deepcopy(fixture)
                if action=='capture':
                    folder=Path(args[0]);data=folder/'inner.txt';data.write_text('synthetic SQL and application data')
                    package=folder/'set.tar'
                    with tarfile.open(package,'w') as archive:archive.add(data,arcname='data.txt')
                    data.unlink()
                    return {'complete':'yes','recoverability':'full','file':str(package)}
                if action=='unpack':
                    stage=owner.root/'application-stage';stage.mkdir(exist_ok=True)
                    return dict(stage=str(stage),**{app:str(stage/app) for app in fixture['applications']})
                if action=='cleanup':return {'removed':True}
                raise AssertionError(action)
            def driver_json_secret(self,action,phrase,*args):
                assert phrase==PHRASE
                owner.operations.append((action,args))
                if action=='restore-part' and args[0]==owner.fail_app:raise full.Error('synthetic application restore failure')
                return {'imported':True} if action=='import-key' else {'restored':True}
            def task(self,action,*args,**kwargs):
                assert (action,args[0])==('dspace-backup-crypto','encrypt')
                owner.crypto.call('--trust-model','always','--output',args[2],'--encrypt','--recipient',owner.fpr,args[1])
                return ''
        self.recovery=Driver(self.driver,self.state);self.fixture=fixture
    def test_all_codecs_open_on_an_independent_destination_using_only_package_and_phrase(self):
        for codec in full.CODECS:
            with self.subTest(codec=codec):
                result=self.recovery.create(self.destination,codec)
                self.assertTrue(result['complete'])
                foreign=full.Recovery(self.driver,self.root/('new-server-'+codec))
                with foreign.opened(result['file'],PHRASE) as (tree,manifest):
                    self.assertEqual(manifest['applications'],['koha'])
                    self.assertEqual((tree/'settings/panel-settings/preferences.json').read_text(),'{"language":"pt"}')
                    self.assertTrue((tree/'data/applications.tar').is_file())
                    self.assertEqual(manifest['compression'],codec)
                self.assertFalse(any((self.root/('new-server-'+codec)).iterdir()))
                self.assertEqual(Path(result['file']).stat().st_mode&0o777,0o600)
    def test_wrong_phrase_does_not_change_source_or_destination_configuration(self):
        result=self.recovery.create(self.destination)
        before=(self.settings/'preferences.json').read_bytes()
        with self.assertRaises(full.Error):self.recovery.verify(result['file'],'wrong-phrase')
        self.assertEqual((self.settings/'preferences.json').read_bytes(),before)
        self.assertFalse(any(self.state.glob('opened-*')))
    def test_query_and_plan_do_not_create_state_or_touch_applications(self):
        result=self.recovery.plan('xz')
        self.assertEqual(result['compression'],'xz');self.assertFalse(result['os_image'])
        self.assertFalse(self.state.exists());self.assertFalse(self.destination.exists())
    def test_an_outdated_portable_kit_is_refused_before_capturing_an_application(self):
        self.kit.write_text(self.kit.read_text().replace('fingerprint='+self.fpr,'fingerprint='+'A'*40))
        with self.assertRaisesRegex(full.Error,'current recovery kit'):self.recovery.create(self.destination)
        self.assertFalse(list(self.destination.iterdir()))
    def test_source_changes_preserve_the_previous_valid_package(self):
        previous=self.recovery.create(self.destination)['file']
        original=self.recovery.driver_json;reads=[0]
        def driver(action,*args):
            if action=='inventory':
                reads[0]+=1
                if reads[0]==2:(self.settings/'new-during-capture.json').write_text('{"changed":true}')
            return original(action,*args)
        self.recovery.driver_json=driver
        with self.assertRaisesRegex(full.Error,'source settings changed'):self.recovery.create(self.destination)
        self.assertEqual(list(self.destination.iterdir()),[Path(previous)])
        self.assertEqual(self.recovery.status()['file'],previous)
    def test_incomplete_capture_is_never_published_as_full(self):
        original=self.recovery.driver_json
        self.recovery.driver_json=lambda action,*args: {'complete':'no','recoverability':'partial'} if action=='capture' else original(action,*args)
        with self.assertRaisesRegex(full.Error,'incomplete'):self.recovery.create(self.destination)
        self.assertFalse(list(self.destination.iterdir()));self.assertFalse((self.state/'last.json').exists())
    def test_unknown_application_state_is_never_silently_omitted(self):
        self.fixture['unknown']=['dspace']
        with self.assertRaisesRegex(full.Error,'unreadable'):self.recovery.plan()
        self.assertFalse(self.state.exists())
    def test_tampered_encrypted_payload_is_refused_before_decryption(self):
        result=self.recovery.create(self.destination)
        with zipfile.ZipFile(result['file']) as archive:members={name:archive.read(name) for name in archive.namelist()}
        members['payload.gpg']=members['payload.gpg'][:-1]+bytes([members['payload.gpg'][-1]^1])
        bad=self.root/'bad.nexus'
        with zipfile.ZipFile(bad,'w') as archive:
            for name,value in members.items():archive.writestr(name,value)
        with self.assertRaisesRegex(full.Error,'damaged'):self.recovery.verify(bad,PHRASE)
    def test_private_key_without_phrase_protection_is_never_exported_in_envelope(self):
        crypto=full.Crypto(self.root/'unprotected')
        try:
            crypto.call('--quick-generate-key','Unprotected Test <bad@example.invalid>','future-default','default','never',phrase='')
            fpr=next(line.split(':')[9] for line in crypto.call('--with-colons','--list-keys').decode().splitlines() if line.startswith('fpr:'))
            key=crypto.call('--armor','--export-secret-keys',fpr,phrase='')
            with self.assertRaisesRegex(full.Error,'passphrase-protected'):crypto.check_key(key,fpr)
        finally:crypto.close()
    def test_archive_code_and_special_entries_are_not_executed_or_extracted(self):
        archive=self.root/'bad.tar'
        with tarfile.open(archive,'w') as stream:
            member=tarfile.TarInfo('settings/link');member.type=tarfile.SYMTYPE;member.linkname='/etc'
            stream.addfile(member)
        target=self.root/'out';target.mkdir()
        with self.assertRaisesRegex(full.Error,'Unsafe'):full.extract(archive,target,1024,'none')
        self.assertFalse(list(target.iterdir()))



    def test_restore_resumes_only_remaining_components_after_a_failure(self):
        self.fixture['applications']=['koha','tainacan','dspace']
        package=self.recovery.create(self.destination)['file']
        session=self.recovery.prepare(package,PHRASE)['session']
        self.fail_app='koha'
        with self.assertRaisesRegex(full.Error,'synthetic application'):self.recovery.restore(session,PHRASE)
        record=self.recovery.restore_plan(session)
        self.assertEqual(record['phase'],'interrupted');self.assertEqual(record['completed'],['dspace'])
        with self.assertRaisesRegex(full.Error,'Resume'):self.recovery.cleanup(session)
        self.fail_app=None
        restored=self.recovery.restore(session,PHRASE)
        self.assertTrue(restored['restored']);self.assertEqual(restored['phase'],'complete')
        calls=[args[0] for name,args in self.operations if name=='restore-part']
        self.assertEqual(calls,['dspace','koha','koha','tainacan'])
        self.recovery.restore(session,PHRASE)
        self.assertEqual(calls,[args[0] for name,args in self.operations if name=='restore-part'])
        self.recovery.cleanup(session);self.assertFalse(Path(session).exists())

    def test_incompatible_destination_never_imports_keys_or_changes_applications(self):
        package=self.recovery.create(self.destination)['file']
        session=self.recovery.prepare(package,PHRASE)['session']
        self.fixture['fingerprint']='A'*40
        plan=self.recovery.restore_plan(session)
        self.assertFalse(plan['compatible']);self.assertIn('different backup key',' '.join(plan['problems']))
        with self.assertRaises(full.Error):self.recovery.restore(session,PHRASE)
        self.assertEqual(self.operations,[])

    def test_bad_phrase_does_not_apply_any_recovery_component(self):
        session=self.recovery.prepare(self.recovery.create(self.destination)['file'],PHRASE)['session']
        with self.assertRaises(full.Error):self.recovery.restore(session,'incorrect')
        self.assertEqual(self.operations,[]);self.assertEqual(self.recovery.restore_plan(session)['phase'],'opened')

    def test_changed_opened_session_is_refused_before_restoration(self):
        session=self.recovery.prepare(self.recovery.create(self.destination)['file'],PHRASE)['session']
        (Path(session)/'tree/program/installer').write_text('changed program')
        with self.assertRaisesRegex(full.Error,'contents changed'):self.recovery.restore(session,PHRASE)
        self.assertEqual(self.operations,[])

    def test_global_operations_share_a_nonblocking_lock(self):
        with full.operation(self.state):
            with self.assertRaisesRegex(full.Error,'already running'):self.recovery.create(self.destination)

    def test_long_server_paths_do_not_break_gnupg_agent_sockets(self):
        self.recovery.home=self.root/('long-server-directory-'*5)/'sessions'
        package=self.recovery.create(self.destination)['file']
        opened=self.recovery.prepare(package,PHRASE)
        self.assertTrue(self.recovery.restore(opened['session'],PHRASE)['restored'])


class Configuration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.tree=self.root/'tree';self.tree.mkdir(mode=0o700)
        self.session=self.root/'session';self.session.mkdir(mode=0o700)
        self.source=self.tree/'settings';self.source.mkdir(mode=0o700)
        self.dest=self.root/'destination';self.dest.mkdir(mode=0o700)
        self.current={'targets':{'panel-settings':str(self.dest/'conf'),'backup-plans':str(self.dest/'plans')}}
    def write(self,role,name,data):
        folder=self.source/role;folder.mkdir(mode=0o700,exist_ok=True)
        (folder/name).write_text(json.dumps(data))
    def test_source_jobs_are_disabled_and_existing_target_jobs_and_identities_are_preserved(self):
        self.write('panel-settings','theme-settings.json',{'colour':'green'})
        self.write('panel-settings','tunnel.conf',{'secret':'never-auto-publish'})
        plan={'schema':1,'id':'daily','members':['dspace'],'time':'02:00','keep':7,'destination':'/old/path','remote':'drive:old'}
        self.write('backup-plans','daily.json',plan)
        self.write('backup-plans','existing.json',dict(plan,id='existing'))
        (self.dest/'plans').mkdir(mode=0o700);(self.dest/'plans/existing.json').write_text('existing target job')
        result=full.apply_settings(self.tree,self.session,self.current)
        self.assertEqual(json.loads((self.dest/'plans/daily.json').read_text())['time'],'')
        self.assertEqual((self.dest/'plans/existing.json').read_text(),'existing target job')
        self.assertFalse((self.dest/'conf/tunnel.conf').exists())
        self.assertFalse(result['source_schedules_activated'])
        self.assertTrue((self.source/'panel-settings/tunnel.conf').exists())
        self.assertEqual(full.apply_settings(self.tree,self.session,self.current),result)
    def test_settings_failure_rolls_back_every_completed_write(self):
        self.write('panel-settings','theme-settings.json',{'colour':'green'})
        plan={'schema':1,'id':'daily','members':['dspace'],'time':'02:00'}
        self.write('backup-plans','daily.json',plan)
        original=full.atomic
        def fail(path,value):
            if Path(path)==self.dest/'conf/theme-settings.json':raise OSError('synthetic full disk')
            return original(path,value)
        with patch.object(full,'atomic',side_effect=fail):
            with self.assertRaises(OSError):full.apply_settings(self.tree,self.session,self.current)
        self.assertFalse((self.dest/'plans/daily.json').exists())
    def test_process_death_rolls_back_partial_settings_before_recomputing_the_restore_list(self):
        plan={'schema':1,'id':'daily','members':['dspace'],'time':'02:00'}
        self.write('backup-plans','daily.json',plan)
        (self.dest/'plans').mkdir(mode=0o700)
        target=self.dest/'plans/daily.json';target.write_text('{"partial":true}')
        area=self.session/'settings-rollback';area.mkdir(mode=0o700)
        full.atomic(area/'journal.json',json.dumps({'phase':'applying','rows':[{'target':str(target),
            'backup':None,'old_sha256':None,'new_sha256':full.sha(target)}]}))
        full.apply_settings(self.tree,self.session,self.current)
        self.assertEqual(json.loads(target.read_text())['time'],'')
        self.assertEqual(json.loads(target.read_text())['id'],'daily')
    def test_symlink_destination_is_refused_before_writing_any_configuration(self):
        self.write('panel-settings','theme-settings.json',{'colour':'green'})
        (self.dest/'conf').symlink_to(self.root/'elsewhere')
        with self.assertRaisesRegex(full.Error,'symbolic link'):full.apply_settings(self.tree,self.session,self.current)
        self.assertFalse((self.root/'elsewhere').exists())
    def test_recovery_never_executes_a_language_shell_fragment(self):
        source=self.source/'panel-language';source.write_text('KOHA_PANEL_LANG="pt"\nKOHA_PANEL_LANG_FULL="pt-BR"\n$(touch forbidden)\n')
        self.current.update(panel_languages=['pt','pt-BR']);self.current['targets']['panel-language']=str(self.dest/'language.conf')
        full.apply_settings(self.tree,self.session,self.current)
        self.assertEqual((self.dest/'language.conf').read_text(),'KOHA_PANEL_LANG="pt"\nKOHA_PANEL_LANG_FULL="pt-BR"\n')


class Distribution(unittest.TestCase):
    def test_adapter_is_pinned_and_shell_driver_keeps_machine_output_separate(self):
        import re
        text=(REPO/'installer').read_text()
        expected=re.search(r'KEI_NEXUS_RECOVERY_SHA="([a-f0-9]{64})"',text)[1]
        self.assertEqual(expected,full.sha(REPO/'platforms/nexus/recovery.py'))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'.set-restore.fixture';(stage/'koha').mkdir(parents=True)
            sql=stage/'koha/test.sql.gz';sql.write_text('fixture SQL')
            body=text[text.index('kei_nexus_recovery_driver() {'):text.index('# kei_set_platforms:')]
            script=root/'driver.sh';script.write_text(body+"\n"+r'''
kei_task() { [ "$1" = restore ] && [ "$2" = "$EXPECTED_SQL" ] || return 5; echo 'database restored'; }
kei_set_koha_extras() { [ "$1" = apply ] && [ "$2" = "$EXPECTED_STAGE" ] && [ "$3" = confirm ] || return 5; printf 'secrets=open\n'; }
kei_nexus_recovery_driver restore-part koha "$EXPECTED_SQL" "$EXPECTED_STAGE"
''')
            result=subprocess.run(['bash',str(script)],env=dict(os.environ,KEI_BK_ROOT=str(root),EXPECTED_STAGE=str(stage),EXPECTED_SQL=str(sql)),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),{'restored':True})
            self.assertIn('database restored',result.stderr)
    def test_single_downloaded_installer_uses_verified_cache_offline_and_refuses_tampering(self):
        text=(REPO/'installer').read_text();start=text.index('kei_nexus_recovery() (');end=text.index('kei_nexus_recovery_driver() {',start)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);driver=root/'config.sh';source=root/'repo/platforms/nexus';source.mkdir(parents=True)
            shutil.copyfile(REPO/'platforms/nexus/recovery.py',source/'recovery.py')
            driver.write_text('fixture driver')
            shell=text[start:end]
            setup='\n'.join(['KEI_NEXUS_RECOVERY_SHA='+full.sha(source/'recovery.py'),
                'KEI_DSPACE_ADAPTER_DIR="$FIXTURE/cache/dspace"','KEI_NEXUS_RECOVERY_HOME="$FIXTURE/home"',
                '_SCRIPT_PATH="$FIXTURE/config.sh"','_SCRIPT_DIR="$FIXTURE/repo"'])+'\n'
            env=dict(os.environ,FIXTURE=str(root))
            result=subprocess.run(['bash','-c',setup+shell+'kei_nexus_recovery cache'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            shutil.rmtree(root/'repo')
            query=setup+shell+'''
curl() { echo "network must not be used" >&2; return 1; }
kei_nexus_recovery status
'''
            result=subprocess.run(['bash','-c',query],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['compression'],'gz')
            self.assertFalse((root/'home').exists())
            cached=next((root/'cache/nexus').rglob('recovery.py'));cached.chmod(0o600);cached.write_text('tampered code')
            result=subprocess.run(['bash','-c',query],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
