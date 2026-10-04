# Koha subdomain broker (Scenario B)

A Cloudflare Worker that gives each library its own address under one central domain, for example `palotina-pr.koha.nexus` (staff interface: `palotina-pr-admin.koha.nexus`). The broker itself answers at `broker.koha.nexus`. It creates a Cloudflare Tunnel for each library and publishes it, without the Cloudflare API token ever leaving Cloudflare.

**Status:** baseline. The Worker builds, and its unit tests and a local end-to-end test pass against a fake Cloudflare API. It has **not yet run against a real Cloudflare account**. The installer's **Free address** menu (Cloudflare Tunnel Manager) uses it; `tests/free_address.bats` runs that menu against this Worker in local workerd. Sign-up is instant and unreviewed (`AUTO_APPROVE = "true"`): every request gets the first free valid name at once, and there is no daily cap (`MAX_LIBRARIES_PER_DAY = "0"`). Set `AUTO_APPROVE = "false"` to approve each request by hand again.

Design documents in the project folder: `analysis/scenario-b-broker-blueprint.md` and `analysis/cloudflare-subdomain-automation.md`.

## What it does

```
Koha panel (installer)                 Worker (this folder)                         Cloudflare API
 device/start ───────────────────────► request approved at once under the first free name
                                       (AUTO_APPROVE=false: pending until an admin approves;
                                        the panel shows the /join link and polls)
 enroll + Ed25519 public key ────────► library row + queued job
                                       Queue ─► Provisioner Durable Object (one per library)
                                                  create tunnel (remotely managed)  ─────► POST cfd_tunnel
                                                  set ingress :80 / :8080           ─────► PUT  configurations
                                                  proxied CNAMEs (never overwrite)  ─────► POST dns_records
 signed GET /v1/tunnel-token ◄────────  token fetched live, never stored          ◄───── GET  token
 cloudflared runs with that token
```

- **Master token:** it lives only in a Worker secret. A library server receives only its own tunnel token, which can run that one tunnel and nothing else. The ingress is managed remotely, so a library cannot add hostnames to its tunnel.
- **Atomic, resumable provisioning:** there is one Durable Object per library. Its `blockConcurrencyWhile` serializes create, rotate, suspend and remove. Steps are idempotent: a retry adopts the tunnel and records that already exist. A DNS name that exists and belongs to someone else is **never overwritten**. After 6 failed attempts, what was created is rolled back.
- **Reconciliation (hourly cron):** deletes tunnels named `kei-lib-<id>` and CNAMEs commented `kei:lib:<id>` whose library is gone (tunnels younger than one hour are left alone). Records without that comment are never touched, so your zone's other DNS entries are safe. It also prunes expired nonces and old requests and re-sends jobs whose queue message was lost. Tunnels are account-wide: do not run a second broker (for example a test one) in the same Cloudflare account, or each would remove the other's tunnels. A test deployment uses `NAME_PREFIX = "t-"` (names like `t-palotina-pr`).
- **Suspension:** switches the tunnel's ingress to `503`. DNS is unchanged, so restoring is instant.
- **Names:** flat names only, because free SSL covers one level (`palotina-pr` and `palotina-pr-admin`). Technical names (`www`, `join`, `broker`, `mail`, ...) are reserved. Automatic approval takes the requested name, else the institution name, else a numbered variant (`palotina-pr-2`), else `biblioteca-<random>`. The phishing-word blocklist (with look-alike spellings such as `l0g1n`) only applies to manual approval (`AUTO_APPROVE = "false"`). A released name is held for 180 days.
- **Rate limits:** 3 new requests per minute per IP address, 30 API calls per minute per IP or library, 20 staff-login attempts per minute.
- **Optional circuit breaker:** `MAX_LIBRARIES_PER_DAY` above 0 pauses enrollment after that many new libraries in 24 hours. `0` (the default) turns it off.
- **After the fact:** the admin API can still suspend, restore or remove any library.

## Files

