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
from kei_panel.screens.install_flow import CheckReportScreen, CompletionScreen, PlanSummaryScreen
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
            if ds == '1':
                tabs.active = 'dash-tab-dspace'
                await pilot.pause(0.3)
                from kei_panel.widgets.cards import LinkCard
                summary = app.screen.query_one('#dash-dspace')
                for card in summary.query(LinkCard):
                    for button in card.query('Button'):
                        assert button.region.right <= card.content_region.right
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
        if isinstance(screen,CheckReportScreen) and screen._final:return True   # a report, not a question
        if isinstance(screen,CompletionScreen):return None    # U4: "Do it later" (test_u4_completion covers the action)
        assert self.answers,'Unexpected question'
        return self.answers.pop(0)


# U3: the initial diagnosis and the final report read these.
DEFAULTS={'preflight':{'checks':[{'id':'memory','state':'ok','label':'Free memory (4 GB needed)','detail':'6.1 GB'}],'ok':True},
          'diagnose':{'status':'installed','services':{},'health':'not-checked'}}


def mock_calls(monkeypatch,answers):
    calls=[]
    async def run(app,title,name,*args,**kwargs):
        calls.append((name,args,kwargs))
        key=args[0] if name=='dspace-panel' else name
        data=answers.get(key,DEFAULTS.get(key,{}))
        return response(data)
    monkeypatch.setattr(dspace,'run_task',run)
    return calls


def test_missing_catalog_never_installs_dependencies_or_asks_for_address(monkeypatch):
    calls=mock_calls(monkeypatch,{'availability':{'available':False,'reason':'No reviewed catalog'}})
    app=App();asyncio.run(dspace.install(app))
    assert [c[:2] for c in calls]==[('dspace-panel',('availability',))]
    assert all(isinstance(s,MessageScreen) for s in app.screens)


@pytest.mark.parametrize('confirm', [False, None, True])
def test_experimental_preparation_is_offered_and_can_be_postponed(monkeypatch, confirm):
    calls = mock_calls(monkeypatch, {
        'availability': {'available': True, 'prepare_required': True},
        'dspace-prerequisites': {}, 'prepare-images': {'prepared': True}})
    # The first answer is the initial diagnosis' Continue (U3).
    app = App([True, confirm, None] if confirm else [True, confirm])
    async def status(): return {'docker': {'installed': True}}
    app.bridge = SimpleNamespace(status=status)
    asyncio.run(dspace.install(app))
    preparations = [c for c in calls if c[1] == ('prepare-images', '--confirm')]
    assert bool(preparations) is bool(confirm)
    assert not any(c[1][0] == 'install' for c in calls)


@pytest.mark.parametrize('confirmed',[False,None])
def test_declining_apache_confirmation_stops_install(monkeypatch,confirmed):
    calls=mock_calls(monkeypatch,{'availability':{'available':True},'dspace-prerequisites':{'apache_missing':True}})
    app=App([True,confirmed])
    async def status():return {'docker':{'installed':True}}
    app.bridge=SimpleNamespace(status=status)
    asyncio.run(dspace.install(app))
    assert [c[:2] for c in calls]==[('dspace-panel',('availability',)),('dspace-prerequisites',('plan',)),('dspace-panel',('preflight',))]


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
    assert all(secret not in getattr(s,'_body','') for s in app.screens)


def test_postpone_and_close_never_configures_cloud_or_backup(monkeypatch):
    calls=mock_calls(monkeypatch,{'setup-status':{'setup':'open','steps':{'admin':'pending'}},'setup-mark':{'setup':'open'},'setup-close':{'setup':'none'},'status':{'url':'http://192.168.1.20:8100'}})
    app=App(['later','later','later','close']);asyncio.run(dspace.assistant(app))
    args=[c[1] for c in calls]
    assert ('setup-mark','admin','later') in args and ('setup-close',) in args
    assert all(c[0]=='dspace-panel' for c in calls)
    assert not any('install' in a or 'backup' in a[0] for a in args)

