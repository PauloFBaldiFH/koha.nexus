import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from kei_panel import cron, schedules
from kei_panel.schedule_controls import Control, EditError, checksum, controls, managed_file
from kei_panel.routines.schedules import apply
from kei_panel.bridge import TaskOutcome
from kei_panel.tasks import TaskResult

TEXT = cron.CRON_PATH + '\n# keep this comment\n0 23 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1\n# my task\n4 3 * * * root echo keep-me\n# BEGIN MANUAL\n0 2 * * * root echo block\n# END MANUAL\n'


def koha(text=TEXT):
    rows=schedules.collect({schedules.TASKS_FILE:text},'library',False)
    values=controls(rows,{schedules.TASKS_FILE:text},'library')
    return rows,next(iter(values.values()))


@pytest.mark.parametrize('freq,day,time,expected', [('daily',0,'09:15','15 9 * * *'),('weekly',6,'03:04','4 3 * * 6'),('monthly',31,'00:08','8 0 31 * *'),('custom',0,'00:00','*/5 * * * *')])
def test_changes_one_known_job_and_preserves_manual_content(freq,day,time,expected):
    rows,control=koha()
    values=control.edited(dict(enabled=True,freq=freq,day=day,time=time,raw='*/5 * * * *'))
    new=control.koha_text(values)
    assert new == TEXT.replace('0 23 * * *',expected,1)
    assert [r.key for r in rows if not r.key] == ['', '']


def test_disable_can_ignore_invalid_unused_time_and_keeps_the_previous_schedule():
    _,control=koha()
    values=control.edited(dict(enabled=False,freq='daily',time='wrong',day=0))
    assert control.koha_text(values)==TEXT.replace('0 23 * * * root',cron.OFF+'0 23 * * * root',1)


@pytest.mark.parametrize('field,value', [('time','24:00'),('time','2:99'),('freq','hourly'),('enabled','yes'),('day',True)])
def test_invalid_edit_refused(field,value):
    _,control=koha()
    with pytest.raises(EditError):control.edited(dict(control.values(),**{field:value}))


def test_duplicate_targets_and_manual_lines_have_no_controls():
    rows,control=koha()
    assert len(controls(rows,{schedules.TASKS_FILE:TEXT},'library'))==1
    repeated=TEXT+TEXT
    rows=schedules.collect({schedules.TASKS_FILE:repeated},'library',False)
    assert controls(rows,{schedules.TASKS_FILE:repeated},'library')=={}


def test_disabled_group_remains_visible_and_has_one_control():
    rows=[]
    state={'schedule':'','key':'FINGERPRINT'}
    values=controls(rows,{},'library',tainacan=state)
    assert len(rows)==len(values)==1
    control=values[id(rows[0])]
    assert control.enabled is False and control.time=='02:30'
    assert control.frequencies==('daily',)


def test_manual_cron_line_prevents_group_rewrite():
    text='0 2 * * * root /usr/local/bin/config.sh --task platform-backup-run tainacan scheduled >/dev/null 2>&1\n'
    assert managed_file(text,'tainacan')
    assert not managed_file(text+'0 3 * * * root echo important\n','tainacan')
    rows=schedules.collect({schedules.PLATFORM_FILE:text+'0 3 * * * root echo important\n'},'library',True)
    values=controls(rows,{schedules.PLATFORM_FILE:text+'0 3 * * * root echo important\n'},'library',tainacan={'schedule':'02:00'})
    assert not values[id(rows[0])].available


def test_disabled_dspace_plan_visible_without_cron_file_and_members_preserved():
    plan=dict(schema=1,id='nightly',time='',members=['koha','dspace'],keep=14,destination='/backup',remote='drive:path')
    rows=[];result=controls(rows,{},'library',plans=[plan]);control=result[id(rows[0])]
    assert not control.enabled and control.plan==plan and rows[0].platform=='koha+dspace'


