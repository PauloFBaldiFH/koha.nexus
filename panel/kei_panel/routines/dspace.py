"""DSpace's existing lifecycle adapter through the normal panel task bridge."""
from __future__ import annotations

import json
import re

from ..bridge import TaskOutcome
from ..dspace import (admin_emails, admin_fact, backup_rows, diagnosis_rows, origin, payload, plan_rows,
                      preflight_rows, repair_rows, restore_plan_rows, restore_rows, test_rows)
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from ..screens.install_flow import CheckReportScreen, CompletionScreen, PlanSummaryScreen
from .admin_access import ask_password
from .common import run_task, show_failure

TITLE = 'DSpace'
EMAIL = re.compile(r'[^@\s|=]+@[^@\s|=]+\.[^@\s|=]+')


async def call(app, command, *args, **kwargs):
    result = await run_task(app, TITLE, 'dspace-panel', command, *args, **kwargs)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    if result.cancelled or not result.ok or out is None or not out.ok:
        await show_failure(app, TITLE, result)
        return None
    data = payload(out)
    if not data:
        await app.push_screen_wait(MessageScreen(TITLE, t('DSpace returned no valid result. Update the panel before continuing.'), kind='error'))
        return None
    return data


async def initial_diagnosis(app):
    """Every requirement in one list before any question (study 16.3).

    Read only: the prerequisites plan and the runtime's preflight. Returns
    the prerequisites (for the confirmations that follow) or None when the
    person stopped here or something must be fixed first."""
    pre = await run_task(app, TITLE, 'dspace-prerequisites', 'plan')
    out = pre.value if isinstance(pre.value, TaskOutcome) else None
    if pre.cancelled or not pre.ok or out is None or not out.ok:
        await show_failure(app, TITLE, pre)
        return None
    deps = payload(out)
    checks = await call(app, 'preflight')
    if checks is None:
        return None
    rows = preflight_rows(checks, deps)
    if not await app.push_screen_wait(CheckReportScreen(t('Before installing DSpace'), rows)):
        return None
    return deps


async def final_diagnosis(app):
    """The installation's own checks, read again (study 16.3). Returns the
    runtime's answer, or None when it could not be read."""
    return await call(app, 'diagnose')


async def completion(app, result, url):
    """The end of the installation (study 8.3): ready, or installed with the
    administrator still to create. Creating it is offered here, once."""
    data = await final_diagnosis(app)
    checks = diagnosis_rows(data) if data is not None else [
        ('fail', 'API, interface and login page checked', t('The diagnosis could not be read.'))]
    admins = await call(app, 'admin-status', cancellable=False)
    fact = admin_fact(admins)
    site = origin(result.get('url', url)) or origin(url)
    note = t(result['note']) if isinstance(result.get('note'), str) and result['note'] else ''
    pending = fact[0] != 'ok'
    choice = await app.push_screen_wait(CompletionScreen(
        'DSpace', checks, [(t('Public site'), site), (t('Sign in'), site + '/login')] if site else [],
        facts=[fact], note=note,
        next_step=t('Create the administrator account to sign in to DSpace.') if pending else '',
        action=t('Create administrator now') if pending and admins is not None else '',
        reminder=t('Administrative access, addresses and backups are always in the DSpace menu.'),
        report_title=t('DSpace diagnosis after the installation'),
        details=json.dumps(data, ensure_ascii=False, indent=2) if data is not None else ''))
    if choice == 'action':
        await admin(app, create=True)


