<?php

use EM\Event\Timeranges;

/**
 * Deals with the booking info for an event
 *
 * @property EM_Booking[] $bookings
 * @property EM_Event $event
 * @property int $event_id;
 */
class EM_Bookings extends EM_Object implements Iterator, ArrayAccess {
	
	/**
	 * Array of EM_Booking objects for a specific event
	 * @var EM_Booking[]
	 */
	protected $bookings;
	/**
	 * @var EM_Tickets
	 */
	var $tickets;
	/**
	 * @var int
	 */
	protected $event_id;
	/**
	 * @var int
	 */
	var $timeslot_id;
	/**
	 * How many spaces this event has
	 * @var int
	 */
	var $spaces;
	/**
	 * @var bool Flag for Multilingual functionality, to help prevent unnecessary reloading of this object if already 'translated'
	 */
	var $translated;
	/**
	 * If flag is true, a registration will be attempted when booking whether the user is logged in or not. Used in cases such as manual bookings (a Pro feature) and should only be enabled during manipulation by an event admin.
	 * @var bool
	 */
	public static $force_registration;
	/**
	 * If flag is true, bookings and forms will not impose restrictions for roles. Future iterations will remove restrictions on dates, space capacity, etc. This is mainly for use by event admins such as for a manual booking (a Pro feature). 
	 * @var bool
	 */
	public static $disable_restrictions = false;
	
	protected $booked_spaces;
	protected $pending_spaces;
	protected $available_spaces;
	protected $reserved_spaces;
	protected $status_counts = [];
	
	/**
	 * Reference to the event object if this object contains bookings of a specific event only
	 * @var EM_Event
	 */
	protected $event;
	
	/**
	 * Creates an EM_Bookings instance, currently accepts an EM_Event object (gets all bookings for that event) or array of any EM_Booking objects, which can be manipulated in bulk with helper functions.
	 * @param EM_Event $event
	 * @return null
	 */
	function __construct( $data = false ){
		if( is_object($data) && get_class($data) == "EM_Event" ){ //Creates a blank bookings object if needed
			$this->event_id = $data->event_id;
			$this->event = $data;
			if ( $this->event->timeslot_id ) {
				$this->timeslot_id = absint($this->event->timeslot_id);
			}
		}elseif( is_array($data) ){
			foreach( $data as $EM_Booking ){
				if( $EM_Booking instanceof EM_Booking ){
					$this->bookings[] = $EM_Booking;
				}
			}
		}
	}
	
	public function __get( $prop ){
		if( $prop == 'bookings' ){
			return $this->load();
		}elseif( $prop == 'event' ){
			return $this->get_event();
		} elseif ( $prop === 'event_id' ) {
			return $this->get_event_uid();
		}
		return parent::__get( $prop );
	}
	
	public function __set( $var, $val ){
		if( $var == 'bookings' ){
			if( is_array($val) ){
				$this->bookings = $val;
			}else{
				$this->bookings = null;
			}
		}elseif( $var == 'event' && $val instanceof EM_Event ){
			$this->event = $val;
			$this->set_event_id( $this->event->event_id );
		} elseif ( $var === 'event_id' ) {
			$this->set_event_id( $val );
		}
		parent::__set( $var, $val );
	}
	
	/**
	 * Counter-intuitive but __isset works against isset() but for our purpose it's mainly aimed at empty() calls, which also references this function.
	 * We don't expect nor do we want people using isset on things like the bookings property.
	 * Assume every property in EM_Bookings isset() == true and avoid it, only use empty() calls to check if there's anything in that property.
	 * Therefore, we'd return !empty($this->bookings) because if there's bookings, isset() should return true 
	 * @param string $var
	 * @return boolean
	 */
	public function __isset( $prop ){
		//if isset is invoked on $EM_Bookings->bookings then we'll assume it's only set if the bookings property is empty, not if null.
		if( $prop == 'bookings' ){
			return $this->bookings !== null;
		}elseif ($prop == 'event') {
			return !empty($this->event);
		}
		return parent::__isset( $prop );
	}
	
	public function load( $refresh = false ){
		if( $refresh || $this->bookings === null ){
			global $wpdb;
			$bookings = $this->bookings = array();
			if( $this->event_id > 0 ){
				$timeslot = "";
				if ( $this->get_event()->is_recurring( true ) ) {
					$subquery = "SELECT event_id FROM " . EM_EVENTS_TABLE . " WHERE recurrence_set_id IN ( SELECT recurrence_set_id FROM " . EM_EVENT_RECURRENCES_TABLE . " WHERE event_id = '{$this->event_id}' )";
					$sql = "SELECT * FROM ". EM_BOOKINGS_TABLE ." WHERE event_id IN ( $subquery ) ORDER BY booking_date";
				} else {
					if ( $this->event->timeslot_id ) {
						$timeslot = " AND timeslot_id = '". absint($this->event->timeslot_id) . "'";
					}
					$sql = "SELECT * FROM ". EM_BOOKINGS_TABLE ." WHERE event_id ='{$this->event_id}' $timeslot ORDER BY booking_date";
				}
				$bookings = $wpdb->get_results($sql, ARRAY_A);
			}
			foreach ($bookings as $booking){
				$this->bookings[] = em_get_booking($booking);
			}
		}
		return apply_filters('em_bookings_load', $this->bookings);
	}
	
	/**
	 * Add a booking into this event (or add spaces if person already booked this). We assume at this point that the booking has already been validated usin $EM_Booking->validate()
	 * @param EM_Booking $EM_Booking
	 * @return boolean
	 */
	/**
	 * Acquire a short-lived MySQL advisory lock scoped to one event's bookings, so the availability check and the insert run as one critical section and concurrent requests can't each pass a stale space count and oversell. Best-effort: returns false if the lock can't be taken, in which case callers fall back to a non-atomic re-check rather than blocking a legitimate booking.
	 * @param int $event_id
	 * @param int $timeout seconds to wait for the lock
	 * @return bool whether the lock was acquired
	 */
	public static function acquire_lock( $event_id, $timeout = 10 ){
		global $wpdb;
		if( empty($event_id) ) return false;
		$got = $wpdb->get_var( $wpdb->prepare( 'SELECT GET_LOCK(%s, %d)', self::lock_name($event_id), $timeout ) );
		return $got === '1' || $got === 1;
	}

	/**
	 * Release a lock previously taken with acquire_lock(). Safe to call only when acquire_lock() returned true.
	 * @param int $event_id
	 */
	public static function release_lock( $event_id ){
		global $wpdb;
		if( empty($event_id) ) return;
		$wpdb->get_var( $wpdb->prepare( 'SELECT RELEASE_LOCK(%s)', self::lock_name($event_id) ) );
	}

	/**
	 * GET_LOCK names are global to the MySQL server and capped at 64 characters, so namespace by database and table prefix: a collision between unrelated installs on a shared server would only cost extra serialization, never correctness.
	 * @param int $event_id
	 * @return string
	 */
	protected static function lock_name( $event_id ){
		global $wpdb;
		return 'em_bk_' . md5( DB_NAME . '|' . $wpdb->prefix . '|' . absint($event_id) );
	}

	function add( $EM_Booking ){
		//Save the booking
		$email = false;
		//set status depending on approval settings
		if( empty($EM_Booking->booking_status) ){ //if status is not set, give 1 or 0 depending on approval settings
			$EM_Booking->booking_status = em_get_option('dbem_bookings_approval') ? 0:1;
		}
		// Re-check availability against a fresh count, holding a per-event lock across the check and the insert so two concurrent bookings can't both pass a stale space count. The caller already validated, but that count can be stale by the time we save. Skipped when restrictions are disabled (e.g. manual bookings, which may intentionally overbook).
		$lock_event_id = $EM_Booking->get_event_id();
		$booking_locked = self::acquire_lock( $lock_event_id );
		if( !self::$disable_restrictions && $EM_Booking->get_event()->get_bookings()->get_available_spaces(true) < $EM_Booking->get_spaces() ){
			if( $booking_locked ) self::release_lock( $lock_event_id );
			$EM_Booking->add_error( $EM_Booking->get_option('dbem_booking_feedback_full') );
			$this->feedback_message = $EM_Booking->get_option('dbem_booking_feedback_full');
			$this->errors = array_merge( $this->errors, $EM_Booking->get_errors() );
			return apply_filters('em_bookings_add', false, $EM_Booking);
		}
		$result = $EM_Booking->save(false);
		if( $booking_locked ) self::release_lock( $lock_event_id );
		if ( $result ){
			//Success
		    do_action('em_bookings_added', $EM_Booking);
			if( $this->bookings === null ) $this->bookings = array();
			$this->bookings[] = $EM_Booking;
			$email = $EM_Booking->email();
			if( em_get_option('dbem_bookings_approval') == 1 && $EM_Booking->booking_status == 0){
				$this->feedback_message = em_get_option('dbem_booking_feedback_pending');
			}else{
				$this->feedback_message = em_get_option('dbem_booking_feedback');
			}
			if( !$email ){
				$EM_Booking->email_not_sent = true;
				$this->feedback_message .= ' '.em_get_option('dbem_booking_feedback_nomail');
				if( current_user_can('activate_plugins') ){
					if( count($EM_Booking->get_errors()) > 0 ){
						$this->feedback_message .= '<br/><strong>Errors:</strong> (only admins see this message)<br/><ul><li>'. implode('</li><li>', $EM_Booking->get_errors()).'</li></ul>';
					}else{
						$this->feedback_message .= '<br/><strong>No errors returned by mailer</strong> (only admins see this message)';
					}
				}
			}
			return apply_filters('em_bookings_add', true, $EM_Booking);
		}else{
			//Failure
			$this->errors[] = "<strong>".em_get_option('dbem_booking_feedback_error')."</strong><br />". implode('<br />', $EM_Booking->errors);
		}
		return apply_filters('em_bookings_add', false, $EM_Booking);
	}

