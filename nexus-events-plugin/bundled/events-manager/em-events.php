<?php
/*
 * This file contains the event related hooks in the front end, as well as some event template tags
 */

use EM\Archetypes;

/**
 * Filters for page content and if an event replaces it with the relevant event data.
 * @param $data
 * @return string
 */
function em_content($page_content) {
	global $post, $EM_Event, $EM_Location, $EM_Notices;
	$in_the_loop = !(defined('EM_CHECK_THE_LOOP') && EM_CHECK_THE_LOOP) || in_the_loop(); // check if we're in the loop... since this may break some themes, we're introducing it as a constant for themes that cause issues vs. breaking themes that already work.
	if( empty($post) || empty($post->ID) || !$in_the_loop ) return $page_content; //fix for any other plugins calling the_content outside the loop
	$event_page_ids = Archetypes::get_option_values('dbem_events_page');
	$locations_page_id = get_option( 'dbem_locations_page' );
	$categories_page_id = get_option( 'dbem_categories_page' );
	$tags_page_id = get_option( 'dbem_tags_page' );
	$edit_events_page_ids = Archetypes::get_option_values( 'dbem_edit_events_page' );
	$edit_locations_page_id = get_option( 'dbem_edit_locations_page' );
	$edit_bookings_page_ids = Archetypes::get_option_values( 'dbem_edit_bookings_page' );
	$my_bookings_page_id = get_option( 'dbem_my_bookings_page' );
	//general defaults
	$args = array(				
		'owner' => false,
		'pagination' => 1,
		'id' => rand(100, getrandmax()),
	);
	$args['ajax'] = isset($args['ajax']) ? $args['ajax']:EM_AJAX_SEARCH;
	if( !post_password_required() && in_array($post->ID, [ $locations_page_id, $categories_page_id, $edit_locations_page_id, $my_bookings_page_id, $tags_page_id, ...array_values($edit_bookings_page_ids), ...array_values($edit_events_page_ids), ...array_values($event_page_ids) ] ) ){
		get_post();
		$content = apply_filters('em_content_pre', '', $page_content);
		if( empty($content) ){
			ob_start();
			if ( in_array( $post->ID, $event_page_ids ) && $post->ID != 0 ) {
				// get the archetype
				$args['event_archetype'] = array_flip( $event_page_ids )[$post->ID];
				Archetypes::set_current( $args['event_archetype'] );
				if ( !empty($_REQUEST['calendar_day']) ) {
					//Events for a specific day
					$args['id'] = 2; // for easier reference in customizations
					$args = EM_Events::get_post_search( $args );
					$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_events_default_limit');
					em_locate_template('templates/calendar-day.php',true, array('args'=>$args));
				}elseif ( is_object($EM_Event)) {
					$args['id'] = 6; // for easier reference in customizations
					em_locate_template('templates/event-single.php',true, array('args'=>$args));	
				}else{
					// Multiple events page
					$args['orderby'] = em_get_option('dbem_events_default_orderby');
					$args['order'] = em_get_option('dbem_events_default_order');
					if (em_get_option ( 'dbem_display_calendar_in_events_page' )){
						$args['id'] = 1; // for easier reference in customizations
						$args['long_events'] = 1;
						em_locate_template('templates/events-calendar.php',true, array('args'=>$args));
					}else{
						//Intercept search request, if defined
						if( !empty($_REQUEST['action']) && ($_REQUEST['action'] == 'search_events' || $_REQUEST['action'] == 'search_events_grouped') ){
							$args = EM_Events::get_post_search( $args );
						} elseif( !empty($_COOKIE['em_search_events']) ) {
							$cookie_args = json_decode(base64_decode($_COOKIE['em_search_events']), true);
							if( is_array($cookie_args) ) $args = EM_Events::get_post_search( $args, false, $cookie_args );
						}
						$args['id'] = 1; // for easier reference in customizations
						if( empty($args['scope']) ){
						    $args['scope'] = em_get_option('dbem_events_page_scope');
						}
						$args['view'] = em_get_option('dbem_search_form_view');
						$args['has_search'] = em_get_option('dbem_events_page_search_form');
						$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_events_default_limit');
						em_output_events_view( $args );
					}
				}
				Archetypes::revert_current();
			}elseif( $post->ID == $locations_page_id && $locations_page_id != 0 ){
				$args['orderby'] = em_get_option('dbem_locations_default_orderby');
				$args['order'] = em_get_option('dbem_locations_default_order');
				$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_locations_default_limit');
				$args['id'] = 3; // for easier reference in customizations
				if( EM_MS_GLOBAL && is_object($EM_Location) ){
					em_locate_template('templates/location-single.php',true, array('args'=>$args));
				}else{
					//Intercept search request, if defined
					if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'search_locations' ){
						$args = EM_Locations::get_post_search( $args );
					}
					$args['has_search'] = em_get_option('dbem_locations_page_search_form');
					em_output_locations_view( $args );
				}
			}elseif( $post->ID == $categories_page_id && $categories_page_id != 0 ){
				$args['id'] = 4; // for easier reference in customizations
				$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_categories_default_limit');
				if( !empty($args['ajax']) ){ echo '<div class="em-search-ajax">'; } //AJAX wrapper open
				em_locate_template('templates/categories-list.php',true, array('args'=>$args));
				if( !empty($args['ajax']) ) echo "</div>"; //AJAX wrapper close
			}elseif( $post->ID == $tags_page_id && $tags_page_id != 0 ){
				$args['id'] = 5; // for easier reference in customizations
				$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_tags_default_limit');
				if( !empty($args['ajax']) ){ echo '<div class="em-search-ajax">'; } //AJAX wrapper open
				em_locate_template('templates/tags-list.php',true, array('args'=>$args));
				if( !empty($args['ajax']) ) echo "</div>"; //AJAX wrapper close
			}elseif( in_array($post->ID, $edit_events_page_ids) && $post->ID != 0 ){
				$args['event_archetype'] = array_flip( $edit_events_page_ids )[$post->ID];
				Archetypes::set_current( $args['event_archetype'] );
				em_events_admin();
				Archetypes::revert_current();
			}elseif( $post->ID == $edit_locations_page_id && $edit_locations_page_id != 0 ){
				em_locations_admin();
			}elseif( $post->ID == $my_bookings_page_id && $my_bookings_page_id != 0 ){
				em_my_bookings();
			}elseif( in_array($post->ID, $edit_bookings_page_ids) && $post->ID != 0 ){
				$args['event_archetype'] = array_flip( $edit_bookings_page_ids )[$post->ID];
				Archetypes::set_current( $args['event_archetype'] );
				em_bookings_admin();
				Archetypes::revert_current();
			}
			$content = ob_get_clean();
			//If disable rewrite flag is on, then we need to add a placeholder here
			if( em_get_option('dbem_disable_title_rewrites') == 1 ){
				$content = str_replace('#_PAGETITLE', em_content_page_title(''),em_get_option('dbem_title_html')) . $content;
			}
			//Now, we either replace CONTENTS or just replace the whole page
			if( preg_match('/CONTENTS/', $page_content) ){
				$content = str_replace('CONTENTS',$content,$page_content);
			}
			if(get_option('dbem_credits')){
				$content .= '<p style="color:#999; font-size:11px;">Powered by <a href="https://wp-events-plugin.com" style="color:#999;" target="_blank">Events Manager</a></p>';
			}
		}
		return apply_filters('em_content', '<div id="em-wrapper">'.$content.'</div>');
	}
	return $page_content;
}
//add the_content filter AFTER wp_head functions have run, so we don't interfere with plugins like WP SEO and other meta-related plugins that make use of the_content for our pages
function em_add_content_filter(){
	// only add this one
	if( !has_action('the_content', 'em_content') ) {
		add_filter('the_content', 'em_content');
	}
}
function em_remove_content_filter(){
	remove_filter('the_content', 'em_content');
}
//remember that this gets removed by taxonomy pages showing a single taxonomy page, so careful if changing the priority
add_action('wp_head', 'em_add_content_filter', 1000);
add_action('wp_head', 'em_remove_content_filter', 1);
/**
 * @return void
 */
