"""nexus_ondemand: the direct server list and the exclusion rule. Only the
direct Z39.50 servers may be contacted; the koha.nexus gateway, its tunnel
and every local endpoint are refused when the list is loaded, after the
name lookup, and before any connection."""

from __future__ import annotations

import asyncio
import json

import pytest

from nexus_gateway import z3950
from nexus_gateway.z3950 import Z3950Error
from nexus_ondemand import targets
from nexus_ondemand.connect import open_session
from nexus_ondemand.policy import Policy, PolicyError, address_refusal, name_refusal
from nexus_ondemand.targets import Address, Target, load, make_target, provider_of


def server(**over) -> dict:
    raw = {"id": "x", "name": "X", "host": "z3950.example.org", "port": 210, "db": "biblio",
           "syntax": "MARC21", "recordtype": "biblio", "protocol": "z3950"}
    raw.update(over)
    return raw


def write_list(tmp_path, servers) -> str:
    path = tmp_path / "direct.json"
    path.write_text(json.dumps({"servers": servers, "fallback": {"host": "127.0.0.1", "port": 5000}}))
    return str(path)


# ----------------------------------------------------------------------
# The real list
# ----------------------------------------------------------------------

def test_every_direct_server_loads_and_nothing_else():
    catalog = load(targets.DEFAULT_LIST, env={})
    assert len(catalog.targets) == 171 and catalog.skipped == []
    hosts = {a.host.lower() for t in catalog.targets.values() for a in t.addresses}
    assert not any(h.endswith("koha.nexus") or h in ("127.0.0.1", "localhost") for h in hosts)
    assert all(not name_refusal(a.host, a.port, a.db) for t in catalog.targets.values() for a in t.addresses)


def test_real_list_unusable_servers_and_providers():
    catalog = load(targets.DEFAULT_LIST, env={})
    unimarc = {t.id for t in catalog.targets.values() if "UNIMARC" in t.unusable}
    assert unimarc == {"bnp", "porbase", "bnf", "sudoc", "bnf-aut", "bnp-aut", "porbase-aut"}
    logins = {t.id for t in catalog.targets.values() if t.unusable.startswith("login")}
    assert logins == {"senado-folio"}               # bnf / bnf-aut are UNIMARC first
    assert sum(t.address.provider == "exlibris-alma" for t in catalog.targets.values()) == 126
    assert {t.address.provider for t in catalog.targets.values() if "loc.gov" in t.address.host} == {"loc"}
    usable = catalog.usable()
    assert all(t.recordtype == "biblio" and not t.unusable for t in usable)
    assert {t.id for t in catalog.targets.values() if t.preselect} == {"utfpr", "ufsc", "unifesp", "loc"}


def test_a_login_from_the_environment_makes_a_server_usable():
    catalog = load(targets.DEFAULT_LIST, env={"KEI_Z3950_SENADO_FOLIO_USER": "u",
                                              "KEI_Z3950_SENADO_FOLIO_PASSWORD": "s3cr3t-pw"})
    t = catalog.targets["senado-folio"]
    assert t.unusable == "" and (t.user, t.password) == ("u", "s3cr3t-pw")
    assert "s3cr3t" not in repr(t)


def test_alternates_keep_their_order_and_own_keys():
    usp = load(targets.DEFAULT_LIST, env={}).targets["usp"]
    keys = [a.key for a in usp.addresses]
    assert len(keys) == 3 and len(set(keys)) == 3
    assert keys[1] == "eu00.alma.exlibrisgroup.com:1921/55USP_INST"


def test_the_list_hash_changes_with_the_file(tmp_path):
    a = load(write_list(tmp_path, [server()]))
    b = load(write_list(tmp_path, [server(db="other")]))
    assert a.sha256 != b.sha256


# ----------------------------------------------------------------------
# Excluded when the list is loaded
# ----------------------------------------------------------------------

@pytest.mark.parametrize("over, why", [
    ({"host": "sru.koha.nexus", "port": 443, "db": "sru/_union"}, "koha.nexus"),
    ({"host": "catalog.koha.nexus", "port": 210}, "koha.nexus"),
    ({"host": "SRU.KOHA.NEXUS.", "port": 210}, "koha.nexus"),
    ({"host": "koha.nexus", "port": 210}, "koha.nexus"),
    ({"host": "127.0.0.1", "port": 5000, "db": "sru/all"}, "port 5000"),
    ({"host": "127.0.0.1", "port": 210}, "not a public address"),
    ({"host": "localhost", "port": 210}, "this machine"),
    ({"host": "10.0.0.60", "port": 5001}, "not a public address"),
    ({"host": "192.168.1.5", "port": 210}, "not a public address"),
    ({"host": "100.64.1.1", "port": 210}, "not a public address"),
    ({"host": "::1", "port": 210}, "not a public address"),
    ({"host": "137.131.205.31", "port": 210}, "koha.nexus server"),
    ({"host": "104.16.1.1", "port": 210}, "Cloudflare"),
    ({"host": "z.example.org", "port": 8088}, "port 8088"),
    ({"host": "z.example.org", "port": 5006}, "port 5006"),
    ({"host": "z.example.org", "port": 443}, "port 443"),
    ({"host": "z.example.org", "port": 210, "db": "sru/ufsc"}, "gateway row"),
    ({"host": "https://z.example.org", "port": 210}, "web address"),
    ({"protocol": "sru"}, "not z3950"),
    ({"host": ""}, "needs host"),
])
def test_excluded_entries_are_skipped_with_the_reason(tmp_path, over, why):
    catalog = load(write_list(tmp_path, [server(**over)]))
    assert catalog.targets == {}
    assert catalog.skipped and why in catalog.skipped[0][1]


