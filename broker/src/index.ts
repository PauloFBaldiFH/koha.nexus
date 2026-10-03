// Koha subdomain broker: router, queue consumer and hourly cron.

import {
  deleteLibrary,
  deleteStaffCredentials,
  deviceStart,
  devicePoll,
  enroll,
  getJob,
  getLibraryInfo,
  getTunnelToken,
  heartbeat,
  joinPage,
  putStaffCredentials,
  rotateToken,
} from "./api";
import {
  adminDeleteLibrary,
  decideEnrollment,
  listEnrollments,
  listLibraries,
  requireAdmin,
  suspendLibrary,
} from "./admin";
import { audit, cfApi, provisioner } from "./db";
import type { Env, JobRow, ProvisionMessage } from "./env";
import { now } from "./env";
import { HttpError, errorResponse, json } from "./http";
import { MAX_ATTEMPTS, reconcile } from "./provision-steps";
import type { StepOutcome } from "./provisioner";
import { staffGate, staffSlugFromHost } from "./staff-auth";

export { Provisioner } from "./provisioner";

const MAX_REQUEST_BYTES = 64 * 1024;
const UUID = "[0-9a-fA-F-]{36}";

type Handler = (request: Request, env: Env, body: ArrayBuffer, params: string[], url: URL) => Promise<Response>;

interface Route {
  method: string;
  pattern: RegExp;
  handler: Handler;
}

const admin =
  (h: Handler): Handler =>
  async (request, env, body, params, url) => {
    await requireAdmin(request, env);
    return h(request, env, body, params, url);
  };

const routes: Route[] = [
  { method: "POST", pattern: /^\/v1\/device\/start$/, handler: (r, e, b) => deviceStart(r, e, b) },
  { method: "POST", pattern: /^\/v1\/device\/poll$/, handler: (r, e, b) => devicePoll(r, e, b) },
  { method: "POST", pattern: /^\/v1\/enroll$/, handler: (r, e, b) => enroll(r, e, b) },
  { method: "GET", pattern: /^\/join\/?$/, handler: (r, e) => joinPage(r, e) },
  { method: "GET", pattern: new RegExp(`^/v1/jobs/(${UUID})$`), handler: (r, e, b, p) => getJob(r, e, b, p[0]!) },
  { method: "GET", pattern: /^\/v1\/library$/, handler: (r, e, b) => getLibraryInfo(r, e, b) },
  { method: "DELETE", pattern: /^\/v1\/library$/, handler: (r, e, b) => deleteLibrary(r, e, b) },
  { method: "GET", pattern: /^\/v1\/tunnel-token$/, handler: (r, e, b) => getTunnelToken(r, e, b) },
  { method: "POST", pattern: /^\/v1\/rotate$/, handler: (r, e, b) => rotateToken(r, e, b) },
  { method: "POST", pattern: /^\/v1\/heartbeat$/, handler: (r, e, b) => heartbeat(r, e, b) },
  { method: "PUT", pattern: /^\/v1\/staff-credentials$/, handler: (r, e, b) => putStaffCredentials(r, e, b) },
  { method: "DELETE", pattern: /^\/v1\/staff-credentials$/, handler: (r, e, b) => deleteStaffCredentials(r, e, b) },

  { method: "GET", pattern: /^\/admin\/enrollments$/, handler: admin((r, e, b, p, u) => listEnrollments(e, u)) },
  {
    method: "POST",
    pattern: /^\/admin\/enrollments\/([A-Z]{4}-[A-Z]{4})\/(approve|deny)$/,
    handler: admin((r, e, b, p) => decideEnrollment(e, p[0]!, p[1] === "approve", b)),
  },
  { method: "GET", pattern: /^\/admin\/libraries$/, handler: admin((r, e) => listLibraries(e)) },
  {
    method: "POST",
    pattern: new RegExp(`^/admin/libraries/(${UUID})/(suspend|restore)$`),
    handler: admin((r, e, b, p) => suspendLibrary(e, p[0]!, p[1] === "suspend")),
  },
  { method: "DELETE", pattern: new RegExp(`^/admin/libraries/(${UUID})$`), handler: admin((r, e, b, p) => adminDeleteLibrary(e, p[0]!)) },

  { method: "GET", pattern: /^\/$/, handler: async () => json({ service: "kei-broker", status: "ok" }) },
];

async function route(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  let pathMatched = false;
  for (const r of routes) {
    const m = r.pattern.exec(url.pathname);
    if (!m) continue;
    pathMatched = true;
    if (r.method !== request.method && !(r.method === "GET" && request.method === "HEAD")) continue;
    const len = Number(request.headers.get("Content-Length") ?? "0");
    if (len > MAX_REQUEST_BYTES) throw new HttpError(413, "request body too large");
    const body = await request.arrayBuffer();
    if (body.byteLength > MAX_REQUEST_BYTES) throw new HttpError(413, "request body too large");
    return r.handler(request, env, body, m.slice(1), url);
  }
  if (pathMatched) throw new HttpError(405, "method not allowed");
  throw new HttpError(404, "not found");
}

// ---- Queue consumer: runs provisioning jobs through the library's Durable Object ----