| Path | Purpose |
|---|---|
| `wrangler.toml` | Bindings: D1, Durable Object (SQLite), Queue (+ dead-letter), 3 rate limiters, cron, routes, vars |
| `package.json`, `package-lock.json`, `tsconfig.json` | Dependencies (wrangler, Miniflare, vitest, TypeScript) and scripts |
| `migrations/0001_init.sql` | D1 schema |
| `src/index.ts` | Router, queue consumer, cron |
| `src/api.ts` | Enrollment (device flow) and signed library endpoints |
| `src/admin.ts` | Approve/deny, suspend/restore, remove |
| `src/provisioner.ts` | Durable Object that runs the steps one library at a time |
| `src/provision-steps.ts` | Idempotent tunnel/DNS steps and reconciliation (unit-tested) |
| `src/cloudflare.ts` | Minimal Cloudflare API client |
| `src/signature.ts` | Ed25519 request verification |
| `src/staff-auth.ts` | Edge gate for staff hostnames |
| `src/names.ts`, `src/netaddr.ts` | Name policy, CIDR matching |
| `src/env.ts`, `src/http.ts`, `src/db.ts`, `src/crypto.ts` | Bindings and row types, HTTP helpers, shared queries, WebCrypto helpers |
| `scripts/kei-sign.sh` | Reference signer (openssl), the same steps the installer runs |
| `test/*.test.ts` | Unit tests (vitest) |
| `test/fake-cloudflare.mjs` | In-memory fake of the Cloudflare API used by all tests |
| `test/e2e/harness.mjs`, `test/e2e/run.mjs`, `test/e2e/serve.mjs` | Local workerd (Miniflare) runner; end-to-end checks; server for `tests/free_address.bats` |

## What you need (and what not to send anyone)

Nothing needs to be sent to Claude or pasted into chat. You set every value yourself.

| Value | Secret? | Where it goes |
|---|---|---|
| Account ID of the account that holds `koha.nexus` | no | `wrangler.toml` → `CF_ACCOUNT_ID` |
| Zone ID of `koha.nexus` | no | `wrangler.toml` → `CF_ZONE_ID` |
| D1 database ID | no | `wrangler.toml` → `database_id` (printed by `wrangler d1 create`) |
| API token for the broker | **yes** | `wrangler secret put CF_API_TOKEN` |
| Admin token | **yes** | `wrangler secret put ADMIN_TOKEN` |
| Staff session key | **yes** | `wrangler secret put STAFF_SESSION_KEY` |

**Deploy the Worker in the same account as the zone.** The API token could manage a zone in another account, but the staff-gate route (`*-admin.koha.nexus/*`) and the `broker.koha.nexus` custom domain can only attach to zones in the Worker's own account.

**API token.** Create it in the zone's account under *Manage Account → Account API Tokens* (or *My Profile → API Tokens*), as a custom token:
- Account → **Cloudflare Tunnel → Edit**
- Zone → **DNS → Edit**, *Specific zone*: `koha.nexus`
- nothing else (deployment uses your own `wrangler login`, not this token)
- optional: an expiry date, rotated before it expires

## Setup

```bash
cd broker
npm ci
npx wrangler login                                  # opens the browser; use the zone's account
npx wrangler d1 create kei-broker                   # copy database_id into wrangler.toml
npx wrangler queues create kei-provision
npx wrangler queues create kei-provision-dlq
# edit wrangler.toml: CF_ACCOUNT_ID, CF_ZONE_ID, database_id
npm run db:migrate                                  # applies migrations/ to the remote D1
npm run deploy                                      # creates the Worker, the custom domain and the route
npx wrangler secret put CF_API_TOKEN                # paste the token at the prompt, never in chat
openssl rand -base64 36 | npx wrangler secret put ADMIN_TOKEN
openssl rand -base64 36 | npx wrangler secret put STAFF_SESSION_KEY
```

Deploy before putting the secrets: `wrangler secret put` on a Worker that does not exist yet stops to ask whether to create it, and a piped value cannot answer that. Until the secrets are set, provisioning jobs retry, `/admin` answers 503 and the staff gate answers 503 once a library sets a password. Keep the admin token somewhere safe (a password manager): print it once with `openssl rand -base64 36`, store it, and pipe the same value to `wrangler secret put`.