async def install(app):
    available = await call(app, 'availability')
    if available is None:
        return
    if not available.get('available'):
        await app.push_screen_wait(MessageScreen(TITLE, t('DSpace image configuration could not be used.') + '\n\n' + str(available.get('reason', ''))))
        return
    deps = await initial_diagnosis(app)
    if deps is None:
        return
    from .platforms import install_docker
    status = await app.bridge.status()
    if not (status.get('docker') or {}).get('installed'):
        if not await install_docker(app):
            return
        status = await app.bridge.status()
        if not (status.get("docker") or {}).get("installed"):
            return
        # Docker is new: read the prerequisites again before using them.
        pre = await run_task(app, TITLE, 'dspace-prerequisites', 'plan')
        out = pre.value if isinstance(pre.value, TaskOutcome) else None
        if pre.cancelled or not pre.ok or out is None or not out.ok:
            await show_failure(app, TITLE, pre)
            return
        deps = payload(out)
    # Closing any confirmation never continues installing.
    for needed, operation, question in (
        ('docker_stopped', 'docker-start', 'Start the existing Docker service for DSpace?'),
        ('apache_missing', 'apache', 'Install Apache to serve DSpace? Its package will be registered as a shared resource.')):
        if deps.get(needed):
            if not await app.push_screen_wait(ConfirmScreen(TITLE, t(question))):
                return
            result = await run_task(app, TITLE, 'dspace-prerequisites', operation, 'confirm', cancellable=False)
            if result.cancelled or not result.ok or not isinstance(result.value, TaskOutcome) or not result.value.ok:
                await show_failure(app, TITLE, result)
                return
    if available.get('prepare_required'):
        if not await app.push_screen_wait(ConfirmScreen(TITLE, t(
                'Prepare the DSpace images on this server? They are built here from a pinned, verified recipe (amd64 processor). This downloads the pinned sources and builds backend, interface and Solr. It can take 30–90 minutes or longer, uses additional disk and memory, and installs Git if missing. Existing Koha/Tainacan data are preserved. You can retry if preparation fails.'))):
            return
        if await call(app, 'prepare-images', '--confirm', cancellable=False) is None:
            return
    current = await call(app, 'status')
    if current is None:
        return
    url = current.get('url')
    from ..screens.port_field import PortScreen, address
    port_body = t('DSpace answers on a port of its own. Keep the suggested port or type another.')
    if not url and deps.get('platform') in ('wsl1', 'wsl2'):
        access = await app.push_screen_wait(ChoiceScreen(TITLE,
            t('Where will you open DSpace? On Windows/WSL, localhost avoids depending on LAN forwarding. Network access needs the real Windows IP and its network setup.'),
            [('local', t('This computer only (localhost)')), ('network', t('Other computers or an institutional domain'))]))
        if access is None:
            return
        if access == 'local':
            # The port shown, editable and checked (U9).
            chosen = await app.push_screen_wait(PortScreen(TITLE, port_body, 'dspace', host='localhost'))
            if chosen is None:
                return
            url = address(chosen, 'http', 'localhost')
    elif not url:
        access = await app.push_screen_wait(ChoiceScreen(TITLE,
            t('How will people open DSpace?'),
            [('port', t("This server's address, on a port of its own")),
             ('domain', t('A name (domain) already pointing to this server'))]))
        if access is None:
            return
        if access == 'port':
            chosen = await app.push_screen_wait(PortScreen(TITLE, port_body, 'dspace'))
            if chosen is None:
                return
            url = address(chosen)
    url = url or await app.push_screen_wait(InputScreen(
        TITLE, t('Use this server’s IP and a separate port (for example http://192.168.1.20:8100), or a DNS name already pointing here. Address and HTTPS assistance remains available after installation.'),
        t('Repository address:'), validate=lambda v: '' if origin(v) else t('Enter one HTTP(S) address without credentials or a path.')))
    if not url:
        return
    language = getattr(getattr(app,'env',None),'lang','en')
    plan = await call(app, 'plan', '--url', url, '--language', language)
    if plan is None:
        return
    # The plain summary first; the technical plan (JSON) stays one button away.
    if not await app.push_screen_wait(PlanSummaryScreen(
            t('Install DSpace · Review'), plan_rows(plan),
            body=t('Only its own resources are created; existing repository data are preserved.'),
            details=json.dumps(plan, ensure_ascii=False, indent=2))):
        return
    # A migration retry is a second, explicit decision, never implied by resume.
    retry = []
    if current.get('migration') in ('running', 'failed'):
        if not await app.push_screen_wait(ConfirmScreen(TITLE, t('An earlier database migration was interrupted or failed. Review the diagnosis and preserved data before another attempt. Explicitly retry the migration?'), danger=True)):
            return
        retry = ['--retry-migration']
    result = await call(app, 'install', '--url', url, '--language', language, '--confirm', *retry)
    if result is not None:
        app.check_platforms()
        await completion(app, result, url)


