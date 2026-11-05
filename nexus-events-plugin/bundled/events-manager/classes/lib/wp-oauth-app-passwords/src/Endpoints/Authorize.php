<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * The Authorization Code endpoint.
 *
 * Served as a normal front-end URL (home_url('/oauth/authorize')) rather than a REST route. This is deliberate: REST cookie authentication requires an X-WP-Nonce, which a plain browser navigation (the OAuth redirect) does not carry, so a REST-hosted authorize endpoint would 403 the very logged-in user we are trying to get consent from. A front-end URL authenticates the user from their session cookie the normal way; the consent POST carries its own nonce for CSRF protection.
 *
 * GET (logged out)  -> redirect through wp-login back to here.
 * GET (logged in)   -> render the branded consent screen.
 * POST (approve)    -> mint an authorization code, redirect to the client.
 * POST (deny)       -> redirect to the client with error=access_denied.
 *
 * No Application Password is created here; that waits until the code is exchanged at the token endpoint, so abandoned or denied flows leave nothing behind.
 */
class Authorize {

	/**
	 * Front-end path (relative to home) where this endpoint lives.
	 *
	 * When the host plugin has set an issuer path (via `pixelite_oauth_issuer_path`), the default authorize path moves under that prefix so the whole OAuth surface is namespaced — e.g. `em-mcp/oauth/authorize` instead of `oauth/authorize`. Hosts can still override the resulting path entirely via `pixelite_oauth_authorize_path`.
	 */
	public static function path(): string {
		$issuer_path = Support::issuer_path();
		$default     = '' === $issuer_path ? 'oauth/authorize' : $issuer_path . '/oauth/authorize';
		return (string) apply_filters( 'pixelite_oauth_authorize_path', $default );
	}

	public static function url(): string {
		return Support::public_url( home_url( '/' . ltrim( self::path(), '/' ) ) );
	}

	/**
	 * Front-end dispatcher, invoked from Server on template_redirect when the authorize query var is set.
	 */
	public static function dispatch(): void {
		$params = self::collect_params();

		$error = self::validate( $params );
		if ( is_wp_error( $error ) ) {
			if ( $params['client'] && $params['redirect_uri'] && Clients::redirect_uri_allowed( $params['client'], $params['redirect_uri'] ) ) {
				self::redirect_error( $params['redirect_uri'], $error->get_error_code(), $error->get_error_message(), $params['state'] );
			}
			self::render_fatal( $error );
		}

		if ( ! is_user_logged_in() ) {
			wp_safe_redirect( wp_login_url( self::self_url( $params ) ) );
			exit;
		}

		if ( 'POST' === strtoupper( (string) ( $_SERVER['REQUEST_METHOD'] ?? 'GET' ) ) ) {
			self::handle_decision( $params );
			exit;
		}

		Consent::render( $params );
		exit;
	}

	private static function handle_decision( array $params ): void {
		if ( ! wp_verify_nonce( self::param( '_pixelite_oauth_nonce' ), 'pixelite_oauth_consent' ) ) {
			self::redirect_error( $params['redirect_uri'], 'invalid_request', __( 'Security check failed. Please try again.', 'wp-oauth-app-passwords' ), $params['state'] );
		}

		if ( ! self::param( 'approve' ) ) {
			self::redirect_error( $params['redirect_uri'], 'access_denied', __( 'Authorization was declined.', 'wp-oauth-app-passwords' ), $params['state'] );
		}

		// The editable field is named "app_label" (not "app_name") so password managers like LastPass don't mistake it for a username and autofill it.
		$app_name = sanitize_text_field( self::param( 'app_label' ) );
		if ( '' === $app_name ) {
			$app_name = $params['app_name'];
		}

		$code = Codes::issue( array(
			'client_id'             => $params['client_id'],
			'user_id'               => get_current_user_id(),
			'redirect_uri'          => $params['redirect_uri'],
			'scope'                 => $params['scope'],
			'code_challenge'        => $params['code_challenge'],
			'code_challenge_method' => $params['code_challenge_method'],
			'app_name'              => $app_name,
			'issued_at'             => time(),
		) );

		$url = add_query_arg( array_filter( array(
			'code'  => rawurlencode( $code ),
			'state' => rawurlencode( $params['state'] ),
		) ), $params['redirect_uri'] );
		wp_redirect( $url );
		exit;
	}

