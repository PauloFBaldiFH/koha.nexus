// Provisioner Durable Object: one instance per library (idFromName(id)).
// blockConcurrencyWhile runs create, rotate, suspend and remove of one
// library strictly one at a time, so two jobs never race on its tunnel or
// records. State lives in D1; the object keeps nothing of its own.

import { DurableObject } from "cloudflare:workers";
import { cfApi, holdNameStatement } from "./db";
import type { Env, LibraryRow } from "./env";
import { now } from "./env";
import { hostnamesFor } from "./names";
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
        const r = await steps.provision(cfApi(this.env), { libraryId, hostnames: hostnamesFor(lib.slug, this.env) });
        await this.env.DB.prepare(
          `UPDATE libraries SET tunnel_id = ?, opac_record_id = ?, staff_record_id = ?, status = 'active', updated_at = ?
           WHERE id = ? AND status = 'provisioning'`,
        )
          .bind(r.tunnelId, r.opacRecordId, r.staffRecordId, now(), libraryId)
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
          hostnames: hostnamesFor(lib.slug, this.env),
          tunnelId: lib.tunnel_id,
        });
      } catch (e) {
        // The hourly reconciliation removes what is left: a failed library counts as gone.
        outcome = { ok: false, error: message(e), retryable: true };
      }
      await this.env.DB.prepare(
        `UPDATE libraries SET status = 'failed', tunnel_id = NULL, opac_record_id = NULL, staff_record_id = NULL, updated_at = ?
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
          hostnames: hostnamesFor(lib.slug, this.env),
          tunnelId: lib.tunnel_id,
        });
      } catch (e) {
        return { ok: false, error: message(e), retryable: steps.isRetryable(e) };
      }
      const t = now();
      await this.env.DB.batch([
        this.env.DB.prepare(
          `UPDATE libraries SET status = 'deleted', tunnel_id = NULL, opac_record_id = NULL, staff_record_id = NULL,
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
      await steps.setSuspended(cfApi(this.env), lib.tunnel_id, hostnamesFor(lib.slug, this.env), suspended);
      await this.env.DB.prepare("UPDATE libraries SET status = ?, updated_at = ? WHERE id = ? AND status = ?")
        .bind(suspended ? "suspended" : "active", now(), libraryId, from)
        .run();
    });
  }
}
