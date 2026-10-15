import subprocess

from koha_nexus_win.wsl import CREATE_NO_WINDOW, WslRunner, decode_wsl, distro_names


def test_decode_utf16_and_utf8():
    assert decode_wsl("koha\r\nUbuntu\r\n".encode("utf-16-le")) == "koha\r\nUbuntu\r\n"
    assert decode_wsl(b"\xff\xfe" + "koha\n".encode("utf-16-le")) == "koha\n"
    assert decode_wsl("Instala\u00e7\u00e3o\n".encode("utf-8")) == "Instala\u00e7\u00e3o\n"
    assert decode_wsl(b"") == ""


def test_distro_names():
    assert distro_names("koha\r\n\r\n Ubuntu-22.04 \r\n") == ["koha", "Ubuntu-22.04"]


class FakeRun:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        code, out = self.replies.get(tuple(argv[1:]), (0, b""))
        return subprocess.CompletedProcess(argv, code, out, b"")


def test_running_never_starts_the_distro_and_hides_the_console():
    run = FakeRun({("--list", "--running", "--quiet"): (0, "Ubuntu\r\n".encode("utf-16-le")),
                   ("--list", "--quiet"): (0, "koha\r\nUbuntu\r\n".encode("utf-16-le"))})
    r = WslRunner(run=run, exe="wsl.exe")
    assert r.installed() is True
    assert r.running() is False
    for argv, kw in run.calls:
        assert "-d" not in argv
        assert kw["creationflags"] == CREATE_NO_WINDOW
        assert kw["env"]["WSL_UTF8"] == "1"


def test_verb_runs_koha_panel_as_root():
    run = FakeRun({("-d", "koha", "-u", "root", "--", "/usr/local/bin/koha-panel", "--status-json"): (0, b'{"schema":1}\n')})
    r = WslRunner(run=run, exe="wsl.exe")
    res = r.verb(["--status-json"], timeout=60)
    assert (res.code, res.out) == (0, '{"schema":1}\n')
    assert run.calls[0][1]["timeout"] == 60


def test_a_failing_wsl_reads_as_not_there():
    def boom(argv, **kw):
        raise FileNotFoundError("wsl.exe")
    r = WslRunner(run=boom, exe="wsl.exe")
    assert r.installed() is False and r.running() is False
    assert r.verb(["--status-json"]).code == -1
    r2 = WslRunner(run=FakeRun({("--list", "--quiet"): (1, b"")}), exe="wsl.exe")
    assert r2.installed() is False
