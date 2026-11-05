<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Bridge between OAuth and WordPress Application Passwords.
 *
 * The OAuth access token we hand back to a client is simply base64("login:application_password") — the exact wire form Application Passwords already travel in. That makes the access token:
 *
 *   - self-contained: no server-side access-token storage at all;
 *   - validated by WordPress core on every request (battle-tested path);
 *   - visible to the site owner in Users -> Profile -> Application Passwords, where last-used / IP are tracked and the connection can be revoked;
 *   - rotated on refresh by deleting + recreating the Application Password with the same display name, so the user sees one stable entry that keeps working while the underlying secret cycles.
 *
 * Because the access token carries an Application Password, it must only ever be transmitted over TLS — the same requirement Application Passwords already impose (is_ssl()).
 */
class App_Passwords {

	/** `app_id` stamped on every Application Password this library creates, so they can be told apart from manually created ones. */
	const APP_ID = 'pixelite-oauth';

	/**
	 * Hook the Bearer -> core-auth translation. We do not authenticate ourselves; we translate the Bearer header into the Basic credentials WordPress core's Application Password validator already understands, then let core (priority 20 on determine_current_user) do the real work.
	 */
	public static function boot(): void {
		add_filter( 'determine_current_user', array( static::class, 'translate_bearer' ), 9 );

		// When a user deletes an Application Password from their profile, drop any matching OAuth refresh grant so a stale refresh token can't resurrect access.
		add_action( 'wp_delete_application_password', array( static::class, 'on_app_password_deleted' ), 10, 2 );
	}

	/**
	 * If the request carries a Bearer token that decodes to "login:password", populate PHP_AUTH_USER / PHP_AUTH_PW so core's Application Password validator picks it up. Returns the incoming value unchanged — we never short-circuit authentication ourselves.
	 *
	 * @param int|false|null $user_id
	 * @return int|false|null
	 */
	public static function translate_bearer( $user_id ) {
		if ( ! empty( $user_id ) ) {
			return $user_id;
		}
		if ( ! empty( $_SERVER['PHP_AUTH_USER'] ) ) {
			return $user_id; // Basic auth already present; leave it for core.
		}
		$token = Support::bearer_token();
		if ( null === $token ) {
			return $user_id;
		}
		$decoded = base64_decode( $token, true );
		if ( false === $decoded || strpos( $decoded, ':' ) === false ) {
			return $user_id;
		}
		list( $login, $password ) = explode( ':', $decoded, 2 );
		if ( '' === $login || '' === $password ) {
			return $user_id;
		}
		// Hand off to core's Application Password validator on the next filter.
		$_SERVER['PHP_AUTH_USER'] = $login;
		$_SERVER['PHP_AUTH_PW']   = $password;
		return $user_id;
	}

	/**
	 * Create an Application Password for a user and return the OAuth access token plus the new password's UUID (for later rotation / revocation).
	 *
	 * @return array{access_token:string, uuid:string}|\WP_Error
	 */
	public static function issue_access_token( int $user_id, string $app_name ) {
		$user = get_userdata( $user_id );
		if ( ! $user ) {
			return new \WP_Error( 'invalid_user', __( 'Unknown user.', 'wp-oauth-app-passwords' ) );
		}
		$created = \WP_Application_Passwords::create_new_application_password( $user_id, array(
			'name'   => self::sanitize_app_name( $app_name ),
			'app_id' => self::APP_ID,
		) );
		if ( is_wp_error( $created ) ) {
			return $created;
		}
		list( $raw_password, $item ) = $created;

		$access_token = base64_encode( $user->user_login . ':' . $raw_password );

		return array(
			'access_token' => $access_token,
			'uuid'         => (string) $item['uuid'],
		);
	}

	/**
	 * Rotate: delete the old Application Password and mint a fresh one under the same display name. Returns the new access token + uuid.
	 *
	 * @return array{access_token:string, uuid:string}|\WP_Error
	 */
	public static function rotate( int $user_id, string $old_uuid, string $app_name ) {
		// Delete first so the old access token stops working immediately.
		if ( $old_uuid ) {
			\WP_Application_Passwords::delete_application_password( $user_id, $old_uuid );
		}
		return self::issue_access_token( $user_id, $app_name );
	}

	public static function revoke( int $user_id, string $uuid ): void {
		if ( $uuid ) {
			\WP_Application_Passwords::delete_application_password( $user_id, $uuid );
		}
	}

	private static function sanitize_app_name( string $name ): string {
		$name = trim( wp_strip_all_tags( $name ) );
		if ( '' === $name ) {
			$name = __( 'MCP client', 'wp-oauth-app-passwords' );
		}
		// WordPress shows this in the user's profile; keep it readable.
		return mb_substr( $name, 0, 191 );
	}

	/**
	 * When an Application Password is deleted (from the profile UI or programmatically), purge any matching OAuth refresh grant.
	 *
	 * @param int   $user_id
	 * @param array $item    The deleted password record (includes 'uuid').
	 */
	public static function on_app_password_deleted( $user_id, $item ): void {
		$uuid = is_array( $item ) ? (string) ( $item['uuid'] ?? '' ) : '';
		if ( ! $uuid ) {
			return;
		}
		$match = Grants::find_by_app_password_uuid( (int) $user_id, $uuid );
		if ( $match ) {
			Grants::delete( (int) $user_id, $match['secret_hash'] );
		}
	}
}
