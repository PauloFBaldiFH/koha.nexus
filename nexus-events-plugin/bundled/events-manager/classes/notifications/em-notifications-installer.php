<?php
namespace EM\Notifications;

class Installer {

	public static function install() {
		global $wpdb;
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';
		$charset_collate = $wpdb->get_charset_collate();
		$table_name      = Devices::table();
		$sql             = "CREATE TABLE $table_name (
			id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
			user_id bigint(20) unsigned NOT NULL,
			token varchar(191) NOT NULL,
			platform varchar(10) NOT NULL DEFAULT '',
			label varchar(191) NOT NULL DEFAULT '',
			prefs longtext NULL DEFAULT NULL,
			created datetime NOT NULL,
			last_seen datetime NOT NULL,
			PRIMARY KEY  (id),
			UNIQUE KEY token (token),
			KEY user_id (user_id)
		) $charset_collate;";
		dbDelta( $sql );
	}
}