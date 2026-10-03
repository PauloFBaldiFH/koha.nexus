// Provisioning steps against the fake Cloudflare API, through the real
// CloudflareApi client.

import { beforeEach, describe, expect, it } from "vitest";
import { CloudflareApi } from "../src/cloudflare";
import * as steps from "../src/provision-steps";
import { createFakeCloudflare, FAKE_ACCOUNT, FAKE_TOKEN, FAKE_ZONE } from "./fake-cloudflare.mjs";

const LIB = "11111111-2222-4333-8444-555555555555";
const OTHER = "99999999-2222-4333-8444-555555555555";
const hostnames = { opac: "t-palotina-pr.example.org", staff: "t-palotina-pr-admin.example.org" };

let fake: any;
let cf: CloudflareApi;

beforeEach(() => {
  fake = createFakeCloudflare();
  cf = new CloudflareApi({ token: FAKE_TOKEN, accountId: FAKE_ACCOUNT, zoneId: FAKE_ZONE, fetcher: fake.fetcher, base: "https://cf.fake/client/v4" });
});

describe("provision", () => {
  it("creates a remotely managed tunnel, its ingress and two proxied CNAMEs", async () => {
    const r = await steps.provision(cf, { libraryId: LIB, hostnames });
    const s = fake.snapshot();
    expect(s.tunnels).toHaveLength(1);
    expect(s.tunnels[0].name).toBe(`kei-lib-${LIB}`);
    expect(s.tunnels[0].id).toBe(r.tunnelId);
    expect(s.tunnels[0].ingress).toEqual([
      { hostname: hostnames.opac, service: "http://localhost:80" },
      { hostname: hostnames.staff, service: "http://localhost:8080" },
      { service: "http_status:404" },
    ]);
    expect(s.dns_records).toHaveLength(2);
    for (const rec of s.dns_records) {
      expect(rec).toMatchObject({ type: "CNAME", content: `${r.tunnelId}.cfargotunnel.com`, proxied: true, comment: `kei:lib:${LIB}` });
    }
    expect(s.dns_records.map((x: { id: string }) => x.id).sort()).toEqual([r.opacRecordId, r.staffRecordId].sort());
    expect(fake.state.tunnels[0].config_src).toBe("cloudflare");
  });

  it("is idempotent: a second run adopts the tunnel and the records", async () => {
    const a = await steps.provision(cf, { libraryId: LIB, hostnames });
    const b = await steps.provision(cf, { libraryId: LIB, hostnames });
    expect(b).toEqual(a);
    expect(fake.snapshot().tunnels).toHaveLength(1);
    expect(fake.snapshot().dns_records).toHaveLength(2);
  });

  it("resumes after a failure halfway", async () => {
    fake.failNext("POST", /dns_records$/, 500, 1);
    await expect(steps.provision(cf, { libraryId: LIB, hostnames })).rejects.toThrow(/500/);
    expect(fake.snapshot().tunnels).toHaveLength(1);
    const r = await steps.provision(cf, { libraryId: LIB, hostnames });
    expect(fake.snapshot().tunnels).toHaveLength(1);
    expect(fake.snapshot().dns_records).toHaveLength(2);
    expect(r.tunnelId).toBe(fake.snapshot().tunnels[0].id);
  });

  it("adopts a tunnel whose create answer was lost", async () => {
    await cf.createTunnel(`kei-lib-${LIB}`);
    const id = await steps.ensureTunnel(cf, LIB);
    expect(id).toBe(fake.snapshot().tunnels[0].id);
  });

  it("never overwrites a record that is not ours, and says so permanently", async () => {
    fake.addForeignRecord(hostnames.opac);
    const err = await steps.provision(cf, { libraryId: LIB, hostnames }).catch((e) => e);
    expect(err).toBeInstanceOf(steps.PermanentStepError);
    expect(steps.isRetryable(err)).toBe(false);
    const recs = fake.snapshot().dns_records;
    expect(recs.find((r: { name: string }) => r.name === hostnames.opac)).toMatchObject({ type: "A", comment: null });
  });

  it("does not take over a record of another library", async () => {
    await steps.provision(cf, { libraryId: OTHER, hostnames });
    await expect(steps.provision(cf, { libraryId: LIB, hostnames })).rejects.toBeInstanceOf(steps.PermanentStepError);
  });

  it("replaces its own stale record pointing at an old tunnel", async () => {
    await cf.createCname(hostnames.opac, "old.cfargotunnel.com", `kei:lib:${LIB}`);
    const r = await steps.provision(cf, { libraryId: LIB, hostnames });
    const opac = fake.snapshot().dns_records.filter((x: { name: string }) => x.name === hostnames.opac);
    expect(opac).toHaveLength(1);
    expect(opac[0].content).toBe(`${r.tunnelId}.cfargotunnel.com`);
  });
});

