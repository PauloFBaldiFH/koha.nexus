<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Proof Key for Code Exchange (RFC 7636). S256 only — plain is intentionally
 * unsupported.
 */
class PKCE {

	const METHOD = 'S256';

	public static function is_valid_challenge( string $challenge, string $method ): bool {
		return $method === self::METHOD && (bool) preg_match( '/^[A-Za-z0-9_\-]{43,128}$/', $challenge );
	}

	public static function verify( string $verifier, string $expected_challenge ): bool {
		if ( ! preg_match( '/^[A-Za-z0-9_\-\.~]{43,128}$/', $verifier ) ) {
			return false;
		}
		$computed = rtrim( strtr( base64_encode( hash( 'sha256', $verifier, true ) ), '+/', '-_' ), '=' );
		return hash_equals( $expected_challenge, $computed );
	}
}
