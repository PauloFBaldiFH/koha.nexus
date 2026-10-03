// Public API used by the Koha installer.
//
// Enrollment follows the device-authorization pattern (RFC 8628): the panel
// asks for a code, shows the verification link as QR / browser / link, and
// polls. With AUTO_APPROVE=true (the default) every request is approved on
// the spot under the first free valid name: no review, no word filter. With
// AUTO_APPROVE=false an admin approves each request (admin.ts).
//
// After enrollment every call is signed with the install's Ed25519 key.

import { audit, cfApi, getLibrary, provisioner, slugAvailable } from "./db";
import type { Env, JobRow, LibraryRow } from "./env";
import { now } from "./env";
import { pbkdf2, randomBytes, randomToken, sha256Hex, toBase64 } from "./crypto";
import { HttpError, json, parseJson, str } from "./http";
import { hostnamesFor, maxSlugLength, slugCandidates, slugify, validateSlug } from "./names";
import { parseCidr } from "./netaddr";
import { checkSignedRequest, isValidPublicKey } from "./signature";

const ENROLLMENT_TTL_SECONDS = 24 * 3600;
const POLL_INTERVAL_SECONDS = 10;
const USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"; // no vowels: no accidental words
const EMAIL_RE = /^[^\s@<>"']{1,64}@[a-z0-9.-]{1,190}\.[a-z]{2,24}$/i;

export function userCode(): string {
  const b = randomBytes(8);
  const chars = [...b].map((x) => USER_CODE_ALPHABET[x % USER_CODE_ALPHABET.length]).join("");
  return `${chars.slice(0, 4)}-${chars.slice(4)}`;
}

function clientIp(request: Request): string {
  return request.headers.get("CF-Connecting-IP") ?? "unknown";
}

async function limit(rl: RateLimit, key: string): Promise<void> {
  if (!(await rl.limit({ key })).success) throw new HttpError(429, "too many requests, try again in a minute");
}

// ---- Enrollment ----

interface StartBody {
  institution_name?: unknown;
  contact_email?: unknown;
  cnpj?: unknown;
  requested_name?: unknown;
}

export async function deviceStart(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const ip = clientIp(request);
  await limit(env.RL_DEVICE, ip);
  const b = parseJson<StartBody>(body);
  const institution = str(b.institution_name, "institution_name", { min: 3, max: 200 });
  const email = str(b.contact_email, "contact_email", { max: 254, re: EMAIL_RE }).toLowerCase();
  const cnpj = typeof b.cnpj === "string" ? b.cnpj.replace(/\D/g, "") : "";
  if (cnpj && cnpj.length !== 14) throw new HttpError(400, "cnpj must have 14 digits");
  const requested = str(b.requested_name, "requested_name", { max: 100, optional: true });

  const opts = { prefix: env.NAME_PREFIX, staffSuffix: env.STAFF_SUFFIX };
  const max = maxSlugLength(opts.prefix, opts.staffSuffix);
  let slug = slugify(requested || institution).slice(0, max).replace(/-+$/, "");

  const deviceCode = randomToken(32);
  const code = userCode();
  const t = now();
  let status: "pending" | "approved" = "pending";
  if (env.AUTO_APPROVE !== "false") {
    // Instant approval: the first free valid name. Only the technical
    // reserved names (www, join, broker, ...) are never handed out.
    const auto = { ...opts, allowBlocked: true };
    const candidates = [...slugCandidates(requested, institution, max), `biblioteca-${userCode().replace("-", "").toLowerCase()}`];
    for (const c of candidates) {
      if (validateSlug(c, auto).ok && (await slugAvailable(env, c))) {
        slug = c;
        status = "approved";
        break;
      }
    }
  }
  await env.DB.prepare(
    `INSERT INTO enrollments (device_code_hash, user_code, status, institution_name, contact_email, cnpj,
       requested_slug, approved_slug, client_ip_hash, created_at, expires_at, decided_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  )
    .bind(
      await sha256Hex(deviceCode),
      code,
      status,
      institution,
      email,
      cnpj || null,
      slug,
      status === "approved" ? slug : null,
      await sha256Hex(`${ip}|${env.ZONE_NAME}`),
      t,
      t + ENROLLMENT_TTL_SECONDS,
      status === "approved" ? t : null,
    )
    .run();
  await audit(env, "public", "enrollment.start", null, { user_code: code, slug, status });

  return json({
    device_code: deviceCode,
    user_code: code,
    verification_uri: `https://${env.BROKER_HOST}/join?c=${code}`,
    suggested_slug: slug,
    expires_in: ENROLLMENT_TTL_SECONDS,
    interval: POLL_INTERVAL_SECONDS,
    status,
    ...(status === "approved" ? { hostnames: hostnamesFor(slug, env) } : {}),
  });
}