	/**
	 * Get POST data and create a booking for each ticket requested. If successful, a booking object is returned, false if not.
	 * @return false|object
	 */
	function add_from_post(){
		$EM_Booking = new EM_booking();
		$result = $EM_Booking->get_post();
		if($result){
			$result = $this->add($EM_Booking);
			if($result){
				$result = $EM_Booking;
			}
			$this->feedback_message = sprintf(__('%s created.','events-manager'),__('Booking','events-manager'));
		}else{
			$this->errors = array_merge($this->errors, $EM_Booking->errors);
		}
		return apply_filters('em_bookings_add_from_post',$result,$EM_Booking,$this);
	}

	public function get_booking_vars() {
		$EM_Booking = $this->has_booking();
		$template_vars = array(
			'EM_Event' => $this->get_event(),
			'tickets_count' =>  count($this->get_tickets()->tickets),
			'available_tickets_count' =>  count( $this->get_available_tickets() ),
			//decide whether user can book, event is open for bookings etc.
			'can_book' =>  is_user_logged_in() || (em_get_option('dbem_bookings_anonymous') && !is_user_logged_in()),
			'is_open' =>  $this->is_open(), //whether there are any available tickets right now
			'is_free' =>  $this->get_event()->is_free(),
			'show_tickets' =>  true,
			'id' =>  $this->get_event_uid(),
			'already_booked' => is_object( $EM_Booking ) && $EM_Booking->booking_id > 0,
			'EM_Booking' => $this->get_intent_default(), // get the booking intent if not supplied already
		);
		return $template_vars;
	}
	
	/**
	 * Gets an initial booking intent object, not saved to DB but containing the minimum information required to make a booking, including required spaces already selected (if set by event owner).
	 * If the booking intent has no value, i.e. no spaces to be booked initially, then the sapces will be 0
	 * @return EM_Booking
	 */
	public function get_intent_default(){
		// calculate minimum number of spaces booked required (i.e. non-optional tickets) and create a booking if there is one, otherwise return null as no booking necessary yet
		$EM_Event = $this->get_event();
		$EM_Booking = new EM_Booking();
		$EM_Booking->booking_status = 10; // booking intent status
		if( $EM_Event->event_id ){
			$EM_Booking->event_id = $EM_Event->event_id;
			$EM_Tickets = $this->get_available_tickets();
			$is_single_ticket = $EM_Tickets->count() == 1;
			foreach( $EM_Tickets as $EM_Ticket ){
				$spaces = !empty($_REQUEST['em_tickets'][$EM_Ticket->ticket_id]['spaces']) ? $_REQUEST['em_tickets'][$EM_Ticket->ticket_id]['spaces']:0;
				$min_spaces = $EM_Ticket->get_spaces_minimum();
				// if ticket spaces defined by post, or if a ticket selection is required (by being only ticket or required)
				if( $spaces > 0 ||  $is_single_ticket || $EM_Ticket->required ) {
					// make sure we meet the minimum
					$spaces = $min_spaces > $spaces ? $min_spaces : $spaces;
				}
				// impose ticket spaces if required
				if( $spaces > 0 ){
					$EM_Ticket_Bookings = $EM_Booking->get_tickets_bookings()->get_ticket_bookings($EM_Ticket->ticket_id);
					for( $i = 0; $i < $spaces; $i++ ){
						$ticket_booking = array(
							'ticket' => $EM_Ticket,
							'booking' => $EM_Booking,
							'ticket_booking_spaces' => 1,
						);
						$EM_Ticket_Booking = new EM_Ticket_Booking($ticket_booking);
						$EM_Ticket_Booking->calculate_price( true );
						$EM_Ticket_Bookings->tickets_bookings[ $EM_Ticket_Booking->ticket_uuid ] = $EM_Ticket_Booking;
					}
				}
			}
			if( $EM_Booking->get_spaces(true) > 0 ){
				$EM_Booking->get_price();
			}
		}
		return apply_filters('em_bookings_get_intent_default', $EM_Booking);
	}

	/**
	 * Returns the base event_id, or alternatively the event ID including timeslot ID if $base_only is set to false. Useful for external code looking only for the numeric event_id, used internally for getting the full event ID including timeslot
	 *
	 * @param $base_only
	 *
	 * @return false|float|int|mixed|string
	 */
	function get_event_id ( $base_only = true ) {
		$event_id = $this->event_id;
		if ( !$base_only && $this->timeslot_id ) {
			$event_id .= ':' . $this->timeslot_id;
		}
		return $event_id;
	}

	/**
	 * Returns the full event ID including the timeslot ID
	 * @return string
	 */
	function get_event_uid() {
		return $this->get_event_id( false );
	}

	/**
	 * Sets the event ID and also the timeslot ID if supplied in UID format
	 * @param $event_id
	 *
	 * @return void
	 */
	public function set_event_id( $event_id ) {
		if ( preg_match('/^(\d+):(\d+)$/', $event_id, $matches) ) {
			$this->event_id = absint($matches[1]);
			$this->timeslot_id = absint($matches[2]);
		} elseif ( is_numeric( $event_id )) {
			$this->event_id = absint($event_id);
		}
	}
	
	/**
	 * Smart event locator, saves a database read if possible. Note that if an event doesn't exist, a blank object will be created to prevent duplicates.
	 */
	function get_event(){
		if( $this->event && $this->event->event_id == $this->get_event_uid() ){
			return $this->event;
		}
		global $EM_Event;
		if( is_object($EM_Event) && $EM_Event->event_id == $this->get_event_uid() ){
			$this->event = $EM_Event;
			return $EM_Event;
		}else{
			if( is_numeric($this->event_id) && $this->event_id > 0 ){
				$this->event = em_get_event( $this->get_event_uid() );
				return $this->event;
			}elseif( is_array($this->bookings) ){
				foreach($this->bookings as $EM_Booking){
					/* @var $EM_Booking EM_Booking */
					return em_get_event( $EM_Booking->event_id );
				}
			}
		}
		return em_get_event($this->event_id);
	}
	
	/**
	 * Retrieve and save the bookings belonging to instance. If called again will return cached version, set $force_reload to true to create a new EM_Tickets object.
	 * @param boolean $force_reload
	 * @return EM_Tickets
	 */
	function get_tickets( $force_reload = false ){
		if( !is_object($this->tickets) || $force_reload ){
			$this->tickets = new EM_Tickets($this->get_event());
			if( em_get_option('dbem_bookings_tickets_single') && count($this->tickets->tickets) == 1 ){
				//if in single ticket mode, then the event booking cut-off is the ticket end date
		    	$EM_Ticket = $this->tickets->get_first();
		    	$EM_Event = $this->get_event();
		    	//if ticket has cut-off date, that should take precedence as we save the ticket cut-off date/time to the event in single ticket mode
		    	if( !empty($EM_Ticket->end) ){
		    		//if ticket end dates are set, move to event
		    		$EM_Event->event_rsvp_date = $EM_Ticket->end()->format('Y-m-d');
		    		$EM_Event->event_rsvp_time = $EM_Ticket->end()->format('H:i:00');
		    		if( $EM_Event->is_recurring( true ) && !empty($EM_Ticket->ticket_meta['recurrences']) ){
		    			$EM_Event->recurrence_rsvp_days = $EM_Ticket->ticket_meta['recurrences']['end_days'];		    			
		    		}
		    	}else{
		    		//if no end date is set, use event end date (which will have defaulted to the event start date
		    		if( !$EM_Event->is_recurring( true ) ){
		    			//save if we have a valid rsvp end date
		    			if( $EM_Event->rsvp_end()->valid ){
						    $EM_Ticket->ticket_end = $EM_Event->rsvp_end()->getDateTime();
					    }
		    		}else{
			    		if( !isset($EM_Ticket->ticket_meta['recurrences']['end_days']) ){
			    			//for recurrences, we take the recurrence_rsvp_days and feed it into the ticket meta that'll handle recurrences
			    			$EM_Ticket->ticket_meta['recurrences']['end_days'] = !empty($EM_Event->recurrence_rsvp_days) ? $EM_Event->recurrence_rsvp_days : 0;
			    			if( !isset($EM_Ticket->ticket_meta['recurrences']['end_time']) ){
			    				iF( empty($EM_Event->event_rsvp_time) ){
								    $EM_Ticket->ticket_meta['recurrences']['end_time'] = $EM_Event->start()->getTime();
							    }else{
								    $EM_Ticket->ticket_meta['recurrences']['end_time'] = $EM_Event->event_rsvp_time;
							    }
			    			}
						    $EM_Ticket->ticket_end = $EM_Event->start()->format('Y-m-d') . $EM_Ticket->ticket_meta['recurrences']['end_time'];
			    		}
		    		}
		    	}
			}
		}else{
			$this->tickets->event_id = $this->event_id;
		}
		return apply_filters('em_bookings_get_tickets', $this->tickets, $this);
	}
	
