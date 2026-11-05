<?php
//Function composing the options subpanel
use EM\Archetypes;
use EM\Archetypes_Admin;
use EM\Exception;

function em_options_save(){
	global $EM_Notices; /* @var EM_Notices $EM_Notices */
	/*
	 * Here's the idea, we have an array of all options that need super admin approval if in multi-site mode
	 * since options are only updated here, its one place fit all
	 */
	if( current_user_can('manage_options') && !empty($_POST['em-submitted']) && check_admin_referer('events-manager-options','_wpnonce') ){
		//Build the array of options here
		EM_Formats::remove_filters(true); // just in case

		// only run this if saving main CPT options
		if ( defined('EM_SETTINGS_ARCHETYPES_MERGED') && EM_SETTINGS_ARCHETYPES_MERGED || Archetypes::get_current() === Archetypes::$event['cpt'] ) {
			// fix some known empty issues, such as phone multiselectors
			if ( !isset($_POST['dbem_phone_countries_include']) ) $_POST['dbem_phone_countries_include'] = [];
			if ( !isset($_POST['dbem_phone_countries_exclude']) ) $_POST['dbem_phone_countries_exclude'] = [];

			foreach ($_POST as $postKey => $postValue){
				if( $postKey != 'dbem_data' && substr($postKey, 0, 5) == 'dbem_' ){
					//TODO some more validation/reporting
					$numeric_options = array('dbem_locations_default_limit','dbem_events_default_limit');
					if( in_array($postKey, array('dbem_bookings_notify_admin','dbem_event_submitted_email_admin','dbem_js_limit_events_form','dbem_js_limit_search','dbem_js_limit_general','dbem_css_limit_include','dbem_css_limit_exclude','dbem_search_form_geo_distance_options')) ){ $postValue = str_replace(' ', '', $postValue); } //clean up comma separated emails, no spaces needed
					if( in_array($postKey,$numeric_options) && !is_numeric($postValue) ){
						//Do nothing, keep old setting.
					}elseif( ($postKey == 'dbem_category_default_color' || $postKey == 'dbem_tag_default_color') && !sanitize_hex_color($postValue) ){
						$EM_Notices->add_error( sprintf(esc_html_x('Colors must be in a valid %s format, such as #FF00EE.', 'hex format', 'events-manager'), '<a href="http://en.wikipedia.org/wiki/Web_colors">hex</a>').' '. esc_html__('This setting was not changed.', 'events-manager'), true);
					}elseif( $postKey == 'dbem_oauth' && is_array($postValue) ){
						foreach($postValue as $postValue_key=>$postValue_val){
							$postValue_val = em_options_save_kses_deep( $postValue_val );
							EM_Options::set($postValue_key, wp_unslash($postValue_val), 'dbem_oauth');
						}
					}else{
						//TODO slashes being added?
						if( is_array($postValue) ){
						    foreach($postValue as $postValue_key=>$postValue_val) $postValue[$postValue_key] = wp_unslash($postValue_val);
						}else{
						    $postValue = wp_unslash($postValue);
						}
						$postValue = em_options_save_kses_deep( $postValue );
						update_option($postKey, $postValue);
					}
				}elseif( $postKey == 'dbem_data' && is_array($postValue) ){
					foreach( $postValue as $postK => $postV ){
						//TODO slashes being added?
						if( is_array($postV) ){
							foreach($postV as $postValue_key=>$postValue_val) $postV[$postValue_key] = wp_unslash($postValue_val);
						}else{
							$postV = wp_unslash($postV);
						}
						$postV = em_options_save_kses_deep( $postV );
						EM_Options::set( $postK, $postV );
					}
				}
			}

			// check formatting mode and optimize autoloading of formats from wp_options, first we make it all auto-loadable
			global $wpdb;
			$formats_to_autoload = EM_Formats::get_default_formats( true );
			array_walk($formats_to_autoload, 'sanitize_key');
			$wpdb->query("UPDATE {$wpdb->options} SET autoload='yes' WHERE option_name IN ('". implode("','", $formats_to_autoload) ."')");
			if( get_option('dbem_advanced_formatting') < 2 ){
				// now we make only the ones that we're loading from files directly non-autoloadable
				$formats_to_not_autoload = EM_Formats::get_default_formats();
				array_walk($formats_to_not_autoload, 'sanitize_key');
				$wpdb->query("UPDATE {$wpdb->options} SET autoload='no' WHERE option_name IN ('". implode("','", $formats_to_not_autoload) ."')");
			}// if set to 2 then we're just autoloading everything anyway
			if( get_option('dbem_advanced_formatting') == 1 ){
				$wpdb->query("UPDATE {$wpdb->options} SET autoload='yes' WHERE option_name='dbem_advanced_formatting_modes'");
			}else{
				$wpdb->query("UPDATE {$wpdb->options} SET autoload='no' WHERE option_name='dbem_advanced_formatting_modes'");
			}

			//set capabilities
			if( !empty($_POST['em_capabilities']) && is_array($_POST['em_capabilities']) && (!is_multisite() || is_multisite() && em_wp_is_super_admin()) ){
				global $em_capabilities_array, $wp_roles;
				if( is_multisite() && is_network_admin() && $_POST['dbem_ms_global_caps'] == 1 ){
				    //apply_caps_to_blog
					global $current_site,$wpdb;
					$blog_ids = $wpdb->get_col('SELECT blog_id FROM '.$wpdb->blogs.' WHERE site_id='.$current_site->id);
					foreach($blog_ids as $blog_id){
						switch_to_blog($blog_id);
					    //normal blog role application
						foreach( $wp_roles->role_objects as $role_name => $role ){
							foreach( array_keys($em_capabilities_array) as $capability){
								if( !empty($_POST['em_capabilities'][$role_name][$capability]) ){
									$role->add_cap($capability);
								}else{
									$role->remove_cap($capability);
								}
							}
						}
						restore_current_blog();
					}
				}elseif( !is_network_admin() ){
				    //normal blog role application
					foreach( $wp_roles->role_objects as $role_name => $role ){
						foreach( array_keys($em_capabilities_array) as $capability){
							if( !empty($_POST['em_capabilities'][$role_name][$capability]) ){
								$role->add_cap($capability);
							}else{
								$role->remove_cap($capability);
							}
						}
					}
				}
			}
		}
		update_option('dbem_flush_needed',1);
		do_action('em_options_save');
		$EM_Notices->add_confirm('<strong>'.__('Changes saved.', 'events-manager').'</strong>', true);
		$referrer = em_wp_get_referer();
		//add tab hash path to url if supplied
		if( !empty($_REQUEST['tab_path']) ){
			$referrer_array = explode('#', $referrer);
			$referrer = esc_url_raw($referrer_array[0] . '#' . $_REQUEST['tab_path']);
		}
		$referrer = apply_filters('em_options_save_redirect', $referrer);
		wp_safe_redirect($referrer);
		exit();
	}
	//Uninstall
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'uninstall' && current_user_can('activate_plugins') && !empty($_REQUEST['confirmed']) && check_admin_referer('em_uninstall_'.get_current_user_id().'_wpnonce') && em_wp_is_super_admin() ){
		if( EM_MS_GLOBAL && !is_main_site() ){
			$EM_Notices->add_error( sprintf( esc_html__('Events Manager was not uninstalled. This network shares one set of event and booking tables, so uninstalling from this site would permanently delete the events and bookings of every site on the network. Uninstall from the %s instead.','events-manager'), '<a href="'. esc_url( network_admin_url('admin.php?page=events-manager-options') ) .'">'. esc_html__('network settings page','events-manager') .'</a>' ) );
		}elseif( check_admin_referer('em_uninstall_'.get_current_user_id().'_confirmed','_wpnonce2') ){
			//We have a go to uninstall
			global $wpdb;
			//delete EM posts
			remove_action('before_delete_post',array('EM_Location_Post_Admin','before_delete_post'),10,1);
			remove_action('before_delete_post',array('EM_Event_Post_Admin','before_delete_post'),10,1);
			remove_action('before_delete_post',array('EM_Event_Recurring_Post_Admin','before_delete_post'),10,1);
			$post_ids = $wpdb->get_col('SELECT ID FROM '.$wpdb->posts." WHERE post_type IN ('".EM_POST_TYPE_EVENT."','".EM_POST_TYPE_LOCATION."','event-recurring')");
			foreach($post_ids as $post_id){
				wp_delete_post($post_id);
			}
			//delete categories
			$cat_terms = get_terms(EM_TAXONOMY_CATEGORY, array('hide_empty'=>false));
			foreach($cat_terms as $cat_term){
				wp_delete_term($cat_term->term_id, EM_TAXONOMY_CATEGORY);
			}
			$tag_terms = get_terms(EM_TAXONOMY_TAG, array('hide_empty'=>false));
			foreach($tag_terms as $tag_term){
				wp_delete_term($tag_term->term_id, EM_TAXONOMY_TAG);
			}
			//delete EM tables
			$wpdb->query('DROP TABLE '.EM_EVENTS_TABLE);
			$wpdb->query('DROP TABLE '.EM_BOOKINGS_TABLE);
			$wpdb->query('DROP TABLE '.EM_LOCATIONS_TABLE);
			$wpdb->query('DROP TABLE '.EM_TICKETS_TABLE);
			$wpdb->query('DROP TABLE '.EM_TICKETS_BOOKINGS_TABLE);
			$wpdb->query('DROP TABLE '.EM_EVENT_RECURRENCES_TABLE);
			$wpdb->query('DROP TABLE '.EM_META_TABLE);
			
			//delete options
			$wpdb->query('DELETE FROM '.$wpdb->options.' WHERE option_name LIKE \'em_%\' OR option_name LIKE \'dbem_%\'');
			//deactivate and go!
			deactivate_plugins(array('events-manager/events-manager.php','events-manager-pro/events-manager-pro.php'), true);
			wp_safe_redirect(admin_url('plugins.php?deactivate=true'));
			exit();
		}
	}
	//Reset
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'reset' && !empty($_REQUEST['confirmed']) && check_admin_referer('em_reset_'.get_current_user_id().'_wpnonce') && em_wp_is_super_admin() ){
		if( check_admin_referer('em_reset_'.get_current_user_id().'_confirmed','_wpnonce2') ){
			//We have a go to uninstall
			global $wpdb;
			//delete options
			$wpdb->query('DELETE FROM '.$wpdb->options.' WHERE option_name LIKE \'em_%\' OR option_name LIKE \'dbem_%\'');
			//reset capabilities
			global $em_capabilities_array, $wp_roles;
			foreach( $wp_roles->role_objects as $role_name => $role ){
				foreach( array_keys($em_capabilities_array) as $capability){
					$role->remove_cap($capability);
				}
			}
			//go back to plugin options page
			$EM_Notices->add_confirm(__('Settings have been reset back to default. Your events, locations and categories have not been modified.','events-manager'), true);
			wp_safe_redirect(em_wp_get_referer());
			exit();
		}
	}
	//Cleanup Event Orphans
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'cleanup_event_orphans' && check_admin_referer('em_cleanup_event_orphans_'.get_current_user_id().'_wpnonce') && em_wp_is_super_admin() ){
		global $wpdb;
		//Firstly, get all orphans
		if ( is_multisite() ) {
			// in MS we need to select the subsite blog posts table, and either the global or blog events table depending if in MS GLobal mode
			if ( !empty($_REQUEST['blog']) && is_numeric($_REQUEST['blog']) ) {
				$blog_id = absint($_REQUEST['blog']);
				switch_to_blog( $blog_id );
				$events_table = EM_MS_GLOBAL ? EM_EVENTS_TABLE : $wpdb->prefix . 'em_events';
				$sql = 'SELECT event_id FROM '.$events_table.' WHERE post_id > 0 AND post_id NOT IN (SELECT ID FROM ' .$wpdb->posts. ' WHERE post_type="'. EM_POST_TYPE_EVENT .'" OR post_type="event-recurring")';
				// if global mode we also need a blog ID to match
				if( EM_MS_GLOBAL ){
					if( get_main_site_id() == $blog_id ){
						$sql .= $wpdb->prepare(' AND (blog_id=%d or blog_id IS NULL)', $blog_id);
					}else{
						$sql .= $wpdb->prepare(' AND blog_id=%d', $blog_id);
					}
				}
			} else {
				$EM_Notices->add_error( 'Please supply a valid blog ID' );
				wp_safe_redirect(em_wp_get_referer());
				exit();
			}
		} else {
			$sql = 'SELECT event_id FROM '.EM_EVENTS_TABLE.' WHERE post_id > 0 AND post_id NOT IN (SELECT ID FROM ' .$wpdb->posts. ' WHERE post_type="'. EM_POST_TYPE_EVENT .'" OR post_type="event-recurring")';
		}
		$results = $wpdb->get_col($sql);
		$deleted_events = 0;
		foreach( $results as $event_id ){
			$EM_Event = new EM_Event($event_id);
			if( !empty($EM_Event->orphaned_event) && $EM_Event->delete() ){
				$deleted_events++;
			}
		}
		//go back to plugin options page
		$EM_Notices->add_confirm(sprintf(__('Found %d orphaned events, deleted %d successfully','events-manager'), count($results), $deleted_events), true);
		wp_safe_redirect(em_wp_get_referer());
		exit();
	}
	//import EM settings
	if( !empty($_REQUEST['action']) && ( ($_REQUEST['action'] == 'import_em_settings' && check_admin_referer('import_em_settings')) || (is_multisite() && $_REQUEST['action'] == 'import_em_ms_settings' && check_admin_referer('import_em_ms_settings')) ) && em_wp_is_super_admin() ){
		//upload uniquely named file to system for usage later
		if( !empty($_FILES['import_settings_file']['size']) && is_uploaded_file($_FILES['import_settings_file']['tmp_name']) ){
			$settings = file_get_contents($_FILES['import_settings_file']['tmp_name']);
			$settings = json_decode($settings, true);
			if( is_array($settings) ){
				if( is_multisite() && $_REQUEST['action'] == 'import_em_ms_settings' ){
					global $EM_MS_Globals, $wpdb;
					$sitewide_options = $EM_MS_Globals->get_globals();
					foreach( $settings as $k => $v ){
						if( in_array($k, $sitewide_options) ) update_site_option($k, $v);
					}
				}else{
					foreach( $settings as $k => $v ){
						if( preg_match('/^(?:db)emp?_/', $k) ){
							update_option($k, $v);
						}
					}
				}
				$EM_Notices->add_confirm(__('Settings imported.','events-manager'), true);
				wp_safe_redirect(em_wp_get_referer());
				exit();
			}
		}
		$EM_Notices->add_error(__('Please upload a valid txt file containing Events Manager import settings.','events-manager'), true);
		wp_safe_redirect(em_wp_get_referer());
		exit();
	}
	//export EM settings
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'export_em_settings' && check_admin_referer('export_em_settings') && em_wp_is_super_admin() ){
		global $wpdb;
		$results = $wpdb->get_results('SELECT option_name, option_value FROM '.$wpdb->options ." WHERE option_name LIKE 'dbem_%' OR option_name LIKE 'emp_%' OR option_name LIKE 'em_%'", ARRAY_A);
		$options = array();
		foreach( $results as $result ) $options[$result['option_name']] = $result['option_value'];
		header('Content-Type: text/plain; charset=utf-8');
		header('Content-Disposition: attachment; filename="events-manager-settings.txt"');
		echo json_encode($options);
		exit();
	}elseif( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'export_em_ms_settings' && check_admin_referer('export_em_ms_settings') && is_multisite() && em_wp_is_super_admin() ){
		//delete transients, and add a flag to recheck dev version next time round
		global $EM_MS_Globals, $wpdb;
		$options = array();
		$sitewide_options = $EM_MS_Globals->get_globals();
		foreach( $sitewide_options as $option ) $options[$option] = get_site_option($option);
		header('Content-Type: text/plain; charset=utf-8');
		header('Content-Disposition: attachment; filename="events-manager-settings.txt"');
		echo json_encode($options);
		exit();
	}

	// convert ALL repeating events
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'convert_repeating_to_recurrence' && check_admin_referer('convert_repeating_to_recurrence_'. get_current_user_id(), 'nonce') ){
		// go through all the repeated events, remove the post, unset post_id and done!
		global $wpdb;
		$post_ids_subquery = 'SELECT post_id FROM '. EM_EVENTS_TABLE ." WHERE post_id IS NOT NULL AND event_type='recurrence'";
		$post_deletion = $wpdb->query( 'DELETE FROM '. $wpdb->posts . ' WHERE ID IN (' . $post_ids_subquery . ')');
		if ( $post_deletion !== false ) {
			$meta_deletion = $wpdb->query( 'DELETE FROM ' . $wpdb->postmeta . ' WHERE post_id IN (' . $post_ids_subquery . ')' );
			if ( $meta_deletion !== false ) {
				$update_events = $wpdb->query( 'UPDATE ' . EM_EVENTS_TABLE . " SET post_id = NULL WHERE event_type = 'recurrence' AND post_id > 0" );
				if ( $update_events !== false ) {
					$wpdb->update( EM_EVENTS_TABLE, ['event_type' => 'recurring'], ['event_type' => 'repeating'] );
					$wpdb->update( $wpdb->postmeta, ['meta_value' => 'recurring'], ['meta_key'=> '_event_type', 'meta_value' => 'repeating'] );
					$wpdb->update( $wpdb->posts, ['post_type' => EM_POST_TYPE_EVENT], ['post_type' => 'event-recurring'] );
					update_option('dbem_repeating_enabled', false);
					update_option('dbem_recurrence_enabled', true);
					$message = __('The repeating events have been converted into recurring events.', 'events-manager');
					$EM_Notices->add_confirm( $message, true );
					EM_Admin_Notices::remove('v7-reconvert-recurrences');
				} else {
					$EM_Notices->add_error( 'Deleted post data and meta, but could not update event.', true );
				}
			} else {
				$EM_Notices->add_error( 'Could not delete post meta.', true );
			}
		} else {
			$EM_Notices->add_error( 'Could not delete post data.', true );
		}
		wp_safe_redirect( em_wp_get_referer() );
		exit();
	}
	
	//reset timezones
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'reset_timezones' && check_admin_referer('reset_timezones') && em_wp_is_super_admin() ){
		include(EM_DIR.'/em-install.php');
		if( empty($_REQUEST['timezone_reset_value']) ) return;
		$timezone = str_replace('UTC ', '', $_REQUEST['timezone_reset_value']);
		if( is_multisite() ){
			if( !empty($_REQUEST['timezone_reset_blog']) && is_numeric($_REQUEST['timezone_reset_blog']) ){
				$blog_id = $_REQUEST['timezone_reset_blog'];
				switch_to_blog($blog_id);
				if( $timezone == 'default' ){
					$timezone = str_replace(' ', EM_DateTimeZone::create()->getName());
				}
				$blog_name = get_bloginfo('name');
				$result = em_migrate_datetime_timezones(true, true, $timezone);
				restore_current_blog();
			}elseif( !empty($_REQUEST['timezone_reset_blog']) && ($_REQUEST['timezone_reset_blog'] == 'all' || $_REQUEST['timezone_reset_blog'] == 'all-resume') ){
				global $wpdb, $current_site;
				$blog_ids = $blog_ids_progress = get_site_option('dbem_reset_timezone_multisite_progress', false);
				if( !is_array($blog_ids) || $_REQUEST['timezone_reset_blog'] == 'all' ){
					$blog_ids = $blog_ids_progress = $wpdb->get_col('SELECT blog_id FROM '.$wpdb->blogs.' WHERE site_id='.$current_site->id);
					update_site_option('dbem_reset_timezone_multisite_progress', $blog_ids_progress);
				}
				foreach($blog_ids as $k => $blog_id){
					$result = true;
					$plugin_basename = plugin_basename(dirname(dirname(__FILE__)).'/events-manager.php');
					if( in_array( $plugin_basename, (array) get_blog_option($blog_id, 'active_plugins', array() ) ) || is_plugin_active_for_network($plugin_basename) ){
						switch_to_blog($blog_id);
						$blog_timezone = $timezone == 'default' ? str_replace(' ', '', EM_DateTimeZone::create()->getName()) : $timezone;
						$blog_name = get_bloginfo('name');
						$blog_result = em_migrate_datetime_timezones(true, true, $blog_timezone);
						if( !$blog_result ){
							$fails[$blog_id] = $blog_name;
						}else{
							unset($blog_ids_progress[$k]);
							update_site_option('dbem_reset_timezone_multisite_progress', $blog_ids_progress);
						}
					}
				}
				if( !empty($fails) ){
					$result = __('The following blog timezones could not be successfully reset:', 'events-manager');
					$result .= '<ul>';
					foreach( $fails as $fail ) $result .= '<li>'.$fail.'</li>';
					$result .= '</ul>';
				}else{
					delete_site_option('dbem_reset_timezone_multisite_progress');
					EM_Admin_Notices::remove('date_time_migration_5.9_multisite', true);
				}
				restore_current_blog();
			}else{
				$result = __('A valid blog ID must be provided, you can only reset one blog at a time.','events-manager');
			}
		}else{
			$result = em_migrate_datetime_timezones(true, true, $timezone);
		}
		if( $result !== true ){
			$EM_Notices->add_error($result, true);
		}else{
			if( is_multisite() ){
				if( $_REQUEST['timezone_reset_blog'] == 'all' || $_REQUEST['timezone_reset_blog'] == 'all-resume' ){
					$EM_Notices->add_confirm(sprintf(__('Event timezones on all blogs have been reset to %s.','events-manager'), '<code>'.$timezone.'</code>'), true);
				}else{
					$EM_Notices->add_confirm(sprintf(__('Event timezones for blog %s have been reset to %s.','events-manager'), '<code>'.$blog_name.'</code>', '<code>'.$timezone.'</code>'), true);
				}
			}else{
				$EM_Notices->add_confirm(sprintf(__('Event timezones have been reset to %s.','events-manager'), '<code>'.$timezone.'</code>'), true);
			}
		}
		wp_safe_redirect(em_wp_get_referer());
		exit();
	}
	
	//update scripts that may need to run
	$blog_updates = is_multisite() ? array_merge(EM_Options::get('updates'), EM_Options::site_get('updates')) : EM_Options::get('updates');
	if( is_array($blog_updates) ) {
		foreach ( $blog_updates as $update => $update_data ) {
			// update keys are script filenames; reject any value that could traverse out of the updates directory
			if ( !is_string($update) || !preg_match('/^[A-Za-z0-9._-]+$/', $update) || strpos($update, '..') !== false ) {
				continue;
			}
			$filename = EM_DIR . '/admin/settings/updates/' . $update . '.php';
			if ( file_exists( $filename ) ) {
				include_once( $filename );
			}
			do_action( 'em_admin_update_' . $update, $update_data );
		}
	}
}
add_action('admin_init', 'em_options_save');

