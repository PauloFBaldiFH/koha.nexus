<?php
defined('WP_UNINSTALL_PLUGIN') || exit;
// Preserve attendance and certificates by default, including their revocation history.
// An administrator must deliberately opt into destructive removal in wp-config.php.
if (!defined('NXEV_DELETE_DATA') || NXEV_DELETE_DATA !== true || is_multisite()) {
    return;
}
global $wpdb;
foreach (array('attendance', 'certificates', 'log') as $name) {
    $wpdb->query('DROP TABLE IF EXISTS `' . $wpdb->prefix . 'nxev_' . $name . '`');
}
foreach (array('nxev_schema', 'nxev_institution') as $name) { delete_option($name); }
$ids = $wpdb->get_col("SELECT DISTINCT post_id FROM {$wpdb->postmeta} WHERE LEFT(meta_key,6)='_nxev_'");
foreach ($ids as $id) {
    foreach (array_keys(get_post_meta($id)) as $key) {
        if (strpos($key, '_nxev_') === 0) { delete_post_meta($id, $key); }
    }
}
