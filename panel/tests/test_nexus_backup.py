"""New full-recovery controls: reads, explicit consent and truthful outcomes."""
import asyncio
import base64
import json

import pytest

from kei_panel.bridge import TaskOutcome
from kei_panel.routines import nexus_backup as full
from kei_panel.screens.dialogs import MessageScreen
from kei_panel.tasks import TaskResult


class App:
    def __init__(self,answers=()):self.answers=list(answers);self.screens=[];self.changed=0
    async def push_screen_wait(self,screen):
        self.screens.append(screen)
        if isinstance(screen,MessageScreen):return None
        assert self.answers,'Unexpected question'
        return self.answers.pop(0)
    def check_platforms(self):self.changed+=1


def calls(monkeypatch,reply):
    recorded=[]
    async def run(app,title,name,*args,**kwargs):
        recorded.append((name,args,kwargs))
        data=reply.get(args[0],{})
        if data is None:return TaskResult(ok=False,value=TaskOutcome(rc=4))
        return TaskResult(ok=True,value=TaskOutcome(results={'payload':base64.b64encode(json.dumps(data).encode()).decode()}))
    monkeypatch.setattr(full,'run_task',run)
    async def show(*args):pass
    monkeypatch.setattr(full,'show_failure',show)
    return recorded


def plan(**more):
    return dict(compatible=True,phase='opened',applications=['koha','tainacan','dspace'],images=4,completed=[],**more)


@pytest.mark.parametrize('confirm',[False,None])
def test_cancelled_recovery_does_not_change_an_application_or_import_an_image(monkeypatch,confirm):
    ran=calls(monkeypatch,{})
    app=App([confirm]);asyncio.run(full.restore_session(app,'/private/session',plan(),'test-phrase'))
    assert ran==[] and app.changed==0


def test_phrase_uses_only_the_single_task_environment_and_failed_restore_never_reports_completion(monkeypatch):
    ran=calls(monkeypatch,{'restore':None})
    app=App([True]);asyncio.run(full.restore_session(app,'/private/session',plan(),'test-phrase'))
    assert ran[0][:2]==('nexus-full',('restore','/private/session','--confirm'))
    assert ran[0][2]['env']=={'KEI_BACKUP_PHRASE':'test-phrase'}
    assert not ran[0][2]['cancellable']
    assert app.changed==0
    assert any('did not finish' in screen._body for screen in app.screens if isinstance(screen,MessageScreen))
    assert not any('test-phrase' in str(vars(screen)) for screen in app.screens)


def test_incompatible_target_may_only_import_images_after_a_second_confirmation(monkeypatch):
    ran=calls(monkeypatch,{'load-images':{'loaded':['sha256:fixture']}})
    data=plan();data.update(compatible=False,problems=['Prepare compatible empty applications first'])
    app=App(['images',True]);asyncio.run(full.restore_session(app,'/private/session',data))
    assert [args[0] for _,args,_ in ran]==['load-images']
    assert app.changed==0


def test_success_refreshes_state_and_points_to_private_review_material(monkeypatch):
    ran=calls(monkeypatch,{'restore':dict(plan(),restored=True,settings={'reference_directory':'/private/review'})})
    app=App([True]);asyncio.run(full.restore_session(app,'/private/session',plan(),'test-phrase'))
    assert app.changed==1
    assert any('/private/review' in screen._body for screen in app.screens if isinstance(screen,MessageScreen))

@pytest.mark.parametrize('size',[(80,24),(160,48)])
def test_full_backup_tab_only_reads_and_stays_reachable_in_small_terminal(monkeypatch,size):
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.views.backups import BackupCenterView
    from textual.widgets import Select
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA','1');monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN','1');monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE','1')
    async def exercise():
        app=KohaPanelApp(PanelEnv(installer=None,lang='en',plain=True,demo=True))
        original=app.bridge.task;ran=[]
        async def task(name,*args,**kwargs):
            ran.append((name,args));return await original(name,*args,**kwargs)
        app.bridge.task=task
        async with app.run_test(size=size) as pilot:
            await pilot.pause(1.0)
            app.backup_scope='nexus';app.screen.action_show('backups')
            for _ in range(120):
                await pilot.pause(.1)
                view=app.screen.query_one(BackupCenterView)
                if not view.query_one('#platform-loader').display:break
            assert view.scope=='nexus' and view.query_one('#bk-nexus').display
            assert not view.query_one('#bk-plans').display
            codec=view.query_one('#bk-nexus-codec',Select)
            assert not codec.disabled and codec.value=='gz'
            assert view.query_one('#bk-scope',Select).value=='nexus'
            assert all(args==('status',) for name,args in ran if name=='nexus-full')
    asyncio.run(exercise())
