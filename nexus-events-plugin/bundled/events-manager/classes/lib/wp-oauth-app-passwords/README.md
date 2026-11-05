# WP OAuth App Passwords

An OAuth 2.0 **Authorization Code + PKCE** server for WordPress that issues, refreshes and revokes native **Application Passwords**. It gives AI / MCP clients (Claude, ChatGPT, Cursor, …) a proper browser-based consent flow and a **persistent, refreshable** credential — without a custom token table and without the constant re-authentication that plagues short-lived-token OAuth servers.

It is a **library, distributed bundled inside other plugins** (Events Manager, bbPress API, …). It can also run standalone as a plugin.

## Why this design

The access token handed to a client is simply `base64("login:application_password")` — the exact wire form Application Passwords already use. That means:

- **No custom token storage.** Access tokens are validated by WordPress core on every request. No table, no transient-expiry surprises, no object-cache flush wiping sessions.
- **Visible & revocable.** Each connection shows up in **Users → Profile → Application Passwords** with the name the user chose ("Claude", "Cursor", …), with last-used / IP tracking, revocable from there.
- **Persistent.** Refresh **rotates** the Application Password — deletes the old one and recreates it with the **same display name**. The user sees one stable entry that keeps working while the secret cycles. No 1-hour TTL, no reconnect loop.
- **Refresh tokens** map back to the rotating credential via one low-cardinality usermeta key per user (`{user_id}~{secret}` token shape → O(1) lookup, no table).

## Endpoints

Served under the REST namespace `oauth/v1` (filterable), plus root well-known paths:

| Path | Purpose |
|---|---|
| `GET/POST /wp-json/oauth/v1/authorize` | Authorization Code endpoint + branded consent screen |
| `POST /wp-json/oauth/v1/token` | `authorization_code` + `refresh_token` grants |
| `POST /wp-json/oauth/v1/revoke` | RFC 7009 revocation |
| `POST /wp-json/oauth/v1/register` | RFC 7591 dynamic client registration (public clients) |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 server metadata |
| `GET /.well-known/oauth-protected-resource` | RFC 9728 resource metadata |

## Bundling it in a plugin

1. Copy this directory into your plugin, e.g. `includes/lib/wp-oauth-app-passwords/`.
2. Include the loader from your main plugin file (before your own classes load):

   ```php
   require_once __DIR__ . '/includes/lib/wp-oauth-app-passwords/loader.php';
   ```

3. Register a scope when the library is ready:

   ```php
   add_action( 'pixelite_oauth_app_passwords_ready', function ( $server ) {
       // $server is the Server class name (string) — call statically.
       $server::register_scope( 'bbpress:mcp', array(
           'label'       => __( 'bbPress forums', 'your-textdomain' ),
           'description' => __( 'Read and reply to forum topics on your behalf.', 'your-textdomain' ),
           // REST route prefixes a credential granted this scope may call. Omit to grant the account's full REST access.
           'routes'      => array( '/bbpress/v1', '/mcp/bbpress' ),
       ) );
   } );
   ```

## Scope enforcement

An Application Password has no scope of its own: it carries every capability of its user. So when a scope is registered with `routes`, the library limits the credentials it mints for that scope to those REST route prefixes (plus its own `oauth/v1` endpoints, so the client can still refresh and revoke). Any other route returns `403 insufficient_scope`. A requested scope the server does not know is reduced to the default scope rather than becoming an unrestricted grant.

A scope registered without `routes` keeps the historical behaviour: full account access. Two filters tune this:

```php
add_filter( 'pixelite_oauth_enforce_scopes', '__return_false' );          // disable enforcement site-wide
add_filter( 'pixelite_oauth_scope_routes', fn( $routes, $scope ) => $routes, 10, 2 ); // adjust the allowlist per granted scope
```

The consent screen and the authorize error page are sent with `X-Frame-Options: DENY` and `frame-ancestors 'none'`. Dynamic registration is limited per IP address (`pixelite_oauth_registration_rate_limit`, default 10 per hour, 0 to disable) and can never evict an admin-created client from the registry.

