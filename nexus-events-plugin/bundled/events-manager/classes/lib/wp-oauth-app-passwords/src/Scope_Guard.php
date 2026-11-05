<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Enforces the granted scope on REST requests authenticated with an Application Password this library issued.
 *
 * An Application Password has no scope of its own: it carries every capability of its user. Left alone, a client approved for "Events Manager" could call any REST route the user can, up to `wp/v2/plugins` for an administrator. So when a scope is registered with a `routes` allowlist (see Server::register_scope()), a request authenticated by one of our passwords is limited to those routes and gets 403 `insufficient_scope` everywhere else.
 *
 * A granted scope that was registered without routes keeps the historical behaviour (full account access), so host plugins that have not declared routes are unaffected.
 */
class Scope_Guard {

	/** @var array<int,string>|null Allowed route prefixes for this request; null means unrestricted. */
	private static $allowed = null;

	public static function boot(): void {
		add_action( 'application_password_did_authenticate', array( static::class, 'on_authenticated' ), 10, 2 );
		add_filter( 'rest_pre_dispatch', array( static::class, 'enforce' ), 0, 3 );
		// Scope can only be checked on the REST transport. WordPress also accepts Application Passwords over XML-RPC and any other non-REST surface, where no scope check runs, so a route-restricted credential is refused there outright rather than acting with the user's full capabilities.
		add_filter( 'determine_current_user', array( static::class, 'enforce_non_rest' ), 30 );
		// The XML-RPC login path authenticates through the `authenticate` filter rather than determine_current_user (e.g. the app password passed as the XML-RPC password argument), so it is refused there too.
		add_filter( 'authenticate', array( static::class, 'enforce_authenticate' ), 30, 3 );
	}

	/**
	 * Resolve the granted scope of the Application Password that just authenticated this request, if it is one of ours.
	 *
	 * @param \WP_User|int $user
	 * @param array        $item The Application Password record (uuid, app_id, ...).
	 */
	public static function on_authenticated( $user, $item ): void {
		if ( ! is_array( $item ) || ( $item['app_id'] ?? '' ) !== App_Passwords::APP_ID ) {
			return;
		}
		if ( ! (bool) apply_filters( 'pixelite_oauth_enforce_scopes', true ) ) {
			return;
		}
		$user_id = $user instanceof \WP_User ? (int) $user->ID : (int) $user;
		$match   = Grants::find_by_app_password_uuid( $user_id, (string) ( $item['uuid'] ?? '' ) );
		// A password of ours with no grant on file (meta lost or hand-edited) is treated as the default scope rather than as unrestricted.
		$scope = $match ? (string) ( $match['grant']['scope'] ?? '' ) : '';
		self::$allowed = Server::routes_for_scope( Server::normalize_scope( $scope ) );
	}

	/**
	 * Refuse a route-restricted credential of ours on any non-REST request. on_authenticated() has already run by this priority and set self::$allowed when one of our passwords authenticated; a restricted scope cannot be honoured off REST, so the request is left unauthenticated rather than granting the user's full capabilities (for example over XML-RPC).
	 *
	 * @param int|false|null $user_id
	 * @return int|false|null
	 */
	public static function enforce_non_rest( $user_id ) {
		if ( empty( $user_id ) || null === self::$allowed ) {
			return $user_id;
		}
		if ( defined( 'REST_REQUEST' ) && REST_REQUEST ) {
			return $user_id;
		}
		return null;
	}

	/**
	 * As enforce_non_rest(), but for the `authenticate` filter that the XML-RPC login path runs through. on_authenticated() fires during core's app-password check on this same filter, so by this priority self::$allowed reflects whether one of our route-restricted passwords just authenticated.
	 *
	 * @param null|\WP_User|\WP_Error $user
	 * @param string                 $username
	 * @param string                 $password
	 * @return null|\WP_User|\WP_Error
	 */
	public static function enforce_authenticate( $user, $username, $password ) {
		if ( ! $user instanceof \WP_User || null === self::$allowed ) {
			return $user;
		}
		if ( defined( 'REST_REQUEST' ) && REST_REQUEST ) {
			return $user;
		}
		return new \WP_Error( 'insufficient_scope', __( 'This credential is limited to the features it was approved for and cannot be used here.', 'wp-oauth-app-passwords' ) );
	}

	/**
	 * @param mixed            $result
	 * @param \WP_REST_Server  $server
	 * @param \WP_REST_Request $request
	 * @return mixed
	 */
	public static function enforce( $result, $server, $request ) {
		if ( null !== $result ) {
			return $result;
		}
		// Authentication normally ran in check_authentication(); force it in case another plugin short-circuited that filter before core's Application Password check.
		wp_get_current_user();
		if ( null === self::$allowed || ! $request instanceof \WP_REST_Request ) {
			return $result;
		}
		$route = (string) $request->get_route();
		foreach ( self::$allowed as $prefix ) {
			if ( self::route_matches( $route, (string) $prefix ) ) {
				return $result;
			}
		}
		if ( $server instanceof \WP_REST_Server ) {
			$server->send_header( 'WWW-Authenticate', 'Bearer error="insufficient_scope"' );
		}
		return new \WP_Error( 'insufficient_scope', __( 'This credential is limited to the features it was approved for and cannot access this endpoint.', 'wp-oauth-app-passwords' ), array( 'status' => 403 ) );
	}

	/** True when $route is $prefix itself or lives beneath it ("/a/v1" matches "/a/v1/x" but not "/a/v10"). */
	public static function route_matches( string $route, string $prefix ): bool {
		$prefix = '/' . trim( $prefix, '/' );
		$route  = '/' . ltrim( $route, '/' );
		return $route === $prefix || 0 === strpos( $route, $prefix . '/' );
	}
}
