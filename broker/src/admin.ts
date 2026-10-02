// Admin endpoints: approve or deny enrollment requests, suspend, restore
// and remove libraries. Protected by a bearer token (ADMIN_TOKEN secret);
// in production also put /admin behind Cloudflare Access.

import { requestDeletion } from "./api";
import { audit, getLibrary, provisioner, slugAvailable } from "./db";
import type { Env } from "./env";
import { now } from "./env";
import { timingSafeEqualStr } from "./crypto";
import { HttpError, json, parseJson } from "./http";
import { hostnamesFor, validateSlug } from "./names";

export async function requireAdmin(request: Request, env: Env): Promise<void> {
  if (!env.ADMIN_TOKEN || env.ADMIN_TOKEN.length < 32) throw new HttpError(503, "admin access is not configured");
  const ok = await timingSafeEqualStr(request.headers.get("Authorization") ?? "", `Bearer ${env.ADMIN_TOKEN}`);
  if (!ok) throw new HttpError(401, "unauthorized");
}

export async function listEnrollments(env: Env, url: URL): Promise<Response> {
  const status = url.searchParams.get("status") ?? "pending";
  const rows = await env.DB.prepare(
    `SELECT user_code, status, institution_name, contact_email, cnpj, requested_slug, approved_slug, created_at, expires_at
     FROM enrollments WHERE status = ? ORDER BY created_at DESC LIMIT 100`,
  )
    .bind(status)
    .all();
  return json({ enrollments: rows.results });
}

export async function decideEnrollment(env: Env, userCode: string, approve: boolean, body: ArrayBuffer): Promise<Response> {
  const row = await env.DB.prepare("SELECT status, requested_slug, expires_at FROM enrollments WHERE user_code = ?")
    .bind(userCode)
    .first<{ status: string; requested_slug: string | null; expires_at: number }>();
  if (!row) throw new HttpError(404, "request not found");
  if (row.status !== "pending" || row.expires_at <= now()) throw new HttpError(409, `request is ${row.status}`);

  if (!approve) {
    await env.DB.prepare("UPDATE enrollments SET status = 'denied', decided_at = ? WHERE user_code = ?").bind(now(), userCode).run();
    await audit(env, "admin", "enrollment.deny", null, { user_code: userCode });
    return json({ status: "denied" });
  }

  const b = parseJson<{ slug?: unknown; force?: unknown }>(body);
  const slug = typeof b.slug === "string" && b.slug ? b.slug.trim().toLowerCase() : row.requested_slug ?? "";
  const check = validateSlug(slug, { prefix: env.NAME_PREFIX, staffSuffix: env.STAFF_SUFFIX, allowBlocked: b.force === true });
  if (!check.ok) throw new HttpError(400, `name "${slug}" rejected: ${check.reason}`);
  if (!(await slugAvailable(env, slug, userCode))) throw new HttpError(409, `name "${slug}" is not available`);

  await env.DB.prepare(
    "UPDATE enrollments SET status = 'approved', approved_slug = ?, decided_at = ? WHERE user_code = ? AND status = 'pending'",
  )
    .bind(slug, now(), userCode)
    .run();
  await audit(env, "admin", "enrollment.approve", null, { user_code: userCode, slug, forced: b.force === true });
  return json({ status: "approved", hostnames: hostnamesFor(slug, env) });
}

export async function listLibraries(env: Env): Promise<Response> {
  const rows = await env.DB.prepare(
    `SELECT id, slug, status, institution_name, contact_email, cnpj, tunnel_id, staff_pass_hash IS NOT NULL AS staff_remote_access,
       koha_version, installer_version, last_heartbeat, created_at, updated_at
     FROM libraries WHERE status <> 'deleted' ORDER BY created_at DESC LIMIT 500`,
  ).all();
  return json({ libraries: rows.results });
}

export async function suspendLibrary(env: Env, id: string, suspended: boolean): Promise<Response> {
  if (!(await getLibrary(env, id))) throw new HttpError(404, "library not found");
  try {
    await provisioner(env, id).setSuspended(id, suspended);
  } catch (e) {
    throw new HttpError(409, e instanceof Error ? e.message : String(e));
  }
  await audit(env, "admin", suspended ? "library.suspend" : "library.restore", id);
  return json({ status: suspended ? "suspended" : "active" });
}

export async function adminDeleteLibrary(env: Env, id: string): Promise<Response> {
  if (!(await getLibrary(env, id))) throw new HttpError(404, "library not found");
  return requestDeletion(env, id, "admin");
}
