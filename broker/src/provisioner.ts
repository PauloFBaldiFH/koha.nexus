// Provisioner Durable Object: one instance per library (idFromName(id)).
// blockConcurrencyWhile runs create, rotate, suspend and remove of one
// library strictly one at a time, so two jobs never race on its tunnel or
// records. State lives in D1; the object keeps nothing of its own.

import { DurableObject } from "cloudflare:workers";
import { cfApi, holdNameStatement } from "./db";
import type { Env, LibraryRow } from "./env";
import { now } from "./env";
import { libraryHosts, parseServices } from "./names";
import * as steps from "./provision-steps";

export type StepOutcome = { ok: true; skipped?: boolean } | { ok: false; error: string; retryable: boolean };

function message(e: unknown): string {
  return (e instanceof Error ? e.message : String(e)).slice(0, 500);
}

export class Provisioner extends DurableObject<Env> {
  // An exception escaping blockConcurrencyWhile resets the object, so the
  // error is carried out of the block and thrown afterwards.
  private async serial<T>(fn: () => Promise<T>): Promise<T> {
    const r = await this.ctx.blockConcurrencyWhile(async () => {
      try {
        return { ok: true as const, value: await fn() };
      } catch (error) {
        return { ok: false as const, error };
      }
    });
    if (!r.ok) throw r.error;
    return r.value;
  }

  private async library(id: string): Promise<LibraryRow | null> {
    return this.env.DB.prepare("SELECT * FROM libraries WHERE id = ?").bind(id).first<LibraryRow>();
  }

  /** Creates or adopts the tunnel, its ingress and both CNAMEs; marks the library active. */
  async provision(libraryId: string): Promise<StepOutcome> {
    return this.serial(async () => {
      const lib = await this.library(libraryId);
      if (!lib || lib.status !== "provisioning") return { ok: true, skipped: true };
      try {
        const r = await steps.provision(cfApi(this.env), {
          libraryId,
          hostnames: libraryHosts(lib.slug, this.env),
          services: parseServices(lib.services),
        });
        await this.env.DB.prepare(
          `UPDATE libraries SET tunnel_id = ?, opac_record_id = ?, staff_record_id = ?, collection_record_id = ?,
             status = 'active', updated_at = ?
           WHERE id = ? AND status = 'provisioning'`,
        )
          .bind(r.tunnelId, r.opacRecordId, r.staffRecordId, r.collectionRecordId, now(), libraryId)
          .run();
        return { ok: true };
      } catch (e) {
        return { ok: false, error: message(e), retryable: steps.isRetryable(e) };
      }
    });
  }

  /** After a provisioning gave up: removes what was created and marks the library failed. */
  async rollback(libraryId: string): Promise<StepOutcome> {
    return this.serial(async () => {
      const lib = await this.library(libraryId);
      if (!lib) return { ok: true, skipped: true };
      let outcome: StepOutcome = { ok: true };
      try {
        await steps.rollback(cfApi(this.env), {
          libraryId,
          hostnames: libraryHosts(lib.slug, this.env),
          tunnelId: lib.tunnel_id,
        });
      } catch (e) {
        // The hourly reconciliation removes what is left: a failed library counts as gone.
        outcome = { ok: false, error: message(e), retryable: true };
      }
      await this.env.DB.prepare(
        `UPDATE libraries SET status = 'failed', tunnel_id = NULL, opac_record_id = NULL, staff_record_id = NULL,
           collection_record_id = NULL, updated_at = ?
         WHERE id = ? AND status = 'provisioning'`,
      )
        .bind(now(), libraryId)
        .run();
      return outcome;
    });
  }

  /** Removes the tunnel and our records; the library row stays as history and its name is held. */
  async deprovision(libraryId: string): Promise<StepOutcome> {
    return this.serial(async () => {
      const lib = await this.library(libraryId);
      if (!lib || lib.status !== "deprovisioning") return { ok: true, skipped: true };
      try {
        await steps.deprovision(cfApi(this.env), {
          libraryId,
          hostnames: libraryHosts(lib.slug, this.env),
          tunnelId: lib.tunnel_id,
        });
      } catch (e) {
        return { ok: false, error: message(e), retryable: steps.isRetryable(e) };
      }
      const t = now();
      await this.env.DB.batch([
        this.env.DB.prepare(
          `UPDATE libraries SET status = 'deleted', tunnel_id = NULL, opac_record_id = NULL, staff_record_id = NULL,
             collection_record_id = NULL,
             staff_user = NULL, staff_pass_hash = NULL, staff_pass_salt = NULL, staff_pass_iter = NULL,
             staff_cred_version = staff_cred_version + 1, updated_at = ?
           WHERE id = ? AND status = 'deprovisioning'`,
        ).bind(t, libraryId),
        holdNameStatement(this.env, lib.slug),
        this.env.DB.prepare("DELETE FROM nonces WHERE library_id = ?").bind(libraryId),
      ]);
      return { ok: true };
    });
  }

