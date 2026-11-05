<?php
/**
 * Version-arbitrating loader for the Pixelite OAuth App Passwords library.
 *
 * This library is bundled directly inside multiple plugins. Each bundled copy
 * includes THIS file while its host plugin's main file is loading. The file does
 * NOT load the library immediately — it registers its own version + directory
 * into a shared global registry. On `plugins_loaded` (very early) the highest
 * registered version is the only one actually loaded; every older copy stands
 * down. The boot step is idempotent, so even if two copies share the same
 * version the classes load exactly once.
 *
 * This file is intentionally namespace-free and uses a unique function prefix so
 * that copies shipped at different library versions can coexist and coordinate
 * without fatal "cannot redeclare" errors.
 *
 * Host plugins include it like this (from their main plugin file):
 *
 *     require_once __DIR__ . '/includes/lib/wp-oauth-app-passwords/loader.php';
 *
 * @package Pixelite\OAuth_App_Passwords
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! function_exists( 'pixelite_oauth_app_passwords_register' ) ) {

	/**
	 * Register a bundled copy of the library. Invoked unconditionally by every
	 * copy's loader so the arbitrator can see all available versions.
	 *
	 * @param string $version Semver version literal of this copy.
	 * @param string $dir     Absolute path to this copy's root directory.
	 */
	function pixelite_oauth_app_passwords_register( $version, $dir ) {
		if ( ! isset( $GLOBALS['pixelite_oauth_app_passwords_copies'] ) ) {
			$GLOBALS['pixelite_oauth_app_passwords_copies'] = array();
		}
		// Last write wins for an identical version string — harmless.
		$GLOBALS['pixelite_oauth_app_passwords_copies'][ (string) $version ] = rtrim( (string) $dir, '/\\' );

		// If plugins_loaded already fired (a copy registered late, e.g. from a
		// plugin included after the hook), boot immediately. Otherwise the
		// hook below handles it once every copy has had a chance to register.
		if ( did_action( 'plugins_loaded' ) ) {
			pixelite_oauth_app_passwords_boot();
		}
	}

	/**
	 * Load the newest registered copy of the library, exactly once per request.
	 */
	function pixelite_oauth_app_passwords_boot() {
		static $booted = false;
		if ( $booted ) {
			return;
		}
		if ( empty( $GLOBALS['pixelite_oauth_app_passwords_copies'] ) ) {
			return;
		}

		$copies = $GLOBALS['pixelite_oauth_app_passwords_copies'];
		uksort( $copies, 'version_compare' );
		$dir     = end( $copies );   // highest version's directory
		$version = key( $copies );   // highest version string

		$bootstrap = $dir . '/bootstrap.php';
		if ( ! is_readable( $bootstrap ) ) {
			return;
		}

		$booted = true;

		if ( ! defined( 'PIXELITE_OAUTH_APP_PASSWORDS_VERSION' ) ) {
			define( 'PIXELITE_OAUTH_APP_PASSWORDS_VERSION', $version );
		}
		if ( ! defined( 'PIXELITE_OAUTH_APP_PASSWORDS_DIR' ) ) {
			define( 'PIXELITE_OAUTH_APP_PASSWORDS_DIR', $dir );
		}

		require_once $bootstrap; // bootstrap.php guards on class_exists().
	}

	// Boot ahead of host plugins, which conventionally initialise on
	// plugins_loaded at the default priority (10) or later.
	add_action( 'plugins_loaded', 'pixelite_oauth_app_passwords_boot', 4 );
}

/*
 * Always register THIS copy. The version literal is the single source of truth
 * for this bundled copy and is bumped on every library release.
 */
pixelite_oauth_app_passwords_register( '0.1.16', __DIR__ );
