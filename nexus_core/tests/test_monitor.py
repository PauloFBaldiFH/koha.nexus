from nexus_core.tests.fixtures import status_json
from nexus_core.alerts import DiskHealth
from nexus_core.monitor import HealthMonitor
from nexus_core.ports import RunResult

NOW = 1_800_000_000


class FakeRunner:
    def __init__(self, installed=True, running=True, out=None, code=0):
        self._installed, self._running = installed, running
        self.out = status_json() if out is None else out
        self.code = code
        self.calls = []

    def installed(self):
        return self._installed

    def running(self):
        return self._running

    def verb(self, args, timeout=30):
        self.calls.append(list(args))
        return RunResult(self.code, "starting the panel...\n" + self.out)


class FakeNotifier:
    def __init__(self):
        self.shown = []

    def notify(self, title, text, level="info"):
        self.shown.append((level, title))
        return "log"


class MemoryStore:
    def __init__(self, **saved):
        self.saved = dict(saved)

    def load(self):
        return dict(self.saved)

    def save(self, changes):
        self.saved.update(changes)


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


def monitor(runner, store, clock=None, **kw):
    clock = clock or Clock(NOW + 1000)
    m = HealthMonitor(runner, FakeNotifier(), store, clock=clock, **kw)
    return m


def test_running_koha_is_read_through_status_json():
    runner = FakeRunner()
    m = monitor(runner, MemoryStore(desired="running", lastBackupLogEpoch=NOW))
    r = m.check()
    assert r.status.state == "running"
    assert r.status.linux.service("apache2") == "active"
    assert runner.calls == [["--status-json"]]
    assert m.store.saved["lastState"] == "running"


def test_a_stopped_distro_is_never_asked_anything():
    runner = FakeRunner(running=False)
    clock = Clock(NOW)
    m = monitor(runner, MemoryStore(desired="running"), clock=clock)
    clock.now = NOW + 120
    assert m.check().status.state == "stopped"
    assert runner.calls == []


def test_the_monitor_start_is_a_grace_period():
    clock = Clock(NOW)
    m = monitor(FakeRunner(running=False), MemoryStore(desired="running"), clock=clock)
    assert m.status().state == "starting"
    clock.now = NOW + 46
    assert m.status().state == "stopped"


def test_a_one_off_look_has_only_the_boot_grace():
    clock = Clock(NOW)               # the computer booted 10 s before NOW
    m = monitor(FakeRunner(running=False), MemoryStore(desired="running"), clock=clock,
                uptime_ms=lambda: (clock.now - NOW + 10) * 1000, start_grace=False)
    clock.now = NOW + 30             # 40 s after boot
    assert m.status().state == "starting"
    clock.now = NOW + 40             # 50 s after boot
    assert m.status().state == "stopped"
    m2 = monitor(FakeRunner(running=False), MemoryStore(desired="running"), clock=clock, start_grace=False)
    assert m2.status().state == "stopped"


def test_a_failed_status_verb_reads_as_not_responding():
    clock = Clock(NOW)
    m = monitor(FakeRunner(code=1), MemoryStore(desired="running"), clock=clock)
    clock.now = NOW + 600
    assert m.status().state == "not_responding"
    m2 = monitor(FakeRunner(out="garbage"), MemoryStore(desired="running"), clock=clock)
    clock.now = NOW + 1200
    assert m2.status().linux is None


def test_alerts_are_shown_once_and_remembered():
    clock = Clock(NOW)
    runner = FakeRunner(out=status_json(state="degraded"))
    store = MemoryStore(desired="running", lastState="running", lastBackupLogEpoch=NOW)
    m = monitor(runner, store, clock=clock)
    clock.now = NOW + 600
    r = m.check()
    assert [a.title for a in r.alerts] == ["Koha is not responding"]
    assert m.notifier.shown == [("error", "Koha is not responding")]
    assert m.check().alerts == []           # lastState is now not_responding
    runner.out = status_json()
    assert [a.title for a in m.check().alerts] == ["Koha is working again"]


def test_disk_health_is_passed_through():
    m = monitor(FakeRunner(), MemoryStore(desired="running", lastState="running", lastBackupLogEpoch=NOW))
    r = m.check(disk=DiskHealth("low", "8 GB free"))
    assert [a.title for a in r.alerts] == ["Disk space is low"]
    assert m.store.saved["lastDiskLevel"] == "low"
