<?php

use EM\Archetypes;

/**
 * Performs actions on init. This works for both ajax and normal requests, the return results depends if an em_ajax flag is passed via POST or GET.
 */
function em_init_actions_start() {
	global $wpdb,$EM_Notices,$EM_Event; 
	if( defined('DOING_AJAX') && DOING_AJAX ) $_REQUEST['em_ajax'] = true;
	
	//NOTE - No EM objects are globalized at this point, as we're hitting early init mode.
	//TODO Clean this up.... use a uniformed way of calling EM Ajax actions
	if( !empty($_REQUEST['em_ajax']) || !empty($_REQUEST['em_ajax_action']) ){
		if(isset($_REQUEST['em_ajax_action']) && $_REQUEST['em_ajax_action'] == 'get_location') {
			if( isset($_REQUEST['id']) ){
				$EM_Location = new EM_Location( absint($_REQUEST['id']), 'location_id' );
				if ( $EM_Location->status == 1 && ( is_post_publicly_viewable( $EM_Location->post_id ) || ( is_user_logged_in() && current_user_can('read_post', $EM_Location->post_id) ) ) ) { // second one is for other plugins that may hide stuff
					$location_data = $EM_Location->to_array();
					// remove any data we don't need to show on the map
					$location_array = [
						'location_id' => $location_data['location_id'],
						'location_latitude' => $location_data['location_latitude'],
						'location_longitude' => $location_data['location_longitude'],
						'location_name' => $location_data['location_name'],
					];
					if ( !post_password_required($EM_Location->post_id) || $EM_Location->can_manage('edit_locations','edit_others_locations') ) {
						// do some minor checks to make sure event can be viewed by user, if password protected remove any content and just show location data
						$location_array['location_balloon'] = $EM_Location->output( em_get_option('dbem_location_baloon_format') );
					}
				}
				if ( empty( $location_array ) ) {
					// provide an anonymous location
					$location_array = [
						'location_id' => 0,
						'location_latitude' => 0,
						'location_longitude' => 0,
						'location_name' => 'Undisclosed Location',
					];
				}
		     	echo EM_Object::json_encode($location_array);
			}
			die();
		}
		if(isset($_REQUEST['query']) && $_REQUEST['query'] == 'GlobalMapData') {
			$EM_Locations = EM_Locations::get( $_REQUEST );
			$json_locations = array();
			foreach($EM_Locations as $location_key => $EM_Location) {
				if ( ! $EM_Location->is_publicly_viewable() ) continue; // never disclose pending, draft or private locations to visitors who can't read them
				$json_locations[$location_key] = $EM_Location->to_array();
				if ( ! $EM_Location->password_required() ) {
					$json_locations[$location_key]['location_balloon'] = $EM_Location->output( em_get_option('dbem_map_text_format') );
				}
			}
			echo EM_Object::json_encode($json_locations);
		 	die();
	 	}
		if(isset($_REQUEST['query']) && $_REQUEST['query'] == 'GlobalEventsMapData') {
			$_REQUEST['has_location'] = true; //we're looking for locations in this context, so locations necessary
			$_REQUEST['groupby'] = 'location_id'; //grouping will generally produce much faster processing
			$EM_Events = EM_Events::get( $_REQUEST );
			$json_locations = array();
			$locations = array();
			foreach($EM_Events as $EM_Event) {
				$EM_Location = $EM_Event->get_location();
				if ( ! $EM_Location->is_publicly_viewable() ) continue; // the joined location is only clamped on the main table, so re-check visibility before disclosing a pending/private venue (incl. venues of password-protected events)
				$location_array = $EM_Location->to_array();
				if ( ! $EM_Location->password_required() ) {
					$location_array['location_balloon'] = $EM_Location->output(em_get_option('dbem_map_text_format'));
				}
				$json_locations[] = $location_array;
			}
			echo EM_Object::json_encode($json_locations);
		 	die();   
	 	}
	
		if(isset($_REQUEST['ajaxCalendar']) && $_REQUEST['ajaxCalendar']) {
			$_REQUEST['has_search'] = false; //prevent search from loading up again
			echo EM_Calendar::output( $_REQUEST, false );
			die();
		}

		// Booking Form actions, AJAX specific
		if( isset($_REQUEST['action']) ) {
			if ( $_REQUEST['action'] == 'booking_form' ) {
				if ( !empty( $_REQUEST['event_id'] ) && !empty( $_REQUEST['nonce'] ) && wp_verify_nonce( $_REQUEST['nonce'], 'booking_form' ) ) {
					$EM_Event = em_get_event( $_REQUEST['event_id'] );
					do_action('em_ajax_output_booking_form', $EM_Event);
					if ( $EM_Event->is_published() ) {
						echo $EM_Event->output_booking_form();
					} else {
						echo '<div class="em-booking-form-error">' . __( 'This event is not available or has been cancelled', 'events-manager' ) . '</div>';
					}
				} else {
					echo '<div class="em-booking-form-error">' . __( 'Invalid request', 'events-manager' ) . '</div>';
				}
				exit();
			} elseif ( $_REQUEST['action'] == 'booking_recurrences' ) {
				if ( !empty( $_REQUEST['event_id'] ) && !empty( $_REQUEST['nonce'] ) && wp_verify_nonce( $_REQUEST['nonce'], 'booking_recurrences' ) ) {
					$EM_Event = em_get_event( $_REQUEST['event_id'] );
					// get the date requested
					$day = $_REQUEST['day'];
					if ( preg_match('/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/', $day) ) {
						$scope = $day;
					}
					if ( !empty($_REQUEST['timezone']) && preg_match('/^(([A-Za-z0-9-_]+\/[A-Za-z0-9-_]+)|([A-Za-z]{1,4})|(UTC|GMT)(\+|-)[0-9]{1,2}([\.:][0-9]{2})?)$/', $_REQUEST['timezone']) ) {
						$EM_Event->set_timezone( $_REQUEST['timezone'] );
					}
					include em_locate_template( 'forms/bookingform/recurring/booking-recurrences.php' );
				} else {
					echo '<div class="em-booking-form-error">' . __( 'Invalid request', 'events-manager' ) . '</div>';
				}
				exit();
			} elseif ( $_REQUEST['action'] == 'booking_form_nonces' ) {
				if ( ( defined( 'WP_CACHE' ) && WP_CACHE ) || defined( 'EM_CACHE' ) && EM_CACHE ) {
					echo EM_Object::json_encode( em_booking_form_nonces() );
					exit();
				}
			}
		}
	}

	//Event Actions
	if( !empty($_REQUEST['action']) && substr($_REQUEST['action'],0,5) == 'event' ){
		//Load the event object, with saved event if requested
		if( !empty($_REQUEST['event_id']) ){
			$EM_Event = em_get_event( $_REQUEST['event_id'] );
		}else{
			$EM_Event = new EM_Event();
		}
		//Save Event, only via BP or via [event_form]
		if( $_REQUEST['action'] == 'event_save' && $EM_Event->can_manage('edit_events','edit_others_events') ){
			//Check Nonces
			if( !wp_verify_nonce($_REQUEST['_wpnonce'], 'wpnonce_event_save') ) exit('Trying to perform an illegal action.');
			//Set server timezone to UTC in case other plugins are doing something naughty
			$server_timezone = date_default_timezone_get();
			date_default_timezone_set('UTC');
			//Grab and validate submitted data
			if ( $EM_Event->get_post() && $EM_Event->save() ) { //EM_Event gets the event if submitted via POST and validates it (safer than to depend on JS)
				$events_result = true;
				//Success notice
				if( is_user_logged_in() ){
					if( empty($_REQUEST['event_id']) ){
						$EM_Notices->add_confirm( $EM_Event->output( $EM_Event->get_option('dbem_events_form_result_success')), true);
					}else{
					    $EM_Notices->add_confirm( $EM_Event->output( $EM_Event->get_option('dbem_events_form_result_success_updated')), true);
					}
				}else{
					$EM_Notices->add_confirm( $EM_Event->output( $EM_Event->get_option('dbem_events_anonymous_result_success')), true);
				}
				$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
				$redirect = em_add_get_params($redirect, array('success'=>1), false, false);
				wp_safe_redirect( $redirect );
				exit();
			}else{
				$EM_Notices->add_error( $EM_Event->get_errors() );
				$events_result = false;				
			}
			//Set server timezone back, even though it should be UTC anyway
			date_default_timezone_set($server_timezone);
		}
		if ( $_REQUEST['action'] == 'event_duplicate' && wp_verify_nonce($_REQUEST['_wpnonce'],'event_duplicate_'.$EM_Event->event_id) ) {
			$event = $EM_Event->duplicate();
			if( $event === false ){
				$EM_Notices->add_error( $EM_Event->errors, true );
				wp_safe_redirect( em_wp_get_referer() );
			}else{
				$EM_Notices->add_confirm( $event->feedback_message, true );
				wp_safe_redirect( $event->get_edit_url( false ) );
			}
			exit();
		}
		if ( $_REQUEST['action'] == 'event_delete' && wp_verify_nonce($_REQUEST['_wpnonce'],'event_delete_'.$EM_Event->event_id) ) { 
			//DELETE action
			$selectedEvents = !empty($_REQUEST['events']) ? $_REQUEST['events']:array();
			if(  EM_Object::array_is_numeric($selectedEvents) ){
				$events_result = EM_Events::delete( $selectedEvents );
			}elseif( is_object($EM_Event) ){
				$events_result = $EM_Event->delete();
			}
			$plural = (count($selectedEvents) > 1) ? __('Events','events-manager'):__('Event','events-manager');
			if($events_result){
				$message = ( !empty($EM_Event->feedback_message) ) ? $EM_Event->feedback_message : sprintf(__('%s successfully deleted.','events-manager'),$plural);
				$EM_Notices->add_confirm( $message, true );
			}else{
				$message = ( !empty($EM_Event->errors) ) ? $EM_Event->errors : sprintf(__('%s could not be deleted.','events-manager'),$plural);
				$EM_Notices->add_error( $message, true );		
			}
			wp_safe_redirect( em_wp_get_referer() );
			exit();
		}elseif( $_REQUEST['action'] == 'event_detach' && wp_verify_nonce($_REQUEST['_wpnonce'],'event_detach_'.get_current_user_id().'_'.$EM_Event->event_id) ){ 
			//Detach event and move on
			if($EM_Event->detach()){
				$EM_Notices->add_confirm( $EM_Event->feedback_message, true );
			}else{
				$EM_Notices->add_error( $EM_Event->errors, true );			
			}
			wp_safe_redirect(em_wp_get_referer());
			exit();
		}elseif( $_REQUEST['action'] == 'event_attach' && !empty($_REQUEST['undo_id']) && !empty($_REQUEST['_wpnonce']) && wp_verify_nonce($_REQUEST['_wpnonce'],'event_attach_'.get_current_user_id().'_'.$EM_Event->event_id) ){
			//Detach event and move on
			if( $EM_Event->attach( absint($_REQUEST['undo_id']), !empty($_REQUEST['recurring_id']) ? absint($_REQUEST['recurring_id']) : null )  ){
				$EM_Notices->add_confirm( $EM_Event->feedback_message, true );
			}else{
				$EM_Notices->add_error( $EM_Event->errors, true );
			}
			wp_safe_redirect(em_wp_get_referer());
			exit();
		}
		
		//AJAX Exit
		if( isset($events_result) && !empty($_REQUEST['em_ajax']) ){
			if( $events_result ){
				$return = array('result'=>true, 'success'=>true, 'message'=>$EM_Event->feedback_message);
			}else{		
				$return = array('result'=>false, 'success'=>false, 'message'=>$EM_Event->feedback_message, 'errors'=>$EM_Event->errors);
			}
			echo EM_Object::json_encode($return);
			edit();
		}
	}
	
	//Location Actions
	if( !empty($_REQUEST['action']) && substr($_REQUEST['action'],0,8) == 'location' ){
		global $EM_Location, $EM_Notices;
		//Load the location object, with saved event if requested
		if( !empty($_REQUEST['location_id']) ){
			$EM_Location = new EM_Location( absint($_REQUEST['location_id']) );
		}else{
			$EM_Location = new EM_Location();
		}
		if( $_REQUEST['action'] == 'location_save' && $EM_Location->can_manage('edit_locations','edit_others_locations') ){
			//Check Nonces
			em_verify_nonce('location_save');
			//Grab and validate submitted data
			if ( $EM_Location->get_post() && $EM_Location->save() ) { //EM_location gets the location if submitted via POST and validates it (safer than to depend on JS)
				$EM_Notices->add_confirm($EM_Location->feedback_message, true);
				$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
				wp_safe_redirect( $redirect );
				exit();
			}else{
				$EM_Notices->add_error( $EM_Location->get_errors() );
				$result = false;		
			}
		}elseif( !empty($_REQUEST['action']) && $_REQUEST['action'] == "location_delete" ){
			//delete location
			em_verify_nonce($_REQUEST['action'], 'nonce');
			//get object or objects			
			if( !empty($_REQUEST['locations']) || !empty($_REQUEST['location_id']) ){
				$args = false;
				if( !empty($_REQUEST['locations']) && EM_Object::array_is_numeric($_REQUEST['locations']) ){
					$args = $_REQUEST['locations'];
				}elseif( !empty($_REQUEST['location_id']) ){
					$args = absint($_REQUEST['location_id']);
				}
				if( !empty($args) ){
					$locations = EM_Locations::get($args);
					foreach($locations as $location) {
						if( !$location->delete() ){
							$EM_Notices->add_error($location->get_errors());
							$errors = true;
						}
					}
				}
				if( empty($errors) ){
					$result = true;
					$location_term = ( count($locations) > 1 ) ?__('Locations', 'events-manager') : __('Location', 'events-manager'); 
					$EM_Notices->add_confirm( sprintf(__('%s successfully deleted', 'events-manager'), $location_term) );
				}else{
					$result = false;
				}
			}
		}elseif( !empty($_REQUEST['action']) && $_REQUEST['action'] == "locations_search" && (!empty($_REQUEST['term']) || !empty($_REQUEST['q'])) ){
			$results = array();
			if( is_user_logged_in() || ( em_get_option('dbem_events_anonymous_submissions') && user_can(em_get_option('dbem_events_anonymous_user'), 'read_others_locations') ) ){
				$location_cond = (is_user_logged_in() && !current_user_can('read_others_locations')) ? "AND location_owner=".get_current_user_id() : '';
				if( !is_user_logged_in() && em_get_option('dbem_events_anonymous_submissions') ){
					if( !user_can(em_get_option('dbem_events_anonymous_user'),'read_private_locations') ){
						$location_cond = " AND location_private=0";	
					}
				}elseif( is_user_logged_in() && !current_user_can('read_private_locations') ){
				    $location_cond = " AND location_private=0";
				}elseif( !is_user_logged_in() ){
					$location_cond = " AND location_private=0";		    
				}
				if( EM_MS_GLOBAL && !get_site_option('dbem_ms_mainblog_locations') ){
					$location_cond .= " AND blog_id=". absint(get_current_blog_id());
				}
				$location_cond = apply_filters('em_actions_locations_search_cond', $location_cond);
				$term = (isset($_REQUEST['term'])) ? '%'.$wpdb->esc_like(wp_unslash($_REQUEST['term'])).'%' : '%'.$wpdb->esc_like(wp_unslash($_REQUEST['q'])).'%';
				$limit = apply_filters('em_locations_autocomplete_limit', 10);
				$page = !empty($_REQUEST['page']) && is_numeric($_REQUEST['page']) ? absint($_REQUEST['page']) : 1;
				$offset = ($page - 1) * $limit;
				
				// Get the results
				$sql = $wpdb->prepare("
					SELECT 
						location_id AS `id`,
						Concat( location_name )  AS `label`,
						Concat( location_name )  AS `text`,
						location_name AS `value`,
						location_address AS `address`,
						location_town AS `town`,
						location_state AS `state`,
						location_region AS `region`,
						location_postcode AS `postcode`,
						location_country AS `country`,
						location_latitude AS `latitude`,
						location_longitude AS `longitude`
					FROM ".EM_LOCATIONS_TABLE." 
					WHERE ( `location_name` LIKE %s ) AND location_status=1 $location_cond LIMIT $limit OFFSET $offset
				", $term); // 'label' is now for backwards compatibility
				$results = $wpdb->get_results($sql);
			}
			$results = apply_filters('em_actions_locations_search_results', $results);
			echo EM_Object::json_encode($results);
			die();
		} elseif ( $_REQUEST['action'] == 'location_duplicate' && wp_verify_nonce($_REQUEST['_wpnonce'],'location_duplicate_'.$EM_Location->location_id) ) {
			$location = $EM_Location->duplicate();
			if( $location === false ){
				$EM_Notices->add_error( $EM_Location->errors, true );
				wp_safe_redirect( em_wp_get_referer() );
			}else{
				$EM_Notices->add_confirm( $location->feedback_message, true );
				wp_safe_redirect( $location->get_edit_url( false ) );
			}
			exit();
		}
		if( isset($result) && $result && !empty($_REQUEST['em_ajax']) ){
			$return = array('result'=>true, 'success'=>true, 'message'=>$EM_Location->feedback_message);
			echo EM_Object::json_encode($return);
			die();
		}elseif( isset($result) && !$result && !empty($_REQUEST['em_ajax']) ){
			$return = array('result'=>false, 'success'=>false, 'message'=>$EM_Location->feedback_message, 'errors'=>$EM_Notices->get_errors());
			echo EM_Object::json_encode($return);
			die();
		}
	}
	
	//Booking Actions
	$booking_allowed_actions = array('bookings_approve'=>'approve','bookings_reject'=>'reject','bookings_unapprove'=>'unapprove', 'bookings_delete'=>'delete');
	$booking_ajax_actions = array('booking_add', 'booking_add_one', 'booking_cancel', 'booking_save', 'booking_set_status', 'booking_resend_email', 'booking_modify_person', 'bookings_add_note', 'booking_form', 'booking_form_summary', 'booking_rsvp_change', 'booking_set_rsvp_status');
	$booking_nopriv_actions = array('booking_add', 'booking_form_summary');
	$booking_actions = array_merge( $booking_ajax_actions, array_keys($booking_allowed_actions) );
	if( !empty($_REQUEST['action']) && in_array($_REQUEST['action'], $booking_actions) && (is_user_logged_in() || (in_array($_REQUEST['action'], $booking_nopriv_actions) && em_get_option('dbem_bookings_anonymous'))) ){
		global $EM_Event, $EM_Booking, $EM_Person;
		//Load the booking object, with saved booking if requested
		$EM_Booking = em_get_booking_request( $_REQUEST['booking_id'] ?? false );
		if( !empty($EM_Booking->event_id) ){
			//Load the event object, with saved event if requested
			$EM_Event = $EM_Booking->get_event();
		}elseif( !empty($_REQUEST['event_id']) ){
			$EM_Event = em_get_event( $_REQUEST['event_id'] );
		}
		// set the archetype
		Archetypes::set_current( $EM_Event->event_archetype );
		// start process
		$result = false;
		$feedback = '';
		do_action('em_before_booking_action_'.$_REQUEST['action'], $EM_Event, $EM_Booking);
		if ( $_REQUEST['action'] == 'booking_add') {
			//ADD/EDIT Booking
			ob_start();
			em_verify_booking_nonce('booking_add');
			// Authorise against the booking's persisted event before get_post() re-assigns event_id from the request. Otherwise a user could pass another user's booking_id together with an event they manage and have that booking re-saved onto their event, the same substitution already guarded in booking_form_summary. A new booking (no booking_id) is unaffected.
			$can_edit_booking = empty($EM_Booking->booking_id) || $EM_Booking->can_manage('manage_bookings','manage_others_bookings') || ( is_user_logged_in() && !empty($EM_Booking->person->ID) && $EM_Booking->person->ID == get_current_user_id() );
			if( empty($EM_Booking->booking_id) && !$EM_Event->can_manage('manage_bookings','manage_others_bookings') ){
				// em_load_event() builds $EM_Person from a request person_id and a new booking adopts it in get_person(), so only someone managing this event may book on another user's behalf.
				$EM_Person = is_user_logged_in() ? new EM_Person( get_current_user_id() ) : null;
			}
			if( !is_user_logged_in() || $EM_Booking->get_option('dbem_bookings_double') || !$EM_Event->get_bookings()->has_booking(get_current_user_id()) ){
				if ( $EM_Event->event_status != 1 || $EM_Event->event_active_status != 1 ) {
					$EM_Notices->add_error( __('This event is not available or has been cancelled', 'events-manager') ); // uncommon, not needed for custom error.
				} elseif ( !$can_edit_booking ) {
					$EM_Notices->add_error( __('You do not have permission to manage this booking.', 'events-manager') );
				} else {
				    $EM_Booking->get_post();
					$post_validation = $EM_Booking->validate();
					do_action('em_booking_add', $EM_Event, $EM_Booking, $post_validation);
					if( $post_validation ){
					    //register the user - or not depending - according to the booking
					    $registration = em_booking_add_registration($EM_Booking);
						$EM_Bookings = $EM_Event->get_bookings();
						if( $registration && $EM_Bookings->add($EM_Booking) ){
						    if( is_user_logged_in() && is_multisite() && !is_user_member_of_blog(get_current_user_id(), get_current_blog_id()) ){
						        add_user_to_blog(get_current_blog_id(), get_current_user_id(), get_option('default_role')); // WP Default role
						    }
							$result = true;
							$EM_Notices->add_confirm( $EM_Bookings->feedback_message );
							$feedback = $EM_Bookings->feedback_message;
						}else{
							if(!$registration){
							    $EM_Notices->add_error( $EM_Booking->get_errors() );
								$feedback = $EM_Booking->feedback_message;
							}else{
							    $EM_Notices->add_error( $EM_Bookings->get_errors() );
								$feedback = $EM_Bookings->feedback_message;
							}
						}
						global $em_temp_user_data; $em_temp_user_data = false; //delete registered user temp info (if exists)
					}else{
						$EM_Notices->add_error( $EM_Booking->get_errors() );
					}
				}
			}else{
				$feedback = $EM_Booking->get_option('dbem_booking_feedback_already_booked');
				$EM_Notices->add_error( $feedback );
			}
			ob_clean();
	  	}elseif ( $_REQUEST['action'] == 'booking_add_one' && is_object($EM_Event) && is_user_logged_in() ) {
			//ADD/EDIT Booking
			em_verify_nonce('booking_add_one');
			if ( $EM_Event->event_status != 1 || $EM_Event->event_active_status != 1 ) {
				$EM_Notices->add_error( __('This event is not available or has been cancelled.', 'events-manager') ); // uncommon, not needed for custom error.
			} else {
				if( $EM_Booking->get_option('dbem_bookings_double') || !$EM_Event->get_bookings()->has_booking(get_current_user_id()) ){
					$EM_Booking = em_get_booking(array('person_id'=>get_current_user_id(), 'event_id'=>$EM_Event->event_id, 'booking_spaces'=>1)); //new booking
					// get first ticket that's available
					foreach( $EM_Event->get_bookings()->get_available_tickets() as $EM_Ticket ){
						if( $EM_Ticket->is_available() ){
							$ticket_found = true;
							break;
						}
					}
					if( !empty($ticket_found) ){
						//get first ticket in this event and book one place there. similar to getting the form values in EM_Booking::get_post_values()
						$EM_Ticket_Booking = new EM_Ticket_Booking(array('ticket_id'=>$EM_Ticket->ticket_id, 'booking_id' => $EM_Booking->booking_id, 'booking' => $EM_Booking));
						$EM_Booking->get_tickets_bookings()->add( $EM_Ticket_Booking );
						$post_validation = $EM_Booking->validate();
						do_action('em_booking_add', $EM_Event, $EM_Booking, $post_validation);
						if( $post_validation ){
							//Now save booking
							if( $EM_Event->get_bookings()->add($EM_Booking) ){
								$result = true;
								$EM_Notices->add_confirm( $EM_Event->get_bookings()->feedback_message );
								$feedback = $EM_Event->get_bookings()->feedback_message;
							}else{
								$EM_Notices->add_error( $EM_Event->get_bookings()->get_errors() );
								$feedback = $EM_Event->get_bookings()->feedback_message;
								if( empty($feedback) ) $feedback = implode("\r\n", $EM_Event->get_bookings()->get_errors());
							}
						}else{
							$EM_Notices->add_error( $EM_Booking->get_errors() );
							$feedback = $EM_Event->get_bookings()->feedback_message;
						}
					}else{
						$EM_Notices->add_error( $EM_Booking->get_option('dbem_booking_feedback_full') );
						$feedback = $EM_Booking->get_option('dbem_booking_feedback_full');
					}
				}else{
					$feedback = $EM_Booking->get_option('dbem_booking_feedback_already_booked');
					$EM_Notices->add_error( $feedback );
				}
			}
	  	}elseif ( $_REQUEST['action'] == 'booking_cancel') {
	  		//Cancel Booking
			em_verify_nonce('booking_cancel');
	  		if( $EM_Booking->can_manage() || $EM_Booking->person->ID == get_current_user_id() ){
				if( !$EM_Booking->can_cancel() ){ // admins also cannot cancel their own bookings this way, only via admin ui
					$feedback = esc_html__('Cancellations are not permitted for this booking.', 'events-manager');
					$EM_Notices->add_error( $feedback );
				}else{
					if( $EM_Booking->cancel() ){
						$result = true;
						if( !defined('DOING_AJAX') ){
							if( $EM_Booking->person->ID == get_current_user_id() ){
								$EM_Notices->add_confirm( $EM_Booking->get_option('dbem_booking_feedback_cancelled'), true );
							}else{
								$EM_Notices->add_confirm( $EM_Booking->feedback_message, true );
							}
							wp_safe_redirect( $_SERVER['HTTP_REFERER'] );
							exit();
						}
					}else{
						$result = false;
						$EM_Notices->add_error( $EM_Booking->get_errors() );
						$feedback = $EM_Booking->feedback_message;
					}
				}
			}else{
				$EM_Notices->add_error( __('You must log in to cancel your booking.', 'events-manager') );
			}
		//TODO user action shouldn't check permission, booking object should.
		}elseif ( $_REQUEST['action'] == 'booking_rsvp_change' && isset($_REQUEST['status']) ) {
			// Change RSVP status
			em_verify_nonce('booking_rsvp');
			$status = absint($_REQUEST['status']);
			if( $EM_Booking->can_manage() || $EM_Booking->person->ID == get_current_user_id() ){
				if( $EM_Booking->can_rsvp( $status ) ) {
					if ( $EM_Booking->set_rsvp_status( $status ) ) {
						$result = true;
						if ( !defined( 'DOING_AJAX' ) ) {
							$EM_Notices->add_confirm( $EM_Booking->feedback_message, true );
							wp_safe_redirect( $_SERVER['HTTP_REFERER'] );
							exit();
						}
					} else {
						$result = false;
						$EM_Notices->add_error( $EM_Booking->get_errors() );
						$feedback = $EM_Booking->feedback_message;
					}
				} else {
					$rsvp_status = EM_Booking::get_rsvp_statuses( $status );
					$feedback = sprintf( esc_html__('You cannot RSVP to this booking with %s', 'events-manager'), "'" . $rsvp_status->label_action . "'");
					$EM_Notices->add_error($feedback);
				}
			}else{
				$EM_Notices->add_error( __('You must log in to cancel your booking.', 'events-manager') );
			}
			//TODO user action shouldn't check permission, booking object should.
		}elseif( array_key_exists($_REQUEST['action'], $booking_allowed_actions) && $EM_Event->can_manage('manage_bookings','manage_others_bookings') ){
	  		//Event Admin only actions
			em_verify_nonce($_REQUEST['action'], 'nonce');
			$action = $booking_allowed_actions[$_REQUEST['action']];
			//Just do it here, since we may be deleting bookings of different events.
			if( !empty($_REQUEST['bookings']) && EM_Object::array_is_numeric($_REQUEST['bookings'])){
				$results = array();
				foreach($_REQUEST['bookings'] as $booking_id){
					$EM_Booking = em_get_booking($booking_id);
					if( !$EM_Booking->get_event()->can_manage('manage_bookings','manage_others_bookings') ){
						$results[] = false;
						continue;
					}
					$result = $EM_Booking->$action();
					$results[] = $result;
					if( !in_array(false, $results) && !$result ){
						$feedback = $EM_Booking->feedback_message;
					}
				}
				$result = !in_array(false,$results);
			}elseif( is_object($EM_Booking) ){
				$result = $EM_Booking->$action();
				$feedback = $EM_Booking->feedback_message;
			}
			//FIXME not adhereing to object's feedback or error message, like other bits in this file.
			//TODO multiple deletion won't work in ajax
			if( !empty($_REQUEST['em_ajax']) ){
				if( $result ){
					echo $feedback;
				}else{
					echo '<span style="color:red">'.$feedback.'</span>';
				}	
				die();
			}else{
			    if( $result ){
			        $EM_Notices->add_confirm($feedback);
			    }else{
			        $EM_Notices->add_error($feedback);
			    }
			}
		}elseif( $_REQUEST['action'] == 'booking_save' ){
			em_verify_nonce('booking_save_'.$EM_Booking->booking_id);
			if( $EM_Booking->can_manage('manage_bookings','manage_others_bookings') ){
				if ($EM_Booking->get_post(true) && $EM_Booking->validate(true) && $EM_Booking->save(false) ){
					$EM_Notices->add_confirm( $EM_Booking->feedback_message, true );
					$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
					wp_safe_redirect( $redirect );
					exit();
				}else{
					$result = false;
					$EM_Notices->add_error( $EM_Booking->get_errors() );			
					$feedback = $EM_Booking->feedback_message;	
				}	
			}
		}elseif( $_REQUEST['action'] == 'booking_set_status' ){
			em_verify_nonce('booking_set_status_'.$EM_Booking->booking_id);
			if( $EM_Booking->can_manage('manage_bookings','manage_others_bookings') && $_REQUEST['booking_status'] != $EM_Booking->booking_status ){
				if ( $EM_Booking->set_status($_REQUEST['booking_status'], false, true) ){
					if( !empty($_REQUEST['send_email']) ){
						if( $EM_Booking->email() ){
						    if( $EM_Booking->mails_sent > 0 ) {
						        $EM_Booking->feedback_message .= " ".__('Email Sent.','events-manager');
						    }else{
						        $EM_Booking->feedback_message .= " "._x('No emails to send for this booking.', 'bookings', 'events-manager');
						    }
						}else{
							$EM_Booking->feedback_message .= ' <span style="color:red">'.__('ERROR : Email Not Sent.','events-manager').'</span>';
						}
					}
					$EM_Notices->add_confirm( $EM_Booking->feedback_message, true );
					$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
					wp_safe_redirect( $redirect );
					exit();
				}else{
					$result = false;
					$EM_Notices->add_error( $EM_Booking->get_errors() );
					$feedback = $EM_Booking->feedback_message;
				}	
			}
		}elseif( $_REQUEST['action'] == 'booking_set_rsvp_status' ){
			em_verify_nonce('booking_set_rsvp_status_'.$EM_Booking->booking_id);
			$status = $_REQUEST['booking_rsvp_status'] === '' ? null : absint($_REQUEST['booking_rsvp_status']);
			if( $EM_Booking->can_manage('manage_bookings','manage_others_bookings') && $status !== $EM_Booking->booking_rsvp_status ){
				$result = $EM_Booking->set_rsvp_status($status, false, true);
				if ( $result ){
					$EM_Notices->add_confirm( $EM_Booking->feedback_message, true );
					$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
					wp_safe_redirect( $redirect );
					exit();
				}else{
					$EM_Notices->add_error( $EM_Booking->get_errors() );
					$feedback = $EM_Booking->feedback_message;
				}
			}
		}elseif( $_REQUEST['action'] == 'booking_resend_email' ){
			em_verify_nonce('booking_resend_email_'.$EM_Booking->booking_id);
			if( $EM_Booking->can_manage('manage_bookings','manage_others_bookings') ){
				if( $EM_Booking->email(false, true) ){
					$result = true;
				    if( $EM_Booking->mails_sent > 0 ) {
					    $feedback = __('Email Sent.','events-manager');
				        $EM_Notices->add_confirm( $feedback, !defined('DOING_AJAX') );
				    }else{
					    $feedback = _x('No emails to send for this booking.', 'bookings', 'events-manager');
				        $EM_Notices->add_confirm( $feedback, !defined('DOING_AJAX') );
				    }
				}else{
					$EM_Notices->add_error( __('ERROR : Email Not Sent.','events-manager'), !defined('DOING_AJAX') );
					$feedback = $EM_Booking->feedback_message;
				}
				if( !empty($_REQUEST['em_ajax']) ){
					if( $result ){
						echo $feedback;
					}else{
						echo '<span style="color:red">'.$feedback.'</span>';
					}
					die();
				}else{
					$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
					wp_safe_redirect($redirect);
					exit();
				}
			}
		}elseif( $_REQUEST['action'] == 'booking_modify_person' ){
			em_verify_nonce('booking_modify_person_'.$EM_Booking->booking_id);
			if( $EM_Booking->can_manage('manage_bookings','manage_others_bookings') ){
			    global $wpdb;
				if( //save just the booking meta, avoid extra unneccesary hooks and things to go wrong
					$EM_Booking->is_no_user() && $EM_Booking->get_person_post() && 
			    	$EM_Booking->update_meta('registration', $EM_Booking->booking_meta['registration'])
				){
					do_action('em_nouser_booking_details_modified', $EM_Booking);
					$EM_Notices->add_confirm( $EM_Booking->feedback_message, true );
					$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
					wp_safe_redirect( $redirect );
					exit();
				}else{
					$result = false;
					$EM_Notices->add_error( $EM_Booking->get_errors() );			
					$feedback = $EM_Booking->feedback_message;	
				}	
			}
			do_action('em_booking_modify_person', $EM_Event, $EM_Booking);
		}elseif( $_REQUEST['action'] == 'bookings_add_note' && $EM_Booking->can_manage('manage_bookings','manage_others_bookings') ) {
			em_verify_nonce('bookings_add_note');
			if( $EM_Booking->add_note(wp_unslash($_REQUEST['booking_note'])) ){
				$EM_Notices->add_confirm($EM_Booking->feedback_message, true);
				$redirect = !empty($_REQUEST['redirect_to']) ? $_REQUEST['redirect_to'] : em_wp_get_referer();
				wp_safe_redirect( $redirect );
				exit();
			}else{
				$EM_Notices->add_error($EM_Booking->errors);
			}
		}elseif( $_REQUEST['action'] === 'booking_form_summary' ){
			// Authorise against the booking's persisted event before get_post() re-assigns event_id from the request, otherwise an owner could substitute an event they manage to read another booking's summary.
			$can_view_summary = $EM_Booking->can_manage() || ( is_user_logged_in() && !empty($EM_Booking->person->ID) && $EM_Booking->person->ID == get_current_user_id() );
			$EM_Booking->get_post();
			if( $can_view_summary ){
				// wrap in main tag as we only need what's inside by JS
				echo '<main>';
				if( $EM_Booking->get_option('dbem_bookings_summary') ){
					em_locate_template('forms/bookingform/summary.php', true, array('EM_Event' => $EM_Event, 'EM_Booking' => $EM_Booking));
				}
				echo $EM_Booking->output_intent_html();
				echo '</main>';
			}
			exit();
		}
		Archetypes::revert_current();

		if( $result && defined('DOING_AJAX') ){
			$return = array('result'=>true, 'success'=>true, 'message'=>$feedback);
			if( !headers_sent() ) header( 'Content-Type: application/javascript; charset=UTF-8', true ); //add this for HTTP -> HTTPS requests which assume it's a cross-site request
			echo EM_Object::json_encode(apply_filters('em_action_'.$_REQUEST['action'], $return, $EM_Booking));
			die();
		}elseif( !$result && defined('DOING_AJAX') ){
			$return = array('result'=>false, 'success'=>false, 'message'=>$feedback, 'errors'=>$EM_Notices->get_errors());
			if( !headers_sent() ) header( 'Content-Type: application/javascript; charset=UTF-8', true ); //add this for HTTP -> HTTPS requests which assume it's a cross-site request
			echo EM_Object::json_encode(apply_filters('em_action_'.$_REQUEST['action'], $return, $EM_Booking));
			die();
		}
	}elseif( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'booking_add' && !is_user_logged_in() && !em_get_option('dbem_bookings_anonymous')){
		global $EM_Booking;
		$EM_Booking = em_get_booking_request( $_REQUEST['booking_id'] ?? false );
		$EM_Notices->add_error( $EM_Booking->get_option('dbem_booking_feedback_log_in') );
		if( defined('DOING_AJAX') ){
			$return = array('result'=>false, 'success'=>false, 'message'=> $EM_Booking->get_option('dbem_booking_feedback_log_in'), 'errors'=>$EM_Notices->get_errors());
			echo EM_Object::json_encode(apply_filters('em_action_'.$_REQUEST['action'], $return, $EM_Booking));
			die();
		}
	}

	// convert repeating events
	if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'convert_to_recurrence' && !empty($_REQUEST['event_id']) && check_admin_referer('convert_to_recurrence_'.absint($_REQUEST['event_id']), 'nonce') ){
		//Convert event to recurring event
		$EM_Event = em_get_event( $_REQUEST['event_id'] );
		if( !$EM_Event->can_manage('edit_events','edit_others_events') ){
			$EM_Notices->add_error( __('You do not have permission to edit this event.', 'events-manager'), true );
			wp_safe_redirect( em_wp_get_referer() );
		}elseif( $EM_Event->convert_to_recurring() ){
			$message = __('The repeating event has been converted into a recurring event.', 'events-manager');
			$EM_Notices->add_confirm( $message, true );
			$redirect = add_query_arg( array('converted' => $EM_Event->event_id), $EM_Event->get_edit_url() );
			wp_safe_redirect( $redirect );
		}else{
			$EM_Notices->add_error( $EM_Event->errors, true );
			wp_safe_redirect( em_wp_get_referer() );
		}
		exit();
	}
	
	//AJAX call for searches
	if( !empty($_REQUEST['action']) && substr($_REQUEST['action'],0,6) == 'search' ){
		//default search arts
		if( $_REQUEST['action'] == 'search_states' ){
			$results = array();
			$conds = array();
			if( !empty($_REQUEST['country']) ){
				$conds[] = $wpdb->prepare("(location_country = '%s' OR location_country IS NULL )", $_REQUEST['country']);
			}
			if( !empty($_REQUEST['region']) ){
				$conds[] = $wpdb->prepare("( location_region = '%s' )", $_REQUEST['region']);
			}
			$cond = (count($conds) > 0) ? "AND ".implode(' AND ', $conds):'';
			$results = $wpdb->get_col("SELECT DISTINCT location_state FROM " . EM_LOCATIONS_TABLE ." WHERE location_state IS NOT NULL AND location_state != '' $cond ORDER BY location_state");
			if( $_REQUEST['return_html'] ) {
				//quick shortcut for quick html form manipulation
				ob_start();
				?>
				<option value=''><?php echo em_get_option('dbem_search_form_states_label') ?></option>
				<?php
				foreach( $results as $result ){
					echo "<option>{$result}</option>";
				}
				$return = ob_get_clean();
				echo apply_filters('em_ajax_search_states', $return);
				exit();
			}else{
				echo EM_Object::json_encode($results);
				exit();
			}
		}
		if( $_REQUEST['action'] == 'search_towns' ){
			$results = array();
			$conds = array();
			if( !empty($_REQUEST['country']) ){
				$conds[] = $wpdb->prepare("(location_country = '%s' OR location_country IS NULL )", $_REQUEST['country']);
			}
			if( !empty($_REQUEST['region']) ){
				$conds[] = $wpdb->prepare("( location_region = '%s' )", $_REQUEST['region']);
			}
			if( !empty($_REQUEST['state']) ){
				$conds[] = $wpdb->prepare("(location_state = '%s' )", $_REQUEST['state']);
			}
			$cond = (count($conds) > 0) ? "AND ".implode(' AND ', $conds):'';
			$results = $wpdb->get_col("SELECT DISTINCT location_town FROM " . EM_LOCATIONS_TABLE ." WHERE location_town IS NOT NULL AND location_town != '' $cond  ORDER BY location_town");
			if( $_REQUEST['return_html'] ) {
				//quick shortcut for quick html form manipulation
				ob_start();
				?>
				<option value=''><?php echo em_get_option('dbem_search_form_towns_label'); ?></option>
				<?php			
				foreach( $results as $result ){
					echo "<option>$result</option>";
				}
				$return = ob_get_clean();
				echo apply_filters('em_ajax_search_towns', $return);
				exit();
			}else{
				echo EM_Object::json_encode($results);
				exit();
			}
		}
		if( $_REQUEST['action'] == 'search_regions' ){
			$results = array();
			if( !empty($_REQUEST['country']) ){
				$conds[] = $wpdb->prepare("(location_country = '%s' )", $_REQUEST['country']);
			}
			$cond = (count($conds) > 0) ? "AND ".implode(' AND ', $conds):'';
			$results = $wpdb->get_results("SELECT DISTINCT location_region AS value FROM " . EM_LOCATIONS_TABLE ." WHERE location_region IS NOT NULL AND location_region != '' $cond  ORDER BY location_region");
			if( $_REQUEST['return_html'] ) {
				//quick shortcut for quick html form manipulation
				ob_start();
				?>
				<option value=''><?php echo em_get_option('dbem_search_form_regions_label'); ?></option>
				<?php	
				foreach( $results as $result ){
					echo "<option>{$result->value}</option>";
				}
				$return = ob_get_clean();
				echo apply_filters('em_ajax_search_regions', $return);
				exit();
			}else{
				echo EM_Object::json_encode($results);
				exit();
			}
		}
	}
		
	//EM Ajax requests require this flag.
	if( is_user_logged_in() ){
		//Admin operations
		//Specific Oject Ajax
		if( !empty($_REQUEST['em_obj']) && $_REQUEST['em_obj'] == 'em_bookings_events_table' ){
			include_once('admin/bookings/em-events.php');
			em_bookings_events_table();
			exit();
		}
	}
}