	/**
	 * Returns EM_Tickets object with available tickets
	 * @param boolean $include_member_tickets - if set to true, member-ony tickets will be considered available even if logged out
	 * @return EM_Tickets
	 */
	function get_available_tickets( $include_member_tickets = false ){
		$tickets = array();
		foreach ($this->get_tickets() as $EM_Ticket){
			if( static::$disable_restrictions || $EM_Ticket->is_available($include_member_tickets) ){
				//within time range
				if( static::$disable_restrictions || $EM_Ticket->get_available_spaces() > 0 ){
					$tickets[] = $EM_Ticket;
				}
			}
		}
		$EM_Tickets = new EM_Tickets($tickets);
		return apply_filters('em_bookings_get_available_tickets', $EM_Tickets, $this);
	}
	
	/**
	 * Deprecated - was never used and therefore is deprecated, will always return an array() and will eventually be removed entirely.
	 * @return array
	 */
	function get_user_list(){
		return array();
	}
	
	/**
	 * Returns a boolean indicating whether this ticket exists in this bookings context.
	 * @return bool 
	 */
	function ticket_exists($ticket_id){
		$EM_Tickets = $this->get_tickets();
		foreach( $EM_Tickets->tickets as $EM_Ticket){
			if($EM_Ticket->ticket_id == $ticket_id){
				return apply_filters('em_bookings_ticket_exists',true, $EM_Ticket, $this);
			}
		}
		$EM_Ticket = new EM_Ticket();
		$EM_Ticket->ticket_id = $ticket_id;
		return apply_filters('em_bookings_ticket_exists',false, $EM_Ticket, $this);
	}
	
	function has_space( $include_member_tickets = false ){
		// recurrences we cannot assume there is no space
		// TOOD [Recurrences] Fina days to quickly check if there are any spaces available for all recurrences
		if ( $this->get_event()->is_recurring() ) return true;
		return count($this->get_available_tickets( $include_member_tickets )->tickets) > 0;
	}
	
	function has_open_time(){
	    $return = false;
	    $EM_Event = $this->get_event();
		if( $EM_Event->event_active_status !== 0 ){
			if( $EM_Event->rsvp_end()->getTimestamp() > time()){
				$return = true;
			}
		}
	    return $return;
	}
	
	function is_open($include_member_tickets = false){
		//TODO extend booking options
		if( static::$disable_restrictions ){
			$return = true;
		}else{
			// with recurrences, we need to go through individual recurrences and see if any are open
			$return = $this->has_open_time() && $this->has_space($include_member_tickets);
		}
		return apply_filters('em_bookings_is_open', $return, $this, $include_member_tickets);
	}
	
	/**
	 * Delete bookings on this id
	 * @return boolean
	 */
	function delete(){
		global $wpdb;
		$booking_ids = $event_ids = $event_uids = array();
		if( !empty($this->bookings) ){
			//get the booking ids tied to this event or preloaded into this object
			foreach( $this->bookings as $EM_Booking ){
				$booking_ids[] = $EM_Booking->booking_id;
				$event_uids[] = $EM_Booking->get_event_uid();
			}
			$result_tickets = true;
			$result = true;
			if( count($booking_ids) > 0 ){
				// before deleting, get all the event ids associated with these bookings, in case we need to do any checks on those events via filters
				$event_ids = $wpdb->get_col("SELECT event_id FROM ". EM_BOOKINGS_TABLE ." WHERE booking_id IN (".implode(',',$booking_ids).");");
				//Delete bookings and ticket bookings
				$result_tickets = $wpdb->query("DELETE FROM ". EM_TICKETS_BOOKINGS_TABLE ." WHERE booking_id IN (".implode(',',$booking_ids).");");
				$result = $wpdb->query("DELETE FROM ".EM_BOOKINGS_TABLE." WHERE booking_id IN (".implode(',',$booking_ids).")");
			}
		}elseif( !empty($this->event_id) ){
			//faster way of deleting bookings for an event circumventing the need to load all bookings if it hasn't been loaded already
			$event_id = absint($this->event_id);
			$event_ids = array($event_id);
			$timeslot = !empty($this->timeslot_id) ? ' AND timeslot_id = ' . absint($this->timeslot_id) : '';
			if( !empty($this->timeslot_id) ) $event_uids[] = $event_id . ':' . absint($this->timeslot_id);
			$booking_ids = $wpdb->get_col("SELECT booking_id FROM ".EM_BOOKINGS_TABLE." WHERE event_id = '$event_id' $timeslot");
			$result_tickets = $wpdb->query("DELETE FROM ". EM_TICKETS_BOOKINGS_TABLE ." WHERE booking_id IN (SELECT booking_id FROM ".EM_BOOKINGS_TABLE." WHERE event_id = '$event_id' $timeslot)");
			$result = $wpdb->query("DELETE FROM ".EM_BOOKINGS_TABLE." WHERE event_id = '$event_id' $timeslot");
			if ( $this->get_event()->is_recurring( true ) ) {
				$this->get_event()->get_recurrence_sets()->delete_bookings();
			}
		}else{
			//we have not bookings loaded to delete, nor an event to delete bookings from, so bookings are considered 'deleted' since there's nothing ot delete
			$result = $result_tickets = true;
		}
		// this path never runs EM_Booking::delete(), so the events it just emptied are dropped from the cache here
		EM_Event::flush_cache( array_merge($event_ids, $event_uids) );
		do_action('em_bookings_deleted', $result, $booking_ids, $event_ids);
		return apply_filters('em_bookings_delete', $result !== false && $result_tickets !== false, $booking_ids, $this, $event_ids);
	}

	
	/**
	 * Will approve all supplied booking ids, which must be in the form of a numeric array or a single number.
	 * @param array|int $booking_ids
	 * @return boolean
	 */
	function approve( $booking_ids ){
		$this->set_status(1, $booking_ids);
		return false;
	}
	
	/**
	 * Will reject all supplied booking ids, which must be in the form of a numeric array or a single number.
	 * @param array|int $booking_ids
	 * @return boolean
	 */
	function reject( $booking_ids ){
		return $this->set_status(2, $booking_ids);
	}
	
	/**
	 * Will unapprove all supplied booking ids, which must be in the form of a numeric array or a single number.
	 * @param array|int $booking_ids
	 * @return boolean
	 */
	function unapprove( $booking_ids ){
		return $this->set_status(0, $booking_ids);
	}
	
	/**
	 * @param int $status
	 * @param array|int $booking_ids
	 * @param bool $send_email
	 * @param bool $ignore_spaces
	 * @return bool
	 */
	function set_status( $status, $booking_ids, $send_email = true, $ignore_spaces = false ){
		//FIXME status should work with instantiated object
		if( self::array_is_numeric($booking_ids) ){
			//Get all the bookings
			$results = array();
			$mails = array();
			foreach( $booking_ids as $booking_id ){
				$EM_Booking = em_get_booking($booking_id);
				if( !$EM_Booking->can_manage() ){
					$this->feedback_message = __('Bookings %s. Mails Sent.', 'events-manager');
					return false;
				}
				$results[] = $EM_Booking->set_status($status, $send_email, $ignore_spaces);
			}
			if( !in_array('false',$results) ){
				$this->feedback_message = __('Bookings %s. Mails Sent.', 'events-manager');
				return true;
			}else{
				//TODO Better error handling needed if some bookings fail approval/failure
				$this->feedback_message = __('An error occurred.', 'events-manager');
				return false;
			}
		}elseif( is_numeric($booking_ids) || is_object($booking_ids) ){
			$EM_Booking = ( $booking_ids instanceof EM_Booking ) ? $booking_ids : em_get_booking($booking_ids);
			$result = $EM_Booking->set_status($status);
			$this->feedback_message = $EM_Booking->feedback_message;
			return $result;
		}
		return false;	
	}
	

	/**
	 * Get the total number of spaces this event has. This will show the lower value of event global spaces limit or total ticket spaces. Setting $force_refresh to true will recheck spaces, even if previously done so.
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_spaces( $force_refresh=false ){
		if ( $this->get_event()->event_active_status === 0 ) {
			$this->spaces = 0;
		} else {
			if ( $force_refresh || $this->spaces == 0 ) {
				$this->spaces = $this->get_tickets()->get_spaces();
			}
			//check overall events cap
			if ( ! empty( $this->get_event()->event_spaces ) && $this->get_event()->event_spaces < $this->spaces ) {
				$this->spaces = $this->get_event()->event_spaces;
			}
		}
		return apply_filters('em_booking_get_spaces',$this->spaces,$this);
	}
	
	/**
	 * Returns number of available spaces for this event. If approval of bookings is on, will include pending bookings depending on em option.
	 * @return int
	 */
	function get_available_spaces( $force_refresh = false ) {
		if ( $this->get_event()->event_active_status === 0 ) {
			$available_spaces = 0;
		}else{
			$spaces = $this->get_spaces($force_refresh);
			$available_spaces = $spaces - $this->get_booked_spaces($force_refresh);
			$available_spaces -= $this->get_reserved_spaces($force_refresh);
		}
		// @deprecated use em_bookings_get_available_spaces instead
		$available_spaces = apply_filters('em_booking_get_available_spaces', $available_spaces, $this);
		return apply_filters('em_bookings_get_available_spaces', $available_spaces, $this, $force_refresh);
	}

