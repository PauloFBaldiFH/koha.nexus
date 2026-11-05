<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * /token — exchanges an authorization code for tokens, and refreshes them.
 *
 * On authorization_code: verify PKCE, create the Application Password now,
 * store the refresh grant, return access + refresh tokens.
 *
 * On refresh_token: validate + rotate the Application Password (delete old,
 * mint new same-named), issue a fresh access + refresh pair, invalidate the
 * old refresh token. This is what makes an AI client's connection persistent:
 * the named credential the user sees never disappears, the bytes behind it
 * rotate, and there is no short transient TTL to expire.
 */
class Token {

	public static function handle( \WP_REST_Request $request ) {
		$grant_type = (string) $request->get_param( 'grant_type' );
		if ( 'authorization_code' === $grant_type ) {
			return self::authorization_code( $request );
		}
		if ( 'refresh_token' === $grant_type ) {
			return self::refresh( $request );
		}
		return self::error( 'unsupported_grant_type', __( 'Only authorization_code and refresh_token are supported.', 'wp-oauth-app-passwords' ) );
	}

	private static function authorization_code( \WP_REST_Request $request ) {
		$code         = (string) $request->get_param( 'code' );
		$verifier     = (string) $request->get_param( 'code_verifier' );
		$client_id    = (string) $request->get_param( 'client_id' );
		$redirect_uri = (string) $request->get_param( 'redirect_uri' );

		if ( ! $code || ! $client_id || ! $verifier || ! $redirect_uri ) {
			return self::error( 'invalid_request', __( 'Missing required parameter.', 'wp-oauth-app-passwords' ) );
		}

		$grant = Codes::consume( $code );
		if ( ! $grant ) {
			return self::error( 'invalid_grant', __( 'Authorization code is invalid or expired.', 'wp-oauth-app-passwords' ) );
		}
		if ( $grant['client_id'] !== $client_id || $grant['redirect_uri'] !== $redirect_uri ) {
			return self::error( 'invalid_grant', __( 'Authorization code does not match this client.', 'wp-oauth-app-passwords' ) );
		}
		if ( ! PKCE::verify( $verifier, (string) $grant['code_challenge'] ) ) {
			return self::error( 'invalid_grant', __( 'PKCE verification failed.', 'wp-oauth-app-passwords' ) );
		}

		$user_id  = (int) $grant['user_id'];
		$app_name = (string) ( $grant['app_name'] ?? '' );

		$issued = App_Passwords::issue_access_token( $user_id, $app_name );
		if ( is_wp_error( $issued ) ) {
			return self::error( 'server_error', $issued->get_error_message() );
		}

		return self::issue_response( $user_id, $client_id, (string) $grant['scope'], $app_name, $issued['uuid'], $issued['access_token'] );
	}

	private static function refresh( \WP_REST_Request $request ) {
		$refresh_token = (string) $request->get_param( 'refresh_token' );
		$client_id     = (string) $request->get_param( 'client_id' );
		if ( ! $refresh_token || ! $client_id ) {
			return self::error( 'invalid_request', __( 'Missing required parameter.', 'wp-oauth-app-passwords' ) );
		}

		$parsed = Grants::parse_refresh_token( $refresh_token );
		if ( ! $parsed ) {
			return self::error( 'invalid_grant', __( 'Malformed refresh token.', 'wp-oauth-app-passwords' ) );
		}
		$grant = Grants::find( $parsed['user_id'], $parsed['secret_hash'] );
		if ( ! $grant ) {
			return self::error( 'invalid_grant', __( 'Refresh token is invalid or expired.', 'wp-oauth-app-passwords' ) );
		}
		if ( ( $grant['client_id'] ?? '' ) !== $client_id ) {
			return self::error( 'invalid_grant', __( 'Refresh token does not match this client.', 'wp-oauth-app-passwords' ) );
		}

		$user_id  = (int) $parsed['user_id'];
		$app_name = (string) ( $grant['app_name'] ?? '' );

		$rotated = App_Passwords::rotate( $user_id, (string) ( $grant['app_password_uuid'] ?? '' ), $app_name );
		if ( is_wp_error( $rotated ) ) {
			return self::error( 'server_error', $rotated->get_error_message() );
		}

		// Invalidate the old refresh grant; a new one is written by issue_response().
		Grants::delete( $user_id, $parsed['secret_hash'] );

		return self::issue_response( $user_id, $client_id, (string) ( $grant['scope'] ?? Server::default_scope() ), $app_name, $rotated['uuid'], $rotated['access_token'] );
	}

	/**
	 * Persist the refresh grant and build the RFC 6749 token response.
	 */
	private static function issue_response( int $user_id, string $client_id, string $scope, string $app_name, string $uuid, string $access_token ) {
		$refresh     = Grants::make_refresh_token( $user_id );
		$access_ttl  = Server::access_token_ttl();
		$refresh_ttl = Server::refresh_token_ttl();

		Grants::save( $user_id, $refresh['secret_hash'], array(
			'client_id'         => $client_id,
			'scope'             => $scope,
			'app_name'          => $app_name,
			'app_password_uuid' => $uuid,
			'created'           => time(),
			'refresh_expires'   => $refresh_ttl > 0 ? time() + $refresh_ttl : 0,
		) );

		$response = new \WP_REST_Response( array(
			'access_token'  => $access_token,
			'token_type'    => 'Bearer',
			'expires_in'    => $access_ttl,
			'refresh_token' => $refresh['token'],
			'scope'         => $scope,
		) );
		$response->header( 'Cache-Control', 'no-store' );
		$response->header( 'Pragma', 'no-cache' );
		return $response;
	}

	private static function error( string $code, string $description ) {
		return new \WP_Error( $code, $description, array( 'status' => 400 ) );
	}
}
