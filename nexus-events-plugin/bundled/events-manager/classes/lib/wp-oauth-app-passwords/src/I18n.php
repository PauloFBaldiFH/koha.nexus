<?php
namespace Pixelite\OAuth_App_Passwords;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Loads the library's own translations. Because the library is usually bundled
 * (not installed as a plugin in its own right), it loads its MO file directly
 * rather than via load_plugin_textdomain().
 */
class I18n {

	public static function boot(): void {
		add_action( 'init', array( static::class, 'load' ) );
	}

	public static function load(): void {
		$domain = Support::TEXT_DOMAIN;
		$locale = apply_filters( 'plugin_locale', determine_locale(), $domain );
		$mofile = Support::dir() . '/languages/' . $domain . '-' . $locale . '.mo';
		if ( is_readable( $mofile ) ) {
			load_textdomain( $domain, $mofile );
		}
		// Also allow a global WP_LANG_DIR override, mirroring core conventions.
		$global = WP_LANG_DIR . '/plugins/' . $domain . '-' . $locale . '.mo';
		if ( is_readable( $global ) ) {
			load_textdomain( $domain, $global );
		}
	}
}