async def control(app, start):
    status = await call(app, 'status')
    if status is None:
        return
    if start and status.get('status') == 'unavailable':
        pre = await run_task(app, TITLE, 'dspace-prerequisites', 'plan')
        out = pre.value if isinstance(pre.value, TaskOutcome) else None
        if pre.cancelled or not pre.ok or out is None or not out.ok:
            await show_failure(app, TITLE, pre)
            return
        if payload(out).get('docker_stopped'):
            if not await app.push_screen_wait(ConfirmScreen(TITLE, t('Start the existing Docker service for DSpace?'))):
                return
            result = await run_task(app, TITLE, 'dspace-prerequisites', 'docker-start', 'confirm', cancellable=False)
            if result.cancelled or not result.ok or not isinstance(result.value, TaskOutcome) or not result.value.ok:
                await show_failure(app, TITLE, result)
                return
    question = 'Start DSpace using its current configuration? No migration or restoration is performed.' if start else 'Stop DSpace gracefully? The repository will be unavailable; all volumes and configuration are kept.'
    if await app.push_screen_wait(ConfirmScreen(TITLE, t(question))):
        data = await call(app, 'start' if start else 'stop', '--confirm', cancellable=False)
        if data is not None:
            await app.push_screen_wait(MessageScreen(TITLE, t('DSpace services updated. See state and addresses in the dashboard.')))


async def start(app):
    await control(app, True)


async def stop(app):
    await control(app, False)


async def diagnose(app):
    data = await call(app, 'diagnose')
    if data is not None:
        await app.push_screen_wait(CheckReportScreen(t('DSpace diagnosis'), diagnosis_rows(data), final=True,
                                                     details=json.dumps(data, ensure_ascii=False, indent=2)))


async def logs(app):
    data = await call(app, 'logs')
    if data is not None:
        await app.push_screen_wait(MessageScreen(t('DSpace logs'), data.get('logs', '')))


async def repair_web(app):
    choice = await app.push_screen_wait(ChoiceScreen(TITLE,
        t('Repair web access without reinstalling DSpace or changing repository data. Local access uses localhost on this computer; network publication remains in the address assistant.'),
        [('local', t('Use localhost on this computer')), ('network', t('Use the actual local network IPv4 address')), ('keep', t('Keep the current address and repair its proxy'))]))
    if choice is None:
        return
    request = {'local_only': choice == 'local'}
    if choice == 'network':
        url = await app.push_screen_wait(InputScreen(TITLE,
            t('Enter the current address shown by ip -br -4 addr, with the existing DSpace port. Example addresses are not real server addresses.'),
            t('Repository address:'), validate=lambda v: '' if origin(v) else t('Enter one HTTP(S) address without credentials or a path.')))
        if not url:
            return
        request['url'] = url
    env = {'KEI_DSPACE_OPERATIONS_DATA': json.dumps(request)}
    plan = await call(app, 'operations', 'repair-web', env=env)
    if plan is None:
        return
    if not await app.push_screen_wait(PlanSummaryScreen(
            t('Repair web access · Review'), repair_rows(plan),
            body=t('Review web repair. Configuration is saved for rollback; database, files, images and schedules are preserved.'),
            details=json.dumps(plan, ensure_ascii=False, indent=2), action=t('Repair'))):
        return
    result = await call(app, 'operations', 'repair-web', '--confirm', env=env, cancellable=False)
    if result is not None:
        app.check_platforms()
        await app.push_screen_wait(MessageScreen(TITLE, t('Web access repaired. Open the address shown in the dashboard.') + '\n\n' + origin(result.get('url', plan.get('url', ''))) + '/login'))