@pytest.mark.parametrize('retry',[False,True])
def test_migration_retry_requires_its_own_confirmation(monkeypatch,retry):
    calls=mock_calls(monkeypatch,{'availability':{'available':True},'dspace-prerequisites':{'apache_missing':False},
                                'status':{'url':'http://192.168.1.20:8100','migration':'failed'},
                                'plan':{'url':'http://192.168.1.20:8100'},'install':{'status':'installed'},'setup-status':{'setup':'none'}})
    app=App([True,True,retry])
    async def status():return {'docker':{'installed':True}}
    app.bridge=SimpleNamespace(status=status)
    app.check_platforms=lambda: None
    asyncio.run(dspace.install(app))
    writes=[args for name,args,kw in calls if name=='dspace-panel' and args[0]=='install']
    assert bool(writes) is retry
    if retry:assert writes[0][-1]=='--retry-migration'


def test_start_with_docker_stopped_requires_separate_consent(monkeypatch):
    calls=mock_calls(monkeypatch,{'status':{'status':'unavailable'},'dspace-prerequisites':{'docker_stopped':True}})
    asyncio.run(dspace.start(App([False])))
    assert [c[:2] for c in calls]==[('dspace-panel',('status',)),('dspace-prerequisites',('plan',))]


def test_external_proxy_instructions_are_shown_before_setup(monkeypatch):
    note='External proxy needs both the /server and / routes; address not verified.'
    mock_calls(monkeypatch,{'availability':{'available':True},'dspace-prerequisites':{'apache_missing':False},
                           'status':{'url':'http://192.168.1.20:8100'},'plan':{'url':'http://192.168.1.20:8100'},
                           'install':{'status':'installed','note':note},'setup-status':{'setup':'none'}})
    app=App([True,True]);app.check_platforms=lambda:None
    async def status():return {'docker':{'installed':True}}
    app.bridge=SimpleNamespace(status=status)
    asyncio.run(dspace.install(app))
    assert any(note==s._note for s in app.screens if isinstance(s,CompletionScreen))   # U4: in the completion


def test_failed_worker_never_continues_even_with_partial_success_payload(monkeypatch):
    async def failed_worker(*args,**kwargs):
        partial=response({'available':True})
        partial.ok=False;partial.error='Worker failed before completing the task'
        return partial
    monkeypatch.setattr(dspace,'run_task',failed_worker)
    app=App();asyncio.run(dspace.install(app))
    assert len(app.screens)==1 and isinstance(app.screens[0],MessageScreen)
    assert 'Worker failed' in app.screens[0]._body


def test_dspace_only_has_individual_scope_and_three_installed_platforms_have_explicit_sets():
    from kei_panel import backup_center
    assert backup_center.scopes(False,False,True)==['dspace']
    assert backup_center.scopes(True,True,True)==['koha','tainacan','dspace','both','koha-dspace','tainacan-dspace','all']


@pytest.mark.parametrize('answer',[None,False])
def test_declining_backup_never_stops_the_repository(monkeypatch,answer):
    calls=mock_calls(monkeypatch,{'backup-settings':{'compression':'xz'}})
    asyncio.run(dspace.backup_create(App([answer])))
    assert [c[:2] for c in calls]==[('dspace-panel',('backup-settings',))]


def test_backup_confirmation_displays_and_uses_the_selected_compression(monkeypatch):
    calls=mock_calls(monkeypatch,{'backup-settings':{'compression':'xz'},
                                'backup-create':{'package':'/backup/repo.tar.xz.gpg'}})
    app=App([True]);asyncio.run(dspace.backup_create(app))
    assert 'XZ / LZMA' in app.screens[0]._question
    assert calls[-1][:2]==('dspace-panel',('backup-create','--compression','xz','--confirm'))


def test_recovery_phrase_is_masked_and_only_in_task_environment(monkeypatch):
    package='/var/backups/koha-nexus/dspace/sample.tar.gpg'; phrase='test recovery phrase only'
    calls=mock_calls(monkeypatch,{'backup-list':{'packages':[package]},'backup-test':{'verified':True}})
    app=App([package,phrase,True]); asyncio.run(dspace.backup_test(app))
    call=calls[-1]
    assert call[:2]==('dspace-panel',('backup-test',package,'--confirm'))
    assert phrase not in str(call[:2])
    assert call[2]['env']=={'KEI_BACKUP_PHRASE':phrase}
    assert any(isinstance(s,InputScreen) and s._password for s in app.screens)


def test_cancel_recovery_phrase_never_starts_restore(monkeypatch):
    package='/var/backups/koha-nexus/dspace/sample.tar.gpg'
    calls=mock_calls(monkeypatch,{'backup-list':{'packages':[package]}})
    asyncio.run(dspace.backup_restore(App([package,None])))
    assert len(calls)==1


