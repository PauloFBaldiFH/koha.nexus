<?php
namespace EM\API;

require_once EM_DIR . '/classes/api/em-api-utils.php';
require_once EM_DIR . '/classes/api/em-api-schemas.php';
require_once EM_DIR . '/classes/api/em-api-service.php';
require_once EM_DIR . '/classes/api/em-api-rest.php';
require_once EM_DIR . '/classes/api/em-api-abilities.php';
require_once EM_DIR . '/classes/api/em-api-mcp-server.php';
if ( is_admin() ) {
	require_once EM_DIR . '/classes/api/em-api-mcp-admin.php';
}

/**
 * Events Manager API bootstrap. Wires up the REST routes, the WordPress Abilities, the dedicated MCP server, the consent-screen scope, and the bundled OAuth + Application-Password library that authenticates incoming MCP / REST requests. The previous in-house OAuth authorization server was removed in favour of the shared `\Pixelite\OAuth_App_Passwords` library (under `classes/lib/wp-oauth-app-passwords`), which is also bundled into the bbPress API plugin so multiple host plugins can coexist on the same site.
 */
class API {

	/** Scope advertised on the consent screen and in discovery metadata. */
	const SCOPE = 'events-manager:mcp';

	public static function init() {
		static::boot_oauth_library();

		\EM\API\REST::init();
		\EM\API\Abilities::init();
		\EM\API\MCP_Server::init();

		add_action( 'init', array( __CLASS__, 'register_scope' ), 1 );
		if ( did_action( 'init' ) ) {
			static::register_scope();
		}

		if ( is_admin() ) {
			\EM\API\MCP_Admin::init();
		}
	}

	/**
	 * Register the Events Manager scope label/description with the OAuth library. The description is filterable via `em_api_scope_description` so satellite plugins in the EM family (Events Manager Pro, the gateway add-ons, the I/O importers) can extend it instead of registering separate scopes — they share this same scope umbrella because they share this same MCP server endpoint, so a separate consent row per satellite would just be noise for the user. No-ops if the bundled OAuth library hasn't loaded yet (e.g. the host is running a fork without it).
	 */
	public static function register_scope() {
		$server = '\\Pixelite\\OAuth_App_Passwords\\Server';
		if ( ! class_exists( $server ) ) {
			return;
		}
		$description = (string) apply_filters( 'em_api_scope_description', __( 'Manage events, bookings, locations, tickets and other related features.', 'events-manager' ) );
		$server::register_scope( static::SCOPE, array(
			'label'       => __( 'Events Manager', 'events-manager' ),
			'description' => $description,
			// REST route prefixes a credential approved for this scope may call; the library rejects everything else with 403. Pro's namespace is listed here rather than left to the filter so a site running an older Pro keeps a working connection once core enforces scopes.
			'routes'      => apply_filters( 'em_api_oauth_scope_routes', array(
				'/' . \EM\API\REST::NAMESPACE,
				'/events-manager-pro/v1',
				'/' . \EM\API\MCP_Server::server_path(),
			) ),
		) );
	}

	/**
	 * Boot the bundled `\Pixelite\OAuth_App_Passwords` library: tunnel-constant bridge, issuer-path namespace filter, and the loader require. Runs at file-load time (`API::init()` is called from the bottom of `em-api.php` when `events-manager.php` includes it), which is comfortably before `plugins_loaded:4` when the library itself boots. Keeping the bootstrap here — alongside the rest of the API wiring — instead of scattered at the top of `events-manager.php` matches where the library actually belongs in the dependency graph: it IS part of the EM API surface.
	 */
	protected static function boot_oauth_library() {
		// Back-compat bridge for the legacy EM_OAUTH_TUNNEL constant so existing dev setups don't have to rename anything in wp-config.php to keep ngrok/cloudflared dev tunnels working with the OAuth library's generic MCP_OAUTH_TUNNEL.
		if ( defined( 'EM_OAUTH_TUNNEL' ) && EM_OAUTH_TUNNEL && ! defined( 'MCP_OAUTH_TUNNEL' ) ) {
			define( 'MCP_OAUTH_TUNNEL', EM_OAUTH_TUNNEL );
		}
		// Namespace the OAuth library's URL surface under `events-manager` so its well-known endpoints (oauth-authorization-server, openid-configuration, oauth-protected-resource) and /oauth/authorize live under our prefix instead of the WordPress site root — avoids collisions with IndieAuth (now in WP core for some setups) or any legacy WP OAuth Server a customer might have installed on the same site. We only claim sub-paths (`/events-manager/oauth/authorize`, `/events-manager/.well-known/*`), never the bare `/events-manager` path, so an events page or CPT at that slug is unaffected. Has to be added before the library reads it on plugins_loaded:4.
		add_filter( 'pixelite_oauth_issuer_path', function () {
			return 'events-manager';
		} );
		require_once EM_DIR . '/classes/lib/wp-oauth-app-passwords/loader.php';
	}
}

API::init();
