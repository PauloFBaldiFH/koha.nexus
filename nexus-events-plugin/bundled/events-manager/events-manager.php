<?php
/*
Plugin Name: Events Manager
Version: 7.4.13
Plugin URI: https://wp-events-plugin.com
Description: Event registration and booking management for WordPress. Recurring events, locations, webinars, google maps, rss, ical, booking registration and more!
Author: Pixelite
Author URI: https://pixelite.com
Text Domain: events-manager
License: GPLv2
*/
/*
Copyright (c) 2026, Marcus Sykes

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
*/

// Setting constants
use EM\Archetypes;

define('EM_VERSION', '7.4.13'); //self expanatory, although version currently may not correspond directly with published version number. until 6.0 we're stuck updating 5.999.x
define('EM_PRO_MIN_VERSION', '3.9'); //self expanatory
define('EM_PRO_MIN_VERSION_CRITICAL', '3.6.0.2'); //self expanatory
define('EM_FILE', __FILE__); //an absolute path to this directory
define('EM_DIR', dirname( __FILE__ )); //an absolute path to this directory
define('EM_DIR_URI', trailingslashit(plugins_url('',__FILE__))); //an absolute path to this directory
define('EM_SLUG', plugin_basename( __FILE__ )); //for updates

// AJAX now enabled by default, disable if you really want to (but why? it's so nice!)
if( !defined('EM_AJAX_SEARCH') ) define( 'EM_AJAX_SEARCH', true );
if( !defined('EM_AJAX') ) define( 'EM_AJAX', true );

/**
 * Whether the block editor (Gutenberg) is enabled for Events Manager post types.
 *
 * Defined here (rather than em-functions.php) so it's available before any of the
 * class includes below run — classes/em-archetypes.php calls Archetypes::init()
 * at include time and that path needs the helper. The legacy EM_GUTENBERG constant
 * takes precedence — defined true or false — so wp-config.php overrides keep
 * working. Otherwise we fall back to the dbem_editor option (radio on the General
 * settings tab), which defaults to 'classic' for upgraded installs and 'gutenberg'
 * for fresh installs.
 *
 * @return bool
 */
function em_use_block_editor() {
	if ( defined( 'EM_GUTENBERG' ) ) {
		return (bool) EM_GUTENBERG;
	}
	return get_option( 'dbem_editor', 'classic' ) === 'gutenberg';
}

if( !defined('EM_CONDITIONAL_RECURSIONS') ) define('EM_CONDITIONAL_RECURSIONS', get_option('dbem_conditional_recursions', 2)); //allows for conditional recursios to be nested, 2 recommended due to our default template formats

//EM_MS_GLOBAL
if( is_multisite() && get_site_option('dbem_ms_global_table') ){
	define('EM_MS_GLOBAL', true);
}else{
	define('EM_MS_GLOBAL',false);
}

/**
 * Gets an option from the WordPress options table, by default the option requested is directly retrieved via the WordPress get_option function.
 *
 * Options that can be customized on a per-archetype basis can override the filters in this function to provide archetype–specific functionality.
 *
 * The only caveat with the additional parameters is that the default option cannot be equal to an archetype name, unless the archetype name is also supplied as the third parameter.
 *
 * @param $option
 * @param mixed ...$args May consist of the default option value and then the archetype name, otherwise one or the other is supported.
 *
 * @return mixed|null
 */
function em_get_option ( $option, ...$args ) {
	if ( class_exists('\EM\Archetypes') ) {
		$value = \EM\Archetypes::get_option( $option, ...$args );
	} else {
		_doing_it_wrong( __FUNCTION__, __( 'Calling em_get_option() too early whilst EM\Archetypes class is not available.', 'events-manager' ), '7.1' );
		$value = get_option( $option );
	}
	return apply_filters( 'em_get_option', $value, $option, $args );
}

// DEBUG MODE - currently not public, not fully tested
if( !defined('WP_DEBUG') && get_option('dbem_wp_debug') ){
	define('WP_DEBUG',true);
}
function dbem_debug_mode(){
	if( !empty($_REQUEST['dbem_debug_off']) ){
		update_option('dbem_debug',0);
		wp_safe_redirect($_SERVER['HTTP_REFERER']);
	}
	if( current_user_can('activate_plugins') ){
		include_once('em-debug.php');
	}
}
//add_action('plugins_loaded', 'dbem_debug_mode');

// do requirements check
include( EM_DIR . '/classes/requirements-check.php' );
$requirements = new EM\Requirements_Check();
if( !$requirements->passes(false) ) return;
unset($requirements);

// INCLUDES
if( is_multisite() ){
	include( EM_DIR . '/classes/em-ms-globals.php' );
}
//Base classes
include( EM_DIR . '/classes/em-exception.php' );
include( EM_DIR . '/classes/em-options.php' );
include( EM_DIR . '/classes/em-utils.php' );
include( EM_DIR . '/classes/em-object.php' );
include( EM_DIR . '/classes/em-datetimezone.php' );
include( EM_DIR . '/classes/em-datetime.php' );
include( EM_DIR . '/classes/em-taxonomy-term.php' );
include( EM_DIR . '/classes/em-taxonomy-terms.php' );
include( EM_DIR . '/classes/em-taxonomy-frontend.php' );
include( EM_DIR . '/classes/uploads/em-uploads-api.php' );
include( EM_DIR . '/classes/uploads/em-uploads-uploader.php' );
//set up events as posts
include( EM_DIR . '/classes/em-archetypes.php' );
include( EM_DIR . '/classes/em-taxonomies.php' );

