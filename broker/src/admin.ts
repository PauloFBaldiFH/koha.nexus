// Admin endpoints: approve or deny enrollment requests, suspend, restore
// and remove libraries. Protected by a bearer token (ADMIN_TOKEN secret);
// in production also put /admin behind Cloudflare Access.

import { requestDeletion, setListing } from "./api";
import { audit, getLibrary, provisioner, slugAvailable } from "./db";
import type { Env } from "./env";
import { now } from "./env";
import { timingSafeEqualStr, toBase64 } from "./crypto";
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
       koha_version, installer_version, last_heartbeat, public_listing, created_at, updated_at
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

// A library whose server was lost together with its key (no recovery file):
// after checking with the library by other means (its contact e-mail), the
// admin gets a new recovery file. The broker makes a new key pair, keeps
// only the public half and hands the private half out once; the old key
// stops working at once. The panel's "I already have an address" reads the
// file and renews the tunnel token, so the old server is cut off too.
export async function issueRecoveryFile(env: Env, id: string, url: URL): Promise<Response> {
  const lib = await getLibrary(env, id);
  if (!lib) throw new HttpError(404, "library not found");
  if (lib.status !== "active" && lib.status !== "suspended") throw new HttpError(409, `library is ${lib.status}`);
  const pair = (await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"])) as CryptoKeyPair;
  const pub = toBase64((await crypto.subtle.exportKey("raw", pair.publicKey)) as ArrayBuffer);
  const pkcs8 = toBase64((await crypto.subtle.exportKey("pkcs8", pair.privateKey)) as ArrayBuffer);
  await env.DB.prepare("UPDATE libraries SET public_key = ?, updated_at = ? WHERE id = ?").bind(pub, now(), id).run();
  await audit(env, "admin", "library.recovery_file", id);
  const file = [
    "# koha.nexus free address recovery file. Whoever has it can publish this",
    "# address: keep it private and outside this server.",
    "KEI_ADDRESS=1",
    `BROKER_URL=${url.origin}`,
    `LIBRARY_ID=${lib.id}`,
    `OPAC_HOST=${hostnamesFor(lib.slug, env).opac}`,
    "-----BEGIN PRIVATE KEY-----",
    ...(pkcs8.match(/.{1,64}/g) ?? []),
    "-----END PRIVATE KEY-----",
    "",
  ].join("\n");
  return new Response(file, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Content-Disposition": `attachment; filename="koha-address-${lib.slug}.key"`,
      "Cache-Control": "no-store",
    },
  });
}

export async function adminSetListing(env: Env, id: string, body: ArrayBuffer): Promise<Response> {
  if (!(await getLibrary(env, id))) throw new HttpError(404, "library not found");
  const b = parseJson<{ public?: unknown }>(body);
  if (typeof b.public !== "boolean") throw new HttpError(400, "public must be true or false");
  await setListing(env, id, b.public, "admin");
  return json({ public_listing: b.public });
}

// Ends the hold on a released name (a library that gave its address up and
// wants it back on a new server). Names reserved by hand stay reserved.
export async function releaseHeldName(env: Env, slug: string): Promise<Response> {
  const r = await env.DB.prepare("DELETE FROM reserved_names WHERE slug = ? AND reason = 'released'").bind(slug).run();
  if (r.meta.changes !== 1) throw new HttpError(404, "name is not on hold");
  await audit(env, "admin", "name.release_hold", null, { slug });
  return json({ slug, available: await slugAvailable(env, slug) });
}
