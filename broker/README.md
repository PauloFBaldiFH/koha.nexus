# Koha subdomain broker (Scenario B)

A Cloudflare Worker that gives each library its own address under one central domain, for example `palotina-pr.koha.page`. It creates a Cloudflare Tunnel for each library and publishes it, without the Cloudflare API token ever leaving Cloudflare.

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
- **Reconciliation (hourly cron):** deletes tunnels named `kei-lib-<id>` and CNAMEs commented `kei:lib:<id>` whose library is gone. Records without that comment are never touched, so your zone's other DNS entries are safe. The test zone also uses the `t-` name prefix.
- **Suspension:** switches the tunnel's ingress to `503`. DNS is unchanged, so restoring is instant.
- **Names:** flat names only, because free SSL covers one level (`t-palotina-pr` and `t-palotina-pr-admin`). Technical names (`www`, `join`, `broker`, `mail`, ...) are reserved. Automatic approval takes the requested name, else the institution name, else a numbered variant (`palotina-pr-2`), else `biblioteca-<random>`. The phishing-word blocklist (with look-alike spellings such as `l0g1n`) only applies to manual approval (`AUTO_APPROVE = "false"`). A released name is held for 180 days.
- **Rate limits:** 3 new requests per minute per IP address, 30 API calls per minute per IP or library, 20 staff-login attempts per minute.
- **Optional circuit breaker:** `MAX_LIBRARIES_PER_DAY` above 0 pauses enrollment after that many new libraries in 24 hours. `0` (the default) turns it off.
- **After the fact:** the admin API can still suspend, restore or remove any library.

## Files

| Path | Purpose |
|---|---|
| `wrangler.toml` | Bindings: D1, Durable Object, Queue (+ dead-letter), 3 rate limiters, cron, routes |
| `migrations/0001_init.sql` | D1 schema |
| `src/index.ts` | Router, queue consumer, cron |
| `src/api.ts` | Enrollment (device flow) and signed library endpoints |
| `src/admin.ts` | Approve/deny, suspend/restore, remove |
| `src/provisioner.ts` | Durable Object that runs the steps one library at a time |
| `src/provision-steps.ts` | Idempotent tunnel/DNS steps (unit-tested) |
| `src/cloudflare.ts` | Minimal Cloudflare API client |
| `src/signature.ts` | Ed25519 request verification |
| `src/staff-auth.ts` | Edge gate for staff hostnames |
| `src/names.ts`, `src/netaddr.ts` | Name policy, CIDR matching |
| `scripts/kei-sign.sh` | Reference signer (openssl), the same steps the installer will run |
| `test/*.test.ts`, `test/e2e/run.mjs` | Unit tests; end-to-end run in local workerd with a fake Cloudflare API |

## What you need (and what not to send anyone)

Nothing needs to be sent to Claude or pasted into chat. You set every value yourself.

| Value | Secret? | Where it goes |
|---|---|---|
| Account ID of the account that holds `bibliotecamunicipalpalotina.org` | no | `wrangler.toml` → `CF_ACCOUNT_ID` |
| Zone ID of `bibliotecamunicipalpalotina.org` | no | `wrangler.toml` → `CF_ZONE_ID` |
| D1 database ID | no | `wrangler.toml` → `database_id` (printed by `wrangler d1 create`) |
| API token for the broker | **yes** | `wrangler secret put CF_API_TOKEN` |
| Admin token | **yes** | `wrangler secret put ADMIN_TOKEN` |
| Staff session key | **yes** | `wrangler secret put STAFF_SESSION_KEY` |

**Deploy the Worker in the same account as the zone.** The API token could manage a zone in another account, but the staff-gate route and the `koha-broker.` custom domain can only attach to zones in the Worker's own account.

**API token.** Create it in the zone's account under *Manage Account → Account API Tokens* (or *My Profile → API Tokens*), as a custom token:
- Account → **Cloudflare Tunnel → Edit**
- Zone → **DNS → Edit**, *Specific zone*: `bibliotecamunicipalpalotina.org`
- nothing else (deployment uses your own `wrangler login`, not this token)
- optional: an expiry date, rotated before it expires

