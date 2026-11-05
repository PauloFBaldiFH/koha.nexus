<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Orchestrator and public facade for the OAuth App Passwords library.
 *
 * One instance serves every consuming plugin on the site (the version arbitrator guarantees a single loaded copy). Consuming plugins register a human-readable scope label via Server::register_scope() so the consent screen and discovery metadata describe what is being granted.
 *
 * All internal wiring uses ::class / static::class so the namespace can be renamed or removed without touching call sites.
 */
class Server {

	/** @var array<string,array> scope => {label, description} */
	private static $scopes = array();

	private static $booted = false;

	public static function boot(): void {
		if ( self::$booted ) {
			return;
		}
		self::$booted = true;

		// Make WordPress tunnel-aware when a request actually arrives via MCP_OAUTH_TUNNEL, so the browser OAuth flow (authorize -> wp-login -> consent -> switch account) stays on the tunnel domain instead of bouncing to the local home URL.
		self::maybe_boot_tunnel();

		I18n::boot();
		App_Passwords::boot();
		Scope_Guard::boot();

		// The shared AI/MCP setup screen registers its install/activate handlers here so consuming plugins only need to call Admin::render() where they want the UI shown — no extra wiring on the host side.
		if ( is_admin() ) {
			Admin::boot();
		}

		add_action( 'rest_api_init', array( static::class, 'register_routes' ) );
		add_action( 'init', array( static::class, 'register_rewrites' ) );
		add_action( 'parse_request', array( static::class, 'maybe_serve_well_known' ), 0 );
		// Front-end authorize endpoint (not REST — see Authorize for why).
		add_action( 'template_redirect', array( static::class, 'maybe_serve_authorize' ) );

		// Advertise this OAuth server on REST 401s so MCP/AI clients can discover how to authenticate. The WordPress MCP Adapter returns a bare WP REST 401 with no WWW-Authenticate header; without the RFC 9728 challenge a client cannot find the authorization server — and on a subdir install it would otherwise probe the wrong (host-root) well-known location.
		add_filter( 'rest_post_dispatch', array( static::class, 'add_auth_challenge' ), 10, 3 );

		// Don't let WordPress canonical-redirect our front-end OAuth endpoints. Behind a tunnel/proxy that rewrites the Host header, redirect_canonical rebuilds the URL from the proxied host and 301s the browser off the tunnel to the local host, breaking the authorize flow before our handler runs. See skip_canonical_redirect().
		add_filter( 'redirect_canonical', array( static::class, 'skip_canonical_redirect' ) );

		// Let consuming plugins register scopes / hook in now that we're ready.
		do_action( 'pixelite_oauth_app_passwords_ready', static::class );
	}

	/**
	 * Developer-tunnel support.
	 *
	 * When MCP_OAUTH_TUNNEL is set AND the current request actually arrived through it (Host header == the tunnel host), make WordPress generate tunnel URLs for the whole request — home, site, login, logout and admin URLs — so the browser OAuth flow stays on the tunnel domain. Without this, wp_login_url() / wp_logout_url() return the local home URL and the flow bounces off the tunnel the moment it needs to log in or switch accounts.
	 *
	 * Local requests (Host == the real home host) are left untouched, so the admin keeps working normally — the admin screen still advertises the tunnel URL via Support::public_url(), which keys off the constant rather than the request.
	 */
	private static function maybe_boot_tunnel(): void {
		if ( ! ( defined( 'MCP_OAUTH_TUNNEL' ) && MCP_OAUTH_TUNNEL ) ) {
			return;
		}
		$tunnel      = untrailingslashit( (string) MCP_OAUTH_TUNNEL );
		$tunnel_host = (string) wp_parse_url( $tunnel, PHP_URL_HOST );
		if ( '' === $tunnel_host ) {
			return;
		}

		// Always let safe redirects reach the tunnel host (wp-login logout/login redirects use wp_safe_redirect, which rejects unknown hosts).
		add_filter( 'allowed_redirect_hosts', static function ( $hosts ) use ( $tunnel_host ) {
			$hosts[] = $tunnel_host;
			return $hosts;
		} );

		// A tunnel request is identified by the tunnel host appearing as the Host header, OR — when the tunnel rewrites Host to the local vhost so the server routes correctly (e.g. ngrok --host-header) — as the X-Forwarded-Host the proxy injects.
		$req_host = isset( $_SERVER['HTTP_HOST'] ) ? (string) wp_unslash( $_SERVER['HTTP_HOST'] ) : '';
		$fwd_host = '';
		if ( ! empty( $_SERVER['HTTP_X_FORWARDED_HOST'] ) ) {
			$parts    = explode( ',', (string) wp_unslash( $_SERVER['HTTP_X_FORWARDED_HOST'] ) );
			$fwd_host = trim( $parts[0] );
		}
		if ( $req_host !== $tunnel_host && $fwd_host !== $tunnel_host ) {
			return; // Not a tunnel request — leave local URLs alone.
		}

		// Local origins to rewrite. Read straight from the WP_HOME / WP_SITEURL constants and the options (NOT home_url()/site_url(), which we are about to filter — that would recurse). Include all so we catch the origin whether WordPress builds URLs from a constant or the database.
		$origins = array_values( array_unique( array_filter( array(
			untrailingslashit( defined( 'WP_HOME' ) ? (string) WP_HOME : '' ),
			untrailingslashit( defined( 'WP_SITEURL' ) ? (string) WP_SITEURL : '' ),
			untrailingslashit( (string) get_option( 'home' ) ),
			untrailingslashit( (string) get_option( 'siteurl' ) ),
		) ) ) );
		if ( empty( $origins ) ) {
			return;
		}
		$to_tunnel = static function ( $url ) use ( $origins, $tunnel ) {
			if ( is_string( $url ) ) {
				foreach ( $origins as $origin ) {
					if ( '' !== $origin && 0 === strpos( $url, $origin ) ) {
						return $tunnel . substr( $url, strlen( $origin ) );
					}
				}
			}
			return $url;
		};
		foreach ( array( 'home_url', 'site_url', 'login_url', 'logout_url', 'admin_url' ) as $hook ) {
			add_filter( $hook, $to_tunnel, 99 );
		}
	}

