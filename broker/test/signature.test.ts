// Signatures made by openssl (scripts/kei-sign.sh, and the installer's own
// broker_sign_headers function) must verify in the Worker code, and every
// tampering must fail.

import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { beforeAll, describe, expect, it } from "vitest";
import { checkSignedRequest, isValidPublicKey, MAX_SKEW_SECONDS, type SignatureDeps } from "../src/signature";

const here = dirname(fileURLToPath(import.meta.url));
const SIGNER = resolve(here, "../scripts/kei-sign.sh");
const INSTALLER = resolve(here, "../../installer");
const LIB = "3f2a6c1e-8b7d-4c5e-9a10-0b1c2d3e4f50";

let dir: string;
let key: string;
let pub: string;

function sh(args: string[], input?: string): string {
  return execFileSync("bash", args, { encoding: "utf8", input });
}

function headersFrom(text: string): Headers {
  const h = new Headers();
  for (const line of text.trim().split("\n")) {
    const i = line.indexOf(":");
    h.set(line.slice(0, i), line.slice(i + 1).trim());
  }
  return h;
}

function signWithScript(method: string, path: string, body?: string): Headers {
  const args = [SIGNER, "headers", key, LIB, method, path];
  if (body !== undefined) {
    const f = join(dir, `body-${Math.random().toString(36).slice(2)}`);
    writeFileSync(f, body);
    args.push(f);
  }
  return headersFrom(sh(args));
}

function deps(over: Partial<SignatureDeps> = {}): SignatureDeps & { nonces: Set<string> } {
  const nonces = new Set<string>();
  return {
    nonces,
    now: Math.floor(Date.now() / 1000),
    lookupKey: async (id) => (id === LIB ? pub : null),
    consumeNonce: async (id, nonce) => {
      const k = `${id}|${nonce}`;
      if (nonces.has(k)) return false;
      nonces.add(k);
      return true;
    },
    ...over,
  };
}

const enc = (s: string) => new TextEncoder().encode(s).buffer as ArrayBuffer;
const empty = new ArrayBuffer(0);
const url = (p: string) => new URL(`https://broker.koha.nexus${p}`);

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "kei-sig-"));
  key = join(dir, "lib.key");
  sh([SIGNER, "keygen", key]);
  pub = sh([SIGNER, "pubkey", key]).trim();
});

describe("public keys", () => {
  it("accepts the raw 32-byte key printed by kei-sign.sh", () => {
    expect(isValidPublicKey(pub)).toBe(true);
  });
  it("rejects other shapes", () => {
    expect(isValidPublicKey("")).toBe(false);
    expect(isValidPublicKey(btoa("x".repeat(31)))).toBe(false);
    expect(isValidPublicKey(btoa("x".repeat(33)))).toBe(false);
    expect(isValidPublicKey(pub.replace(/=$/, ""))).toBe(false);
  });
});

