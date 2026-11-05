<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Authorization-code store. Codes are single-use and live ~10 minutes, so a
 * transient is appropriate: the only failure mode of an object-cache flush is
 * that an in-flight authorization must be retried, which is benign.
 *
 * No long-lived credential is ever stored here — the Application Password is
 * not created until the code is successfully exchanged at the token endpoint.
 */
class Codes {

	const PREFIX = 'pixelite_oauth_code_';
	const TTL    = 600; // 10 minutes.

	public static function issue( array $grant ): string {
		$code = Support::random_token( 48 );
		set_transient( self::PREFIX . Support::hash( $code ), $grant, self::TTL );
		return $code;
	}

	public static function consume( string $code ): ?array {
		$key   = self::PREFIX . Support::hash( $code );
		$grant = get_transient( $key );
		if ( ! is_array( $grant ) ) {
			return null;
		}
		delete_transient( $key ); // single use
		return $grant;
	}
}
