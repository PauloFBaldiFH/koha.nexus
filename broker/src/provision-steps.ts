// Idempotent tunnel and DNS steps for one library. Every step can be run
// again after a partial failure: it adopts the tunnel and the records that
// already exist. A DNS name that exists and is not ours (no `kei:lib:<id>`
// comment) is never overwritten or deleted.

import type { CloudflareApi, DnsRecord, IngressRule } from "./cloudflare";
import { randomBytes, toBase64 } from "./crypto";
import type { Hostnames, Services } from "./names";

/** A library's names: Koha's two and Tainacan's (published or not, by services). */
export interface LibraryHosts extends Hostnames {
  collection: string;
}

const KOHA_ONLY: Services = { koha: true, tainacan: false };

/** The subset of the Cloudflare client the steps use (a fake in the tests). */
export type CfClient = Pick<
  CloudflareApi,
  | "createTunnel"
  | "findTunnelByName"
  | "listTunnels"
  | "putTunnelIngress"
  | "getTunnelToken"
  | "rotateTunnelSecret"
  | "deleteTunnel"
  | "findDnsRecords"
  | "listDnsRecords"
  | "createCname"
  | "deleteDnsRecord"
>;

export const TUNNEL_PREFIX = "kei-lib-";
export const COMMENT_PREFIX = "kei:lib:";
/** Attempts before a provisioning job gives up and rolls back. */
export const MAX_ATTEMPTS = 6;

export const tunnelName = (libraryId: string): string => `${TUNNEL_PREFIX}${libraryId}`;
export const recordComment = (libraryId: string): string => `${COMMENT_PREFIX}${libraryId}`;
export const tunnelTarget = (tunnelId: string): string => `${tunnelId}.cfargotunnel.com`;

export function libraryIdFromTunnelName(name: string): string | null {
  return name.startsWith(TUNNEL_PREFIX) ? name.slice(TUNNEL_PREFIX.length) || null : null;
}

export function libraryIdFromComment(comment: string | null | undefined): string | null {
  return comment && comment.startsWith(COMMENT_PREFIX) ? comment.slice(COMMENT_PREFIX.length) || null : null;
}

/** An error that retrying will not fix (for example a DNS name owned by someone else). */
export class PermanentStepError extends Error {
  readonly permanent = true;
  constructor(message: string) {
    super(message);
    this.name = "PermanentStepError";
  }
}

export function isRetryable(e: unknown): boolean {
  // Everything else (API errors, network errors) may pass: the job retries
  // with backoff and rolls back after MAX_ATTEMPTS.
  return !(e instanceof PermanentStepError);
}

/**
 * Ingress of an active library: OPAC to Koha's port 80, staff to 8080 (the
 * staff hostname is still behind the Worker gate, closed until the library
 * sets a password), the collection to Apache's port 80, where Tainacan's own
 * site answers by its name. Only the services the library publishes. The
 * catch-all answers 404. A suspended library answers 503 for everything.
 */
export function ingressFor(h: Hostnames | LibraryHosts, suspended = false, services: Services = KOHA_ONLY): IngressRule[] {
  if (suspended) return [{ service: "http_status:503" }];
  const rules: IngressRule[] = [];
  if (services.koha) {
    rules.push({ hostname: h.opac, service: "http://localhost:80" }, { hostname: h.staff, service: "http://localhost:8080" });
  }
  if (services.tainacan && "collection" in h) rules.push({ hostname: h.collection, service: "http://localhost:80" });
  rules.push({ service: "http_status:404" });
  return rules;
}

export interface ProvisionInput {
  libraryId: string;
  hostnames: Hostnames | LibraryHosts;
  suspended?: boolean;
  /** Unset: Koha only (libraries made before Tainacan could be published). */
  services?: Services;
}

export interface ProvisionResult {
  tunnelId: string;
  opacRecordId: string | null;
  staffRecordId: string | null;
  collectionRecordId: string | null;
}

export async function ensureTunnel(cf: CfClient, libraryId: string): Promise<string> {
  const name = tunnelName(libraryId);
  const existing = await cf.findTunnelByName(name);
  if (existing) return existing.id;
  try {
    return (await cf.createTunnel(name)).id;
  } catch (e) {
    // Created by an earlier attempt that lost its answer: adopt it.
    const again = await cf.findTunnelByName(name);
    if (again) return again.id;
    throw e;
  }
}

function isOurs(r: DnsRecord, libraryId: string): boolean {
  return libraryIdFromComment(r.comment) === libraryId;
}

/** A proxied CNAME name -> tunnel, created or adopted; never takes over a foreign record. */
export async function ensureCname(cf: CfClient, libraryId: string, name: string, tunnelId: string): Promise<string> {
  const target = tunnelTarget(tunnelId);
  const records = await cf.findDnsRecords(name);
  const foreign = records.filter((r) => !isOurs(r, libraryId));
  if (foreign.length) {
    throw new PermanentStepError(`DNS name ${name} already exists and is not managed by the broker`);
  }
  let keep: DnsRecord | undefined;
  for (const r of records) {
    if (!keep && r.type === "CNAME" && r.content === target && r.proxied !== false) keep = r;
    else await cf.deleteDnsRecord(r.id); // ours but stale (old tunnel, duplicate)
  }
  if (keep) return keep.id;
  return (await cf.createCname(name, target, recordComment(libraryId))).id;
}