	/**
	 * Returns number of booked spaces for this event. If approval of bookings is on, will return number of booked confirmed spaces.
	 * @return int
	 */
	function get_booked_spaces($force_refresh = false){
		if( $this->booked_spaces === null || $force_refresh ){
			$status_cond = !em_get_option('dbem_bookings_approval') ? '0,1' : '1';
			$booked_spaces = $this->get_status_count( $status_cond, $force_refresh );
			$this->booked_spaces = $booked_spaces > 0 ? $booked_spaces : 0;
			$this->booked_spaces = apply_filters('em_bookings_get_booked_spaces', $this->booked_spaces, $this, $force_refresh);
		}
		return $this->booked_spaces;
	}

	/**
	 * Gets number of reserved spaces. Will return 0 if booking approval is not enabled.
	 * @return int
	 */
	function get_reserved_spaces( $force_refresh = false ) {
		if( em_get_option('dbem_bookings_approval') && em_get_option('dbem_bookings_approval_reserved') ) {
			if ( $this->reserved_spaces === null || $force_refresh ) {
				$reserved_spaces = $this->get_status_count( 0, $force_refresh );
				$this->reserved_spaces = $reserved_spaces > 0 ? $reserved_spaces : 0;
				// run here, once unless forced to refresh
				$this->reserved_spaces = apply_filters('em_bookings_get_reserved_spaces', $this->reserved_spaces, $this, $force_refresh);
			}
			return $this->reserved_spaces;
		}
		// if we reach here, always run the filter to allow other bookings to override other reserved spaces with bookings of different status
		return apply_filters('em_bookings_get_reserved_spaces', $this->reserved_spaces ?? 0, $this, $force_refresh);
	}
	
	/**
	 * Gets number of pending spaces awaiting approval. Will return 0 if booking approval is not enabled.
	 * @return int
	 */
	function get_pending_spaces( $force_refresh = false ){
		if( em_get_option('dbem_bookings_approval') ) {
			if ( $this->pending_spaces === null || $force_refresh ) {
				$pending_spaces = $this->get_status_count( 0, $force_refresh );
				$this->pending_spaces = $pending_spaces > 0 ? $pending_spaces : 0;
				$this->pending_spaces = apply_filters('em_bookings_get_pending_spaces', $this->pending_spaces, $this, $force_refresh);
			}
			return $this->pending_spaces;
		}
		// if we reach here, always run the filter to allow other bookings to override other reserved spaces with bookings of different status
		return apply_filters('em_bookings_get_pending_spaces', 0, $this, $force_refresh);
	}

	public function get_status_count( $status, $force_refresh = false ) {
		global $wpdb;
		// clean up $status
		if ( is_array($status) ) {
			$status = implode(',', $status);
		}
		$status = str_replace(' ', '', $status);
		// run if $status is clean
		if ( preg_match('/^[0-9,]+$/D', $status) ) {
			if ( !isset( $this->status_counts[ $status ] ) || $force_refresh ) {
				if ( $this->get_event()->is_recurring( true ) ) {
					$subquery = "SELECT event_id FROM " . EM_EVENTS_TABLE . " WHERE recurrence_set_id IN ( SELECT recurrence_set_id FROM " . EM_EVENT_RECURRENCES_TABLE . " WHERE event_id = '{$this->event_id}' )";
					$sql = "SELECT SUM(booking_spaces) FROM " . EM_BOOKINGS_TABLE . " WHERE booking_status IN ( $status ) AND event_id IN ( $subquery )";
				} else {
					$timeslot = !empty($this->timeslot_id) ? ' AND timeslot_id = ' . absint( $this->timeslot_id ) : '';
					$sql = 'SELECT SUM(booking_spaces) FROM ' . EM_BOOKINGS_TABLE . " WHERE booking_status IN ( $status ) AND event_id=" . absint( $this->event_id ) . $timeslot;
				}
				$this->status_counts[ $status ] =  (int) $wpdb->get_var( $sql );
			}
		}
		return apply_filters('em_bookings_get_status_count', $this->status_counts[ $status ] ?? 0, $this, $status, $force_refresh);
	}
	
	/**
	 * Gets booking objects (not spaces). If booking approval is enabled, only the number of approved bookings will be shown.
	 * @param boolean $all_bookings If set to true, then all bookings with any status is returned
	 * @return EM_Bookings
	 */
	function get_bookings( $all_bookings = false ){
		$confirmed = array();
		foreach ( $this->load() as $EM_Booking ){
			if( $EM_Booking->booking_status == 1 || ( $EM_Booking->get_option('dbem_bookings_approval') == 0 && $EM_Booking->booking_status == 0) || $all_bookings ){
				$confirmed[] = $EM_Booking;
			}
		}
		$EM_Bookings = new EM_Bookings($confirmed);
		return $EM_Bookings;		
	}
	
	/**
	 * Get pending bookings. If booking approval is disabled, will return no bookings. 
	 * @return EM_Bookings
	 */
	function get_pending_bookings(){
		if( em_get_option('dbem_bookings_approval') == 0 ){
			return new EM_Bookings();
		}
		$pending = array();
		foreach ( $this->load() as $EM_Booking ){
			if($EM_Booking->booking_status == 0){
				$pending[] = $EM_Booking;
			}
		}
		$EM_Bookings = new EM_Bookings($pending);
		return $EM_Bookings;	
	}	
	
	/**
	 * Get rejected bookings. If booking approval is disabled, will return no bookings. 
	 * @return array EM_Bookings
	 */
	function get_rejected_bookings(){
		$rejected = array();
		foreach ( $this->load() as $EM_Booking ){
			if($EM_Booking->booking_status == 2){
				$rejected[] = $EM_Booking;
			}
		}
		$EM_Bookings = new EM_Bookings($rejected);
		return $EM_Bookings;
	}	
	
	/**
	 * Get cancelled bookings. 
	 * @return array EM_Booking
	 */
	function get_cancelled_bookings(){
		$cancelled = array();
		foreach ( $this->load() as $EM_Booking ){
			if($EM_Booking->booking_status == 3){
				$cancelled[] = $EM_Booking;
			}
		}
		$EM_Bookings = new EM_Bookings($cancelled);
		return $EM_Bookings;
	}
	
	/**
	 * Checks if a person with similar details has booked for this before
	 * @param $person_id
	 * @return EM_Booking
	 */
	function find_previous_booking($EM_Booking){
		//First see if we have a similar person on record that's making this booking
		$EM_Booking->person->load_similar();
		//If person exists on record, see if they've booked this event before, if so return the booking.
		if( is_numeric($EM_Booking->person->ID) && $EM_Booking->person->ID > 0 ){
			$EM_Booking->person_id = $EM_Booking->person->ID;
			foreach ($this->load() as $booking){
				if( $booking->person_id == $EM_Booking->person->ID ){
					return $booking;
				}
			}
		}
		return false;
	}
	
	/**
	 * Checks to see if user has a booking for this event
	 * @param int $user_id
	 */
	function has_booking( $user_id = false ){
		if( $user_id === false ){
			$user_id = get_current_user_id();
		}
		if( is_numeric($user_id) && $user_id > 0 ){
			global $wpdb;
			// get the first booking ID available and return that
			$timeslot = !empty($this->timeslot_id) ? ' AND timeslot_id = ' . absint($this->timeslot_id) : '';
			$sql = $wpdb->prepare('SELECT booking_id FROM '.EM_BOOKINGS_TABLE.' WHERE event_id = %d AND person_id = %d AND booking_status NOT IN (2,3)' . $timeslot, $this->event_id, $user_id);
			$booking_id = $wpdb->get_var($sql);
			if( (int) $booking_id > 0 ){
				$EM_Booking = em_get_booking($booking_id);
				return apply_filters('em_bookings_has_booking', $EM_Booking, $this);
			}
		}
		return apply_filters('em_bookings_has_booking', false, $this);
	}
	
