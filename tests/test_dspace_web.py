"""HTTP checks and transactional configuration repair; no real DSpace data."""
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'platforms/dspace'))
import runtime as ds
import operations as ops

class WebChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),self.handler())
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        self.documents={
            '/server/api':dict(dspaceVersion='DSpace 10.1',dspaceUI=self.origin,dspaceServer=self.origin+'/server',_links={'communities':{'href':self.origin+'/server/api/core/communities'}}),
            '/server/api/authn/status':dict(okay=True,authenticated=False),
            '/assets/config.json':dict(ui={'baseUrl':self.origin},rest={'baseUrl':self.origin+'/server'}),
            '/': '<ds-app>DSpace</ds-app>',
            '/login':'<ds-app>DSpace<input type="email"><input type="password"></ds-app>'}
        self.failures={};self.origins=[]
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.rt=ds.Runtime(Path(self.tmp.name)/'dspace',lab=True)
        self.rt.state=Mock(return_value=dict(url=self.origin,proxy_status='apache-configured',ports={'ui':self.server.server_port,'backend':self.server.server_port}))
    def handler(self):
        test=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                test.origins.append(self.headers.get('Origin'))
                self.send_response(test.failures.get(self.path,200));self.end_headers()
                data=test.documents.get(self.path,{})
                self.wfile.write((data if isinstance(data,str) else json.dumps(data)).encode())
            def log_message(self,*args):pass
        return Handler
    def test_full_local_proxy_and_actual_canonical_origin(self):
        result=self.rt.public_health()
        self.assertEqual(result['status'],'verified-local-proxy')
        self.assertEqual(result['login_form'],'ok')
        self.assertTrue(all(origin==self.origin for origin in self.origins))
    def test_http_200_shell_and_translated_500_page_are_not_a_login(self):
        self.documents['/login']='<ds-app>DSpace<h1>500</h1>Serviço indisponível</ds-app>'
        with self.assertRaisesRegex(ds.Refused,'password form'):self.rt.web_checks(self.server.server_port,self.server.server_port)
    def test_stale_browser_configuration_is_rejected(self):
        self.documents['/assets/config.json']['rest']['baseUrl']='http://192.168.1.50:8100/server'
        with self.assertRaisesRegex(ds.Refused,'browser configuration'):self.rt.public_health()
    def test_api_root_ok_does_not_hide_failed_authentication(self):
        self.failures['/server/api/authn/status']=500
        with self.assertRaisesRegex(ds.Refused,'HTTP 500'):self.rt.public_health()
    def test_advertised_api_links_must_use_the_browser_origin(self):
        self.documents['/server/api']['dspaceServer']='http://192.168.1.50:8100/server'
        with self.assertRaisesRegex(ds.Refused,'different public address'):self.rt.public_health()
    def test_unreachable_canonical_address_is_not_healthy(self):
        real_open=ds.HTTP.open
        def open_request(request,**kwargs):
            if request.full_url==self.origin+'/server/api/authn/status' and request.get_header('Host') is None:
                raise OSError('Connection timed out')
            return real_open(request,**kwargs)
        with patch.object(ds.HTTP,'open',side_effect=open_request),self.assertRaisesRegex(ds.Refused,'configured browser address'):self.rt.public_health()

