// Bindings, configuration and the D1 row shapes (migrations/*.sql).

import type { Provisioner } from "./provisioner";

export interface ProvisionMessage {
  jobId: string;
}

export interface Env {
  // Bindings (wrangler.toml)
  DB: D1Database;
  PROVISIONER: DurableObjectNamespace<Provisioner>;
  PROVISION_QUEUE: Queue<ProvisionMessage>;
  RL_DEVICE: RateLimit;
  RL_API: RateLimit;
  RL_STAFF: RateLimit;

  // Vars (wrangler.toml)
  CF_ACCOUNT_ID: string;
  CF_ZONE_ID: string;
  ZONE_NAME: string;
  BROKER_HOST: string;
  NAME_PREFIX: string;
  STAFF_SUFFIX: string;
  AUTO_APPROVE: string;
  MAX_LIBRARIES_PER_DAY: string;
  PBKDF2_ITERATIONS: string;
  /** Local tests only: points the Cloudflare client at a fake API. */
  CF_API_BASE?: string;

  // Secrets (`wrangler secret put`)
  CF_API_TOKEN: string;
  ADMIN_TOKEN: string;
  STAFF_SESSION_KEY: string;
}

/** Unix time in seconds. */
export function now(): number {
  return Math.floor(Date.now() / 1000);
}

export type EnrollmentStatus = "pending" | "approved" | "denied" | "consumed";
export type LibraryStatus = "provisioning" | "active" | "suspended" | "failed" | "deprovisioning" | "deleted";
export type JobKind = "provision" | "deprovision";
export type JobState = "queued" | "running" | "done" | "failed";

export interface EnrollmentRow {
  device_code_hash: string;
  user_code: string;
  status: EnrollmentStatus;
  institution_name: string;
  contact_email: string;
  cnpj: string | null;
  requested_slug: string | null;
  approved_slug: string | null;
  client_ip_hash: string | null;
  created_at: number;
  expires_at: number;
  decided_at: number | null;
  consumed_at: number | null;
}

export interface LibraryRow {
  id: string;
  slug: string;
  status: LibraryStatus;
  institution_name: string;
  contact_email: string;
  cnpj: string | null;
  public_key: string;
  recovery_hash: string | null;
  tunnel_id: string | null;
  opac_record_id: string | null;
  staff_record_id: string | null;
  staff_user: string | null;
  staff_pass_hash: string | null;
  staff_pass_salt: string | null;
  staff_pass_iter: number | null;
  staff_cred_version: number;
  staff_allow_cidrs: string | null;
  koha_version: string | null;
  installer_version: string | null;
  last_heartbeat: number | null;
  created_at: number;
  updated_at: number;
}

export interface JobRow {
  id: string;
  library_id: string;
  kind: JobKind;
  state: JobState;
  attempts: number;
  error: string | null;
  created_at: number;
  updated_at: number;
}

export interface NonceRow {
  library_id: string;
  nonce: string;
  expires_at: number;
}

export interface ReservedNameRow {
  slug: string;
  reason: string;
  until: number | null;
}

export interface AuditRow {
  id: number;
  at: number;
  actor: string;
  action: string;
  library_id: string | null;
  detail: string | null;
}
