<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Shared helpers. Namespace-agnostic: internal references use self::/static:: and ::class only, so the namespace can be renamed or removed.
 */
class Support {

	/** Library text domain. */
	const TEXT_DOMAIN = 'wp-oauth-app-passwords';

	/** REST namespace for the OAuth endpoints (filterable). */
	public static function rest_namespace(): string {
		return (string) apply_filters( 'pixelite_oauth_rest_namespace', 'oauth/v1' );
	}

	/** Absolute base URL for the REST endpoints. */
	public static function rest_base_url(): string {
		return rest_url( self::rest_namespace() );
	}

	/**
	 * Optional URL-path prefix the host plugin opts into so the OAuth surface lives under a dedicated namespace (e.g. "events-manager-mcp") rather than at the WordPress site root. This keeps the well-known endpoints (`oauth-authorization-server`, `openid-configuration`, `oauth-protected-resource`) from colliding with another OAuth server on the same site — IndieAuth and legacy WP-OAuth-Server plugins both claim the site-root well-known paths, and `add_rewrite_rule` at 'top' is effectively last-registered-wins, which makes the behaviour racy when more than one plugin is in play.
	 *
	 * Default is empty (current behaviour). Hosts opt in via the `pixelite_oauth_issuer_path` filter, set early — before plugins_loaded:4 when the library boots — typically alongside the loader require in the main plugin file:
	 *
	 *     add_filter( 'pixelite_oauth_issuer_path', fn() => 'events-manager-mcp' );
	 *     require_once __DIR__ . '/lib/wp-oauth-app-passwords/loader.php';
	 *
	 * Trailing and leading slashes are stripped.
	 */
	public static function issuer_path(): string {
		return trim( (string) apply_filters( 'pixelite_oauth_issuer_path', '' ), '/' );
	}

	/**
	 * Canonical issuer URL. When `issuer_path()` is set, this is `home_url() . '/' . issuer_path`; otherwise it's plain `home_url()`. Use this everywhere the library produces an "issuer" value (metadata issuer field, OIDC discovery, etc.).
	 */
	public static function issuer_url(): string {
		$path = self::issuer_path();
		return self::public_url( '' === $path ? home_url() : home_url( '/' . $path ) );
	}

	/**
	 * Resolve the absolute URL for one of the three well-known endpoints we serve, honouring both the spec for that endpoint and the configured issuer path:
	 *
	 *   - `authorization_server` (RFC 8414): always at the host root with the issuer's path component appended as a suffix.
	 *     example: `https://site.com/.well-known/oauth-authorization-server/em-mcp`
	 *
	 *   - `openid_configuration` (OIDC Discovery 1.0): issuer-relative.
	 *     example: `https://site.com/em-mcp/.well-known/openid-configuration`
	 *
	 *   - `protected_resource` (RFC 9728): no spec mandate on the location for a custom resource URL, so we put it under the issuer path for the same conflict-avoidance reason.
	 *     example: `https://site.com/em-mcp/.well-known/oauth-protected-resource`
	 *
	 * Passes through `public_url()` so tunnel rewriting still applies.
	 */
	public static function well_known_url( string $type ): string {
		$issuer_path = self::issuer_path();
		$prefix      = '' === $issuer_path ? '' : '/' . $issuer_path;
		switch ( $type ) {
			case 'authorization_server':
				$path = '/.well-known/oauth-authorization-server' . ( '' === $issuer_path ? '' : '/' . $issuer_path );
				break;
			case 'openid_configuration':
				$path = $prefix . '/.well-known/openid-configuration';
				break;
			case 'protected_resource':
				$path = $prefix . '/.well-known/oauth-protected-resource';
				break;
			default:
				return '';
		}
		return self::public_url( home_url( $path ) );
	}