@pytest.mark.parametrize('driver,task,args', [('tainacan','platform-backup-schedule',('tainacan','off')),('set','set-schedule',('time=off',))])
def test_group_disable_only_sends_schedule_and_expected_revision(monkeypatch,driver,task,args):
    from kei_panel.routines import schedules as routine
    calls=[]
    async def run(app,title,name,*values,**kwargs):
        calls.append((name,values));return TaskResult(ok=True,value=TaskOutcome())
    async def done(*args):pass
    monkeypatch.setattr(routine,'run_task',run);monkeypatch.setattr(routine,'show_done',done)
    control=Control(schedules.Row('tainacan','backup','Backup','','on','file'),driver,original='original')
    assert asyncio.run(apply(SimpleNamespace(),control,dict(enabled=False,time='02:30')))
    assert calls[0][0]==task and calls[0][1][:len(args)]==args
    assert checksum('original') in calls[0][1][-1]


def test_koha_writer_receives_private_tempfile_and_revision_and_cleans_up(monkeypatch):
    from kei_panel.routines import schedules as routine
    _,control=koha();calls=[]
    async def run(app,title,name,*args,**kwargs):
        path=Path(args[0]);calls.append(path)
        assert name=='cron-apply' and args[1]==checksum(TEXT)
        assert path.read_text()==TEXT.replace('0 23 * * *','0 8 * * *',1)
        return TaskResult(ok=True,value=TaskOutcome())
    async def done(*args):pass
    monkeypatch.setattr(routine,'run_task',run);monkeypatch.setattr(routine,'show_done',done)
    values=control.edited(dict(control.values(),time='08:00'))
    assert asyncio.run(apply(SimpleNamespace(),control,values))
    assert not calls[0].exists()


@pytest.mark.parametrize('size',[(80,24),(160,48)])
def test_editor_keeps_drafts_cancel_is_read_only_and_save_persists_through_writer(monkeypatch,size):
    from kei_panel import demo
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.screens.dialogs import ConfirmScreen, MessageScreen
    from textual.widgets import Switch
    files={schedules.TASKS_FILE:TEXT}
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA','1')
    monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN','0')
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE','0')
    monkeypatch.setattr(demo,'demo_cron_files',lambda *args:dict(files))
    async def until(pilot, condition):
        for _ in range(80):
            if condition(): return
            await pilot.pause(.1)
        raise AssertionError('Schedule editor did not reach the expected state')
    async def exercise():
        calls=[];app=KohaPanelApp(PanelEnv(installer=None,lang='en',plain=True,demo=True));original=app.bridge.task
        async def task(name,*args,**kwargs):
            if name=='cron-apply':
                assert args[1]==checksum(files[schedules.TASKS_FILE])
                files[schedules.TASKS_FILE]=Path(args[0]).read_text()
                calls.append(name)
                return TaskOutcome()
            return await original(name,*args,**kwargs)
        app.bridge.task=task
        async with app.run_test(size=size) as pilot:
            await pilot.pause(.3)
            app.screen.action_show('schedules')
            view=app.screen.query_one('#view-schedules')
            await until(pilot,lambda:view.ready)
            index=next(i for i,r in enumerate(view.rows) if r.key=='koha:backup_sql')
            view.query_one(f'#sc-on-{index}',Switch).value=False
            await pilot.pause(.1)
            assert not calls and files[schedules.TASKS_FILE]==TEXT
            for button in view.query('.sc-controls Button'):
                assert button.region.right <= view.content_region.right
            view.query_one(f'#sc-save-{index}').press()
            await until(pilot,lambda:isinstance(app.screen,ConfirmScreen))
            app.screen.dismiss(False)
            await pilot.pause(.2)
            assert not calls
            view.query_one(f'#sc-save-{index}').press()
            await until(pilot,lambda:isinstance(app.screen,ConfirmScreen))
            app.screen.dismiss(True)
            await until(pilot,lambda:isinstance(app.screen,MessageScreen))
            app.screen.dismiss(None)
            await until(pilot,lambda:view.ready and bool(view.controls) and not next(c for c in view.controls.values() if c.row.key=='koha:backup_sql').enabled)
            assert calls==['cron-apply']
            assert files[schedules.TASKS_FILE]==TEXT.replace('0 23 * * * root',cron.OFF+'0 23 * * * root',1)
            # Re-enable and change its hour, then filter without losing the draft.
            index=next(i for i,r in enumerate(view.rows) if r.key=='koha:backup_sql')
            view.query_one(f'#sc-on-{index}',Switch).value=True
            view.query_one(f'#sc-time-{index}').value='08:30'
            view.set_scope('server')
            await until(pilot,lambda:not view.query(f'#sc-on-{index}'))
            view.set_scope('koha')
            await until(pilot,lambda:bool(view.query(f'#sc-on-{index}')))
            assert view.query_one(f'#sc-time-{index}').value=='08:30'
            assert len(calls)==1
    asyncio.run(exercise())


