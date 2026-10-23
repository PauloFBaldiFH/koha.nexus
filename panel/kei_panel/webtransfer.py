"""Backups between this server and the person's computer through their own
browser, when the panel runs over SSH (a VPS, a remote server): a file
dropped on the terminal is only a path of the other computer, and the
Downloads folder is there too, so the panel cannot reach either.

While the transfer screen is open the panel serves one page:

  https://SERVER:8765/t/TOKEN/

  upload    the person picks or drops the backup on the page; the browser
            sends it in pieces (PUT .../chunk, each one at the offset the
            server already has, so a lost answer is just sent again) and
            computes its SHA-256 as it goes; POST .../finish compares the
            size and the SHA-256 the server computed while writing. Only
            then FILE.part becomes FILE in the receiving folder.
  download  the page shows the backup's name, size and SHA-256 and a link
            (GET .../file) that the browser saves in Downloads.

  TLS       a self-signed certificate made by openssl for this run only (the
            browser warns once; the panel shows its SHA-256 fingerprint);
            the backup holds patrons' data, so it never goes in clear text.
  TOKEN     128 random bits in the address: anything else gets 404.
  ufw       when it is active the port is opened while the screen is open
            and closed after (a rule the person already had is kept). A
            firewall of the VPS provider is out of reach: the screen also
            shows the ssh -L tunnel, which needs no open port.

Nothing listens once the screen is closed (stop()).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import transfer

DEFAULT_PORT = 8765
PORT_TRIES = 10
CHUNK = 4 * 1024 * 1024          # what the page sends at a time
MAX_CHUNK = 16 * 1024 * 1024     # the most one request may carry
SPARE = 64 * 1024 * 1024         # disk left free after an upload


class TransferError(Exception):
    """The page cannot be served (no openssl, no free port...)."""


# ----------------------------------------------------------------------
# Addresses, certificate, firewall
# ----------------------------------------------------------------------
def addresses(ssh_connection: str | None, server_ip: str | None) -> list[str]:
    """The addresses the person's computer may use for this server: the one
    it reached over SSH (third field of SSH_CONNECTION), then the one the
    installer knows; unique, IPv6 in brackets."""
    found: list[str] = []
    parts = (ssh_connection or "").split()
    for raw in ([parts[2]] if len(parts) >= 3 else []) + [server_ip or ""]:
        raw = raw.strip().strip("[]")
        if not raw:
            continue
        try:
            ip = ipaddress.ip_address(raw.split("%")[0])
            host = f"[{ip}]" if ip.version == 6 else str(ip)
        except ValueError:
            host = raw
        if host not in found:
            found.append(host)
    return found


def make_certificate(folder: Path, hosts: list[str], run=subprocess.run) -> tuple[Path, Path]:
    """A self-signed certificate (one day) for hosts, made by openssl."""
    openssl = shutil.which("openssl")
    if not openssl:
        raise TransferError("openssl not found")
    names = []
    for host in hosts:
        bare = host.strip("[]")
        try:
            ipaddress.ip_address(bare)
            names.append(f"IP:{bare}")
        except ValueError:
            names.append(f"DNS:{bare}")
    names.append("IP:127.0.0.1")
    cert, key = folder / "cert.pem", folder / "key.pem"
    argv = [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "1",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=Koha Nexus transfer",
            "-addext", "subjectAltName=" + ",".join(dict.fromkeys(names))]
    done = run(argv, capture_output=True, text=True, timeout=60)
    if done.returncode != 0 or not cert.is_file():
        raise TransferError((done.stderr or "openssl failed").strip().splitlines()[-1])
    os.chmod(key, 0o600)
    return cert, key


def fingerprint(cert: Path) -> str:
    """The certificate's SHA-256 as browsers show it (AB:CD:...)."""
    der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))


