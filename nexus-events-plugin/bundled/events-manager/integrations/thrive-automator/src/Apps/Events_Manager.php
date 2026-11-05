<?php
namespace EM\Thrive\Automator\Apps;

use Thrive\Automator\Items\App;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Events_Manager extends App {
	public static function get_id() {
		return 'events-manager';
	}

	public static function get_name() {
		return 'Events Manager';
	}

	public static function get_description() {
		return __('Integration with Events Manager Plugin', 'events-manager-for-thrive-automator');
	}

	public static function get_logo() {
		return trailingslashit(EM_DIR_URI).'includes/images/logo-160x160.png';
	}

	/**
	 * Whether the current App is available for the current user
	 * e.g prevent premium items from being shown to free users
	 *
	 * @return bool
	 */
	public static function has_access() {
		return defined('EM_VERSION') && version_compare(EM_VERSION, '6.1.5.1', '>=');
	}
	
	public static function get_acccess_url() {
		return 'https://wordpress.org/plugins/events-manager/';
	}
	
}