The **version arbitrator** in `loader.php` ensures that if several plugins each bundle a copy, only the **newest** version's classes load — the rest stand down. So multiple hosts can ship it safely.

## Updating bundled copies

This repo is the canonical source. After changing the library (and bumping the version in `loader.php`), propagate it into every plugin that bundles it:

```bash
bin/sync.sh                    # rsync the current source into every discovered bundle
bin/sync.sh --dry-run          # preview without writing
bin/sync.sh --prefer main      # when a repo has the bundle in several worktrees
bin/sync.sh --root ~/some/tree
```

`bin/sync.sh` auto-discovers bundles — any `*/wp-oauth-app-passwords/` directory containing `loader.php` and `src/Server.php` under the parent tree — and prints a before/after version table. Dev-only files (`bin/`, the standalone `wp-oauth-app-passwords.php`, `.git`, `node_modules`) are never copied into a consumer; they only ever receive `loader.php`, `bootstrap.php`, `src/`, `templates/`, `languages/`, `README.md` and `index.php`.

**Worktree de-duplication.** A gitree-style repo can have the bundle checked out in several worktrees at once (e.g. a feature branch *and* `main`). The script groups bundles by their underlying git repository and syncs only **one** worktree per repo — preferring a feature branch over `main`/`master`, or whatever you pass to `--prefer` — so the same change is never written to two branches at once. Skipped worktrees are reported, and ephemeral agent worktrees (`.claude/`) are ignored.

Because of the version arbitrator above, consumers don't have to update in lockstep — the newest bundled copy on a site wins — but `sync.sh` keeps them current in one command. Review and commit each consumer repo afterwards.

## Drop-in admin screen

The library ships the **AI / MCP setup** UI so every host renders an identical screen — WordPress version check, MCP Adapter install/activate, the server URL, authentication status, and self-diagnosing subdirectory discovery (RFC 8414). Drop it into any settings page with one line:

```php
\Pixelite\OAuth_App_Passwords\Admin::render( array(
    'server_path' => 'mcp/mcp-adapter-default-server', // MCP Adapter's default server
    'docs_url'    => 'https://example.com/docs/ai/',    // optional "documentation" link
    'intro'       => '',                                // optional; overrides the default blurb
    'heading'     => __( 'AI / MCP setup', 'your-textdomain' ), // '' to hide the <h2>
) );
```

There is nothing else to wire up: `Server::boot()` registers the install / activate POST handlers and the admin notice automatically in `wp-admin`. The card / pill styling matches the Events Manager AI/MCP meta box, so consuming plugins are visually consistent out of the box.

Two filters tailor it per host:

```php
// Rewrite the advertised MCP URL (e.g. through a tunnel during local dev).
add_filter( 'pixelite_oauth_mcp_public_url', fn( $url, $path ) => $url, 10, 2 );

// Override where the MCP Adapter ZIP is fetched from.
add_filter( 'pixelite_oauth_mcp_adapter_zip', fn( $zip ) => $zip );
```

## Lifetimes (filterable)

```php
add_filter( 'pixelite_oauth_access_token_ttl',  fn() => 8  * HOUR_IN_SECONDS ); // default 8 hours
add_filter( 'pixelite_oauth_refresh_token_ttl', fn() => 30 * DAY_IN_SECONDS );  // default 30 days
```

Note: the access token's *effective* lifetime is "until the next refresh rotates the Application Password". `expires_in` is advisory — it tells well-behaved clients when to refresh (and thus rotate). A hard session cap is a planned later stage.

## Namespace

Code is under `\Pixelite\OAuth_App_Passwords` but **never references the namespace as a hardcoded string** — internal wiring uses `self::` / `static::` / `::class` / `__NAMESPACE__`. To rename or remove the namespace, edit only the `namespace` declarations and `use` statements.

## Requirements

- WordPress 6.0+ (Application Passwords require 5.6+ and HTTPS)
- PHP 7.4+

## License

GPL-2.0-or-later.
