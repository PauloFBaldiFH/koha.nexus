"""SRU 1.1 responses: searchRetrieveResponse, explainResponse, diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

ZS = "http://www.loc.gov/zing/srw/"
DIAG = "http://www.loc.gov/zing/srw/diagnostic/"
EXPLAIN = "http://explain.z3950.org/dtd/2.0/"
MARC = "http://www.loc.gov/MARC21/slim"
# The schema name put in each record. YAZ (Koha's ZOOM client) drops records
# whose recordSchema is the full URI, so the short name goes out; the URI is
# still accepted on the way in and listed in explain.
MARCXML_SCHEMA = "marcxml"
MARCXML_URI = "info:srw/schema/1/marcxml-v1.1"
SOAP = "http://schemas.xmlsoap.org/soap/envelope/"

ET.register_namespace("zs", ZS)
ET.register_namespace("diag", DIAG)
ET.register_namespace("marc", MARC)
ET.register_namespace("ex", EXPLAIN)
ET.register_namespace("SOAP-ENV", SOAP)

# Names Koha and other clients send for MARCXML. An empty schema means the
# server default, which is MARCXML too.
MARCXML_NAMES = {"", "marcxml", "marc21", "marc", "usmarc", "marc21xml",
                 "info:srw/schema/1/marcxml-v1.1", "info:srw/schema/1/marcxml-v1.1-light",
                 "http://www.loc.gov/marc21/slim"}

# SRU diagnostics used here: info:srw/diagnostic/1/<n>
GENERAL_ERROR = 1
UNSUPPORTED_OPERATION = 4
UNSUPPORTED_VERSION = 5
UNSUPPORTED_PARAMETER_VALUE = 6
MANDATORY_PARAMETER_MISSING = 7
QUERY_SYNTAX_ERROR = 10
FIRST_RECORD_OUT_OF_RANGE = 61
UNKNOWN_SCHEMA = 66
UNSUPPORTED_PACKING = 71


@dataclass
class Diagnostic:
    code: int
    details: str = ""
    message: str = ""


def _el(parent: ET.Element, tag: str, text: str | int | None = None, ns: str = ZS) -> ET.Element:
    node = ET.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        node.text = str(text)
    return node


def _diagnostics(parent: ET.Element, diags: list[Diagnostic]) -> None:
    if not diags:
        return
    box = _el(parent, "diagnostics")
    for d in diags:
        node = _el(box, "diagnostic", ns=DIAG)
        _el(node, "uri", f"info:srw/diagnostic/1/{d.code}", ns=DIAG)
        if d.details:
            _el(node, "details", d.details, ns=DIAG)
        if d.message:
            _el(node, "message", d.message, ns=DIAG)


def serialize(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def search_retrieve_response(
    *,
    total: int,
    records: list[ET.Element],
    start: int,
    packing: str = "xml",
    echo: dict[str, str] | None = None,
    diagnostics: list[Diagnostic] | None = None,
) -> bytes:
    root = ET.Element(f"{{{ZS}}}searchRetrieveResponse")
    _el(root, "version", "1.1")
    _el(root, "numberOfRecords", total)
    if records:
        box = _el(root, "records")
        for offset, data in enumerate(records):
            rec = _el(box, "record")
            _el(rec, "recordSchema", MARCXML_SCHEMA)
            _el(rec, "recordPacking", packing)
            holder = _el(rec, "recordData")
            if packing == "string":
                holder.text = ET.tostring(data, encoding="unicode")
            else:
                holder.append(data)
            _el(rec, "recordPosition", start + offset)
        nxt = start + len(records)
        if nxt <= total:
            _el(root, "nextRecordPosition", nxt)
    if echo:
        e = _el(root, "echoedSearchRetrieveRequest")
        for key in ("version", "query", "startRecord", "maximumRecords",
                    "recordPacking", "recordSchema"):
            if echo.get(key):
                _el(e, key, echo[key])
    _diagnostics(root, diagnostics or [])
    return serialize(root)


def diagnostic_response(diag: Diagnostic, operation: str = "searchRetrieve") -> bytes:
    tag = "explainResponse" if operation == "explain" else "searchRetrieveResponse"
    root = ET.Element(f"{{{ZS}}}{tag}")
    _el(root, "version", "1.1")
    if tag == "searchRetrieveResponse":
        _el(root, "numberOfRecords", 0)
    _diagnostics(root, [diag])
    return serialize(root)


def explain_response(host: str, port: int, database: str, max_records: int) -> bytes:
    root = ET.Element(f"{{{ZS}}}explainResponse")
    _el(root, "version", "1.1")
    rec = _el(root, "record")
    _el(rec, "recordSchema", "http://explain.z3950.org/dtd/2.0/")
    _el(rec, "recordPacking", "xml")
    data = _el(rec, "recordData")

    def x(parent, tag, text=None, **attrs):
        node = ET.SubElement(parent, f"{{{EXPLAIN}}}{tag}", attrs)
        if text is not None:
            node.text = str(text)
        return node

    explain = x(data, "explain")
    server = x(explain, "serverInfo", protocol="SRU", version="1.1")
    x(server, "host", host)
    x(server, "port", port)
    x(server, "database", database)
    info = x(explain, "databaseInfo")
    x(info, "title", "Catálogo Zeus (BU/UFSC) via SRU", lang="pt", primary="true")
    x(info, "description",
      "Federated search of Brazilian university catalogues through Catálogo Zeus.", lang="en")
    index_info = x(explain, "indexInfo")
    x(index_info, "set", name="dc", identifier="info:srw/cql-context-set/1/dc-v1.1")
    x(index_info, "set", name="bath", identifier="http://zing.z3950.org/cql/bath/2.0/")
    for title, set_name, name in (("ISBN", "dc", "isbn"), ("ISBN", "bath", "isbn"),
                                  ("Title", "dc", "title"),
                                  ("Any", "cql", "serverChoice")):
        idx = x(index_info, "index")
        x(idx, "title", title)
        m = x(idx, "map")
        x(m, "name", name, set=set_name)
    schema_info = x(explain, "schemaInfo")
    s = x(schema_info, "schema", identifier=MARCXML_URI, name=MARCXML_SCHEMA)
    x(s, "title", "MARCXML")
    cfg = x(explain, "configInfo")
    x(cfg, "default", 10, type="numberOfRecords")
    x(cfg, "setting", max_records, type="maximumRecords")
    return serialize(root)


def soap_wrap(body: bytes) -> bytes:
    """An SRU response inside a SOAP 1.1 envelope (SRW), for SOAP requests."""
    env = ET.Element(f"{{{SOAP}}}Envelope")
    ET.SubElement(env, f"{{{SOAP}}}Body").append(ET.fromstring(body))
    return serialize(env)