	/**
	 * Prevent WordPress's canonical redirect (trailing-slash / host normalisation) from firing on our front-end OAuth endpoints. Behind a tunnel or reverse proxy that rewrites the Host header, redirect_canonical rebuilds the URL from the proxied host and 301s the browser off the tunnel to the local host — breaking the authorize flow before our handler runs. REST routes (token, revoke, register, the MCP server) are already exempt from canonical redirects.
	 *
	 * @param string|false $redirect_url
	 * @return string|false
	 */
	public static function skip_canonical_redirect( $redirect_url ) {
		if ( get_query_var( 'pixelite_oauth_authorize' ) || get_query_var( 'pixelite_oauth_wk' ) ) {
			return false;
		}
		return $redirect_url;
	}

	/* ---------------------------------------------------------------------
	 * Public facade for consuming plugins
	 * ------------------------------------------------------------------ */

	/**
	 * Register a scope shown on the consent screen and advertised in metadata.
	 *
	 * `routes` is the list of REST route prefixes (e.g. `/events-manager/v1`, `/mcp/events-manager`) a credential granted this scope may call; Scope_Guard rejects every other route with 403. Omit it and the scope grants the account's full REST access, which is what Application Passwords do on their own.
	 *
	 * @param string $scope       e.g. "bbpress:mcp"
	 * @param array  $args        { label, description, routes[] }
	 */
	public static function register_scope( string $scope, array $args = array() ): void {
		$routes = array();
		foreach ( (array) ( $args['routes'] ?? array() ) as $route ) {
			$route = trim( (string) $route, "/ \t\n\r" );
			if ( '' !== $route ) {
				$routes[] = '/' . $route;
			}
		}
		self::$scopes[ $scope ] = array(
			'label'       => (string) ( $args['label'] ?? $scope ),
			'description' => (string) ( $args['description'] ?? '' ),
			'routes'      => array_values( array_unique( $routes ) ),
		);
	}

	/**
	 * The registered scope names a requested scope string resolves to. Unknown names are ignored; when nothing known remains, the default scope's names are used instead. Never returns a name that is not registered.
	 *
	 * @return array<int,string>
	 */
	private static function resolve_scope_names( string $scope ): array {
		$known = array_keys( self::scopes() );
		$names = array_filter( (array) preg_split( '/\s+/', trim( $scope ) ) );
		$kept  = array_values( array_intersect( $names, $known ) );
		if ( $kept ) {
			return $kept;
		}
		$default = array_filter( (array) preg_split( '/\s+/', trim( self::default_scope() ) ) );
		return array_values( array_intersect( $default, $known ) );
	}

	/**
	 * Reduce a requested scope string to scopes this server knows. A client asking for `wp:api` on a site whose only registered scope is `events-manager:mcp` gets the Events Manager scope (and its route limits), not an unrestricted token.
	 */
	public static function normalize_scope( string $scope ): string {
		$names = self::resolve_scope_names( $scope );
		return $names ? implode( ' ', $names ) : self::default_scope();
	}

