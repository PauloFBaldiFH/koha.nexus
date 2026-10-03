// Ed25519 request signatures (see README "Signatures (Ed25519)").
//
// Signed string, no trailing newline:
//   KEI-SIG-v1\n<METHOD>\n<path?query>\n<unix time>\n<nonce>\n<sha256 hex of body>
//
// Check order: header format, clock skew, key of a live library, signature,
// and only then the nonce. An unsigned caller therefore cannot use up
// nonces, and a replayed request is rejected.

import { fromBase64, sha256Hex } from "./crypto";

export const SIG_VERSION = "KEI-SIG-v1";
export const MAX_SKEW_SECONDS = 300;
/** Nonces are kept a little longer than the window in which a timestamp is accepted. */
export const NONCE_TTL_SECONDS = 2 * MAX_SKEW_SECONDS + 60;

const LIBRARY_ID_RE = /^[A-Za-z0-9-]{1,64}$/;
const TIMESTAMP_RE = /^\d{1,12}$/;
const NONCE_RE = /^[A-Za-z0-9_-]{16,64}$/;

export interface SignatureDeps {
  now: number;
  /** Public key (base64) of a live library, or null. */
  lookupKey(libraryId: string): Promise<string | null>;
  /** Stores the nonce; false when it was already used. */
  consumeNonce(libraryId: string, nonce: string, expiresAt: number): Promise<boolean>;
}

export type SignatureResult = { ok: true; libraryId: string } | { ok: false; status: 400 | 401; error: string };

/** A raw 32-byte Ed25519 public key in standard base64. */
export function isValidPublicKey(b64: string): boolean {
  const raw = fromBase64(b64);
  return raw !== null && raw.length === 32;
}

export async function canonicalString(
  method: string,
  pathAndQuery: string,
  timestamp: string,
  nonce: string,
  body: ArrayBuffer | Uint8Array,
): Promise<string> {
  return [SIG_VERSION, method.toUpperCase(), pathAndQuery, timestamp, nonce, await sha256Hex(body)].join("\n");
}

export async function verifyEd25519(publicKeyB64: string, signature: Uint8Array, message: string): Promise<boolean> {
  const raw = fromBase64(publicKeyB64);
  if (!raw || raw.length !== 32 || signature.length !== 64) return false;
  try {
    const key = await crypto.subtle.importKey("raw", raw, { name: "Ed25519" }, false, ["verify"]);
    return await crypto.subtle.verify({ name: "Ed25519" }, key, signature, new TextEncoder().encode(message));
  } catch {
    return false;
  }
}

const fail = (status: 400 | 401, error: string): SignatureResult => ({ ok: false, status, error });

export async function checkSignedRequest(
  method: string,
  url: URL,
  headers: Headers,
  body: ArrayBuffer,
  deps: SignatureDeps,
): Promise<SignatureResult> {
  // 1. Header format.
  const libraryId = headers.get("X-KEI-Library") ?? "";
  const ts = headers.get("X-KEI-Timestamp") ?? "";
  const nonce = headers.get("X-KEI-Nonce") ?? "";
  const sigB64 = headers.get("X-KEI-Signature") ?? "";
  if (!libraryId && !ts && !nonce && !sigB64) return fail(401, "signature required");
  if (!LIBRARY_ID_RE.test(libraryId) || !TIMESTAMP_RE.test(ts) || !NONCE_RE.test(nonce)) {
    return fail(401, "malformed signature headers");
  }
  const sig = fromBase64(sigB64);
  if (!sig || sig.length !== 64) return fail(401, "malformed signature headers");

  // 2. Clock skew.
  const t = Number(ts);
  if (Math.abs(deps.now - t) > MAX_SKEW_SECONDS) return fail(401, "request timestamp is too far from the server clock");

  // 3. Key of a live library.
  const key = await deps.lookupKey(libraryId);
  if (!key) return fail(401, "invalid signature");

  // 4. Signature over method, path and query, time, nonce and body.
  const message = await canonicalString(method, url.pathname + url.search, ts, nonce, body);
  if (!(await verifyEd25519(key, sig, message))) return fail(401, "invalid signature");

  // 5. Only now the nonce: a second use is a replay.
  if (!(await deps.consumeNonce(libraryId, nonce, deps.now + NONCE_TTL_SECONDS))) return fail(401, "replayed request");

  return { ok: true, libraryId };
}
