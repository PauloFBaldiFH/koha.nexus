// End-to-end run of the bundled Worker in local workerd (Miniflare) with a
// fake Cloudflare API: enrollment, provisioning through the queue and the
// Durable Object, signed calls (signed by scripts/kei-sign.sh), the staff
// gate, suspension, rotation, reconciliation and removal.
//
//   npm run test:e2e     (builds first with `npm run build:local`)

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ADMIN_TOKEN, BROKER_DIR, rawRequest, startBroker } from "./harness.mjs";

const SIGNER = join(BROKER_DIR, "scripts/kei-sign.sh");
const tmp = mkdtempSync(join(tmpdir(), "kei-e2e-"));
const KEY = join(tmp, "lib.key");

let passed = 0;
async function step(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ok  ${name}`);
  } catch (e) {
    console.error(`  FAIL ${name}`);
    throw e;
  }
}

const b = await startBroker();
const { url: B, fake, settle } = b;
const admin = { Authorization: `Bearer ${ADMIN_TOKEN}` };

async function call(method, path, { body, headers = {} } = {}) {
  const res = await fetch(`${B}${path}`, {
    method,
    headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
  });
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  return { status: res.status, json, text, headers: res.headers };
}

function signHeaders(libraryId, method, path, body) {
  const args = [SIGNER, "headers", KEY, libraryId, method, path];
  if (body !== undefined) {
    const f = join(tmp, "body.json");
    writeFileSync(f, body);
    args.push(f);
  }
  const out = execFileSync("bash", args, { encoding: "utf8" });
  return Object.fromEntries(
    out
      .trim()
      .split("\n")
      .map((l) => [l.slice(0, l.indexOf(":")), l.slice(l.indexOf(":") + 1).trim()]),
  );
}

async function signed(libraryId, method, path, body) {
  const raw = body === undefined ? undefined : JSON.stringify(body);
  return call(method, path, { body: raw, headers: signHeaders(libraryId, method, path, raw) });
}

const STAFF_HOST = "t-palotina-pr-admin.example.org";
const gate = (headers = {}, path = "/cgi-bin/koha/mainpage.pl") => rawRequest(`${B}${path}`, { headers: { Host: STAFF_HOST, ...headers } });
const basic = (u, p) => ({ Authorization: `Basic ${Buffer.from(`${u}:${p}`).toString("base64")}` });

let start, lib, job;

try {
  console.log(`broker e2e on ${B}`);

  await step("service answers and unknown paths are JSON 404", async () => {
    assert.equal((await call("GET", "/")).status, 200);
    const r = await call("GET", "/nope");
    assert.equal(r.status, 404);
    assert.equal(r.json.error, "not found");
    assert.equal((await call("GET", "/v1/enroll")).status, 405);
  });

  await step("device/start approves at once under the requested name", async () => {
    const r = await call("POST", "/v1/device/start", {
      body: { institution_name: "Biblioteca Pública Municipal de Palotina", contact_email: "biblioteca@palotina.pr.gov.br", requested_name: "Palotina PR" },
    });
    assert.equal(r.status, 200, r.text);
    assert.equal(r.json.status, "approved");
    assert.equal(r.json.suggested_slug, "palotina-pr");
    assert.deepEqual(r.json.hostnames, { opac: "t-palotina-pr.example.org", staff: STAFF_HOST });
    assert.match(r.json.verification_uri, /^https:\/\/broker\.example\.org\/join\?c=[A-Z]{4}-[A-Z]{4}$/);
    start = r.json;
  });

  await step("device/start validates input", async () => {
    const r = await call("POST", "/v1/device/start", { body: { institution_name: "x", contact_email: "a@b.org" } });
    assert.equal(r.status, 400);
  });

  await step("device/poll and the /join page show the approval", async () => {
    const r = await call("POST", "/v1/device/poll", { body: { device_code: start.device_code } });
    assert.equal(r.json.status, "approved");
    const page = await call("GET", `/join?c=${start.user_code}`);
    assert.equal(page.status, 200);
    assert.match(page.text, /approved/);
  });

  await step("enroll binds the key and queues provisioning; the code is single use", async () => {
    execFileSync("bash", [SIGNER, "keygen", KEY]);
    const pub = execFileSync("bash", [SIGNER, "pubkey", KEY], { encoding: "utf8" }).trim();
    assert.equal((await call("POST", "/v1/enroll", { body: { device_code: start.device_code, public_key: "abc" } })).status, 400);
    const r = await call("POST", "/v1/enroll", { body: { device_code: start.device_code, public_key: pub } });
    assert.equal(r.status, 202, r.text);
    lib = r.json.library_id;
    job = r.json.job_id;
    assert.equal(r.json.hostnames.opac, "t-palotina-pr.example.org");
    assert.equal((await call("POST", "/v1/enroll", { body: { device_code: start.device_code, public_key: pub } })).status, 409);
  });

  await step("the queue runs the job: tunnel, ingress and two proxied CNAMEs", async () => {
    assert.ok(await settle(), "job did not finish");
    const r = await signed(lib, "GET", `/v1/jobs/${job}`);
    assert.equal(r.status, 200, r.text);
    assert.equal(r.json.state, "done");
    assert.equal(r.json.library_status, "active");
    const s = fake.snapshot();
    assert.equal(s.tunnels.length, 1);
    assert.equal(s.tunnels[0].name, `kei-lib-${lib}`);
    assert.equal(s.tunnels[0].ingress.length, 3);
    assert.equal(s.dns_records.length, 2);
    for (const rec of s.dns_records) {
      assert.equal(rec.type, "CNAME");
      assert.equal(rec.proxied, true);
      assert.equal(rec.comment, `kei:lib:${lib}`);
      assert.equal(rec.content, `${s.tunnels[0].id}.cfargotunnel.com`);
    }
  });

  let token;
  await step("signed tunnel-token returns the live token; replay and unsigned calls fail", async () => {
    const h = signHeaders(lib, "GET", "/v1/tunnel-token");
    const r = await call("GET", "/v1/tunnel-token", { headers: h });
    assert.equal(r.status, 200, r.text);
    assert.match(r.json.tunnel_token, /^tunnel-token-for-/);
    token = r.json.tunnel_token;
    assert.equal((await call("GET", "/v1/tunnel-token", { headers: h })).status, 401, "replay");
    assert.equal((await call("GET", "/v1/tunnel-token")).status, 401, "unsigned");
    const info = await signed(lib, "GET", "/v1/library");
    assert.equal(info.json.slug, "palotina-pr");
    assert.equal(info.json.staff_remote_access, false);
  });

  await step("staff gate is closed (403) before credentials are set; OPAC hosts are not gated", async () => {
    assert.equal((await gate()).status, 403);
    assert.equal((await gate(basic("biblioteca", "uma senha bem longa"))).status, 403);
    const opac = await rawRequest(`${B}/`, { headers: { Host: "t-palotina-pr.example.org" } });
    assert.equal(opac.status, 200); // the API answers; in production OPAC hosts do not route to the Worker
  });

  await step("signed PUT /v1/staff-credentials turns remote access on", async () => {
    const bad = await signed(lib, "PUT", "/v1/staff-credentials", { username: "biblioteca", password: "curta" });
    assert.equal(bad.status, 400);
    const r = await signed(lib, "PUT", "/v1/staff-credentials", { username: "biblioteca", password: "uma senha bem longa", allow_cidrs: [] });
    assert.equal(r.status, 200, r.text);
    assert.equal(r.json.hostname, STAFF_HOST);
  });

  let cookie;
  await step("staff gate: 401 without or with a wrong password, 200 with the right one", async () => {
    const none = await gate();
    assert.equal(none.status, 401);
    assert.match(none.headers["www-authenticate"], /^Basic /);
    assert.equal((await gate(basic("biblioteca", "errada"))).status, 401);
    const ok = await gate({ ...basic("biblioteca", "uma senha bem longa"), Cookie: "CGISESSID=abc" });
    assert.equal(ok.status, 200, ok.body);
    const seen = JSON.parse(ok.body);
    assert.equal(seen.koha, true);
    assert.equal(seen.host, STAFF_HOST);
    assert.equal(seen.authorization, null, "Koha never sees the gate password");
    assert.equal(seen.cookie, "CGISESSID=abc");
    const sc = [].concat(ok.headers["set-cookie"] ?? []);
    assert.match(sc[0] ?? "", /^__Host-kei_staff=[^;]+; Path=\/; Max-Age=43200; Secure; HttpOnly/);
    cookie = sc[0].split(";")[0];
    const again = await gate({ Cookie: cookie });
    assert.equal(again.status, 200);
    assert.equal(JSON.parse(again.body).cookie, null, "the session cookie is stripped too");
  });

  await step("heartbeat is recorded and visible to the admin", async () => {
    const r = await signed(lib, "POST", "/v1/heartbeat", { koha_version: "24.11.05", installer_version: "1.5.4" });
    assert.equal(r.status, 200, r.text);
    assert.equal((await call("GET", "/admin/libraries")).status, 401);
    const list = await call("GET", "/admin/libraries", { headers: admin });
    assert.equal(list.status, 200);
    const row = list.json.libraries.find((x) => x.id === lib);
    assert.equal(row.installer_version, "1.5.4");
    assert.equal(row.staff_remote_access, 1);
  });

  await step("rotate gives a new tunnel token", async () => {
    const r = await signed(lib, "POST", "/v1/rotate", {});
    assert.equal(r.status, 200, r.text);
    assert.deepEqual(Object.values(fake.snapshot().rotations), [1]);
    const t = await signed(lib, "GET", "/v1/tunnel-token");
    assert.notEqual(t.json.tunnel_token, token);
  });

  await step("admin suspend switches ingress to 503, restore brings it back", async () => {
    const s = await call("POST", `/admin/libraries/${lib}/suspend`, { headers: admin });
    assert.equal(s.status, 200, s.text);
    assert.deepEqual(fake.snapshot().tunnels[0].ingress, [{ service: "http_status:503" }]);
    assert.equal(fake.snapshot().dns_records.length, 2);
    assert.equal((await call("POST", `/admin/libraries/${lib}/suspend`, { headers: admin })).status, 409);
    const r = await call("POST", `/admin/libraries/${lib}/restore`, { headers: admin });
    assert.equal(r.status, 200, r.text);
    assert.equal(fake.snapshot().tunnels[0].ingress.length, 3);
  });

  await step("DELETE /v1/staff-credentials closes the gate and ends sessions", async () => {
    const r = await signed(lib, "DELETE", "/v1/staff-credentials");
    assert.equal(r.status, 200, r.text);
    assert.equal((await gate({ Cookie: cookie })).status, 403);
    assert.equal((await gate(basic("biblioteca", "uma senha bem longa"))).status, 403);
  });

  await step("hourly cron removes orphaned tunnels and records only", async () => {
    const orphan = "deadbeef-0000-4000-8000-000000000000";
    fake.state.tunnels.push({ id: "orphan-tunnel", name: `kei-lib-${orphan}`, created_at: "2020-01-01T00:00:00Z", deleted_at: null, ingress: null });
    fake.state.dns_records.push({ id: "orphan-rec", type: "CNAME", name: "t-gone.example.org", content: "orphan-tunnel.cfargotunnel.com", proxied: true, comment: `kei:lib:${orphan}` });
    const foreign = fake.addForeignRecord("www.example.org", "example.net", "CNAME");
    await b.db.prepare("INSERT INTO nonces (library_id, nonce, expires_at) VALUES ('x', 'old-nonce-0000000', 1)").run();
    const worker = await b.mf.getWorker();
    await worker.scheduled({ cron: "0 * * * *" });
    const deadline = Date.now() + 5000;
    while (fake.state.tunnels.some((t) => t.id === "orphan-tunnel") && Date.now() < deadline) await new Promise((ok) => setTimeout(ok, 100));
    const s = fake.snapshot();
    assert.equal(s.tunnels.length, 1);
    assert.equal(s.tunnels[0].name, `kei-lib-${lib}`);
    assert.ok(!s.dns_records.some((r) => r.id === "orphan-rec"));
    assert.ok(s.dns_records.some((r) => r.id === foreign.id), "foreign record untouched");
    assert.equal(s.dns_records.filter((r) => r.comment === `kei:lib:${lib}`).length, 2);
    for (let i = 0; i < 20; i++) {
      const n = await b.db.prepare("SELECT COUNT(*) AS n FROM nonces WHERE nonce = 'old-nonce-0000000'").first();
      if (!n.n) break;
      await new Promise((ok) => setTimeout(ok, 100));
    }
    assert.equal((await b.db.prepare("SELECT COUNT(*) AS n FROM nonces WHERE nonce = 'old-nonce-0000000'").first()).n, 0);
    fake.state.dns_records = fake.state.dns_records.filter((r) => r.id !== foreign.id);
  });

  await step("DELETE /v1/library removes tunnel and records; the key stops working", async () => {
    const r = await signed(lib, "DELETE", "/v1/library");
    assert.equal(r.status, 202, r.text);
    assert.ok(await settle(), "deprovision job did not finish");
    const s = fake.snapshot();
    assert.deepEqual(s.tunnels, []);
    assert.deepEqual(s.dns_records, []);
    assert.equal((await signed(lib, "GET", "/v1/library")).status, 401);
    assert.equal((await gate()).status, 404);
  });

  await step("a released name is held: the same request gets palotina-pr-2", async () => {
    const r = await call("POST", "/v1/device/start", {
      body: { institution_name: "Biblioteca Pública Municipal de Palotina", contact_email: "biblioteca@palotina.pr.gov.br", requested_name: "Palotina PR" },
    });
    assert.equal(r.status, 200, r.text);
    assert.equal(r.json.suggested_slug, "palotina-pr-2");
  });

  await step("device/start is rate limited (3 per minute per IP)", async () => {
    const body = { institution_name: "Biblioteca Teste", contact_email: "a@b.org" };
    const codes = [];
    for (let i = 0; i < 2; i++) codes.push((await call("POST", "/v1/device/start", { body })).status);
    assert.ok(codes.includes(429), `expected a 429, got ${codes}`);
  });

  console.log(`\nbroker e2e: ${passed} checks passed`);
} catch (e) {
  console.error(e);
  console.error(`\nbroker e2e: failed after ${passed} passed checks`);
  process.exitCode = 1;
} finally {
  await b.close();
  rmSync(tmp, { recursive: true, force: true });
}
