"""Names of the MARC 21 bibliographic fields a librarian meets most, for the
field mapping screen ("campo 2 (245$a - Title)"), and the Library of
Congress page that documents each one."""

from __future__ import annotations

LOC = "https://www.loc.gov/marc/bibliographic/"

TAGS = {
    "001": "Control number", "003": "Control number identifier", "005": "Date and time of latest transaction",
    "008": "Fixed-length data elements", "010": "LC control number", "020": "ISBN", "022": "ISSN",
    "035": "System control number", "040": "Cataloging source", "041": "Language code",
    "043": "Geographic area code", "080": "UDC number", "082": "Dewey class (DDC)", "090": "Local call number",
    "100": "Personal name (author)", "110": "Corporate name (author)", "111": "Meeting name",
    "130": "Uniform title", "240": "Uniform title", "245": "Title", "246": "Variant title", "250": "Edition",
    "260": "Publication (260)", "264": "Publication (264)", "300": "Physical description",
    "490": "Series statement", "500": "General note", "504": "Bibliography note", "505": "Contents note",
    "520": "Summary", "600": "Subject: personal name", "610": "Subject: corporate name",
    "650": "Topical subject", "651": "Subject: geographic name", "655": "Genre/form",
    "700": "Added author (personal name)", "710": "Added author (corporate name)", "830": "Series added entry",
    "856": "Electronic location (link)", "942": "Koha record type", "952": "Koha item (copy)",
}

SUBFIELDS = {
    "020$a": "ISBN", "022$a": "ISSN", "082$a": "Dewey class (DDC)", "100$a": "Personal name (author)",
    "245$a": "Title", "245$b": "Remainder of title (subtitle)", "245$c": "Statement of responsibility",
    "250$a": "Edition", "260$a": "Place of publication (260)", "260$b": "Publisher (260)",
    "260$c": "Date of publication (260)", "264$a": "Place of publication (264)", "264$b": "Publisher (264)",
    "264$c": "Date of publication (264)", "300$a": "Extent (pages)", "490$a": "Series statement",
    "500$a": "General note", "650$a": "Topical subject", "700$a": "Added author (personal name)",
    "942$c": "Koha item type", "952$a": "Home library", "952$b": "Current library",
    "952$c": "Shelving location", "952$d": "Date acquired", "952$e": "Source of acquisition",
    "952$g": "Price", "952$h": "Volume", "952$i": "Inventory number (tombo)", "952$o": "Call number",
    "952$p": "Barcode / accession number of the item", "952$t": "Copy number", "952$x": "Non-public note",
    "952$y": "Koha item type", "952$z": "Public note", "952$8": "Collection code",
}


def label(ref: str) -> str:
    """English name of TAG$c or TAG ("" when unknown); the screen translates it."""
    return SUBFIELDS.get(ref) or TAGS.get(ref.partition("$")[0], "")


def loc_url(ref: str = "") -> str:
    """The Library of Congress page of a tag (bd245.html), or the index for
    local tags (9XX, Koha's 942 and 952) and anything else."""
    tag = ref.partition("$")[0]
    if len(tag) == 3 and tag.isdigit() and not tag.startswith("9"):
        return f"{LOC}bd{tag}.html"
    return LOC