async def admin(app, create=False):
    """Create an administrator or change one's password. create=True comes
    from the completion screen: the choice was already made there."""
    data = await call(app, 'admin-status', cancellable=False)
    if data is None:
        return
    emails = admin_emails(data)
    if create:
        choice = 'create'
    else:
        choices = [('create', t('Create an administrator'))]
        if emails:
            choices.append(('password', t('Change the password of an administrator')))
        choice = await app.push_screen_wait(ChoiceScreen(TITLE, t('DSpace accounts are separate from Koha and WordPress. Existing accounts are never promoted or overwritten when creating an administrator.') + '\n\n' + ', '.join(emails), choices))
        if choice is None:
            return
    request = {}
    if choice == 'create':
        for key, label in (('email', 'E-mail:'), ('first', 'First name:'), ('last', 'Last name:')):
            value = await app.push_screen_wait(InputScreen(TITLE, '', t(label), validate=lambda v, k=key: '' if (EMAIL.fullmatch(v) if k == 'email' else v.strip()) else t('Invalid value.')))
            if not value:
                return
            request[key] = value
        choices = [(row['code'], row['label']) for row in data.get('languages', [])
                   if isinstance(row,dict) and isinstance(row.get('code'),str) and isinstance(row.get('label'),str)]
        if not choices:
            choices = [('pt_BR', 'Português'), ('en', 'English'), ('es', 'Español')]
        preferred = getattr(getattr(app,'env',None),'lang','en').split('-')[0].split('_')[0]
        choices.sort(key=lambda row: not row[0].startswith(preferred))
        language = await app.push_screen_wait(ChoiceScreen(TITLE, t('Account language'), choices))
        if not language:
            return
        request['language'] = language
    else:
        email = await app.push_screen_wait(ChoiceScreen(TITLE, t('Which account?'), [(e, e) for e in emails]))
        if not email:
            return
        request['email'] = email
    password = await ask_password(app, TITLE, request['email'])
    if password is None:
        return
    request['password'] = password
    if not await app.push_screen_wait(ConfirmScreen(TITLE, t('Apply this administrator change in DSpace? Other accounts and encryption keys are kept.'))):
        return
    result = await call(app, 'admin-' + choice, '--confirm', env={'KEI_DSPACE_ADMIN_DATA': json.dumps(request)}, cancellable=False)
    request.clear()
    password = ''
    if result is not None:
        await app.push_screen_wait(MessageScreen(TITLE, t('Administrator saved. Sign in with the e-mail and password you chose.')))


async def help(app):
    data = await call(app, 'status')
    if data is None:
        return
    url = origin(data.get('url'))
    await app.push_screen_wait(MessageScreen(t('DSpace first steps'), t(
        'Sign in, then create a community and a collection. Deposit a document with its metadata and review its access policy before publishing. Private files require an authorized account.\n\nAdministrator management and diagnosis remain in the DSpace menu. Encrypted individual backups and recovery are in the Backup center. Explicit backup plans and cloud copies are in the shared Backup center. Address/HTTPS and reviewed same-version updates remain in the DSpace menu.') + '\n\n' + url + '/login'))


async def assistant(app):
    data = await call(app, 'setup-status', '--refresh')
    if data is None or data.get('setup') != 'open':
        await help(app)
        return
    if data.get('steps', {}).get('admin') != 'done':
        choice = await app.push_screen_wait(ChoiceScreen(TITLE, t('Create the DSpace administrator now, or leave it for later? This option always remains in DSpace > Administrative access.'), [('now', t('Set up now')), ('later', t('Do it later'))]))
        if choice is None:
            return
        if choice == 'now':
            await admin(app)
        else:
            await call(app, 'setup-mark', 'admin', 'later')
    for step,label,routine in [('public','Configure the repository address and HTTPS now?',address),('backup','Configure an encrypted backup plan and cloud copy now?',plan)]:
        choice=await app.push_screen_wait(ChoiceScreen(TITLE,t(label),[('now',t('Configure now')),('later',t('Do it later'))]))
        if choice is None:return
        if choice=='now':await routine(app)
        else:await call(app,'setup-mark',step,'later')
    choice=await app.push_screen_wait(ChoiceScreen(TITLE,t('Keep the setup reminder? All these actions remain available in the menus.'),[('keep',t('Keep the reminder')),('close',t('Do not remind me again'))]))
    if choice=='close':await call(app,'setup-close')
    await help(app)


async def backup_create(app):
    settings = await call(app, 'backup-settings')
    if settings is None:
        return
    compression = settings.get('compression', 'gz')
    from ..backup_center import DSPACE_CODECS
    if compression not in DSPACE_CODECS:
        await app.push_screen_wait(MessageScreen(TITLE, t('Could not read the backup compression setting.')))
        return
    text = t('Create an encrypted DSpace backup? The repository pauses while PostgreSQL, files and all Solr cores are captured. The existing backup key must already be configured.')
    text += '\n\n' + t('Compression') + ': ' + t(DSPACE_CODECS[compression])
    if not await app.push_screen_wait(ConfirmScreen(TITLE, text)):
        return
    data = await call(app, 'backup-create', '--compression', compression, '--confirm', cancellable=False)
    if data is not None:
        await app.push_screen_wait(MessageScreen(TITLE, t('Encrypted DSpace backup created.'), details=backup_rows(data)))


