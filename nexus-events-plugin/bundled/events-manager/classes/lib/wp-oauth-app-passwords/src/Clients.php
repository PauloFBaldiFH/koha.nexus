<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * OAuth client registry. Supports minimal Dynamic Client Registration
 * (RFC 7591) so MCP clients such as Claude can self-register, plus
 * admin-registered static clients. Public clients only — PKCE is required,
 * no client secrets are issued or stored.
 *
 * Stored in a single autoloaded-off option; cardinality stays low because
 * registrations are de-duplicated by (name + redirect-URI set).
 */
class Clients {

	const OPTION = 'pixelite_oauth_clients';
	const MAX    = 200;

	/** @return array<string,array> */
	public static function all(): array {
		$raw = get_option( self::OPTION, array() );
		return is_array( $raw ) ? $raw : array();
	}

	public static function get( string $client_id ): ?array {
		$all = self::all();
		return $all[ $client_id ] ?? null;
	}

	/**
	 * Register (or return an existing matching) client.
	 *
	 * @param array $meta { name, redirect_uris[], scopes[] }
	 */
	public static function register( array $meta ): array {
		$name          = sanitize_text_field( (string) ( $meta['name'] ?? '' ) );
		$redirect_uris = array_values( array_unique( array_filter( array_map(
			array( Support::class, 'sanitize_redirect_uri' ),
			(array) ( $meta['redirect_uris'] ?? array() )
		) ) ) );
		$scopes = array_values( array_unique( array_map(
			'sanitize_text_field',
			(array) ( $meta['scopes'] ?? array( Server::default_scope() ) )
		) ) );

		$all = self::all();

		// De-duplicate: same name + identical redirect set returns the existing id.
		$fingerprint = md5( strtolower( $name ) . '|' . implode( ',', $redirect_uris ) );
		foreach ( $all as $existing ) {
			if ( ( $existing['fingerprint'] ?? '' ) === $fingerprint ) {
				return $existing;
			}
		}

		// Bound the registry. A flood of drive-by registrations may only ever push out other self-registered clients, never one an administrator created, so it cannot evict the site's real client and break its authorize flow.
		if ( count( $all ) >= self::MAX ) {
			$dynamic = array_filter( $all, static function ( $client ) {
				return ! empty( $client['dynamic'] );
			} );
			if ( $dynamic ) {
				uasort( $dynamic, static function ( $a, $b ) {
					return ( $a['created'] ?? 0 ) <=> ( $b['created'] ?? 0 );
				} );
				unset( $all[ array_key_first( $dynamic ) ] );
			}
		}

		$client = array(
			'client_id'     => 'oauth-' . wp_generate_password( 24, false, false ),
			'name'          => $name,
			'redirect_uris' => $redirect_uris,
			'scopes'        => $scopes ?: array( Server::default_scope() ),
			'fingerprint'   => $fingerprint,
			'created'       => time(),
			'dynamic'       => ! empty( $meta['dynamic'] ),
		);
		$all[ $client['client_id'] ] = $client;
		update_option( self::OPTION, $all, false );

		return $client;
	}

	public static function delete( string $client_id ): bool {
		$all = self::all();
		if ( ! isset( $all[ $client_id ] ) ) {
			return false;
		}
		unset( $all[ $client_id ] );
		update_option( self::OPTION, $all, false );
		return true;
	}

	public static function redirect_uri_allowed( array $client, string $uri ): bool {
		// Exact match against a registered URI — use the same normalizer as storage.
		if ( in_array( Support::sanitize_redirect_uri( $uri ), (array) ( $client['redirect_uris'] ?? array() ), true ) ) {
			return true;
		}
		// Loopback IP redirect URIs may vary by port per RFC 8252 §7.3 — allow
		// any port for 127.0.0.1 / [::1] if the host (sans port) was registered.
		return self::loopback_match( $client, $uri );
	}

	private static function loopback_match( array $client, string $uri ): bool {
		$host = (string) wp_parse_url( $uri, PHP_URL_HOST );
		if ( $host !== '127.0.0.1' && $host !== '::1' && $host !== 'localhost' ) {
			return false;
		}
		$scheme = strtolower( (string) wp_parse_url( $uri, PHP_URL_SCHEME ) );
		$upath  = (string) wp_parse_url( $uri, PHP_URL_PATH );
		foreach ( (array) ( $client['redirect_uris'] ?? array() ) as $registered ) {
			$rscheme = strtolower( (string) wp_parse_url( $registered, PHP_URL_SCHEME ) );
			$rhost   = (string) wp_parse_url( $registered, PHP_URL_HOST );
			$rpath   = (string) wp_parse_url( $registered, PHP_URL_PATH );
			if ( $rscheme === $scheme && $rhost === $host && $rpath === $upath ) {
				return true;
			}
		}
		return false;
	}
}