@pytest.mark.parametrize('size',[(80,24),(160,48)])
def test_dspace_only_backup_center_has_its_own_actions_without_writes(monkeypatch,size):
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA','0')
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN','0')
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE','1')
    async def exercise():
        app=KohaPanelApp(PanelEnv(installer=None,lang='en',plain=True,demo=True))
        calls=[]; real=app.bridge.task
        async def task(name,*args,**kwargs):
            calls.append((name,args)); return await real(name,*args,**kwargs)
        app.bridge.task=task
        async with app.run_test(size=size) as pilot:
            await pilot.pause(1.8)
            app.backup_scope='dspace'; app.screen.action_show('backups')
            await pilot.pause(1.8)
            view=app.screen.query_one('#view-backups')
            assert view.scope=='dspace'
            cards={c.entry.action for c in view.query(ActionCard) if c.display}
            assert {'dspace-backup-create','dspace-backup-test','dspace-backup-restore','dspace-backup-key'} <= cards
            assert not cards & {'backup-manual','tainacan-backup','set-backup','restore-assisted'}
            assert all(not (name=='dspace-panel' and args and args[0].startswith('backup-') and args[0]!='backup-list') for name,args in calls)
    asyncio.run(exercise())


def test_declining_recovery_plan_never_stops_the_repository(monkeypatch):
    package='/var/backups/koha-nexus/dspace/sample.tar.gpg'
    calls=mock_calls(monkeypatch,{'backup-list':{'packages':[package]},'backup-plan':{'old_volumes_preserved':True}})
    app=App([package,'test-only recovery phrase',False])
    asyncio.run(dspace.backup_restore(app))
    assert [c[:2] for c in calls]==[('dspace-panel',('backup-list',)),('dspace-panel',('backup-plan',package))]


def test_new_backup_sets_use_explicit_members_without_widening_legacy_scope():
    from kei_panel import backup_center as b
    assert b.MEMBERS['both']==('koha','tainacan')
    assert b.scopes(True,False,True)==['koha','dspace','koha-dspace']
    assert b.scopes(False,True,True)==['tainacan','dspace','tainacan-dspace']
    assert b.MEMBERS['all']==('koha','tainacan','dspace')


def test_operations_cancellation_never_applies_a_change(monkeypatch):
    async def preview(*args,**kwargs):return {'safety_backup':True,'url':'https://repo.example.org','previous_url':'http://repo.local:8100','external_proxy_manual':False}
    calls=[]
    async def observe(app,command,*args,**kwargs):calls.append((command,args));return await preview()
    monkeypatch.setattr(dspace,'call',observe)
    app=App([False]);asyncio.run(dspace.operation(app,'address',{'url':'https://repo.example.org'}))
    assert calls==[('operations',('address',))]


def test_address_without_key_can_be_postponed_before_reserving_a_free_name(monkeypatch):
    from kei_panel.routines import platforms, common
    async def no_key(app):return SimpleNamespace(key=False)
    calls=[]
    async def interactive(*args,**kwargs):calls.append((args,kwargs))
    monkeypatch.setattr(platforms,'backup_state',no_key)
    monkeypatch.setattr(common,'run_interactive',interactive)
    app=App(['free',False])
    asyncio.run(dspace.address(app))
    assert not calls


def test_encrypted_plan_rows_report_upload_failure_separately():
    from kei_panel import backup_center as b
    data={'plans':[{'id':'nightly','members':['dspace'],'destination':'/backups','remote':'drive:Repo','time':'02:30','keep':7,
                    'last':{'capture':'ok','copy':'failed','finished':1}}]}
    rows=b.operation_plans(data,'dspace')
    assert len(rows)==1 and rows[0].state=='bad' and 'encrypted' in rows[0].encrypted.lower()
    assert b.operation_plans(data,'koha-dspace')==[]


