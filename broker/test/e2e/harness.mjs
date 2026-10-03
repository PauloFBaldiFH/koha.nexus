// Runs the bundled Worker (.wrangler/e2e-build/index.js, from
// `npm run build:local`) in local workerd through Miniflare, with the same
// bindings as wrangler.toml, a fresh D1 with the migrations applied, and a
// fake Cloudflare API plus a fake Koha origin behind the outbound service.
// Used by run.mjs (npm run test:e2e) and serve.mjs (tests/free_address.bats).

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { request as httpRequest } from "node:http";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Miniflare, Response as MfResponse } from "miniflare4";
import { createFakeCloudflare, FAKE_ACCOUNT, FAKE_TOKEN, FAKE_ZONE } from "../fake-cloudflare.mjs";

const here = dirname(fileURLToPath(import.meta.url));
export const BROKER_DIR = resolve(here, "../..");
export const BUILD = join(BROKER_DIR, ".wrangler/e2e-build/index.js");
export const ADMIN_TOKEN = "a".repeat(40);
export const CF_API_HOST = "cf-api.fake";

export const TEST_VARS = {
  CF_ACCOUNT_ID: FAKE_ACCOUNT,
  CF_ZONE_ID: FAKE_ZONE,
  ZONE_NAME: "example.org",
  BROKER_HOST: "broker.example.org",
  NAME_PREFIX: "t-",
  STAFF_SUFFIX: "-admin",
  AUTO_APPROVE: "true",
  MAX_LIBRARIES_PER_DAY: "0",
  PBKDF2_ITERATIONS: "1000",
  CF_API_BASE: `http://${CF_API_HOST}/client/v4`,
  CF_API_TOKEN: FAKE_TOKEN,
  ADMIN_TOKEN,
  STAFF_SESSION_KEY: "s".repeat(48),
};

function compatibilityDate() {
  const toml = readFileSync(join(BROKER_DIR, "wrangler.toml"), "utf8");
  return /^compatibility_date\s*=\s*"([^"]+)"/m.exec(toml)?.[1] ?? "2026-07-01";
}

function migrationStatements() {
  const dir = join(BROKER_DIR, "migrations");
  const out = [];
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".sql")).sort()) {
    const sql = readFileSync(join(dir, f), "utf8")
      .split("\n")
      .map((l) => l.replace(/--.*$/, ""))
      .join("\n");
    for (const s of sql.split(";")) if (s.trim()) out.push(s.trim());
  }
  return out;
}

async function toMf(res) {
  return new MfResponse(await res.arrayBuffer(), { status: res.status, headers: [...res.headers] });
}

/**
 * Starts the broker. Returns { mf, url, fake, db, close, settle }.
 * `settle()` waits until no job is queued or running.
 */
export async function startBroker({ port = 0, vars = {} } = {}) {
  if (!existsSync(BUILD)) throw new Error(`missing ${BUILD}: run npm run build:local first`);
  const fake = createFakeCloudflare();
  const originRequests = [];

  const mf = new Miniflare({
    modules: true,
    scriptPath: BUILD,
    compatibilityDate: compatibilityDate(),
    host: "127.0.0.1",
    port,
    bindings: { ...TEST_VARS, ...vars },
    d1Databases: { DB: "kei-broker-local" },
    durableObjects: { PROVISIONER: { className: "Provisioner", useSQLite: true } },
    queueProducers: { PROVISION_QUEUE: { queueName: "kei-provision" } },
    queueConsumers: {
      "kei-provision": { maxBatchSize: 5, maxBatchTimeout: 1, maxRetries: 10, deadLetterQueue: "kei-provision-dlq" },
    },
    ratelimits: {
      RL_DEVICE: { namespace_id: "7301", simple: { limit: 3, period: 60 } },
      RL_API: { namespace_id: "7302", simple: { limit: 30, period: 60 } },
      RL_STAFF: { namespace_id: "7303", simple: { limit: 20, period: 60 } },
    },
    async outboundService(request) {
      const url = new URL(request.url);
      if (url.hostname === CF_API_HOST) {
        const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
        return toMf(await fake.handle(new Request(request.url, { method: request.method, headers: [...request.headers], body })));
      }
      // Anything else is the library's origin behind the tunnel (Koha).
      const seen = { host: url.hostname, path: url.pathname, authorization: request.headers.get("Authorization"), cookie: request.headers.get("Cookie") };
      originRequests.push(seen);
      return new MfResponse(JSON.stringify({ koha: true, ...seen }), { headers: { "Content-Type": "application/json" } });
    },
  });
  const url = (await mf.ready).toString().replace(/\/$/, "");
  const db = await mf.getD1Database("DB");
  for (const s of migrationStatements()) await db.prepare(s).run();

  async function settle(timeoutMs = 20000) {
    const end = Date.now() + timeoutMs;
    for (;;) {
      const r = await db.prepare("SELECT COUNT(*) AS n FROM jobs WHERE state IN ('queued', 'running')").first();
      if (!r?.n) return true;
      if (Date.now() > end) return false;
      await new Promise((ok) => setTimeout(ok, 200));
    }
  }

  return { mf, url, fake, db, originRequests, settle, close: () => mf.dispose() };
}

/** Plain HTTP request that can set the Host header (fetch cannot). */
export function rawRequest(url, { method = "GET", headers = {}, body } = {}) {
  return new Promise((ok, fail) => {
    const u = new URL(url);
    const req = httpRequest(
      { hostname: u.hostname, port: u.port, path: u.pathname + u.search, method, headers },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => ok({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString("utf8") }));
      },
    );
    req.on("error", fail);
    if (body !== undefined) req.write(body);
    req.end();
  });
}