//include( EM_DIR . '/em-posts.php' );
//Template Tags & Template Logic
include( EM_DIR . '/em-actions.php' );
include( EM_DIR . '/em-events.php' );
include( EM_DIR . '/em-emails.php' );
include( EM_DIR . '/em-functions.php' );
include( EM_DIR . '/em-updates.php' );
include( EM_DIR . '/em-ical.php' );
include( EM_DIR . '/em-shortcode.php' );
include( EM_DIR . '/em-template-tags.php' );
include( EM_DIR . '/classes/consent/consent.php');
include( EM_DIR . '/classes/consent/privacy-consent.php');
include( EM_DIR . '/classes/consent/comms-consent.php');
include( EM_DIR . '/multilingual/em-ml.php' );
//Widgets
include( EM_DIR . '/widgets/em-events.php' );
if( get_option('dbem_locations_enabled') ){
	include( EM_DIR . '/widgets/em-locations.php' );
}
include( EM_DIR . '/widgets/em-calendar.php' );
//Gutenberg blocks + validation guard (registers blocks, REST field, editor JS)
include( EM_DIR . '/blocks/_bootstrap.php' );
//Event/Location editor: tab registry (EM\Editor\Tabs + Event/Location) + canvas/tabs/metaboxes layout controller
include( EM_DIR . '/classes/editor/em-editor.php' );
//Classes
include( EM_DIR . '/classes/em-list-table.php' );
include( EM_DIR . '/classes/em-booking.php' );
include( EM_DIR . '/classes/em-bookings.php' );
include( EM_DIR . '/classes/em-withdrawal.php' );
include( EM_DIR . '/classes/em-bookings-table.php' );
include( EM_DIR . '/classes/em-list-table-events-bookings.php' );
include( EM_DIR . '/classes/em-calendar.php' );
include( EM_DIR . '/classes/em-category.php' );
include( EM_DIR . '/classes/em-categories.php' );
include( EM_DIR . '/classes/em-categories-frontend.php' );
include( EM_DIR . '/classes/timeslots/timeranges.php' );
include( EM_DIR . '/classes/timeslots/event-timeranges.php' );
include( EM_DIR . '/classes/recurrences/recurrence-set.php' );
include( EM_DIR . '/classes/recurrences/recurrence-sets.php' );
include( EM_DIR . '/classes/em-event.php' );
include( EM_DIR . '/classes/event-locations/em-event-locations.php' );
include( EM_DIR . '/classes/em-event-post.php' );
include( EM_DIR . '/classes/em-events.php' );
include( EM_DIR . '/classes/em-location.php' );
include( EM_DIR . '/classes/em-location-post.php' );
include( EM_DIR . '/classes/em-locations.php' );
include( EM_DIR . '/classes/em-mailer.php' );
include( EM_DIR . '/classes/em-notices.php' );
include( EM_DIR . '/classes/em-people.php' );
include( EM_DIR . '/classes/em-person.php' );
include( EM_DIR . '/classes/em-permalinks.php' );
include( EM_DIR . '/classes/em-tag.php' );
include( EM_DIR . '/classes/em-tags.php' );
include( EM_DIR . '/classes/em-tags-frontend.php' );
include( EM_DIR . '/classes/em-ticket-booking.php' );
include( EM_DIR . '/classes/em-ticket.php' );
include( EM_DIR . '/classes/em-tickets-bookings.php' );
include( EM_DIR . '/classes/em-ticket-bookings.php' );
include( EM_DIR . '/classes/em-tickets.php' );
include( EM_DIR . '/classes/em-phone.php' );
// EM's API bootstrap loads the bundled OAuth library, registers REST routes, abilities, and the MCP server — see EM\API\API::init().
include( EM_DIR . '/classes/api/em-api.php' );
// Push-notification framework for the mobile app: a generic type registry (bookings, events, …) that dispatches to Expo and registers its own /app/* REST routes under the API namespace — see EM\Notifications\Notifications::init(). Loaded after the API so it can reuse the same namespace and auth layer.
include( EM_DIR . '/classes/notifications/em-notifications.php' );


//Admin / API context
if( is_admin() || ( defined('REST_REQUEST') && REST_REQUEST ) ){
	include_once( EM_DIR . '/classes/em-admin-notices.php' );
	include( EM_DIR . '/admin/em-admin.php' );
	include( EM_DIR . '/admin/em-admin-modals.php' );
	include( EM_DIR . '/admin/em-bookings.php' );
	include( EM_DIR . '/admin/dashboard.php' );
	include( EM_DIR . '/admin/em-docs.php' );
	include( EM_DIR . '/admin/em-help.php' );
	include( EM_DIR . '/admin/em-options.php' );
	include( EM_DIR . '/admin/em-data-privacy.php' );
	if( is_multisite() ){
		include( EM_DIR . '/admin/em-ms-options.php' );
	}
	//post/taxonomy controllers
	include( EM_DIR . '/classes/em-event-post-admin.php' );
	include( EM_DIR . '/classes/em-event-posts-admin.php' );
	include( EM_DIR . '/classes/em-location-post-admin.php' );
	include( EM_DIR . '/classes/em-location-posts-admin.php' );
	include( EM_DIR . '/classes/em-taxonomy-admin.php' );
	include( EM_DIR . '/classes/em-categories-admin.php' );
	include( EM_DIR . '/classes/em-tags-admin.php' );
}
include( EM_DIR . '/classes/em-scripts-and-styles.php' );

/* Only load the component if BuddyPress is loaded and initialized. */
function bp_em_init() {
	if ( version_compare( BP_VERSION, '1.3', '>' ) ){
		require( EM_DIR . '/buddypress/bp-em-core.php' );
	}
}
add_action( 'bp_include', 'bp_em_init' );

