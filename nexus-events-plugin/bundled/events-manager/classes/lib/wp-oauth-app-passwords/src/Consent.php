<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Renders the branded consent screen. Produces a complete, theme-independent HTML document (the endpoint exits afterwards), styled to look at home next to the WordPress login screen and carrying the site's own branding.
 */
class Consent {

	public static function render( array $params ): void {
		$user = wp_get_current_user();

		$view = array(
			'app_name'    => $params['app_name'],
			'scope'       => $params['scope'],
			'scopes'      => self::scope_rows( $params['scope'] ),
			'user'        => $user,
			/**
			 * Optional short note shown after "Acts as your account" on the consent screen, e.g. a role label. Empty by default so the screen stays generic and doesn't leak the user's raw WordPress roles.
			 *
			 * @param string   $note
			 * @param \WP_User $user
			 */
			'account_note' => (string) apply_filters( 'pixelite_oauth_consent_account_note', '', $user ),
			'branding'    => self::branding(),
			// Where approving actually sends the credential. Without this the user sees only a name the client chose and has no way to tell a first-party integration from someone else's host.
			'destination' => self::destination_label( $params['redirect_uri'] ),
			// A client that registered itself through the open /register endpoint has been vetted by nobody, so say so rather than letting its chosen name imply otherwise.
			'self_registered' => ! empty( $params['client']['dynamic'] ),
			// Whether the credential will be limited to the registered scopes' REST routes (see Scope_Guard) or carries the account's full access.
			'restricted'  => null !== Server::routes_for_scope( $params['scope'] ),
			'hidden'      => array_filter( array(
				'response_type'         => 'code',
				'client_id'             => $params['client_id'],
				'redirect_uri'          => $params['redirect_uri'],
				'state'                 => $params['state'],
				'scope'                 => $params['scope'],
				'code_challenge'        => $params['code_challenge'],
				'code_challenge_method' => $params['code_challenge_method'],
			) ),
			'form_action' => Authorize::url(),
			'switch_url'  => wp_logout_url( self::current_url() ),
		);

		status_header( 200 );
		nocache_headers();
		header( 'Content-Type: text/html; charset=' . get_option( 'blog_charset' ) );
		// This is a front-end URL, so WordPress's own anti-framing headers (sent on admin_init/login_init only) do not cover it; without these the Approve button can be framed and overlaid.
		header( 'X-Frame-Options: DENY' );
		header( "Content-Security-Policy: frame-ancestors 'none'" );

		// Expose $view to the template.
		$pixelite_oauth_view = $view;
		require Support::dir() . '/templates/consent.php';
	}

	/**
	 * Short, readable form of the redirect URI for display: the host for an http(s) URI, the scheme itself for a custom-scheme app redirect, and the raw URI as a last resort.
	 */
	private static function destination_label( string $redirect_uri ): string {
		if ( '' === $redirect_uri ) {
			return '';
		}
		$host = (string) wp_parse_url( $redirect_uri, PHP_URL_HOST );
		if ( '' !== $host ) {
			$port = wp_parse_url( $redirect_uri, PHP_URL_PORT );
			return $port ? $host . ':' . (int) $port : $host;
		}
		$scheme = (string) wp_parse_url( $redirect_uri, PHP_URL_SCHEME );
		return '' !== $scheme ? $scheme . '://' : $redirect_uri;
	}

	/**
	 * Build the list of permission rows shown on the consent screen.
	 *
	 * Important: the OAuth scope string is purely a client-side label in this library. The access token the client receives IS a WordPress Application Password, and App Passwords have no scope concept — they grant the user's full WordPress capabilities. Whichever scope the client requested, the granted access is identical.
	 *
	 * Rendering different rows for different requested scopes (e.g. Claude requesting `events-manager:mcp` sees 1 row, ChatGPT requesting `wp:api` sees 2 rows on the same site) is therefore misleading: it implies the grants differ. They do not.
	 *
	 * So we always render every plugin-registered scope. The screen tells the user the truth — "here's everything this site's MCP/API surface covers, and you're about to give the client access to all of it as your account." The $scope argument is kept for future use (per-row "requested" highlighting, third-party filters that want to override) but isn't used to gate which rows render.
	 *
	 * @return array<int,array{label:string, description:string}>
	 */
	private static function scope_rows( string $scope ): array {
		unset( $scope ); // intentionally unused; see method docblock.
		return array_values( Server::scopes() );
	}

	/**
	 * Resolve the site's branding: a logo image URL if one exists, plus the site name. Prefers the Customizer custom logo, then the site icon.
	 */
	private static function branding(): array {
		$logo_url = '';
		$logo_id  = (int) get_theme_mod( 'custom_logo' );
		if ( $logo_id ) {
			$img = wp_get_attachment_image_src( $logo_id, 'full' );
			if ( $img ) {
				$logo_url = $img[0];
			}
		}
		if ( ! $logo_url && function_exists( 'get_site_icon_url' ) ) {
			$logo_url = get_site_icon_url( 96 );
		}
		return array(
			'logo_url'  => $logo_url,
			'site_name' => get_bloginfo( 'name' ),
			'site_url'  => home_url(),
		);
	}

	private static function current_url(): string {
		// "Switch account" must return the user to this same screen, so build the URL from Authorize::url() (tunnel- and issuer-path-aware via Support::public_url()) plus the live query string.
		// Not from $_SERVER['HTTP_HOST']: behind a developer tunnel that is the internal vhost (e.g. wp.lan), which yields an off-tunnel redirect_to that wp_safe_redirect() rejects — dropping the user on wp-admin after they switch accounts instead of bringing them back here.
		$query = isset( $_SERVER['QUERY_STRING'] ) ? (string) wp_unslash( $_SERVER['QUERY_STRING'] ) : '';
		$url   = Authorize::url();
		if ( '' !== $query ) {
			$url .= ( false === strpos( $url, '?' ) ? '?' : '&' ) . $query;
		}
		return esc_url_raw( $url );
	}
}
