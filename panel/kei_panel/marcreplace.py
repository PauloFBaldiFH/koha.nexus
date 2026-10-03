"""The MARC Replace staff tool, as seen from the AI setup screen.

The page itself (marc_replace.pl, with its "AI cataloguing" tab that reads
vision.conf) is installed by the installer's function_marc_replace; the
panel only tells whether it is there and opens that routine
(`config.sh --task run marc-replace`, its menus as panel screens). An installer older than that action only
knows `library-tools`, whose menu has the same entry (12).
"""

from __future__ import annotations

import os
from pathlib import Path

ACTION = "marc-replace"
FALLBACK_ACTION = "library-tools"
STAFF_URL = "/cgi-bin/koha/tools/marc_replace.pl"
VISION_URL = STAFF_URL + "?op=vision"


def page_file() -> Path:
    cgi = os.environ.get("KOHA_INTRA_CGI") or "/usr/share/koha/intranet/cgi-bin"
    return Path(cgi) / "tools" / "marc_replace.pl"


def installed(demo: bool = False) -> bool:
    return demo or page_file().is_file()


def assistant_installed(demo: bool = False) -> bool:
    """The AI assistant of the staff home page (installer: aia_installed)."""
    return demo or page_file().with_name("ai_assistant.pl").is_file()


def action(bridge) -> str:
    return ACTION if bridge.has_action(ACTION) else FALLBACK_ACTION