	/**
	 * Rewrite an absolute site URL through a developer tunnel when the MCP_OAUTH_TUNNEL constant is set (e.g. an ngrok / cloudflared base URL). This lets a local install advertise working OAuth + MCP discovery URLs to an external AI client during development. Only the leading home origin is replaced, so paths and query strings are preserved. A complete no-op (apart from the filter) in production, where the constant is undefined.
	 */
	public static function public_url( string $url ): string {
		$tunnel = ( defined( 'MCP_OAUTH_TUNNEL' ) && MCP_OAUTH_TUNNEL ) ? (string) MCP_OAUTH_TUNNEL : '';
		if ( '' !== $tunnel ) {
			$tunnel = untrailingslashit( $tunnel );
			$home   = untrailingslashit( home_url() );
			if ( '' !== $home && 0 === strpos( $url, $home ) ) {
				$url = $tunnel . substr( $url, strlen( $home ) );
			}
		}
		return (string) apply_filters( 'pixelite_oauth_public_url', $url );
	}

	public static function version(): string {
		return defined( 'PIXELITE_OAUTH_APP_PASSWORDS_VERSION' ) ? PIXELITE_OAUTH_APP_PASSWORDS_VERSION : '0';
	}

	public static function dir(): string {
		return defined( 'PIXELITE_OAUTH_APP_PASSWORDS_DIR' ) ? PIXELITE_OAUTH_APP_PASSWORDS_DIR : dirname( __DIR__ );
	}

	public static function url(): string {
		// plugins_url works whether bundled or standalone.
		return plugins_url( '', self::dir() . '/loader.php' );
	}

	/**
	 * Read the Bearer token from the current request, if present.
	 */
	public static function bearer_token(): ?string {
		$header = self::auth_header();
		if ( ! $header || stripos( $header, 'Bearer ' ) !== 0 ) {
			return null;
		}
		$token = trim( substr( $header, 7 ) );
		return $token !== '' ? $token : null;
	}

	public static function auth_header(): string {
		if ( ! empty( $_SERVER['HTTP_AUTHORIZATION'] ) ) {
			return trim( (string) wp_unslash( $_SERVER['HTTP_AUTHORIZATION'] ) );
		}
		if ( ! empty( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ) ) {
			return trim( (string) wp_unslash( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ) );
		}
		if ( function_exists( 'getallheaders' ) ) {
			foreach ( (array) getallheaders() as $key => $value ) {
				if ( strcasecmp( $key, 'Authorization' ) === 0 ) {
					return trim( (string) $value );
				}
			}
		}
		return '';
	}

	/** Constant-length hash for token storage / lookup. */
	public static function hash( string $value ): string {
		return hash( 'sha256', $value );
	}

	/** Cryptographically-random opaque token. */
	public static function random_token( int $length = 48 ): string {
		return wp_generate_password( $length, false, false );
	}