/** Removes our records for `name` (a service the library no longer publishes). */
async function dropOurs(cf: CfClient, libraryId: string, name: string): Promise<void> {
  for (const r of await cf.findDnsRecords(name)) {
    if (isOurs(r, libraryId)) await cf.deleteDnsRecord(r.id);
  }
}

/**
 * Tunnel, ingress and one proxied CNAME per published name. Also the way to
 * change what a library publishes: the names it no longer publishes lose
 * our records (never someone else's).
 */
export async function provision(cf: CfClient, input: ProvisionInput): Promise<ProvisionResult> {
  const services = input.services ?? KOHA_ONLY;
  const h = input.hostnames;
  const tunnelId = await ensureTunnel(cf, input.libraryId);
  await cf.putTunnelIngress(tunnelId, ingressFor(h, input.suspended, services));
  const out: ProvisionResult = { tunnelId, opacRecordId: null, staffRecordId: null, collectionRecordId: null };
  if (services.koha) {
    out.opacRecordId = await ensureCname(cf, input.libraryId, h.opac, tunnelId);
    out.staffRecordId = await ensureCname(cf, input.libraryId, h.staff, tunnelId);
  } else {
    await dropOurs(cf, input.libraryId, h.opac);
    await dropOurs(cf, input.libraryId, h.staff);
  }
  if ("collection" in h) {
    if (services.tainacan) out.collectionRecordId = await ensureCname(cf, input.libraryId, h.collection, tunnelId);
    else await dropOurs(cf, input.libraryId, h.collection);
  }
  return out;
}

export async function setSuspended(
  cf: CfClient,
  tunnelId: string,
  hostnames: Hostnames | LibraryHosts,
  suspended: boolean,
  services: Services = KOHA_ONLY,
): Promise<void> {
  await cf.putTunnelIngress(tunnelId, ingressFor(hostnames, suspended, services));
}

/** New tunnel secret: the previous tunnel token stops working. */
export async function rotate(cf: CfClient, tunnelId: string): Promise<void> {
  await cf.rotateTunnelSecret(tunnelId, toBase64(randomBytes(32)));
}

export interface DeprovisionInput {
  libraryId: string;
  hostnames: Hostnames | LibraryHosts;
  tunnelId?: string | null;
}

/** Removes our records for every name of the library and its tunnel. Safe to repeat. */
export async function deprovision(cf: CfClient, input: DeprovisionInput): Promise<void> {
  const h = input.hostnames;
  for (const name of [h.opac, h.staff, ...("collection" in h ? [h.collection] : [])]) {
    await dropOurs(cf, input.libraryId, name);
  }
  const ids = new Set<string>();
  if (input.tunnelId) ids.add(input.tunnelId);
  const byName = await cf.findTunnelByName(tunnelName(input.libraryId));
  if (byName) ids.add(byName.id);
  for (const id of ids) await cf.deleteTunnel(id);
}

/** Undo of a provisioning that gave up: the same as deprovisioning. */
export const rollback = deprovision;

export interface ReconcileResult {
  tunnelsDeleted: string[];
  recordsDeleted: string[];
}

/**
 * Deletes tunnels named kei-lib-<id> and CNAMEs commented kei:lib:<id>
 * whose library is gone. Anything else is never touched. Tunnels younger
 * than `minAgeSeconds` are left alone (a library being created right now).
 */
export async function reconcile(
  cf: CfClient,
  isLive: (libraryId: string) => Promise<boolean>,
  nowSeconds: number,
  minAgeSeconds = 3600,
): Promise<ReconcileResult> {
  const out: ReconcileResult = { tunnelsDeleted: [], recordsDeleted: [] };
  const cache = new Map<string, boolean>();
  const live = async (id: string) => {
    if (!cache.has(id)) cache.set(id, await isLive(id));
    return cache.get(id)!;
  };
  for (const t of await cf.listTunnels()) {
    const id = libraryIdFromTunnelName(t.name);
    if (!id || t.deleted_at) continue;
    const created = Date.parse(t.created_at) / 1000;
    if (Number.isFinite(created) && nowSeconds - created < minAgeSeconds) continue;
    if (await live(id)) continue;
    await cf.deleteTunnel(t.id);
    out.tunnelsDeleted.push(t.id);
  }
  for (const r of await cf.listDnsRecords()) {
    const id = libraryIdFromComment(r.comment);
    if (!id || (await live(id))) continue;
    await cf.deleteDnsRecord(r.id);
    out.recordsDeleted.push(r.id);
  }
  return out;
}