def test_a_refused_alternate_is_dropped_and_the_server_kept():
    t, why = make_target(server(alternates=[{"host": "sru.koha.nexus", "port": 443, "db": "sru/x"},
                                            {"host": "z2.example.org", "port": 210, "db": "b"}]), env={})
    assert why == "" and [a.host for a in t.alternates] == ["z2.example.org"]


def test_a_login_env_must_be_a_kei_z3950_name():
    t, why = make_target(server(login_env="HOME"), env={"HOME_USER": "x"})
    assert t is None and "KEI_Z3950_" in why


def test_duplicates_and_bad_files(tmp_path):
    catalog = load(write_list(tmp_path, [server(), server()]))
    assert list(catalog.targets) == ["x"] and catalog.skipped == [("x", "listed twice")]
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    with pytest.raises(targets.ListError):
        load(bad)


def test_providers():
    assert provider_of("na01.alma.exlibrisgroup.com") == "exlibris-alma"
    assert provider_of("usp.alma.exlibrisgroup.com.") == "exlibris-alma"
    assert provider_of("lx2.loc.gov") == "loc" and provider_of("loc.gov") == "loc"
    assert provider_of("notloc.gov") == "" and provider_of("z3950.dnb.de") == ""


# ----------------------------------------------------------------------
# Checked again after the lookup
# ----------------------------------------------------------------------

def resolver(*addresses):
    async def lookup(host, port):
        return list(addresses)
    return lookup


def resolve(policy, host, port=210, db="b"):
    return asyncio.run(policy.resolve(host, port, db))


def test_a_public_name_resolves_to_its_checked_address():
    assert resolve(Policy(resolver=resolver("2a00:1450:4001::1", "200.19.73.127")), "z.example.org") == "200.19.73.127"
    assert resolve(Policy(resolver=resolver("2a00:1450::1")), "z.example.org") == "2a00:1450::1"
    assert resolve(Policy(), "200.19.73.127") == "200.19.73.127"          # a public literal: no lookup


@pytest.mark.parametrize("addresses", [
    ("127.0.0.1",), ("10.1.2.3",), ("200.19.73.127", "192.168.0.10"), ("137.131.205.31",),
    ("104.16.132.229",), ("2606:4700::6810:84e5",), ("172.67.1.1",), ("169.254.1.1",), ("fe80::1",),
])
def test_a_name_that_resolves_to_a_refused_address_is_refused(addresses):
    with pytest.raises(PolicyError) as info:
        resolve(Policy(resolver=resolver(*addresses)), "innocent.example.org")
    assert info.value.kind == "policy" and info.value.phase == "connect"


def test_refused_names_are_never_looked_up():
    asked = []

    async def lookup(host, port):
        asked.append(host)
        return ["200.19.73.127"]

    for host in ("sru.koha.nexus", "catalog.koha.nexus", "localhost"):
        with pytest.raises(PolicyError):
            resolve(Policy(resolver=lookup), host)
    assert asked == []


def test_lookup_failures_are_dns_errors():
    async def missing(host, port):
        raise OSError(-2, "Name or service not known")

    async def slow(host, port):
        await asyncio.sleep(5)

    for policy in (Policy(resolver=missing), Policy(resolver=slow, dns_timeout=0.1), Policy(resolver=resolver())):
        with pytest.raises(Z3950Error) as info:
            resolve(policy, "nowhere.example.org")
        assert info.value.kind == "dns"


def test_allowed_networks_only_lift_the_address_check():
    policy = Policy(allowed=("127.0.0.0/8",))
    assert resolve(policy, "127.0.0.1") == "127.0.0.1"
    for host, port in (("127.0.0.1", 5000), ("sru.koha.nexus", 210), ("localhost", 210)):
        with pytest.raises(PolicyError):
            resolve(policy, host, port)
    assert address_refusal("127.0.0.1") and not address_refusal("127.0.0.1", policy._allowed)


# ----------------------------------------------------------------------
# open_session: nothing is contacted when the policy refuses
# ----------------------------------------------------------------------

def test_open_session_connects_to_the_checked_address(monkeypatch):
    seen = []

    async def fake_open(self):
        seen.append((self.host, self.address, self.name))

    monkeypatch.setattr(z3950.Session, "open", fake_open)
    t = Target("x", "X", Address("z.example.org", 210, "b"))
    s = asyncio.run(open_session(t, t.address, Policy(resolver=resolver("200.19.73.127"))))
    assert seen == [("z.example.org", "200.19.73.127", "koha.nexus on-demand")] and s.address == "200.19.73.127"


def test_open_session_refused_never_connects(monkeypatch):
    async def no_connection(*a, **k):
        raise AssertionError("a refused host was contacted")

    monkeypatch.setattr(asyncio, "open_connection", no_connection)
    for host, addr in (("sru.koha.nexus", "200.19.73.127"), ("z.example.org", "104.16.1.1"),
                       ("z.example.org", "127.0.0.1")):
        t = Target("x", "X", Address(host, 210, "b"))
        with pytest.raises(PolicyError):
            asyncio.run(open_session(t, t.address, Policy(resolver=resolver(addr))))


def test_the_package_never_imports_the_sru_client():
    import nexus_ondemand
    from pathlib import Path
    for path in Path(nexus_ondemand.__file__).parent.glob("*.py"):
        text = path.read_text()
        assert "upstream" not in text and "urllib" not in text, path.name
