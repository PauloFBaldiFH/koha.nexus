"""Apply one confirmed schedule through its existing writer."""
from __future__ import annotations

import json
from .. import cron
from ..i18n import t
from ..schedule_controls import checksum
from ..bridge import TaskOutcome
from .common import run_task, show_done


async def apply(app, control, values):
    title = t('Schedules')
    when = values['time'] if values['enabled'] else 'off'
    if control.driver == 'koha':
        text = control.koha_text(values)
        path = cron.write_temp(text)
        try:
            result = await run_task(app, title, 'cron-apply', str(path), checksum(control.original))
        finally:
            path.unlink(missing_ok=True)
    elif control.driver == 'tainacan':
        result = await run_task(app, title, 'platform-backup-schedule', 'tainacan', when, checksum(control.original))
    elif control.driver == 'set':
        result = await run_task(app, title, 'set-schedule', 'time=' + when, 'expected=' + checksum(control.original))
    elif control.driver == 'operations':
        expected = dict(control.plan)
        if values['enabled']:
            request = dict(expected, time=when, expected_plan=expected)
            action = 'plan-save'
        else:
            request = dict(id=expected['id'], expected_plan=expected)
            action = 'plan-disable'
        result = await run_task(app, title, 'dspace-panel', 'operations', action, '--confirm',
                                env={'KEI_DSPACE_OPERATIONS_DATA': json.dumps(request)}, cancellable=False)
    else:
        raise ValueError('Unknown schedule driver')
    await show_done(app, title, result)
    return bool(result.ok and not result.cancelled and isinstance(result.value, TaskOutcome) and result.value.ok)
