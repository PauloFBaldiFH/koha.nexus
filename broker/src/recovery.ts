// Recovery codes: shown once at enrollment, written down by the librarian,
// and used to take the address back on a reinstalled or new server. The
// broker keeps only the sha256 of the normalized code.

import { randomBytes, sha256Hex } from "./crypto";
import type { HostEnv } from "./names";

// No vowels (no words), no 0/O/1/I lookalikes.
const ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789";
const GROUPS = 4;
const GROUP_LEN = 4;

/** 16 random symbols (about 77 bits) as XXXX-XXXX-XXXX-XXXX. */
export function recoveryCode(): string {
  const out: string[] = [];
  // Rejection sampling keeps every symbol equally likely.
  const limit = 256 - (256 % ALPHABET.length);
  while (out.length < GROUPS * GROUP_LEN) {
    for (const b of randomBytes(32)) {
      if (b < limit && out.length < GROUPS * GROUP_LEN) out.push(ALPHABET[b % ALPHABET.length]!);
    }
  }
  const s = out.join("");
  return Array.from({ length: GROUPS }, (_, i) => s.slice(i * GROUP_LEN, (i + 1) * GROUP_LEN)).join("-");
}

/** Uppercase, spaces and hyphens dropped. Null when it cannot be a code. */
export function normalizeRecoveryCode(input: string): string | null {
  const s = input.toUpperCase().replace(/[\s-]/g, "");
  if (s.length !== GROUPS * GROUP_LEN || ![...s].every((c) => ALPHABET.includes(c))) return null;
  return s;
}

export async function recoveryHash(normalized: string): Promise<string> {
  return sha256Hex(`kei-recovery-v1|${normalized}`);
}

/**
 * The name part of what the librarian typed: the slug itself, the OPAC or
 * staff hostname, or a full URL. Returns "" when nothing usable is left.
 */
export function slugFromAddress(input: string, env: HostEnv): string {
  let s = input.trim().toLowerCase();
  s = s.replace(/^[a-z]+:\/\//, "").replace(/[/?#].*$/, "");
  const zone = `.${env.ZONE_NAME.toLowerCase()}`;
  if (s.endsWith(zone)) s = s.slice(0, -zone.length);
  if (s.includes(".")) return "";
  if (env.NAME_PREFIX && s.startsWith(env.NAME_PREFIX)) s = s.slice(env.NAME_PREFIX.length);
  if (env.STAFF_SUFFIX && s.endsWith(env.STAFF_SUFFIX)) s = s.slice(0, -env.STAFF_SUFFIX.length);
  return /^[a-z0-9-]{1,63}$/.test(s) ? s : "";
}