class WebRepair(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'dspace';self.root.mkdir(mode=0o700)
        self.rt=ds.Runtime(self.root,lab=True)
        self.rt.mark(status="preparing")
        self.old_url='http://192.168.1.50:8100'
        self.new_url='http://192.168.100.56:8100'
        self.compose={'services':{'ui':{'image':'sha256:unchanged-ui','environment':{'DSPACE_UI_BASEURL':self.old_url,'DSPACE_REST_HOST':'192.168.1.50','DSPACE_REST_PORT':'8100','DSPACE_REST_SSL':'false','DSPACE_REST_SSRBASEURL':'http://backend:8080/server','OTHER':'kept'}},'backend':{'image':'sha256:unchanged-api'}},'volumes':{'data':{'name':'kn-dspace-postgres'}}}
        cfg='dspace.ui.url = '+self.old_url+'\ndspace.server.url = '+self.old_url+'/server\nrest.cors.allowed-origins = '+self.old_url+'\ndb.password = unchanged-test-password\ncustom.option = kept\n'
        for name,text in [('local.cfg',cfg),('compose.json',json.dumps(self.compose)),('db-password','unchanged-test-password')]:ds.atomic(self.root/name,text)
        self.rt.mark(status='installed',phase='ready',prepared=True,migration='done',url=self.old_url,release_sha256=self.rt.release_hash,ports={'ui':18100,'backend':18101},proxy_status='apache-configured',files={n:ds.digest(self.root/n) for n in ('local.cfg','compose.json','db-password')})
        self.original={n:(self.root/n).read_bytes() for n in ('state.json','local.cfg','compose.json','db-password')}
        self.rt.existing_resources=Mock();self.rt.compose=Mock();self.rt.dependencies=Mock();self.rt.health=Mock();self.rt.public_health=Mock(return_value={'status':'verified-local-proxy'})
        self.rt.core=Mock(return_value='apache-nexus');self.o=ops.Operations(self.rt)
    def test_plan_does_not_write_or_restart(self):
        result=self.o.repair_web({'url':self.new_url})
        self.assertEqual(result['url'],self.new_url);self.rt.compose.assert_not_called()
        self.assertFalse(self.o.journal.exists())
        self.assertEqual(self.original,{n:(self.root/n).read_bytes() for n in self.original})
    def test_repair_changes_only_web_configuration_and_keeps_data_images_and_secrets(self):
        with patch.object(ops.Recovery,'capture') as capture,patch.object(ops.Recovery,'test') as restore:
            result=self.o.repair_web({'url':self.new_url},True)
        self.assertTrue(result['repaired']);capture.assert_not_called();restore.assert_not_called()
        self.assertEqual((self.root/'db-password').read_bytes(),self.original['db-password'])
        self.assertIn('custom.option = kept',(self.root/'local.cfg').read_text())
        actual=json.loads((self.root/'compose.json').read_text())
        expected=copy.deepcopy(self.compose);expected['services']['ui']['environment'].update(DSPACE_UI_BASEURL=self.new_url,DSPACE_REST_HOST='192.168.100.56')
        self.assertEqual(actual,expected)
        self.assertEqual(self.rt.state()['url'],self.new_url)
        journal=json.loads(self.o.journal.read_text());self.assertEqual(journal['phase'],'complete')
        self.assertEqual(journal['files']['local.cfg'].encode(),self.original['local.cfg'])
        self.assertEqual(self.o.journal.stat().st_mode&0o777,0o600)
        self.assertFalse(any('migrate' in str(c) for c in self.rt.compose.call_args_list))
    def test_localhost_mode_updates_api_ui_and_cors_together(self):
        result=self.o.repair_web({'local_only':True},True)
        self.assertEqual(result['url'],'http://localhost:8100');self.assertTrue(result['local_only'])
        cfg=(self.root/'local.cfg').read_text();self.assertNotIn(self.old_url,cfg)
        self.assertEqual(cfg.count('http://localhost:8100'),3)
    def test_failed_web_check_rolls_back_the_exact_configuration(self):
        self.rt.public_health.side_effect=ds.Refused('Injected proxy failure')
        with self.assertRaisesRegex(ds.Refused,'Injected proxy failure'):self.o.repair_web({'url':self.new_url},True)
        self.assertEqual({n:v for n,v in self.original.items() if n!='state.json'}, {n:(self.root/n).read_bytes() for n in self.original if n!='state.json'})
        self.assertEqual(json.loads(self.original['state.json']),self.rt.state())
        self.assertEqual(json.loads(self.o.journal.read_text())['phase'],'rolled-back')
    def test_can_finish_a_failed_web_phase_without_rerunning_migration(self):
        self.rt.mark(status='failed',phase='proxy')
        self.o.repair_web({'url':self.new_url},True)
        self.assertEqual(self.rt.state()['phase'],'ready')
        self.assertEqual(self.rt.state()['migration'],'done')
        self.assertFalse(any('migrate' in str(c) for c in self.rt.compose.call_args_list))
    def test_unassigned_address_is_refused_before_writes(self):
        self.rt.core.side_effect=ds.Refused('Address not found')
        with self.assertRaises(ds.Refused):self.o.repair_web({'url':self.new_url},True)
        self.assertFalse(self.o.journal.exists());self.rt.compose.assert_not_called()
    def test_port_domain_or_https_change_requires_the_address_flow(self):
        for url in ('http://192.168.100.56:8200','https://repo.example.org','http://repo.example.org:8100'):
            with self.subTest(url=url),self.assertRaises(ds.Refused):self.o.repair_web({'url':url},True)
        self.rt.compose.assert_not_called()
