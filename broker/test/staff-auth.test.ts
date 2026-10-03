// Staff gate: helpers, and the gate itself with a stub database.

import { describe, expect, it } from "vitest";
import { pbkdf2, toBase64 } from "../src/crypto";
import type { Env, LibraryRow } from "../src/env";
import {
  getCookie,
  makeSessionValue,
  parseBasicAuth,
  removeCookie,
  SESSION_COOKIE,
  staffGate,
  staffSlugFromHost,
  stripGateCredentials,
  verifySessionValue,
} from "../src/staff-auth";

const KEY = "k".repeat(40);
const LIB_ID = "11111111-2222-4333-8444-555555555555";
const hostEnv = { NAME_PREFIX: "t-", STAFF_SUFFIX: "-admin", ZONE_NAME: "example.org" };

describe("staffSlugFromHost", () => {
  it("extracts the slug of staff hostnames only", () => {
    expect(staffSlugFromHost("t-palotina-pr-admin.example.org", hostEnv)).toBe("palotina-pr");
    expect(staffSlugFromHost("T-Palotina-PR-Admin.Example.org.", hostEnv)).toBe("palotina-pr");
    expect(staffSlugFromHost("t-palotina-pr.example.org", hostEnv)).toBeNull();
    expect(staffSlugFromHost("palotina-pr-admin.example.org", hostEnv)).toBeNull();
    expect(staffSlugFromHost("a.t-x-admin.example.org", hostEnv)).toBeNull();
    expect(staffSlugFromHost("t-x-admin.example.org.evil.com", hostEnv)).toBeNull();
    expect(staffSlugFromHost("broker.koha.nexus", { NAME_PREFIX: "", STAFF_SUFFIX: "-admin", ZONE_NAME: "koha.nexus" })).toBeNull();
  });
});

describe("Basic auth and cookies", () => {
  it("parses Basic credentials with a colon in the password", () => {
    expect(parseBasicAuth(`Basic ${btoa("user:pa:ss")}`)).toEqual({ user: "user", pass: "pa:ss" });
    expect(parseBasicAuth("Bearer x")).toBeNull();
    expect(parseBasicAuth(`Basic ${btoa("nocolon")}`)).toBeNull();
    expect(parseBasicAuth(null)).toBeNull();
  });
  it("reads and removes one cookie", () => {
    const h = `a=1; ${SESSION_COOKIE}=v; CGISESSID=abc`;
    expect(getCookie(h, SESSION_COOKIE)).toBe("v");
    expect(removeCookie(h, SESSION_COOKIE)).toBe("a=1; CGISESSID=abc");
  });
  it("session values are bound to library, credential version and time", async () => {
    const t = 1_800_000_000;
    const v = await makeSessionValue(KEY, LIB_ID, 3, t);
    expect(await verifySessionValue(KEY, v, LIB_ID, 3, t + 60)).toBe(true);
    expect(await verifySessionValue(KEY, v, LIB_ID, 4, t + 60)).toBe(false); // password changed
    expect(await verifySessionValue(KEY, v, "other", 3, t + 60)).toBe(false);
    expect(await verifySessionValue(KEY, v, LIB_ID, 3, t + 12 * 3600 + 1)).toBe(false); // expired
    expect(await verifySessionValue("x".repeat(40), v, LIB_ID, 3, t)).toBe(false);
    expect(await verifySessionValue(KEY, v.replace(/^3\./, "4."), LIB_ID, 4, t)).toBe(false);
  });
  it("strips only the gate's own credentials", () => {
    const req = new Request("https://t-x-admin.example.org/", {
      headers: { Authorization: `Basic ${btoa("biblioteca:secret")}`, Cookie: `${SESSION_COOKIE}=v; CGISESSID=abc` },
    });
    const out = stripGateCredentials(req, "biblioteca");
    expect(out.headers.get("Authorization")).toBeNull();
    expect(out.headers.get("Cookie")).toBe("CGISESSID=abc");
    const api = new Request("https://t-x-admin.example.org/api/v1/patrons", { headers: { Authorization: `Basic ${btoa("kohaapi:pw")}` } });
    expect(stripGateCredentials(api, "biblioteca").headers.get("Authorization")).not.toBeNull();
  });
});