Workers plan **[verify current limits]**: Durable Objects with SQLite storage, Queues, rate-limiting bindings, Cron Triggers and D1 are all offered on the Workers Free plan, within daily quotas (queue operations and Durable Object requests per day). The Free plan's CPU limit is 10 ms per request, so `PBKDF2_ITERATIONS` in `wrangler.toml` is 20,000 (about 3 ms per hash; 100,000, the most workerd accepts, takes about 15 ms and would fail staff logins on the Free plan). On the Workers Paid plan (US$5/month, 30 s CPU) it can be raised to 100,000; each password keeps the count it was saved with. The gate only hashes on login; the session cookie covers later requests.

### Trying it by hand

```bash
B=https://broker.koha.nexus
A="Authorization: Bearer <your admin token>"
./scripts/kei-sign.sh keygen /tmp/lib.key
curl -s $B/v1/device/start -H 'Content-Type: application/json' \
  -d '{"institution_name":"Biblioteca Teste","contact_email":"voce@exemplo.org","requested_name":"palotina-pr"}'
# only with AUTO_APPROVE = "false":
curl -s $B/admin/enrollments -H "$A"
curl -s -X POST $B/admin/enrollments/<USER-CODE>/approve -H "$A" -H 'Content-Type: application/json' -d '{}'
curl -s $B/v1/enroll -H 'Content-Type: application/json' \
  -d "{\"device_code\":\"<device_code>\",\"public_key\":\"$(./scripts/kei-sign.sh pubkey /tmp/lib.key)\"}"
./scripts/kei-sign.sh curl /tmp/lib.key <library_id> GET $B/v1/jobs/<job_id>
./scripts/kei-sign.sh curl /tmp/lib.key <library_id> GET $B/v1/tunnel-token
# on a Koha server:  sudo cloudflared service install <tunnel token>
```

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /v1/device/start` | rate limit per IP | `{institution_name, contact_email, cnpj?, requested_name?}` → `device_code`, `user_code`, `verification_uri` |
| `POST /v1/device/poll` | device code | `pending` / `approved` / `denied` / `expired` |
| `POST /v1/enroll` | device code (single use) | binds the Ed25519 public key, queues provisioning; returns the `recovery_code` once |
| `POST /v1/recover` | recovery code | `{address, recovery_code, public_key}`: binds a new server key to the address and returns a new code (see below) |
| `POST /v1/recovery-code` | signed | new recovery code; the previous one stops working |
| `GET /join?c=CODE` | none | status page behind the QR code (verification form comes later) |
| `GET /v1/jobs/{id}`, `GET /v1/library` | signed | status |
| `GET /v1/tunnel-token` | signed | current tunnel token |
| `POST /v1/rotate` | signed | new tunnel secret; fetch the token again |
| `POST /v1/heartbeat` | signed | Koha and installer versions |
| `PUT` / `DELETE /v1/staff-credentials` | signed | turn remote staff access on (user, password, optional CIDRs) or off |
| `DELETE /v1/library` | signed | remove tunnel and records |
| `/admin/...` | `Bearer ADMIN_TOKEN` | `GET /admin/enrollments?status=`, `POST /admin/enrollments/{code}/approve` (`{slug?, force?}`) or `/deny`, `GET /admin/libraries`, `POST /admin/libraries/{id}/suspend` or `/restore`, `DELETE /admin/libraries/{id}` |

## Recovery codes

Enrollment returns a recovery code (`XXXX-XXXX-XXXX-XXXX`, about 77 bits) once; the broker stores only its sha256. The panel shows it, saves it in `/etc/koha-easy-install/broker-recovery.txt` (root only) and asks the librarian to write it down. On a reinstalled or new server, "Recover my address" sends the address, the code and the new server's public key to `POST /v1/recover`:

- **Live address:** the new key replaces the old one, the tunnel secret is rotated (an old server still running drops off), and a new code replaces the used one.
- **Given-up address, name still on hold (180 days):** the address is provisioned again under the same name for the new key.

A wrong address or code gets the same 403, and both the IP and the name are rate limited. Libraries enrolled before recovery codes existed get one from the panel (`POST /v1/recovery-code`). After updating the Worker, apply the new migration with `npm run db:migrate`.

## Signatures (Ed25519)

At enrollment the installer creates a key with `openssl genpkey -algorithm ed25519` (file mode 0600) and sends the raw 32-byte public key in base64. Each later request carries:

```
X-KEI-Library:   <library id>
X-KEI-Timestamp: <unix seconds>
X-KEI-Nonce:     <16-64 chars [A-Za-z0-9_-]>
X-KEI-Signature: base64 Ed25519 signature of
                 "KEI-SIG-v1\n<METHOD>\n<path?query>\n<timestamp>\n<nonce>\n<sha256 hex of body>"