async def _recovery(app, restore):
    data = await call(app, 'backup-list')
    if data is None: return
    packages = data.get('packages', [])
    if not packages:
        await app.push_screen_wait(MessageScreen(TITLE, t('No encrypted DSpace backup is available yet.')))
        return
    path = await app.push_screen_wait(ChoiceScreen(TITLE, t('Choose a DSpace recovery package'), [(p, p.rsplit('/',1)[-1]) for p in packages]))
    if not path: return
    phrase = await app.push_screen_wait(InputScreen(TITLE, t('Recovery phrase for the existing backup key:'), t('Recovery phrase:'), password=True))
    if not phrase: return
    plan = await call(app, 'backup-plan', path, env={'KEI_BACKUP_PHRASE':phrase}) if restore else {}
    if plan is None: return
    if restore:
        if not await confirm_restore(app, plan, path): return
    elif not await app.push_screen_wait(ConfirmScreen(TITLE, t('Test DSpace recovery in new volumes on an internal network without public ports? The active repository data are kept.'))): return
    result = await call(app, 'backup-restore' if restore else 'backup-test', path, '--confirm',
                        env={'KEI_BACKUP_PHRASE':phrase}, cancellable=False)
    phrase = ''
    if result is not None:
        await show_recovery(app, result, restore)


async def confirm_restore(app, plan, path):
    """Restoring replaces the active data: a plain summary, Back focused."""
    return await app.push_screen_wait(PlanSummaryScreen(
        t('Restore DSpace · Review'), restore_plan_rows(plan, path),
        body=t('Restore DSpace? A safety backup is made first. Recovery is verified in independent volumes before replacing the active data. Old volumes are kept.'),
        details=json.dumps(plan, ensure_ascii=False, indent=2), action=t('Restore'), danger=True))


async def show_recovery(app, result, restore):
    await app.push_screen_wait(MessageScreen(
        TITLE, t('DSpace restored. Check the repository before sharing its address.') if restore
        else t('Recovery test passed. The backup can be restored.'),
        details=restore_rows(result) if restore else test_rows(result)))


async def backup_test(app):
    await _recovery(app, False)


async def backup_restore(app):
    await _recovery(app, True)


def operation_text(action, plan):
    """Describe the decision in operator language; full machine plans remain in the CLI."""
    if action in ('plan-save','plan-disable'):
        data=plan['plan']
        return '\n'.join([t('Platforms: ${names}',names=' + '.join(x.title() if x!='dspace' else 'DSpace' for x in data['members'])),
            t('Local folder: ${folder}',folder=data['destination'].rstrip('/')+'/nexus-'+data['id']),t('Cloud copy: ${where}',where=data.get('remote') or t('Local only')),
            t('Daily time: ${time}',time=data['time'] or t('Off')),t('Keep the newest ${n} successful packages.',n=data['keep']),
            t('The entire package is encrypted. Partial captures and failed uploads never delete the last good copy.'),
            t('Save this plan? No backup runs now.')])
    if action=='address':
        return '\n'.join([t('Current address: ${url}',url=plan['previous_url']),t('New address: ${url}',url=plan['url']),
            t('An encrypted safety backup is tested before the address changes. Repository data and identifiers are preserved.'),
            t('An external proxy must be configured separately.') if plan['external_proxy_manual'] else t('Only the managed repository web configuration changes.'),
            t('The repository pauses during this operation. Continue?')])
    if action=='upgrade':
        return '\n'.join([t('Reviewed update: DSpace 10.1, recipe ${old} to ${new}.',old=plan['from_recipe'],new=plan['to_recipe']),
            t('Database schema and persistent volumes remain unchanged. An encrypted safety backup is verified first.'),
            t('After a successful update, backups made before it (including this safety backup) are refused by recovery on this installation: it requires the exact image matrix. A failed update rolls back automatically.') if plan.get('earlier_backups_restorable_after_update') is False else '',
            t('The repository pauses during this operation. Continue?')])
    if action=='remove':
        return '\n'.join([t('Keep all repository data and configuration.') if plan['keep_data'] else t('Erase the active owned repository volumes after verifying a safety backup. Backups and earlier recovery volumes remain.'),
            t('Plans containing DSpace are disabled. Plans of the other platforms remain unchanged.'),
            t('Shared Docker, Apache, tunnel and cloud connections remain. Continue?')])
    return t('Apply the reviewed operation?')