//Table names
global $wpdb;
if( EM_MS_GLOBAL ){
	$prefix = $wpdb->base_prefix;
}else{
	$prefix = $wpdb->prefix;
}
	define('EM_EVENTS_TABLE',$prefix.'em_events'); //TABLE NAME
	define('EM_EVENT_RECURRENCES_TABLE',$prefix.'em_event_recurrences'); //TABLE NAME
	define('EM_TIMERANGES_TABLE', $prefix . 'em_timeranges');
	define('EM_EVENT_TIMESLOTS_TABLE', $prefix . 'em_event_timeslots');
	define('EM_TICKETS_TABLE', $prefix.'em_tickets'); //TABLE NAME
	define('EM_TICKETS_BOOKINGS_TABLE', $prefix.'em_tickets_bookings'); //TABLE NAME
	define('EM_META_TABLE',$prefix.'em_meta'); //TABLE NAME
	define('EM_LOCATIONS_TABLE',$prefix.'em_locations'); //TABLE NAME
	define('EM_BOOKINGS_TABLE',$prefix.'em_bookings'); //TABLE NAME
	define('EM_BOOKINGS_META_TABLE',$prefix.'em_bookings_meta'); //TABLE NAME
	define('EM_TICKETS_BOOKINGS_META_TABLE',$prefix.'em_tickets_bookings_meta'); //TABLE NAME

//Backward compatability for old images stored in < EM 5
if( EM_MS_GLOBAL ){
	//If in ms recurrence mode, we are getting the default wp-content/uploads folder
	$upload_dir = array(
		'basedir' => WP_CONTENT_DIR.'/uploads/',
		'baseurl' => WP_CONTENT_URL.'/uploads/'
	);
}else{
	$upload_dir = wp_upload_dir();
}
if( file_exists($upload_dir['basedir'].'/locations-pics' ) ){
	define("EM_IMAGE_UPLOAD_DIR", $upload_dir['basedir']."/locations-pics/");
	define("EM_IMAGE_UPLOAD_URI", $upload_dir['baseurl']."/locations-pics/");
	define("EM_IMAGE_DS",'-');
}else{
	define("EM_IMAGE_UPLOAD_DIR", $upload_dir['basedir']."/events-manager/");
	define("EM_IMAGE_UPLOAD_URI", $upload_dir['baseurl']."/events-manager/");
	define("EM_IMAGE_DS",'/');
}

/**
 * Provides a way to proactively load groups of files, once, when needed.
 * @since 5.9.7.4
 */
class EM_Loader {
	public static $oauth = false;
	
	public static function oauth(){
		require_once('classes/em-oauth/oauth-api.php');
		add_action('em_enqueue_admin_styles', function(){
			wp_enqueue_style('events-manager-oauth-admin', plugins_url('includes/css/events-manager-oauth-admin.css',__FILE__), array(), EM_VERSION);
		});
		self::$oauth = true;
	}
}

class EM_Scripts_and_Styles extends EM\Scripts_and_Styles {}
function em_enqueue_public(){ EM_Scripts_and_Styles::public_enqueue(); } //In case ppl used this somewhere

/**
 * Perform plugins_loaded actions
 */
function em_plugins_loaded(){
	//WPFC Integration
	if( defined('WPFC_VERSION') ){
		function load_em_wpfc_plugin(){
			if( !function_exists('wpfc_em_init') ) include( EM_DIR . '/em-wpfc.php' );	
		}
		add_action('init', 'load_em_wpfc_plugin', 200);
	}
	//bbPress
	if( class_exists( 'bbPress' ) ) include( EM_DIR . '/em-bbpress.php' );
	// other integrations
	if( class_exists('\Thrive\Automator\Admin') ){
		include( EM_DIR . '/integrations/thrive-automator/events-manager-thrive-automator.php' );
	}
	// duplicate posts - small so we just include it
	include( EM_DIR . '/integrations/duplicate-post-plugins/duplicate-post-plugins.php' );
	// fix Pro timeslot support by disabling timeslots if not the high enough version
	if ( defined('EMP_VERSION')  && version_compare( EMP_VERSION, '3.7.2', '<' ) ) {
		add_filter('pre_option_dbem_event_timeranges_enabled', '__return_zero');
	}
}
add_filter('plugins_loaded','em_plugins_loaded');

/**
 * Perform init actions
 */
