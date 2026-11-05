<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * /revoke — token revocation (RFC 7009).
 *
 * Accepts either an access token (base64 login:password) or a refresh token
 * ("{user_id}~{secret}"). Deletes the underlying Application Password and the
 * refresh grant. Always returns 200, per the RFC, regardless of whether the
 * token was found.
 */
class Revoke {

	public static function handle( \WP_REST_Request $request ) {
		$token = (string) $request->get_param( 'token' );
		if ( '' === $token ) {
			return rest_ensure_response( array() );
		}

		// Refresh-token shape?
		$parsed = Grants::parse_refresh_token( $token );
		if ( $parsed ) {
			$grant = Grants::find( $parsed['user_id'], $parsed['secret_hash'] );
			if ( $grant ) {
				App_Passwords::revoke( $parsed['user_id'], (string) ( $grant['app_password_uuid'] ?? '' ) );
				Grants::delete( $parsed['user_id'], $parsed['secret_hash'] );
			}
			return rest_ensure_response( array() );
		}

		// Access-token shape: base64(login:password). Authenticate to find the
		// owning user + the specific Application Password, then delete it.
		$decoded = base64_decode( $token, true );
		if ( false !== $decoded && strpos( $decoded, ':' ) !== false ) {
			list( $login, $password ) = explode( ':', $decoded, 2 );
			$user = wp_authenticate_application_password( null, $login, $password );
			if ( $user instanceof \WP_User ) {
				$uuid = self::find_uuid_for_password( $user->ID, $password );
				if ( $uuid ) {
					App_Passwords::revoke( $user->ID, $uuid );
					$match = Grants::find_by_app_password_uuid( $user->ID, $uuid );
					if ( $match ) {
						Grants::delete( $user->ID, $match['secret_hash'] );
					}
				}
			}
		}

		return rest_ensure_response( array() );
	}

	private static function find_uuid_for_password( int $user_id, string $raw_password ): string {
		foreach ( \WP_Application_Passwords::get_user_application_passwords( $user_id ) as $item ) {
			if ( ! empty( $item['password'] ) && wp_check_password( $raw_password, $item['password'], $user_id ) ) {
				return (string) $item['uuid'];
			}
		}
		return '';
	}
}