	/**
	 * Generates an SQL statement, which would be used to search for bookings via EM_Bookings::get()
	 *
	 * @param array $args Search args.
	 * @param bool $count Whether to return a count SQL statement or a full SQL statement.
	 * @param bool $filter_args Whether to run $args through filters. ONLY set to false if you ran $args through EM_Bookings::get_default_search() already, this is meant to prevent duplicating the process.
	 *
	 * @return mixed|null
	 */
	public static function get_sql( $args, $count = false, $filter_args = true ){
		global $wpdb;
		$bookings_table = EM_BOOKINGS_TABLE;
		$events_table = EM_EVENTS_TABLE;
		$sql_parts = array(
			'statement' => array(
				'select' => '',
				'join' => '',
				'where' => '',
				'groupby' => '',
				'orderby' => '',
				'limit' => '',
				'offset' => '',
			),
			'data' => array(
				'selectors' => '',
				'joins' => array(),
				'conditions' => array(),
				'orderbys' => array(),
				'groupbys' => array(),
			),
		);
		
		if( $filter_args ) {
			$args = self::get_default_search($args);
		}
		if( !$count ) {
			$sql_parts['statement']['limit'] = ( $args['limit'] && is_numeric($args['limit'])) ? "LIMIT {$args['limit']}" : '';
			$sql_parts['statement']['offset'] = ( $sql_parts['statement']['limit'] != "" && is_numeric($args['offset']) ) ? "OFFSET {$args['offset']}" : '';
		}
		
		//Get the default conditions
		$sql_parts['data']['conditions'] = self::build_sql_conditions($args);
		//Put it all together
		$sql_parts['statement']['where'] = ( count($sql_parts['data']['conditions']) > 0 ) ? " WHERE " . implode ( " AND ", $sql_parts['data']['conditions'] ):'';
		
		//Get ordering instructions
		$accepted_fields = self::get_sql_accepted_fields();
		$sql_parts['data']['orderbys'] = self::build_sql_orderby($args, $accepted_fields['orderby']);
		//Now, build orderby sql
		$sql_parts['statement']['orderby'] = ( count($sql_parts['data']['orderbys']) > 0 ) ? 'ORDER BY '. implode(', ', $sql_parts['data']['orderbys']) : 'ORDER BY booking_date';
		//Selectors
		if( $count ){
			$sql_parts['data']['selectors'] = 'COUNT(DISTINCT '. EM_BOOKINGS_TABLE . '.booking_id)';
		}elseif( is_array($args['array']) ){
			$sql_parts['data']['selectors'] = implode(',', $args['array']);
		}else{
			$sql_parts['data']['selectors'] = '*';
		}
		$sql_parts['statement']['select'] = "SELECT {$sql_parts['data']['selectors']} FROM $bookings_table";
		
		//check if we need to join a location table for this search, which is necessary if any location-specific are supplied, or if certain arguments such as orderby contain location fields
		$table_joins = array();
		$required_tables = EM_MS_GLOBAL ? array(EM_EVENTS_TABLE) : array(); // we always need to join events table to determine blog id when in MS Global mode
		$join_check_queue = array_keys($accepted_fields['tables']);
		do {
			$table_name = reset($join_check_queue); // rather than current, because we keep shifting things off the beginning on each loop, avoiding pointer issues
			$table_data = $accepted_fields['tables'][$table_name];
			$join_table = false;
			if( in_array($table_name, $required_tables) ){
				$join_table = true;
			}
			if( !$join_table ) {
				foreach( $table_data['args'] as $arg ) {
					$ignore_arg_values = array();
					if( isset($table_data['ignore_args'][$arg]) ){
						$ignore_arg_values = is_array($table_data['ignore_args'][$arg]) ? $table_data['ignore_args'][$arg] : array($table_data['ignore_args'][$arg]);
					}
					if ( !empty($args[$arg]) && !in_array( $args[$arg] , $ignore_arg_values ) ) {
						$join_table = true;
					}elseif( !empty($table_data['empty_args'][$arg]) && isset($args[$arg]) ) {
						// it could either be an array of 'legit' empty values vs any empty value meaning this table-specific arg isn't used, therefore no join needed
						if( is_array($table_data['empty_args'][$arg]) ){
							$join_table = in_array($args[$arg], $table_data['empty_args'][$arg]);
						}elseif( $args[$arg] !== $table_data['empty_args'][$arg] ){
							$join_table = true;
						}
					}
					unset($ignore_arg_values);
				}
				//check ordering and grouping arguments for precense of location fields requiring a join
				if( !$join_table ){
					foreach( array('groupby', 'orderby', 'groupby_orderby') as $arg ){
						if( !is_array($args[$arg]) ) continue; //ignore this argument if set to false
						//we assume all these arguments are now array thanks to self::get_search_defaults() cleaning it up
						foreach( $args[$arg] as $field_name ){
							if( !empty($table_data['fields']) && in_array($field_name, $table_data['fields']) ){
								$join_table = true;
								break; //we join, no need to keep searching
							}elseif( !empty($table_data['orderby_extras'][$field_name]) ){ // TODO this will never be reached because orderby_extras are commented out further down... experimental - 3rd pty developers - don't try to extend!
								// account for meta joins, which requires a cheeky condition insertion here instead
								$joined_tables[$table_name] = $wpdb->prepare($table_data['join'], $table_data['orderby_extras'][$field_name]);
								$join_table = true;
								break; //we join, no need to keep searching
							}
						}
					}
				}
			}
			if( $join_table ){
				// check if there's any other required joins
				if ( !empty($table_data['requires']) ) {
					// add required table to join check queue and as a required table, if not already added
					$table_dependencies = is_array( $table_data['requires'] ) ? $table_data['requires'] : array( $table_data['requires'] );
					// supports arrays for multiple tables required
					foreach ( $table_dependencies as $required_table ) {
						if ( !in_array($required_table, $required_tables) ) {
							// add to required joins for later checks
							$required_tables[] = $required_table;
						}
						if ( empty($joined_tables[$required_table]) && !in_array($required_table, $join_check_queue)  ) {
							// add to the queue if not already there, even if alraedy processed earlier but not joined
							$join_check_queue[] = $required_table;
						}
					}
				}
				// join the table here
				$table_joins[$table_name] = $table_data['join'];
			}
			array_shift( $join_check_queue );
		} while ( !empty($join_check_queue) );
		
		// build joins, adding required tables first (to avoid dependency issues, in order, and then subsequent joins to end of the $joins array
		$joins = array();
		foreach ( $required_tables as $table_name ) {
			$joins[$table_name] = $table_joins[$table_name];
		}
		// now add the rest of the joins
		foreach ( $table_joins as $table_name => $table_join ) {
			if( empty($joins[$table_name]) ) $joins[$table_name] = $table_joins[$table_name];
		}
		
		// special join... if we are ordering by user meta, because we need to account for guest bookings stored in bookings meta vs real users in user meta
		$bookings_table = EM_BOOKINGS_TABLE;
		if( !empty($args['orderby']) ) {
			$orderby = is_array( $args['orderby'] ) ? $args['orderby'] : array_map( 'trim', explode( ',', (string) $args['orderby'] ) );
				$array_meta_intersect = array_intersect( $orderby, array_keys($accepted_fields['orderby_user_meta']) );
			$array_data_intersect = array_intersect( $orderby, array_keys($accepted_fields['orderby_user_data']) );
			$array_booking_meta_intersect = array_intersect( $orderby, array_keys($accepted_fields['orderby_booking_meta']) );
			if ( in_array( 'user_name', $orderby ) ) {
				// a nuts order to join by name
				// here we add a special join where we concat first and last names, because we'll always have a combo of those two even if user_name is saved, but not necessarily the other way around
				// however, we also need to account for some bookings which may have just used the full 'user_name' when saving, so we add that to the end of the union
				$joins['field.user_name'] = "
					LEFT JOIN (
						SELECT b.booking_id AS user_name_bid, user_name FROM {$bookings_table} b LEFT JOIN (
							SELECT wm1.user_id, CONCAT(wm1.meta_value,' ',wm2.meta_value) as user_name FROM {$wpdb->usermeta} wm1
							LEFT JOIN {$wpdb->usermeta} wm2 ON wm1.user_id=wm2.user_id AND wm2.meta_key='last_name'
							WHERE wm1.meta_key='first_name'
						) um ON um.user_id = b.person_id WHERE user_id IS NOT NULL AND user_name != ' '
						UNION
						SELECT b.booking_id AS user_name_bid, CONCAT(bm1.meta_value,' ',bm2.meta_value) as user_name FROM " . EM_BOOKINGS_TABLE . " b
							LEFT JOIN " . EM_BOOKINGS_META_TABLE . " bm1 ON bm1.booking_id = b.booking_id AND (bm1.meta_key='_registration_first_name' OR bm1.meta_key='_registration|first_name')
							LEFT JOIN " . EM_BOOKINGS_META_TABLE . " bm2 ON bm2.booking_id = b.booking_id AND (bm2.meta_key='_registration_last_name' OR bm2.meta_key='_registration|last_name')
						WHERE bm1.meta_key IS NOT NULL OR bm2.meta_key IS NOT NULL
						UNION
						SELECT b.booking_id AS user_name_bid, bm1.meta_value FROM " . EM_BOOKINGS_TABLE . " b
							LEFT JOIN " . EM_BOOKINGS_META_TABLE . " bm1 ON bm1.booking_id = b.booking_id AND (bm1.meta_key='_registration_user_name' OR bm1.meta_key='_registration|user_name')
						WHERE bm1.meta_key IS NOT NULL
					) user_name ON user_name.user_name_bid = {$bookings_table}.booking_id
				";
			} elseif ( !empty($array_data_intersect) ) {
				// we're looking for data in wp_users table or otherwise in wp_usermeta if no-user
				$field = current($array_data_intersect);
				$field_key = $accepted_fields['orderby_user_data'][$field]; // this may be different to the orderby key
				$joins[ 'field.' . $field ] = "
					LEFT JOIN (
						SELECT booking_id AS {$field}_bid, {$field_key} FROM {$bookings_table}
                            LEFT JOIN {$wpdb->users} ON ID = person_id
                            WHERE {$field} IS NOT NULL
						UNION
						SELECT b.booking_id AS {$field}_bid, meta_value AS {$field_key} FROM " . EM_BOOKINGS_TABLE . " b
							LEFT JOIN " . EM_BOOKINGS_META_TABLE . " bm1 ON bm1.booking_id = b.booking_id AND (bm1.meta_key='_registration_{$field_key}' OR bm1.meta_key='_registration|{$field_key}')
						WHERE bm1.meta_value IS NOT NULL
					) {$field} ON {$field}.{$field}_bid = {$bookings_table}.booking_id
				";
			} elseif ( !empty($array_meta_intersect) ) {
				// we're looking for data that may be in the wp_usermeta table or in booking meta if no-user
				$field = current( $array_meta_intersect );
				$field_key = $accepted_fields['orderby_user_meta'][$field]; // this may be different to the orderby key
				if( !empty($accepted_fields['orderby'][$field]) ) {
					$joins[ 'field.' . $field ] = "
						LEFT JOIN (
							SELECT b.booking_id AS {$field}_bid, meta_value AS {$field_key} FROM {$bookings_table} b LEFT JOIN (
								SELECT wm1.user_id, meta_value FROM {$wpdb->usermeta} wm1
								WHERE wm1.meta_key='{$field_key}'
							) um ON um.user_id = b.person_id WHERE meta_value IS NOT NULL
							UNION
							SELECT b.booking_id AS {$field}_bid, meta_value AS {$field_key} FROM " . EM_BOOKINGS_TABLE . " b
								LEFT JOIN " . EM_BOOKINGS_META_TABLE . " bm1 ON bm1.booking_id = b.booking_id AND  (bm1.meta_key='_registration_{$field_key}' OR bm1.meta_key='_registration|{$field_key}')
							WHERE bm1.meta_value IS NOT NULL
						) {$field} ON {$field}.{$field}_bid = {$bookings_table}.booking_id
					";
				}
			} elseif ( !empty($array_booking_meta_intersect) ) {
				// order by booking-specific fields
				$field = current($array_booking_meta_intersect);
				$field_key = $accepted_fields['orderby_booking_meta'][$field]; // this may be different to the orderby key
				$joins[ 'field.' . $field ] = "
					LEFT JOIN (
						SELECT booking_id AS {$field}_bid, meta_value AS {$field_key} FROM " . EM_BOOKINGS_META_TABLE . " WHERE meta_key='_booking_{$field_key}' OR meta_key='_booking|{$field_key}'
					) {$field} ON {$field}.{$field}_bid = {$bookings_table}.booking_id
				";
			} else {
				$joins = apply_filters('em_bookings_get_sql_orderby_joins', $joins, [ 'args' => $args, 'count' => $count, 'filter_args' => $filter_args ]);
			}
		}
		// we will also add a group by if not in a count
		if( !$count ) {
			$sql_parts['data']['groupbys'][] = 'booking_id';
			$sql_parts['statement']['groupby'] = ' GROUP BY ' . implode( ', ', $sql_parts['data']['groupbys'] );
		}
		//plugins can override this optional joining behaviour here in case they add custom WHERE conditions or something like that
		$sql_parts['data']['joins'] = apply_filters('em_bookings_get_optional_joins', $joins, $args, $accepted_fields);
		$sql_parts['statement']['join'] = implode("\r\n", $sql_parts['data']['joins']);
		// return SQL parts, we use a different filter name to function because it's already taken in earlier versions
		return apply_filters('em_bookings_get_sql_parts', $sql_parts, [ 'args' => $args, 'count' => $count, 'filter_args' => $filter_args ]);
	}
	
