"""Bundled-language capabilities, selection and configuration transactions."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'platforms/dspace'))
import languages as lang
import runtime
import operations

class Catalog(unittest.TestCase):
    def test_bundled_codes_and_old_image_capabilities(self):
        self.assertEqual(len(lang.catalog()),37)
        self.assertEqual(len(lang.catalog(4)),35)
        self.assertEqual(len({r['code'] for r in lang.catalog()}),37)
        self.assertEqual({r['code'] for r in lang.catalog()}-{r['code'] for r in lang.catalog(4)},{'ja','sw'})
        self.assertTrue(all(len(r['sha256'])==64 and r['label'] for r in lang.catalog()))
    def test_suggestions_use_real_supported_translations(self):
        for panel,expected in [('pt','pt-BR'),('pt_PT','pt-PT'),('de','de'),('ja','ja'),('ko','en'),('fil','en'),('unknown','en')]:
            self.assertEqual(lang.suggest(panel),expected)
        self.assertEqual(lang.suggest('ja',4),'en')
    def test_account_creation_matches_the_installed_helper(self):
        self.assertEqual(lang.account_code('pt_BR',4),'pt_BR')
        self.assertEqual(lang.account_code('fr',4),'')
        self.assertEqual(lang.account_code('pt_BR',5),'pt-BR')
        self.assertEqual(lang.account_code('fr',5),'fr')
    def test_invalid_or_inactive_fallback_never_mutates_configuration(self):
        compose={'services':{'ui':{'environment':{'OTHER':'keep'}}}}
        for request in ({'active':[],'fallback':'en'},{'active':['en'],'fallback':'fr'},{'active':['unknown'],'fallback':'en'},{'active':['en','en'],'fallback':'en'}):
            old=copy.deepcopy(compose)
            with self.assertRaises(ValueError):lang.edit(compose,request)
            self.assertEqual(old,compose)
    def test_selection_changes_only_language_environment_fields(self):
        compose={'services':{'ui':{'environment':{'DSPACE_UI_BASEURL':'http://repo.test:8100','OTHER':'keep'}}},'volumes':{'assetstore':'kept'}}
        result=lang.edit(compose,{'active':['en','fr'],'fallback':'fr'})
        self.assertEqual(result['active'],['en','fr']);self.assertEqual(result['fallback'],'fr')
        self.assertEqual(compose['services']['ui']['environment']['OTHER'],'keep')
        self.assertEqual(compose['volumes'],{'assetstore':'kept'})
    def test_legacy_indices_are_preserved_even_with_new_languages_inserted(self):
        legacy={r['code']:r['index'] for r in lang.catalog(4)}
        self.assertEqual(legacy['fr'],10);self.assertEqual(legacy['pt-BR'],24)
        compose={'services':{'ui':{'environment':{}}}}
        result=lang.edit(compose,{'active':['en','fr'],'fallback':'fr'},4)
        self.assertEqual(result['active'],['en','fr'])
        self.assertNotIn('ja',[r['code'] for r in result['available']])
    def test_image_upgrade_preserves_languages_by_code_when_indices_change(self):
        compose={'services':{'ui':{'environment':{'OTHER':'kept'}}}}
        lang.edit(compose,{'active':['en','kk','pt-PT','sr-lat'],'fallback':'pt-PT'},4)
        result=lang.migrate_environment(compose,4)
        self.assertEqual(set(result['active']),{'en','kk','pt-PT','sr-lat'})
        self.assertEqual(result['fallback'],'pt-PT')
        self.assertEqual(compose['services']['ui']['environment']['OTHER'],'kept')
    def test_custom_mapping_is_preserved_instead_of_reinterpreted(self):
        compose={'services':{'ui':{'environment':{'DSPACE_LANGUAGES_1_CODE':'custom'}}}}
        before=copy.deepcopy(compose)
        with self.assertRaises(ValueError):lang.migrate_environment(compose,4)
        self.assertEqual(before,compose)

class LanguageTransaction(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'dspace';self.root.mkdir(mode=0o700)
        self.rt=runtime.Runtime(self.root,lab=True);self.rt.mark(status='preparing')
        compose={'services':{'ui':{'image':'unchanged-ui','environment':{'OTHER':'kept'}},'backend':{'image':'unchanged-backend'}},'volumes':{'db':'unchanged-volume'}}
        for name,text in [('compose.json',json.dumps(compose)),('local.cfg','private unchanged configuration'),('db-password','test-only')]:runtime.atomic(self.root/name,text)
        self.rt.mark(status='installed',phase='ready',migration='done',release_sha256=self.rt.release_hash,prepared=True,url='http://localhost:8100',files={n:runtime.digest(self.root/n) for n in ('compose.json','local.cfg','db-password')})
        self.rt.existing_resources=Mock();self.rt.compose=Mock();self.rt.health=Mock();self.rt.public_health=Mock()
        self.op=operations.Operations(self.rt);self.request={'active':['en','pt-BR','fr','ja'],'fallback':'pt-BR'}
    def test_interrupted_language_rollback_restarts_only_the_interface(self):
        original=(self.root/'compose.json').read_bytes()
        self.op.snapshot('languages')
        runtime.atomic(self.root/'compose.json','{}')
        self.op.rollback()
        self.assertEqual((self.root/'compose.json').read_bytes(),original)
        self.rt.compose.assert_called_once_with('up','-d','--pull','never','--no-deps','--force-recreate','ui',timeout=240)
    def test_interrupted_language_rollback_keeps_stopped_services_stopped(self):
        self.rt.mark(intended='stopped')
        self.op.snapshot('languages')
        runtime.atomic(self.root/'compose.json','{}')
        self.op.rollback()
        self.rt.compose.assert_not_called()
        self.rt.health.assert_not_called()
        self.assertEqual(self.rt.state()['intended'],'stopped')
    def test_read_and_plan_never_restart_or_change_files(self):
        before={n:runtime.digest(self.root/n) for n in ('compose.json','local.cfg','db-password','state.json')}
        status=self.op.languages({'panel_language':'pt'})
        self.assertEqual(status['suggested'],'pt-BR');self.assertFalse(status['downloads_required'])
        self.op.language_save(self.request)
        self.assertEqual(before,{n:runtime.digest(self.root/n) for n in before});self.rt.compose.assert_not_called()
        self.assertFalse(self.op.journal.exists())
    def test_save_restarts_only_ui_and_preserves_repository_configuration(self):
        before={n:(self.root/n).read_bytes() for n in ('local.cfg','db-password')}
        result=self.op.language_save(self.request,True)
        self.assertTrue(result['saved']);self.assertEqual(result['fallback'],'pt-BR')
        self.rt.compose.assert_called_once_with('up','-d','--pull','never','--no-deps','--force-recreate','ui',timeout=240)
        self.assertEqual(before,{n:(self.root/n).read_bytes() for n in before})
        self.assertEqual(json.loads((self.root/'compose.json').read_text())['volumes'],{'db':'unchanged-volume'})
    def test_failed_web_validation_restores_previous_configuration(self):
        old=(self.root/'compose.json').read_bytes();old_state=self.rt.state()
        self.rt.public_health.side_effect=runtime.Refused('Injected web failure')
        with self.assertRaises(runtime.Refused):self.op.language_save(self.request,True)
        self.assertEqual((self.root/'compose.json').read_bytes(),old)
        self.assertEqual(self.rt.state(),old_state)
        self.assertEqual(json.loads(self.op.journal.read_text())['phase'],'rolled-back')
    def test_stale_plan_is_refused_before_a_snapshot_or_restart(self):
        with self.assertRaisesRegex(runtime.Refused,'configuration changed'):
            self.op.language_save(dict(self.request,expected_revision='0'*64),True)
        self.assertFalse(self.op.journal.exists());self.rt.compose.assert_not_called()
    def test_stopped_repository_saves_without_starting_any_service(self):
        self.rt.mark(status='stopped',intended='stopped')
        result=self.op.language_save(self.request,True)
        self.assertTrue(result['pending_start']);self.rt.compose.assert_not_called()
        self.rt.health.assert_not_called();self.rt.public_health.assert_not_called()
        self.assertEqual(self.rt.state()['intended'],'stopped')
    def test_changed_running_intent_requires_reviewing_the_plan_again(self):
        plan=self.op.language_save(self.request)
        self.rt.mark(status='stopped',intended='stopped')
        with self.assertRaisesRegex(runtime.Refused,'configuration changed'):
            self.op.language_save(dict(self.request,expected_revision=plan['revision']),True)
        self.rt.compose.assert_not_called()

class ReadOnlyCLI(unittest.TestCase):
    def test_language_query_does_not_wait_for_stdin(self):
        import io
        with tempfile.TemporaryDirectory() as temp, patch.object(sys,'argv',['runtime.py','--root',str(Path(temp)/'dspace'),'operations','languages']),patch.object(sys,'stdout',new_callable=io.StringIO),patch.object(sys,'stdin') as stdin,patch.object(operations.Operations,'languages',return_value={'available':[]}) as read:
            stdin.read.side_effect=AssertionError('Readonly query must not wait for operator input')
            self.assertEqual(runtime.main(),0)
            read.assert_called_once_with({})
