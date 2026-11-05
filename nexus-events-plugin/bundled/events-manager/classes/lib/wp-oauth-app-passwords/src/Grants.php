<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Refresh-grant store, backed by a single usermeta key per user.
 *
 * The refresh token has the shape "{user_id}~{random}". We embed the user id so
 * a refresh lookup is O(1) without a custom table and without a high-cardinality
 * meta_key: we parse the id, load that one user's grant array, and match the
 * random part by hash. Each connection is one entry; entries are replaced on
 * rotation and removed on revocation, so steady-state size is tiny (one or two
 * per user).
 *
 * No access tokens are stored here — those are the Application Password itself,
 * validated by WordPress core on each request.
 */
class Grants {

	const META_KEY  = '_pixelite_oauth_grants';
	const SEPARATOR = '~';

	/**
	 * Build an opaque refresh token that embeds the user id for O(1) lookup.
	 */
	public static function make_refresh_token( int $user_id ): array {
		$secret = Support::random_token( 64 );
		$token  = $user_id . self::SEPARATOR . $secret;
		return array( 'token' => $token, 'secret_hash' => Support::hash( $secret ) );
	}

	/**
	 * @return array{user_id:int, secret_hash:string}|null
	 */
	public static function parse_refresh_token( string $token ): ?array {
		$pos = strpos( $token, self::SEPARATOR );
		if ( $pos === false ) {
			return null;
		}
		$user_id = (int) substr( $token, 0, $pos );
		$secret  = substr( $token, $pos + 1 );
		if ( $user_id <= 0 || $secret === '' ) {
			return null;
		}
		return array( 'user_id' => $user_id, 'secret_hash' => Support::hash( $secret ) );
	}

	/** @return array<string,array> hash => grant */
	public static function for_user( int $user_id ): array {
		$raw = get_user_meta( $user_id, self::META_KEY, true );
		return is_array( $raw ) ? $raw : array();
	}

	public static function save( int $user_id, string $secret_hash, array $grant ): void {
		$all                 = self::for_user( $user_id );
		$all[ $secret_hash ] = $grant;
		update_user_meta( $user_id, self::META_KEY, $all );
	}

	public static function find( int $user_id, string $secret_hash ): ?array {
		$all = self::for_user( $user_id );
		if ( empty( $all[ $secret_hash ] ) ) {
			return null;
		}
		$grant = $all[ $secret_hash ];
		if ( ! empty( $grant['refresh_expires'] ) && (int) $grant['refresh_expires'] < time() ) {
			return null;
		}
		return $grant;
	}

	public static function delete( int $user_id, string $secret_hash ): void {
		$all = self::for_user( $user_id );
		if ( isset( $all[ $secret_hash ] ) ) {
			unset( $all[ $secret_hash ] );
			if ( $all ) {
				update_user_meta( $user_id, self::META_KEY, $all );
			} else {
				delete_user_meta( $user_id, self::META_KEY );
			}
		}
	}

	/**
	 * Find the grant that owns a given Application Password UUID (used when the
	 * user revokes from their profile and we want to drop the matching grant).
	 *
	 * @return array{secret_hash:string, grant:array}|null
	 */
	public static function find_by_app_password_uuid( int $user_id, string $uuid ): ?array {
		foreach ( self::for_user( $user_id ) as $hash => $grant ) {
			if ( ( $grant['app_password_uuid'] ?? '' ) === $uuid ) {
				return array( 'secret_hash' => $hash, 'grant' => $grant );
			}
		}
		return null;
	}
}
