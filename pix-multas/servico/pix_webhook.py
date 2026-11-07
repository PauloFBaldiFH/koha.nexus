#!/usr/bin/env python3
"""Koha.Nexus - Pix fine payments: dynamic charges and bank webhook.

Standard library only (Python 3.9+). This service never touches Koha's SQL
tables. It reads patrons and balances through the official REST API and posts
the payment credit with POST /api/v1/patrons/{patron_id}/account/credits.
Its own state (pending charges) lives in a small SQLite file owned by the
service user, outside Koha.

Identity: the reader is never trusted from the browser. The request must carry
the reader's own Koha OPAC session cookie (CGISESSID). The service fetches the
OPAC account page with that cookie, reads the card number and resolves the
patron through REST. If anything does not match, the request is refused
(fail closed).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = logging.getLogger("nexus-pix")
MAX_BODY = 64 * 1024
PAID_STATUS = "paid"  # value the bank/PSP sends in "status" when the charge is paid
SESSID_RE = re.compile(r"^[A-Za-z0-9]{8,128}$")
TXID_RE = re.compile(r"^[A-Za-z0-9]{26,35}$")
CENT = Decimal("0.01")


def _is_localhost(url: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    return host in ("127.0.0.1", "localhost", "::1")


@dataclass(frozen=True)
class Config:
    koha_api_base: str
    koha_opac_base: str
    koha_api_user: str
    koha_api_password: str
    cardnumber_re: str
    pix_provider_url: str
    pix_provider_token: str
    webhook_secret: str
    db_path: str = "/var/lib/nexus-pix/charges.db"
    max_amount: Decimal = Decimal("500.00")
    charge_ttl: int = 3600
    credit_type: str = "PAYMENT"
    credit_payment_type: str = ""
    listen_host: str = "127.0.0.1"
    listen_port: int = 8790

    @classmethod
    def from_env(cls, env=None) -> "Config":
        env = os.environ if env is None else env

        def need(name):
            value = (env.get(name) or "").strip()
            if not value:
                raise ValueError(f"missing required setting {name}")
            return value

        cfg = cls(
            koha_api_base=need("KOHA_API_BASE").rstrip("/"),
            koha_opac_base=need("KOHA_OPAC_BASE").rstrip("/"),
            koha_api_user=need("KOHA_API_USER"),
            koha_api_password=need("KOHA_API_PASSWORD"),
            cardnumber_re=need("KOHA_CARDNUMBER_RE"),
            pix_provider_url=need("PIX_PROVIDER_URL"),
            pix_provider_token=need("PIX_PROVIDER_TOKEN"),
            webhook_secret=need("PIX_WEBHOOK_SECRET"),
            db_path=env.get("PIX_DB_PATH") or "/var/lib/nexus-pix/charges.db",
            max_amount=Decimal(env.get("PIX_MAX_AMOUNT") or "500.00"),
            charge_ttl=int(env.get("PIX_CHARGE_TTL") or 3600),
            credit_type=env.get("PIX_CREDIT_TYPE") or "PAYMENT",
            credit_payment_type=env.get("PIX_CREDIT_PAYMENT_TYPE") or "",
            listen_host=env.get("LISTEN_HOST") or "127.0.0.1",
            listen_port=int(env.get("LISTEN_PORT") or 8790),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        for url in (self.koha_api_base, self.koha_opac_base, self.pix_provider_url):
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != "https" and not (parts.scheme == "http" and _is_localhost(url)):
                raise ValueError(f"URL must be https (http only for localhost): {url}")
        if len(self.webhook_secret) < 32:
            raise ValueError("PIX_WEBHOOK_SECRET must have at least 32 characters")
        compiled = re.compile(self.cardnumber_re)
        if compiled.groups < 1:
            raise ValueError("KOHA_CARDNUMBER_RE needs one capturing group for the card number")
        if self.max_amount <= 0 or self.charge_ttl <= 0:
            raise ValueError("PIX_MAX_AMOUNT and PIX_CHARGE_TTL must be positive")


def verify_signature(secret: str, raw: bytes, header: str) -> bool:
    """Check 'X-Signature: sha256=<hex>' = HMAC-SHA256(secret, raw body). Fails closed."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):].strip().lower())