function add_content_filter_template_include( $template ){
	// add the_content earlier than above in FSE situations
	if( preg_match('/'.WPINC.'\/template-canvas.php$/', $template ) ){
		em_add_content_filter();
	}
	return $template;
}
add_action('template_include', 'add_content_filter_template_include');

/**
 * Filter for titles when on event pages
 * @param $data
 * @return string
 */
function em_content_page_title($original_content, $id = null) {
	global $EM_Event, $EM_Location, $EM_Category, $wp_query, $post;
	$in_the_loop = !(defined('EM_CHECK_THE_LOOP') && EM_CHECK_THE_LOOP) || in_the_loop(); // check if we're in the loop... since this may break some themes, we're introducing it as a constant for themes that cause issues vs. breaking themes that already work.
	if( empty($post) || empty($post->ID) || !$in_the_loop ) return $original_content; //fix for any other plugins calling the_content outside the loop
	if ($id && $id !== $post->ID) return $original_content;
	
	$event_page_ids = Archetypes::get_option_values('dbem_events_page');
	$locations_page_id = get_option( 'dbem_locations_page' );
	$edit_events_page_ids = Archetypes::get_option_values( 'dbem_edit_events_page' );
	$edit_locations_page_id = get_option( 'dbem_edit_locations_page' );
	$edit_bookings_page_ids = Archetypes::get_option_values( 'dbem_edit_bookings_page' );
	if( !empty($post->ID) && in_array($post->ID, [ $locations_page_id, $edit_locations_page_id, ...array_values($edit_bookings_page_ids), ...array_values($edit_events_page_ids), ...array_values($event_page_ids) ] ) ){
		//override the titles with this filter if needed, preventing the following code from being run
	    $content = apply_filters('em_content_page_title_pre', '', $original_content);
		if( empty($content) ){
			$content =  $original_content; //leave untouched by default
			if ( in_array( $post->ID, $event_page_ids ) && $post->ID != 0 ) {
				$event_archetype = array_flip( $event_page_ids )[$post->ID];
				Archetypes::set_current( $event_archetype );
				if ( !empty( $_REQUEST['calendar_day'] ) ) {
					$events = EM_Events::get(array('limit'=>2,'scope'=>$_REQUEST['calendar_day'],'owner'=>false));
					if ( count($events) != 1 || em_get_option('dbem_display_calendar_day_single') == 1 ) {
						//We only support dates for the calendar day list title, so we do a simple filter for the supplied calendar_day
						$content = em_get_option ('dbem_list_date_title');
						preg_match_all("/#[A-Za-z0-9]+/", $content, $placeholders);
						foreach($placeholders[0] as $placeholder) {
							// matches all PHP date and time placeholders
							if (preg_match('/^#[dDjlNSwzWFmMntLoYyaABgGhHisueIOPTZcrU]$/', $placeholder)) {
								$content = str_replace($placeholder, mysql2date(ltrim($placeholder, "#"), $_REQUEST['calendar_day']),$content );
							}
						}
					}else{
						$event = array_shift($events);
						$content =  $event->output( $event->get_option('dbem_event_page_title_format') );
					}
				}elseif ( EM_MS_GLOBAL && is_object($EM_Event) && !em_get_option('dbem_ms_global_events_links') ) {
					// single event page
					$content =  $EM_Event->output ( $EM_Event->get_option ( 'dbem_event_page_title_format' ) );
				}
				Archetypes::revert_current();
			}elseif( $post->ID == $locations_page_id ){
				if( EM_MS_GLOBAL && is_object($EM_Location) && em_get_option('dbem_ms_global_locations_links') ){
					$content = $EM_Location->output(em_get_option( 'dbem_location_page_title_format' ));
				}
			}elseif( in_array($post->ID, $edit_events_page_ids) && $post->ID != 0 ){
				$event_archetype = array_flip( $edit_events_page_ids )[$post->ID];
				Archetypes::set_current( $event_archetype );
				if( !empty($_REQUEST['action']) && $_REQUEST['action'] = 'edit' ){
					if( is_object($EM_Event) && $EM_Event->event_id){					
						if($EM_Event->is_recurring( true )){
							$content = __( "Reschedule Events", 'events-manager')." '{$EM_Event->event_name}'";
						}else{
							$content = __( "Edit Event", 'events-manager') . " '" . $EM_Event->event_name . "'";
						}
					}else{
						$content = __( 'Add Event', 'events-manager');
					}
				}
				Archetypes::revert_current();
			}elseif( $post->ID == $edit_locations_page_id ){
				if( !empty($_REQUEST['action']) && $_REQUEST['action'] = 'edit' ){
					if( empty($EM_Location) || !is_object($EM_Location) ){
						$content = __('Add Location', 'events-manager');
					}else{
						$content = __('Edit Location', 'events-manager');
					}
				}
			}elseif( in_array($post->ID, $edit_bookings_page_ids) && $post->ID != 0 ){ 
				$event_archetype = array_flip( $edit_bookings_page_ids )[$post->ID];
				Archetypes::set_current( $event_archetype );
				if( is_object($EM_Event) ){
					$content = $EM_Event->name .' - '. $original_content;
				}
				Archetypes::revert_current();
			}
		}
		return apply_filters('em_content_page_title', $content);
	}
	return $original_content;
}

