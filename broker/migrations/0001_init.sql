-- koha.nexus broker: initial schema (Cloudflare D1 / SQLite).
-- Times are unix seconds.

CREATE TABLE enrollments (
  device_code_hash TEXT PRIMARY KEY,           -- sha256 of the device code; the code itself is never stored
  user_code        TEXT NOT NULL UNIQUE,       -- short code shown to people (XXXX-XXXX)
  status           TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'denied', 'consumed')),
  institution_name TEXT NOT NULL,
  contact_email    TEXT NOT NULL,
  cnpj             TEXT,
  requested_slug   TEXT,
  approved_slug    TEXT,
  client_ip_hash   TEXT,
  created_at       INTEGER NOT NULL,
  expires_at       INTEGER NOT NULL,
  decided_at       INTEGER,
  consumed_at      INTEGER
);
CREATE INDEX enrollments_status ON enrollments (status, created_at);
CREATE INDEX enrollments_approved_slug ON enrollments (approved_slug) WHERE status = 'approved';

CREATE TABLE libraries (
  id                 TEXT PRIMARY KEY,         -- UUID; also names the tunnel (kei-lib-<id>)
  slug               TEXT NOT NULL,
  status             TEXT NOT NULL CHECK (status IN ('provisioning', 'active', 'suspended', 'failed', 'deprovisioning', 'deleted')),
  institution_name   TEXT NOT NULL,
  contact_email      TEXT NOT NULL,
  cnpj               TEXT,
  public_key         TEXT NOT NULL,            -- base64 raw Ed25519 public key of the install
  tunnel_id          TEXT,
  opac_record_id     TEXT,
  staff_record_id    TEXT,
  staff_user         TEXT,                     -- remote staff access (edge Basic Auth)
  staff_pass_hash    TEXT,                     -- PBKDF2-SHA256, base64
  staff_pass_salt    TEXT,
  staff_pass_iter    INTEGER,
  staff_cred_version INTEGER NOT NULL DEFAULT 0,  -- bumps invalidate staff sessions
  staff_allow_cidrs  TEXT,                     -- JSON array of CIDRs, NULL = any IP
  koha_version       TEXT,
  installer_version  TEXT,
  last_heartbeat     INTEGER,
  created_at         INTEGER NOT NULL,
  updated_at         INTEGER NOT NULL
);
-- A name belongs to at most one live library; deleted and failed rows keep history.
CREATE UNIQUE INDEX libraries_live_slug ON libraries (slug) WHERE status NOT IN ('deleted', 'failed');
CREATE INDEX libraries_created ON libraries (created_at);

CREATE TABLE jobs (
  id         TEXT PRIMARY KEY,
  library_id TEXT NOT NULL REFERENCES libraries (id),
  kind       TEXT NOT NULL CHECK (kind IN ('provision', 'deprovision')),
  state      TEXT NOT NULL CHECK (state IN ('queued', 'running', 'done', 'failed')),
  attempts   INTEGER NOT NULL DEFAULT 0,
  error      TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX jobs_library ON jobs (library_id);

-- Replay protection for signed requests.
CREATE TABLE nonces (
  library_id TEXT NOT NULL,
  nonce      TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  PRIMARY KEY (library_id, nonce)
);

-- Names on hold after a release, or reserved by hand (until NULL = forever).
CREATE TABLE reserved_names (
  slug   TEXT PRIMARY KEY,
  reason TEXT NOT NULL,
  until  INTEGER
);

CREATE TABLE audit_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  at         INTEGER NOT NULL,
  actor      TEXT NOT NULL,                    -- admin | public | system | library:<id>
  action     TEXT NOT NULL,
  library_id TEXT,
  detail     TEXT                              -- JSON, never secrets
);
CREATE INDEX audit_log_at ON audit_log (at);