interface EnrollmentRow {
  status: "pending" | "approved" | "denied" | "consumed";
  approved_slug: string | null;
  expires_at: number;
}

export async function devicePoll(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  await limit(env.RL_API, clientIp(request));
  const b = parseJson<{ device_code?: unknown }>(body);
  const deviceCode = str(b.device_code, "device_code", { max: 64 });
  const row = await env.DB.prepare("SELECT status, approved_slug, expires_at FROM enrollments WHERE device_code_hash = ?")
    .bind(await sha256Hex(deviceCode))
    .first<EnrollmentRow>();
  if (!row) throw new HttpError(404, "unknown device code");
  if (row.expires_at <= now() && row.status !== "consumed") return json({ status: "expired" });
  const out: Record<string, unknown> = { status: row.status, interval: POLL_INTERVAL_SECONDS };
  if (row.status === "approved" && row.approved_slug) out.hostnames = hostnamesFor(row.approved_slug, env);
  return json(out);
}

export async function enroll(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  await limit(env.RL_API, clientIp(request));
  const b = parseJson<{ device_code?: unknown; public_key?: unknown }>(body);
  const deviceCode = str(b.device_code, "device_code", { max: 64 });
  const publicKey = str(b.public_key, "public_key", { max: 64 });
  if (!isValidPublicKey(publicKey)) throw new HttpError(400, "public_key must be a base64 raw Ed25519 key (32 bytes)");

  // Optional global circuit breaker: MAX_LIBRARIES_PER_DAY above 0 pauses
  // enrollment after that many new libraries in 24 hours. 0 turns it off.
  const t = now();
  const cap = Number(env.MAX_LIBRARIES_PER_DAY || "0");
  if (cap > 0) {
    const recent = await env.DB.prepare("SELECT COUNT(*) AS n FROM libraries WHERE created_at > ?")
      .bind(t - 86400)
      .first<{ n: number }>();
    if ((recent?.n ?? 0) >= cap) {
      await audit(env, "system", "circuit_breaker.open", null, { recent: recent?.n });
      throw new HttpError(503, "new registrations are paused, try again later");
    }
  }

  const hash = await sha256Hex(deviceCode);
  const enrollment = await env.DB.prepare(
    `UPDATE enrollments SET status = 'consumed', consumed_at = ?1
     WHERE device_code_hash = ?2 AND status = 'approved' AND expires_at > ?1
     RETURNING institution_name, contact_email, cnpj, approved_slug`,
  )
    .bind(t, hash)
    .first<{ institution_name: string; contact_email: string; cnpj: string | null; approved_slug: string }>();
  if (!enrollment) throw new HttpError(409, "this request is not approved, has expired or was already used");

  const libraryId = crypto.randomUUID();
  const jobId = crypto.randomUUID();
  try {
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO libraries (id, slug, status, institution_name, contact_email, cnpj, public_key, created_at, updated_at)
         VALUES (?, ?, 'provisioning', ?, ?, ?, ?, ?, ?)`,
      ).bind(libraryId, enrollment.approved_slug, enrollment.institution_name, enrollment.contact_email, enrollment.cnpj, publicKey, t, t),
      env.DB.prepare(
        "INSERT INTO jobs (id, library_id, kind, state, created_at, updated_at) VALUES (?, ?, 'provision', 'queued', ?, ?)",
      ).bind(jobId, libraryId, t, t),
    ]);
  } catch {
    // Most likely the name was taken in between: give the enrollment back.
    await env.DB.prepare("UPDATE enrollments SET status = 'approved', consumed_at = NULL WHERE device_code_hash = ?")
      .bind(hash)
      .run();
    throw new HttpError(409, "the approved name is no longer available, ask for a new one");
  }
  await env.PROVISION_QUEUE.send({ jobId });
  await audit(env, `library:${libraryId}`, "library.enroll", libraryId, { slug: enrollment.approved_slug });
  return json({ library_id: libraryId, job_id: jobId, hostnames: hostnamesFor(enrollment.approved_slug, env) }, 202);
}

// Human-facing page behind the QR code: shows the status of the request.
export async function joinPage(request: Request, env: Env): Promise<Response> {
  await limit(env.RL_API, clientIp(request));
  const code = new URL(request.url).searchParams.get("c") ?? "";
  const row = /^[A-Z]{4}-[A-Z]{4}$/.test(code)
    ? await env.DB.prepare("SELECT status, expires_at FROM enrollments WHERE user_code = ?").bind(code).first<EnrollmentRow>()
    : null;
  const status = !row ? "unknown" : row.expires_at <= now() && row.status !== "consumed" ? "expired" : row.status;
  const text: Record<string, string> = {
    unknown: "This request code was not found. Check the code shown in the Koha panel.",
    expired: "This request has expired. Start again from the Koha panel.",
    pending: "Your request was received and is waiting for review. The Koha panel continues on its own once it is approved.",
    approved: "Your request was approved. Go back to the Koha panel to finish.",
    denied: "This request was not approved.",
    consumed: "This request was already used to set up a library.",
  };
  const html = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Koha library address</title><body style="font-family:system-ui;max-width:36rem;margin:3rem auto;padding:0 1rem"><h1>Koha library address</h1><p><strong>${status === "unknown" ? "" : code}</strong></p><p>${text[status]}</p>`;
  return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex" } });
}

// ---- Signed endpoints ----

async function signedLibrary(request: Request, env: Env, body: ArrayBuffer): Promise<LibraryRow> {
  const res = await checkSignedRequest(request.method, new URL(request.url), request.headers, body, {
    now: now(),
    lookupKey: async (id) =>
      (
        await env.DB.prepare("SELECT public_key FROM libraries WHERE id = ? AND status NOT IN ('deleted', 'failed')")
          .bind(id)
          .first<{ public_key: string }>()
      )?.public_key ?? null,
    consumeNonce: async (id, nonce, expiresAt) =>
      (
        await env.DB.prepare("INSERT INTO nonces (library_id, nonce, expires_at) VALUES (?, ?, ?) ON CONFLICT DO NOTHING")
          .bind(id, nonce, expiresAt)
          .run()
      ).meta.changes === 1,
  });
  if (!res.ok) throw new HttpError(res.status, res.error);
  await limit(env.RL_API, `lib:${res.libraryId}`);
  const lib = await getLibrary(env, res.libraryId);
  if (!lib) throw new HttpError(401, "invalid signature");
  return lib;
}

export async function getJob(request: Request, env: Env, body: ArrayBuffer, jobId: string): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  const job = await env.DB.prepare("SELECT * FROM jobs WHERE id = ? AND library_id = ?").bind(jobId, lib.id).first<JobRow>();
  if (!job) throw new HttpError(404, "job not found");
  return json({ id: job.id, kind: job.kind, state: job.state, error: job.error, library_status: lib.status });
}