	/**
	 * Get bookings that match the array of arguments passed.
	 * @return EM_Bookings|array
	 * @static
	 */
	public static function get( $args = array(), $count = false ){
		global $wpdb;
		$bookings_table = EM_BOOKINGS_TABLE;
		$events_table = EM_EVENTS_TABLE;
		
		//Quick version, we can accept an array of IDs, which is easy to retrieve
		if( self::array_is_numeric($args) ){ //Array of numbers, assume they are event IDs to retreive
			//We can just get all the events here and return them
			$sql = "
				SELECT * FROM $bookings_table b 
				LEFT JOIN $events_table e ON e.event_id=b.event_id
				WHERE booking_id=".implode(" OR booking_id=", $args);
			$results = $wpdb->get_results(apply_filters('em_bookings_get_sql',$sql),ARRAY_A);
			$bookings = array();
			foreach($results as $result){
				$bookings[] = em_get_booking($result);
			}
			return $bookings; //We return all the bookings matched as an EM_Booking array. 
		}
		
		//We assume it's either an empty array or array of search arguments to merge with defaults			
		$args = self::get_default_search($args);
		
		//If we're only counting results, remove orderby and avoid complex joins
		if( $count ){
			$args['orderby'] = false;
 		}
		
		// build the SQL
		$sql_parts = static::get_sql( $args, $count, false );
		$sql = apply_filters('em_bookings_get_sql', implode("\r\n", $sql_parts['statement']), $args, $sql_parts);
		
		//If we're only counting results, return the number of results
		if( $count ){
			return apply_filters('em_bookings_get_count', $wpdb->get_var($sql), $args);
		}
		$results = $wpdb->get_results($sql, ARRAY_A);

		//If we want results directly in an array, why not have a shortcut here?
		if( !empty($args['array']) ){
			return $results;
		}
		
		//Make returned results EM_Booking objects
		$results = (is_array($results)) ? $results:array();
		$bookings = array();
		foreach ( $results as $booking ){
			$bookings[] = em_get_booking($booking);
		}
		$EM_Bookings = new EM_Bookings($bookings);
		return apply_filters('em_bookings_get', $EM_Bookings);
	}
	
	public static function count( $args = array() ){
		return self::get($args, true);
	}
	

	//List of patients in the patient database, that a user can choose and go on to edit any previous treatment data, or add a new admission.
	//Deprecated
	//@todo remove in 6.0
	function export_csv() {
		global $EM_Event;
		if( $EM_Event->event_id != $this->get_event_uid() ){
			$event = $this->get_event();
			$event_name = $event->name;
		}else{
			$event_name = $EM_Event->name;
		}
		// The name of the file on the user's pc
		$file_name = sanitize_title($event_name). "-bookings.csv";
		
		header("Content-Type: application/octet-stream");
		header("Content-Disposition: Attachment; filename=$file_name");
		em_locate_template('templates/csv-event-bookings.php', true);
		exit();
	}
	
	static function enqueue_js(){
        if( !defined('EM_BOOKING_JS_LOADED') ){ //request loading of JS file in footer of page load
        	add_action('wp_footer','EM_Bookings::em_booking_js_footer', 20);
        	add_action('admin_footer','EM_Bookings::em_booking_js_footer', 20);
        	define('EM_BOOKING_JS_LOADED',true);
        }
	}
	
	static function em_booking_js_footer(){
		?>		
		<script type="text/javascript">
			jQuery(document).ready( function($){	
				<?php
					//we call the segmented JS files and include them here
					do_action('em_gateway_js'); //deprecated use em_booking_js below instead
					do_action('em_booking_js'); //use this instead
				?>							
			});
			<?php
			do_action('em_booking_js_footer');
			?>
		</script>
		<?php
	}
	
	/**
	 * Checks whether a booking being made should register user information as a booking from another user whilst an admin is logged in
	 * @return boolean
	 */
	public static function is_registration_forced(){
		return ( defined('EM_FORCE_REGISTRATION') || self::$force_registration );
	}
	
