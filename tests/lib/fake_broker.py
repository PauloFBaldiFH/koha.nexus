#!/usr/bin/env python3
"""A stand-in for the free address service (broker/), for tests/tainacan_free.bats.

Only the answers the installer reads, in the shapes of broker/src/api.ts. It
keeps one library and logs every request (method, path, whether it was
signed, body) to DIR/broker.log. The real service is tested in broker/
(vitest and test/e2e). Usage: fake_broker.py DIR; the port goes to DIR/port.
A file DIR/old makes it a service without collection addresses (404 on
/v1/capabilities, as before migration 0003).
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DIR = sys.argv[1]
ZONE = "example.org"
STATE = {"slug": None, "services": [], "requested": []}


def hostnames():
    slug, s = STATE["slug"], STATE["services"]
    out = {}
    if "koha" in s:
        out.update(opac=f"t-{slug}.{ZONE}", staff=f"t-{slug}-admin.{ZONE}")
    if "tainacan" in s:
        out["collection"] = f"t-{slug}-acervo.{ZONE}"
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def answer(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        signed = "signed" if self.headers.get("X-KEI-Signature") else "unsigned"
        with open(os.path.join(DIR, "broker.log"), "a") as log:
            log.write(f"{self.command} {self.path} {signed} {raw}\n")
        body = json.loads(raw) if raw else {}
        route = (self.command, self.path)
        if route == ("GET", "/v1/capabilities"):
            if os.path.exists(os.path.join(DIR, "old")):
                return self.answer(404, {"error": "not found"})
            return self.answer(200, {"services": ["koha", "tainacan"], "collection_suffix": "-acervo"})
        if route == ("POST", "/v1/device/start"):
            STATE["requested"] = body.get("services") or ["koha"]
            STATE["slug"] = body.get("requested_name") or "biblioteca"
            return self.answer(201, {"device_code": "dev-code-1", "user_code": "ABCD-EFGH",
                                     "verification_uri": "https://broker.example.org/join?c=ABCD-EFGH",
                                     "suggested_slug": STATE["slug"], "status": "approved"})
        if route == ("POST", "/v1/enroll"):
            STATE["services"] = list(STATE["requested"])
            return self.answer(201, {"library_id": "lib-1", "job_id": "job-1", "hostnames": hostnames()})
        if signed != "signed":
            return self.answer(401, {"error": "unsigned"})
        if route == ("GET", "/v1/jobs/job-1"):
            return self.answer(200, {"state": "done"})
        if route == ("GET", "/v1/tunnel-token"):
            return self.answer(200, {"tunnel_token": "tunnel-token-0123456789abcdefghij"})
        if route == ("GET", "/v1/library"):
            return self.answer(200, {"id": "lib-1", "services": STATE["services"], "hostnames": hostnames(),
                                     "staff_remote_access": False, "public_listing": False})
        if route == ("PUT", "/v1/services"):
            wanted = [s for s in STATE["services"] if s != "tainacan"] + (["tainacan"] if body.get("tainacan") else [])
            if not wanted:
                return self.answer(409, {"error": "a library needs at least one service"})
            STATE["services"] = wanted
            return self.answer(200, {"services": wanted, "hostnames": hostnames()})
        if route == ("PUT", "/v1/listing"):
            return self.answer(200, {"public_listing": body.get("public")})
        if route == ("DELETE", "/v1/library"):
            STATE["services"] = []
            return self.answer(200, {"released": True})
        return self.answer(404, {"error": "not found"})

    do_GET = do_POST = do_PUT = do_DELETE = handle_any


def main():
    # A library this test already has (Koha on a free address): seeded by DIR/seed.
    seed = os.path.join(DIR, "seed")
    if os.path.exists(seed):
        with open(seed) as f:
            slug, services = f.read().split()
        STATE.update(slug=slug, services=services.split(","))
    server = HTTPServer(("127.0.0.1", 0), Handler)
    with open(os.path.join(DIR, "port.tmp"), "w") as f:
        f.write(str(server.server_port))
    os.rename(os.path.join(DIR, "port.tmp"), os.path.join(DIR, "port"))
    server.serve_forever()


if __name__ == "__main__":
    main()