@pytest.mark.parametrize('size',[(80,24),(160,48)])
def test_all_three_platforms_remain_reachable_in_the_shared_backup_selector(monkeypatch,size):
    for name in ('KOHA','TAINACAN','DSPACE'):monkeypatch.setenv('KEI_PANEL_DEMO_'+name,'1')
    async def exercise():
        app=KohaPanelApp(PanelEnv(installer=None,lang='en',plain=True,demo=True))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(1.8)
            app.backup_scope='dspace';app.screen.action_show('backups')
            view=app.screen.query_one('#view-backups')
            async def ready(condition):
                for _ in range(120):
                    if condition(): return
                    await pilot.pause(.1)
                raise AssertionError('Backup selector did not reach the expected state')
            await ready(lambda: view.facts is not None and not view.query_one('#platform-loader').display)
            from textual.widgets import Select
            select=view.query_one('#bk-scope',Select)
            assert 'all' in [value for _label,value in select._options]
            assert select.region.intersection(view.region).width==select.region.width
            select.value='all'
            await ready(lambda: view.scope=='all' and app.backup_scope=='all')
    asyncio.run(exercise())


@pytest.mark.parametrize('answer',[None,False])
def test_web_repair_cancel_never_changes_configuration(monkeypatch,answer):
    calls=mock_calls(monkeypatch,{'operations':{'url':'http://localhost:8100'}})
    app=App([None] if answer is None else ['local',False])
    asyncio.run(dspace.repair_web(app))
    assert not any('--confirm' in c[1] for c in calls)


def test_web_repair_uses_the_chosen_actual_network_ip_and_explicit_confirmation(monkeypatch):
    actual='http://192.168.100.56:8100'
    calls=mock_calls(monkeypatch,{'operations':{'url':actual}})
    app=App(['network',actual,True]);app.check_platforms=lambda:None
    asyncio.run(dspace.repair_web(app))
    assert [c[1] for c in calls]==[('operations','repair-web'),('operations','repair-web','--confirm')]
    assert all(json.loads(c[2]['env']['KEI_DSPACE_OPERATIONS_DATA'])=={'local_only':False,'url':actual} for c in calls)
    assert actual+'/login' in app.screens[-1]._body


def test_wsl_install_can_choose_localhost_without_copying_an_example_ip(monkeypatch):
    calls=mock_calls(monkeypatch,{'availability':{'available':True},'dspace-prerequisites':{'platform':'wsl2'},'status':{'status':'absent'},'plan':{'url':'http://localhost:8100'}})
    app=App([True,'local',False])
    async def status():return {'docker':{'installed':True}}
    app.bridge=SimpleNamespace(status=status)
    asyncio.run(dspace.install(app))
    assert any(c[1]==('plan','--url','http://localhost:8100','--language','en') for c in calls)
    assert not any(isinstance(s,InputScreen) for s in app.screens)
    assert not any(c[1][0]=='install' for c in calls)


LANGUAGE_STATE={'available':[{'code':'en','label':'English'},{'code':'pt-BR','label':'Português do Brasil'},{'code':'fr','label':'Français'}], 'active':['en','pt-BR','fr'],'fallback':'en','suggested':'pt-BR','revision':'a'*64}

@pytest.mark.parametrize('answers',[[None],[['en'],None],[['en','fr'],'fr',False]])
def test_interface_language_cancel_never_applies(monkeypatch,answers):
    calls=mock_calls(monkeypatch,{'operations':LANGUAGE_STATE})
    asyncio.run(dspace.languages(App(answers)))
    assert not any('--confirm' in c[1] for c in calls)


def test_interface_language_save_has_an_explicit_review_and_keeps_separate_panel_preference(monkeypatch):
    calls=mock_calls(monkeypatch,{'operations':LANGUAGE_STATE})
    app=App([['en','fr'],'fr',True]);app.env=SimpleNamespace(lang='pt')
    asyncio.run(dspace.languages(app))
    writes=[c for c in calls if '--confirm' in c[1]]
    assert len(writes)==1 and writes[0][1]==('operations','language-save','--confirm')
    assert json.loads(writes[0][2]['env']['KEI_DSPACE_OPERATIONS_DATA'])=={'active':['en','fr'],'fallback':'fr','expected_revision':'a'*64}
    assert app.env.lang=='pt'


def test_administrator_choices_come_from_installed_capabilities(monkeypatch):
    supported=[{'code':'en','ui_code':'en','label':'English'},{'code':'fr','ui_code':'fr','label':'Français'}]
    calls=mock_calls(monkeypatch,{'admin-status':{'state':'missing','admins':[],'languages':supported}})
    app=App(['create','admin@example.org','Name','Last',None])
    asyncio.run(dspace.admin(app))
    assert app.screens[-1]._options==[('en','English'),('fr','Français')]
    assert not any('--confirm' in c[1] for c in calls)
