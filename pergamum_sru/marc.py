"""Pergamum's MARC text (the "MARC" tab of a record) to MARCXML.

What Pergamum sends between <inicio> and <fim> looks like:

    001 123456
    020    $a 9788535902778
    245 10 $a Dom Casmurro / $c Machado de Assis.
    852    $

one field a line, lines ending in a bare carriage return. Each rule below
comes from a record Koha refused (MARC::File::XML) before it was there.
"""

from __future__ import annotations

import html
import re
from xml.etree import ElementTree as ET

from zeus_sru.sru import MARC

DEFAULT_LEADER = "00000cam a2200000 a 4500"
_SUBFIELD = re.compile(r"\$([a-zA-Z0-9])\s*([^$]+)")
# Characters XML 1.0 cannot carry (tab and newline are dealt with before).
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(block: str) -> str:
    """Line ends to \\n, entities decoded, separators out.

    Lines end in \\r alone: left in, the first tag reads "\\r0" and Koha
    stops with 'Tag "\\r0" is not a valid tag'. The Sajax answer may also
    carry them escaped (a backslash and an r). Accents stay as they are:
    no unicode_escape, which turns "é" into mojibake."""
    text = block.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text.replace("&nbsp;", " "))
    text = text.replace("\u001e", " ")
    return _XML_INVALID.sub(" ", text)


def text_to_marcxml(block: str) -> ET.Element:
    record = ET.Element(f"{{{MARC}}}record")
    leader = ET.SubElement(record, f"{{{MARC}}}leader")
    leader.text = DEFAULT_LEADER

    for raw_line in clean_text(block).split("\n"):
        line = raw_line.strip()
        if len(line) < 3:
            continue
        tag = line[:3]
        rest = line[3:].strip()
        if tag in ("LDR", "000"):
            if len(rest) == 24:
                leader.text = rest
            continue
        if not tag.isdigit():
            continue

        # Control fields 001-009.
        if int(tag) < 10:
            if rest:
                cf = ET.SubElement(record, f"{{{MARC}}}controlfield", tag=tag)
                cf.text = rest
            continue

        ind1 = ind2 = " "
        if rest and not rest.startswith("$"):
            parts = rest.split("$", 1)
            inds = parts[0].replace(" ", "").replace("#", " ")
            if len(inds) >= 1:
                ind1 = inds[0]
            if len(inds) >= 2:
                ind2 = inds[1]
            rest = "$" + parts[1] if len(parts) > 1 else ""

        subfields = [(c, v.strip()) for c, v in _SUBFIELD.findall(rest) if v.strip()]
        # A datafield without a subfield ("852    $") stops Koha with "Field
        # 852 must have at least one subfield": it is dropped.
        if not subfields:
            continue
        df = ET.SubElement(record, f"{{{MARC}}}datafield", tag=tag, ind1=ind1, ind2=ind2)
        for code, value in subfields:
            sf = ET.SubElement(df, f"{{{MARC}}}subfield", code=code)
            sf.text = value
    return record