## Setup (test zone)

```bash
cd broker
npm install
npx wrangler login                                  # opens the browser; use the zone's account
npx wrangler d1 create kei-broker                   # copy database_id into wrangler.toml
npx wrangler queues create kei-provision
npx wrangler queues create kei-provision-dlq
# edit wrangler.toml: CF_ACCOUNT_ID, CF_ZONE_ID, database_id
npx wrangler secret put CF_API_TOKEN
openssl rand -base64 36 | npx wrangler secret put ADMIN_TOKEN
openssl rand -base64 36 | npx wrangler secret put STAFF_SESSION_KEY
npm run db:migrate
npm run deploy
```

Queues and higher CPU limits may require the Workers Paid plan (US$5/month) **[verify current free-plan limits]**. PBKDF2 at 100,000 iterations uses more CPU than the free plan allows per request **[verify]**. The gate hashes only on login (the session cookie covers later requests), but lower `PBKDF2_ITERATIONS` if the free plan rejects it.

### Trying it by hand

```bash
B=https://koha-broker.bibliotecamunicipalpalotina.org
A="Authorization: Bearer <your admin token>"
./scripts/kei-sign.sh keygen /tmp/lib.key
curl -s $B/v1/device/start -H 'Content-Type: application/json' \
  -d '{"institution_name":"Biblioteca Teste","contact_email":"voce@exemplo.org","requested_name":"palotina-pr"}'
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
| `POST /v1/enroll` | device code (single use) | binds the Ed25519 public key, queues provisioning |
| `GET /join?c=CODE` | none | status page behind the QR code (verification form comes later) |
| `GET /v1/jobs/{id}`, `GET /v1/library` | signed | status |
| `GET /v1/tunnel-token` | signed | current tunnel token |
| `POST /v1/rotate` | signed | new tunnel secret; fetch the token again |
| `POST /v1/heartbeat` | signed | Koha and installer versions |
| `PUT` / `DELETE /v1/staff-credentials` | signed | turn remote staff access on (user, password, optional CIDRs) or off |
| `DELETE /v1/library` | signed | remove tunnel and records |
| `/admin/...` | `Bearer ADMIN_TOKEN` | list/approve/deny requests, list/suspend/restore/remove libraries |

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
npm test              # unit tests (vitest): names, CIDRs, staff gate helpers, signatures via openssl, provisioning steps
npm run test:e2e      # bundles the Worker and runs the full flow in local workerd (Miniflare) with a fake Cloudflare API
```

`CF_API_BASE` (used only by local tests) points the client at a fake API. Leave it unset in production.

## Installer side

The panel's **Free address** item (menu 6, Cloudflare Tunnel Manager) is the client. It asks for the library name, contact e-mail and wanted name, and connects right away when the broker approves at once (the default). With manual approval it shows the request page as a QR code, browser or link and continues on its own once the request is approved. It creates the server key (`/etc/koha-easy-install/broker.key`, 0600), keeps the tunnel token only in `/etc/cloudflared/koha-broker.env` (0600) and runs `cloudflared tunnel run` as a service. It sends a daily signed heartbeat (`/etc/cron.d/koha_broker`) and has menu items for remote staff access, reconnect, token renewal, sharing the catalog link (QR code on screen, printable PNG, browser, link) and giving the address up. A server uses either a free address or its own domain, never both.

The installer points at `https://koha-broker.bibliotecamunicipalpalotina.org` (the test zone). `KEI_BROKER_URL` overrides it.

To run the installer tests: `npm install` here, then `sudo KEI_TEST_SANDBOX=1 tests/run.sh tests/free_address.bats` from the repository root. `npm run test:e2e` runs the Worker-only end-to-end checks.

## Next steps

1. Monitoring: Koha fingerprint check, reputation feeds, and automatic suspension.