function em_content_wp_title($title, $sep = '', $seplocation = ''){
	global $EM_Location, $post;
	$in_the_loop = !(defined('EM_CHECK_THE_LOOP') && EM_CHECK_THE_LOOP) || in_the_loop(); // check if we're in the loop... since this may break some themes, we're introducing it as a constant for themes that cause issues vs. breaking themes that already work.
	if( empty($post) || empty($post->ID) || !$in_the_loop ) return $title; //fix for any other plugins calling the_content outside the loop
	//single event and location page titles get parsed for formats
	if( is_single() && !empty($post->post_type) ){
		if( Archetypes::is_event($post) ){
			$EM_Event = em_get_event($post);
			return $EM_Event->output($title);
		}elseif( $post->post_type == EM_POST_TYPE_LOCATION ){
			$EM_Location = em_get_location($post);
			return $EM_Location->output($title);
		}
	}
	//we only rewrite titles on events and locations pages since they are 'special'
	$pages = array( get_option('dbem_events_page'), get_option( 'dbem_locations_page' ) );
	if( !empty($post->ID) && !in_array($post->ID,$pages) ){ return $title; }
	// Determines position of the separator and direction of the breadcrumb
	$new_title = em_content_page_title($title);
	if( $new_title != $title ){
	    if( $sep == '' ) $sep = '  ';
		$title_array = explode( $sep, $title );
		foreach($title_array as $title_item_key => $title_item){ if(trim($title_item) == ''){ unset($title_array[$title_item_key]); } } //remove blanks
		$title_array[] = $new_title;
		if ( 'right' == $seplocation ) { // sep on right, so reverse the order
			array_unshift($title_array, '');
			$title_array = array_reverse( $title_array );
		}else{
		    $title_array[] = '';
		}
	    if( $sep == '  ' ) $sep = '';
		$title = implode( " $sep ", $title_array );
	}
	return $title;
}
add_filter ( 'wp_title', 'em_content_wp_title',100,3 ); //override other plugin SEO due to way EM works.