function em_init(){
	//Capabilities
	global $em_capabilities_array;
	$em_capabilities_array = apply_filters('em_capabilities_array', array(
		/* Booking Capabilities */
		'manage_others_bookings' => sprintf(__('You do not have permission to manage others %s','events-manager'),__('bookings','events-manager')),
		'manage_bookings' => sprintf(__('You do not have permission to manage %s','events-manager'),__('bookings','events-manager')),
		/* Event Capabilities */
		'publish_events' => sprintf(__('You do not have permission to publish %s','events-manager'),__('events','events-manager')),
		'delete_others_events' => sprintf(__('You do not have permission to delete others %s','events-manager'),__('events','events-manager')),
		'delete_events' => sprintf(__('You do not have permission to delete %s','events-manager'),__('events','events-manager')),
		'edit_others_events' => sprintf(__('You do not have permission to edit others %s','events-manager'),__('events','events-manager')),
		'edit_events' => sprintf(__('You do not have permission to edit %s','events-manager'),__('events','events-manager')),
		'read_private_events' => sprintf(__('You cannot read private %s','events-manager'),__('events','events-manager')),
		/*'read_events' => sprintf(__('You cannot view %s','events-manager'),__('events','events-manager')),*/
		/* Recurring Event Capabilties */
		'publish_recurring_events' => sprintf(__('You do not have permission to publish %s','events-manager'),__('recurring events','events-manager')),
		'delete_others_recurring_events' => sprintf(__('You do not have permission to delete others %s','events-manager'),__('recurring events','events-manager')),
		'delete_recurring_events' => sprintf(__('You do not have permission to delete %s','events-manager'),__('recurring events','events-manager')),
		'edit_others_recurring_events' => sprintf(__('You do not have permission to edit others %s','events-manager'),__('recurring events','events-manager')),
		'edit_recurring_events' => sprintf(__('You do not have permission to edit %s','events-manager'),__('recurring events','events-manager')),
		/* Location Capabilities */
		'publish_locations' => sprintf(__('You do not have permission to publish %s','events-manager'),__('locations','events-manager')),
		'delete_others_locations' => sprintf(__('You do not have permission to delete others %s','events-manager'),__('locations','events-manager')),
		'delete_locations' => sprintf(__('You do not have permission to delete %s','events-manager'),__('locations','events-manager')),
		'edit_others_locations' => sprintf(__('You do not have permission to edit others %s','events-manager'),__('locations','events-manager')),
		'edit_locations' => sprintf(__('You do not have permission to edit %s','events-manager'),__('locations','events-manager')),
		'read_private_locations' => sprintf(__('You cannot read private %s','events-manager'),__('locations','events-manager')),
		'read_others_locations' => sprintf(__('You cannot view others %s','events-manager'),__('locations','events-manager')),
		/*'read_locations' => sprintf(__('You cannot view %s','events-manager'),__('locations','events-manager')),*/
		/* Category Capabilities */
		'delete_event_categories' => sprintf(__('You do not have permission to delete %s','events-manager'),__('categories','events-manager')),
		'edit_event_categories' => sprintf(__('You do not have permission to edit %s','events-manager'),__('categories','events-manager')),
		/* Upload Capabilities */
		'upload_event_images' => __('You do not have permission to upload images','events-manager')
	));
	//Hard Links
	global $EM_Mailer, $wp_rewrite;
	if( get_option("dbem_events_page") > 0 ){
		define('EM_URI', get_permalink(get_option("dbem_events_page"))); //PAGE URI OF EM
	}else{
		if( $wp_rewrite->using_permalinks() ){
			define('EM_URI', trailingslashit(home_url()). EM_POST_TYPE_EVENT_SLUG.'/'); //PAGE URI OF EM
		}else{
			define('EM_URI', trailingslashit(home_url()).'?post_type='.EM_POST_TYPE_EVENT); //PAGE URI OF EM
		}
	}
	if( $wp_rewrite->using_permalinks() ){
		$rss_url = trailingslashit(home_url()). EM_POST_TYPE_EVENT_SLUG.'/feed/';
		define('EM_RSS_URI', $rss_url); //RSS PAGE URI via CPT archives page
	}else{
		$rss_url = em_add_get_params(home_url(), array('post_type'=>EM_POST_TYPE_EVENT, 'feed'=>'rss2'));
		define('EM_RSS_URI', $rss_url); //RSS PAGE URI
	}
	$EM_Mailer = new EM_Mailer();
	//add custom functions.php file
	locate_template('plugins/events-manager/functions.php', true);
	//fire a loaded hook, most plugins should consider going through here to load anything EM related
	if ( current_user_can('manage_options') ) {
		em_upgrade_plugin_check();
	}
	do_action('events_manager_loaded');
}
add_filter('init','em_init',1);

/**
 * This function will load an event into the global $EM_Event variable during page initialization, provided an event_id is given in the url via GET or POST.
 * global $EM_Recurrences also holds global array of recurrence objects when loaded in this instance for performance
 * All functions (admin and public) can now work off this object rather than it around via arguments.
 * @return null
 */
function em_load_event(){
	global $EM_Event, $EM_Recurrences, $EM_Location, $EM_Person, $EM_Booking, $EM_Category, $EM_Ticket, $current_user;
	if( !defined('EM_LOADED') ){
		$EM_Recurrences = array();
		if( isset( $_REQUEST['event_id'] ) && ( is_numeric($_REQUEST['event_id']) || preg_match('/^\d+:\d+$/', $_REQUEST['event_id']) ) && !is_object($EM_Event) ){
			$EM_Event = em_get_event( $_REQUEST['event_id'] );
		}elseif( isset($_REQUEST['post']) && Archetypes::is_event( $_REQUEST['post'] ) ){
			$EM_Event = em_get_event($_REQUEST['post'], 'post_id');
		}elseif ( !empty($_REQUEST['event_slug']) && EM_MS_GLOBAL && is_main_site() && !get_site_option('dbem_ms_global_events_links')) {
			// single event page for a subsite event being shown on the main blog
			global $wpdb;
			$matches = array();
			if( preg_match('/\-([0-9]+)$/', $_REQUEST['event_slug'], $matches) ){
				$event_id = $matches[1];
			}else{
				$query = $wpdb->prepare('SELECT event_id FROM '.EM_EVENTS_TABLE.' WHERE event_slug = %s AND blog_id != %d', $_REQUEST['event_slug'], get_current_blog_id());
				$event_id = $wpdb->get_var($query);
			}
			$EM_Event = em_get_event($event_id);
		}
		if( isset($_REQUEST['location_id']) && is_numeric($_REQUEST['location_id']) && !is_object($EM_Location) ){
			$EM_Location = new EM_Location( absint($_REQUEST['location_id']) );
		}elseif( isset($_REQUEST['post']) && get_post_type($_REQUEST['post']) == EM_POST_TYPE_LOCATION ){
			$EM_Location = em_get_location($_REQUEST['post'], 'post_id');
		}elseif ( !empty($_REQUEST['location_slug']) && EM_MS_GLOBAL && is_main_site() && !get_site_option('dbem_ms_global_locations_links')) {
			// single event page for a subsite event being shown on the main blog
			global $wpdb;
			$matches = array();
			if( preg_match('/\-([0-9]+)$/', $_REQUEST['location_slug'], $matches) ){
				$location_id = $matches[1];
			}else{
				$query = $wpdb->prepare('SELECT location_id FROM '.EM_LOCATIONS_TABLE." WHERE location_slug = %s AND blog_id != %d", $_REQUEST['location_slug'], get_current_blog_id());
				$location_id = $wpdb->get_var($query);
			}
			$EM_Location = em_get_location($location_id);
		}
		if( is_user_logged_in() || (!empty($_REQUEST['person_id']) && is_numeric($_REQUEST['person_id'])) ){
			//make the request id take priority, this shouldn't make it into unwanted objects if they use theobj::get_person().
			if( !empty($_REQUEST['person_id']) ){
				$EM_Person = new EM_Person( absint($_REQUEST['person_id']) );
			}else{
				$EM_Person = new EM_Person( get_current_user_id() );
			}
		}
		if( isset($_REQUEST['booking_id']) && is_numeric($_REQUEST['booking_id']) && !is_object($_REQUEST['booking_id']) ){
			$EM_Booking = em_get_booking( absint($_REQUEST['booking_id']) );
		}
		if( isset($_REQUEST['category_id']) && is_numeric($_REQUEST['category_id']) && !is_object($_REQUEST['category_id']) ){
			$EM_Category = new EM_Category( absint($_REQUEST['category_id']) );
		}elseif( isset($_REQUEST['category_slug']) && !is_object($EM_Category) ){
			$EM_Category = new EM_Category( $_REQUEST['category_slug'] );
		}
		if( isset($_REQUEST['ticket_id']) && is_numeric($_REQUEST['ticket_id']) && !is_object($_REQUEST['ticket_id']) ){
			$EM_Ticket = new EM_Ticket( absint($_REQUEST['ticket_id']) );
		}
		
		// check if we're on a bookings page, and if so load the dashboard graph
		if ( is_page( get_option('dbem_edit_bookings_page') ) && get_option('dbem_booking_charts_frontend') ) {
			include('admin/dashboard.php');
		}
		
		define('EM_LOADED',true);
	}
}
add_action('template_redirect', 'em_load_event', 1);
if( is_admin() ){ add_action('init', 'em_load_event', 2); }

