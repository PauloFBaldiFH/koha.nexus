// Shared data access: audit log, library lookups, name availability, the
// Cloudflare client and the per-library Provisioner stub.

import { CloudflareApi } from "./cloudflare";
import type { Env, LibraryRow } from "./env";
import { now } from "./env";

/** A released name is held this long before anyone else can take it. */
export const NAME_HOLD_SECONDS = 180 * 86400;

export async function audit(
  env: Env,
  actor: string,
  action: string,
  libraryId: string | null,
  detail?: Record<string, unknown>,
): Promise<void> {
  await env.DB.prepare("INSERT INTO audit_log (at, actor, action, library_id, detail) VALUES (?, ?, ?, ?, ?)")
    .bind(now(), actor, action, libraryId, detail === undefined ? null : JSON.stringify(detail))
    .run();
}

export function cfApi(env: Env): CloudflareApi {
  if (!env.CF_API_TOKEN) throw new Error("CF_API_TOKEN is not set");
  return new CloudflareApi({
    token: env.CF_API_TOKEN,
    accountId: env.CF_ACCOUNT_ID,
    zoneId: env.CF_ZONE_ID,
    base: env.CF_API_BASE || undefined,
  });
}

/** Any library that is not deleted (failed ones included, for history). */
export async function getLibrary(env: Env, id: string): Promise<LibraryRow | null> {
  return env.DB.prepare("SELECT * FROM libraries WHERE id = ? AND status <> 'deleted'").bind(id).first<LibraryRow>();
}

export async function getLibraryBySlug(env: Env, slug: string): Promise<LibraryRow | null> {
  return env.DB.prepare("SELECT * FROM libraries WHERE slug = ? AND status NOT IN ('deleted', 'failed')")
    .bind(slug)
    .first<LibraryRow>();
}

/**
 * A name is available when no live library uses it, it is not on hold or
 * reserved (reserved_names), and no other open approved request holds it.
 * `exceptUserCode` skips the request being decided.
 */
export async function slugAvailable(env: Env, slug: string, exceptUserCode?: string): Promise<boolean> {
  const t = now();
  const row = await env.DB.prepare(
    `SELECT
       (SELECT COUNT(*) FROM libraries WHERE slug = ?1 AND status NOT IN ('deleted', 'failed')) +
       (SELECT COUNT(*) FROM reserved_names WHERE slug = ?1 AND (until IS NULL OR until > ?2)) +
       (SELECT COUNT(*) FROM enrollments WHERE approved_slug = ?1 AND status = 'approved' AND expires_at > ?2
          AND user_code <> ?3) AS n`,
  )
    .bind(slug, t, exceptUserCode ?? "")
    .first<{ n: number }>();
  return (row?.n ?? 1) === 0;
}

/** Puts a released name on hold for NAME_HOLD_SECONDS. */
export function holdNameStatement(env: Env, slug: string): D1PreparedStatement {
  return env.DB.prepare(
    `INSERT INTO reserved_names (slug, reason, until) VALUES (?1, 'released', ?2)
     ON CONFLICT (slug) DO UPDATE SET until = MAX(COALESCE(until, ?2), ?2) WHERE until IS NOT NULL`,
  ).bind(slug, now() + NAME_HOLD_SECONDS);
}

/** The Durable Object that serializes all tunnel/DNS work of one library. */
export function provisioner(env: Env, libraryId: string): DurableObjectStub<import("./provisioner").Provisioner> {
  return env.PROVISIONER.get(env.PROVISIONER.idFromName(libraryId));
}
