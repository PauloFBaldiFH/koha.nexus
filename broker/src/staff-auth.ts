// Edge gate for the staff hostnames (<prefix><slug><STAFF_SUFFIX>.<zone>),
// run on the Worker route `*-admin.<zone>/*` before the request reaches the
// library's tunnel. See README "Staff interface security".
//
//  1. Closed (403) until the library sets credentials (signed PUT /v1/staff-credentials).
//  2. Optional IP allowlist (CIDRs) per library.
//  3. A valid signed session cookie passes; otherwise HTTP Basic Auth is
//     checked against the PBKDF2-SHA256 hash, rate limited per IP and
//     library. A good login sets a 12 h `__Host-` cookie bound to the
//     credential version, so changing the password ends every session.
//  4. The gate's own Authorization header and cookie are removed before the
//     request goes on to Koha.

import { hmacSign, hmacVerify, pbkdf2, fromBase64, timingSafeEqualStr } from "./crypto";
import type { Env, LibraryRow } from "./env";
import { now } from "./env";
import { ipInAny } from "./netaddr";

export const SESSION_COOKIE = "__Host-kei_staff";
export const SESSION_TTL_SECONDS = 12 * 3600;
const REALM = "Koha staff (remote access)";

export interface StaffHostEnv {
  NAME_PREFIX: string;
  STAFF_SUFFIX: string;
  ZONE_NAME: string;
}

/** The library slug of a staff hostname, or null when the host is not one. */
export function staffSlugFromHost(host: string, env: StaffHostEnv): string | null {
  const h = host.toLowerCase().replace(/\.$/, "");
  const tail = `${env.STAFF_SUFFIX}.${env.ZONE_NAME}`.toLowerCase();
  if (!env.STAFF_SUFFIX || !h.endsWith(tail)) return null;
  const label = h.slice(0, -tail.length);
  if (!label || label.includes(".") || !label.startsWith(env.NAME_PREFIX)) return null;
  const slug = label.slice(env.NAME_PREFIX.length);
  return /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(slug) ? slug : null;
}

export function parseBasicAuth(header: string | null): { user: string; pass: string } | null {
  const m = /^Basic\s+([A-Za-z0-9+/=]+)\s*$/i.exec(header ?? "");
  if (!m) return null;
  const raw = fromBase64(m[1]!);
  if (!raw) return null;
  let decoded: string;
  try {
    decoded = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(raw);
  } catch {
    return null;
  }
  const i = decoded.indexOf(":");
  if (i < 0) return null;
  return { user: decoded.slice(0, i), pass: decoded.slice(i + 1) };
}