/**
 * Works much like <a href="http://codex.wordpress.org/Function_Reference/locate_template" target="_blank">locate_template</a>, except it takes a string instead of an array of templates, we only need to load one.
 * @param string $template_name
 * @param boolean $load
 * @uses locate_template()
 * @return string
 */
function em_locate_template( $template_name, $load=false, $the_args = array() ) {
	//First we check if there are overriding tempates in the child or parent theme
	$located = locate_template(array('plugins/events-manager/'.$template_name));
	if( !$located ){
		// now check the wp-content/plugin-templates/events-manager/ folder
		if( file_exists(WP_CONTENT_DIR.'/plugin-templates/events-manager/'.$template_name) ){
			$located = WP_CONTENT_DIR.'/plugin-templates/events-manager/'.$template_name;
		}else{
			// finally get the plugin from EM if no others exist
			$located = apply_filters('em_locate_template_default', $located, $template_name, $load, $the_args);
			if ( !$located && file_exists(EM_DIR.'/templates/'.$template_name) ) {
				$located = EM_DIR.'/templates/'.$template_name;
			}
		}
	}
	$located = apply_filters('em_locate_template', $located, $template_name, $load, $the_args);
	if( $located && $load ){
		$the_args = apply_filters('em_locate_template_args_'.$template_name, $the_args, $located);
		if( is_array($the_args) ) extract($the_args);
		do_action('em_template_before_'.$template_name, $the_args);
		include($located);
		do_action('em_template_after_'.$template_name, $the_args);
	}
	return $located;
}

function em_get_template_components_classes( $component ){
	$component_classes = array('em-' . $component);
	$show_theme_class = 1;
	$show_theme_class_admin = 1;
	switch( $component ){
		// Calendar
		case 'calendar':
		case 'calendar-preview':
			$show_theme_class = get_option('dbem_css_calendar');
			break;
		// Lists
		case 'events-list':
			array_unshift($component_classes, 'em-list');
			$show_theme_class = get_option('dbem_css_evlist');
			break;
		case 'events-grid':
			array_unshift($component_classes, 'em-grid');
			$show_theme_class = get_option('dbem_css_evlist');
			break;
		case 'categories-list':
			array_unshift($component_classes, 'em-list');
			$show_theme_class = get_option('dbem_css_catlist');
			break;
		case 'tags-list':
			array_unshift($component_classes, 'em-list');
			$show_theme_class = get_option('dbem_css_taglist');
			break;
		case 'locations-list':
			array_unshift($component_classes, 'em-list');
			$show_theme_class = get_option('dbem_css_loclist');
			break;
		case 'locations-grid':
			array_unshift($component_classes, 'em-grid');
			$show_theme_class = get_option('dbem_css_loclist');
			break;
		case 'event-booking-form':
			$show_theme_class = get_option('dbem_css_rsvp');
			if( get_option('dbem_bookings_form_hide_dynamic') ){
				array_unshift($component_classes, 'em-hide-dynamic');
			}
			break;
		case 'view-container':
			$show_theme_class = 2; // not a theme wrapper, just a view wrapper
			break;
		// Single Items
		case 'event-single':
			array_unshift($component_classes, 'em-item', 'em-item-single', 'em-event');
			$show_theme_class = get_option('dbem_css_event');
			break;
		case 'location-single':
			array_unshift($component_classes, 'em-item', 'em-item-single', 'em-location');
			$show_theme_class = get_option('dbem_css_location');
			break;
		case 'category-single':
			array_unshift($component_classes, 'em-item', 'em-item-single', 'em-taxonomy', 'em-taxonomy-single', 'em-category');
			$show_theme_class = get_option('dbem_css_category');
			break;
		case 'tag-single':
			array_unshift($component_classes, 'em-item', 'em-item-single', 'em-taxonomy', 'em-taxonomy-single', 'em-tag');
			$show_theme_class = get_option('dbem_css_tag');
			break;
		// Widgets/Blocks
		case 'events-widget':
		case 'locations-widget':
			array_unshift($component_classes, 'em-list-widget');
			break;
		// Admin Areas
		case 'list-table':
		case 'bookings-table':
		case 'events-bookings-table':
			$component_classes[] = 'has-filter';
			$show_theme_class = true;
			$show_theme_class_admin = 0;
			break;
		case 'bookings-admin':
			$show_theme_class = get_option('dbem_css_rsvpadmin');
			$show_theme_class_admin = 0;
			break;
		case 'event-editor':
			array_unshift($component_classes, 'em-event-admin-editor'); // backwards compat
		case 'location-editor':
		case 'locations-admin':
		case 'events-admin':
			$show_theme_class = get_option('dbem_css_editors');
			break;
		// Others
		case 'search':
			$show_theme_class = get_option('dbem_css_search'); // we don't need pixelbones
			break;
		case 'my-bookings': // the 'my bookings' page for visitors, not admins
			$show_theme_class = get_option('dbem_css_myrsvp'); // we don't need pixelbones
			break;
	}
	return array('classes' => $component_classes, 'use_theme' => absint($show_theme_class), 'use_theme_admin' => $show_theme_class_admin );
}

