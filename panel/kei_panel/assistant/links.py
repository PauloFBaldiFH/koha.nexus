"""[[kind:id|label]] references: parsing, and rendering as blue links.

render() turns an answer into Textual content markup: a verified
reference becomes blue underlined text whose click runs the widget's
open_ref action; an unverified one (an id no tool returned) stays plain
text, so an invented record is never clickable. Everything else is
escaped: text from the model or from records is never markup.
"""

from __future__ import annotations

import re

from textual.markup import escape

REF = re.compile(r"\[\[(biblio|patron|report|syspref|page):([A-Za-z0-9_.-]+)\|([^\]]*)\]\]")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
LINK_STYLE = "underline #58a6ff"


def refs(text: str) -> list[tuple[str, str]]:
    """(key, label) of every reference, in order, without repeats."""
    seen, out = set(), []
    for m in REF.finditer(text):
        key = f"{m.group(1)}:{m.group(2)}"
        if key not in seen:
            seen.add(key)
            out.append((key, m.group(3).strip() or key))
    return out


def _plain(text: str) -> str:
    return BOLD.sub(lambda m: f"[b]{m.group(1)}[/b]", escape(text))


def render(text: str, verified: dict[str, str]) -> str:
    out, pos = [], 0
    for m in REF.finditer(text):
        out.append(_plain(text[pos:m.start()]))
        key, label = f"{m.group(1)}:{m.group(2)}", m.group(3).strip() or f"{m.group(1)}:{m.group(2)}"
        if key in verified:
            out.append(f"[{LINK_STYLE} @click=open_ref('{key}')]{escape(label)}[/]")
        else:
            out.append(escape(label))
        pos = m.end()
    out.append(_plain(text[pos:]))
    return "".join(out)


def strip(text: str) -> str:
    """The answer as plain text (labels only)."""
    return REF.sub(lambda m: m.group(3), text)