def test_operations_group_contains_only_the_exact_plan_command():
    source='30 2 * * * root KEI_DSPACE_OPERATIONS_DATA=\'{"id":"nightly"}\' /usr/local/bin/config.sh --task dspace operations plan-run --confirm >/dev/null 2>&1\n'
    assert managed_file(source,'operations','nightly')
    assert not managed_file(source,'operations','another')
    assert not managed_file(source+'0 3 * * * root echo manual\n','operations','nightly')


def test_missing_configured_cron_is_explicitly_repairable_without_reporting_it_enabled():
    rows=[]
    result=controls(rows,{},'library',tainacan={'schedule':'07:15','key':'FINGERPRINT'})
    control=result[id(rows[0])]
    assert not control.enabled and control.out_of_sync and control.time=='07:15'


@pytest.mark.parametrize('enabled,action',[ (False,'plan-disable'), (True,'plan-save')])
def test_operations_schedule_edit_keeps_other_plan_fields_and_sends_snapshot(monkeypatch,enabled,action):
    import json
    from kei_panel.routines import schedules as routine
    plan=dict(schema=1,id='nightly',members=['koha','dspace'],time='02:30',keep=17,destination='/old',remote='drive:old')
    calls=[]
    async def run(app,title,name,*args,**kwargs):
        request=json.loads(kwargs['env']['KEI_DSPACE_OPERATIONS_DATA']);calls.append(request)
        assert name=='dspace-panel' and args==('operations',action,'--confirm')
        return TaskResult(ok=True,value=TaskOutcome())
    async def done(*args):pass
    monkeypatch.setattr(routine,'run_task',run);monkeypatch.setattr(routine,'show_done',done)
    control=Control(schedules.Row('koha+dspace','backup','nightly','','on','file'),'operations',plan=plan)
    assert asyncio.run(apply(SimpleNamespace(),control,dict(enabled=enabled,time='08:30')))
    assert calls[0]['expected_plan']==plan and plan['time']=='02:30'
    if enabled:
        assert {k:calls[0][k] for k in plan if k!='time'}=={k:v for k,v in plan.items() if k!='time'}
        assert calls[0]['time']=='08:30'


def test_group_preserves_manual_environment_by_refusing_a_rewrite():
    assert not managed_file('CRON_TZ=UTC\n','tainacan')
    assert not managed_file('MAILTO=person@example.org\n','set')
    assert not managed_file('SHELL=/custom/shell\n','set')


def test_real_protocol_tainacan_schedule_is_normalized_and_editable(monkeypatch):
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    monkeypatch.setenv('KEI_PANEL_DEMO_KOHA','0');monkeypatch.setenv('KEI_PANEL_DEMO_TAINACAN','1')
    monkeypatch.setenv('KEI_PANEL_DEMO_DSPACE','0')
    async def exercise():
        app=KohaPanelApp(PanelEnv(installer=None,lang='en',plain=True,demo=True))
        async with app.run_test(size=(80,24)) as pilot:
            await pilot.pause(.2);app.screen.action_show('schedules')
            view=app.screen.query_one('#view-schedules')
            for _ in range(100):
                if view.ready:break
                await pilot.pause(.1)
            assert view.ready
            row=next(r for r in view.rows if r.key=='tainacan:run')
            control=view.controls[id(row)]
            assert control.time=='02:30' and control.enabled and control.available
    asyncio.run(exercise())