/**
 * Returns a class list array according to the supplied component and subcomponent, which can be hooked into or altered according to EM settings page.
 * The point of this function is to decide whether this component should include base (.em) and theme (.pixelite) clases to further style the component.
 * Additionally, you can add one or more subcomponents which will also include their related classes but include base/theme classes if the main compononent allows this.
 * This sort of scenario could be useful if displaying a list of events within another component, such as a calendar, and you want to style the list but use our calendar styles.
 *
 * @param string|false $component           The component being displayed, such as events-list, single-event, etc. and these are usually repeated into the classlist with an em- prefix
 * @param string|array $subcomponents       Additional CSS components to be added which will get prefixed with em-
 * @param string|array $just_subcomponent   If you want to display subcomponent clases, but also decide whether to show the base classes ('em' and 'pixelbones') based on the main component, set to true and main component classes will not be returned
 * @return array
 */
function em_get_template_classes($component, $subcomponents = array(), $just_subcomponent = false ){
	// get base components
	if( $component ) {
		$component_data = em_get_template_components_classes($component);
	}else{
		// we assume here that we're looking here for subcomponent classes, nothing more
		$component_data = array('classes' => array(), 'use_theme' => 0, 'use_theme_admin' => 0);
	}
	// get additional components
	$subcomponent_classes = $subcomponents_data = array();
	if( !empty($subcomponents) ){
		if( !is_array($subcomponents) ) $subcomponents = str_replace(' ', '', explode(',', $subcomponents));
		foreach($subcomponents as $subcomponent ){
			// merge classes here as we go, store into data variable for the filter further down
			$subcomponent_data = em_get_template_components_classes( $subcomponent );
			$subcomponents_data[$subcomponent] = $subcomponent_data;
			$subcomponent_classes = array_merge( $subcomponent_classes, $subcomponents_data[$subcomponent]['classes'] );
		}
	}
	// add base classes (if applicable)
	$base_classes = array();
	$theme = 'pixelbones';
	if( is_admin() && (!defined('EM_DOING_AJAX') || !EM_DOING_AJAX) ){
		$base_classes = array('em');
		if( !empty($component_data['use_theme_admin']) ){
			$base_classes[] = $theme;
		}
	}elseif( get_option('dbem_css') ) {
		if( $component_data['use_theme'] ){
			$base_classes[] = 'em'; // our base class
			if( $component_data['use_theme'] !== 2 && get_option('dbem_css_theme') ) {
				$base_classes[] = $theme;
			} // if greater than 1 then it won't include pixelbones
		}
	}
	if( $just_subcomponent ){
		$classes = array_unique(array_merge($base_classes, $subcomponent_classes));
	} else {
		$classes = array_unique(array_merge($base_classes, $component_data['classes'], $subcomponent_classes));
	}
	return apply_filters('em_get_template_classes', $classes, $component, $subcomponents, $just_subcomponent, $component_data, $subcomponents_data);
}

/* Want to overpower our styling? See these examples:
add_filter('em_get_template_classes', '__return_empty_array');
*/
/*
add_filter('em_get_template_classes', function( $classes, $component, $subcomponents, $just_subcomponent, $component_data, $subcomponents_data ){
	$component_classes[] = 'em';
	return $component_classes;
}, 1, 5);
*/

/**
 * @see em_get_template_classes()
 * @param $component
 * @param $theme
 * @return void
 */
function em_template_classes( $component, $additional_classes = array(), $theme = null ){
	$classes = em_get_template_classes($component, $additional_classes, $theme);
	echo esc_attr(implode(' ', $classes));
}

/**
 * Quick class to dynamically catch wp_options that are EM formats and need replacing with template files.
 * Since the options filter doesn't have a catchall filter, we send all filters to the __call function and figure out the option that way.
 * @method event_list_item_format()
 */
class EM_Formats {
	/**
	 * @var array array of previously loaded formats for faster reference. much like get_option does
	 */
	public static $loaded_formats = array();
	/**
	 * @var string Name of filter for other plugins to override, should be overriden also by extending class
	 */
	protected static $formats_filter = 'em_formats_filter';
	
	public static function init(){
		add_action( 'events_manager_loaded', 'EM_Formats::add_filters');
	}
	public static function add_filters( $get_all = false ){
		//you can hook into this filter and activate the format options you want to override by supplying the wp option names in an array, just like in the database.
		if( is_admin() && !empty($_REQUEST['page']) && $_REQUEST['page'] == 'events-manager-options' ) return; // exit on setting pages to avoid content wiping
		$formats = apply_filters(static::$formats_filter, static::get_default_formats($get_all));
		foreach( $formats as $format_name ){
			add_filter('pre_option_'.$format_name, 'EM_Formats::'. $format_name, 1,1);
		}
	}
	
	public static function remove_filters( $get_all = false ){
		$formats = apply_filters(static::$formats_filter, static::get_default_formats($get_all));
		foreach( $formats as $format_name ){
			remove_filter('pre_option_'.$format_name, 'EM_Formats::'. $format_name, 1);
		}
	}
	