/**
 * Runs wp_kses on string or recursviely into array.
 * @param array|string $string
 *
 * @return mixed
 */
function em_options_save_kses_deep( $string ) {
	if ( (defined('EM_UNFILTERED_HTML') && EM_UNFILTERED_HTML) || current_user_can('unfiltered_html') ) return $string;
	if( is_array($string) ) {
		foreach ( $string as $k => $v ) {
			$string[$k] = em_options_save_kses_deep( $v );
		}
	} else {
		$string = wp_kses_post( $string );
	}
	return $string;
}

function em_admin_email_test_ajax(){
    if( wp_verify_nonce($_REQUEST['_check_email_nonce'] ?? '','check_email') && current_user_can('manage_options') ){
        $subject = __("Events Manager Test Email",'events-manager');
        $content = __('Congratulations! Your email settings work.','events-manager');
        $current_user = get_user_by('id', get_current_user_id());
        //add filters for options used in EM_Mailer so the current supplied ones are used
        ob_start();
        function pre_option_dbem_mail_sender_name(){ return sanitize_text_field($_REQUEST['dbem_mail_sender_name']); }
        add_filter('pre_option_dbem_mail_sender_name', 'pre_option_dbem_mail_sender_name');
        function pre_option_dbem_mail_sender_address(){ return sanitize_text_field($_REQUEST['dbem_mail_sender_address']); }
        add_filter('pre_option_dbem_mail_sender_address', 'pre_option_dbem_mail_sender_address');
        function pre_option_dbem_rsvp_mail_send_method(){ return sanitize_text_field($_REQUEST['dbem_rsvp_mail_send_method']); }
        add_filter('pre_option_dbem_rsvp_mail_send_method', 'pre_option_dbem_rsvp_mail_send_method');
        function pre_option_dbem_rsvp_mail_port(){ return sanitize_text_field($_REQUEST['dbem_rsvp_mail_port']); }
        add_filter('pre_option_dbem_rsvp_mail_port', 'pre_option_dbem_rsvp_mail_port');
	    function pre_option_dbem_smtp_encryption(){ return sanitize_text_field($_REQUEST['dbem_smtp_encryption']); }
	    add_filter('pre_option_dbem_smtp_encryption', 'pre_option_dbem_smtp_encryption');
	    function pre_option_dbem_smtp_autotls(){ return sanitize_text_field($_REQUEST['dbem_smtp_autotls']); }
	    add_filter('pre_option_dbem_smtp_autotls', 'pre_option_dbem_smtp_autotls');
        function pre_option_dbem_rsvp_mail_SMTPAuth(){ return sanitize_text_field($_REQUEST['dbem_rsvp_mail_SMTPAuth']); }
        add_filter('pre_option_dbem_rsvp_mail_SMTPAuth', 'pre_option_dbem_rsvp_mail_SMTPAuth');
        function pre_option_dbem_smtp_host(){ return sanitize_text_field($_REQUEST['dbem_smtp_host']); }
        add_filter('pre_option_dbem_smtp_host', 'pre_option_dbem_smtp_host');
        function pre_option_dbem_smtp_username(){ return sanitize_text_field($_REQUEST['dbem_smtp_username']); }
        add_filter('pre_option_dbem_smtp_username', 'pre_option_dbem_smtp_username');
        function pre_option_dbem_smtp_password(){ return sanitize_text_field($_REQUEST['dbem_smtp_password']); }
        add_filter('pre_option_dbem_smtp_password', 'pre_option_dbem_smtp_password');        
        ob_clean(); //remove any php errors/warnings output
        $EM_Event = new EM_Event();
        if( $EM_Event->email_send($subject,$content,$current_user->user_email) ){
        	$result = array(
        		'result' => true,
        		'message' => sprintf(__('Email sent successfully to %s','events-manager'),$current_user->user_email)
        	);
        }else{
            $result = array(
            	'result' => false,
            	'message' => __('Email not sent.','events-manager')." <ul><li>".implode('</li><li>',$EM_Event->get_errors()).'</li></ul>'
            );
        }
        echo EM_Object::json_encode($result);
    }else{
        echo EM_Object::json_encode( array(
            'result' => false,
            'message' => esc_html__('You do not have permission to send a test email, or this page has expired. Please reload the settings page and try again.','events-manager'),
        ) );
    }
    exit();
}
add_action('wp_ajax_em_admin_test_email','em_admin_email_test_ajax');

