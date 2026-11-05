<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Authorization-server metadata (RFC 8414) and protected-resource metadata (RFC 9728). Served both as REST routes and at the conventional root /.well-known/ paths (handled by Server via a rewrite), so MCP clients that probe the well-known location can discover the endpoints.
 */
class Metadata {

	public static function authorization_server(): array {
		$base = Support::public_url( Support::rest_base_url() );
		$metadata = array(
			'issuer'                                => Support::issuer_url(),
			'authorization_endpoint'                => Authorize::url(),
			'token_endpoint'                        => $base . '/token',
			'registration_endpoint'                 => $base . '/register',
			'revocation_endpoint'                   => $base . '/revoke',
			'response_types_supported'              => array( 'code' ),
			'grant_types_supported'                 => array( 'authorization_code', 'refresh_token' ),
			'code_challenge_methods_supported'      => array( PKCE::METHOD ),
			'token_endpoint_auth_methods_supported' => array( 'none' ),
			'revocation_endpoint_auth_methods_supported' => array( 'none' ),
			'scopes_supported'                      => array_keys( Server::scopes() ),
		);
		// Optional: host plugins can advertise their own docs URL via the pixelite_oauth_service_documentation filter, or the broader pixelite_oauth_authorization_server_metadata filter. No default — the library doesn't presume the host wants to point at any URL.
		$docs = (string) apply_filters( 'pixelite_oauth_service_documentation', '' );
		if ( $docs !== '' ) {
			$metadata['service_documentation'] = $docs;
		}
		return apply_filters( 'pixelite_oauth_authorization_server_metadata', $metadata );
	}

	public static function protected_resource(): array {
		return apply_filters( 'pixelite_oauth_protected_resource_metadata', array(
			'resource'                 => Support::public_url( rest_url() ),
			'authorization_servers'    => array( Support::issuer_url() ),
			'scopes_supported'         => array_keys( Server::scopes() ),
			'bearer_methods_supported' => array( 'header' ),
		) );
	}

	/**
	 * OpenID Connect Discovery (1.0) document. We are not actually an OIDC provider — we never issue ID tokens — but ChatGPT (and a growing number of MCP clients) probe `/.well-known/openid-configuration` after a token is issued and treat a 404 as a connection failure ("Some enabled actions may not be callable…"). So we serve an OIDC-shaped document that points at our OAuth endpoints and explicitly advertises "we don't sign ID tokens" via id_token_signing_alg_values_supported=[none]. Clients that understand the doc will see there's no OIDC ID-token flow available and use the OAuth flow they already completed.
	 */
	public static function openid_configuration(): array {
		$base = Support::public_url( Support::rest_base_url() );
		$oauth = self::authorization_server();
		$oidc = array_merge( $oauth, array(
			'jwks_uri'                            => $base . '/jwks',
			'subject_types_supported'             => array( 'public' ),
			'id_token_signing_alg_values_supported' => array( 'none' ),
		) );
		return apply_filters( 'pixelite_oauth_openid_configuration', $oidc );
	}

	/**
	 * Empty JWKS set. We don't issue signed tokens, so there are no keys to publish — but the discovery doc has to advertise a jwks_uri, and clients that fetch it expect a well-formed JWKS response.
	 */
	public static function jwks(): array {
		return apply_filters( 'pixelite_oauth_jwks', array( 'keys' => array() ) );
	}

	public static function rest_authorization_server( \WP_REST_Request $request ) {
		return rest_ensure_response( self::authorization_server() );
	}

	public static function rest_protected_resource( \WP_REST_Request $request ) {
		return rest_ensure_response( self::protected_resource() );
	}

	public static function rest_jwks( \WP_REST_Request $request ) {
		return rest_ensure_response( self::jwks() );
	}
}