export function getCookie(header: string | null, name: string): string | null {
  for (const part of (header ?? "").split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    if (part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return null;
}

export function removeCookie(header: string | null, name: string): string {
  return (header ?? "")
    .split(";")
    .map((p) => p.trim())
    .filter((p) => p && p.slice(0, p.indexOf("=") < 0 ? p.length : p.indexOf("=")).trim() !== name)
    .join("; ");
}

function sessionMessage(libraryId: string, credVersion: number, expires: number): string {
  return `kei-staff-v1|${libraryId}|${credVersion}|${expires}`;
}

/** Cookie value: <credVersion>.<expires>.<hmac>; the library is implied by the hostname. */
export async function makeSessionValue(key: string, libraryId: string, credVersion: number, nowSeconds: number): Promise<string> {
  const expires = nowSeconds + SESSION_TTL_SECONDS;
  return `${credVersion}.${expires}.${await hmacSign(key, sessionMessage(libraryId, credVersion, expires))}`;
}

export async function verifySessionValue(
  key: string,
  value: string | null,
  libraryId: string,
  credVersion: number,
  nowSeconds: number,
): Promise<boolean> {
  const m = /^(\d{1,10})\.(\d{1,12})\.([A-Za-z0-9_-]{43})$/.exec(value ?? "");
  if (!m) return false;
  const version = Number(m[1]);
  const expires = Number(m[2]);
  if (version !== credVersion || expires <= nowSeconds || expires > nowSeconds + SESSION_TTL_SECONDS) return false;
  return hmacVerify(key, sessionMessage(libraryId, version, expires), m[3]!);
}

export function sessionCookieHeader(value: string): string {
  return `${SESSION_COOKIE}=${value}; Path=/; Max-Age=${SESSION_TTL_SECONDS}; Secure; HttpOnly; SameSite=Lax`;
}

/** The request Koha receives: without the gate's password and cookie. */
export function stripGateCredentials(request: Request, staffUser: string | null): Request {
  const headers = new Headers(request.headers);
  const basic = parseBasicAuth(headers.get("Authorization"));
  if (basic && (staffUser === null || basic.user === staffUser)) headers.delete("Authorization");
  const cookie = removeCookie(headers.get("Cookie"), SESSION_COOKIE);
  if (cookie) headers.set("Cookie", cookie);
  else headers.delete("Cookie");
  return new Request(request, { headers });
}

function textResponse(status: number, text: string, headers: Record<string, string> = {}): Response {
  return new Response(`${text}\n`, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex", ...headers },
  });
}

async function checkPassword(lib: LibraryRow, user: string, pass: string): Promise<boolean> {
  if (!lib.staff_user || !lib.staff_pass_hash || !lib.staff_pass_salt || !lib.staff_pass_iter) return false;
  const salt = fromBase64(lib.staff_pass_salt);
  if (!salt) return false;
  const hash = await pbkdf2(pass, salt, lib.staff_pass_iter);
  const userOk = await timingSafeEqualStr(user, lib.staff_user);
  const passOk = await timingSafeEqualStr(hash, lib.staff_pass_hash);
  return userOk && passOk;
}

export interface GateOptions {
  /** Forwards the cleaned request to the origin (the library's tunnel). */
  forward?: (request: Request) => Promise<Response>;
}

export async function staffGate(request: Request, env: Env, opts: GateOptions = {}): Promise<Response> {
  const url = new URL(request.url);
  const slug = staffSlugFromHost(url.hostname, env);
  if (!slug) return textResponse(404, "Not found.");
  const lib = await env.DB.prepare("SELECT * FROM libraries WHERE slug = ? AND status IN ('active', 'suspended')")
    .bind(slug)
    .first<LibraryRow>();
  if (!lib) return textResponse(404, "This address is not in use.");

  // 1. Closed until the library turns remote staff access on.
  if (!lib.staff_pass_hash) return textResponse(403, "Remote access to the staff interface is turned off for this library.");
  if (!env.STAFF_SESSION_KEY || env.STAFF_SESSION_KEY.length < 32) {
    return textResponse(503, "Remote staff access is not configured on the address service.");
  }

  // 2. Optional network allowlist.
  const ip = request.headers.get("CF-Connecting-IP") ?? "";
  if (lib.staff_allow_cidrs) {
    let cidrs: string[] = [];
    try {
      cidrs = JSON.parse(lib.staff_allow_cidrs) as string[];
    } catch {
      cidrs = [];
    }
    if (!ipInAny(ip, cidrs)) return textResponse(403, "This network is not allowed to reach the staff interface.");
  }

  const forward = opts.forward ?? ((r: Request) => fetch(r));
  const t = now();

  // 3a. Valid session.
  const cookie = getCookie(request.headers.get("Cookie"), SESSION_COOKIE);
  if (await verifySessionValue(env.STAFF_SESSION_KEY, cookie, lib.id, lib.staff_cred_version, t)) {
    return forward(stripGateCredentials(request, lib.staff_user));
  }

  // 3b. Basic Auth, rate limited per IP and library.
  if (!(await env.RL_STAFF.limit({ key: `${ip}|${lib.id}` })).success) {
    return textResponse(429, "Too many attempts. Wait a minute and try again.", { "Retry-After": "60" });
  }
  const basic = parseBasicAuth(request.headers.get("Authorization"));
  if (!basic || !(await checkPassword(lib, basic.user, basic.pass))) {
    return textResponse(401, "Remote access user and password required.", {
      "WWW-Authenticate": `Basic realm="${REALM}", charset="UTF-8"`,
    });
  }

  const res = await forward(stripGateCredentials(request, lib.staff_user));
  const out = new Response(res.body, res);
  out.headers.append("Set-Cookie", sessionCookieHeader(await makeSessionValue(env.STAFF_SESSION_KEY, lib.id, lib.staff_cred_version, t)));
  return out;
}
