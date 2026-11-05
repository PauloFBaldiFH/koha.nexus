<?php
	/**
	 * generates an ical feed on init if url is correct
	 */
	function em_ical( ){
		//check if this is a calendar request for all events
		if ( preg_match('/events.ics(\?.+)?$/', $_SERVER['REQUEST_URI']) || $_SERVER['REQUEST_URI'] == '/?ical=1' ) {
			header('Content-Type: text/calendar; charset=utf-8');
			header('Content-Disposition: inline; filename="events.ics"');
			//send headers
			em_ical_protect_passworded_events();
			em_locate_template('templates/ical.php', true);
			die();
		}
	}
	add_action ( 'init', 'em_ical' );
	
	/**
	 * Keeps password-protected events out of an iCalendar feed. The feed publishes the event name, description, permalink, image, location and coordinates, none of which a visitor should get without the password, and the query layer can't tell: event_status and event_private say nothing about wp_posts.post_password.
	 *
	 * Filtering EM_Events::get() rather than the template means a theme carrying its own copy of ical.php is covered too.
	 */
	function em_ical_protect_passworded_events(){
		add_filter('em_events_get', function( $events ){
			foreach ( $events as $key => $EM_Event ) {
				if ( is_object($EM_Event) && method_exists($EM_Event, 'password_required') && $EM_Event->password_required() ) {
					unset($events[$key]);
				}
			}
			return $events;
		});
	}
	
	/**
	 * Generates an ics file for a single event, or a specific archetype
	 */
	function em_ical_item(){
		global $wpdb, $wp_query;
		//check if we're outputting an ical feed
		if( !empty($wp_query) && $wp_query->get('ical') ){
			$filename = 'events';
			$args = array('scope' => 'all', 'status' => 1);
			// check for archetype request
			// single event
			$archetype = $wp_query->get('event_archetype');
			EM\Archetypes::set_current($archetype);
			if ( $archetype ) {
				$path = $wp_query->get( $archetype );
				$args['event_archetype'] = $archetype;
				if ( $path ) {
					if( preg_match('/\//', $path) ) {
						$post_id = em_get_page_by_path_for_ical( $path, OBJECT, [ $archetype ] );
						// get event by slug via WP, to account for complex permalink structures
						if ( $post_id ) {
							$EM_Event = em_get_event( $post_id, 'post_id' );
							$event_id = $EM_Event->event_id;
							$event_slug = $EM_Event->event_slug;
						}
					} else {
						// try to get event by slug directly from EM tables
						$event = $wpdb->get_row($wpdb->prepare("SELECT event_id, event_slug FROM " . EM_EVENTS_TABLE . " WHERE event_slug=%s AND event_status=1 AND event_archetype=%s LIMIT 1", $path, $archetype));
						if ( $event ) {
							$event_id = $event->event_id;
							$event_slug = $event->event_slug;
						}
					}
					if( !empty($event_id) ){
						$filename = $event_slug;
						$args['event'] = $event_id;
					}
				} else {
					unset( $args['scope'] );
				}
			//single location
			} elseif( $wp_query->get(EM_POST_TYPE_LOCATION) ) {
				$location_id = $wpdb->get_var($wpdb->prepare('SELECT location_id FROM '.EM_LOCATIONS_TABLE." WHERE location_slug=%s AND location_status=1 LIMIT 1", $wp_query->get(EM_POST_TYPE_LOCATION)));
				if( !empty($location_id) ){
					$filename = $wp_query->get(EM_POST_TYPE_LOCATION);
					$args['location'] = $location_id;
				}
			//taxonomies
			} else {
				$taxonomies = EM_Object::get_taxonomies();
				foreach($taxonomies as $tax_arg => $taxonomy_info){
					$taxonomy_term = $wp_query->get($taxonomy_info['query_var']); 
					if( $taxonomy_term ){
						$filename = $taxonomy_term;
						$args[$tax_arg] = $taxonomy_term;
					}
				}
			}
			//only output the ical if we have a match from above
			if( count($args) > 0 ){
				//send headers and output ical
				header('Content-type: text/calendar; charset=utf-8');
				header('Content-Disposition: inline; filename="'.$filename.'.ics"');
				em_ical_protect_passworded_events();
				em_locate_template('templates/ical.php', true, array('args'=>$args));
				exit();
			}else{
				//no item exists, so redirect to original URL
				$url_to_redirect = preg_replace("/ical\/$/",'', esc_url_raw(add_query_arg(array('ical'=>null))));				
				wp_safe_redirect($url_to_redirect, '302');
				exit();
			}
		}
	}
	add_action ( 'parse_query', 'em_ical_item' );
	

	/**
	 * A utf-8 safe wordwrap function, avoiding CRLF issues with Chinese and other multi-byte characters.
	 * @param string $string
	 * @return string
	 */
	function em_mb_ical_wordwrap($string){
		if( function_exists('mb_strcut') && (!defined('EM_MB_ICAL_WORDWRAP') || EM_MB_ICAL_WORDWRAP) ){
			$return = '';
			for ( $i = 0; strlen($string) > 0; $i++ ) {
				$linewidth = ($i == 0? 75 : 74);
				$linesize = (strlen($string) > $linewidth? $linewidth: strlen($string));
				if($i > 0) $return .= "\r\n ";
				$return .= mb_strcut($string,0,$linesize);
				$string = mb_strcut($string,$linewidth);
			}
			return $return;
		}
		return wordwrap($string, 75, "\r\n ", true);
	}

	/**
	 * Modified version of get_page_by_path() so that first found path is provided, allowing for easy retrieval of complex permalink structures like dates.
	 * The main differences are the cached ID is changed, the foreach loop gets the first result, and only the post id is returned
	 *
	 * @param $page_path
	 * @param $output
	 * @param $post_type
	 *
	 * @return array|int|mixed|void|WP_Post|null
	 */
	function em_get_page_by_path_for_ical( $page_path, $output = OBJECT, $post_type = array('event') ) {
		global $wpdb;

		$last_changed = wp_cache_get_last_changed( 'posts' );

		$hash      = md5( $page_path . serialize( $post_type ) );
		$cache_key = "get_event_ical_page_by_path:$hash:$last_changed";
		$cached    = wp_cache_get( $cache_key, 'events' );
		if ( false !== $cached ) {
			// Special case: '0' is a bad `$page_path`.
			if ( '0' === $cached || 0 === $cached ) {
				return;
			} else {
				return $cached; // just return the ID
			}
		}

		$page_path     = rawurlencode( urldecode( $page_path ) );
		$page_path     = str_replace( '%2F', '/', $page_path );
		$page_path     = str_replace( '%20', ' ', $page_path );
		$parts         = explode( '/', trim( $page_path, '/' ) );
		$parts         = array_map( 'sanitize_title_for_query', $parts );
		$escaped_parts = esc_sql( $parts );

		$in_string = "'" . implode( "','", $escaped_parts ) . "'";

		if ( is_array( $post_type ) ) {
			$post_types = $post_type;
		} else {
			$post_types = array( $post_type, 'attachment' );
		}

		$post_types          = esc_sql( $post_types );
		$post_type_in_string = "'" . implode( "','", $post_types ) . "'";
		$sql                 = "
			SELECT ID, post_name, post_parent, post_type
			FROM $wpdb->posts
			WHERE post_name IN ($in_string)
			AND post_type IN ($post_type_in_string)
		";

		$pages = $wpdb->get_results( $sql, OBJECT_K );

		$revparts = array_reverse( $parts );

		$foundid = 0;
		foreach ( (array) $pages as $page ) {
			$foundid = $page->ID;
			break;
		}

		// We cache misses as well as hits.
		wp_cache_set( $cache_key, $foundid, 'events' );

		return $foundid;
	}
?>