function em_admin_option_default_ajax() {
	if( current_user_can('activate_plugins') && wp_verify_nonce($_REQUEST['nonce'], 'option-default-'.$_REQUEST['option_name']) && preg_match('/^[a-zA-Z_0-9]+$/', $_REQUEST['option_name']) ) {
		$return = call_user_func("EM_Formats::".$_REQUEST['option_name'], '');
		echo $return;
	}
	exit();
}
add_action('wp_ajax_em_admin_get_option_default','em_admin_option_default_ajax');

function em_admin_options_reset_page(){
	if( check_admin_referer('em_reset_'.get_current_user_id().'_wpnonce') && em_wp_is_super_admin() ){
		?>
		<div class="wrap">		
			<div id='icon-options-general' class='icon32'><br /></div>
			<h2><?php _e('Reset Events Manager','events-manager'); ?></h2>
			<p style="color:red; font-weight:bold;"><?php _e('Are you sure you want to reset Events Manager?','events-manager')?></p>
			<p style="font-weight:bold;"><?php _e('All your settings, including email templates and template formats for Events Manager will be deleted.','events-manager')?></p>
			<p>
				<a href="<?php echo esc_url(add_query_arg(array('_wpnonce2' => wp_create_nonce('em_reset_'.get_current_user_id().'_confirmed'), 'confirmed'=>1))); ?>" class="button-primary"><?php _e('Reset Events Manager','events-manager'); ?></a>
				<a href="<?php echo esc_url(em_wp_get_referer()); ?>" class="button-secondary"><?php _e('Cancel','events-manager'); ?></a>
			</p>
		</div>		
		<?php
	}
}
function em_admin_options_uninstall_page(){
	if( check_admin_referer('em_uninstall_'.get_current_user_id().'_wpnonce') && em_wp_is_super_admin() ){
		$network_wide = EM_MS_GLOBAL;
		$refused = $network_wide && !is_main_site();
		?>
		<div class="wrap">		
			<div id='icon-options-general' class='icon32'><br /></div>
			<h2><?php _e('Uninstall Events Manager','events-manager'); ?></h2>
			<p style="color:red; font-weight:bold;"><?php
				if( $refused ){
					esc_html_e('Events Manager cannot be uninstalled from this site.','events-manager');
				}else{
					_e('Are you sure you want to uninstall Events Manager?','events-manager');
				}
			?></p>
			<p style="font-weight:bold;"><?php
				if( $refused ){
					echo sprintf( esc_html__('This network shares one set of event and booking tables, so uninstalling from this site would permanently delete the events and bookings of every site on the network. Uninstall from the %s instead.','events-manager'), '<a href="'. esc_url( network_admin_url('admin.php?page=events-manager-options') ) .'">'. esc_html__('network settings page','events-manager') .'</a>' );
				}elseif( $network_wide ){
					esc_html_e('All settings, events and bookings for every site on this network will be permanently deleted. This cannot be undone.','events-manager');
				}else{
					_e('All your settings and events will be permanently deleted. This cannot be undone.','events-manager');
				}
			?></p>
			<p><?php echo sprintf(__('If you just want to deactivate the plugin, <a href="%s">go to your plugins page</a>.','events-manager'), wp_nonce_url(admin_url('plugins.php'))); ?></p>
			<p>
				<?php if( !$refused ) : ?>
				<a href="<?php echo esc_url(add_query_arg(array('_wpnonce2' => wp_create_nonce('em_uninstall_'.get_current_user_id().'_confirmed'), 'confirmed'=>1))); ?>" class="button-primary"><?php _e('Uninstall and Deactivate','events-manager'); ?></a>
				<?php endif; ?>
				<a href="<?php echo esc_url(em_wp_get_referer()); ?>" class="button-secondary"><?php _e('Cancel','events-manager'); ?></a>
			</p>
		</div>		
		<?php
	}
}