	/**
	 * REST route prefixes a credential granted this scope string may call, or null when it is unrestricted, i.e. when any granted scope was registered without routes. The library's own endpoints are always included so a scoped client can still refresh and revoke.
	 *
	 * @return array<int,string>|null
	 */
	public static function routes_for_scope( string $scope ): ?array {
		$known  = self::scopes();
		$routes = array();
		foreach ( self::resolve_scope_names( $scope ) as $name ) {
			if ( empty( $known[ $name ]['routes'] ) ) {
				return null;
			}
			$routes = array_merge( $routes, $known[ $name ]['routes'] );
		}
		if ( empty( $routes ) ) {
			return null;
		}
		$routes[] = '/' . trim( Support::rest_namespace(), '/' );
		/**
		 * Filter the REST route prefixes a scoped credential may call. Return an empty array to lift the restriction.
		 *
		 * @param array<int,string> $routes
		 * @param string            $scope  The granted scope string.
		 */
		$routes = (array) apply_filters( 'pixelite_oauth_scope_routes', array_values( array_unique( $routes ) ), $scope );
		return $routes ? array_values( $routes ) : null;
	}

	/** @return array<string,array> */
	public static function scopes(): array {
		if ( empty( self::$scopes ) ) {
			// Always advertise at least the default generic scope when no plugin has registered one. Returned rather than stored: if this ran before a host's register_scope() (an early metadata or default_scope() call), the unrestricted generic scope would otherwise stick as the first-registered default and every later grant could resolve to it.
			return array(
				self::default_scope() => array(
					'label'       => __( 'Site API access', 'wp-oauth-app-passwords' ),
					'description' => __( 'Read and write access to this site through the REST API, acting as your account.', 'wp-oauth-app-passwords' ),
					'routes'      => array(),
				),
			);
		}
		return self::$scopes;
	}

	/**
	 * The scope handed to a dynamic-registration client that does not specify one of its own. Prefers the first plugin-registered scope when any are available — so a freshly registered MCP client picks up something meaningful (e.g. "events-manager:mcp") instead of the library's generic "wp:api" fallback. Without that, well-behaved clients record "wp:api" at registration time and keep requesting it on every later authorize, even though the server's metadata advertises real scopes.
	 *
	 * Sites can override via the `pixelite_oauth_default_scope` filter, e.g. to force a specific space-separated scope string.
	 */
	public static function default_scope(): string {
		$fallback = ! empty( self::$scopes ) ? (string) array_key_first( self::$scopes ) : 'wp:api';
		return (string) apply_filters( 'pixelite_oauth_default_scope', $fallback );
	}

	public static function access_token_ttl(): int {
		return (int) apply_filters( 'pixelite_oauth_access_token_ttl', 8 * HOUR_IN_SECONDS );
	}

	public static function refresh_token_ttl(): int {
		return (int) apply_filters( 'pixelite_oauth_refresh_token_ttl', 30 * DAY_IN_SECONDS );
	}

	public static function availability(): array {
		return Support::availability();
	}

	public static function mcp_metadata_url(): string {
		return Support::well_known_url( 'authorization_server' );
	}

	/**
	 * True when WordPress lives in a subdirectory (e.g. /support) rather than at the domain root. This is the single biggest cause of "the AI client won't connect" failures: RFC 8414 clients look for the authorization-server metadata at the DOMAIN ROOT, which does not reach a subdirectory install.
	 */
	public static function is_subdirectory_install(): bool {
		$path = untrailingslashit( (string) wp_parse_url( home_url(), PHP_URL_PATH ) );
		return '' !== $path;
	}

	/**
	 * Everything an admin screen needs to explain and fix subdirectory discovery, including a live self-test of the domain-root metadata URL a strict client will actually request.
	 *
	 * @return array
	 */
	public static function discovery_status(): array {
		$scheme = (string) wp_parse_url( home_url(), PHP_URL_SCHEME );
		$host   = (string) wp_parse_url( home_url(), PHP_URL_HOST );
		$port   = wp_parse_url( home_url(), PHP_URL_PORT );
		$origin = $scheme . '://' . $host . ( $port ? ':' . $port : '' );
		$path   = untrailingslashit( (string) wp_parse_url( home_url(), PHP_URL_PATH ) );

		// Where a strict RFC 8414 client will actually fetch the metadata. well_known_url() folds in the issuer-prefix path when the host plugin has opted into one — so this stays correct whether we're at site root or namespaced under e.g. /em-mcp.
		$expected_as = Support::well_known_url( 'authorization_server' );
		$reachable   = self::probe_url( $expected_as );

		return array(
			'is_subdir'      => '' !== $path,
			'subdir'         => $path,
			'origin'         => $origin,
			'issuer_path'    => Support::issuer_path(),
			'expected_as'    => $expected_as,
			'actual_as'      => $expected_as,
			'root_reachable' => $reachable, // true|false|null(unknown)
			'htaccess'       => self::htaccess_rule( $path ),
		);
	}

