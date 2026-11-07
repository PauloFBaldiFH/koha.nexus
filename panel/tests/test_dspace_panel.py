"""DSpace's independent navigation, confirmations and protected account flow."""
import asyncio
import base64
import itertools
import json
from types import SimpleNamespace

import pytest
from textual.widgets import TabbedContent

from kei_panel.app import KohaPanelApp
from kei_panel.bridge import TaskOutcome
from kei_panel.dspace import origin, payload
from kei_panel.env import PanelEnv
from kei_panel.routines import dspace
from kei_panel.screens.dialogs import InputScreen, MessageScreen
from kei_panel.tasks import TaskResult
from kei_panel.widgets.cards import ActionCard


def response(data):
    out = TaskOutcome()
    out.feed('@@result payload=' + base64.b64encode(json.dumps(data).encode()).decode())
    return TaskResult(ok=True, value=out)


def test_payload_preserves_newlines_and_unicode_without_protocol_injection():
    data={'logs': 'first\n@@result changed=true\nSão Paulo'}
    out=response(data).value
    assert payload(out)==data and 'changed' not in out.results
    assert payload(TaskOutcome(results={'payload': 'not base64'}))=={}


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'http://u:pass@example.org', 'http://example.org/path', 'http://example.org\nHeader'])
def test_dashboard_never_opens_an_untrusted_url(url):
    assert origin(url)==''


@pytest.mark.parametrize('koha,tainacan,ds', list(itertools.product(('0','1'),repeat=3)))
@pytest.mark.parametrize('size', [(80,24),(160,48)])
def test_independent_dspace_navigation_reads_only(monkeypatch,koha,tainacan,ds,size):
    for key,value in [('KOHA',koha),('TAINACAN',tainacan),('DSPACE',ds)]:
        monkeypatch.setenv('KEI_PANEL_DEMO_'+key,value)
    async def exercise():
        app=KohaPanelApp(PanelEnv(installer=None,lang='en',plain=True,demo=True))
        calls=[];real=app.bridge.task
        async def task(name,*args,**kwargs):
            calls.append((name,args));return await real(name,*args,**kwargs)
        app.bridge.task=task
        async with app.run_test(size=size) as pilot:
            await pilot.pause(1.8)
            tabs=app.screen.query_one('#dash-tabs',TabbedContent)
            assert tabs.get_tab('dash-tab-dspace').display is (ds=='1')
            app.screen.action_show('dspace')
            await pilot.pause(1.8)
            view=app.screen.query_one('#view-dspace')
            cards=[c.entry.action for c in view.query(ActionCard) if c.display]
            assert ('dspace-install' in cards) is (ds=='0')
            assert ('dspace-admin' in cards) is (ds=='1')
            assert not set(cards)&{'restore','tainacan-restore','backup-manual'}
            assert all(name=='platform-backup-status' or (name=='dspace-panel' and args==('setup-status',)) for name,args in calls)
    asyncio.run(exercise())


class App:
    def __init__(self,answers=()):self.answers=list(answers);self.screens=[]
    async def push_screen_wait(self,screen):
        self.screens.append(screen)
        if isinstance(screen,MessageScreen):return None
        assert self.answers,'Unexpected question'
        return self.answers.pop(0)


def mock_calls(monkeypatch,answers):
    calls=[]
    async def run(app,title,name,*args,**kwargs):
        calls.append((name,args,kwargs))
        data=answers.get(args[0] if name=='dspace-panel' else name,{})
        return response(data)
    monkeypatch.setattr(dspace,'run_task',run)
    return calls


def test_missing_catalog_never_installs_dependencies_or_asks_for_address(monkeypatch):
    calls=mock_calls(monkeypatch,{'availability':{'available':False,'reason':'No reviewed catalog'}})
    app=App();asyncio.run(dspace.install(app))
    assert [c[:2] for c in calls]==[('dspace-panel',('availability',))]
    assert all(isinstance(s,MessageScreen) for s in app.screens)


@pytest.mark.parametrize('confirmed',[False,None])
def test_declining_apache_confirmation_stops_install(monkeypatch,confirmed):
    calls=mock_calls(monkeypatch,{'availability':{'available':True},'dspace-prerequisites':{'apache_missing':True}})
    app=App([confirmed])
    async def status():return {'docker':{'installed':True}}
    app.bridge=SimpleNamespace(status=status)
    asyncio.run(dspace.install(app))
    assert [c[:2] for c in calls]==[('dspace-panel',('availability',)),('dspace-prerequisites',('plan',))]


@pytest.mark.parametrize('answers',[[None],['create','admin@example.org','Name','Last','en',None],['create','admin@example.org','Name','Last','en','Private-password-123','Does-not-match']])
def test_cancel_or_mismatched_password_never_creates_admin(monkeypatch,answers):
    calls=mock_calls(monkeypatch,{'admin-status':{'state':'missing','admins':[]}})
    app=App(answers);asyncio.run(dspace.admin(app))
    assert [c[:2] for c in calls]==[('dspace-panel',('admin-status',))]


def test_admin_password_is_hidden_and_only_sent_in_one_task_environment(monkeypatch):
    secret='Private-password-123'
    calls=mock_calls(monkeypatch,{'admin-status':{'state':'missing','admins':[]},'admin-create':{'changed':True}})
    app=App(['create','admin@example.org','Name','Last','pt_BR',secret,secret,True])
    asyncio.run(dspace.admin(app))
    saved=calls[-1]
    assert saved[:2]==('dspace-panel',('admin-create','--confirm'))
    assert secret not in str(saved[:2])
    assert json.loads(saved[2]['env']['KEI_DSPACE_ADMIN_DATA'])['password']==secret
    assert len([s for s in app.screens if isinstance(s,InputScreen) and s._password])==2
    assert all(secret not in getattr(s,'_text','') for s in app.screens)


def test_postpone_and_close_never_configures_cloud_or_backup(monkeypatch):
    calls=mock_calls(monkeypatch,{'setup-status':{'setup':'open','steps':{'admin':'pending'}},'setup-mark':{'setup':'open'},'setup-close':{'setup':'none'},'status':{'url':'http://192.168.1.20:8100'}})
    app=App(['later','close']);asyncio.run(dspace.assistant(app))
    args=[c[1] for c in calls]
    assert ('setup-mark','admin','later') in args and ('setup-close',) in args
    assert all(c[0]=='dspace-panel' for c in calls)
    assert not any('install' in a or 'backup' in a[0] for a in args)