function em_admin_options_page() {
	global $wpdb, $EM_Notices;
	//Check for uninstall/reset request
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'uninstall' ){
		em_admin_options_uninstall_page();
		return;
	}	
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'reset' ){
		em_admin_options_reset_page();
		return;
	}
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'update' && !empty($_REQUEST['update_action']) ){
		do_action('em_admin_update_settings_confirm_'.$_REQUEST['update_action']);
		return;
	}
	//substitute dropdowns with input boxes for some situations to improve speed, e.g. if there 1000s of locations or users
	$total_users = $wpdb->get_var("SELECT COUNT(ID) FROM {$wpdb->users};");
	if( $total_users > 100 && !defined('EM_OPTIMIZE_SETTINGS_PAGE_USERS') ){ define('EM_OPTIMIZE_SETTINGS_PAGE_USERS',true); }
	$total_locations = EM_Locations::count();
	if( $total_locations > 100 && !defined('EM_OPTIMIZE_SETTINGS_PAGE_LOCATIONS') ){ define('EM_OPTIMIZE_SETTINGS_PAGE_LOCATIONS',true); }
	//TODO place all options into an array
	global $events_placeholder_tip, $locations_placeholder_tip, $categories_placeholder_tip, $bookings_placeholder_tip;
	$events_placeholders = '<a href="'.EM_ADMIN_URL .'&amp;page=events-manager-help#event-placeholders">'. __('Event Related Placeholders','events-manager') .'</a>';
	$locations_placeholders = '<a href="'.EM_ADMIN_URL .'&amp;page=events-manager-help#location-placeholders">'. __('Location Related Placeholders','events-manager') .'</a>';
	$bookings_placeholders = '<a href="'.EM_ADMIN_URL .'&amp;page=events-manager-help#booking-placeholders">'. __('Booking Related Placeholders','events-manager') .'</a>';
	$categories_placeholders = '<a href="'.EM_ADMIN_URL .'&amp;page=events-manager-help#category-placeholders">'. __('Category Related Placeholders','events-manager') .'</a>';
	$events_placeholder_tip = " ". sprintf(__('This accepts %s and %s placeholders.','events-manager'),$events_placeholders, $locations_placeholders);
	$locations_placeholder_tip = " ". sprintf(__('This accepts %s placeholders.','events-manager'), $locations_placeholders);
	$categories_placeholder_tip = " ". sprintf(__('This accepts %s placeholders.','events-manager'), $categories_placeholders);
	$bookings_placeholder_tip = " ". sprintf(__('This accepts %s, %s and %s placeholders.','events-manager'), $bookings_placeholders, $events_placeholders, $locations_placeholders);
	
	global $save_button;
	$save_button = '<tr><th>&nbsp;</th><td><p class="submit" style="margin:0px; padding:0px; text-align:right;"><input type="submit" class="button-primary" name="Submit" value="'. __( 'Save Changes', 'events-manager') .' ('. __('All','events-manager') .')" /></p></td></tr>';
	
	do_action('em_options_page_header');
	
	if( defined('EM_SETTINGS_TABS') && EM_SETTINGS_TABS ){
	    $tabs_enabled = true;
	    $general_tab_link = esc_url(add_query_arg( array('em_tab'=>'general')));
	    $pages_tab_link = esc_url(add_query_arg( array('em_tab'=>'pages')));
	    $formats_tab_link = esc_url(add_query_arg( array('em_tab'=>'formats')));
	    $bookings_tab_link = esc_url(add_query_arg( array('em_tab'=>'bookings')));
	    $emails_tab_link = esc_url(add_query_arg( array('em_tab'=>'emails')));
	}else{
	    $general_tab_link = $pages_tab_link = $formats_tab_link = $bookings_tab_link = $emails_tab_link = '';
	}
	$current_archetype = ($_REQUEST['post_type'] ?? '') === Archetypes::$event['cpt'] ? 'all' : Archetypes::get_current();
	?>
	<style type="text/css">
		.postbox h3 { cursor:pointer; }
		<?php foreach ( Archetypes::$types as $type => $archetype ) : ?>
		.wp-admin #em-options-page[data-archetype="<?php echo esc_attr( $type ); ?>"] .em-archetype-options > .em-archetype-option[data-archetype="<?php echo esc_attr( $type ); ?>"] {
			display: block;
			visibility: visible;
		}
		<?php endforeach; ?>
	</style>
	<div id="em-options-page" class="wrap <?php if(empty($tabs_enabled)) echo 'tabs-active' ?>" data-archetype="<?php echo $current_archetype; ?>" data-archetype-mode="<?php echo defined('EM_SETTINGS_ARCHETYPES_MERGED') && EM_SETTINGS_ARCHETYPES_MERGED ? 'merged' : 'single'; ?>">
		<h1 id="em-options-title"><?php _e ( 'Event Manager Options', 'events-manager'); ?></h1>
		<?php if ( !empty( Archetypes::$types ) ) : $i = 0; ?>
		<ul class="subsubsub em-archetype-tabs">
			<li class="archetype-view-all"><?php echo esc_html( sprintf( __('%s Options', 'events-manager'), __('Archetype', 'events-manager') ) ); ?>:
				<a data-archetype="all" class="current">
					<?php echo esc_html( sprintf( __('%s Options', 'events-manager'), __('All', 'events-manager') ) ); ?>
					<em><?php echo ' (' . esc_html__('Default', 'events-manager') . ' - ' . Archetypes::$event['label'] . ')'; ?></em>
				</a> |
			</li>
			<?php foreach ( Archetypes::$types as $type => $archetype ) : $i++ ?>
				<li class="archetype-view-<?php echo esc_attr($type); ?>">
					<a data-archetype="<?php echo esc_attr($type); ?>"><?php echo esc_attr($archetype['label']); ?></a>
					<?php if ( $i < count( Archetypes::$types ) ) : ?>|<?php endif; ?>
				</li>
			<?php endforeach; ?>
		</ul>
		<?php endif; ?>
		<h2 class="nav-tab-wrapper">
			<a href="<?php echo $general_tab_link; ?>#general" id="em-menu-general" class="nav-tab nav-tab-active"><?php _e('General','events-manager'); ?></a>
			<a href="<?php echo $pages_tab_link; ?>#pages" id="em-menu-pages" class="nav-tab"><?php _e('Pages','events-manager'); ?></a>
			<a href="<?php echo $formats_tab_link; ?>#formats" id="em-menu-formats" class="nav-tab"><?php _e('Formatting','events-manager'); ?></a>
			<?php if( get_option('dbem_rsvp_enabled') ): ?>
			<a href="<?php echo $bookings_tab_link; ?>#bookings" id="em-menu-bookings" class="nav-tab"><?php _e('Bookings','events-manager'); ?></a>
			<?php endif; ?>
			<a href="<?php echo $emails_tab_link; ?>#emails" id="em-menu-emails" class="nav-tab"><?php _e('Emails','events-manager'); ?></a>
			<?php
			$custom_tabs = apply_filters('em_options_page_tabs', array());
			foreach( $custom_tabs as $tab_key => $tab_name ){
				$tab_link = !empty($tabs_enabled) ? esc_url(add_query_arg( array('em_tab'=>$tab_key))) : '';
				$active_class = !empty($tabs_enabled) && !empty($_GET['em_tab']) && $_GET['em_tab'] == $tab_key ? 'nav-tab-active':'';
				echo "<a href='$tab_link#$tab_key' id='em-menu-$tab_key' class='nav-tab $active_class'>$tab_name</a>";
			}
			?>
		</h2>
		<div class="em-options-archetypes-description">
			<span class="em-icon em-icon-info"></span>
			<div>
				<p><?php esc_html_e('You are currently viewing options for an archetype. These can override the default options with the follwoing available options.', 'events-manager'); ?></p>
				<p><?php echo sprintf( esc_html__('If you want to edit general options for Events Manager, visit the main %s.', 'events-manager'), '<a href="'. em_admin_url( EM_POST_TYPE_EVENT ) .'&page=events-manager-options">'. esc_html__('Settings Page', 'events-manager') .'</a>' ); ?></p>
				<p><strong>Archetypes are in beta</strong> - if you have suggestions for useful overrideale options that aren't here, let us know in our support forums!</p>
			</div>
		</div>
		<form id="em-options-form" method="post" action="">
			<div class="metabox-holder">         
			<!-- // TODO Move style in css -->
			<div class='postbox-container' style='width: 99.5%'>
			<div id="">
			
			<?php
			if( !empty($tabs_enabled) ){
			    if( empty($_REQUEST['em_tab']) || $_REQUEST['em_tab'] == 'general' ){ 
			        include('settings/tabs/general.php');
			    }else{
        			if( $_REQUEST['em_tab'] == 'pages' ) include('settings/tabs/pages.php');
        			if( $_REQUEST['em_tab'] == 'formats' ) include('settings/tabs/formats.php');
        			if( get_option('dbem_rsvp_enabled') && $_REQUEST['em_tab'] == 'bookings'  ){
        			    include('settings/tabs/bookings.php');
        			}
        			if( $_REQUEST['em_tab'] == 'emails' ) include('settings/tabs/emails.php');
					if( array_key_exists($_REQUEST['em_tab'], $custom_tabs) ){
						?>
						<div class="em-menu-<?php echo esc_attr($_REQUEST['em_tab']) ?> em-menu-group">
						<?php do_action('em_options_page_tab_'. $_REQUEST['em_tab']); ?>
						</div>
						<?php
					}
			    }
			}else{
    			include('settings/tabs/general.php');
    			include('settings/tabs/pages.php');
    			include('settings/tabs/formats.php');
    			if( get_option('dbem_rsvp_enabled') ){
    			    include('settings/tabs/bookings.php');
    			}
    			include('settings/tabs/emails.php');
				foreach( $custom_tabs as $tab_key => $tab_name ){
					?>
					<div class="em-menu-<?php echo esc_attr($tab_key) ?> em-menu-group" style="display:none;">
						<?php do_action('em_options_page_tab_'. $tab_key); ?>
					</div>
					<?php
				}
			}
			?>
			
			<?php /*
			<div  class="postbox " >
			<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Debug Modes', 'events-manager'); ?> </span></h3>
			<div class="inside">
				<table class='form-table'>
					<?php
					em_options_radio_binary ( __( 'EM Debug Mode?', 'events-manager'), 'dbem_debug', __( 'Setting this to yes will display different content to admins for event pages and emails so you can see all the available placeholders and their values.', 'events-manager') );
					em_options_radio_binary ( __( 'WP Debug Mode?', 'events-manager'), 'dbem_wp_debug', __( 'This will turn WP_DEBUG mode on. Useful if you want to troubleshoot php errors without looking at your logs.', 'events-manager') );
					?>
				</table>
			</div> <!-- . inside -->
			</div> <!-- .postbox -->
			*/ ?>

			<p class="submit">
				<input type="submit" class="button-primary" name="Submit" value="<?php esc_attr_e( 'Save Changes', 'events-manager'); ?>">
				<input type="hidden" name="em-submitted" value="1">
				<input type="hidden" name="_wpnonce" value="<?php echo wp_create_nonce('events-manager-options'); ?>" <?php if ( $current_archetype !== 'all' ) : ?>disabled<?php endif; ?>>
			</p>  
			
			</div> <!-- .metabox-sortables -->
			</div> <!-- .postbox-container -->
			
			</div> <!-- .metabox-holder -->	
		</form>
	</div>
	<?php
}