```

The Worker (`src/signature.ts`) checks the header format first, then that the clock skew is at most 5 minutes, then the stored key for a live library, then the signature. Only after all of that does it store the nonce: a second use of the same nonce is rejected as a replay, and an unsigned caller can't use up nonces. A tampered body, path or method fails verification. A removed library's key stops working immediately. `scripts/kei-sign.sh` is the reference implementation, and the tests use it, so the openssl side and the Worker side are checked against each other.

## Staff interface security

The staff hostname (`<name>-admin.<zone>`) stays reachable from anywhere, behind these layers:

1. **Closed by default.** Until the library sets a remote-access password from the panel (a signed `PUT /v1/staff-credentials`), the gate answers 403.
2. **Worker gate on the route `*-admin.<zone>/*`:** HTTP Basic Auth checked against a PBKDF2-SHA256 hash. After a successful login it sets a signed `__Host-` session cookie (12 h, HttpOnly, Secure). Changing the password invalidates all sessions. The gate strips its own password and cookie before forwarding, so Koha never sees them. Koha's own login still applies afterwards.
3. **Optional IP allowlist per library** (up to 20 CIDRs), for example the city hall's network.
4. **Rate limit:** at most 20 attempts per minute per IP and library without a valid session.

Extra WAF rules you can add in the dashboard (zone → Security → WAF). They are manual, not managed by the token:
- **Country filter (custom rule):** `(http.host contains "-admin.") and (ip.src.country ne "BR")` → *Block*. This is simple and effective for Brazilian municipal libraries.
- **Rate limiting rule** on `http.request.uri.path eq "/cgi-bin/koha/mainpage.pl" and http.request.method eq "POST"` for staff hosts. Free plans allow a limited number of these rules **[verify]**.
- Hidden or "obscured" paths are not recommended: Koha's staff paths are fixed and well known, so hiding them adds no real protection.
- Cloudflare Access (email one-time PIN) remains the strongest option if its free seats are enough. They are shared across the whole account **[verify current limit]**.

The OPAC hostnames don't run this Worker (no cost, no latency). Protect them with the zone-wide path-allowlist rule from the blueprint.

## Development

```bash
npm run typecheck     # tsc
npm test              # unit tests (vitest): names, CIDRs, staff gate, signatures via openssl (kei-sign.sh and the installer's signer), provisioning steps
npm run test:e2e      # bundles the Worker and runs the full flow in local workerd (Miniflare) with a fake Cloudflare API
```

`CF_API_BASE` (used only by local tests) points the client at a fake API. Leave it unset in production.

## Installer side

The panel's **Free address** item (menu 6, Cloudflare Tunnel Manager) is the client. It asks for the library name, contact e-mail and wanted name, and connects right away when the broker approves at once (the default). With manual approval it shows the request page as a QR code, browser or link and continues on its own once the request is approved. It creates the server key (`/etc/koha-easy-install/broker.key`, 0600), keeps the tunnel token only in `/etc/cloudflared/koha-broker.env` (0600) and runs `cloudflared tunnel run` as a service. It sends a daily signed heartbeat (`/etc/cron.d/koha_broker`) and has menu items for remote staff access, reconnect, token renewal, sharing the catalog link (QR code on screen, printable PNG, browser, link) and giving the address up. A server uses either a free address or its own domain, never both.

The installer still defaults to the old test broker, `https://koha-broker.bibliotecamunicipalpalotina.org`; change its `KEI_BROKER_URL` default to `https://broker.koha.nexus` once this deployment is live. `KEI_BROKER_URL` overrides it meanwhile.

To run the installer tests: `npm install` here, then `sudo KEI_TEST_SANDBOX=1 tests/run.sh tests/free_address.bats` from the repository root. `npm run test:e2e` runs the Worker-only end-to-end checks.

## Next steps

1. Monitoring: Koha fingerprint check, reputation feeds, and automatic suspension.
