<?php
namespace EM\Notifications;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Storage for the mobile app's push-notification device registry. One row per device token, owned by the WordPress user that authenticated when the app registered it. Each row carries the user's per-notification-type preferences as JSON ({"booking_added":{"own":true,"others":false}, ...}); device counts per site are small (a handful of organisers), so dispatch loads the set and filters in PHP rather than querying the JSON.
 *
 * The table is created by Installer::install() on EM install/upgrade, hooked to em_install_create_tables (wired in em-notifications.php, fired from em-install.php) — the EM way, rather than self-installing on every load.
 */
class Devices {

	public static function table() {
		global $wpdb;
		return $wpdb->prefix . 'em_app_devices';
	}

	/**
	 * Register a device, or update it if the token already exists (tokens are unique and survive reinstalls, so the same token can come back under a different user or with new prefs). $prefs is the per-type preference map; it is stored verbatim as JSON.
	 */
	public static function register( $user_id, $token, $platform, $label, array $prefs ) {
		global $wpdb;
		$now   = current_time( 'mysql', true );
		$table = self::table();
		$data  = array(
			'user_id'   => (int) $user_id,
			'token'     => $token,
			'platform'  => $platform,
			'label'     => $label,
			'prefs'     => wp_json_encode( $prefs ),
			'last_seen' => $now,
		);
		$existing_id = $wpdb->get_var( $wpdb->prepare( "SELECT id FROM $table WHERE token = %s", $token ) );
		if ( $existing_id ) {
			$wpdb->update( $table, $data, array( 'id' => $existing_id ) );
			return (int) $existing_id;
		}
		$data['created'] = $now;
		$wpdb->insert( $table, $data );
		return (int) $wpdb->insert_id;
	}

	/** Remove a token. Scoped to the owning user so one user can't delete another's device by guessing a token. */
	public static function unregister( $user_id, $token ) {
		global $wpdb;
		return (bool) $wpdb->delete( self::table(), array( 'token' => $token, 'user_id' => (int) $user_id ) );
	}

	/** Delete a token outright, irrespective of owner — used to prune tokens the push service reports as dead. */
	public static function prune( $token ) {
		global $wpdb;
		$wpdb->delete( self::table(), array( 'token' => $token ) );
	}

	/** Every device this user has registered (for the app to show/reconcile its own state). */
	public static function get_for_user( $user_id ) {
		global $wpdb;
		$table = self::table();
		$rows  = $wpdb->get_results( $wpdb->prepare( "SELECT id, token, platform, label, prefs, last_seen FROM $table WHERE user_id = %d", (int) $user_id ), ARRAY_A );
		return array_map( array( __CLASS__, 'hydrate' ), $rows ?: array() );
	}

	/** All devices on this site. Device counts are small; dispatch filters this set by type + capability in PHP. */
	public static function all() {
		global $wpdb;
		$table = self::table();
		$rows  = $wpdb->get_results( "SELECT id, user_id, token, platform, label, prefs FROM $table", ARRAY_A );
		return array_map( array( __CLASS__, 'hydrate' ), $rows ?: array() );
	}

	/** Decode the stored prefs JSON into an array on the row. */
	protected static function hydrate( $row ) {
		$row['prefs'] = $row['prefs'] ? json_decode( $row['prefs'], true ) : array();
		if ( ! is_array( $row['prefs'] ) ) {
			$row['prefs'] = array();
		}
		return $row;
	}

	/** Read one device's preference for a type+scope ('own'|'others'), defaulting off when unset. */
	public static function pref_enabled( array $device, $type_key, $scope ) {
		return ! empty( $device['prefs'][ $type_key ][ $scope ] );
	}
}