describe("checkSignedRequest with kei-sign.sh", () => {
  it("verifies a GET without body", async () => {
    const h = signWithScript("GET", "/v1/tunnel-token");
    expect(await checkSignedRequest("GET", url("/v1/tunnel-token"), h, empty, deps())).toEqual({ ok: true, libraryId: LIB });
  });

  it("verifies a POST with a JSON body and a query string", async () => {
    const body = '{"koha_version":"24.11","installer_version":"1.5.4"}';
    const h = signWithScript("post", "/v1/heartbeat?x=1&y=%20z", body);
    const r = await checkSignedRequest("POST", url("/v1/heartbeat?x=1&y=%20z"), h, enc(body), deps());
    expect(r).toEqual({ ok: true, libraryId: LIB });
  });

  it("rejects a tampered body, path, query or method", async () => {
    const body = '{"a":1}';
    const h = signWithScript("POST", "/v1/heartbeat", body);
    expect((await checkSignedRequest("POST", url("/v1/heartbeat"), h, enc('{"a":2}'), deps())).ok).toBe(false);
    expect((await checkSignedRequest("POST", url("/v1/rotate"), h, enc(body), deps())).ok).toBe(false);
    expect((await checkSignedRequest("POST", url("/v1/heartbeat?a=1"), h, enc(body), deps())).ok).toBe(false);
    expect((await checkSignedRequest("PUT", url("/v1/heartbeat"), h, enc(body), deps())).ok).toBe(false);
  });

  it("rejects a replayed nonce", async () => {
    const d = deps();
    const h = signWithScript("GET", "/v1/library");
    expect((await checkSignedRequest("GET", url("/v1/library"), h, empty, d)).ok).toBe(true);
    expect(await checkSignedRequest("GET", url("/v1/library"), h, empty, d)).toMatchObject({ ok: false, error: "replayed request" });
  });

  it("rejects clock skew over 5 minutes before looking up the key", async () => {
    const h = signWithScript("GET", "/v1/library");
    let looked = false;
    const d = deps({
      now: Number(h.get("X-KEI-Timestamp")) + MAX_SKEW_SECONDS + 1,
      lookupKey: async () => {
        looked = true;
        return pub;
      },
    });
    expect((await checkSignedRequest("GET", url("/v1/library"), h, empty, d)).ok).toBe(false);
    expect(looked).toBe(false);
    const d2 = deps({ now: Number(h.get("X-KEI-Timestamp")) - MAX_SKEW_SECONDS });
    expect((await checkSignedRequest("GET", url("/v1/library"), h, empty, d2)).ok).toBe(true);
  });

  it("rejects an unknown library or a removed key, without using up the nonce", async () => {
    const h = signWithScript("GET", "/v1/library");
    const d = deps({ lookupKey: async () => null });
    expect(await checkSignedRequest("GET", url("/v1/library"), h, empty, d)).toMatchObject({ ok: false, status: 401 });
    expect(d.nonces.size).toBe(0);
  });

  it("does not store the nonce of a bad signature", async () => {
    const h = signWithScript("GET", "/v1/library");
    const d = deps();
    expect((await checkSignedRequest("GET", url("/v1/rotate"), h, empty, d)).ok).toBe(false);
    expect(d.nonces.size).toBe(0);
    // The genuine request still goes through afterwards.
    expect((await checkSignedRequest("GET", url("/v1/library"), h, empty, d)).ok).toBe(true);
  });

  it("rejects a signature by another key", async () => {
    const other = join(dir, "other.key");
    sh([SIGNER, "keygen", other]);
    const h = headersFrom(sh([SIGNER, "headers", other, LIB, "GET", "/v1/library"]));
    expect((await checkSignedRequest("GET", url("/v1/library"), h, empty, deps())).ok).toBe(false);
  });

  it("rejects malformed headers", async () => {
    const good = signWithScript("GET", "/v1/library");
    const cases: [string, string][] = [
      ["X-KEI-Nonce", "short"],
      ["X-KEI-Nonce", "bad nonce with spaces!!"],
      ["X-KEI-Timestamp", "12a"],
      ["X-KEI-Signature", "not-base64"],
      ["X-KEI-Library", "../etc"],
    ];
    for (const [name, value] of cases) {
      const h = new Headers(good);
      h.set(name, value);
      expect((await checkSignedRequest("GET", url("/v1/library"), h, empty, deps())).ok, name).toBe(false);
    }
    expect(await checkSignedRequest("GET", url("/v1/library"), new Headers(), empty, deps())).toMatchObject({ ok: false, status: 401 });
  });
});

describe("the installer's broker_sign_headers", () => {
  it("produces signatures the Worker accepts", async () => {
    const src = readFileSync(INSTALLER, "utf8");
    const m = /^broker_sign_headers\(\) \{\n[\s\S]*?\n\}\n/m.exec(src);
    expect(m, "broker_sign_headers in installer").not.toBeNull();
    const body = '{"username":"biblioteca","password":"uma senha bem longa","allow_cidrs":[]}';
    const bodyFile = join(dir, "inst-body");
    writeFileSync(bodyFile, body);
    const script = `${m![0]}
tunnel_conf_get() { [ "$1" = LIBRARY_ID ] && printf '%s' "${LIB}"; }
BROKER_KEY="${key}"
broker_sign_headers PUT /v1/staff-credentials "${bodyFile}"`;
    const h = headersFrom(sh(["-c", script]));
    expect(h.get("X-KEI-Library")).toBe(LIB);
    const r = await checkSignedRequest("PUT", url("/v1/staff-credentials"), h, enc(body), deps());
    expect(r).toEqual({ ok: true, libraryId: LIB });
  });
});
