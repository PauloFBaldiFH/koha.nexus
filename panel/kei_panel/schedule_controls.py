"""Editable views of existing schedules; no second schedule store."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import re
from . import cron, schedules
from .i18n import t


class EditError(ValueError):
    pass


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass
class Control:
    row: schedules.Row
    driver: str
    time: str = '02:30'
    freq: str = 'daily'
    day: int = 0
    raw: str = ''
    original: str = ''
    job: cron.Job | None = None
    plan: dict | None = None
    enabled: bool = False
    available: bool = True
    note: str = ''
    out_of_sync: bool = False

    @property
    def frequencies(self):
        if self.driver != 'koha':
            return ('daily',)
        preset = cron.BY_KEY.get(self.job.key)
        values = preset.freqs if preset else tuple(cron.FREQS)
        return tuple(dict.fromkeys((*values, self.freq)))

    def values(self):
        return dict(enabled=self.enabled, freq=self.freq, time=self.time, day=self.day, raw=self.raw)

    def edited(self, values):
        if type(values.get('enabled')) is not bool or values.get('freq') not in self.frequencies:
            raise EditError('Choose a supported frequency.')
        if not values['enabled']:
            return dict(self.values(), enabled=False) # disable even if an unused time field is invalid
        freq = values['freq']
        if freq == 'custom':
            raw = ' '.join(str(values.get('raw', '')).split())
            problem = cron.schedule_problem(raw)
            if problem: raise EditError(problem)
            return dict(self.values(), enabled=True, freq=freq, raw=raw)
        hm = cron.parse_time(str(values.get('time', '')))
        if hm is None: raise EditError('Use HH:MM (00:00 to 23:59).')
        day = values.get('day', 0)
        if type(day) is not int or (freq == 'weekly' and not 0 <= day <= 6) or (freq == 'monthly' and not 1 <= day <= 31):
            raise EditError('Choose a valid day.')
        return dict(enabled=True, freq=freq, time=f'{hm[0]:02d}:{hm[1]:02d}', day=day if freq in ('weekly','monthly') else 0, raw='')

    def koha_text(self, values):
        """Replace one identified line, preserving all other bytes and manual blocks."""
        if not self.job or not self.job.key:
            raise EditError('This task is read-only.')
        old = self.job
        new = replace(old, enabled=values['enabled'], freq=values['freq'], day=values['day'], raw=values['raw'])
        if values['freq'] != 'custom': new.hour, new.minute = cron.parse_time(values['time'])
        lines = self.original.splitlines(keepends=True)
        matches = []
        in_block = False
        for i, line in enumerate(lines):
            if line.startswith('# BEGIN '): in_block = True
            if line.startswith('# END '): in_block = False; continue
            if in_block: continue
            text = line.strip()
            if text.startswith(cron.OFF.strip()): text = text[len(cron.OFF.strip()):].strip()
            match = cron._LINE.fullmatch(text)
            if match and match['sched'] == old.schedule() and match['user'] == old.user and match['cmd'].strip() == old.command:
                matches.append(i)
        if len(matches) != 1: raise EditError('This task is ambiguous. Open its original editor.')
        i = matches[0]
        ending = '\r\n' if lines[i].endswith('\r\n') else '\n' if lines[i].endswith('\n') else ''
        lines[i] = ('' if new.enabled else cron.OFF) + f'{new.schedule()} {new.user} {cron.run_command(new)}' + ending
        result = ''.join(lines)
        problem = cron.file_problem(result)
        if problem: raise EditError(problem)
        return result


def managed_file(text, driver, name=""):
    """Do not let a group writer discard cron lines it does not own."""
    expressions = {
        'tainacan': r'\S+ --task platform-backup-(?:run tainacan scheduled|maintain tainacan|verify tainacan 30) >/dev/null 2>&1',
        'set': r'\S+ --task set-run scheduled >/dev/null 2>&1',
        'operations': r'''KEI_DSPACE_OPERATIONS_DATA='\{"id":"'''+re.escape(name)+r'''"\}' \S+ --task dspace operations plan-run --confirm >/dev/null 2>&1''',
    }
    for line in text.splitlines():
        raw = line.strip()
        if not raw: continue
        if raw.startswith('#') and not raw.startswith(cron.OFF.strip()): continue
        if raw in ('SHELL=/bin/bash', 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'): continue
        match = cron._LINE.fullmatch(raw)
        if not match or match['user'] != 'root' or not re.fullmatch(expressions[driver], ' '.join(match['cmd'].split())):
            return False
    return True


def controls(rows, files, instance, *, tainacan=None, joint=None, plans=()):
    """Return controls and virtual OFF rows for configured schedules with no cron file."""
    result = {}
    original = files.get(schedules.TASKS_FILE, '')
    jobs = cron.parse(original, instance).jobs if original else []
    for row in rows:
        if row.source != schedules.TASKS_FILE or not row.key.startswith('koha:'): continue
        key = row.key[len('koha:'):]
        matches = [j for j in jobs if j.key == key]
        same_rows = [r for r in rows if r.source == row.source and r.key == row.key]
        if len(matches) != 1 or len(same_rows) != 1: continue
        job = matches[0]
        control = Control(row, 'koha', job.time(), job.freq, job.day, job.raw, original, job, enabled=job.enabled)
        try: control.koha_text(control.values())
        except EditError: continue
        result[id(row)] = control

    def primary(key, platform, name, source, state, driver, note):
        candidates = [r for r in rows if r.key == key]
        if len(candidates) > 1: return
        row = candidates[0] if candidates else schedules.Row(platform, schedules.BACKUP, t(name), schedules.describe('30 2 * * *'), 'off', source, editor=schedules.screen('backups'), key=key)
        if not candidates: rows.append(row)
        hour = state.get('schedule') or '02:30'
        consistent = True
        if candidates:
            job = cron.Job('', '', '')
            cron._from_schedule(job, row.sched)
            consistent = bool(state.get('schedule')) == (row.state == 'on') and job.freq == 'daily' and job.time() == hour
        elif state.get('schedule'):
            note += ' ' + 'The configured cron entry is missing. Enable and save to recreate it.'
        result[id(row)] = Control(row, driver, time=hour, original=files.get(source, ''), enabled=row.state == 'on', available=state.get('known', True) and consistent and managed_file(files.get(source, ''), driver), note=note, out_of_sync=not candidates and bool(state.get('schedule')))

    if tainacan is not None:
        primary('tainacan:run', 'tainacan', 'Backup', schedules.PLATFORM_FILE, tainacan, 'tainacan',
                'This also schedules weekly maintenance one hour later and a monthly restore test two hours later. All three are disabled together.')
    if joint is not None and joint.get('dest'):
        primary('set:run', schedules.BOTH, 'Joint backup (Koha + Tainacan)', schedules.SET_FILE, joint, 'set',
                'Only the schedule changes. Destination, retention and cloud copy are kept.')
    for plan in plans:
        if not isinstance(plan, dict): continue
        name = plan.get('id', '')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',name): continue
        key = 'operations:koha-nexus-plan-' + name
        candidates = [r for r in rows if r.key == key]
        if len(candidates) > 1: continue
        row = candidates[0] if candidates else schedules.Row('+'.join(plan.get('members', [])), schedules.BACKUP,
            t('Encrypted platform backup') + ' · ' + name, '', 'off', 'koha-nexus-plan-' + name, editor=schedules.screen('backups'), key=key)
        if not candidates: rows.append(row)
        available = managed_file(files.get(row.source, ''), 'operations', name)
        if candidates:
            job = cron.Job('', '', '')
            cron._from_schedule(job, row.sched)
            available = available and job.freq == 'daily' and job.time() == plan.get('time')
        result[id(row)] = Control(row, 'operations', time=plan.get('time') or '02:30', enabled=row.state == 'on', available=available, out_of_sync=not candidates and bool(plan.get('time')),
            plan={k:v for k,v in plan.items() if k != 'last'}, note='Only the schedule changes. Participants, destination, retention and cloud copy are kept.')
    return result
