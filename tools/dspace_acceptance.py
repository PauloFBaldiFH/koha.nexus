"""Public, secret-free phase timings for disposable DSpace acceptance jobs."""
import contextlib
import json
import os
from pathlib import Path
import tempfile
import time

SUITES = ('all', 'lifecycle', 'backup-operations')
COMMON = ('image-preparation', 'installation', 'browser-fixture', 'final-health')
GROUPS = {'lifecycle': ('native-recovery', 'lifecycle-restart', 'web-repair-languages'),
          'backup-operations': ('nexus-full-recovery', 'backup-plans-cloud-address-removal')}


def includes(suite, group):
    if suite not in SUITES or group not in GROUPS:
        raise ValueError('Unknown DSpace acceptance suite.')
    return suite == 'all' or suite == group


def required(suite):
    return COMMON + tuple(phase for group, phases in GROUPS.items() if includes(suite, group) for phase in phases)


class Timings:
    """Write before entering a phase, so abrupt runner termination is visible.

    Only fixed phase names, clocks, statuses and exception class names are
    exported; error messages, arguments and runtime configuration stay out.
    """
    def __init__(self, output, suite):
        if suite not in SUITES:
            raise ValueError('Unknown DSpace acceptance suite.')
        self.path = Path(output) / ('dspace-phase-timings-' + suite + '.json')
        self.suite = suite
        self.phases = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.dspace-timings-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as target:
                json.dump({'schema': 1, 'suite': self.suite, 'phases': self.phases}, target, indent=2)
                target.write('\n'); target.flush(); os.fsync(target.fileno())
                # This deliberately public CI receipt contains no private data.
                os.fchmod(target.fileno(), 0o644)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    @contextlib.contextmanager
    def phase(self, name):
        started = time.monotonic()
        row = {'name': name, 'status': 'running', 'started_at': time.time()}
        self.phases.append(row); self.save()
        print('DSpace acceptance: START ' + name, flush=True)
        try:
            yield
        except BaseException as error:
            row.update(status='failed', error_type=type(error).__name__)
            raise
        else:
            row['status'] = 'passed'
        finally:
            row.update(seconds=round(time.monotonic() - started, 3), finished_at=time.time())
            self.save()
            print('DSpace acceptance: ' + row['status'].upper() + ' ' + name +
                  ' (' + str(row['seconds']) + ' s)', flush=True)

    def require_complete(self):
        missing = [name for name in required(self.suite)
                   if not any(row['name'] == name and row['status'] == 'passed' for row in self.phases)]
        if missing:
            raise RuntimeError('Acceptance did not complete required phases: ' + ', '.join(missing))