async function makeEnv(lib: Partial<LibraryRow> | null, limitOk = true): Promise<Env> {
  const row = lib ? ({ id: LIB_ID, slug: "x", status: "active", staff_cred_version: 1, ...lib } as LibraryRow) : null;
  const db = {
    prepare: () => ({ bind: () => ({ first: async () => row }) }),
  };
  return {
    ...hostEnv,
    DB: db as unknown as D1Database,
    RL_STAFF: { limit: async () => ({ success: limitOk }) },
    STAFF_SESSION_KEY: KEY,
  } as unknown as Env;
}

async function withPassword(pass: string, extra: Partial<LibraryRow> = {}): Promise<Partial<LibraryRow>> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return {
    staff_user: "biblioteca",
    staff_pass_hash: await pbkdf2(pass, salt, 1000),
    staff_pass_salt: toBase64(salt),
    staff_pass_iter: 1000,
    ...extra,
  };
}

const origin = async (r: Request) =>
  new Response(JSON.stringify({ koha: true, authorization: r.headers.get("Authorization"), cookie: r.headers.get("Cookie") }));

const staffReq = (headers: Record<string, string> = {}) =>
  new Request("https://t-x-admin.example.org/cgi-bin/koha/mainpage.pl", { headers: { "CF-Connecting-IP": "200.10.1.2", ...headers } });

describe("staffGate", () => {
  it("answers 404 for an unknown library and 403 until credentials are set", async () => {
    expect((await staffGate(staffReq(), await makeEnv(null), { forward: origin })).status).toBe(404);
    expect((await staffGate(staffReq(), await makeEnv({}), { forward: origin })).status).toBe(403);
  });

  it("asks for the password, refuses a wrong one and passes the right one with a session cookie", async () => {
    const env = await makeEnv(await withPassword("uma senha bem longa"));
    const none = await staffGate(staffReq(), env, { forward: origin });
    expect(none.status).toBe(401);
    expect(none.headers.get("WWW-Authenticate")).toMatch(/^Basic realm=/);
    const wrong = await staffGate(staffReq({ Authorization: `Basic ${btoa("biblioteca:errada")}` }), env, { forward: origin });
    expect(wrong.status).toBe(401);
    const good = await staffGate(staffReq({ Authorization: `Basic ${btoa("biblioteca:uma senha bem longa")}`, Cookie: "CGISESSID=abc" }), env, {
      forward: origin,
    });
    expect(good.status).toBe(200);
    expect(await good.json()).toEqual({ koha: true, authorization: null, cookie: "CGISESSID=abc" });
    const setCookie = good.headers.get("Set-Cookie")!;
    expect(setCookie).toMatch(/^__Host-kei_staff=.+; Path=\/; Max-Age=43200; Secure; HttpOnly/);

    // The cookie alone is enough afterwards, and Koha never sees it.
    const cookie = setCookie.split(";")[0]!;
    const again = await staffGate(staffReq({ Cookie: `${cookie}; CGISESSID=abc` }), env, { forward: origin });
    expect(again.status).toBe(200);
    expect(await again.json()).toMatchObject({ cookie: "CGISESSID=abc" });

    // A password change (new credential version) ends the session.
    const env2 = await makeEnv(await withPassword("outra senha bem longa", { staff_cred_version: 2 }));
    expect((await staffGate(staffReq({ Cookie: cookie }), env2, { forward: origin })).status).toBe(401);
  });

  it("applies the network allowlist", async () => {
    const env = await makeEnv(await withPassword("uma senha bem longa", { staff_allow_cidrs: JSON.stringify(["10.0.0.0/8"]) }));
    const auth = { Authorization: `Basic ${btoa("biblioteca:uma senha bem longa")}` };
    expect((await staffGate(staffReq(auth), env, { forward: origin })).status).toBe(403);
    expect((await staffGate(staffReq({ ...auth, "CF-Connecting-IP": "10.2.3.4" }), env, { forward: origin })).status).toBe(200);
  });

  it("rate limits attempts without a session", async () => {
    const env = await makeEnv(await withPassword("uma senha bem longa"), false);
    const r = await staffGate(staffReq({ Authorization: `Basic ${btoa("biblioteca:uma senha bem longa")}` }), env, { forward: origin });
    expect(r.status).toBe(429);
  });
});