async def operation(app, action, request, destructive=False):
    env={'KEI_DSPACE_OPERATIONS_DATA':json.dumps(request)}
    plan=await call(app,'operations',action,env=env)
    if plan is None:return None
    if plan.get('external_proxy_snippet'):
        await app.push_screen_wait(MessageScreen(TITLE,t('Add this snippet to the existing TLS site of the chosen domain, then verify its syntax. Existing proxy files and certificates are not modified by the panel.'),command=plan['external_proxy_snippet'],is_command=False))
    if not await app.push_screen_wait(ConfirmScreen(TITLE,operation_text(action,plan),danger=destructive)):return None
    if action in ('address','upgrade') or (action=='remove' and request.get('purge')):
        phrase=await app.push_screen_wait(InputScreen(TITLE,t('The safety backup will be tested before applying this change. Enter the recovery phrase:'),t('Recovery phrase:'),password=True))
        if not phrase:return None
        env['KEI_BACKUP_PHRASE']=phrase
    result=await call(app,'operations',action,'--confirm',env=env,cancellable=False)
    if result is not None:
        app.check_platforms()
        detail = result.get('safety_backup') or result.get('package') or ''
        await app.push_screen_wait(MessageScreen(TITLE,t('Operation completed. Check the repository before sharing its address.') + ('\n\n'+str(detail) if detail else '')))
    return result


async def plan(app):
    from ..backup_center import MEMBERS
    from ..screens.files import PathPickerScreen
    selected=list(MEMBERS.get(getattr(app,'backup_scope','dspace'),('dspace',)))
    if 'dspace' not in selected:selected=['dspace']
    data=await call(app,'operations','plans')
    if data is None:return
    options=[('new',t('Create an explicit backup plan'))]+[(p['id'],p['id']+' · '+','.join(p['members'])) for p in data.get('plans',[])]
    chosen=await app.push_screen_wait(ChoiceScreen(TITLE,t('Choose a plan. Editing never widens existing Koha/Tainacan schedules.'),options))
    if not chosen:return
    old=next((p for p in data.get('plans',[]) if p['id']==chosen),{})
    if old:
        how=await app.push_screen_wait(ChoiceScreen(TITLE,t('Edit this plan or disable its schedule? Disabling works even when a cloud connection or destination is unavailable.'),[('edit',t('Edit plan')),('off',t('Disable this schedule'))]))
        if not how:return
        if how=='off':
            await operation(app,'plan-disable',{'id':chosen})
            return
    from . import platforms as tn
    if not (await tn.backup_state(app)).key:
        if not await app.push_screen_wait(ConfirmScreen(TITLE,t('DSpace backups require encryption. Configure the shared backup key now?'))):return
        await tn.backup_setup(app)
        if not (await tn.backup_state(app)).key:return
    name=old.get('id') or await app.push_screen_wait(InputScreen(TITLE,t('Name for this backup plan (lowercase letters, digits and hyphens).'),t('Plan name:'),validate=lambda v:'' if re.fullmatch(r'[a-z][a-z0-9-]{0,31}',v) else t('Invalid plan name.')))
    if not name:return
    folder=await app.push_screen_wait(PathPickerScreen(TITLE,old.get('destination','/var/backups'),mode='dir',help_text=t('Choose a server backup folder. A private subfolder is created for this plan.')))
    if not folder:return
    when=await app.push_screen_wait(InputScreen(TITLE,t('Daily server time HH:MM; empty disables this schedule.'),t('Time:'),value=old.get('time','02:30')))
    if when is None:return
    keep=await app.push_screen_wait(InputScreen(TITLE,t('Number of successful encrypted packages to keep (1 to 365).'),t('Retention:'),value=str(old.get('keep',7)),validate=lambda v:'' if v.isdigit() and 1<=int(v)<=365 else t('Choose 1 to 365.')))
    if keep is None:return
    from .. import cloud
    remotes=cloud.parse_remotes((await app.bridge.task('cloud-list')).lists.get('remote',[])) if app.bridge.has_task('cloud-list') else []
    remote=await app.push_screen_wait(ChoiceScreen(TITLE,t('Cloud copy (connections are managed in the shared Backup center).'),[('',t('Local only'))]+[(r.name,r.name) for r in remotes]))
    if remote is None:return
    target=''
    if remote:
        sub=await app.push_screen_wait(InputScreen(TITLE,t('Separate folder for this encrypted plan in the cloud.'),t('Cloud folder:'),value='KohaNexus/'+name))
        if not sub:return
        target=remote+':'+sub
    await operation(app,'plan-save',dict(id=name,members=old.get('members',selected),time=when,keep=int(keep),destination=str(folder),remote=target))


