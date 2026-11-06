// Tainacan through the free address (Paulo, 2026-11-06): a library can
// publish Koha (catalogue and staff), Tainacan (the collection,
// <slug>-acervo) or both. Libraries made before keep publishing Koha only;
// changing what a library publishes never touches a record that is not ours.

import { beforeEach, describe, expect, it } from "vitest";
import { CloudflareApi } from "../src/cloudflare";
import {
  collectionFits,
  libraryHosts,
  maxSlugLength,
  parseServices,
  publishedHostnames,
  servicesText,
  validateSlug,
} from "../src/names";
import * as steps from "../src/provision-steps";
import { createFakeCloudflare, FAKE_ACCOUNT, FAKE_TOKEN, FAKE_ZONE } from "./fake-cloudflare.mjs";

const env = { NAME_PREFIX: "t-", STAFF_SUFFIX: "-admin", TAINACAN_SUFFIX: "-acervo", ZONE_NAME: "example.org" };
const LIB = "11111111-2222-4333-8444-555555555555";
const hosts = libraryHosts("palotina-pr", env);
const KOHA = { koha: true, tainacan: false };
const TAINACAN = { koha: false, tainacan: true };
const BOTH = { koha: true, tainacan: true };

let fake: any;
let cf: CloudflareApi;

beforeEach(() => {
  fake = createFakeCloudflare();
  cf = new CloudflareApi({ token: FAKE_TOKEN, accountId: FAKE_ACCOUNT, zoneId: FAKE_ZONE, fetcher: fake.fetcher, base: "https://cf.fake/client/v4" });
});

const names = () => fake.snapshot().dns_records.map((r: { name: string }) => r.name).sort();

describe("services and names", () => {
  it("reads the column; anything unknown is Koha only, as before", () => {
    expect(parseServices("koha")).toEqual(KOHA);
    expect(parseServices("tainacan")).toEqual(TAINACAN);
    expect(parseServices("koha,tainacan")).toEqual(BOTH);
    expect(parseServices(null)).toEqual(KOHA);
    expect(parseServices("")).toEqual(KOHA);
    expect(parseServices("wordpress")).toEqual(KOHA);
    expect(servicesText(BOTH)).toBe("koha,tainacan");
  });

  it("publishes only the names of the services", () => {
    expect(publishedHostnames("palotina-pr", env, KOHA)).toEqual({ opac: "t-palotina-pr.example.org", staff: "t-palotina-pr-admin.example.org" });
    expect(publishedHostnames("palotina-pr", env, TAINACAN)).toEqual({ collection: "t-palotina-pr-acervo.example.org" });
    expect(Object.keys(publishedHostnames("palotina-pr", env, BOTH)).sort()).toEqual(["collection", "opac", "staff"]);
  });

  it("new names leave room for the longer suffix and cannot end in it", () => {
    expect(maxSlugLength("", "-admin", "-acervo")).toBe(56);
    const opts = { prefix: "", staffSuffix: "-admin", collectionSuffix: "-acervo" };
    expect(validateSlug("museu-acervo", opts).ok).toBe(false);
    expect(validateSlug("a".repeat(57), opts).ok).toBe(false);
    expect(validateSlug("a".repeat(56), opts).ok).toBe(true);
    // An old 57-character name still fits Koha, not a collection address.
    expect(collectionFits("a".repeat(57), { ...env, NAME_PREFIX: "" })).toBe(false);
    expect(collectionFits("palotina-pr", env)).toBe(true);
  });
});

describe("provisioning by service", () => {
  it("a library made before Tainacan (no services) is provisioned as before", async () => {
    await steps.provision(cf, { libraryId: LIB, hostnames: hosts });
    expect(names()).toEqual(["t-palotina-pr-admin.example.org", "t-palotina-pr.example.org"]);
    expect(fake.snapshot().tunnels[0].ingress).toHaveLength(3);
  });

  it("Tainacan only: one name, Apache's port 80, no staff address", async () => {
    const r = await steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: TAINACAN });
    expect(names()).toEqual(["t-palotina-pr-acervo.example.org"]);
    expect(fake.snapshot().tunnels[0].ingress).toEqual([
      { hostname: "t-palotina-pr-acervo.example.org", service: "http://localhost:80" },
      { service: "http_status:404" },
    ]);
    expect(r.opacRecordId).toBeNull();
    expect(r.staffRecordId).toBeNull();
    expect(r.collectionRecordId).toBeTruthy();
  });

  it("adding and taking out Tainacan changes only the collection name", async () => {
    const a = await steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: KOHA });
    const b = await steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: BOTH });
    expect(b.tunnelId).toBe(a.tunnelId);
    expect(b.opacRecordId).toBe(a.opacRecordId);
    expect(b.staffRecordId).toBe(a.staffRecordId);
    expect(names()).toHaveLength(3);
    expect(fake.snapshot().tunnels[0].ingress.map((x: { hostname?: string }) => x.hostname)).toEqual([
      "t-palotina-pr.example.org",
      "t-palotina-pr-admin.example.org",
      "t-palotina-pr-acervo.example.org",
      undefined,
    ]);
    const c = await steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: KOHA });
    expect(c.collectionRecordId).toBeNull();
    expect(names()).toEqual(["t-palotina-pr-admin.example.org", "t-palotina-pr.example.org"]);
  });

  it("a collection name that belongs to someone else is never taken", async () => {
    await cf.createCname("t-palotina-pr-acervo.example.org", "elsewhere.example.net", "not ours");
    await expect(steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: BOTH })).rejects.toThrow(/not managed by the broker/);
    expect(fake.snapshot().dns_records.find((r: { name: string }) => r.name === "t-palotina-pr-acervo.example.org").content).toBe(
      "elsewhere.example.net",
    );
    // Taking Tainacan out does not delete the foreign record either.
    await steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: KOHA });
    expect(names()).toContain("t-palotina-pr-acervo.example.org");
  });

  it("suspension answers 503 for every name; removal takes the collection name too", async () => {
    const r = await steps.provision(cf, { libraryId: LIB, hostnames: hosts, services: BOTH });
    await steps.setSuspended(cf, r.tunnelId, hosts, true, BOTH);
    expect(fake.snapshot().tunnels[0].ingress).toEqual([{ service: "http_status:503" }]);
    await steps.setSuspended(cf, r.tunnelId, hosts, false, BOTH);
    expect(fake.snapshot().tunnels[0].ingress).toHaveLength(4);
    await steps.deprovision(cf, { libraryId: LIB, hostnames: hosts, tunnelId: r.tunnelId });
    expect(fake.snapshot().dns_records).toEqual([]);
    expect(fake.snapshot().tunnels).toEqual([]);
  });
});
