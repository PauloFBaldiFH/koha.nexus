"""SIP2 for self-check machines: Koha's SIPconfig.xml, edited from a form.

The SIP2 tab of the messaging hub (views/hub.py) asks for the port, who
may connect, the SIP login, its library and what the machine may do; this
module reads the current file and writes the new one. `config.sh --task
sip-apply FILE PORT PUBLIC` checks it, keeps a dated copy of the old file,
puts it in place and restarts Koha's SIP server.

The login is also a Koha patron: the machine signs in with the same user
name and password, so the patron must exist in Koha (the tab opens Koha's
"New patron" page) with the circulate permission. Koha's example logins
(term1, koha, ...) have published passwords: the form offers to drop them.
"""

from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

NS = "http://openncip.org/acs-config/1.0/"
EXAMPLES = ("term1", "koha", "koha2", "lpl-sc", "lpl-sc-beacock")

# Koha's own template (debian/templates/SIPconfig.xml), for an instance
# whose file is missing.
TEMPLATE = """<acsconfig xmlns="http://openncip.org/acs-config/1.0/">
  <error-detect enabled="true" />
  <server-params min_servers='1' min_spare_servers='0' log_file='Sys::Syslog' />
  <listeners>
    <service port="127.0.0.1:6001/tcp" transport="RAW" protocol="SIP/2.00" client_timeout="600" timeout="60" />
  </listeners>
  <accounts>
  </accounts>
  <institutions>
  </institutions>
</acsconfig>
"""


@dataclass
class SipSettings:
    port: int = 6001
    public: bool = False          # listen on every address (else 127.0.0.1 only)
    login: str = ""
    password: str = ""            # "" keeps the password of an existing login
    institution: str = ""         # a Koha library code
    checkout: bool = True
    checkin: bool = True
    renewal: bool = True
    status_update: bool = False   # the machine may change patron data
    remove_examples: bool = True


def conf_path(instance: str) -> Path:
    return Path(os.environ.get("KEI_SIP_CONF") or f"/etc/koha/sites/{instance}/SIPconfig.xml")


def _parse(text: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(text or TEMPLATE, parser=parser)


def _ns(root: ET.Element) -> str:
    m = re.match(r"\{([^}]*)\}", root.tag)
    return m.group(1) if m else ""


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}" if ns else tag


def _child(parent: ET.Element, ns: str, tag: str) -> ET.Element:
    found = parent.find(_q(ns, tag))
    if found is None:
        found = ET.SubElement(parent, _q(ns, tag))
    return found


def _sip_service(root: ET.Element, ns: str) -> ET.Element | None:
    listeners = root.find(_q(ns, "listeners"))
    if listeners is None:
        return None
    for service in listeners.findall(_q(ns, "service")):
        if service.get("transport", "").upper() == "RAW":
            return service
    return None


def logins(text: str) -> list[dict[str, str]]:
    """The SIP logins of the file (no passwords)."""
    root = _parse(text)
    ns = _ns(root)
    accounts = root.find(_q(ns, "accounts"))
    if accounts is None:
        return []
    return [{"id": e.get("id", ""), "institution": e.get("institution", ""), "example": str(e.get("id") in EXAMPLES)}
            for e in accounts.findall(_q(ns, "login"))]


def read_settings(text: str) -> SipSettings:
    """The form's starting values: the listener and the first login that is
    not one of Koha's examples (its password is never read back)."""
    s = SipSettings()
    root = _parse(text)
    ns = _ns(root)
    service = _sip_service(root, ns)
    if service is not None:
        m = re.match(r"(?:(?P<host>[^:]*):)?(?P<port>\d+)(?:/tcp)?$", service.get("port", ""))
        if m:
            s.port = int(m.group("port"))
            s.public = (m.group("host") or "0.0.0.0") in ("0.0.0.0", "*", "")
    own = [lg for lg in logins(text) if lg["example"] == "False"]
    if own:
        s.login, s.institution = own[0]["id"], own[0]["institution"]
    s.remove_examples = any(lg["example"] == "True" for lg in logins(text))
    if s.institution:
        for inst in root.iter(_q(ns, "institution")):
            if inst.get("id") == s.institution:
                policy = inst.find(_q(ns, "policy"))
                if policy is not None:
                    for name in ("checkout", "checkin", "renewal", "status_update"):
                        setattr(s, name, policy.get(name, "true" if name != "status_update" else "false") == "true")
    return s


