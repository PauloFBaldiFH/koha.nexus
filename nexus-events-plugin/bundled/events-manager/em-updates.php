<?php
/**
 * Plugin update checks and the auto-update veto.
 *
 * Kept in one always-loaded file rather than the admin-only em-admin.php, so the auto_update_plugin
 * veto is registered during background cron runs — which is where WordPress performs unattended updates.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * Resolves the dev (trunk) or stable (readme Stable tag) version for Events Manager and any .org plugin
 * hooked onto em_org_dev_versions, read directly from WordPress.org SVN. Returns an array keyed by plugin
 * file of update-response objects flagged em_manual_only. The result is cached (per request and in a site
 * transient) so repeated admin reads of the update transient don't re-hit SVN. Empty when neither dev nor
 * stable checking is enabled.
 *
 * @return array<string,\stdClass>
 */
function em_updates_bypass_entries() {
	static $resolved;
	if ( isset( $resolved ) ) {
		return $resolved;
	}
	$resolved = array();

	$want_dev    = em_get_option( 'em_check_dev_version' ) || em_get_option( 'dbem_pro_dev_updates' );
	$want_stable = em_get_option( 'em_check_stable_version' ) || em_get_option( 'dbem_check_stable_version' );
	if ( ! $want_dev && ! $want_stable ) {
		return $resolved;
	}

	// A one-off button (Re-Check Updates / Check Dev Versions) forces a fresh lookup, then clears its flag.
	if ( em_get_option( 'em_check_dev_version' ) || em_get_option( 'em_check_stable_version' ) ) {
		delete_option( 'em_check_dev_version' );
		delete_option( 'em_check_stable_version' );
		delete_site_transient( 'em_updates_bypass' );
	}

	$cached = get_site_transient( 'em_updates_bypass' );
	if ( is_array( $cached ) ) {
		$resolved = $cached;
		return $resolved;
	}

	$plugins = apply_filters( 'em_org_dev_versions', array(
		'events-manager' => array(
			'slug'    => EM_SLUG,
			'version' => EM_VERSION,
		),
	) );
	foreach ( $plugins as $org_slug => $plugin_info ) {
		$wp_slug     = $plugin_info['slug'];
		$new_version = false;
		$package     = 'https://downloads.wordpress.org/plugin/' . $org_slug . '.zip';
		if ( $want_dev ) {
			// trunk holds the latest development build
			$request = wp_remote_get( 'https://plugins.svn.wordpress.org/' . $org_slug . '/trunk/' . $org_slug . '.php' );
			if ( ! is_wp_error( $request ) && preg_match( '/Version: ([0-9a-z\.]+)/', $request['body'], $m ) ) {
				$new_version = $m[1];
			}
		} elseif ( $want_stable ) {
			// the Stable tag in trunk's readme names the current release, readable before the wp.org update API serves it
			$request = wp_remote_get( 'https://plugins.svn.wordpress.org/' . $org_slug . '/trunk/readme.txt' );
			if ( ! is_wp_error( $request ) && preg_match( '/Stable tag:\s*([0-9a-z\.\-]+)/i', $request['body'], $m ) && strtolower( $m[1] ) !== 'trunk' ) {
				$new_version = $m[1];
				$package     = 'https://downloads.wordpress.org/plugin/' . $org_slug . '.' . $new_version . '.zip';
			}
		}
		if ( is_wp_error( $request ) || empty( $new_version ) ) {
			continue;
		}
		$response                 = new stdClass();
		$response->slug           = $org_slug;
		$response->plugin         = $wp_slug;
		$response->new_version    = $new_version;
		$response->url            = 'https://wordpress.org/plugins/' . $org_slug . '/';
		$response->package        = $package;
		$response->em_manual_only = true;
		$icon = wp_remote_get( 'https://ps.w.org/' . $org_slug . '/assets/icon-128x128.png' );
		if ( ! is_wp_error( $icon ) && $icon['response']['code'] == 200 ) {
			$response->icons = array(
				'1x' => 'https://ps.w.org/' . $org_slug . '/assets/icon-128x128.png',
				'2x' => 'https://ps.w.org/' . $org_slug . '/assets/icon-256x256.png',
			);
		}
		$resolved[ $wp_slug ] = $response;
	}
	set_site_transient( 'em_updates_bypass', $resolved, HOUR_IN_SECONDS );
	return $resolved;
}