/**
 * New action to handle init of EM. It is now being fired in wp_loaded rather than init, the below will either queue up the em_init_actions_start() (previously the em_init_actions() function) if wp_loaded hasn't fired yet, or execute it if added later for whatever reason.
 * @return void
 */
function em_init_actions(){
	if( defined('DOING_AJAX') && DOING_AJAX && !empty($_REQUEST['action']) ){
		//add ajax action filter so it runs after AJAX actions, preventing em_init_actions_start from overriding legit AJAX functions
		add_action('wp_ajax_nopriv_' . $_REQUEST['action'], 'em_init_actions_start', 999999);
		add_action('wp_ajax_' . $_REQUEST['action'], 'em_init_actions_start', 999999);
	} else {
		if ( !did_action( 'wp_loaded' ) ) {
			add_action( 'wp_loaded', 'em_init_actions_start', 11 );
		} else {
			em_init_actions_start();
		}
	}
}
add_action('init', 'em_init_actions', 11);

/**
 * Handles AJAX Searching and Pagination for events, locations, tags and categories
 */
function em_ajax_search_and_pagination(){
	if( !defined('EM_DOING_AJAX') ) define('EM_DOING_AJAX', true);
	$args = array( 'owner' => false, 'pagination' => 1, 'ajax' => true);
	ob_start();
	if( $_REQUEST['action'] == 'search_events' ){
		// new and default way of doing things
		$view = !empty($_REQUEST['view']) && preg_match('/^[a-zA-Z0-9-_]+$/', $_REQUEST['view']) ? $_REQUEST['view'] : 'list';
		$args = EM_Events::get_post_search($args);
        if( em_get_option('dbem_search_form_cookies', true) ) {
	        if ( empty( $_REQUEST['clear_search'] ) ) {
		        // clear known unecesssary and empty keys
		        $cookie_args = array();
		        $known_args  = array( 'action', 'view_id', 'view', 'ajax', 'owner', 'pagination' );
		        foreach ( $args as $k => $v ) {
			        if ( !in_array( $k, $known_args ) && ! empty( $v ) ) {
				        $cookie_args[ $k ] = $v;
			        }
		        }
                // deal with scope in case empty
                if ( !empty($cookie_args['scope']) && !empty($_REQUEST['scope']) && is_array($_REQUEST['scope']) && empty($_REQUEST['scope'][0]) && empty($_REQUEST['scope'][1]) ) {
                    unset($cookie_args['scope']);
                }
	        }
            if( !empty($cookie_args) ) {
                setcookie( 'em_search_events', base64_encode( json_encode( $args ) ), time() + MONTH_IN_SECONDS, COOKIEPATH, COOKIE_DOMAIN, is_ssl(), true );
	        } else {
		        setcookie( 'em_search_events', null, time() - 30, COOKIEPATH, COOKIE_DOMAIN, is_ssl(), true );
                unset($_COOKIE['em_search_events']);
	        }
        }
		$search_args = em_get_search_form_defaults($args);
		$args = array_merge($search_args, $args);
		$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_events_default_limit');
		em_output_events_view( $args, $view );
	}elseif( $_REQUEST['action'] == 'search_locations'){
		// new and default way of doing things
		$view = !empty($_REQUEST['view']) && preg_match('/^[a-zA-Z0-9-_]+$/', $_REQUEST['view']) ? $_REQUEST['view'] : 'list';
		$args = EM_Locations::get_post_search($args);
		$search_args = em_get_search_form_defaults($args);
		// so eventful searches show upcoming event locations only
		$args['scope'] = !empty($args['eventful']) ? 'future' :'all' ;
		$args = array_merge($search_args, $args);
		switch( $view ){
			case 'list':
				$args = EM_Locations::get_post_search($args);
				$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_locations_default_limit');
				break;
			case 'map':
				$args = EM_Locations::get_post_search($args);
				$args['width'] = '100%';
				$args['height'] = 0;
				$args['limit'] = 0;
				break;
		}
		em_output_locations_view($args, $view);
	}else{
		if( $_REQUEST['action'] == 'search_events_grouped' && defined('DOING_AJAX') ) {
			// legacy
			$args = EM_Events::get_post_search($args);
            // set cookies if relevant
			if( em_get_option('dbem_search_form_cookies', true) ) {
				if ( empty( $_REQUEST['clear_search'] ) ) {
					setcookie( 'em_search_events', base64_encode( json_encode( $args ) ), time() + MONTH_IN_SECONDS, COOKIEPATH, COOKIE_DOMAIN, is_ssl(), true );
				} else {
					setcookie( 'em_search_events', null, time() - 30, COOKIEPATH, COOKIE_DOMAIN, is_ssl(), true );
				}
			}
            // set limit and output template
			$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_events_default_limit');
			em_locate_template('templates/events-list-grouped.php', true, array('args' => $args)); //if successful, this template overrides the settings and defaults, including search
		}elseif( $_REQUEST['action'] == 'search_tags' && defined('DOING_AJAX') ){
			$args = EM_Tags::get_post_search($args);
			$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_tags_default_limit');
			em_locate_template('templates/tags-list.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
		}elseif( $_REQUEST['action'] == 'search_cats' && defined('DOING_AJAX') ){
			$args = EM_Categories::get_post_search($args);
			$args['limit'] = !empty($args['limit']) ? $args['limit'] : em_get_option('dbem_categories_default_limit');
			em_locate_template('templates/categories-list.php', true, array('args'=>$args)); //if successful, this template overrides the settings and defaults, including search
		}
	}
	echo apply_filters('em_ajax_'.$_REQUEST['action'], ob_get_clean(), $args);
	exit();
}
add_action('wp_ajax_nopriv_search_events','em_ajax_search_and_pagination');
add_action('wp_ajax_search_events','em_ajax_search_and_pagination');
add_action('wp_ajax_nopriv_search_events_grouped','em_ajax_search_and_pagination');
add_action('wp_ajax_search_events_grouped','em_ajax_search_and_pagination');
add_action('wp_ajax_nopriv_search_locations','em_ajax_search_and_pagination');
add_action('wp_ajax_search_locations','em_ajax_search_and_pagination');
add_action('wp_ajax_nopriv_search_tags','em_ajax_search_and_pagination');
add_action('wp_ajax_search_tags','em_ajax_search_and_pagination');
add_action('wp_ajax_nopriv_search_cats','em_ajax_search_and_pagination');
add_action('wp_ajax_search_cats','em_ajax_search_and_pagination');

/*
Added in dev 5.4.4.2 but may delete in favour of Google autocomplete service
function em_ajax_geocoding_search(){
	//GeoNames
	if( !empty($_REQUEST['q']) && em_get_option('dbem_geonames_username') ){
		$url = 'http://api.geonames.org/searchJSON?username='.em_get_option('dbem_geonames_username').'&featureClass=p&style=full&maxRows=12&q=' . rawurlencode(utf8_encode($_REQUEST['q']));
		if( !empty($_REQUEST['country']) ){
			$url .= '&countryBias=' . rawurlencode(utf8_encode($_REQUEST['country']));	
		}
		if( !empty($_REQUEST['callback']) ){
			$url .= '&callback=' . rawurlencode(utf8_encode($_REQUEST['callback']));
		}
	};
	if( !empty($url) ){
		$return = wp_remote_get($url);
		if( !is_wp_error($return) ){
			echo $return['body'];
			die();
		}
	}
	//If nothing is set up
	$default = array('geonames'=>array(array('name'=>'No Information Available','lat'=>'', 'lng'=>'', 'adminName1'=> '', 'countryName'=>'')));
	echo json_encode($default);
	die();
}
add_action('wp_ajax_nopriv_geocoding_search','em_ajax_geocoding_search');
add_action('wp_ajax_geocoding_search','em_ajax_geocoding_search');
*/
?>