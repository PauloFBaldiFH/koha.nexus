<?php
/**
 * Catches various option names and returns a network-wide option value instead of the individual blog option. Uses the magc __call function to catch unprecedented names.
 * @author marcus
 *
 */
class EM_MS_Globals {
	function __construct(){
		add_action( 'init', array(&$this, 'add_filters'), 1);
	}

	function add_filters(){
		foreach( $this->get_globals() as $global_option_name ){
			add_filter('pre_option_'.$global_option_name, array(&$this, 'pre_option_'.$global_option_name), 1,1);
			add_filter('pre_update_option_'.$global_option_name, array(&$this, 'pre_update_option_'.$global_option_name), 1,2);
			add_action('add_option_'.$global_option_name, array(&$this, 'add_option_'.$global_option_name), 1,1);
		}
		//if we're in MS Global mode, the categories option currently resides in the main blog, consider moving this to a network setting in the future
		if( EM_MS_GLOBAL ){
			add_filter('pre_option_dbem_categories_enabled', array(&$this, 'pre_option_dbem_categories_enabled'), 1,1);
		}
	}

	function get_globals(){
		$globals = array(
			// archetypes
			'dbem_ms_archetypes_enabled', 'dbem_ms_archetypes_mode', 'dbem_archetypes_rename_labels', 'dbem_archetypes_rename_slugs', 'dbem_archetypes_rename_cpts',
			//multisite settings
			'dbem_ms_global_table', 'dbem_ms_global_caps',
			'dbem_ms_global_events', 'dbem_ms_global_events_links','dbem_ms_events_slug',
			'dbem_ms_global_locations','dbem_ms_global_locations_links','dbem_ms_locations_slug','dbem_ms_mainblog_locations',
			//mail
			'dbem_rsvp_mail_port', 'dbem_mail_sender_address', 'dbem_smtp_password', 'dbem_smtp_username','dbem_smtp_host', 'dbem_mail_sender_name','dbem_smtp_html','dbem_smtp_html_br','dbem_smtp_host','dbem_rsvp_mail_send_method','dbem_rsvp_mail_SMTPAuth',
			//images
			'dbem_image_max_width','dbem_image_max_height','dbem_image_max_size','dbem_image_min_width', 'dbem_image_min_height',
			// uploads
			'dbem_uploads_ui', 'dbem_uploads_max_file_size', 'dbem_uploads_max_files', 'dbem_uploads_allow_multiple', 'dbem_uploads_type', 'dbem_uploads_extensions',
		);
		if( EM_MS_GLOBAL ){
			$globals[] = 'dbem_taxonomy_category_slug';
		}
		return apply_filters('em_ms_globals', $globals);
	}

	function __call($filter_name, $value){
		if( strstr($filter_name, 'pre_option_') !== false ){
			$return = get_site_option(str_replace('pre_option_','',$filter_name));
			return $return;
		}elseif( strstr($filter_name, 'pre_update_option_') !== false ){
			if( em_wp_is_super_admin() ){
				update_site_option(str_replace('pre_update_option_','',$filter_name), $value[0]);
			}
			return $value[1];
		}elseif( strstr($filter_name, 'add_option_') !== false ){
			if( em_wp_is_super_admin() ){
				update_site_option(str_replace('add_option_','',$filter_name),$value[0]);
			}
			delete_option(str_replace('pre_option_','',$filter_name));
			return;
		}
		return $value[0];
	}

	/**
	 * Returns the option of the main site in this network, this function should only be fired if in MS Global mode.
	 * @param int $value
	 * @return int
	 */
	function pre_option_dbem_categories_enabled($value){
		if( !is_main_site() ){ //only alter value if not on main site already
			$value = get_blog_option(get_current_site()->blog_id, 'dbem_categories_enabled') ? 1:0; //return a number since false will not circumvent pre_option_ filter
		}
		return $value;
	}
}
global $EM_MS_Globals;
$EM_MS_Globals = new EM_MS_Globals();