/**
 * @depreacted
 * @use em_admin_option_box_uploads()
 * @return void
 */
function em_admin_option_box_image_sizes() {
	em_admin_option_box_uploads();
}
/**
 * Meta options box for image sizes. Shared in both MS and Normal options page, hence it's own function 
 */
function em_admin_option_box_uploads(){
	global $save_button;
	?>
	<div class="postbox" id="em-opt-uploads">
		<div class="handlediv" title="<?php esc_attr_e('Click to toggle', 'events-manager'); ?>"><br></div>
		<h3><span><?php esc_html_e('Uploads', 'events-manager'); ?></span></h3>
		<div class="inside">

			<!-- Visual Uploader -->
			<div class="em-opt-section">
				<table class="form-table">
					<?php em_options_radio_binary(__('Enable Visual Uploader', 'events-manager'), 'dbem_uploads_ui', __('Enable a modern visual uploader UI.', 'events-manager')); ?>
				</table>
			</div>

			<!-- Upload Limits -->
			<div class="em-opt-section">
				<h4><?php esc_html_e('Upload Limits', 'events-manager'); ?></h4>
				<table class="form-table">
					<?php
					em_options_input_text(__('Maximum File Size', 'events-manager'), 'dbem_uploads_max_file_size', __('The maximum size in bytes per uploaded file.', 'events-manager') . ' ' . sprintf(__(' Maximum size permitted by WordPress is %s.', 'events-manager'), '<code>' . wp_max_upload_size() . '</code>'));
					em_options_input_text(__('Maximum Files Per Upload', 'events-manager'), 'dbem_uploads_max_files', __('The maximum number of files a user can upload at once. Leave blank for unlimited.', 'events-manager'));
					em_options_radio_binary(__('Allow Multiple Uploads', 'events-manager'), 'dbem_uploads_allow_multiple', __('Enable multiple file uploads by default.', 'events-manager'));
					em_options_select(
						__('File Type', 'events-manager'),
						'dbem_uploads_type',
						[
							'' => __('Any Type', 'events-manager'),
							'image' => __('Image', 'events-manager'),
							'document' => __('Document', 'events-manager'),
							'spreadsheet' => __('Spreadsheet', 'events-manager'),
						],
						__('Restrict uploads to a specific type of file. Leave as "Any Type" to allow all.', 'events-manager')
					);
					em_options_input_text(
						__('Allowed Extensions', 'events-manager'),
						'dbem_uploads_extensions',
						sprintf( __('Comma-separated list of allowed file extensions: %s. Leave blank to allow any.', 'events-manager'), '<code>' . implode( ', ', array_keys(EM\Uploads\Uploader::$supported_file_types) ) . '</code>') .'<br>' . __('If File Type is also set, only these extensions within the permitted File Type will be permitted.', 'events-manager')
					);
					?>
				</table>
			</div>

			<!-- Image Dimensions -->
			<div class="em-opt-section">
				<h4><?php esc_html_e('Image Dimensions', 'events-manager'); ?></h4>
				<table class="form-table">
					<?php
					em_options_input_text(__('Maximum Width (px)', 'events-manager'), 'dbem_image_max_width', __('The maximum width an uploaded image can have. Larger images will be rejected. Leave blank to allow any size.', 'events-manager'));
					em_options_input_text(__('Maximum Height (px)', 'events-manager'), 'dbem_image_max_height', __('The maximum height an uploaded image can have. Larger images will be rejected. Leave blank to allow any size.', 'events-manager'));
					em_options_input_text(__('Minimum Width (px)', 'events-manager'), 'dbem_image_min_width', __('The minimum width an uploaded image can have. Smaller images will be rejected. Leave blank to allow any size.', 'events-manager'));
					em_options_input_text(__('Minimum Height (px)', 'events-manager'), 'dbem_image_min_height', __('The minimum height an uploaded image can have. Smaller images will be rejected. Leave blank to allow any size.', 'events-manager'));
					em_options_input_text ( __( 'Maximum size (bytes)', 'events-manager'), 'dbem_image_max_size', __( "The maximum allowed size for images uploaded, in bytes", 'events-manager') . '. ' . sprintf(__(' Maximum size permitted by WordPress is %s.', 'events-manager'), '<code>' . wp_max_upload_size() . '</code>') );
					?>
				</table>
			</div>

			<?php echo $save_button; ?>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	<?php
}

/**
 * Meta options box for email settings. Shared in both MS and Normal options page, hence it's own function 
 */
