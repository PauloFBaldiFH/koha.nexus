<?php
namespace EM\Integrations;

class Duplicate_Post_Plugins {

	public static function init(){
		// Yoast Duplicate Post plugin
		if ( defined('DUPLICATE_POST_CURRENT_VERSION') ) {
			add_filter( 'duplicate_post_enabled_post_types', [ static::class, 'disable_yoast_duplicate_posts' ] );
		}
		// Copy and Duplicate Plugin
		if ( defined('CDP_VERSION') ) {
			add_action('template_redirect', [ static::class, 'disable_copy_and_duplicate_plugin' ] );
		}
		// Admin checks
		if ( is_admin() ) {
			include('duplicate-post-plugins-admin.php');
		}
	}

	/**
	 * Returns our CPTs that should not be duplicated by other plugins
	 *
	 * @return array
	 */
	public static function get_cpts() {
		return [EM_POST_TYPE_EVENT, EM_POST_TYPE_LOCATION, 'event-recurring'];
	}

	/**
	 * Disables events and locations from Yoast Duplicate posts, so that things aren't duplicated badly. Use EM duplication functions instead.
	 *
	 * @param array $enabled_post_types The array of post type names for which the plugin is enabled.
	 *
	 * @return array The filtered array of post types names.
	 */
	public static function disable_yoast_duplicate_posts( $enabled_post_types ) {
		foreach ( $enabled_post_types as $key => $post_type ) {
			if ( in_array( $post_type, [ EM_POST_TYPE_EVENT, EM_POST_TYPE_LOCATION, 'event-recurring' ] ) ) {
				unset( $enabled_post_types[ $key ] );
			}
		}
		return $enabled_post_types;
	}

	// Copy and Duplicate Plugin
	public static function disable_copy_and_duplicate_plugin() {
		if ( is_single() && in_array( get_post_type(), self::get_cpts() ) ) {
			add_filter('option__cdp_globals', [ static::class, 'disable_copy_and_duplicate_plugin_option' ], 10, 1 );
		}
	}

	public static function disable_copy_and_duplicate_plugin_option( $option ) {
		$option['others']['cdp-content-custom'] = 'false';
		return $option;
	}
}
Duplicate_Post_Plugins::init();