describe("suspend, rotate", () => {
  it("suspension answers 503 and restore brings the ingress back", async () => {
    const r = await steps.provision(cf, { libraryId: LIB, hostnames });
    await steps.setSuspended(cf, r.tunnelId, hostnames, true);
    expect(fake.snapshot().tunnels[0].ingress).toEqual([{ service: "http_status:503" }]);
    expect(fake.snapshot().dns_records).toHaveLength(2);
    await steps.setSuspended(cf, r.tunnelId, hostnames, false);
    expect(fake.snapshot().tunnels[0].ingress).toHaveLength(3);
  });

  it("rotation sets a new 32-byte secret and changes the token", async () => {
    const r = await steps.provision(cf, { libraryId: LIB, hostnames });
    const before = await cf.getTunnelToken(r.tunnelId);
    await steps.rotate(cf, r.tunnelId);
    expect(fake.snapshot().rotations[r.tunnelId]).toBe(1);
    expect(await cf.getTunnelToken(r.tunnelId)).not.toBe(before);
  });
});

describe("deprovision and rollback", () => {
  it("removes the tunnel and only our records; repeating is harmless", async () => {
    const r = await steps.provision(cf, { libraryId: LIB, hostnames });
    const foreign = fake.addForeignRecord("www.example.org");
    await steps.deprovision(cf, { libraryId: LIB, hostnames, tunnelId: r.tunnelId });
    expect(fake.snapshot().tunnels).toEqual([]);
    expect(fake.snapshot().dns_records.map((x: { id: string }) => x.id)).toEqual([foreign.id]);
    await steps.deprovision(cf, { libraryId: LIB, hostnames, tunnelId: r.tunnelId });
  });

  it("rollback removes what a partial provisioning created", async () => {
    fake.failNext("POST", /dns_records$/, 500, 1);
    await steps.provision(cf, { libraryId: LIB, hostnames }).catch(() => undefined);
    await steps.rollback(cf, { libraryId: LIB, hostnames });
    expect(fake.snapshot().tunnels).toEqual([]);
    expect(fake.snapshot().dns_records).toEqual([]);
  });

  it("leaves a foreign record with the same name alone", async () => {
    fake.addForeignRecord(hostnames.staff);
    await steps.provision(cf, { libraryId: LIB, hostnames }).catch(() => undefined);
    await steps.rollback(cf, { libraryId: LIB, hostnames });
    expect(fake.snapshot().dns_records).toHaveLength(1);
    expect(fake.snapshot().dns_records[0].comment).toBeNull();
  });
});

describe("reconcile", () => {
  it("deletes tunnels and records of libraries that are gone, nothing else", async () => {
    await steps.provision(cf, { libraryId: LIB, hostnames });
    await steps.provision(cf, { libraryId: OTHER, hostnames: { opac: "t-x.example.org", staff: "t-x-admin.example.org" } });
    await cf.createTunnel("someone-elses-tunnel");
    const foreign = fake.addForeignRecord("mail.example.org", "mail.example.net", "CNAME");
    for (const t of fake.state.tunnels) t.created_at = "2020-01-01T00:00:00Z";

    const r = await steps.reconcile(cf, async (id) => id === LIB, Math.floor(Date.now() / 1000));
    expect(r.tunnelsDeleted).toHaveLength(1);
    expect(r.recordsDeleted).toHaveLength(2);
    const s = fake.snapshot();
    expect(s.tunnels.map((t: { name: string }) => t.name).sort()).toEqual([`kei-lib-${LIB}`, "someone-elses-tunnel"].sort());
    expect(s.dns_records.map((x: { id: string }) => x.id)).toContain(foreign.id);
    expect(s.dns_records.filter((x: { comment: string }) => x.comment === `kei:lib:${LIB}`)).toHaveLength(2);
  });

  it("leaves young tunnels alone", async () => {
    await steps.provision(cf, { libraryId: OTHER, hostnames });
    const r = await steps.reconcile(cf, async () => false, Math.floor(Date.now() / 1000));
    expect(r.tunnelsDeleted).toEqual([]);
  });
});

describe("helpers", () => {
  it("parses names and comments", () => {
    expect(steps.libraryIdFromTunnelName(`kei-lib-${LIB}`)).toBe(LIB);
    expect(steps.libraryIdFromTunnelName("kei-lib-")).toBeNull();
    expect(steps.libraryIdFromTunnelName("other")).toBeNull();
    expect(steps.libraryIdFromComment(`kei:lib:${LIB}`)).toBe(LIB);
    expect(steps.libraryIdFromComment(null)).toBeNull();
  });
});
