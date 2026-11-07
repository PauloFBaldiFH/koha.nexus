"""Tests for the Pix webhook service. No network, no bank, no Koha: all fakes."""
import hashlib
import hmac
import json
import os
import sys
import tempfile
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "servico"))
import pix_webhook as pw  # noqa: E402

SECRET = "s" * 40
CARD_RE = r'data-cardnumber="([^"]+)"'


def make_cfg(**over):
    base = dict(koha_api_base="https://biblio.example/api/v1", koha_opac_base="https://biblio.example",
                koha_api_user="nexus-pix", koha_api_password="x", cardnumber_re=CARD_RE,
                pix_provider_url="https://psp.example/cob", pix_provider_token="t",
                webhook_secret=SECRET, db_path=":memory:", max_amount=Decimal("500"))
    base.update(over)
    return pw.Config(**base)


class FakeKoha:
    """Stands in for KohaClient. Records every credit so tests can assert REST-only writes."""

    def __init__(self, owed="12.50", session_card="123456", fail_credit=False):
        self.owed, self.session_card, self.fail_credit = Decimal(owed), session_card, fail_credit
        self.credits = []

    def patron_id_from_session(self, sessid):
        return 42 if self.session_card else None

    def outstanding(self, patron_id):
        return self.owed

    def credit(self, patron_id, amount, description, note):
        if self.fail_credit:
            raise RuntimeError("koha 500")
        self.credits.append((patron_id, amount, note))


class FakeProvider:
    def create_charge(self, txid, amount, description, expires_s):
        return {"copia_cola": "00020126" + txid, "qr_base64": ""}


@pytest.fixture
def app(tmp_path):
    cfg = make_cfg(db_path=str(tmp_path / "c.db"))
    return pw.App(cfg, FakeKoha(), FakeProvider(), pw.Store(cfg.db_path), clock=lambda: 1_800_000_000)


def sign(raw: bytes, secret=SECRET):
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def create(app, cookie="CGISESSID=abcdefgh12345678"):
    return app.create_charge(cookie)


def pay(app, txid, valor="12.50", status="paid", sig=None):
    raw = json.dumps({"txid": txid, "status": status, "valor": valor}).encode()
    return app.handle_webhook(raw, sig if sig is not None else sign(raw))


def test_config_requires_settings_and_https():
    with pytest.raises(ValueError):
        pw.Config.from_env({})
    env = {k: "v" for k in ["KOHA_API_BASE", "KOHA_OPAC_BASE", "KOHA_API_USER", "KOHA_API_PASSWORD",
                            "KOHA_CARDNUMBER_RE", "PIX_PROVIDER_URL", "PIX_PROVIDER_TOKEN", "PIX_WEBHOOK_SECRET"]}
    env.update(KOHA_CARDNUMBER_RE=CARD_RE, PIX_WEBHOOK_SECRET=SECRET,
               KOHA_API_BASE="https://b.example/api/v1", KOHA_OPAC_BASE="https://b.example",
               PIX_PROVIDER_URL="https://psp.example/cob")
    assert pw.Config.from_env(env).webhook_secret == SECRET
    env["KOHA_API_BASE"] = "http://b.example/api/v1"  # plain http refused off localhost
    with pytest.raises(ValueError):
        pw.Config.from_env(env)
    env["KOHA_API_BASE"] = "http://127.0.0.1/api/v1"  # allowed on localhost
    env["PIX_WEBHOOK_SECRET"] = "short"
    with pytest.raises(ValueError):
        pw.Config.from_env(env)


def test_signature_fails_closed():
    raw = b'{"a":1}'
    assert pw.verify_signature(SECRET, raw, sign(raw))
    assert not pw.verify_signature(SECRET, raw + b" ", sign(raw))  # body changed
    assert not pw.verify_signature(SECRET, raw, "")  # missing
    assert not pw.verify_signature(SECRET, raw, sign(raw, secret="o" * 40))  # wrong key
    assert not pw.verify_signature("", raw, sign(raw, secret=""))  # empty secret never passes