function em_admin_option_box_email(){
	global $save_button;
	$current_user = get_user_by('id', get_current_user_id());
	?>
	<div  class="postbox "  id="em-opt-email-settings">
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Email Settings', 'events-manager'); ?></span></h3>
	<div class="inside em-email-form">
		<p class="em-email-settings-check em-boxheader">
			<em><?php _e('Before you save your changes, you can quickly send yourself a test email by clicking this button.','events-manager'); ?>
			<?php echo sprintf(__('A test email will be sent to your account email - %s','events-manager'), $current_user->user_email . ' <a href="'.admin_url( 'profile.php' ).'">'.__('edit','events-manager').'</a>'); ?></em><br />
			<input type="button" id="em-admin-check-email" class="button-secondary" value="<?php esc_attr_e('Test Email Settings','events-manager'); ?>" />
			<input type="hidden" name="_check_email_nonce" value="<?php echo wp_create_nonce('check_email'); ?>" />
			<span id="em-email-settings-check-status"></span>
		</p>
		<table class="form-table">
			<?php
			em_options_input_text ( __( 'Notification sender name', 'events-manager'), 'dbem_mail_sender_name', __( "Insert the display name of the notification sender.", 'events-manager') );
			em_options_input_text ( __( 'Notification sender address', 'events-manager'), 'dbem_mail_sender_address', __( "Insert the address of the notification sender.", 'events-manager') );
			em_options_select ( __( 'Mail sending method', 'events-manager'), 'dbem_rsvp_mail_send_method', array ('smtp' => 'SMTP', 'mail' => __( 'PHP mail function', 'events-manager'), 'sendmail' => 'Sendmail', 'qmail' => 'Qmail', 'wp_mail' => 'WP Mail' ), __( 'Select the method to send email notification.', 'events-manager') );
			em_options_radio_binary ( __( 'Send HTML Emails?', 'events-manager'), 'dbem_smtp_html', __( 'If set to yes, your emails will be sent in HTML format, otherwise plaintext.', 'events-manager').' '.__( 'Depending on server settings, some sending methods may ignore this settings.', 'events-manager') );
			em_options_radio_binary ( __( 'Add br tags to HTML emails?', 'events-manager'), 'dbem_smtp_html_br', __( 'If HTML emails are enabled, br tags will automatically be added for new lines.', 'events-manager') );
			?>
			<tbody class="em-email-settings-smtp">
				<?php
				em_options_input_text ( 'Mail sending port', 'dbem_rsvp_mail_port', __( "The port through which you e-mail notifications will be sent. Make sure the firewall doesn't block this port", 'events-manager') );
				em_options_radio_binary ( __( 'Use SMTP authentication?', 'events-manager'), 'dbem_rsvp_mail_SMTPAuth', __( 'SMTP authentication is often needed. If you use Gmail, make sure to set this parameter to Yes', 'events-manager') );
				em_options_select ( __( 'SMTP Encryption', 'events-manager'), 'dbem_smtp_encryption', array ('0' => __( 'None', 'events-manager'), 'ssl' => 'SSL', 'tls' => 'TLS' ), __( 'Encryption is always recommended if your SMTP server supports it. If your server supports TLS, this is also the most recommended method.', 'events-manager') );
				em_options_radio_binary ( __( 'AutoTLS', 'events-manager'), 'dbem_smtp_autotls', __( 'We recommend leaving this on unless you are experiencing issues configuring your email.', 'events-manager') );
				em_options_input_text ( 'SMTP host', 'dbem_smtp_host', __( "The SMTP host. Usually it corresponds to 'localhost'. If you use Gmail, set this value to 'tls://smtp.gmail.com:587'.", 'events-manager') );
				em_options_input_text ( __( 'SMTP username', 'events-manager'), 'dbem_smtp_username', __( "Insert the username to be used to access your SMTP server.", 'events-manager') );
				em_options_input_password ( __( 'SMTP password', 'events-manager'), "dbem_smtp_password", __( "Insert the password to be used to access your SMTP server", 'events-manager') );
				?>
			</tbody>
			<?php
			echo $save_button;
			?>
		</table>
		<script type="text/javascript" charset="utf-8">
			jQuery(document).ready(function($){
				$('#dbem_rsvp_mail_send_method_row select').on('change', function(){
					el = $(this);
					if( el.find(':selected').val() == 'smtp' ){
						$('.em-email-settings-smtp').show();
					}else{
						$('.em-email-settings-smtp').hide();
					}
				}).trigger('change');
				$('input#em-admin-check-email').on('click', function(e,el){
					var email_data = $('.em-email-form input, .em-email-form select').serialize();
					$.ajax({
						url: EM.ajaxurl,
						dataType: 'json',
						data: email_data+"&action=em_admin_test_email",
						success: function(data){
							if(data.result && data.message){
								$('#em-email-settings-check-status').css({'color':'green','display':'block'}).html(data.message);
							}else{
								var msg = (data.message) ? data.message:'Email not sent';
								$('#em-email-settings-check-status').css({'color':'red','display':'block'}).html(msg);
							}
						},
						error: function(){ $('#em-email-settings-check-status').css({'color':'red','display':'block'}).html('Server Error'); },
						beforeSend: function(){ $('input#em-admin-check-email').val('<?php _e('Checking...','events-manager') ?>'); },
						complete: function(){ $('input#em-admin-check-email').val('<?php _e('Test Email Settings','events-manager'); ?>');  }
					});
				});
			});
		</script>
	</div> <!-- . inside -->
	</div> <!-- .postbox --> 
	<?php
}

/**
 * Meta options box for user capabilities. Shared in both MS and Normal options page, hence it's own function 
 */
function em_admin_option_box_caps(){
	global $save_button, $wpdb;
	?>
	<div  class="postbox" id="em-opt-user-caps" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'User Capabilities', 'events-manager'); ?></span></h3>
	<div class="inside">
            <table class="form-table">
            <tr><td colspan="2" class="em-boxheader">
            	<p><strong><?php _e('Warning: Changing these values may result in exposing previously hidden information to all users.', 'events-manager')?></strong></p>
            	<p><em><?php _e('You can now give fine grained control with regards to what your users can do with events. Each user role can have perform different sets of actions.','events-manager'); ?></em></p>
            </td></tr>
			<?php
            global $wp_roles;
			$cap_docs = array(
				sprintf(__('%s Capabilities','events-manager'),__('Event','events-manager')) => array(
					/* Event Capabilities */
					'publish_events' => sprintf(__('Users can publish %s and skip any admin approval','events-manager'),__('events','events-manager')),
					'delete_others_events' => sprintf(__('User can delete other users %s','events-manager'),__('events','events-manager')),
					'edit_others_events' => sprintf(__('User can edit other users %s','events-manager'),__('events','events-manager')),
					'delete_events' => sprintf(__('User can delete their own %s','events-manager'),__('events','events-manager')),
					'edit_events' => sprintf(__('User can create and edit %s','events-manager'),__('events','events-manager')),
					'read_private_events' => sprintf(__('User can view private %s','events-manager'),__('events','events-manager')),
					/*'read_events' => sprintf(__('User can view %s','events-manager'),__('events','events-manager')),*/
				),
				sprintf(__('%s Capabilities','events-manager'),__('Recurring Event','events-manager')) => array(
					/* Recurring Event Capabilties */
					'publish_recurring_events' => sprintf(__('Users can publish %s and skip any admin approval','events-manager'),__('repeating events','events-manager')),
					'delete_others_recurring_events' => sprintf(__('User can delete other users %s','events-manager'),__('repeating events','events-manager')),
					'edit_others_recurring_events' => sprintf(__('User can edit other users %s','events-manager'),__('repeating events','events-manager')),
					'delete_recurring_events' => sprintf(__('User can delete their own %s','events-manager'),__('repeating events','events-manager')),
					'edit_recurring_events' => sprintf(__('User can create and edit %s','events-manager'),__('repeating events','events-manager'))
				),
				sprintf(__('%s Capabilities','events-manager'),__('Location','events-manager')) => array(
					/* Location Capabilities */
					'publish_locations' => sprintf(__('Users can publish %s and skip any admin approval','events-manager'),__('locations','events-manager')),
					'delete_others_locations' => sprintf(__('User can delete other users %s','events-manager'),__('locations','events-manager')),
					'edit_others_locations' => sprintf(__('User can edit other users %s','events-manager'),__('locations','events-manager')),
					'delete_locations' => sprintf(__('User can delete their own %s','events-manager'),__('locations','events-manager')),
					'edit_locations' => sprintf(__('User can create and edit %s','events-manager'),__('locations','events-manager')),
					'read_private_locations' => sprintf(__('User can view private %s','events-manager'),__('locations','events-manager')),
					'read_others_locations' => __('User can use other user locations for their events.','events-manager'),
					/*'read_locations' => sprintf(__('User can view %s','events-manager'),__('locations','events-manager')),*/
				),
				sprintf(__('%s Capabilities','events-manager'),__('Other','events-manager')) => array(
					/* Category Capabilities */
					'delete_event_categories' => sprintf(__('User can delete %s categories and tags.','events-manager'),__('event','events-manager')),
					'edit_event_categories' => sprintf(__('User can edit %s categories and tags.','events-manager'),__('event','events-manager')),
					/* Booking Capabilities */
					'manage_others_bookings' => __('User can manage other users individual bookings and event booking settings.','events-manager'),
					'manage_bookings' => __('User can use and manage bookings with their events.','events-manager'),
					'upload_event_images' => __('User can upload images along with their events and locations.','events-manager')
				)
			);
            ?>
            <?php 
        	if( is_multisite() && is_network_admin() ){
	            echo em_options_radio_binary(__('Apply global capabilities?','events-manager'), 'dbem_ms_global_caps', __('If set to yes the capabilities will be applied all your network blogs and you will not be able to set custom capabilities each blog. You can select no later and visit specific blog settings pages to add/remove capabilities.','events-manager') );
	        }
	        ?>
            <tr><td colspan="2">
	            <table class="em-caps-table" style="width:auto;" cellspacing="0" cellpadding="0">
					<thead>
						<tr>
							<td>&nbsp;</td>
							<?php 
							$odd = 0;
							foreach(array_keys($cap_docs) as $capability_group){
								?><th class="<?php echo ( !is_int($odd/2) ) ? 'odd':''; ?>"><?php echo $capability_group ?></th><?php
								$odd++;
							} 
							?>
						</tr>
					</thead>
					<tbody>
            			<?php foreach($wp_roles->role_objects as $role): ?>
	            		<tr>
	            			<td class="cap"><strong><?php echo $role->name; ?></strong></td>
							<?php 
							$odd = 0;
							foreach($cap_docs as $capability_group){
								?>
	            				<td class="<?php echo ( !is_int($odd/2) ) ? 'odd':''; ?>">
									<?php foreach($capability_group as $cap => $cap_help){ ?>
	            					<input type="checkbox" name="em_capabilities[<?php echo $role->name; ?>][<?php echo $cap ?>]" value="1" id="<?php echo $role->name.'_'.$cap; ?>" <?php echo $role->has_cap($cap) ? 'checked="checked"':''; ?> />
	            					&nbsp;<label for="<?php echo $role->name.'_'.$cap; ?>"><?php echo $cap; ?></label>&nbsp;<a href="#" title="<?php echo $cap_help; ?>">?</a>
	            					<br />
	            					<?php } ?>
	            				</td>
	            				<?php
								$odd++;
							} 
							?>
	            		</tr>
			            <?php endforeach; ?>
			        </tbody>
	            </table>
	        </td></tr>
	        <?php echo $save_button; ?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	<?php
}