async def plan_run(app):
    data=await call(app,'operations','plans')
    if data is None:return
    chosen=await app.push_screen_wait(ChoiceScreen(TITLE,t('Run a configured backup plan now?'),[(p['id'],p['id']+' · '+','.join(p['members'])) for p in data.get('plans',[])])) if data.get('plans') else None
    if not chosen:return
    if not await app.push_screen_wait(ConfirmScreen(TITLE,t('Capture the explicitly selected platforms, encrypt the package and copy it to the configured cloud destination? Each platform pauses separately.'))):return
    result=await call(app,'operations','plan-run','--confirm',env={'KEI_DSPACE_OPERATIONS_DATA':json.dumps({'id':chosen})},cancellable=False)
    if result:await app.push_screen_wait(MessageScreen(TITLE,t('Encrypted backup created: ${file}',file=result.get('file',''))))


async def address(app):
    mode=await app.push_screen_wait(ChoiceScreen(TITLE,t('How will this repository be published?'),[('apache',t('Local network or institutional HTTP')),('external',t('Existing external HTTPS proxy')),('tls',t('Apache HTTPS with an existing certificate')),('free',t('Free koha.nexus address')),('free-off',t('Release only the repository free address'))]))
    if not mode:return
    from . import platforms as tn
    if not (await tn.backup_state(app)).key:
        if not await app.push_screen_wait(ConfirmScreen(TITLE,t('An address change needs a verified encrypted safety backup. Configure the shared backup key now?'))):return
        await tn.backup_setup(app)
        if not (await tn.backup_state(app)).key:return
    if mode in ('free','free-off'):
        from .common import run_interactive
        await run_interactive(app,TITLE,'dspace-free','off' if mode=='free-off' else 'on')
        app.check_platforms()
        return
    url=await app.push_screen_wait(InputScreen(TITLE,t('Canonical public repository address, without a path.'),t('Address:'),validate=lambda v:'' if origin(v) else t('Enter one HTTP(S) origin.')))
    if not url:return
    request=dict(url=url,mode=mode)
    if mode=='external':
        proxy=await app.push_screen_wait(ChoiceScreen(TITLE,t('Existing external proxy:'),[('nginx','Nginx'),('caddy','Caddy')]))
        if not proxy:return
        request['proxy']=proxy
    if mode=='tls':
        for key,label in [('certificate','Certificate PEM path:'),('key','Private key PEM path:')]:
            path=await app.push_screen_wait(InputScreen(TITLE,t('Use the certificate already managed for this institution. The panel does not publish or request certificates automatically.'),t(label)))
            if not path:return
            request[key]=path
    await operation(app,'address',request,True)