def test_session_cookie_is_isolated():
    assert pw.parse_sessid("theme=x; CGISESSID=abcdefgh12345678; other=1") == "abcdefgh12345678"
    assert pw.parse_sessid("CGISESSID=bad value!") is None
    assert pw.parse_sessid(None) is None


def test_charge_needs_login(app):
    assert create(app, cookie=None) == (401, {"error": "login_required"})
    assert create(app, cookie="theme=x") == (401, {"error": "login_required"})


def test_nothing_owed_and_limit(tmp_path):
    cfg = make_cfg(db_path=str(tmp_path / "c.db"), max_amount=Decimal("20"))
    koha = FakeKoha(owed="0")
    a = pw.App(cfg, koha, FakeProvider(), pw.Store(cfg.db_path))
    assert create(a)[0] == 409
    koha.owed = Decimal("25")
    status, body = create(a)
    assert status == 409 and body["error"] == "amount_over_limit"


def test_charge_created_and_paid_credits_once_via_rest(app):
    status, body = create(app)
    assert status == 200 and body["amount"] == "12.50" and len(body["txid"]) == 32
    assert pay(app, body["txid"]) == (200, {"result": "credited"})
    assert app.koha.credits == [(42, Decimal("12.50"), f"Pix txid {body['txid']} (Koha.Nexus)")]
    # bank retries the same event: no second credit
    assert pay(app, body["txid"]) == (200, {"result": "already_processed"})
    assert len(app.koha.credits) == 1


def test_bad_signature_and_unknown_txid(app):
    _, body = create(app)
    raw = json.dumps({"txid": body["txid"], "status": "paid", "valor": "12.50"}).encode()
    assert app.handle_webhook(raw, sign(raw, secret="o" * 40)) == (401, {"error": "bad_signature"})
    assert app.koha.credits == []
    assert pay(app, "f" * 32)[0] == 404


def test_amount_mismatch_is_not_credited(app):
    _, body = create(app)
    assert pay(app, body["txid"], valor="1.00")[0] == 409
    assert app.koha.credits == []
    assert app.store.get(body["txid"])[2] == "amount_mismatch"


def test_credit_failure_lets_bank_retry(app):
    _, body = create(app)
    app.koha.fail_credit = True
    assert pay(app, body["txid"])[0] == 500
    app.koha.fail_credit = False
    assert pay(app, body["txid"]) == (200, {"result": "credited"})
    assert len(app.koha.credits) == 1


def test_unpaid_status_is_ignored(app):
    _, body = create(app)
    assert pay(app, body["txid"], status="pending") == (200, {"result": "ignored"})
    assert app.koha.credits == []


def test_koha_card_match_resolves_patron_or_fails_closed():
    # Koha client reads the card from the OPAC page, then REST resolves the patron.
    cfg = make_cfg()
    calls = []

    class Resp:
        def __init__(self, data): self.data = data
        def read(self): return self.data
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def opener(req, timeout=None):
        calls.append(req.full_url)
        if "opac-account.pl" in req.full_url:
            assert req.headers["Cookie"] == "CGISESSID=abcdefgh12345678"
            return Resp(b'<div data-cardnumber="123456"></div>')
        return Resp(json.dumps([{"patron_id": 42}]).encode())

    client = pw.KohaClient(cfg, opener=opener)
    assert client.patron_id_from_session("abcdefgh12345678") == 42
    assert any("/api/v1/patrons?" in u for u in calls)

    def logged_out(req, timeout=None):
        return Resp(b"<form>login</form>")
    assert pw.KohaClient(cfg, opener=logged_out).patron_id_from_session("abcdefgh12345678") is None


def test_service_never_touches_koha_sql():
    source = open(os.path.join(os.path.dirname(pw.__file__), "pix_webhook.py")).read()
    for banned in ("import pymysql", "import MySQLdb", "import mysql", "accountlines", "UPDATE accountlines"):
        assert banned not in source
    # Only the service's own SQLite store uses sqlite3; Koha is reached through REST helpers.
    assert "POST" in source and "/account/credits" in source