export function retryDelaySeconds(attempts: number): number {
  return Math.min(300, 10 * 2 ** Math.max(0, attempts - 1));
}

async function setJob(env: Env, id: string, state: JobRow["state"], error: string | null): Promise<void> {
  await env.DB.prepare("UPDATE jobs SET state = ?, error = ?, updated_at = ? WHERE id = ?").bind(state, error, now(), id).run();
}

export async function runJob(env: Env, jobId: string): Promise<{ retryIn?: number }> {
  const job = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(jobId).first<JobRow>();
  if (!job || job.state === "done" || job.state === "failed") return {};
  const attempts = job.attempts + 1;
  await env.DB.prepare("UPDATE jobs SET state = 'running', attempts = ?, updated_at = ? WHERE id = ?").bind(attempts, now(), jobId).run();

  const stub = provisioner(env, job.library_id);
  let r: StepOutcome;
  try {
    r = job.kind === "provision" ? await stub.provision(job.library_id) : await stub.deprovision(job.library_id);
  } catch (e) {
    r = { ok: false, error: e instanceof Error ? e.message : String(e), retryable: true };
  }

  if (r.ok) {
    await setJob(env, jobId, "done", null);
    await audit(env, "system", `job.${job.kind}.done`, job.library_id, { job_id: jobId, attempts });
    return {};
  }
  if (r.retryable && attempts < MAX_ATTEMPTS) {
    await setJob(env, jobId, "queued", r.error);
    return { retryIn: retryDelaySeconds(attempts) };
  }
  // Give up. A provisioning that gave up removes what it created.
  if (job.kind === "provision") {
    try {
      await stub.rollback(job.library_id);
    } catch {
      // The library stays as it is; reconciliation removes leftovers of failed libraries.
    }
  }
  await setJob(env, jobId, "failed", r.error);
  await audit(env, "system", `job.${job.kind}.failed`, job.library_id, { job_id: jobId, attempts, error: r.error });
  return {};
}

// ---- Cron: reconciliation and cleanup ----

const STALE_JOB_SECONDS = 3600;

export async function scheduledRun(env: Env): Promise<Record<string, unknown>> {
  const t = now();
  const summary: Record<string, unknown> = {};
  try {
    const isLive = async (id: string) => {
      const row = await env.DB.prepare("SELECT status FROM libraries WHERE id = ?").bind(id).first<{ status: string }>();
      return !!row && row.status !== "deleted" && row.status !== "failed";
    };
    const r = await reconcile(cfApi(env), isLive, t);
    summary.tunnels_deleted = r.tunnelsDeleted.length;
    summary.records_deleted = r.recordsDeleted.length;
  } catch (e) {
    summary.reconcile_error = e instanceof Error ? e.message : String(e);
  }

  const res = await env.DB.batch([
    env.DB.prepare("DELETE FROM nonces WHERE expires_at < ?").bind(t),
    env.DB.prepare("DELETE FROM enrollments WHERE expires_at < ? AND status <> 'consumed'").bind(t - 7 * 86400),
    env.DB.prepare("DELETE FROM reserved_names WHERE until IS NOT NULL AND until < ?").bind(t),
  ]);
  summary.nonces_pruned = res[0]?.meta.changes ?? 0;
  summary.enrollments_pruned = res[1]?.meta.changes ?? 0;

  // Jobs whose queue message was lost (dead-letter queue): send them again.
  const stale = await env.DB.prepare("SELECT id FROM jobs WHERE state IN ('queued', 'running') AND updated_at < ? LIMIT 50")
    .bind(t - STALE_JOB_SECONDS)
    .all<{ id: string }>();
  for (const j of stale.results) await env.PROVISION_QUEUE.send({ jobId: j.id });
  summary.jobs_requeued = stale.results.length;

  if (summary.tunnels_deleted || summary.records_deleted || summary.reconcile_error || summary.jobs_requeued) {
    await audit(env, "system", "reconcile", null, summary);
  }
  return summary;
}

export default {
  async fetch(request, env): Promise<Response> {
    try {
      if (staffSlugFromHost(new URL(request.url).hostname, env)) return await staffGate(request, env);
      return await route(request, env);
    } catch (e) {
      if (e instanceof HttpError) return errorResponse(e);
      console.error("unhandled error", e instanceof Error ? e.stack ?? e.message : String(e));
      return json({ error: "internal error" }, 500);
    }
  },

  async queue(batch, env): Promise<void> {
    for (const msg of batch.messages) {
      try {
        const r = await runJob(env, msg.body.jobId);
        if (r.retryIn !== undefined) msg.retry({ delaySeconds: r.retryIn });
        else msg.ack();
      } catch (e) {
        console.error("job error", e instanceof Error ? e.message : String(e));
        msg.retry({ delaySeconds: 30 });
      }
    }
  },

  async scheduled(_controller, env, ctx): Promise<void> {
    ctx.waitUntil(
      scheduledRun(env).then(
        (s) => console.log("reconcile", JSON.stringify(s)),
        (e) => console.error("reconcile failed", e instanceof Error ? e.message : String(e)),
      ),
    );
  },
} satisfies ExportedHandler<Env, ProvisionMessage>;