def ufw_open(port: int, run=subprocess.run) -> bool:
    """Opens port in ufw when ufw is active and does not allow it yet. True
    when a rule was added (ufw_close takes it away again)."""
    if not shutil.which("ufw"):
        return False
    try:
        status = run(["ufw", "status"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    if "Status: active" not in status:
        return False
    if any(line.split()[:1] in ([f"{port}/tcp"], [str(port)]) and "ALLOW" in line
           for line in status.splitlines()):
        return False
    try:
        return run(["ufw", "allow", f"{port}/tcp"], capture_output=True, text=True,
                   timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ufw_close(port: int, run=subprocess.run) -> None:
    try:
        run(["ufw", "delete", "allow", f"{port}/tcp"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


def file_sha256(path: Path, stop: threading.Event | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            if stop is not None and stop.is_set():
                return ""
            h.update(chunk)
    return h.hexdigest()


def safe_name(name: str) -> str:
    """The file name the browser sent, without folders or control characters."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if c >= " " and c != "\x7f").strip().lstrip(".")
    return name[:200]


# ----------------------------------------------------------------------
# The upload being received
# ----------------------------------------------------------------------
class Upload:
    """One file arriving in pieces: FILE.part, the bytes written so far and
    their SHA-256. Finished only when size and SHA-256 match the browser's."""

    def __init__(self, folder: Path, name: str, size: int):
        self.folder, self.name, self.size = folder, name, size
        self.part = folder / f".{name}.part"
        self.written = 0
        self.hasher = hashlib.sha256()
        self.started = time.monotonic()
        folder.mkdir(parents=True, exist_ok=True)
        with open(self.part, "wb"):
            pass
        os.chmod(self.part, 0o600)

    def write(self, data: bytes) -> None:
        with open(self.part, "ab") as f:
            f.write(data)
        self.hasher.update(data)
        self.written += len(data)

    def finish(self, sha256: str) -> Path:
        if self.written != self.size:
            raise ValueError(f"size: {self.written} received, {self.size} expected")
        if not hmac.compare_digest(self.hasher.hexdigest(), (sha256 or "").strip().lower()):
            raise ValueError("SHA-256 does not match")
        target = transfer.free_target(self.folder, self.name)
        os.replace(self.part, target)
        return target

    def drop(self) -> None:
        try:
            self.part.unlink()
        except OSError:
            pass


# ----------------------------------------------------------------------
# The server
# ----------------------------------------------------------------------
class TransferServer:
    """mode "upload" (into folder) or "download" (of file). start() makes
    the certificate, binds the port and serves in a thread; state() is read
    by the screen; stop() closes everything."""

    def __init__(self, mode: str, folder: Path | None = None, file: Path | None = None,
                 hosts: list[str] | None = None, port: int = DEFAULT_PORT, bind: str = "0.0.0.0",
                 texts: dict[str, str] | None = None, tls: bool = True, firewall: bool = True):
        if mode not in ("upload", "download"):
            raise ValueError(mode)
        self.mode, self.folder, self.file = mode, folder, file
        self.hosts = hosts or []
        self.port, self.bind, self.tls, self.firewall = port, bind, tls, firewall
        self.texts = texts or {}
        self.token = secrets.token_urlsafe(16)
        self.cert_fingerprint = ""
        self.sha256 = ""                   # of the file offered (download)
        self.upload: Upload | None = None
        self.received: Path | None = None
        self.error = ""
        self.downloads = 0
        self.sent = 0
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._httpd: ThreadingHTTPServer | None = None
        self._tmp: Path | None = None
        self._ufw = False

    # -- life ---------------------------------------------------------
    def start(self) -> None:
        ctx = None
        if self.tls:
            self._tmp = Path(tempfile.mkdtemp(prefix="koha-transfer-"))
            cert, key = make_certificate(self._tmp, self.hosts)
            self.cert_fingerprint = fingerprint(cert)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(str(cert), str(key))
        self._httpd = self._bind(ctx)
        self.port = self._httpd.server_address[1]
        if self.firewall:
            self._ufw = ufw_open(self.port)
        threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.3},
                         daemon=True, name="koha-transfer").start()
        if self.mode == "download" and self.file is not None:
            threading.Thread(target=self._hash_offered, daemon=True).start()

    def _bind(self, ctx) -> ThreadingHTTPServer:
        owner = self
        handler = type("Handler", (_Handler,), {"owner": owner})

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

            def finish_request(self, request, client_address):
                # The TLS handshake runs here, in the request's own thread:
                # a slow or refused handshake never holds the others.
                request.settimeout(60)
                if ctx is not None:
                    try:
                        request = ctx.wrap_socket(request, server_side=True)
                    except (ssl.SSLError, OSError):
                        return
                super().finish_request(request, client_address)

            def handle_error(self, request, client_address):
                pass

        last: OSError | None = None
        tries = 1 if self.port == 0 else PORT_TRIES
        for port in range(self.port, self.port + tries):
            try:
                return Server((self.bind, port), handler)
            except OSError as e:
                last = e
        raise TransferError(f"no free port from {self.port}: {last}")

    def _hash_offered(self) -> None:
        digest = file_sha256(self.file, self._stop)
        with self.lock:
            self.sha256 = digest

    def stop(self) -> None:
        self._stop.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._ufw:
            ufw_close(self.port)
            self._ufw = False
        with self.lock:
            if self.upload is not None and self.received is None:
                self.upload.drop()
            self.upload = None
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    # -- what the screen shows -------------------------------------------
    def path(self) -> str:
        return f"/t/{self.token}/"

    def urls(self) -> list[str]:
        scheme = "https" if self.tls else "http"
        return [f"{scheme}://{host}:{self.port}{self.path()}" for host in self.hosts]

    def tunnel_url(self) -> str:
        return f"{'https' if self.tls else 'http'}://127.0.0.1:{self.port}{self.path()}"

    def state(self) -> dict:
        with self.lock:
            up = self.upload
            return {"name": up.name if up else "", "done": up.written if up else 0,
                    "total": up.size if up else 0, "received": self.received, "error": self.error,
                    "downloads": self.downloads, "sent": self.sent, "sha256": self.sha256}

    # -- requests -------------------------------------------------------
    def begin(self, name: str, size: int) -> int:
        """The offset to send from: 0 for a new file, what was already
        written when the same file is sent again (a reloaded page)."""
        name = safe_name(name)
        if not transfer.is_backup_name(name):
            raise PermissionError("not a backup")
        if size <= 0:
            raise ValueError("empty file")
        with self.lock:
            if self.received is not None:
                raise PermissionError("a file was already received")
            up = self.upload
            if up is not None and up.name == name and up.size == size:
                return up.written
            self.folder.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(self.folder).free
            if size + SPARE > free:
                raise OSError(f"not enough free space: {size} needed, {free} free")
            if up is not None:
                up.drop()
            self.upload = Upload(self.folder, name, size)
            self.error = ""
            return 0

    def chunk(self, name: str, size: int, offset: int, data: bytes) -> int:
        with self.lock:
            up = self.upload
            if up is None or up.name != safe_name(name) or up.size != size:
                raise LookupError("no such upload")
            if offset != up.written:
                return up.written
            if up.written + len(data) > up.size:
                raise ValueError("more data than the size")
            up.write(data)
            return up.written

    def finish(self, name: str, size: int, sha256: str) -> Path:
        with self.lock:
            up = self.upload
            if up is None or up.name != safe_name(name) or up.size != size:
                raise LookupError("no such upload")
            try:
                target = up.finish(sha256)
            except ValueError as e:
                up.drop()
                self.upload = None
                self.error = str(e)
                raise
            self.received = target
            return target


class _Handler(BaseHTTPRequestHandler):
    owner: TransferServer
    server_version = "KohaNexus"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):    # noqa: A002 - nothing may reach the panel's terminal
        pass

    def _route(self) -> tuple[str | None, dict]:
        """What follows /t/TOKEN/ ("" for the page), None for anything else."""
        url = urlparse(self.path)
        prefix = f"/t/{self.owner.token}/"
        if url.path == prefix[:-1]:
            return "/", {}
        if not hmac.compare_digest(url.path[:len(prefix)].encode(), prefix.encode()):
            return None, {}
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        return url.path[len(prefix):], query

    def _send(self, code: int, body: bytes, kind: str = "application/json; charset=utf-8",
              extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data).encode())

    def _not_found(self) -> None:
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def _int(self, query: dict, key: str) -> int:
        try:
            return int(query.get(key, ""))
        except ValueError:
            return -1

    def do_GET(self):  # noqa: N802
        route, query = self._route()
        owner = self.owner
        if route == "/":
            self._send(301, b"", "text/plain", {"Location": owner.path()})
        elif route == "":
            self._send(200, page(owner).encode(), "text/html; charset=utf-8",
                       {"Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; "
                                                   "style-src 'unsafe-inline'; connect-src 'self'"})
        elif route == "info" and owner.mode == "download":
            with owner.lock:
                digest = owner.sha256
            self._json(200, {"sha256": digest})
        elif route == "status" and owner.mode == "upload":
            try:
                offset = owner.begin(query.get("name", ""), self._int(query, "size"))
            except PermissionError as e:
                self._json(403, {"error": str(e)})
            except (OSError, ValueError) as e:
                self._json(400, {"error": str(e)})
            else:
                self._json(200, {"offset": offset, "chunk": CHUNK})
        elif route == "file" and owner.mode == "download":
            self._file()
        else:
            self._not_found()

    def _file(self) -> None:
        src = self.owner.file
        try:
            size = src.stat().st_size
            f = open(src, "rb")
        except OSError:
            self._not_found()
            return
        with f:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(src.name)}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            sent = 0
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                self.wfile.write(chunk)
                sent += len(chunk)
                with self.owner.lock:
                    self.owner.sent = sent
        if sent == size:
            with self.owner.lock:
                self.owner.downloads += 1

    def _drain(self) -> None:
        """The body of a request that is refused, read and thrown away: a
        connection closed with unread data is reset before the answer."""
        length = self._int({"n": self.headers.get("Content-Length", "")}, "n")
        if 0 < length <= MAX_CHUNK:
            self.rfile.read(length)
        else:
            self.close_connection = True

    def do_PUT(self):  # noqa: N802
        route, query = self._route()
        if route != "chunk" or self.owner.mode != "upload":
            self._drain()
            self._not_found()
            return
        length = self._int({"n": self.headers.get("Content-Length", "")}, "n")
        if length < 0 or length > MAX_CHUNK:
            self.close_connection = True
            self._json(413, {"error": "chunk too large"})
            return
        data = self.rfile.read(length)
        if len(data) != length:
            return
        try:
            offset = self.owner.chunk(query.get("name", ""), self._int(query, "size"),
                                      self._int(query, "offset"), data)
        except (LookupError, ValueError, OSError) as e:
            self._json(409, {"error": str(e)})
            return
        self._json(200, {"offset": offset})

    def do_POST(self):  # noqa: N802
        route, query = self._route()
        if route != "finish" or self.owner.mode != "upload":
            self._drain()
            self._not_found()
            return
        try:
            target = self.owner.finish(query.get("name", ""), self._int(query, "size"), query.get("sha256", ""))
        except (LookupError, ValueError, OSError) as e:
            self._json(409, {"error": str(e)})
            return
        self._json(200, {"ok": True, "name": target.name})


# ----------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------
PAGE_TEXTS = {
    "title": "Koha Nexus: backup transfer",
    "pick": "Choose or drop the backup file here (.sql, .sql.gz, .sql.bz2, .sql.xz, .sql.zst)",
    "not_backup": "This is not a Koha backup (.sql, .sql.gz, .sql.bz2, .sql.xz or .sql.zst).",
    "sending": "Sending",
    "checking": "Checking size and SHA-256...",
    "done": "Received and checked. Go back to the panel: the restore continues there.",
    "failed": "The transfer failed:",
    "retry": "Connection lost, trying again...",
    "download": "Download the backup",
    "calculating": "calculating...",
    "keep_open": "Keep the panel's transfer screen open until the transfer ends.",
}


def page(owner: TransferServer) -> str:
    texts = {**PAGE_TEXTS, **owner.texts}
    info = {"mode": owner.mode, "texts": texts, "chunk": CHUNK, "suffixes": list(transfer.BACKUP_SUFFIXES)}
    if owner.mode == "download" and owner.file is not None:
        info.update(name=owner.file.name, size=owner.file.stat().st_size, sha256=owner.sha256)
    data = json.dumps(info).replace("<", "\\u003c")
    return _PAGE.replace("__TITLE__", _html(texts["title"])).replace("__DATA__", data)


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f4f6f8;--fg:#1d2733;--card:#fff;--line:#c9d2dc;--acc:#1f6feb;--ok:#1a7f37;--bad:#cf222e}
@media (prefers-color-scheme: dark){:root{--bg:#0d1117;--fg:#e6edf3;--card:#161b22;--line:#30363d;--acc:#4493f8;--ok:#3fb950;--bad:#f85149}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:24px 16px}
h1{font-size:1.3rem}
#drop{display:block;border:2px dashed var(--line);border-radius:12px;background:var(--card);padding:40px 16px;text-align:center;cursor:pointer}
#drop.over{border-color:var(--acc)}
#drop input{display:none}
progress{width:100%;height:18px;margin-top:16px}
.ok{color:var(--ok)}.bad{color:var(--bad)}
code{word-break:break-all;font-size:.85rem}
a.button{display:inline-block;background:var(--acc);color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none}
.muted{opacity:.75;font-size:.9rem}
</style></head><body><main>
<h1 id="title"></h1>
<div id="box"></div>
<p id="msg"></p>
<p class="muted" id="hint"></p>
</main>
<script>
"use strict";
const D = __DATA__, T = D.texts;
const $ = (id) => document.getElementById(id);
$("title").textContent = T.title;
$("hint").textContent = T.keep_open;

function human(n) {
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < 3) { n /= 1024; i++; }
  return (i ? n.toFixed(1) : n.toFixed(0)) + " " + u[i];
}

// SHA-256 computed piece by piece (crypto.subtle has no incremental API and
// is missing on some browsers for a self-signed page).
const K = new Uint32Array([
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
class Sha256 {
  constructor() {
    this.h = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
    this.buf = new Uint8Array(64); this.n = 0; this.len = 0; this.w = new Uint32Array(64);
  }
  block(d, o) {
    const w = this.w, h = this.h;
    for (let i = 0; i < 16; i++) w[i] = (d[o+4*i] << 24) | (d[o+4*i+1] << 16) | (d[o+4*i+2] << 8) | d[o+4*i+3];
    for (let i = 16; i < 64; i++) {
      const a = w[i-15], b = w[i-2];
      const s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3);
      const s1 = ((b >>> 17) | (b << 15)) ^ ((b >>> 19) | (b << 13)) ^ (b >>> 10);
      w[i] = (w[i-16] + s0 + w[i-7] + s1) | 0;
    }
    let A = h[0], B = h[1], C = h[2], E = h[3], F = h[4], G = h[5], H = h[6], I = h[7];
    for (let i = 0; i < 64; i++) {
      const S1 = ((F >>> 6) | (F << 26)) ^ ((F >>> 11) | (F << 21)) ^ ((F >>> 25) | (F << 7));
      const ch = (F & G) ^ (~F & H);
      const t1 = (I + S1 + ch + K[i] + w[i]) | 0;
      const S0 = ((A >>> 2) | (A << 30)) ^ ((A >>> 13) | (A << 19)) ^ ((A >>> 22) | (A << 10));
      const mj = (A & B) ^ (A & C) ^ (B & C);
      const t2 = (S0 + mj) | 0;
      I = H; H = G; G = F; F = (E + t1) | 0; E = C; C = B; B = A; A = (t1 + t2) | 0;
    }
    h[0] += A; h[1] += B; h[2] += C; h[3] += E; h[4] += F; h[5] += G; h[6] += H; h[7] += I;
  }
  update(d) {
    let i = 0; this.len += d.length;
    if (this.n) {
      while (this.n < 64 && i < d.length) this.buf[this.n++] = d[i++];
      if (this.n < 64) return;
      this.block(this.buf, 0); this.n = 0;
    }
    for (; i + 64 <= d.length; i += 64) this.block(d, i);
    while (i < d.length) this.buf[this.n++] = d[i++];
  }
  hex() {
    const bits = this.len * 8, tail = new Uint8Array((this.n < 56 ? 64 : 128) - this.n);
    tail[0] = 0x80;
    const hi = Math.floor(bits / 4294967296), lo = bits >>> 0, e = tail.length;
    tail[e-8] = hi >>> 24; tail[e-7] = hi >>> 16; tail[e-6] = hi >>> 8; tail[e-5] = hi;
    tail[e-4] = lo >>> 24; tail[e-3] = lo >>> 16; tail[e-2] = lo >>> 8; tail[e-1] = lo;
    this.update(tail);
    return Array.from(this.h, (x) => x.toString(16).padStart(8, "0")).join("");
  }
}
window.Sha256 = Sha256;

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function call(method, route, params, body) {
  const q = new URLSearchParams(params).toString();
  for (let tries = 0; ; tries++) {
    try {
      const r = await fetch(route + "?" + q, {method, body, cache: "no-store"});
      const j = await r.json().catch(() => ({}));
      if (r.ok || r.status < 500) return [r.status, j];
    } catch (e) { /* network: try again */ }
    if (tries >= 30) throw new Error("network");
    $("msg").textContent = T.retry;
    await wait(Math.min(1000 * (tries + 1), 10000));
  }
}

async function send(file) {
  const msg = $("msg");
  if (!D.suffixes.some((s) => file.name.toLowerCase().endsWith(s))) {
    msg.className = "bad"; msg.textContent = T.not_backup; return;
  }
  const bar = document.createElement("progress"); bar.max = file.size; bar.value = 0;
  $("box").replaceChildren(bar);
  const base = {name: file.name, size: String(file.size)};
  let [code, j] = await call("GET", "status", base);
  if (code !== 200) { msg.className = "bad"; msg.textContent = T.failed + " " + (j.error || code); return; }
  const hash = new Sha256(), chunk = j.chunk || D.chunk, t0 = Date.now();
  let hashed = 0, offset = j.offset || 0;
  async function hashTo(end) {          // what the server already has
    while (hashed < end) {
      const stop = Math.min(end, hashed + chunk);
      hash.update(new Uint8Array(await file.slice(hashed, stop).arrayBuffer()));
      hashed = stop;
    }
  }
  while (offset < file.size) {
    await hashTo(offset);
    const piece = file.slice(offset, Math.min(file.size, offset + chunk));
    [code, j] = await call("PUT", "chunk", {...base, offset: String(offset)}, piece);
    if (code !== 200) { msg.className = "bad"; msg.textContent = T.failed + " " + (j.error || code); return; }
    offset = j.offset;
    bar.value = offset;
    const secs = (Date.now() - t0) / 1000, speed = secs > 0 ? offset / secs : 0;
    msg.className = ""; msg.textContent = T.sending + " " + file.name + ": " + human(offset) + " / " +
      human(file.size) + (speed ? " · " + human(speed) + "/s" : "");
  }
  await hashTo(file.size);
  msg.textContent = T.checking;
  [code, j] = await call("POST", "finish", {...base, sha256: hash.hex()});
  if (code === 200) { msg.className = "ok"; msg.textContent = T.done; }
  else { msg.className = "bad"; msg.textContent = T.failed + " " + (j.error || code); }
}

if (D.mode === "upload") {
  const label = document.createElement("label"); label.id = "drop";
  const input = document.createElement("input"); input.type = "file";
  input.accept = D.suffixes.join(",") + ",.gz,.bz2,.xz,.zst";
  label.append(T.pick, input);
  $("box").append(label);
  input.addEventListener("change", () => input.files[0] && send(input.files[0]));
  for (const ev of ["dragenter", "dragover"]) document.addEventListener(ev, (e) => { e.preventDefault(); label.classList.add("over"); });
  document.addEventListener("dragleave", () => label.classList.remove("over"));
  document.addEventListener("drop", (e) => {
    e.preventDefault(); label.classList.remove("over");
    const f = e.dataTransfer.files[0]; if (f) send(f);
  });
} else {
  const a = document.createElement("a"); a.className = "button"; a.href = "file"; a.textContent = T.download;
  const p = document.createElement("p"); p.textContent = D.name + " · " + human(D.size);
  const sum = document.createElement("p"); sum.className = "muted";
  const show = (s) => { sum.replaceChildren("SHA-256: ", Object.assign(document.createElement("code"), {textContent: s || T.calculating})); };
  show(D.sha256);
  $("box").append(p, a, sum);
  (async () => { while (!D.sha256) { await wait(2000); try { D.sha256 = (await (await fetch("info")).json()).sha256; } catch (e) {} show(D.sha256); } })();
}
</script></body></html>
"""