def parse_sessid(cookie_header: str | None) -> str | None:
    """Return the CGISESSID value only; every other cookie is dropped."""
    for part in (cookie_header or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == "CGISESSID" and SESSID_RE.match(value):
            return value
    return None


class KohaClient:
    """Reads and credits through the Koha REST API and reads the OPAC account page."""

    def __init__(self, cfg: Config, opener=urllib.request.urlopen):
        self.cfg = cfg
        self._open = opener
        self._auth = "Basic " + base64.b64encode(
            f"{cfg.koha_api_user}:{cfg.koha_api_password}".encode()).decode()
        self._card_re = re.compile(cfg.cardnumber_re)

    def _api(self, method: str, path: str, body=None, query=None):
        url = self.cfg.koha_api_base + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": self._auth, "Accept": "application/json",
            "Content-Type": "application/json"})
        with self._open(req, timeout=15) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else None

    def patron_id_from_session(self, sessid: str) -> int | None:
        req = urllib.request.Request(self.cfg.koha_opac_base + "/cgi-bin/koha/opac-account.pl",
                                     headers={"Cookie": f"CGISESSID={sessid}"})
        with self._open(req, timeout=15) as resp:
            page = resp.read().decode("utf-8", "replace")
        match = self._card_re.search(page)
        if not match:
            return None  # not logged in, or the pattern does not match this OPAC
        rows = self._api("GET", "/patrons", query={"q": json.dumps({"cardnumber": match.group(1)})})
        if not rows or len(rows) != 1:
            return None
        return int(rows[0]["patron_id"])

    def outstanding(self, patron_id: int) -> Decimal:
        account = self._api("GET", f"/patrons/{patron_id}/account") or {}
        debits = account.get("outstanding_debits") or {}
        total = debits.get("total_outstanding", 0)
        return max(Decimal(str(total)), Decimal("0")).quantize(CENT, ROUND_HALF_UP)

    def credit(self, patron_id: int, amount: Decimal, description: str, note: str) -> None:
        body = {"credit_type_code": self.cfg.credit_type, "amount": float(amount),
                "description": description[:200], "note": note[:500]}
        if self.cfg.credit_payment_type:
            body["payment_type"] = self.cfg.credit_payment_type
        self._api("POST", f"/patrons/{patron_id}/account/credits", body=body)