  /** New tunnel secret; the library fetches its token again. Throws when not possible. */
  async rotate(libraryId: string): Promise<void> {
    return this.serial(async () => {
      const lib = await this.library(libraryId);
      if (!lib || !lib.tunnel_id || (lib.status !== "active" && lib.status !== "suspended")) {
        throw new Error(`library is ${lib?.status ?? "unknown"}`);
      }
      await steps.rotate(cfApi(this.env), lib.tunnel_id);
    });
  }

  /** Suspend: ingress answers 503, DNS unchanged. Restore: normal ingress again. */
  async setSuspended(libraryId: string, suspended: boolean): Promise<void> {
    return this.serial(async () => {
      const lib = await this.library(libraryId);
      const from = suspended ? "active" : "suspended";
      if (!lib || lib.status !== from || !lib.tunnel_id) {
        throw new Error(`library is ${lib?.status ?? "unknown"}, expected ${from}`);
      }
      await steps.setSuspended(cfApi(this.env), lib.tunnel_id, libraryHosts(lib.slug, this.env), suspended, parseServices(lib.services));
      await this.env.DB.prepare("UPDATE libraries SET status = ?, updated_at = ? WHERE id = ? AND status = ?")
        .bind(suspended ? "suspended" : "active", now(), libraryId, from)
        .run();
    });
  }

  /** Remove exactly DSpace, reading the latest services inside the per-library lock. */
  async detachRepository(libraryId:string):Promise<{services:string; job_id?:string}> {
    return this.serial(async()=>{
      const lib=await this.library(libraryId);
      if(lib?.status==="deprovisioning" && parseServices(lib.services).dspace && !parseServices(lib.services).koha && !parseServices(lib.services).tainacan){
        const job=await this.env.DB.prepare("SELECT id,state FROM jobs WHERE library_id=? AND kind='deprovision' ORDER BY created_at DESC LIMIT 1").bind(libraryId).first<{id:string;state:string}>();
        if(job){
          if(job.state==="queued")await this.env.PROVISION_QUEUE.send({jobId:job.id});
          return {services:"",job_id:job.id};
        }
      }
      if(!lib || !lib.tunnel_id || !["active","suspended"].includes(lib.status))throw new Error("Library is not active");
      const current=parseServices(lib.services);
      if(!current.dspace)return {services:lib.services};
      const next={...current,dspace:false};
      if(!next.koha && !next.tainacan){
        // No other service can attach between this decision and the state change.
        const job=crypto.randomUUID(), t=now();
        await this.env.DB.batch([
          this.env.DB.prepare("UPDATE libraries SET status='deprovisioning',updated_at=? WHERE id=?").bind(t,libraryId),
          this.env.DB.prepare("INSERT INTO jobs(id,library_id,kind,state,created_at,updated_at) VALUES(?,?,'deprovision','queued',?,?)").bind(job,libraryId,t,t),
        ]);
        await this.env.PROVISION_QUEUE.send({jobId:job});
        return {services:"",job_id:job};
      }
      const text=[...(next.koha?["koha"]:[]),...(next.tainacan?["tainacan"]:[])].join(",");
      try {
        await steps.provision(cfApi(this.env),{libraryId,hostnames:libraryHosts(lib.slug,this.env),services:next,suspended:lib.status==="suspended"});
      } catch(e) {
        await steps.provision(cfApi(this.env),{libraryId,hostnames:libraryHosts(lib.slug,this.env),services:current,suspended:lib.status==="suspended"}).catch(()=>undefined);
        throw e;
      }
      await this.env.DB.prepare("UPDATE libraries SET services=?,updated_at=? WHERE id=?").bind(text,now(),libraryId).run();
      return {services:text};
    });
  }

  /**
   * What a library publishes changed (Tainacan added or taken out): the
   * ingress and the records follow the new services first, and only then the
   * row says so. On a failure the old services are applied again, so the
   * address never points somewhere the row does not say.
   */
  async setServices(libraryId: string, services: string, expected?:string): Promise<{ collectionRecordId: string | null }> {
    return this.serial(async () => {
      const lib = await this.library(libraryId);
      if (!lib || !lib.tunnel_id || (lib.status !== "active" && lib.status !== "suspended")) {
        throw new Error(`library is ${lib?.status ?? "unknown"}`);
      }
      if (expected!==undefined && lib.services!==expected) throw new Error("Services changed concurrently; refresh and retry.");
      const apply = async (text: string) =>
        steps.provision(cfApi(this.env), {
          libraryId,
          hostnames: libraryHosts(lib.slug, this.env),
          services: parseServices(text),
          suspended: lib.status === "suspended",
        });
      let r: steps.ProvisionResult;
      try {
        r = await apply(services);
      } catch (e) {
        await apply(lib.services).catch(() => undefined);
        throw e;
      }
      await this.env.DB.prepare(
        `UPDATE libraries SET services = ?, tunnel_id = ?, opac_record_id = ?, staff_record_id = ?, collection_record_id = ?,
           updated_at = ? WHERE id = ?`,
      )
        .bind(services, r.tunnelId, r.opacRecordId, r.staffRecordId, r.collectionRecordId, now(), libraryId)
        .run();
      return { collectionRecordId: r.collectionRecordId };
    });
  }
}
