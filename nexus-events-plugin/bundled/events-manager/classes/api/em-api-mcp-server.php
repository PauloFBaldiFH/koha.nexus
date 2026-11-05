<?php
namespace EM\API;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Registers a dedicated MCP server for Events Manager on the WordPress MCP Adapter at a clean, stable route: `wp-json/mcp/events-manager`. Rather than riding the adapter's shared default server, every `events-manager/*` ability is listed explicitly so each one (`events-manager/create-event`, `events-manager/list-bookings`, …) appears to the AI client as a first-class MCP tool. Satellite plugins in the EM family (Events Manager Pro, gateways, importers) add their own ability namespaces to this same server via the `em_mcp_server_ability_prefixes` filter — there's no value in a separate Pro server when consent and auth already cover the whole site.
 *
 * Authentication flows through the bundled OAuth library: the adapter's default transport permission is `is_user_logged_in()`, which a valid Application Password token satisfies (and an anonymous request fails, triggering the OAuth discovery challenge the library adds to REST 401s).
 */
class MCP_Server {

	const ROUTE_NAMESPACE = 'mcp';
	const ROUTE           = 'events-manager';
	const SERVER_ID       = 'events-manager';

	/**
	 * Ability-name prefixes whose abilities are exposed as tools on this server. Core only knows about its own `events-manager/` namespace; satellites add theirs by hooking `em_mcp_server_ability_prefixes` (e.g. EM Pro appends `events-manager-pro/`), keeping core ignorant of which add-ons are installed.
	 *
	 * @return string[]
	 */
	protected static function ability_prefixes() {
		return (array) apply_filters( 'em_mcp_server_ability_prefixes', array(
			'events-manager/',
		) );
	}

	public static function init() {
		// Servers must be created during the adapter's init action.
		add_action( 'mcp_adapter_init', array( static::class, 'register' ) );
	}

	/**
	 * REST path of this server, e.g. "mcp/events-manager". Single source of truth shared with the admin screen so the displayed URL matches what we register.
	 */
	public static function server_path() {
		return static::ROUTE_NAMESPACE . '/' . static::ROUTE;
	}

	/**
	 * @param object $adapter The McpAdapter instance passed by mcp_adapter_init.
	 */
	public static function register( $adapter ) {
		if ( ! is_object( $adapter ) || ! method_exists( $adapter, 'create_server' ) ) {
			return;
		}

		// HttpTransport makes the server reachable over REST. If the adapter is too old to provide it, stand down rather than fatal.
		$transport = '\\WP\\MCP\\Transport\\HttpTransport';
		if ( ! class_exists( $transport ) ) {
			return;
		}

		$tools = static::tool_names();
		if ( empty( $tools ) ) {
			// No abilities registered (e.g. WordPress < 7.0) — nothing to expose.
			return;
		}

		$adapter->create_server(
			static::SERVER_ID,
			static::ROUTE_NAMESPACE,
			static::ROUTE,
			__( 'Events Manager', 'events-manager' ),
			__( 'Events Manager tools — create and manage events, bookings, locations, tickets and media — for MCP-compatible AI clients.', 'events-manager' ),
			defined( 'EM_VERSION' ) ? EM_VERSION : '0.0.0',
			array( $transport ),
			null, // error handler — adapter falls back to its Null handler.
			null, // observability handler — adapter falls back to its Null handler.
			$tools,
			array(), // resources
			array()  // prompts
		);
	}

	/**
	 * Every registered ability under any configured prefix, exposed as a tool. Built dynamically so new abilities appear automatically.
	 *
	 * @return string[]
	 */
	protected static function tool_names() {
		if ( ! function_exists( 'wp_get_abilities' ) ) {
			return array();
		}
		$prefixes = static::ability_prefixes();
		$names = array();
		foreach ( wp_get_abilities() as $ability ) {
			$name = is_object( $ability ) && method_exists( $ability, 'get_name' ) ? (string) $ability->get_name() : '';
			if ( '' === $name ) {
				continue;
			}
			foreach ( $prefixes as $prefix ) {
				if ( $prefix && strpos( $name, (string) $prefix ) === 0 ) {
					$names[] = $name;
					break;
				}
			}
		}
		return $names;
	}
}
