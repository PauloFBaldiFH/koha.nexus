"""sip.py: SIPconfig.xml written from the SIP2 form."""

import xml.etree.ElementTree as ET

import pytest

from kei_panel import sip

KOHA_DEFAULT = """<acsconfig xmlns="http://openncip.org/acs-config/1.0/">
<!-- Koha's example file -->
  <error-detect enabled="true" />
  <server-params min_servers='1' min_spare_servers='0' log_file='Sys::Syslog' />
  <listeners>
    <service port="127.0.0.1:8023/tcp" transport="telnet" protocol="SIP/2.00" timeout="60" />
    <service port="127.0.0.1:6001/tcp" transport="RAW" protocol="SIP/2.00" client_timeout="600" timeout="60" />
  </listeners>
  <accounts>
      <login id="term1"  password="term1" delimiter="|" error-detect="enabled" institution="CPL" encoding="ascii" checked_in_ok="1" />
      <login id="koha"   password="koha"  delimiter="|" error-detect="enabled" institution="kohalibrary" encoding="utf8" />
      <login id="desk"   password="Old-Pass-123" delimiter="^" institution="CPL" encoding="ascii" />
  </accounts>
  <institutions>
    <institution id="CPL" implementation="ILS" parms="">
      <policy checkin="true" renewal="false" checkout="true" status_update="false" offline="false" timeout="25" retries="5" />
    </institution>
  </institutions>
</acsconfig>
"""


def _settings(**kw):
    base = dict(port=6001, public=False, login="selfcheck", password="S3lf-Check-99", institution="CPL")
    base.update(kw)
    return sip.SipSettings(**base)


def test_read_settings_from_kohas_file():
    s = sip.read_settings(KOHA_DEFAULT)
    assert (s.port, s.public, s.login, s.institution) == (6001, False, "desk", "CPL")
    assert s.password == "" and s.renewal is False and s.checkout is True and s.remove_examples
    assert [lg["id"] for lg in sip.logins(KOHA_DEFAULT)] == ["term1", "koha", "desk"]
    assert sip.read_settings(sip.TEMPLATE).login == ""


def test_apply_new_login_public_and_examples_removed():
    out = sip.apply(KOHA_DEFAULT, _settings(public=True, port=6010, renewal=False, status_update=True))
    root = ET.fromstring(out)
    ns = {"a": sip.NS}
    ports = [e.get("port") for e in root.findall("a:listeners/a:service", ns)]
    assert ports == ["127.0.0.1:8023/tcp", "0.0.0.0:6010/tcp"]           # the telnet one is untouched
    assert [lg["id"] for lg in sip.logins(out)] == ["desk", "selfcheck"]
    new = root.find("a:accounts/a:login[@id='selfcheck']", ns)
    assert new.get("password") == "S3lf-Check-99" and new.get("institution") == "CPL"
    policy = root.find("a:institutions/a:institution[@id='CPL']/a:policy", ns)
    assert policy.get("renewal") == "false" and policy.get("status_update") == "true"
    assert policy.get("timeout") == "25"                                   # its own tuning stays
    assert "Koha's example file" in out                                   # comments survive
    assert 'xmlns="http://openncip.org/acs-config/1.0/"' in out and "ns0:" not in out
    assert not out.startswith("<?xml")


def test_existing_login_keeps_password_and_tuning():
    out = sip.apply(KOHA_DEFAULT, _settings(login="desk", password="", remove_examples=False, institution="MPL"))
    root = ET.fromstring(out)
    desk = root.find(f"{{{sip.NS}}}accounts/{{{sip.NS}}}login[@id='desk']")
    assert desk.get("password") == "Old-Pass-123" and desk.get("delimiter") == "^" and desk.get("encoding") == "ascii"
    assert desk.get("institution") == "MPL"
    assert [lg["id"] for lg in sip.logins(out)] == ["term1", "koha", "desk"]
    assert root.find(f"{{{sip.NS}}}institutions/{{{sip.NS}}}institution[@id='MPL']") is not None


def test_template_and_xml_header():
    out = sip.apply('<?xml version="1.0"?>\n' + sip.TEMPLATE, _settings())
    assert out.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    s = sip.read_settings(out)
    assert s.login == "selfcheck" and not s.remove_examples


@pytest.mark.parametrize("kw,expected", [
    ({"port": 80}, "between 1024"),
    ({"login": "bad login"}, "letters, digits"),
    ({"login": "term1"}, "example"),
    ({"password": ""}, "password"),
    ({"password": "short"}, "8 characters"),
    ({"institution": "XYZ"}, "library"),
])
def test_problem(kw, expected):
    assert expected in sip.problem(_settings(**kw), ["desk"], ["CPL", "MPL"])


def test_problem_accepts_good_settings_and_kept_password():
    assert sip.problem(_settings(), [], ["CPL"]) == ""
    assert sip.problem(_settings(login="desk", password=""), ["desk"], ["CPL"]) == ""


def test_write_temp_is_private(monkeypatch, tmp_path):
    path = sip.write_temp("<acsconfig/>")
    try:
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        path.unlink()
    monkeypatch.setenv("KEI_SIP_CONF", str(tmp_path / "x.xml"))
    assert sip.conf_path("library") == tmp_path / "x.xml"
    monkeypatch.delenv("KEI_SIP_CONF")
    assert str(sip.conf_path("library")) == "/etc/koha/sites/library/SIPconfig.xml"