	/** Best-effort loopback probe of a URL; cached briefly. Returns true|false|null. */
	private static function probe_url( string $url ) {
		$key    = 'pixelite_oauth_probe_' . md5( $url );
		$cached = get_transient( $key );
		if ( false !== $cached ) {
			return 'ok' === $cached ? true : ( 'fail' === $cached ? false : null );
		}
		$resp = wp_remote_get( $url, array( 'timeout' => 5, 'redirection' => 3, 'sslverify' => false ) );
		if ( is_wp_error( $resp ) ) {
			set_transient( $key, 'unknown', 5 * MINUTE_IN_SECONDS );
			return null;
		}
		$ok = 200 === (int) wp_remote_retrieve_response_code( $resp )
			&& false !== strpos( (string) wp_remote_retrieve_header( $resp, 'content-type' ), 'json' );
		set_transient( $key, $ok ? 'ok' : 'fail', 5 * MINUTE_IN_SECONDS );
		return $ok;
	}

	private static function htaccess_rule( string $path ): string {
		$p = ltrim( $path, '/' );
		return implode( "\n", array(
			'# OAuth / MCP discovery for the WordPress install in /' . $p . ' (RFC 8414 + 9728).',
			'# Add to the DOMAIN-ROOT .htaccess, ABOVE the main "# BEGIN WordPress" block.',
			'<IfModule mod_rewrite.c>',
			'RewriteEngine On',
			'RewriteRule "^\\.well-known/oauth-authorization-server/' . $p . '/?$" "/' . $p . '/.well-known/oauth-authorization-server" [R=302,L,QSA]',
			'RewriteRule "^\\.well-known/oauth-protected-resource/' . $p . '(/.*)?$" "/' . $p . '/.well-known/oauth-protected-resource$1" [R=302,L,QSA]',
			'</IfModule>',
		) );
	}

	/* ---------------------------------------------------------------------
	 * Routes
	 * ------------------------------------------------------------------ */

	public static function register_routes(): void {
		$ns = Support::rest_namespace();

		register_rest_route( $ns, '/token', array(
			'methods'             => 'POST',
			'callback'            => array( Token::class, 'handle' ),
			'permission_callback' => '__return_true',
		) );
		register_rest_route( $ns, '/revoke', array(
			'methods'             => 'POST',
			'callback'            => array( Revoke::class, 'handle' ),
			'permission_callback' => '__return_true',
		) );
		register_rest_route( $ns, '/register', array(
			'methods'             => 'POST',
			'callback'            => array( Register::class, 'handle' ),
			'permission_callback' => '__return_true',
		) );
		register_rest_route( $ns, '/metadata', array(
			'methods'             => 'GET',
			'callback'            => array( Metadata::class, 'rest_authorization_server' ),
			'permission_callback' => '__return_true',
		) );
		// JWKS stub. We never sign tokens so the set is empty, but the OIDC discovery doc has to advertise a jwks_uri and clients fetch it.
		register_rest_route( $ns, '/jwks', array(
			'methods'             => 'GET',
			'callback'            => array( Metadata::class, 'rest_jwks' ),
			'permission_callback' => '__return_true',
		) );
	}

	/* ---------------------------------------------------------------------
	 * Well-known endpoints at the install root
	 * ------------------------------------------------------------------ */

