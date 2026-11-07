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
        await app.push_screen_wait(MessageScreen(TITLE, t('DSpace needs a reviewed immutable image catalog before installation. No packages were installed.') + '\n\n' + str(available.get('reason', ''))))
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
    current = await call(app, 'status')
    if current is None:
        return
    url = current.get('url') or await app.push_screen_wait(InputScreen(
        TITLE, t('Use this server’s IP and a separate port (for example http://192.168.1.20:8100), or a DNS name already pointing here. Free addresses and managed HTTPS arrive later.'),
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
        await assistant(app)


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
        'Sign in, then create a community and a collection. Deposit a document with its metadata and review its access policy before publishing. Private files require an authorized account.\n\nAdministrator management and diagnosis remain in the DSpace menu. Backups, automated schedules, domain assistance and updates are not available in this experimental release.') + '\n\n' + url + '/login'))


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
    choice = await app.push_screen_wait(ChoiceScreen(TITLE, t('Backups and domain assistance are delivered in subsequent stages. Keep the setup reminder for later? The local repository and administrator remain accessible from their menus.'), [('keep', t('Keep the reminder')), ('close', t('Do not remind me again'))]))
    if choice is None:
        return
    await call(app, 'setup-mark', 'backup', 'later')
    if choice == 'close':
        await call(app, 'setup-close')
    await help(app)


async def backup_create(app):
    if not await app.push_screen_wait(ConfirmScreen(TITLE, t('Create an encrypted DSpace backup? The repository pauses while PostgreSQL, files and all Solr cores are captured. The existing backup key must already be configured.'))):
        return
    data = await call(app, 'backup-create', '--confirm', cancellable=False)
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
    question = ('Restore DSpace? A safety backup is made first. Recovery is verified in independent volumes before replacing the active data. Old volumes are kept.' if restore else 'Test DSpace recovery in new volumes on an internal network without public ports? The active repository data are kept.')
    if not await app.push_screen_wait(ConfirmScreen(TITLE, t(question), danger=restore)): return
    result = await call(app, 'backup-restore' if restore else 'backup-test', path, '--confirm',
                        env={'KEI_BACKUP_PHRASE':phrase}, cancellable=False)
    phrase = ''
    if result is not None:
        await app.push_screen_wait(MessageScreen(TITLE, json.dumps(result, ensure_ascii=False, indent=2)))


async def backup_test(app):
    await _recovery(app, False)


async def backup_restore(app):
    await _recovery(app, True)