function em_admin_option_box_uninstall(){
	global $save_button;
	if( is_multisite() ){
		$uninstall_url = admin_url().'network/admin.php?page=events-manager-options&action=uninstall&_wpnonce='.wp_create_nonce('em_uninstall_'.get_current_user_id().'_wpnonce');
		$reset_url = admin_url().'network/admin.php?page=events-manager-options&action=reset&_wpnonce='.wp_create_nonce('em_reset_'.get_current_user_id().'_wpnonce');
		$recheck_updates_url = admin_url().'network/admin.php?page=events-manager-options&action=recheck_updates&_wpnonce='.wp_create_nonce('em_recheck_updates_'.get_current_user_id().'_wpnonce');
		$cleanup_event_orphans_url = admin_url().'network/admin.php?page=events-manager-options&action=cleanup_event_orphans&_wpnonce='.wp_create_nonce('em_cleanup_event_orphans_'.get_current_user_id().'_wpnonce').'&blog='.get_main_site_id();
		$check_devs = admin_url().'network/admin.php?page=events-manager-options&action=check_devs&_wpnonce='.wp_create_nonce('em_check_devs_wpnonce');
		$export_settings_url = admin_url().'network/admin.php?page=events-manager-options&action=export_em_ms_settings&_wpnonce='.wp_create_nonce('export_em_ms_settings');
		$import_nonce = wp_create_nonce('import_em_ms_settings');
	}else{
		$uninstall_url = EM_ADMIN_URL.'&page=events-manager-options&action=uninstall&_wpnonce='.wp_create_nonce('em_uninstall_'.get_current_user_id().'_wpnonce');
		$reset_url = EM_ADMIN_URL.'&page=events-manager-options&action=reset&_wpnonce='.wp_create_nonce('em_reset_'.get_current_user_id().'_wpnonce');
		$recheck_updates_url = EM_ADMIN_URL.'&page=events-manager-options&action=recheck_updates&_wpnonce='.wp_create_nonce('em_recheck_updates_'.get_current_user_id().'_wpnonce');
		$cleanup_event_orphans_url= EM_ADMIN_URL.'&page=events-manager-options&action=cleanup_event_orphans&_wpnonce='.wp_create_nonce('em_cleanup_event_orphans_'.get_current_user_id().'_wpnonce');
		$check_devs = EM_ADMIN_URL.'&page=events-manager-options&action=check_devs&_wpnonce='.wp_create_nonce('em_check_devs_wpnonce');
		$export_settings_url = EM_ADMIN_URL.'&page=events-manager-options&action=export_em_settings&_wpnonce='.wp_create_nonce('export_em_settings');
		$import_nonce = wp_create_nonce('import_em_settings');
	}
	$reset_timezone_nonce = wp_create_nonce('reset_timezones');
	$options_data = get_option('dbem_data');  
	?>
	<div  class="postbox" id="em-opt-admin-tools" >
		<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Admin Tools', 'events-manager'); ?> (<?php _e ( 'Advanced', 'events-manager'); ?>)</span></h3>
		<div class="inside">
			
			<?php
			//update scripts that may need to run
			$blog_updates = is_multisite() ? array_merge(EM_Options::get('updates'), EM_Options::site_get('updates')) : EM_Options::get('updates');
			foreach( $blog_updates as $update => $update_data ){
				do_action('em_admin_update_settings_'.$update, $update_data);
			}
			?>

			<table class="form-table">
				<tr class="em-header"><td colspan="2">
					<h4><?php _e ( 'Shortcode HTML Entity Decoding', 'events-manager'); ?></h4>
					<p>
						<?php
							esc_html_e('Recent Events Manager updates have made security improvements to how events are output, specifically with Shortcodes. The result is that some shortcode created prior to these updates will be displayed as raw/escaped HTML rather than content.','events-manager');
						?>
					</p>
					<p>
						<?php
							esc_html_e('The following options will re-enable this behaviour. If you notice escaped content (raw HTML) displayed on your site, you can enable these temporarily whilst you fix the underlying issue.','events-manager');
						?>
					</p>
					<p style="font-weight:bold; color: red;">
						<?php
							echo sprintf( esc_html__('These options have security implications and are intended for transition! For more information, please see our %s.','events-manager'), '<a href="https://wp-events-plugin.com/documentation/advanced/security/shortcode-security/">'. esc_html__('documentation', 'events-manager') .'</a>');
						?>
					</p>
				</td></tr>
				<?php em_options_radio_binary ( __( 'Decode shortcode content?', 'events-manager'), 'dbem_shortcodes_decode_content', sprintf(esc_html__('Content supplied within shortcode tags like %s will be HTML entity-decoded.', 'events-manager'), '<code>[shortcode]content[/shortcode]</code>'), '', '#dbem_shortcodes_kses_decoded_content_row' ); ?>
				<?php em_options_radio_binary ( __( 'Sanitize shortcode content?', 'events-manager'), 'dbem_shortcodes_kses_decoded_content', esc_html__('HTML entity-decoded shortcode content will be sanitized after being decoded, we STRONGLY recommend leaving this enabled.', 'events-manager') ); ?>
				<?php em_options_radio_binary ( __( 'Allow format shortcode parameters?', 'events-manager'), 'dbem_shortcodes_allow_format_params', sprintf(esc_html__('%s parameters will be permitted in shortcode.', 'events-manager'), '<code>format</code> <code>format_header</code> <code>format_footer</code>'), '', '#dbem_shortcodes_decode_params_row' ); ?>
				<?php em_options_radio_binary ( __( 'Decode shortcode format parameters?', 'events-manager'), 'dbem_shortcodes_decode_params', esc_html__('Content supplied within shortcode tags and the %s parameters will be HTML entity-decoded and sanitized.', 'events-manager') ); ?>
			</table>
			
			<table class="form-table">
    		    <tr class="em-header"><td colspan="2">
        			<h4><?php _e ( 'Development Versions &amp; Updates', 'events-manager'); ?></h4>
        			<p><?php _e('We\'re always making improvements, adding features and fixing bugs between releases. We incrementally make these changes in between updates and make it available as a development version. You can download these manually, but we\'ve made it easy for you. <strong>Warning:</strong> Development versions are not always fully tested before release, use wisely!','events-manager'); ?></p>
    			</td></tr>
				<?php em_options_radio_binary ( __( 'Always check the latest stable version?', 'events-manager'), 'dbem_check_stable_version', sprintf( __('If enabled, Events Manager checks WordPress.org directly for the latest stable release rather than waiting for the staggered update rollout, which can take up to 24 hours. Releases found this way are shown for a manual update only and are never auto-installed, unless you define the %1$s constant. %2$s', 'events-manager'), '<code>EM_AUTO_UPDATES</code>', '<a href="https://wp-events-plugin.com/blog/2026/07/04/plugin-updating-recommendations/" target="_blank">'. esc_html__('Read more on our blog', 'events-manager') .'</a> &middot; <a href="https://wp-events-plugin.com/documentation/installation/latest-stable/" target="_blank">'. esc_html__('Documentation', 'events-manager') .'</a>' ) ); ?>
				<?php em_options_radio_binary ( __( 'Enable Dev Updates?', 'events-manager'), 'dbem_pro_dev_updates', __('If enabled, the latest dev version will always be checked instead of the latest stable version of the plugin.', 'events-manager') ); ?>
				<tr>
    			    <th style="text-align:right;"><a href="<?php echo $recheck_updates_url; ?>" class="button-secondary"><?php _e('Re-Check Updates','events-manager'); ?></a></th>
    			    <td><?php _e('Checks WordPress.org directly for the latest stable release, skipping the staggered rollout delay (which can take up to 24 hours). Any newer stable version will appear on your Plugins or Updates page for a manual update.','events-manager'); ?></td>
    			</tr>
    			<tr>
    			    <th style="text-align:right;"><a href="<?php echo $check_devs; ?>" class="button-secondary"><?php _e('Check Dev Versions','events-manager'); ?></a></th>
    			    <td><?php _e('If you would like to download a dev version, but just as a one-off, you can force a dev version check by clicking the button below. If there is one available, it should appear in your plugin updates page as a regular update.','events-manager'); ?></td>
				</tr>
			</table>
			
			<table class="form-table">
    		    <tr class="em-header"><td colspan="2">
        			<h4><?php esc_html_e( 'Import/Export Settings', 'events-manager'); ?></h4>
        			<?php if( is_multisite() && is_network_admin() ): ?>
        			<p><?php esc_html_e("Within the network admin area, only network-specific settings will be exported or imported. For individual site settings please visit the relevant site within your network.", 'events-manager'); ?></p>
        			<?php endif; ?>
    			</td></tr>
				<tr>
    			    <th style="text-align:right;">
    			    	<a href="#" class="button-secondary" id="em-admin-import-settings"><?php esc_html_e('Import Settings','events-manager'); ?></a>
    			    </th>
    			    <td>
    			    	<input type="file" name="import_settings_file" id="em-admin-import-settings-file" />
    			    	<p><em><?php echo esc_html(sprintf(__('Choose a settings file saved from a backup or another Events Manager installation and click the \'%s\' button.','events-manager'), __('Import Settings','events-manager'))); ?></em></p>
    			    </td>
					<script type="text/javascript" charset="utf-8">
						jQuery(document).ready(function($){
							$('a#em-admin-import-settings').on('click', function(e,el){
								var thisform = $(this).closest('form');
								thisform.find('input[type=text], textarea, select, input[type=radio], input[type=hidden]').prop('disabled', true);
								thisform.find('input[name=_wpnonce]').val('<?php echo esc_attr($import_nonce); ?>').prop('disabled', false);
								thisform.append($('<input type="hidden" name="action" value="<?php echo is_multisite() ? 'import_em_ms_settings':'import_em_settings'; ?>" />'));
								thisform.attr('enctype', 'multipart/form-data').submit();
							});
						});
					</script>
    			</tr>
    			<tr>
    			    <th style="text-align:right;">
    			    	<a href="<?php echo $export_settings_url; ?>" class="button-secondary"><?php esc_html_e('Export Settings','events-manager'); ?></a>
    			    </th>
    			    <td><p><?php esc_html_e('Export your Events Manager settings and restore them here or on another website running this plugin.','events-manager'); ?></p></td>
				</tr>
			</table>
			
			
			<table class="form-table">
    		    <tr class="em-header"><td colspan="2">
    		        <h4><?php esc_html_e( 'Database Cleanup', 'events-manager'); ?></h4>
    		    </td></tr>
				<tr>
    			    <th style="text-align:right;">
				        <a id="em-cleanup-orphans-button" href="<?php echo $cleanup_event_orphans_url; ?>"
				           class="button-secondary admin-tools-db-cleanup"><?php _e( 'Remove Orphaned Events', 'events-manager' ); ?></a>
			        </th>

					<td>
						<?php if ( is_multisite() ): ?>
							<select id="em-cleanup-blog-selector">
								<?php foreach ( get_sites() as $site ): ?>
									<option value="<?php echo $site->blog_id; ?>" <?php selected( $site->blog_id, get_main_site_id() ); ?>><?php echo $site->blogname; ?></option>
								<?php endforeach; ?>
							</select>
							<script>
								jQuery( document ).ready( function ( $ ) {
									$( '#em-cleanup-blog-selector' ).on( 'change', function () {
										let url = '<?php echo remove_query_arg( 'blog', $cleanup_event_orphans_url ); ?>';
										document.getElementById('em-cleanup-orphans-button').href = url + '&blog=' + $( this ).val();
									} );
								} );
							</script>
						<?php endif; ?>
						<p>
						<?php
						if ( !is_multisite() ) {
							global $wpdb;
							$sql = 'SELECT count(*) FROM ' . EM_EVENTS_TABLE . ' WHERE post_id > 0 AND post_id NOT IN (SELECT ID FROM ' . $wpdb->posts . ' WHERE post_type="' . EM_POST_TYPE_EVENT . '" OR post_type="event-recurring")';
							if ( EM_MS_GLOBAL ) {
								if ( is_main_site() ) {
									$sql .= $wpdb->prepare( ' AND (blog_id=%d or blog_id IS NULL)', get_current_blog_id() );
								} else {
									$sql .= $wpdb->prepare( ' AND blog_id=%d', get_current_blog_id() );
								}
							}
							$results = $wpdb->get_var( $sql );
							esc_html_e( 'Orphaned events may show on your event lists but not point to real event pages, and can be deleted.', 'events-manager' );
							echo ' ' . sprintf( esc_html__( '%d potentially orphaned events have been found.', 'events-manager' ), $results );
						} else {
							esc_html_e( 'Orphaned events may show on your event lists but not point to real event pages, and can be deleted.', 'events-manager' );
							echo '<br>';
							esc_html_e( 'Select a blog and click the button next to it to clean up that specific blog. You must clean up one blog at a time.', 'events-manager' );
						}
						?></p>
    			    </td>
    			</tr>
			</table>
			<script type="text/javascript">
				if( typeof EM == 'object' ){ EM.admin_db_cleanup_warning = '<?php echo esc_js(__('Are you sure you want to proceed? We recommend you back up your database first, just in case!', 'events-manager')); ?>'; }
			</script>
			
			<table class="form-table">
    		    <tr class="em-header"><td colspan="2">
    		        <h4><?php _e ( 'Reset Timezones', 'events-manager'); ?></h4>
					<?php if( is_multisite() && get_site_option('dbem_reset_timezone_multisite_progress', false) !== false ): ?>
					<p style="color:red;">
						<?php 
						echo sprintf( esc_html__('Your last attempt to reset all blogs to a certain timezone did not complete successfully. You can attempt to reset only those blogs that weren\'t completed by selecting your desired timezone again and then %s from the dropdowns below', 'events-manager'), '<code>'.esc_html__('Resume Previous Attempt (All Blogs)', 'events-manager').'</code>' ); 
						?>
					</p>
					<?php endif; ?>
				</td></tr>
    		    <tr>
    			    <th style="text-align:right;">
    			    	<a href="#" class="button-secondary" id="em-reset-event-timezones"><?php esc_html_e('Reset Event Timezones','events-manager'); ?></a>
    			    </th>
    			    <td>
    			    	<select name="timezone_reset_value" class="em-reset-event-timezones">
    			    		<?php 
    			    			if( is_multisite() ){
    			    				$timezone_default = 'none';
    			    				echo '<option value="default">'.__('Blog Default Timezone', 'events-manager').'</option>';
    			    			}else{
	    			    			$timezone_default = str_replace(' ', '', EM_DateTimeZone::create()->getName());
								}
							?>
    			    		<?php echo wp_timezone_choice($timezone_default); ?>
    			    	</select>
    			    	<?php if( is_multisite() ): ?>
    			    		<select name="timezone_reset_blog" class="em-reset-event-timezones">
    			    			<option value="0"><?php esc_html_e('Select a blog...', 'events-manager'); ?></option>
    			    			<option value="all"><?php esc_html_e('All Blogs', 'events-manager'); ?></option>
    			    			<?php if( is_multisite() && get_site_option('dbem_reset_timezone_multisite_progress', false) !== false ): ?>
    			    			<option value="all-resume"><?php esc_html_e('Resume Previous Attempt (All Blogs)', 'events-manager'); ?></option>
    			    			<?php endif; ?>
    			    			<?php
	    			    		foreach( get_sites() as $WP_Site){ /* @var WP_Site $WP_Site */
	    			    			echo '<option value="'.esc_attr($WP_Site->blog_id).'">'. esc_html($WP_Site->blogname) .'</option>';
	    			    		}
	    			    		?>
    			    		</select>
    			    	<?php endif; ?>
	    		        <p>
	    		        	<em><?php esc_html_e('Select a Timezone to reset all your blog events to.','events-manager'); ?></em><br />
	    		        	<em><strong><?php esc_html_e('WARNING! This cannot be undone and will overwrite all event timezones, you may want to back up your database first!','events-manager'); ?></strong></em>
	    		        </p>
    			    </td>
					<script type="text/javascript" charset="utf-8">
						jQuery(document).ready(function($){
							$('select[name="timezone_reset_value"]').on('change', function( e ){
								if( $(this).val() == '' ){
									$('a#em-reset-event-timezones').css({opacity:0.5, cursor:'default'});
								}else{
									$('a#em-reset-event-timezones').css({opacity:1, cursor:'pointer'});
								}
							}).trigger('change');
							$('a#em-reset-event-timezones').on('click', function(e,el){
								if( $('select[name="timezone_reset_value"]').val() == '' ) return false;
								var thisform = $(this).closest('form');
								thisform.find('input, textarea, select').prop('disabled', true);
								thisform.find('select.em-reset-event-timezones').prop('disabled', false);
								thisform.find('input[name=_wpnonce]').val('<?php echo esc_attr($reset_timezone_nonce); ?>').prop('disabled', false);
								thisform.append($('<input type="hidden" name="action" value="<?php echo is_multisite() ? 'reset_timezones':'reset_timezones'; ?>" />'));
								thisform.submit();
							});
						});
					</script>
    		    </td></tr>
			</table>

			<?php if ( get_option('dbem_repeating_enabled') ) : ?>
			<table class="form-table">
				<tr class="em-header"><td colspan="2">
						<h4><?php esc_html_e ( 'Convert and Deactivate Repeating Events', 'events-manager'); ?></h4>
						<p><?php esc_html_e('Click the button below to mass-convert all your repeating events into recurring events.','events-manager'); ?></p>
						<p>
							<?php
							$warning = esc_html__('This will delete all event recurrence posts/pages, and unify them into one URL. Any 404 pages resulting from these will automatically 302-redirect to the recurring event (which will be a new URL).', 'events-manager');
							echo $warning;
						?></p>
						<p style="color:firebrick; font-weight: bold;"><?php esc_html_e('We strongly suggest you back up your database before proceding with this action, it cannot be undone otherwise!', 'events-manager'); ?></p>
					</td></tr>
				<tr><td colspan="2">
						<?php
						$convert_url = esc_url( add_query_arg( ['action' => 'convert_repeating_to_recurrence', 'nonce' => 'x'] ) );
						$convert_nonce = wp_create_nonce('convert_repeating_to_recurrence_'. get_current_user_id());
						EM\Scripts_and_Styles::add_js_var('convert_recurring_warning', __('Are you sure you want to convert all repeating events into recurring events?', 'events-manager') . "\n\n" . __('WARNING: This action cannot be undone.', 'events-manager') . "\n\n"  . $warning);
						?>
						<a href="<?php echo esc_url($convert_url); ?>" class="button-secondary em-convert-recurrence-link" data-nonce="<?php echo esc_attr($convert_nonce); ?>"><?php esc_html_e('Convert ALL Repeating Events', 'events-manager'); ?></a>
					</td></tr>
			</table>
			<?php endif; ?>
			
			<table class="form-table">
    		    <tr class="em-header"><td colspan="2">
    		        <h4><?php _e ( 'Uninstall/Reset', 'events-manager'); ?></h4>
    		        <p><?php _e('Use the buttons below to uninstall Events Manager completely from your system or reset Events Manager to original settings and keep your event data.','events-manager'); ?></p>
    		    </td></tr>
    		    <tr><td colspan="2">
        			<a href="<?php echo $uninstall_url; ?>" class="button-secondary"><?php _e('Uninstall','events-manager'); ?></a>
        			<a href="<?php echo $reset_url; ?>" class="button-secondary"><?php _e('Reset','events-manager'); ?></a>
    		    </td></tr>
			</table>
			<?php do_action('em_options_page_panel_admin_tools'); ?>
			<?php echo $save_button; ?>
		</div>
	</div>
	<?php	
}
?>