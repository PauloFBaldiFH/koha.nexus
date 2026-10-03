// In-memory fake of the parts of the Cloudflare API v4 the broker uses
// (remotely managed tunnels and DNS records of one zone). Used by the unit
// tests (as the CloudflareApi fetcher) and by the local end-to-end runs (as
// Miniflare's outbound service). Plain JavaScript so Node can load it
// without a build step.

export const FAKE_TOKEN = "fake-cf-api-token-0123456789";
export const FAKE_ACCOUNT = "acc0000000000000000000000000000a";
export const FAKE_ZONE = "zon0000000000000000000000000000z";

export function createFakeCloudflare({ token = FAKE_TOKEN, accountId = FAKE_ACCOUNT, zoneId = FAKE_ZONE } = {}) {
  let seq = 0;
  const id = (p) => `${p}${(++seq).toString(16).padStart(7, "0")}-0000-4000-8000-${Date.now().toString(16).padStart(12, "0").slice(-12)}`;
  const state = {
    tunnels: [], // { id, name, created_at, config_src, ingress }
    dns_records: [], // { id, type, name, content, proxied, comment, created_on }
    rotations: {}, // tunnelId -> count
    calls: [], // "METHOD /path"
  };
  const failures = []; // { method, re, status, remaining, code }

  const ok = (result, extra = {}) =>
    new Response(JSON.stringify({ success: true, errors: [], messages: [], result, ...extra }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  const err = (status, code, message) =>
    new Response(JSON.stringify({ success: false, errors: [{ code, message }], messages: [], result: null }), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const page = (list, q) => {
    const per = Number(q.get("per_page") || 20);
    const p = Number(q.get("page") || 1);
    const slice = list.slice((p - 1) * per, p * per);
    return ok(slice, { result_info: { page: p, per_page: per, count: slice.length, total_count: list.length, total_pages: Math.max(1, Math.ceil(list.length / per)) } });
  };

  async function handle(request) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/client\/v4/, "");
    const method = request.method;
    state.calls.push(`${method} ${path}`);
    if (request.headers.get("Authorization") !== `Bearer ${token}`) return err(403, 10000, "Authentication error");
    for (const f of failures) {
      if (f.remaining > 0 && (!f.method || f.method === method) && f.re.test(path)) {
        f.remaining--;
        return err(f.status, f.code ?? 1000 + f.status, `injected failure ${f.status}`);
      }
    }
    const body = method === "GET" || method === "DELETE" ? null : await request.json().catch(() => null);
    const q = url.searchParams;
    let m;

    // ---- Tunnels ----
    if ((m = /^\/accounts\/([^/]+)\/cfd_tunnel$/.exec(path))) {
      if (m[1] !== accountId) return err(403, 9109, "Unauthorized to access requested resource");
      if (method === "GET") {
        const name = q.get("name");
        return page(state.tunnels.filter((t) => !name || t.name === name), q);
      }
      if (method === "POST") {
        if (!body?.name) return err(400, 1003, "name is required");
        if (state.tunnels.some((t) => t.name === body.name)) return err(409, 1013, "You already have a tunnel with this name");
        const t = { id: id("7"), name: body.name, created_at: new Date().toISOString(), deleted_at: null, config_src: body.config_src, ingress: null };
        state.tunnels.push(t);
        return ok(t);
      }
    }
    if ((m = /^\/accounts\/([^/]+)\/cfd_tunnel\/([^/]+)(\/[a-z]+)?$/.exec(path))) {
      if (m[1] !== accountId) return err(403, 9109, "Unauthorized to access requested resource");
      const t = state.tunnels.find((x) => x.id === m[2]);
      if (!t) return err(404, 1002, "Tunnel not found");
      const sub = m[3] ?? "";
      if (sub === "/configurations" && method === "PUT") {
        if (!Array.isArray(body?.config?.ingress)) return err(400, 1003, "config.ingress required");
        t.ingress = body.config.ingress;
        return ok({ tunnel_id: t.id, config: body.config, version: 1 });
      }
      if (sub === "/token" && method === "GET") return ok(`tunnel-token-for-${t.id}-${state.rotations[t.id] ?? 0}`);
      if (sub === "/connections" && method === "DELETE") return ok(null);
      if (sub === "" && method === "PATCH") {
        if (typeof body?.tunnel_secret !== "string" || atob(body.tunnel_secret).length < 32) return err(400, 1003, "tunnel_secret must be 32+ bytes");
        state.rotations[t.id] = (state.rotations[t.id] ?? 0) + 1;
        return ok(t);
      }
      if (sub === "" && method === "DELETE") {
        state.tunnels = state.tunnels.filter((x) => x !== t);
        return ok(t);
      }
    }

    // ---- DNS ----
    if ((m = /^\/zones\/([^/]+)\/dns_records$/.exec(path))) {
      if (m[1] !== zoneId) return err(403, 9109, "Unauthorized to access requested resource");
      if (method === "GET") {
        const name = q.get("name");
        const type = q.get("type");
        return page(state.dns_records.filter((r) => (!name || r.name === name) && (!type || r.type === type)), q);
      }
      if (method === "POST") {
        if (!body?.name || !body?.type) return err(400, 1004, "DNS Validation Error");
        if (state.dns_records.some((r) => r.name === body.name)) {
          return err(400, 81053, "An A, AAAA, or CNAME record with that host already exists.");
        }
        const r = { id: id("d"), type: body.type, name: body.name, content: body.content, proxied: !!body.proxied, ttl: body.ttl ?? 1, comment: body.comment ?? null, created_on: new Date().toISOString() };
        state.dns_records.push(r);
        return ok(r);
      }
    }
    if ((m = /^\/zones\/([^/]+)\/dns_records\/([^/]+)$/.exec(path)) && method === "DELETE") {
      if (m[1] !== zoneId) return err(403, 9109, "Unauthorized to access requested resource");
      const r = state.dns_records.find((x) => x.id === m[2]);
      if (!r) return err(404, 81044, "Record does not exist.");
      state.dns_records = state.dns_records.filter((x) => x !== r);
      return ok({ id: r.id });
    }
    return err(404, 7003, `No route for ${method} ${path}`);
  }

  return {
    state,
    handle,
    fetcher: (input, init) => handle(input instanceof Request ? input : new Request(input, init)),
    /** The next `count` calls matching method + path regex answer `status`. */
    failNext(method, re, status, count = 1, code) {
      failures.push({ method, re, status, remaining: count, code });
    },
    /** Adds a record that is not managed by the broker (no kei comment). */
    addForeignRecord(name, content = "192.0.2.10", type = "A") {
      const r = { id: id("d"), type, name, content, proxied: false, ttl: 1, comment: null, created_on: new Date().toISOString() };
      state.dns_records.push(r);
      return r;
    },
    /** Public view used by tests (no internals). */
    snapshot() {
      return {
        tunnels: state.tunnels.map(({ id, name, created_at, ingress }) => ({ id, name, created_at, ingress })),
        dns_records: state.dns_records.map(({ id, type, name, content, proxied, comment }) => ({ id, type, name, content, proxied, comment })),
        rotations: state.rotations,
      };
    },
  };
}