class PixProvider:
    """Creates dynamic Pix charges at the PSP. Adjust the JSON mapping to your PSP's contract."""

    def __init__(self, cfg: Config, opener=urllib.request.urlopen):
        self.cfg = cfg
        self._open = opener

    def create_charge(self, txid: str, amount: Decimal, description: str, expires_s: int) -> dict:
        body = json.dumps({"txid": txid, "valor": f"{amount:.2f}",
                           "descricao": description[:140], "expiracao": expires_s}).encode()
        req = urllib.request.Request(self.cfg.pix_provider_url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.cfg.pix_provider_token}",
            "Content-Type": "application/json", "Accept": "application/json"})
        with self._open(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return {"copia_cola": data["pix_copia_cola"], "qr_base64": data.get("qr_base64", "")}


class Store:
    """Pending charges, in a service-owned SQLite file (never Koha's database)."""

    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS charges (
            txid TEXT PRIMARY KEY, patron_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL,
            status TEXT NOT NULL, created_at INTEGER NOT NULL, paid_at INTEGER)""")
        self._db.commit()

    def insert(self, txid: str, patron_id: int, amount: Decimal) -> None:
        with self._lock:
            self._db.execute("INSERT INTO charges VALUES (?,?,?,?,?,NULL)",
                             (txid, patron_id, int(amount * 100), "pending", int(time.time())))
            self._db.commit()

    def get(self, txid: str):
        with self._lock:
            return self._db.execute(
                "SELECT patron_id, amount_cents, status FROM charges WHERE txid=?", (txid,)).fetchone()

    def claim(self, txid: str) -> bool:
        """Move pending/credit_failed -> crediting. Only one caller wins (idempotency)."""
        with self._lock:
            cur = self._db.execute(
                "UPDATE charges SET status='crediting' WHERE txid=? AND status IN ('pending','credit_failed')",
                (txid,))
            self._db.commit()
            return cur.rowcount == 1

    def set_status(self, txid: str, status: str, paid_at: int | None = None) -> None:
        with self._lock:
            self._db.execute("UPDATE charges SET status=?, paid_at=COALESCE(?, paid_at) WHERE txid=?",
                             (status, paid_at, txid))
            self._db.commit()


class App:
    def __init__(self, cfg: Config, koha: KohaClient, provider: PixProvider, store: Store, clock=time.time):
        self.cfg, self.koha, self.provider, self.store, self.clock = cfg, koha, provider, store, clock

    def create_charge(self, cookie_header: str | None) -> tuple[int, dict]:
        sessid = parse_sessid(cookie_header)
        if not sessid:
            return 401, {"error": "login_required"}
        try:
            patron_id = self.koha.patron_id_from_session(sessid)
            if patron_id is None:
                return 401, {"error": "login_required"}
            owed = self.koha.outstanding(patron_id)
        except Exception:
            LOG.exception("koha lookup failed")
            return 503, {"error": "koha_unavailable"}
        if owed <= 0:
            return 409, {"error": "nothing_owed"}
        if owed > self.cfg.max_amount:
            return 409, {"error": "amount_over_limit", "max": f"{self.cfg.max_amount:.2f}"}
        txid = uuid.uuid4().hex  # 32 alphanumeric characters, within the BCB 26-35 rule
        try:
            pix = self.provider.create_charge(txid, owed, "Multas Biblioteca", self.cfg.charge_ttl)
        except Exception:
            LOG.exception("pix provider failed")
            return 503, {"error": "pix_unavailable"}
        self.store.insert(txid, patron_id, owed)
        LOG.info("charge created txid=%s amount=%s", txid, owed)
        return 200, {"txid": txid, "amount": f"{owed:.2f}", "copia_cola": pix["copia_cola"],
                     "qr_base64": pix["qr_base64"], "expires_in": self.cfg.charge_ttl}

    def handle_webhook(self, raw: bytes, signature: str | None) -> tuple[int, dict]:
        if not verify_signature(self.cfg.webhook_secret, raw, signature or ""):
            LOG.warning("webhook rejected: bad signature")
            return 401, {"error": "bad_signature"}
        try:
            event = json.loads(raw)
            txid = str(event.get("txid", ""))
        except (ValueError, AttributeError):
            return 400, {"error": "bad_json"}
        if not TXID_RE.match(txid):
            return 400, {"error": "bad_txid"}
        charge = self.store.get(txid)
        if charge is None:
            LOG.warning("webhook for unknown txid=%s", txid)
            return 404, {"error": "unknown_charge"}
        patron_id, amount_cents, _status = charge
        if event.get("status") != PAID_STATUS:
            return 200, {"result": "ignored"}
        try:
            paid = Decimal(str(event.get("valor"))).quantize(CENT, ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return 400, {"error": "bad_amount"}
        if paid != Decimal(amount_cents) / 100:
            self.store.set_status(txid, "amount_mismatch")
            LOG.error("amount mismatch txid=%s", txid)
            return 409, {"error": "amount_mismatch"}
        if not self.store.claim(txid):
            return 200, {"result": "already_processed"}
        try:
            self.koha.credit(patron_id, paid, f"Pix {txid}", f"Pix txid {txid} (Koha.Nexus)")
        except Exception:
            self.store.set_status(txid, "credit_failed")
            LOG.exception("credit failed txid=%s; bank retry will re-attempt", txid)
            return 500, {"error": "credit_failed"}  # non-2xx makes the bank retry
        self.store.set_status(txid, "credited", paid_at=int(self.clock()))
        LOG.info("credited txid=%s", txid)
        return 200, {"result": "credited"}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "nexus-pix"

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> bytes | None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._send(413, {"error": "too_large"})
                return None
            return self.rfile.read(length)

        def do_POST(self):
            if self.path == "/nexus-pix/charges":
                if self._body() is None:
                    return
                status, payload = app.create_charge(self.headers.get("Cookie"))
            elif self.path == "/nexus-pix/webhook":
                raw = self._body()
                if raw is None:
                    return
                status, payload = app.handle_webhook(raw, self.headers.get("X-Signature"))
            else:
                status, payload = 404, {"error": "not_found"}
            self._send(status, payload)

        def log_message(self, fmt, *args):  # keep cookies and bodies out of the logs
            LOG.info("%s %s", self.command, self.path.split("?")[0])

    return Handler


def build_app(cfg: Config) -> App:
    return App(cfg, KohaClient(cfg), PixProvider(cfg), Store(cfg.db_path))


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        cfg = Config.from_env()
    except ValueError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    if "--check" in argv:
        print("config ok")
        return 0
    app = build_app(cfg)
    server = ThreadingHTTPServer((cfg.listen_host, cfg.listen_port), make_handler(app))
    LOG.info("listening on %s:%s", cfg.listen_host, cfg.listen_port)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