/**
 * Yoast SEO friendly short circuit, fixes issues in Yoast 14 update by changing the $sep function into the actual separator.
 * @param $title
 * @param string|mixed $sep
 * @param string $seplocation
 * @return string
 */
function em_content_wpseo_title($title, $sep = '', $seplocation = ''){
	if( class_exists('WPSEO_Utils') && method_exists('WPSEO_Utils', 'get_title_separator') && version_compare(WPSEO_VERSION, '15.2', '<') ){
		$sep = WPSEO_Utils::get_title_separator();
	}elseif( !is_string( $sep ) ){
		$sep = '';
	}
	if( !is_string($seplocation) ){
		$seplocation = '';
	}
	return em_content_wp_title( $title, $sep, $seplocation = '' );
}
add_filter( 'wpseo_title', 'em_content_wpseo_title', 100, 2 ); //WP SEO friendly

/**
 * Makes sure we're in "THE Loop", which is determinied by a flag set when the_post() (start) is first called, and when have_posts() (end) returns false.
 * @param string $data
 * @return string
 */
function em_wp_the_title($data, $id = null){
	global $post, $wp_query, $EM_Location, $EM_Event;
	$in_the_loop = !(defined('EM_CHECK_THE_LOOP') && EM_CHECK_THE_LOOP) || in_the_loop(); // check if we're in the loop... since this may break some themes, we're introducing it as a constant for themes that cause issues vs. breaking themes that already work.
	if( empty($post) || empty($post->ID) || !$in_the_loop ) return $data; //fix for any other plugins calling the_content outside the loop
	//because we're only editing the main title of the page here, we make sure we're in the main query
	if( is_main_query() && $id == $post->ID ){
	    $event_page_ids = Archetypes::get_option_values('dbem_events_page');
	    $locations_page_id = get_option( 'dbem_locations_page' );
	    $edit_events_page_ids = Archetypes::get_option_values( 'dbem_edit_events_page' );
	    $edit_locations_page_id = get_option( 'dbem_edit_locations_page' );
	    $edit_bookings_page_ids = Archetypes::get_option_values( 'dbem_edit_bookings_page' );
		if( !empty($post->ID) && in_array($post->ID, [ $locations_page_id, $edit_locations_page_id, ...array_values($edit_bookings_page_ids), ...array_values($edit_events_page_ids), ...array_values($event_page_ids) ] ) ){
			if ( $wp_query->in_the_loop ) {
				return apply_filters('em_wp_the_title', em_content_page_title($data, $id)) ;
			}
		}elseif( is_single() && !empty($post->post_type) ){
			if( Archetypes::is_event($post) ){
				$EM_Event = em_get_event($post);
				return apply_filters('em_wp_the_title', $EM_Event->output($data)) ;
			}elseif( $post->post_type == EM_POST_TYPE_LOCATION ){
				$EM_Location = em_get_location($post);
				return apply_filters('em_wp_the_title', $EM_Location->output($data)) ;
			}
		}
	}
	return $data;
}
add_filter ( 'the_title', 'em_wp_the_title',10, 2 );


