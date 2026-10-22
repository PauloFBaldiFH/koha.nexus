"""Freeze the two proven binary readers during the generic import upgrade.

These digests cover source code only, never uploaded catalog/patron data.
Behavioral coverage remains in tests/magic_import.bats and the reader suites.
"""

import hashlib
import re

import pytest

from conftest import INSTALLER


@pytest.mark.parametrize("function, expected", [
    ("isis_write_reader", "9b0f6214202fd75b94183653fccb26a24aeb35c269fccdcc40975b7c7c787ceb"),
    ("bf_write_dbreader", "8784dd01483c358b827d378accfa437965f639ade66b4f82a171ef02c0982cd0"),
])
def test_proven_binary_reader_source_is_unchanged(function, expected):
    source = INSTALLER.read_text(encoding="utf-8")
    tail = source[source.index(function + "()") :]
    marker = re.search(r"<<'([^']+)'\n", tail)
    body = tail[marker.end():].split("\n" + marker[1] + "\n", 1)[0]
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == expected