	/**
	 * Intercepts the pre_option_ hooks and check if we have a php file format verion, if so that content is supplied.
	 * @param string $name
	 * @param string[] $args
	 * @return string
	 */
	public static function __callStatic($name, $args ){
		if( !empty(static::$loaded_formats[$name]) ){
			return static::$loaded_formats[$name];
		} // cached already
		$value = empty($args) || !isset($args[0]) ? '' : $args[0];
		$filename = preg_replace('/^dbem_/', '', $name);
		$format = static::locate_template('formats/'.$filename.'.php');
		if( $format ){
			ob_start();
			include($format);
			$value = ob_get_clean();
		}
		static::$loaded_formats[$name] = $value;
		return $value;
	}
	
	public static function locate_template($template){
		return em_locate_template( $template );
	}
	
	public static function get_email_format( $format_name ){
		$format_name = preg_replace('/^dbem_/', '', $format_name);
		if( !preg_match('/\.php$/', $format_name) ){
			$format_name .= '.php';
		}
		$template =  em_locate_template('emails/formats/'.$format_name);
		if( $template ) {
			ob_start();
			include($template);
			return ob_get_clean();
		}
		return '';
	}
	
	/**
	 * @return mixed|void
	 */
	public static function get_formatting_modes_map(){
		$formatting_modes_map = array (
			'events-list' => array(
				'dbem_event_list_item_format_header',
				'dbem_event_list_item_format',
				'dbem_event_list_item_format_footer',
			),
			'events-grid' => array(
				'dbem_event_grid_item_format_header',
				'dbem_event_grid_item_format',
				'dbem_event_grid_item_format_footer',
			),
			'event-single' => array(
				'dbem_single_event_format',
			),
			'event-excerpt' => array(
				'dbem_event_excerpt_format',
				'dbem_event_excerpt_alt_format',
			),
			'calendar-previews' => array(
				'dbem_calendar_preview_modal_event_format',
				'dbem_calendar_preview_modal_date_format',
				'dbem_calendar_preview_tooltip_event_format',
			),
			'locations-list' => array(
				'dbem_location_list_item_format_header',
				'dbem_location_list_item_format',
				'dbem_location_list_item_format_footer',
			),
			'locations-grid' => array(
				'dbem_location_grid_item_format_header',
				'dbem_location_grid_item_format',
				'dbem_location_grid_item_format_footer',
			),
			'location-single' => array(
				'dbem_single_location_format',
			),
			'location-excerpt' => array(
				'dbem_location_excerpt_format',
				'dbem_location_excerpt_alt_format',
			),
			'location-event-lists' => array(
				'dbem_location_event_list_item_header_format',
				'dbem_location_event_list_item_format',
				'dbem_location_event_list_item_footer_format'
			),
			'categories-list' => array(
				'dbem_categories_list_item_format_header',
				'dbem_categories_list_item_format',
				'dbem_categories_list_item_format_footer',
			),
			'category-single' => array(
				'dbem_category_page_format',
			),
			'category-events-list' => array(
				'dbem_category_event_list_item_header_format',
				'dbem_category_event_list_item_format',
				'dbem_category_event_list_item_footer_format',
			),
			'tags-list' => array(
				'dbem_tags_list_item_format_header',
				'dbem_tags_list_item_format',
				'dbem_tags_list_item_format_footer',
			),
			'tag-single' => array(
				'dbem_tag_page_format',
			),
			'tag-events-list' => array(
				'dbem_tag_event_list_item_header_format',
				'dbem_tag_event_list_item_format',
				'dbem_tag_event_list_item_footer_format',
			),
			'maps' => array(
				'dbem_map_text_format',
				'dbem_location_baloon_format',
			),
		);
		return apply_filters('em_formats_formatting_modes_map', $formatting_modes_map);
	}
	
	public static function get_default_formats( $get_all = false ){
		$default_formats = array();
		$formatting_modes_map = static::get_formatting_modes_map();
		if( get_option('dbem_advanced_formatting') == 0  || $get_all == true ){
			// load all formats from files
			foreach( $formatting_modes_map as $k => $formats ){
				$default_formats = array_merge($default_formats, $formats);
			}
		}elseif( get_option('dbem_advanced_formatting') == 1 ){
			// go through settings and see what needs loading from files and which don't
			$formatting_modes = get_option('dbem_advanced_formatting_modes');
			foreach( $formatting_modes as $mode => $status ){
				if( !$status && !empty($formatting_modes_map[$mode]) ){
					$default_formats = array_merge($default_formats, $formatting_modes_map[$mode]);
				}
			}
		} // if set to 2 (or something else) we're loading everything direct from settings
		return $default_formats;
	}

	/**
	 * Formats a request may select by name, as id => option name. Empty by default; nothing is exposed to requests
	 * until it is registered here:
	 *
	 *     add_filter('em_registered_formats', function( $formats ){
	 *         $formats['front-page-format'] = 'mytheme_front_page_format';
	 *         return $formats;
	 *     });
	 *
	 * @return array<string,string>
	 */
	public static function get_registered_formats(){
		return apply_filters('em_registered_formats', array());
	}

	/**
	 * Resolves a format id to the format stored against it, false if the id isn't registered. Never falls back to the
	 * id itself, or an injected format would pass straight through.
	 *
	 * @param string $format_id
	 * @return string|false
	 */
	public static function get_registered_format( $format_id ){
		if( !is_string($format_id) || !preg_match('/^[a-zA-Z0-9_-]+$/', $format_id) ) return false;
		$registered_formats = static::get_registered_formats();
		if( !isset($registered_formats[$format_id]) ) return false;
		$format = em_get_option( $registered_formats[$format_id] );
		if( !is_string($format) || $format === '' ) return false;
		return apply_filters('em_registered_format', $format, $format_id);
	}
}
EM_Formats::init();

/**
 * Catches the event rss feed requests
 */