function em_get_page_type(){
	global $EM_Location, $EM_Category, $EM_Event, $wp_query, $post, $em_category_id, $em_tag_id;
	$event_page_ids = Archetypes::get_option_values('dbem_events_page');
	$locations_page_id = get_option( 'dbem_locations_page' );
	$categories_page_id = get_option( 'dbem_categories_page' );
	$has_post = is_object($post);
	if ( !empty($event_page_ids) && $has_post && in_array($post->ID, $event_page_ids) ) {
		if ( $wp_query->get('calendar_day') ) {
			return "calendar_day";
		}else{
			return is_object($EM_Event) ? "event" : "events";
		}
	}elseif( empty($event_page_ids) ){
		if( $wp_query->get('calendar_day') ){
			return "calendar_day";
		}
	}
	if( is_single() && $has_post && $post->post_type == EM_POST_TYPE_EVENT  ){
		return 'event';
	}
	if( (!empty($locations_page_id) && $has_post && $post->ID == $locations_page_id) || (!is_single() && !empty($wp_query->query_vars['post_type']) && $wp_query->query_vars['post_type'] == EM_POST_TYPE_LOCATION) ){
		return is_object($EM_Location) ? "location":"locations";
	}elseif( is_single() && $post->post_type == EM_POST_TYPE_LOCATION ){
		return 'location';
	}
	if( (!empty($categories_page_id) && $has_post && $post->ID == $categories_page_id) ){
		return "categories";
	}elseif( is_tax(EM_TAXONOMY_CATEGORY) || !empty($wp_query->em_category_id) || ($has_post && $post->ID == get_option('dbem_categories_page') && !empty($em_category_id)) ){
		return "category";
	}elseif( is_tax(EM_TAXONOMY_TAG) || !empty($wp_query->em_tag_id) || !empty($em_tag_id) ){
		return "tag";
	}
}
?>