export async function getLibraryInfo(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  return json({
    id: lib.id,
    slug: lib.slug,
    status: lib.status,
    hostnames: hostnamesFor(lib.slug, env),
    staff_remote_access: Boolean(lib.staff_pass_hash),
    staff_allow_cidrs: lib.staff_allow_cidrs ? JSON.parse(lib.staff_allow_cidrs) : [],
  });
}

// The tunnel token is fetched live from Cloudflare and never stored by the broker.
export async function getTunnelToken(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  if (!lib.tunnel_id || (lib.status !== "active" && lib.status !== "suspended")) {
    throw new HttpError(409, `library is ${lib.status}`);
  }
  const token = await cfApi(env).getTunnelToken(lib.tunnel_id);
  await audit(env, `library:${lib.id}`, "tunnel_token.fetch", lib.id);
  return json({ tunnel_token: token });
}

export async function heartbeat(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  const b = parseJson<{ koha_version?: unknown; installer_version?: unknown }>(body);
  const koha = str(b.koha_version, "koha_version", { max: 32, optional: true });
  const installer = str(b.installer_version, "installer_version", { max: 32, optional: true });
  await env.DB.prepare("UPDATE libraries SET koha_version = ?, installer_version = ?, last_heartbeat = ? WHERE id = ?")
    .bind(koha || null, installer || null, now(), lib.id)
    .run();
  return json({ status: lib.status });
}