def problem(s: SipSettings, existing: list[str], branches: list[str]) -> str:
    """"" when the settings can be written, else what to fix."""
    if not 1024 <= int(s.port) <= 65535:
        return "The port must be between 1024 and 65535."
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", s.login or ""):
        return "The SIP login has letters, digits and . _ @ - only."
    if s.login in EXAMPLES:
        return "Choose a login of your own: Koha's example logins have published passwords."
    if not s.password and s.login not in existing:
        return "Type the password of the SIP login."
    if s.password and (len(s.password) < 8 or re.search(r"[\x00-\x1f]", s.password)):
        return "The password needs at least 8 characters."
    if branches and s.institution not in branches:
        return "Choose the library of the self-check machine."
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,10}", s.institution or ""):
        return "Choose the library of the self-check machine."
    return ""


def apply(text: str, s: SipSettings) -> str:
    """The file with the listener, the login and the library's policy set."""
    root = _parse(text)
    ns = _ns(root)
    listeners = _child(root, ns, "listeners")
    service = _sip_service(root, ns)
    if service is None:
        service = ET.SubElement(listeners, _q(ns, "service"), {"transport": "RAW", "protocol": "SIP/2.00",
                                                               "client_timeout": "600", "timeout": "60"})
    service.set("port", f"{'0.0.0.0' if s.public else '127.0.0.1'}:{int(s.port)}/tcp")

    accounts = _child(root, ns, "accounts")
    if s.remove_examples:
        for login in list(accounts.findall(_q(ns, "login"))):
            if login.get("id") in EXAMPLES:
                accounts.remove(login)
    login = next((e for e in accounts.findall(_q(ns, "login")) if e.get("id") == s.login), None)
    if login is None:
        login = ET.SubElement(accounts, _q(ns, "login"))
    attrs = {"id": s.login, "password": s.password, "delimiter": "|", "error-detect": "enabled",
             "institution": s.institution, "encoding": "utf8", "checked_in_ok": "1"}
    if not s.password:
        del attrs["password"]
    for key, value in attrs.items():
        if key in ("delimiter", "error-detect", "encoding", "checked_in_ok") and login.get(key) is not None:
            continue          # an existing login keeps its own fine-tuning
        login.set(key, value)

    institutions = _child(root, ns, "institutions")
    inst = next((e for e in institutions.findall(_q(ns, "institution")) if e.get("id") == s.institution), None)
    if inst is None:
        inst = ET.SubElement(institutions, _q(ns, "institution"), {"id": s.institution, "implementation": "ILS",
                                                                   "parms": ""})
    policy = _child(inst, ns, "policy")
    for name in ("checkin", "renewal", "checkout", "status_update"):
        policy.set(name, "true" if getattr(s, name) else "false")
    for name, value in (("offline", "false"), ("timeout", "100"), ("retries", "5")):
        if policy.get(name) is None:
            policy.set(name, value)

    if ns:
        ET.register_namespace("", ns)
    ET.indent(root, "  ")
    body = ET.tostring(root, encoding="unicode")
    head = '<?xml version="1.0" encoding="UTF-8"?>\n' if (text or "").lstrip().startswith("<?xml") else ""
    return head + body + "\n"


def write_temp(text: str) -> Path:
    fd, name = tempfile.mkstemp(prefix="kei-sip-", suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return Path(name)
