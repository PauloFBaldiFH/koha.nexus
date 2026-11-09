"""DSpace's existing lifecycle adapter through the normal panel task bridge."""
from __future__ import annotations

import json
import re

from ..bridge import TaskOutcome
from ..dspace import origin, payload
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
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


async def install(app):
    available = await call(app, 'availability')
    if available is None:
        return
    if not available.get('available'):
        await app.push_screen_wait(MessageScreen(TITLE, t('DSpace image configuration could not be used.') + '\n\n' + str(available.get('reason', ''))))
        return
    from .platforms import install_docker
    status = await app.bridge.status()
    if not (status.get('docker') or {}).get('installed'):
        if not await install_docker(app):
            return
        status = await app.bridge.status()
        if not (status.get("docker") or {}).get("installed"):
            return
    # Re-read prerequisites; closing any confirmation never continues installing.
    pre = await run_task(app, TITLE, 'dspace-prerequisites', 'plan')
    out = pre.value if isinstance(pre.value, TaskOutcome) else None
    if pre.cancelled or not pre.ok or out is None or not out.ok:
        await show_failure(app, TITLE, pre)
        return
    deps = payload(out)
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
                'Prepare the experimental DSpace images on this server? This downloads the pinned sources and builds backend, interface and Solr. It can take 30–90 minutes or longer, uses additional disk and memory, and installs Git if missing. Existing Koha/Tainacan data are preserved. You can retry if preparation fails.'))):
            return
        if await call(app, 'prepare-images', '--confirm', cancellable=False) is None:
            return
    current = await call(app, 'status')
    if current is None:
        return
    url = current.get('url')
    if not url and deps.get('platform') in ('wsl1', 'wsl2'):
        access = await app.push_screen_wait(ChoiceScreen(TITLE,
            t('Where will you open DSpace? On Windows/WSL, localhost avoids depending on LAN forwarding. Network access needs the real Windows IP and its network setup.'),
            [('local', t('This computer only (localhost)')), ('network', t('Other computers or an institutional domain'))]))
        if access is None:
            return
        if access == 'local':
            url = 'http://localhost:8100'
    url = url or await app.push_screen_wait(InputScreen(
        TITLE, t('Use this server’s IP and a separate port (for example http://192.168.1.20:8100), or a DNS name already pointing here. Address and HTTPS assistance remains available after installation.'),
        t('Repository address:'), validate=lambda v: '' if origin(v) else t('Enter one HTTP(S) address without credentials or a path.')))
    if not url:
        return
    plan = await call(app, 'plan', '--url', url)
    if plan is None:
        return
    text = t('Review the DSpace installation plan. Only its own resources are created; existing repository data are preserved.') + '\n\n' + json.dumps(plan, ensure_ascii=False, indent=2)
    if not await app.push_screen_wait(ConfirmScreen(TITLE, text)):
        return
    # A migration retry is a second, explicit decision, never implied by resume.
    retry = []
    if current.get('migration') in ('running', 'failed'):
        if not await app.push_screen_wait(ConfirmScreen(TITLE, t('An earlier database migration was interrupted or failed. Review the diagnosis and preserved data before another attempt. Explicitly retry the migration?'), danger=True)):
            return
        retry = ['--retry-migration']
    result = await call(app, 'install', '--url', url, '--confirm', *retry)
    if result is not None:
        app.check_platforms()
        if isinstance(result.get('note'), str) and result['note']:
            await app.push_screen_wait(MessageScreen(TITLE, t(result['note'])))
        await app.push_screen_wait(MessageScreen(TITLE, t("DSpace is installed. Administrative access, addresses and backups are available in the menus.") + '\n\n' + origin(result.get('url', url)) + '/login'))


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
        await app.push_screen_wait(MessageScreen(t('DSpace diagnosis'), json.dumps(data, ensure_ascii=False, indent=2)))


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
    if not await app.push_screen_wait(ConfirmScreen(TITLE,
            t('Review web repair. Configuration is saved for rollback; database, files, images and schedules are preserved.') + '\n\n' + json.dumps(plan, ensure_ascii=False, indent=2))):
        return
    result = await call(app, 'operations', 'repair-web', '--confirm', env=env, cancellable=False)
    if result is not None:
        app.check_platforms()
        await app.push_screen_wait(MessageScreen(TITLE, t('Web access repaired. Open the address shown in the dashboard.') + '\n\n' + origin(result.get('url', plan.get('url', ''))) + '/login'))


async def admin(app):
    data = await call(app, 'admin-status', cancellable=False)
    if data is None:
        return
    emails = [v for v in data.get('admins', []) if isinstance(v, str) and len(v) <= 254 and EMAIL.fullmatch(v)]
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
        language = await app.push_screen_wait(ChoiceScreen(TITLE, t('Account language'), [('pt_BR', 'Português'), ('en', 'English'), ('es', 'Español')]))
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
        await app.push_screen_wait(MessageScreen(TITLE, str(data.get('package', ''))))


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
    question = ('Restore DSpace? A safety backup is made first. Recovery is verified in independent volumes before replacing the active data. Old volumes are kept.' if restore else 'Test DSpace recovery in new volumes on an internal network without public ports? The active repository data are kept.')
    if not await app.push_screen_wait(ConfirmScreen(TITLE, t(question) + ('\n\n' + json.dumps(plan,ensure_ascii=False,indent=2) if restore else ''), danger=restore)): return
    result = await call(app, 'backup-restore' if restore else 'backup-test', path, '--confirm',
                        env={'KEI_BACKUP_PHRASE':phrase}, cancellable=False)
    phrase = ''
    if result is not None:
        await app.push_screen_wait(MessageScreen(TITLE, json.dumps(result, ensure_ascii=False, indent=2)))


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


async def upgrade(app):
    from ..screens.files import PathPickerScreen
    path=await app.push_screen_wait(PathPickerScreen(TITLE,'/etc/koha-nexus',mode='file',suffixes=('.json',),help_text=t('Choose the reviewed immutable image catalog for the recipe 3 to 4 update. Other migrations are refused.')))
    if path:await operation(app,'upgrade',{'catalog':str(path)},True)


async def remove(app):
    choice=await app.push_screen_wait(ChoiceScreen(TITLE,t('Remove only DSpace. Shared Docker, Apache, tunnel and cloud connections remain.'),[('keep',t('Keep all repository data (recommended)')),('purge',t('Erase owned repository volumes after a verified safety backup'))]))
    if not choice:return
    request={'purge':choice=='purge'}
    if choice=='purge':
        erase=await app.push_screen_wait(InputScreen(TITLE,t('Type DSpace to confirm permanent removal of its data.'),t('Confirmation:')))
        if erase!='DSpace':return
        request['erase']=erase
    await operation(app,'remove',request,True)


async def restore_path(app,path):
    phrase=await app.push_screen_wait(InputScreen(TITLE,t('DSpace always requires the recovery phrase; it cannot recover encrypted data without it.'),t('Recovery phrase:'),password=True))
    if not phrase:return False
    env={'KEI_BACKUP_PHRASE':phrase}
    plan=await call(app,'backup-plan',path,env=env)
    if plan is None:return False
    if not await app.push_screen_wait(ConfirmScreen(TITLE,json.dumps(plan,ensure_ascii=False,indent=2),danger=True)):return False
    return await call(app,'backup-restore',path,'--confirm',env=env,cancellable=False) is not None