	public static function get_sql_accepted_fields(){
		$EM_Booking = new EM_Booking();
		$EM_Event = new EM_Event();
		$EM_Location = (new EM_Location())->get_fields(true);
		$accepted_fields = array(
			'tables' => array(
				/* WIP - Meta will work like this to allow re-ordring by custom data, paused temporarily to sort out inconcsistencies with stored data in WP Users vs. meta for guests
				// see event table key for docs on each array item
				EM_TICKETS_BOOKINGS_META_TABLE => array(
					'args' => array(),
					'join' => "LEFT JOIN ".EM_TICKETS_BOOKINGS_META_TABLE." ON ".EM_TICKETS_BOOKINGS_META_TABLE.".ticket_booking_id=".EM_TICKETS_BOOKINGS_TABLE.".ticket_booking_id",
					'requires' => EM_TICKETS_BOOKINGS_TABLE,
					// see booking meta, could add custom attendee data the same way
				),
				EM_TICKETS_TABLE => array(
					'args' => array('ticket_id'),
					'join' => "LEFT JOIN ".EM_TICKETS_TABLE." ON ".EM_TICKETS_TABLE.".event_id=".EM_EVENTS_TABLE.".event_id",
					'requires' => EM_TICKETS_BOOKINGS_TABLE,
					'fields' => (new EM_Ticket())->get_fields(true),
				),
				EM_TICKETS_BOOKINGS_TABLE => array(
					'args' => array(),
					'join' => "LEFT JOIN ".EM_TICKETS_BOOKINGS_TABLE." ON ". EM_BOOKINGS_TABLE.".booking_id=".EM_BOOKINGS_META_TABLE.".booking_id",
					'fields' => (new EM_Ticket_Booking())->get_fields(true),
				),
				EM_BOOKINGS_META_TABLE => array(
					'args' => array(),
					'join' => "LEFT JOIN ".EM_BOOKINGS_META_TABLE." ON ".EM_BOOKINGS_TABLE.".booking_id=".EM_BOOKINGS_META_TABLE.".booking_id AND meta_key=%s",
					'fields' => array(
						'user_name' => 'meta_value',
						'user_email' => 'meta_value',
					),
					'orderby_extras' => array(
						'user_name' => '_registration_user_name',
						'user_email' => '_registration_user_email',
					),
				),
				/**/
				EM_LOCATIONS_TABLE => array(
					'args' => array('town', 'state', 'country', 'region', 'near', 'geo', 'search', 'location_status'), // if we have these we need to join
					'join' => "LEFT JOIN ".EM_LOCATIONS_TABLE." ON ".EM_LOCATIONS_TABLE.".location_id=".EM_EVENTS_TABLE.".location_id",
					'requires' => EM_EVENTS_TABLE,
					'fields' => (new EM_Location())->get_fields(true),
				),
				EM_EVENTS_TABLE => array(
					// accepted args that would require events table to be joined
					'args' => array('event_archetype', 'type', 'scope', 'timezone', 'recurring', 'private', 'private_only', 'post_id', 'mode', 'has_location', 'no_location', 'event_location_type', 'has_event_location', 'category', 'tag', 'event_status', 'month', 'year', 'owner', 'language','recurrence', 'recurrences', 'recurrence', 'recurring_event'),
					// any args that may have a specific empty value that still means it's 'set', could also be an array of empty value types
					'empty_args' => array(),
					// any args here that match the value or that within the array of values will be considered as ignored, for example scope 'all' doesn't actually require any SQL conditions
					'ignore_args' => array('scope' => 'all'),
					// the JOIN SQL required to join this table
					'join' => "LEFT JOIN ".EM_EVENTS_TABLE." ON ".EM_BOOKINGS_TABLE.".event_id=".EM_EVENTS_TABLE.".event_id",
					// field names with shortcut field name as key
					'fields' => (new EM_Event())->get_fields(true),
					// name of table (or array of tables) this join would also require, if joining based on a dependent table that links it to bookings
					'requires' => null,
				),
				/* Needed?
				EM_EVENT_TIMESLOTS_TABLE => array(
						'args' => ['timeslot_id'],
						'join' => "LEFT JOIN ".EM_EVENT_TIMESLOTS_TABLE." ON ".EM_EVENT_TIMESLOTS_TABLE.".event_id=".EM_EVENTS_TABLE.".event_id",
						'fields' => (new TimeRanges(''))->get_fields(true),
						'requires' => EM_EVENTS_TABLE,
				)
				*/
			),
			'prefixes' => array(
				EM_EVENTS_TABLE => 'event',
				EM_LOCATIONS_TABLE => 'location',
				EM_TICKETS_TABLE => 'ticket',
				EM_BOOKINGS_META_TABLE => 'booking_meta',
				EM_TICKETS_BOOKINGS_TABLE => 'ticket_booking',
				EM_TICKETS_BOOKINGS_META_TABLE => 'ticket_booking_meta',
			),
			'orderby' => array_combine(array_keys($EM_Booking->fields), array_keys($EM_Booking->fields)), // maps field names to absolute DB field names
			// these are mapped further down to a orderby_key => db_key format and then merged into orderby, in this case just making the value the key as well
			'orderby_user_data' => ['user_email'], // mapped further down, see comment above
 			'orderby_user_meta' => ['user_name', 'first_name', 'last_name', 'dbem_phone'], // mapped further down, see comment above
			'orderby_booking_meta' => [], // mapped further down, see comment above
		);
		$accepted_fields['orderby']['booking_date'] = 'booking_date'; // not covered in fields array
		// map the orderby fields to the actual db fields
		foreach( ['orderby_user_meta', 'orderby_user_data', 'orderby_booking_meta'] as $orderby_key ) {
			$accepted_fields[$orderby_key] = array_combine( $accepted_fields[$orderby_key], $accepted_fields[$orderby_key] ); // make it an array of identical key/values, simlar to orderby
			$accepted_fields[$orderby_key] = apply_filters('em_bookings_sql_fields_'.$orderby_key, $accepted_fields[$orderby_key]); // allow plugins to add to these fields
			if( $orderby_key === 'orderby_booking_meta') {
				// if we add booking meta to orderby, we prefix both sides with the full search name (i.e. prefixed with booking_meta), because we do this to avoid clashes in DB names and when applying to ORDER BY we'll have inconsistent names
				$accepted_fields['orderby'] = $accepted_fields['orderby'] + array_combine( array_keys($accepted_fields[$orderby_key]), array_keys($accepted_fields[$orderby_key]) );
			} else {
				$accepted_fields['orderby'] = $accepted_fields['orderby'] + $accepted_fields[ $orderby_key ]; // merge the two array so we can order by all these items
			}
		}
		// reserved field names that the main object here has right to, other tables use full or prefix with type to map orderby fields
		$reserved_field_names = array(
			'spaces', 'post_id', 'blog_id', 'post_content', 'content', 'slug', 'name', 'owner', 'status', 'private', 'language', 'parent', 'translation', 'attributes', 'date_created', 'date_modified',
		);
		// go through each table and add to accepted fields. Go in reverse as preference is from least to greatest (for joining dependences optimally)
		foreach( $accepted_fields['tables'] as $table_name => $table_data ){
			if( !empty($table_data['fields']) ){
				foreach( $table_data['fields'] as $field_key => $field_name ){
					if( in_array($field_key, $reserved_field_names) || !empty($accepted_fields['orderby'][$field_name]) ){
						$prefix = $accepted_fields['prefixes'][$table_name];
						$field_name_unique = in_array($field_name, $reserved_field_names) ? $prefix . '_' . $field_name : $field_name;
						$accepted_fields['orderby'][$field_name_unique] = $table_name.'.'.$field_name;
					}else{
						if( !empty($table_data['orderby_extras'][$field_key]) ){
							// special meta table, so we map the key even though it's not a real field
							if( empty($accepted_fields['orderby'][$field_key]) ){
								// duplicates will just be ignored, at this point overriders should be more specific
								$accepted_fields['orderby'][$field_key] = $table_name.'.'.$field_name;
							}
						}else{
							$accepted_fields['orderby'][$field_name] = $table_name.'.'.$field_name;
						}
					}
				}
			}
		}
		return apply_filters( 'em_bookings_get_sql_accepted_fields', $accepted_fields );
	}
	
	public static function build_sql_groupby_orderby( $args, $accepted_fields, $default_order = 'ASC' ) {
		
		return parent::build_sql_groupby_orderby( $args, $accepted_fields, $default_order ); // TODO: Change the autogenerated stub
	}
	
	/* Overrides EM_Object method to apply a filter to result
	 * @see wp-content/plugins/events-manager/classes/EM_Object#build_sql_orderby()
	 */
	public static function build_sql_orderby( $args, $accepted_fields, $default_order = 'ASC' ){
		return apply_filters( 'em_bookings_build_sql_orderby', parent::build_sql_orderby($args, $accepted_fields, em_get_option('dbem_bookings_default_order','booking_date')), $args, $accepted_fields, $default_order );
	}
	
