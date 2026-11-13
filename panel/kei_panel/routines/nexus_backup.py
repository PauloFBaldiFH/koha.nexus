"""Portable full Nexus capture and explicit, resumable application recovery."""
from __future__ import annotations

from pathlib import Path

from ..bridge import TaskOutcome
from ..dspace import payload
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from ..screens.files import PathPickerScreen
from .common import facts, run_task, show_failure

TITLE = 'Full Nexus backup'
NOTE = ('One encrypted file with all installed applications, their data and secrets, Nexus settings and container images. '
        'Gzip, Bzip2, XZ or no compression. The recovery key is included protected by your recovery phrase. '
        'Keep that phrase separately. This is an application recovery package, not an operating-system disk image. '
        'Applications are captured in turn, not at the same instant.')
# The Backup center's full backup, in one line (study 7.6, U8); what it
# brings back is the table below, not a paragraph.
SHORT_NOTE = 'One encrypted file with all the systems of this server.'
# What a recovery does with each part of the package (platforms/nexus/
# recovery.py: restore, settings_changes; the capture: installer's
# nexus-full inventory). Kept true to the code: a test checks the roles.
BRINGS_BACK = (
    ('Comes back automatically',
     'the data of Koha, Tainacan and DSpace, each with its own restore checks and safety backup; the backup key; '
     "the panel's look and language; the backup plans, turned off until you set their time"),
    ('Loaded during recovery', 'the container images, included in the file'),
    ('Kept for review, not turned on',
     "the source server's schedules, cloud connections, Cloudflare tunnel files, Docker settings, panel files "
     'and installation names; the destination keeps its own addresses'),
    ('Must be ready on the destination',
     'the same operating system release and architecture; each system installed and empty, with the same Koha '
     'package and the same container images; DSpace with the same release and address'),
    ('Not included', 'the operating system, Windows and WSL, older backup packages, and files kept outside '
     'these systems'),
)
RESTORE_NOTE = ('Prepare compatible empty applications on the destination before restoring: the same OS release and architecture, '
                'the same Koha package, and matching container images. DSpace also requires the same release and repository address. '
                'Each application uses its existing restore checks and safety backup. Recovery is sequential; completed applications '
                'remain recorded if another one fails. Target addresses and existing jobs are preserved. Source jobs, cloud accounts '
                'and publication identities remain private references for review; new recovered backup plans are disabled.')


async def call(app, command, *args, phrase=None, **kwargs):
    env = {'KEI_BACKUP_PHRASE': phrase} if phrase is not None else {}
    result = await run_task(app, t(TITLE), 'nexus-full', command, *map(str, args), env=env, **kwargs)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    if result.cancelled or not result.ok or out is None or not out.ok:
        await show_failure(app, t(TITLE), result)
        return None
    data = payload(out)
    if not data:
        await app.push_screen_wait(MessageScreen(t(TITLE), t('The backup task returned no valid result. See its log before continuing.'), kind='error'))
        return None
    return data


async def pick_file(app):
    info = await facts(app)
    picked = await app.push_screen_wait(PathPickerScreen(t(TITLE), info.get('real_home') or '/root', mode='file',
        suffixes=(), help_text=t('Choose a full Nexus recovery package. Its contents and recovery phrase will be verified.')))
    return str(picked) if picked else None


async def phrase(app):
    return await app.push_screen_wait(InputScreen(t(TITLE), t('Enter the recovery phrase used when the backup key was created. It is not a WordPress or Koha password.'),
        t('Recovery phrase:'), password=True))


def restore_summary(data):
    lines = [t(RESTORE_NOTE), '', t('Applications:') + ' ' + ', '.join(data.get('applications', [])),
             t('Container images:') + ' ' + str(data.get('images', 0))]
    lines += [t('Apply settings:') + ' ' + ', '.join(data.get('settings_to_apply', [])),
              t('Keep privately for review:') + ' ' + ', '.join(data.get('settings_for_review', []))]
    if data.get('completed'):
        lines.append(t('Completed components:') + ' ' + ', '.join(data['completed']))
    if data.get('problems'):
        lines += ['', t('Destination prerequisites:')] + ['• ' + str(v) for v in data['problems']]
    return '\n'.join(lines)