	public static function register_rewrites(): void {
		$authorize_path = Authorize::path();
		$issuer_path    = Support::issuer_path();

		if ( '' === $issuer_path ) {
			// Default: well-knowns at site root. Used when the host plugin is the only OAuth server on the install.
			$wk_as_rule   = '^\.well-known/oauth-authorization-server/?$';
			$wk_oidc_rule = '^\.well-known/openid-configuration/?$';
			$wk_pr_rule   = '^\.well-known/oauth-protected-resource(?:/.*)?$';
		} else {
			// Issuer-prefix mode: every well-known lives under the host's dedicated path so it can't collide with another OAuth server (e.g. IndieAuth) that owns the site-root well-known paths. RFC 8414 authz metadata is at site-root with the issuer as a suffix; OIDC discovery and RFC 9728 protected-resource are issuer-relative.
			$p             = preg_quote( $issuer_path, '#' );
			$wk_as_rule    = '^\.well-known/oauth-authorization-server/' . $p . '/?$';
			$wk_oidc_rule  = '^' . $p . '/\.well-known/openid-configuration/?$';
			$wk_pr_rule    = '^' . $p . '/\.well-known/oauth-protected-resource(?:/.*)?$';
			// Also accept the issuer-relative authz-metadata path that some clients probe in addition to (or instead of) the RFC 8414 form.
			add_rewrite_rule( '^' . $p . '/\.well-known/oauth-authorization-server/?$', 'index.php?pixelite_oauth_wk=as', 'top' );
		}

		add_rewrite_rule( $wk_as_rule, 'index.php?pixelite_oauth_wk=as', 'top' );
		add_rewrite_rule( $wk_oidc_rule, 'index.php?pixelite_oauth_wk=oidc', 'top' );
		add_rewrite_rule( $wk_pr_rule, 'index.php?pixelite_oauth_wk=pr', 'top' );
		add_rewrite_rule( '^' . preg_quote( $authorize_path, '#' ) . '/?$', 'index.php?pixelite_oauth_authorize=1', 'top' );

		add_filter( 'query_vars', static function ( $vars ) {
			$vars[] = 'pixelite_oauth_wk';
			$vars[] = 'pixelite_oauth_authorize';
			return $vars;
		} );

		// Self-heal: if our rules aren't registered yet (e.g. a freshly bundled copy whose host plugin didn't flush on activation, or a host that just flipped the issuer_path filter), flush once.
		$rules          = get_option( 'rewrite_rules' );
		$authorize_rule = '^' . preg_quote( $authorize_path, '#' ) . '/?$';
		$missing_rules  = is_array( $rules ) && (
			! isset( $rules[ $wk_as_rule ] )
			|| ! isset( $rules[ $wk_oidc_rule ] )
			|| ! isset( $rules[ $authorize_rule ] )
		);
		// Signature of the exact rules we depend on. Stored after each flush so a change to ANY of them (e.g. the host flips the issuer_path or authorize_path filter) re-flushes automatically — a static transient name would only ever flush once and leave discovery 404ing after a path change until someone manually saved permalinks.
		$signature = md5( implode( '|', array( $wk_as_rule, $wk_oidc_rule, $wk_pr_rule, $authorize_rule ) ) );
		if ( ( $missing_rules || get_option( 'pixelite_oauth_rules_signature' ) !== $signature ) ) {
			flush_rewrite_rules( false );
			update_option( 'pixelite_oauth_rules_signature', $signature, false );
		}
	}

	public static function maybe_serve_well_known( \WP $wp ): void {
		$which = $wp->query_vars['pixelite_oauth_wk'] ?? '';
		if ( ! $which ) {
			return;
		}
		nocache_headers();
		header( 'Content-Type: application/json; charset=' . get_option( 'blog_charset' ) );
		switch ( $which ) {
			case 'as':
				$payload = Metadata::authorization_server();
				break;
			case 'oidc':
				$payload = Metadata::openid_configuration();
				break;
			case 'pr':
			default:
				$payload = Metadata::protected_resource();
				break;
		}
		echo wp_json_encode( $payload );
		exit;
	}

	public static function maybe_serve_authorize(): void {
		if ( ! get_query_var( 'pixelite_oauth_authorize' ) ) {
			return;
		}
		Authorize::dispatch();
	}

	/**
	 * Add an RFC 9728 Bearer challenge to REST 401 responses that don't already carry one, pointing at this site's protected-resource metadata. This is what lets an MCP/AI client discover the authorization server from a 401.
	 *
	 * @param mixed            $result  Response (WP_REST_Response) about to be sent.
	 * @param \WP_REST_Server  $server
	 * @param \WP_REST_Request $request
	 * @return mixed
	 */
	public static function add_auth_challenge( $result, $server, $request ) {
		if ( ! $result instanceof \WP_REST_Response || 401 !== (int) $result->get_status() ) {
			return $result;
		}
		$headers = $result->get_headers();
		foreach ( array_keys( (array) $headers ) as $name ) {
			if ( 0 === strcasecmp( $name, 'WWW-Authenticate' ) ) {
				return $result; // Respect an existing challenge.
			}
		}
		$prm = Support::well_known_url( 'protected_resource' );
		$result->header( 'WWW-Authenticate', sprintf( 'Bearer resource_metadata="%s"', esc_url_raw( $prm ) ) );
		return $result;
	}
}