	/* Overrides EM_Object method to apply a filter to result
	 * @see wp-content/plugins/events-manager/classes/EM_Object#build_sql_conditions()
	 */
	public static function build_sql_conditions( $args = array() ){
		global $wpdb;
		$conditions = parent::build_sql_conditions($args);
		if( is_numeric($args['status']) ){
			$conditions['status'] = 'booking_status='.$args['status'];
		}elseif( self::array_is_numeric($args['status']) && count($args['status']) > 0 ){
			$conditions['status'] = 'booking_status IN ('.implode(',',$args['status']).')';
		}elseif( !is_array($args['status']) && preg_match('/^([0-9],?)+$/D', $args['status']) ){
			$conditions['status'] = 'booking_status IN ('.$args['status'].')';
		}
		// RSVP status
		if( $args['rsvp_status'] !== false ){
			if( is_numeric($args['rsvp_status']) ){
				$conditions['rsvp_status'] = 'booking_rsvp_status='.$args['rsvp_status'];
			}elseif( $args['rsvp_status'] === null || $args['rsvp_status'] === 'null' ){
				$conditions['rsvp_status'] = 'booking_rsvp_status IS NULL';
			}elseif( self::array_is_numeric($args['rsvp_status']) && count($args['rsvp_status']) > 0 ){
				$conditions['rsvp_status'] = 'booking_status IN ('.implode(',',$args['rsvp_status']).')';
			}elseif( !is_array($args['rsvp_status']) && preg_match('/^(([0-9]|null),?)+$/iD', $args['rsvp_status']) ){
				$conditions['rsvp_status'] = 'booking_rsvp_status IN ('.$args['rsvp_status'].')';
			}
		}
		// person/owner
		if( is_numeric($args['person']) ){
			$conditions['person'] = EM_BOOKINGS_TABLE.'.person_id='.$args['person'];
		} elseif ( EM_Object::array_is_numeric($args['person']) ) {
			$conditions['person'] = EM_BOOKINGS_TABLE.'.person_id IN (' . implode(',', $args['person']) . ')';
		}
		if( EM_MS_GLOBAL && !empty($args['blog']) && is_numeric($args['blog']) ){
			if( is_main_site($args['blog']) ){
				$conditions['blog'] = "(".EM_EVENTS_TABLE.".blog_id={$args['blog']} OR ".EM_EVENTS_TABLE.".blog_id IS NULL)";
			}else{
				$conditions['blog'] = "(".EM_EVENTS_TABLE.".blog_id={$args['blog']})";
			}
		}
		if( empty($conditions['event']) && $args['event'] === false ){
			$conditions['event'] = EM_BOOKINGS_TABLE.'.event_id != 0';
		} elseif ( !empty($conditions['event']) ) {
			// we always include the bookings table, we don't always include the events table now
			$conditions['event'] = str_replace( EM_EVENTS_TABLE . '.event_id', EM_BOOKINGS_TABLE . '.event_id', $conditions['event']);
		}
		if( !empty($args['search']) ){
			// escape the value directly, because otherwise it messes up with % marks in prepare
			$search = '%' . $wpdb->_real_escape($wpdb->esc_like($args['search'])) . '%';
			$search_conditions = array();
			$search_conditions[] = EM_BOOKINGS_TABLE.'.person_id IN (SELECT user_id FROM '.$wpdb->usermeta ." WHERE meta_value LIKE '$search' AND meta_key NOT LIKE '%_settings')";
			$search_conditions[] = EM_BOOKINGS_TABLE.'.booking_id IN (SELECT booking_id FROM '.EM_BOOKINGS_META_TABLE." WHERE meta_value LIKE '$search')";
			$search_conditions[] = EM_BOOKINGS_TABLE.'.person_id IN (SELECT ID FROM '.$wpdb->users." WHERE user_nicename LIKE '$search' OR user_email LIKE '$search' OR display_name LIKE '$search' OR user_login LIKE '$search')";
			if( preg_match('/^[a-zA-Z0-9]{32}$/D', $args['search']) ) {
				$search_conditions[] = EM_BOOKINGS_TABLE . '.booking_id IN (SELECT booking_id FROM ' . EM_TICKETS_BOOKINGS_TABLE . " WHERE ticket_uuid = '{$args['search']}')";
			}
			$conditions['search'] = '('. implode(' OR ', $search_conditions) . ')';
		}
		if( is_numeric($args['ticket_id']) ){
			$EM_Ticket = new EM_Ticket($args['ticket_id']);
			if( $EM_Ticket->can_manage() ){
				$conditions['ticket'] = EM_BOOKINGS_TABLE.'.booking_id IN (SELECT booking_id FROM '.EM_TICKETS_BOOKINGS_TABLE." WHERE ticket_id='{$args['ticket_id']}')";
			}
		}
		if( !empty($args['booking_id']) && static::array_is_numeric($args['booking_id']) ) {
			$conditions['ticket'] = EM_BOOKINGS_TABLE.'.booking_id IN ('.implode(',', $args['booking_id']).')';
		}
		if ( !empty( $args['timeslot_id'] ) ) {
			$conditions['timeslot'] = EM_BOOKINGS_TABLE . '. timeslot_id = ' . absint($args['timeslot_id']);
		}
		return apply_filters('em_bookings_build_sql_conditions', $conditions, $args);
	}
	
	/* 
	 * Adds custom Events search defaults
	 * @param array $array_or_defaults may be the array to override defaults
	 * @param array $array
	 * @return array
	 * @uses EM_Object#get_default_search()
	 */
	public static function get_default_search( $array_or_defaults = array(), $array = array() ){
		$defaults = array(
			'status' => false,
			'rsvp_status' => false,
			'person' => true, //to add later, search by person's bookings...
			'blog' => get_current_blog_id(),
			'ticket_id' => false,
			'array' => false, //returns an array of results if true, if an array or text it's assumed an array of specific table fields or single field name requested
			'country' => false, // experimeenal, if you see this and want more locatiion booking searches, let us know!
			'booking_id' => [],
			'timeslot_id' => false,
		);
		//sort out whether defaults were supplied or just the array of search values
		if( empty($array) ){
			$array = $array_or_defaults;
		}else{
			$defaults = array_merge($defaults, $array_or_defaults);
		}
		//figure out default owning permissions
		if( !current_user_can('edit_others_events') || !isset($defaults['owner']) ){
			$defaults['owner'] = get_current_user_id();
		}else{
			$defaults['owner'] = false;
		}
		if( EM_MS_GLOBAL && !is_admin() ){
			if( empty($array['blog']) && is_main_site() && get_site_option('dbem_ms_global_events') ){
			    $array['blog'] = false;
			}
		}
		if ( !empty($array['timeslot_id']) ) {
			$array['timeslot_id'] = absint( $array['timeslot_id'] );
		}
		// deal with timeslot event ids
		if ( !empty($array['event']) && preg_match('/^([0-9]+):([0-9]+)$/', $array['event'], $matches) ) {
			$array['event'] = absint( $matches[1] );
			$array['timeslot_id'] = absint( $matches[2] );
		}
		// get search defaults from parent
		$search_defaults = parent::get_default_search($defaults,$array);
		//clean up array value, which could be an actual array for EM_Bookings
		if( !empty($array['array']) ){
			$EM_Booking = new EM_Booking();
			if( is_array($array['array']) ){
				$clean_arg = array();
				foreach( $array['array'] as $k => $field ){
					if( array_key_exists($field, $EM_Booking->fields) ){
						$clean_arg[] = $field;
					}
				}
				$search_defaults['array'] = !empty($clean_arg) ? $clean_arg : true; //if invalid args given, just return all fields
			}elseif( is_string($array['array']) && array_key_exists($array['array'], $EM_Booking->fields) ){
				$search_defaults['array'] = array($array['array']);
			}else{
				$search_defaults['array'] = true;
			}
		}else{
			$search_defaults['array'] = false;
		}
		// clean up the orderby, we cannot allow more than one custom user meta ordering to avoid crazy SQL statements
		// regualr fields in the bookings table are fine, but user meta fields will bloat with joins
		if( !empty($search_defaults['orderby']) ){
			$EM_Booking = $EM_Booking ?? new EM_Booking();
			$clean_orderby = array();
			$custom_fields = 0;
			foreach( $search_defaults['orderby'] as $orderby ){
				if( array_key_exists($orderby, $EM_Booking->fields) ){
					$clean_orderby[] = $orderby;
				} elseif( $custom_fields === 0 ) {
					$clean_orderby[] = $orderby;
					$custom_fields++;
				}
			}
			$search_defaults['orderby'] = !empty($clean_orderby) ? $clean_orderby : false;
		}
		// allow to filter by booking_id
		$search_defaults = static::clean_id_atts($search_defaults, ['booking_id']);
		// return the search defaults
		return apply_filters('em_bookings_get_default_search', $search_defaults, $array, $defaults);
	}

	//Iterator Implementation - if we iterate this object, we automatically invoke the load() function first
	//and load up all bookings to go through from the database.
	#[\ReturnTypeWillChange]
    public function rewind(){
    	$this->load();
        reset($this->bookings);
    }
	#[\ReturnTypeWillChange]
    public function current(){
    	$this->load();
        $var = current($this->bookings);
        return $var;
    }
	#[\ReturnTypeWillChange]
    public function key(){
    	$this->load();
        $var = key($this->bookings);
        return $var;
    }
	#[\ReturnTypeWillChange]
    public function next(){
    	$this->load();
        $var = next($this->bookings);
        return $var;
    }
	#[\ReturnTypeWillChange]
    public function valid(){
    	$this->load();
        $key = key($this->bookings);
        $var = ($key !== NULL && $key !== FALSE);
        return $var;
    }
	
	// ArrayAccess Implementation
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @param $value
	 * @return void
	 */
	public function offsetSet($offset, $value) {
		if (is_null($offset)) {
			$this->bookings[] = $value;
		} else {
			$this->bookings[$offset] = $value;
		}
	}
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @return bool
	 */
	public function offsetExists($offset) {
		return isset($this->bookings[$offset]);
	}
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @return void
	 */
	public function offsetUnset($offset) {
		unset($this->bookings[$offset]);
	}
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @return EM_Ticket_Bookings|null
	 */
	public function offsetGet($offset) {
		return isset($this->bookings[$offset]) ? $this->bookings[$offset] : null;
	}
}
?>