async def create(app):
    from . import platforms
    if not (await platforms.backup_state(app)).key:
        if not await app.push_screen_wait(ConfirmScreen(t(TITLE), t('A full Nexus backup requires the shared backup key. Configure it now?'))):
            return
        await platforms.backup_setup(app)
        if not (await platforms.backup_state(app)).key:
            return
    # Save a current kit before inventory; this is an explicit backup action,
    # never a write caused by opening the center or reading status.
    saved = await run_task(app, t(TITLE), 'platform-backup-kit')
    if not saved.ok or not isinstance(saved.value, TaskOutcome) or not saved.value.ok:
        await show_failure(app, t(TITLE), saved)
        return
    codec = getattr(app, 'nexus_backup_codec', 'gz')
    plan = await call(app, 'plan', '--compression', codec)
    if plan is None:
        return
    info = await facts(app)
    folder = await app.push_screen_wait(PathPickerScreen(t(TITLE), info.get('real_home') or '/root', mode='dir',
        help_text=t('Choose a parent folder. The package is saved in a private nexus-full subfolder.')))
    if folder is None:
        return
    destination = Path(folder) / 'nexus-full'
    text = t(NOTE) + '\n\n' + t('Applications:') + ' ' + ', '.join(plan.get('applications', []))
    text += '\n' + t('Compression') + ': ' + codec + '\n' + t('Destination') + ': ' + str(destination)
    text += '\n' + t('Estimated staging space: ${n} bytes (four times the inventoried data and images).', n=int(plan.get('estimated_source_bytes', 0)) * 4)
    if not await app.push_screen_wait(ConfirmScreen(t(TITLE), text + '\n\n' + t('Create the full recovery package now?'))):
        return
    result = await call(app, 'create', destination, '--compression', codec, '--confirm', cancellable=False)
    if result is not None:
        await app.push_screen_wait(MessageScreen(t(TITLE), t('Full package created. Verify it with the recovery phrase before relying on it.') + '\n\n' + str(result['file']), kind='ok'))


async def verify(app):
    path = await pick_file(app)
    if not path:
        return
    secret = await phrase(app)
    if not secret:
        return
    result = await call(app, 'verify', path, phrase=secret, cancellable=False)
    if result is not None:
        await app.push_screen_wait(MessageScreen(t(TITLE), t('The phrase, encryption and all archived file checksums passed using an isolated keyring. This verifies the package contents; it does not start an application recovery test.') + '\n\n' + ', '.join(result.get('applications', [])), kind='ok'))


async def restore(app):
    path = await pick_file(app)
    if path:
        await restore_path(app, path)


async def restore_path(app, path):
    secret = await phrase(app)
    if not secret:
        return
    data = await call(app, 'open', path, phrase=secret, cancellable=False)
    if data is not None:
        await restore_session(app, data['session'], data, secret)


async def restore_session(app, session, data, secret=None):
    if data.get('phase') == 'complete':
        await app.push_screen_wait(MessageScreen(t(TITLE), t('This recovery session is already complete. Its private reference files are kept here:') + '\n\n' + session))
        return
    if not data.get('compatible'):
        choice = await app.push_screen_wait(ChoiceScreen(t(TITLE), restore_summary(data), [
            ('keep', t('Keep this private session and prepare the destination')),
            ('images', t('Import the archived container images now'))]))
        if choice == 'images' and await app.push_screen_wait(ConfirmScreen(t(TITLE), t('Load the archived immutable images into local Docker? No application is installed, started or restored by this step.'))):
            await call(app, 'load-images', session, '--confirm', cancellable=False)
        return
    if not await app.push_screen_wait(ConfirmScreen(t(TITLE), restore_summary(data) + '\n\n' + t('Restore these applications and the listed settings now?'), danger=True)):
        return
    secret = secret or await phrase(app)
    if not secret:
        return
    result = await call(app, 'restore', session, '--confirm', phrase=secret, cancellable=False)
    if result is None:
        await app.push_screen_wait(MessageScreen(t(TITLE), t('The recovery did not finish. Check the log and use Recovery sessions to review completed components and resume.') + '\n\n' + session, kind='error'))
        return
    app.check_platforms()
    references = result.get('settings', {}).get('reference_directory', session)
    await app.push_screen_wait(MessageScreen(t(TITLE), t('Application recovery finished. Review the recovered source configuration before enabling schedules or publishing addresses.') + '\n\n' + str(references), kind='ok'))


async def sessions(app):
    status = await call(app, 'status')
    if status is None:
        return
    rows = status.get('sessions', [])
    if not rows:
        await app.push_screen_wait(MessageScreen(t(TITLE), t('There are no private recovery sessions. Open a full package to prepare a recovery.')))
        return
    selected = await app.push_screen_wait(ChoiceScreen(t(TITLE), t('Private sessions retain decrypted data as root-only files. Interrupted sessions can resume from the recorded components.'),
        [(row['session'], str(row['phase']) + ' · ' + Path(row['session']).name) for row in rows]))
    if selected is None:
        return
    data = await call(app, 'restore-plan', selected)
    if data is None:
        return
    choices = [('resume', t('Review and continue recovery'))]
    if data.get('phase') in ('opened', 'complete'):
        choices.append(('remove', t('Delete this private staging session')))
    choice = await app.push_screen_wait(ChoiceScreen(t(TITLE), restore_summary(data), choices))
    if choice == 'resume':
        await restore_session(app, selected, data)
    elif choice == 'remove' and await app.push_screen_wait(ConfirmScreen(t(TITLE), t('Delete the decrypted staging and reference files of this session? The encrypted original package and application safety backups are kept.'), danger=True)):
        await call(app, 'cleanup', selected)