async def languages(app):
    from ..screens.dialogs import ChecklistScreen
    request={'panel_language':getattr(getattr(app,'env',None),'lang','en')}
    env={'KEI_DSPACE_OPERATIONS_DATA':json.dumps(request)}
    data=await call(app,'operations','languages',env=env)
    if data is None:return
    options=[(row['code'],row['label'],row['code'] in data['active']) for row in data['available']]
    active=await app.push_screen_wait(ChecklistScreen(TITLE,t('These translations are already included in the installed image. Choose the languages available to visitors.'),options))
    if active is None:return
    if not active:
        app.notify(t('Keep at least one language active.'),severity='warning');return
    labels={row['code']:row['label'] for row in data['available']}
    suggestion=data['suggested'] if data['suggested'] in active else data['fallback'] if data['fallback'] in active else active[0]
    ordered=[suggestion]+[code for code in active if code!=suggestion]
    fallback=await app.push_screen_wait(ChoiceScreen(TITLE,t('Fallback language. Visitors keep their own saved or browser preference when available. The first suggestion follows the panel language.'),[(code,labels[code]) for code in ordered]))
    if fallback is None:return
    env={'KEI_DSPACE_OPERATIONS_DATA':json.dumps(dict(active=active,fallback=fallback))}
    plan=await call(app,'operations','language-save',env=env)
    if plan is None:return
    question = t('DSpace is stopped. Save these languages for its next start without starting any service?') if plan.get('pending_start') else t('Apply these languages and restart only the DSpace interface? Existing accounts, repository data, domains and schedules are kept.')
    if not await app.push_screen_wait(ConfirmScreen(TITLE,question+'\n\n'+', '.join(labels[c] for c in active)+'\n'+labels[fallback])):return
    if isinstance(plan.get('revision'),str):
        env={'KEI_DSPACE_OPERATIONS_DATA':json.dumps(dict(active=active,fallback=fallback,expected_revision=plan['revision']))}
    result=await call(app,'operations','language-save','--confirm',env=env,cancellable=False)
    if result is not None:
        message=t('Languages saved for the next DSpace start. Services remain stopped.') if result.get('pending_start') else t('Languages saved and the DSpace interface restarted.')
        await app.push_screen_wait(MessageScreen(TITLE,message))


async def upgrade(app):
    from ..screens.files import PathPickerScreen
    mode=await app.push_screen_wait(ChoiceScreen(TITLE,t('Use the current reviewed image recipe, preserving the repository and verifying a safety backup before replacing images.'),[('prepare',t('Prepare the reviewed images on this server')),('catalog',t('Choose an existing reviewed image catalog'))]))
    if mode is None:return
    if mode=='prepare':
        if not await app.push_screen_wait(ConfirmScreen(TITLE,t('Build the reviewed update images? This can take 30–90 minutes or longer. Current repository images and data remain until the separate update plan is confirmed.'))):return
        prepared=await call(app,'prepare-upgrade-images','--confirm',cancellable=False)
        if prepared is None:return
        if prepared.get('already_current'):
            await app.push_screen_wait(MessageScreen(TITLE,t('The repository already uses the current reviewed image recipe.')));return
        path=prepared['catalog']
    else:
        path=await app.push_screen_wait(PathPickerScreen(TITLE,'/etc/koha-nexus',mode='file',suffixes=('.json',),help_text=t('Choose the reviewed image catalog for this update. Database migrations are not performed.')))
    if path:await operation(app,'upgrade',{'catalog':str(path)},True)


async def remove(app):
    from .. import names
    # Its visible name (U6): said in the title and typed to erase its data.
    name=names.custom(names.of(app),'dspace')
    title=t('Remove “${name}” (DSpace)',name=name) if name else TITLE
    choice=await app.push_screen_wait(ChoiceScreen(title,t('Remove only DSpace. Shared Docker, Apache, tunnel and cloud connections remain.'),[('keep',t('Keep all repository data (recommended)')),('purge',t('Erase owned repository volumes after a verified safety backup'))]))
    if not choice:return
    request={'purge':choice=='purge'}
    if choice=='purge':
        if name:
            typed=await app.push_screen_wait(InputScreen(title,t('Type the name “${name}” to confirm permanent removal of its data.',name=name),t('Confirmation:')))
            if (typed or '').strip()!=name:return
            erase='DSpace'        # the installer's own confirmation word, unchanged
        else:
            erase=await app.push_screen_wait(InputScreen(TITLE,t('Type DSpace to confirm permanent removal of its data.'),t('Confirmation:')))
            if erase!='DSpace':return
        request['erase']=erase
    await operation(app,'remove',request,True)


async def restore_path(app,path,show=True):
    """show=False inside a whole-set restore, which reports at its end."""
    phrase=await app.push_screen_wait(InputScreen(TITLE,t('DSpace always requires the recovery phrase; it cannot recover encrypted data without it.'),t('Recovery phrase:'),password=True))
    if not phrase:return False
    env={'KEI_BACKUP_PHRASE':phrase}
    plan=await call(app,'backup-plan',path,env=env)
    if plan is None:return False
    if not await confirm_restore(app,plan,path):return False
    result=await call(app,'backup-restore',path,'--confirm',env=env,cancellable=False)
    if result is None:return False
    if show:await show_recovery(app,result,True)
    return True