	/**
	 * Sanitize an OAuth redirect URI, keeping the schemes a public client legitimately needs:
	 *
	 *  - http / https (incl. loopback http://127.0.0.1[:port]) — kept via esc_url_raw() with an explicit protocol allowlist, exactly as before.
	 *  - RFC 8252 §7.1 private-use / custom schemes (e.g. `myapp://cb` or `com.example.app:/cb`) used by native mobile apps that can neither run a loopback listener nor rely on https without per-site Universal Links. esc_url_raw() silently strips these, so for a valid, non-dangerous custom scheme we return the URI unchanged after removing control characters.
	 *
	 * Always rejects schemes that can execute script or read local resources (javascript, data, vbscript, file, about, blob). Idempotent — sanitizing an already-clean value returns it byte-for-byte — so the authorize/token exact match against the stored value succeeds. Custom schemes are filterable so an admin can require reverse-DNS only, or disable them.
	 *
	 * @param mixed $uri
	 * @return string '' if empty, malformed, or a disallowed scheme.
	 */
	public static function sanitize_redirect_uri( $uri ): string {
		$uri = is_string( $uri ) ? $uri : '';
		// Strip control characters (never valid in a URI; the CRLF/injection vector).
		$uri = trim( (string) preg_replace( '/[\x00-\x1F\x7F]/', '', $uri ) );
		if ( '' === $uri ) {
			return '';
		}

		$scheme = strtolower( (string) wp_parse_url( $uri, PHP_URL_SCHEME ) );
		if ( '' === $scheme && preg_match( '#^([a-z][a-z0-9+.\-]*):#i', $uri, $m ) ) {
			$scheme = strtolower( $m[1] ); // parse_url can choke on dotted schemes.
		}
		if ( '' === $scheme || ! preg_match( '/^[a-z][a-z0-9+.\-]*$/', $scheme ) ) {
			return '';
		}

		// Web schemes (and loopback, which is http/https) keep full WP sanitization.
		if ( 'http' === $scheme || 'https' === $scheme ) {
			return (string) esc_url_raw( $uri, array( 'http', 'https' ) );
		}

		// Never allow schemes that can execute script or read local resources.
		if ( in_array( $scheme, array( 'javascript', 'data', 'vbscript', 'file', 'about', 'blob' ), true ) ) {
			return '';
		}

		// Private-use scheme (native app). Remove any internal whitespace and return as-is — esc_url_raw() would strip the whole URI.
		$uri = (string) preg_replace( '/\s+/', '', $uri );

		/**
		 * Whether to allow a given native-app (private-use) redirect-URI scheme. Return false to reject — e.g. to require reverse-DNS schemes only (`strpos( $scheme, '.' ) !== false`), or to disable custom schemes.
		 *
		 * @param bool   $allow
		 * @param string $scheme Lower-cased scheme, e.g. "com.example.app".
		 * @param string $uri    The full (control-stripped) redirect URI.
		 */
		if ( ! (bool) apply_filters( 'pixelite_oauth_allow_custom_redirect_scheme', true, $scheme, $uri ) ) {
			return '';
		}
		return $uri;
	}

	/**
	 * Map a redirect-URI host (or supplied client name) to a friendly default app name shown on the consent screen.
	 */
	public static function guess_app_name( string $client_name, string $redirect_uri ): string {
		$client_name = trim( wp_strip_all_tags( $client_name ) );
		if ( $client_name !== '' ) {
			return $client_name;
		}
		$host = '';
		if ( $redirect_uri ) {
			$host = (string) wp_parse_url( $redirect_uri, PHP_URL_HOST );
		}
		$host = strtolower( preg_replace( '/^www\./', '', $host ) );

		$known = (array) apply_filters( 'pixelite_oauth_known_clients', array(
			'claude.ai'    => 'Claude',
			'anthropic.com'=> 'Claude',
			'chatgpt.com'  => 'ChatGPT',
			'openai.com'   => 'ChatGPT',
			'cursor.com'   => 'Cursor',
			'cursor.sh'    => 'Cursor',
			'github.com'   => 'GitHub',
			'vscode.dev'   => 'VS Code',
		) );
		foreach ( $known as $needle => $label ) {
			if ( $host === $needle || ( $host && substr( $host, -strlen( $needle ) - 1 ) === '.' . $needle ) ) {
				return $label;
			}
		}
		if ( $host ) {
			// Title-case the registrable label, e.g. "myapp.example.com" -> "Myapp".
			$parts = explode( '.', $host );
			$label = isset( $parts[ count( $parts ) - 2 ] ) ? $parts[ count( $parts ) - 2 ] : $parts[0];
			return ucfirst( $label );
		}
		return __( 'MCP client', 'wp-oauth-app-passwords' );
	}

	/**
	 * Whether the OAuth server can currently issue credentials, with a reason when it cannot. Consuming plugins surface this in their admin UI.
	 *
	 * @return array{available:bool, reason:string}
	 */
	public static function availability(): array {
		if ( ! class_exists( '\\WP_Application_Passwords' ) ) {
			return array(
				'available' => false,
				'reason'    => __( 'Application Passwords are not available on this WordPress version (requires 5.6+).', 'wp-oauth-app-passwords' ),
			);
		}
		if ( function_exists( 'wp_is_application_passwords_available' ) && ! wp_is_application_passwords_available() ) {
			return array(
				'available' => false,
				'reason'    => __( 'Application Passwords are disabled. They require the site to be served over HTTPS (or an override filter).', 'wp-oauth-app-passwords' ),
			);
		}
		return array( 'available' => true, 'reason' => '' );
	}
}