function em_rss() {
	global $post, $wp_query, $wpdb;
	//check if we're meant to override the feeds - we only check EM's taxonomies because we can't guarantee (well, not without more coding) that it's not being used by other CPTs
	if( is_feed() && $wp_query->get(EM_TAXONOMY_CATEGORY) ){
		//event category feed
		$args = array('category' => $wp_query->get(EM_TAXONOMY_CATEGORY));
		$args['event_archetype'] = false;
	}elseif( is_feed() && $wp_query->get(EM_TAXONOMY_TAG) ){
		//event tag feed
		$args = array('tag' => $wp_query->get(EM_TAXONOMY_TAG));
		$args['event_archetype'] = false;
	}elseif( is_feed() && $wp_query->get('post_type') == EM_POST_TYPE_LOCATION && $wp_query->get(EM_POST_TYPE_LOCATION) ){
		//location feeds
		$location_id = $wpdb->get_var($wpdb->prepare('SELECT location_id FROM '.EM_LOCATIONS_TABLE." WHERE location_slug=%s AND location_status=1 LIMIT 1", $wp_query->get(EM_POST_TYPE_LOCATION)));
		if( !empty($location_id) ){
			$args = array('location'=> $location_id);
		}
	}elseif( is_feed() && EM\Archetypes::is_valid_cpt( $wp_query->get('post_type') ) ) {
		//events feed - show it all
		$args = array();
		$args['event_archetype'] = $wp_query->get('post_type');
	}
	if( isset($args) ){
		$wp_query->is_feed = true; //make is_feed() return true AIO SEO fix
		ob_start();
		em_locate_template('templates/rss.php', true, array('args'=>$args));
		echo apply_filters('em_rss', ob_get_clean());
		die();
	}
}
add_action ( 'template_redirect', 'em_rss' );

/**
 * Monitors event saves and changes the rss pubdate and a last modified option so it's current
 * @param boolean $result
 * @return boolean
 */
function em_modified_monitor($result){
	if($result){
	    update_option('em_last_modified', time());
	}
	return $result;
}
add_filter('em_event_save', 'em_modified_monitor', 10,1);
add_filter('em_location_save', 'em_modified_monitor', 10,1);

function em_admin_bar_mod($wp_admin_bar){
	$wp_admin_bar->add_menu( array(
		'parent' => 'network-admin',
		'id'     => 'network-admin-em',
		'title'  => __( 'Events Manager','events-manager'),
		'href'   => network_admin_url('admin.php?page=events-manager-options'),
	) );
}
add_action( 'admin_bar_menu', 'em_admin_bar_mod', 21 );

function em_delete_blog( $blog_id ){
	global $wpdb;
	$prefix = $wpdb->get_blog_prefix($blog_id);
	$wpdb->query('DROP TABLE '.$prefix.'em_events');
	$wpdb->query('DROP TABLE '.$prefix.'em_bookings');
	$wpdb->query('DROP TABLE '.$prefix.'em_locations');
	$wpdb->query('DROP TABLE '.$prefix.'em_tickets');
	$wpdb->query('DROP TABLE '.$prefix.'em_tickets_bookings');
	$wpdb->query('DROP TABLE '.$prefix.'em_meta');
	//per-site in plain multisite; under MS Global these are shared and any per-site copy is a leftover from before 7.4.6, so dropping by this site's prefix is right in both modes
	$wpdb->query('DROP TABLE IF EXISTS '.$prefix.'em_timeranges');
	$wpdb->query('DROP TABLE IF EXISTS '.$prefix.'em_event_timeslots');
	//these are per-site only in plain multisite; under MS Global they are base-prefix/shared and must never be dropped per-blog
	if( !EM_MS_GLOBAL ){
		$wpdb->query('DROP TABLE IF EXISTS '.$prefix.'em_event_recurrences');
		$wpdb->query('DROP TABLE IF EXISTS '.$prefix.'em_bookings_meta');
		$wpdb->query('DROP TABLE IF EXISTS '.$prefix.'em_tickets_bookings_meta');
	}
	//delete events if MS Global
	if( EM_MS_GLOBAL ){
	    EM_Events::delete(array('limit'=>0, 'blog'=>$blog_id));
	    EM_Locations::delete(array('limit'=>0, 'blog'=>$blog_id));
	}
}
add_action('delete_blog','em_delete_blog');

function em_activate() {
	update_option('dbem_flush_needed',1);
}
register_activation_hook( __FILE__,'em_activate');

/* Creating the wp_events table to store event data*/
function em_deactivate() {
	global $wp_rewrite;
   	$wp_rewrite->flush_rules();
}
register_deactivation_hook( __FILE__,'em_deactivate');

/**
 * Fail-safe compatibility checking of EM Pro 
 */
function em_check_pro_compatability(){
	if( defined('EMP_VERSION') && EMP_VERSION < EM_PRO_MIN_VERSION_CRITICAL && (!defined('EMP_DISABLE_CRITICAL_WARNINGS') || !EMP_DISABLE_CRITICAL_WARNINGS) ){
		include( EM_DIR . '/em-pro-compatibility.php' );
	}
}
add_action('plugins_loaded','em_check_pro_compatability', 1);

function events_manager_plugin_loaded(){
	do_action('events_manager_plugin_loaded');
}
add_action('plugins_loaded','events_manager_plugin_loaded');

// Upgrade/Install logic
$v6 = EM_Options::get('v6', null);
if( $v6 !== null ){
	include( EM_DIR . '/v6-migrate.php' );
}

function em_upgrade_plugin_check() {
	if( version_compare(EM_VERSION, get_option('dbem_version', 0), '>') || (is_multisite() && !EM_MS_GLOBAL && get_option('em_ms_global_install')) ){
		require_once( dirname(__FILE__).'/em-install.php');
		em_install();
	}
}
add_action( 'em_upgrade_plugin_check', 'em_upgrade_plugin_check' );

function em_schedule_update_check( $upgrader, $options ) {
	wp_schedule_single_event( time(), 'em_upgrade_plugin_check' );
}
add_action( 'upgrader_process_complete', 'em_schedule_update_check', 10, 2 );
?>