export async function putStaffCredentials(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  const b = parseJson<{ username?: unknown; password?: unknown; allow_cidrs?: unknown }>(body);
  const username = str(b.username, "username", { min: 3, max: 64, re: /^[A-Za-z0-9._@-]+$/ });
  if (typeof b.password !== "string" || b.password.length < 12 || b.password.length > 256) {
    throw new HttpError(400, "password must have 12 to 256 characters");
  }
  const cidrs = b.allow_cidrs ?? [];
  if (!Array.isArray(cidrs) || cidrs.length > 20 || cidrs.some((c) => typeof c !== "string" || !parseCidr(c))) {
    throw new HttpError(400, "allow_cidrs must be a list of up to 20 CIDR ranges");
  }
  const iterations = Number(env.PBKDF2_ITERATIONS || "20000");
  const salt = randomBytes(16);
  const hash = await pbkdf2(b.password, salt, iterations);
  await env.DB.prepare(
    `UPDATE libraries SET staff_user = ?, staff_pass_hash = ?, staff_pass_salt = ?, staff_pass_iter = ?,
       staff_cred_version = staff_cred_version + 1, staff_allow_cidrs = ?, updated_at = ? WHERE id = ?`,
  )
    .bind(username, hash, toBase64(salt), iterations, cidrs.length ? JSON.stringify(cidrs) : null, now(), lib.id)
    .run();
  await audit(env, `library:${lib.id}`, "staff_access.set", lib.id, { cidrs: cidrs.length });
  return json({ staff_remote_access: true, hostname: hostnamesFor(lib.slug, env).staff });
}

export async function deleteStaffCredentials(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  await env.DB.prepare(
    `UPDATE libraries SET staff_user = NULL, staff_pass_hash = NULL, staff_pass_salt = NULL, staff_pass_iter = NULL,
       staff_cred_version = staff_cred_version + 1, updated_at = ? WHERE id = ?`,
  )
    .bind(now(), lib.id)
    .run();
  await audit(env, `library:${lib.id}`, "staff_access.off", lib.id);
  return json({ staff_remote_access: false });
}

export async function rotateToken(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  await provisioner(env, lib.id).rotate(lib.id);
  await audit(env, `library:${lib.id}`, "tunnel_token.rotate", lib.id);
  return json({ rotated: true });
}

export async function requestDeletion(env: Env, libraryId: string, actor: string): Promise<Response> {
  const t = now();
  const jobId = crypto.randomUUID();
  const res = await env.DB.batch([
    env.DB.prepare(
      "UPDATE libraries SET status = 'deprovisioning', updated_at = ? WHERE id = ? AND status IN ('active', 'suspended', 'provisioning')",
    ).bind(t, libraryId),
    env.DB.prepare(
      `INSERT INTO jobs (id, library_id, kind, state, created_at, updated_at)
       SELECT ?, id, 'deprovision', 'queued', ?, ? FROM libraries WHERE id = ? AND status = 'deprovisioning'`,
    ).bind(jobId, t, t, libraryId),
  ]);
  if ((res[1]?.meta.changes ?? 0) === 0) throw new HttpError(409, "library cannot be removed in its current state");
  await env.PROVISION_QUEUE.send({ jobId });
  await audit(env, actor, "library.delete", libraryId);
  return json({ job_id: jobId }, 202);
}

export async function deleteLibrary(request: Request, env: Env, body: ArrayBuffer): Promise<Response> {
  const lib = await signedLibrary(request, env, body);
  return requestDeletion(env, lib.id, `library:${lib.id}`);
}

