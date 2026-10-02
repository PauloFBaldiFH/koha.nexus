// Minimal Cloudflare API v4 client for what the broker needs: remotely
// managed tunnels and proxied CNAME records in one zone. The token is only
// ever placed in the Authorization header; errors never include it.

export class CfApiError extends Error {
  constructor(
    readonly status: number,
    readonly codes: number[],
    message: string,
  ) {
    super(message);
    this.name = "CfApiError";
  }
  get retryable(): boolean {
    return this.status === 429 || this.status >= 500;
  }
  get notFound(): boolean {
    return this.status === 404;
  }
}

export interface CfConfig {
  token: string;
  accountId: string;
  zoneId: string;
  fetcher?: typeof fetch;
  base?: string;
}

export interface Tunnel {
  id: string;
  name: string;
  created_at: string;
  deleted_at?: string | null;
}

export interface DnsRecord {
  id: string;
  name: string;
  type: string;
  content: string;
  proxied?: boolean;
  comment?: string | null;
  created_on?: string;
}

export interface IngressRule {
  hostname?: string;
  service: string;
}

interface Envelope<T> {
  success: boolean;
  result: T;
  errors?: { code: number; message: string }[];
  result_info?: { page: number; total_pages: number };
}

export class CloudflareApi {
  private readonly base: string;

  constructor(private readonly c: CfConfig) {
    this.base = c.base ?? "https://api.cloudflare.com/client/v4";
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<Envelope<T>> {
    const doFetch = this.c.fetcher ?? fetch;
    const res = await doFetch(`${this.base}${path}`, {
      method,
      headers: { Authorization: `Bearer ${this.c.token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let data: Envelope<T> | null = null;
    try {
      data = (await res.json()) as Envelope<T>;
    } catch {
      data = null;
    }
    if (!res.ok || !data?.success) {
      const errs = data?.errors ?? [];
      const detail = errs.map((e) => `${e.code}: ${e.message}`).join("; ") || "no error body";
      throw new CfApiError(res.status, errs.map((e) => e.code), `${method} ${path.split("?")[0]} -> ${res.status} ${detail}`);
    }
    return data;
  }

  private acct(path: string): string {
    return `/accounts/${this.c.accountId}${path}`;
  }

  private zone(path: string): string {
    return `/zones/${this.c.zoneId}${path}`;
  }

  // ---- Tunnels (remotely managed: ingress lives at Cloudflare) ----

  async createTunnel(name: string): Promise<Tunnel> {
    return (await this.call<Tunnel>("POST", this.acct("/cfd_tunnel"), { name, config_src: "cloudflare" })).result;
  }

  async findTunnelByName(name: string): Promise<Tunnel | null> {
    const q = new URLSearchParams({ name, is_deleted: "false" });
    const list = (await this.call<Tunnel[]>("GET", this.acct(`/cfd_tunnel?${q}`))).result;
    return list.find((t) => t.name === name) ?? null;
  }

  async listTunnels(): Promise<Tunnel[]> {
    const out: Tunnel[] = [];
    for (let page = 1; ; page++) {
      const q = new URLSearchParams({ is_deleted: "false", per_page: "100", page: String(page) });
      const env = await this.call<Tunnel[]>("GET", this.acct(`/cfd_tunnel?${q}`));
      out.push(...env.result);
      if (env.result.length < 100 || (env.result_info && page >= env.result_info.total_pages)) return out;
    }
  }

  async putTunnelIngress(tunnelId: string, ingress: IngressRule[]): Promise<void> {
    await this.call("PUT", this.acct(`/cfd_tunnel/${tunnelId}/configurations`), { config: { ingress } });
  }

  async getTunnelToken(tunnelId: string): Promise<string> {
    return (await this.call<string>("GET", this.acct(`/cfd_tunnel/${tunnelId}/token`))).result;
  }

  // Replaces the tunnel secret, which invalidates the previous tunnel token.
  // [verify] PATCH with tunnel_secret on a remotely managed tunnel.
  async rotateTunnelSecret(tunnelId: string, secretB64: string): Promise<void> {
    await this.call("PATCH", this.acct(`/cfd_tunnel/${tunnelId}`), { tunnel_secret: secretB64 });
  }

  async deleteTunnel(tunnelId: string): Promise<void> {
    try {
      await this.call("DELETE", this.acct(`/cfd_tunnel/${tunnelId}/connections`));
    } catch (e) {
      if (!(e instanceof CfApiError) || e.retryable) throw e;
    }
    try {
      await this.call("DELETE", this.acct(`/cfd_tunnel/${tunnelId}`));
    } catch (e) {
      if (!(e instanceof CfApiError && e.notFound)) throw e;
    }
  }

  // ---- DNS ----

  async findDnsRecords(name: string): Promise<DnsRecord[]> {
    const q = new URLSearchParams({ name });
    return (await this.call<DnsRecord[]>("GET", this.zone(`/dns_records?${q}`))).result;
  }

  async listDnsRecords(): Promise<DnsRecord[]> {
    const out: DnsRecord[] = [];
    for (let page = 1; ; page++) {
      const q = new URLSearchParams({ type: "CNAME", per_page: "500", page: String(page) });
      const env = await this.call<DnsRecord[]>("GET", this.zone(`/dns_records?${q}`));
      out.push(...env.result);
      if (env.result.length < 500 || (env.result_info && page >= env.result_info.total_pages)) return out;
    }
  }

  async createCname(name: string, target: string, comment: string): Promise<DnsRecord> {
    return (
      await this.call<DnsRecord>("POST", this.zone("/dns_records"), {
        type: "CNAME",
        name,
        content: target,
        proxied: true,
        ttl: 1,
        comment,
      })
    ).result;
  }

  async deleteDnsRecord(id: string): Promise<void> {
    try {
      await this.call("DELETE", this.zone(`/dns_records/${id}`));
    } catch (e) {
      if (!(e instanceof CfApiError && e.notFound)) throw e;
    }
  }
}