	/** Read a request parameter (GET or POST), unslashed, as a string. */
	private static function param( string $key ): string {
		if ( isset( $_POST[ $key ] ) ) {
			return trim( (string) wp_unslash( $_POST[ $key ] ) );
		}
		if ( isset( $_GET[ $key ] ) ) {
			return trim( (string) wp_unslash( $_GET[ $key ] ) );
		}
		return '';
	}

	private static function collect_params(): array {
		$client_id = self::param( 'client_id' );
		$client    = $client_id ? Clients::get( $client_id ) : null;
		$redirect  = self::param( 'redirect_uri' );
		// Unknown scope names are dropped (and an empty request falls back to the default) so a client cannot ask for an unregistered scope and end up with an unrestricted grant.
		$scope     = Server::normalize_scope( self::param( 'scope' ) );
		// The displayed name comes from the stored client record, never from the request. Taking it from a `client_name` parameter let anyone who could register a client (registration is open by RFC 7591's open profile) put an arbitrary trusted-looking name on a consent screen served from the site's own domain.
		$client_name = is_array( $client ) ? (string) ( $client['name'] ?? '' ) : '';

		return array(
			'client_id'             => $client_id,
			'client'                => $client,
			'redirect_uri'          => $redirect,
			'state'                 => self::param( 'state' ),
			'scope'                 => $scope,
			'code_challenge'        => self::param( 'code_challenge' ),
			'code_challenge_method' => self::param( 'code_challenge_method' ),
			'response_type'         => self::param( 'response_type' ),
			'app_name'              => Support::guess_app_name( $client_name, $redirect ),
		);
	}

	private static function self_url( array $p ): string {
		return add_query_arg( rawurlencode_deep( array_filter( array(
			'response_type'         => 'code',
			'client_id'             => $p['client_id'],
			'redirect_uri'          => $p['redirect_uri'],
			'state'                 => $p['state'],
			'scope'                 => $p['scope'],
			'code_challenge'        => $p['code_challenge'],
			'code_challenge_method' => $p['code_challenge_method'],
		) ) ), self::url() );
	}

	private static function validate( array $p ) {
		if ( 'code' !== $p['response_type'] ) {
			return new \WP_Error( 'unsupported_response_type', __( 'Only response_type=code is supported.', 'wp-oauth-app-passwords' ) );
		}
		if ( ! $p['client'] ) {
			return new \WP_Error( 'invalid_client', __( 'Unknown client_id. Register the client first.', 'wp-oauth-app-passwords' ) );
		}
		if ( ! Clients::redirect_uri_allowed( $p['client'], $p['redirect_uri'] ) ) {
			return new \WP_Error( 'invalid_request', __( 'redirect_uri does not match a registered URI for this client.', 'wp-oauth-app-passwords' ) );
		}
		if ( ! PKCE::is_valid_challenge( $p['code_challenge'], $p['code_challenge_method'] ) ) {
			return new \WP_Error( 'invalid_request', __( 'A PKCE code_challenge using S256 is required.', 'wp-oauth-app-passwords' ) );
		}
		return true;
	}

	private static function redirect_error( string $redirect_uri, string $code, string $description, string $state ): void {
		$url = add_query_arg( array_filter( array(
			'error'             => rawurlencode( $code ),
			'error_description' => rawurlencode( $description ),
			'state'             => rawurlencode( $state ),
		) ), $redirect_uri );
		wp_redirect( $url );
		exit;
	}

	/** Render a minimal error page when we cannot safely redirect to a client. */
	private static function render_fatal( \WP_Error $error ): void {
		status_header( 400 );
		nocache_headers();
		header( 'Content-Type: text/html; charset=' . get_option( 'blog_charset' ) );
		header( 'X-Frame-Options: DENY' );
		header( "Content-Security-Policy: frame-ancestors 'none'" );
		echo '<!DOCTYPE html><meta charset="utf-8"><title>' . esc_html__( 'Authorization error', 'wp-oauth-app-passwords' ) . '</title>';
		echo '<div style="font-family:sans-serif;max-width:480px;margin:4em auto;padding:1.5em;border:1px solid #dcdcde;border-radius:8px">';
		echo '<h1 style="font-size:1.2em">' . esc_html__( 'Authorization error', 'wp-oauth-app-passwords' ) . '</h1>';
		echo '<p>' . esc_html( $error->get_error_message() ) . '</p>';
		echo '<p style="color:#646970;font-size:.85em">' . esc_html( $error->get_error_code() ) . '</p></div>';
		exit;
	}
}
