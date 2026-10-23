"""Magic Import: a plain .gz/.xz/... is unpacked only while the disk keeps
MIN_FREE (installer, kei_import/intake.py). No size cap, so a big file
that fits still unpacks; one that would fill the disk stops with ENOSPC
and leaves no partial file."""

import errno
import gzip
import importlib
import re
import sys
from collections import namedtuple

import pytest
from conftest import INSTALLER

Usage = namedtuple("Usage", "total used free")


@pytest.fixture(scope="module")
def intake(tmp_path_factory):
    d = tmp_path_factory.mktemp("kei")
    text = INSTALLER.read_text(encoding="utf-8")
    for m in re.finditer(r'cat > "\$d/((?:kei_import/)?\w+\.py)" <<\'KEIPY\'\n(.*?)\nKEIPY\n', text, re.S):
        f = d / m.group(1)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(m.group(2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(d))
    for name in [n for n in sys.modules if n == "kei_import" or n.startswith("kei_import.")]:
        del sys.modules[name]
    yield importlib.import_module("kei_import.intake")
    sys.path.remove(str(d))


def gz(tmp_path, size):
    p = tmp_path / "records.mrc.gz"
    with gzip.open(p, "wb") as f:
        f.write(b"0" * size)
    return p


def test_unpacks_when_there_is_room(intake, tmp_path, monkeypatch):
    monkeypatch.setattr(intake.shutil, "disk_usage", lambda p: Usage(0, 0, intake.MIN_FREE + (64 << 20)))
    m = intake.Member(str(gz(tmp_path, 5 << 20)), "records.mrc.gz", codec="gz")
    out = m.plain(str(tmp_path / "work"))
    assert (tmp_path / "work" / "plain").is_dir() and open(out, "rb").read() == b"0" * (5 << 20)


def test_stops_before_the_disk_fills(intake, tmp_path, monkeypatch):
    left = [intake.MIN_FREE + (3 << 20)]

    def usage(p):
        return Usage(0, 0, left[0])

    real_copy = intake.copy_keeping_room

    def counting(src, dst, where, display):
        class Dst:
            def write(self, b):
                left[0] -= len(b)
                dst.write(b)
        real_copy(src, Dst(), where, display)

    monkeypatch.setattr(intake.shutil, "disk_usage", usage)
    monkeypatch.setattr(intake, "copy_keeping_room", counting)
    m = intake.Member(str(gz(tmp_path, 20 << 20)), "records.mrc.gz", codec="gz")
    with pytest.raises(OSError) as e:
        m.plain(str(tmp_path / "work"))
    assert e.value.errno == errno.ENOSPC and "records.mrc.gz" in str(e.value)
    assert list((tmp_path / "work" / "plain").iterdir()) == []
    assert m._plain is None