/**
 * Folds the manual-only bypass entries into an update-plugins transient object — for versions newer than
 * what's installed, and never over a version WordPress.org is already broadcasting (that one auto-updates
 * as usual). Shared by the write and read paths below.
 */
function em_updates_apply_bypass( $transient ) {
	if ( ! is_object( $transient ) || empty( $transient->checked ) ) {
		return $transient;
	}
	foreach ( em_updates_bypass_entries() as $wp_slug => $response ) {
		if ( empty( $transient->checked[ $wp_slug ] ) ) {
			continue;
		}
		if ( isset( $transient->response[ $wp_slug ] ) && version_compare( $transient->response[ $wp_slug ]->new_version, $response->new_version, '>=' ) ) {
			continue;
		}
		if ( version_compare( $transient->checked[ $wp_slug ], $response->new_version ) < 0 ) {
			$transient->response[ $wp_slug ] = $response;
			unset( $transient->no_update[ $wp_slug ] );
		} elseif ( ! isset( $transient->response[ $wp_slug ] ) ) {
			$transient->no_update[ $wp_slug ] = $response;
		}
	}
	return $transient;
}

/**
 * Fold the bypass into the update transient whenever WordPress (re)builds it — in every context, including cron.
 * Storing it in the transient is what keeps the held-back release visible between WordPress's throttled rebuilds,
 * with no need for a per-read filter: once written it persists until the next rebuild, which re-adds it. The
 * em_manual_only flag it carries is what keeps it out of unattended auto-updates (see the veto below), so putting
 * it in the cron-built transient is safe — it's surfaced for a manual "Update now" only.
 */
function em_updates_check( $transient ) {
	return em_updates_apply_bypass( $transient );
}
add_filter( 'pre_set_site_transient_update_plugins', 'em_updates_check', 100 );

/**
 * Versions surfaced above deliberately bypass the WordPress.org staggered rollout, so they must never drive
 * unattended background auto-updates — only manual "Update now". A null $update means WordPress is only asking
 * whether auto-updates are *forced* (the Plugins-screen display); pass that through so the plugin keeps showing
 * its normal opt-in state, and only veto the real auto-update decision, which passes a boolean.
 */
function em_prevent_manual_only_autoupdate( $update, $item ) {
	if ( empty( $item->em_manual_only ) ) {
		return $update;
	}
	// EM_AUTO_UPDATES=true (wp-config constant) auto-updates held-back versions too, not just showing them for manual install.
	if ( defined( 'EM_AUTO_UPDATES' ) && EM_AUTO_UPDATES ) {
		return true;
	}
	return null === $update ? $update : false;
}
add_filter( 'auto_update_plugin', 'em_prevent_manual_only_autoupdate', 100, 2 );

/**
 * Settings-page buttons: "Re-Check Updates" (one-off stable check) and "Check Dev Versions", both of which
 * clear the caches and flag the next check to read WordPress.org directly.
 */
function em_updates_admin_actions() {
	if ( empty( $_REQUEST['action'] ) || ! em_wp_is_super_admin() ) {
		return;
	}
	global $EM_Notices;
	if ( $_REQUEST['action'] == 'recheck_updates' && check_admin_referer( 'em_recheck_updates_' . get_current_user_id() . '_wpnonce' ) ) {
		delete_transient( 'update_plugins' );
		delete_site_transient( 'update_plugins' );
		delete_site_transient( 'em_updates_bypass' );
		update_option( 'em_check_stable_version', true );
		$EM_Notices->add_confirm( __( 'Checking for the latest stable version.', 'events-manager' ) . ' ' . __( 'If there are any new updates, you should now see them in your Plugins or Updates admin pages.', 'events-manager' ), true );
		wp_safe_redirect( em_wp_get_referer() );
		exit();
	}
	if ( $_REQUEST['action'] == 'check_devs' && check_admin_referer( 'em_check_devs_wpnonce' ) ) {
		delete_transient( 'update_plugins' );
		delete_site_transient( 'update_plugins' );
		delete_site_transient( 'em_updates_bypass' );
		update_option( 'em_check_dev_version', true );
		$EM_Notices->add_confirm( __( 'Checking for dev versions.', 'events-manager' ) . ' ' . __( 'If there are any new updates, you should now see them in your Plugins or Updates admin pages.', 'events-manager' ), true );
		wp_safe_redirect( em_wp_get_referer() );
		exit();
	}
}
add_action( 'admin_init', 'em_updates_admin_actions' );
