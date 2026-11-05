<?php
/**
 * Groups up ticket bookings for a single ticket type, simlar to EM_Tickets_Bookings but this is specific to one ticket type.
 * This essentially marries a EM_Tickets_Bookings with EM_Ticket_Booking, it can be used as one or the other with functions (not properties)
 * @author marcus
 *
 * @since 6.1
 *
 * By default the following overriden classes return the EM_Ticket_Booking objects rather than itself.
 * @method EM_Ticket_Booking        current()
 * @methox EM_Ticket_Booking        next()
 * @method EM_Ticket_Bookings|null  offsetGet() offsetGet(int $offset)
 * @property $ticket_bookings       EM_Ticket_Booking[]                 Alias (sensible name) for tickets_bookings.
 *
 */
class EM_Ticket_Bookings extends EM_Tickets_Bookings {
	/**
	 * Whilst it should be ticket_bookings, we use this to make it easier to extend EM_Tickets_Bookings
	 * @var EM_Ticket_Booking[]
	 */
	public $tickets_bookings = array();
	/**
	 * @var int The ticket ID associated with these ticket bookings
	 */
	public $ticket_id;
	/**
	 * @var EM_Ticket The ticket associated with these booked spaces.
	 */
	public $ticket;
	/**
	 * @var string Ensures extended parent class functions use the right filter name
	 */
	public static $n = 'em_ticket_bookings';
	
	/**
	 * Adds EM_Ticket_Booking objects to the internal array or alternatively
	 * @param EM_Ticket_Booking[]|array  Array of tiket booking objects or an array of information used to add new ticket booking objects. If 'spaces' is supplied in the plain associative array, that many EM_Ticket_Booking ojbect will be created.
	 */
	public function __construct($data = false ) {
		if( !empty($data) ){
			if( is_array( $data ) ){
				foreach( $data as $array_item ){
					if( $array_item instanceof EM_Ticket_Booking ){
						$is_booking_tickets_array = true;
						break;
					}
				}
				if( !empty($is_booking_tickets_array) ){
					// we were supplied an array of EM_Ticket_Booking objects, so we load them up
					foreach($data as $key => $EM_Ticket_Booking ) {
						if( $key !== 'booking' && $key !== 'ticket' ){
							$this->tickets_bookings[$EM_Ticket_Booking->ticket_uuid] = $EM_Ticket_Booking;
						}
					}
					$this->tickets_bookings_loaded = true;
					$this->ticket = $EM_Ticket_Booking->get_ticket();
					$this->ticket_id = $this->ticket->ticket_id;
					// try to load a booking in any way possible, preferably by a passed reference rather than ID
					if( !empty($data['booking']) ){
						$this->booking = $data['booking'];
					}elseif( $EM_Ticket_Booking->booking ){
						$this->booking = $EM_Ticket_Booking->booking;
						$this->booking_id = $this->booking->booking_id;
					}elseif( $EM_Ticket_Booking->booking_id ){
						// set booking_id now, get booking later if needed
						$this->booking_id = $EM_Ticket_Booking->booking_id;
					}
				}else{
					// we may have been passed an array of options we can use to create multiple single EM_Ticket_Booking objects
					$ticket_booking = $data;
					// get a ticket ID
					if( !empty($ticket_booking['ticket_id']) ) $this->ticket_id = $ticket_booking['ticket_id'];
					if( !empty($ticket_booking['ticket']) ){
						$this->ticket = $ticket_booking['ticket'];
						if( empty($this->ticket_id) ) $this->ticket_id = $this->ticket->ticket_id;
					}
					// get a booking ID and object (if booking not made, we need a booking object reference)
					if( !empty($ticket_booking['booking']) ){
						$this->booking = $ticket_booking['booking'];
						$this->booking_id = $this->booking->booking_id;
					}elseif( !empty($ticket_booking['booking_id']) ){
						$this->booking_id = $ticket_booking['booking_id'];
					}
					if( $this->ticket_id && $this->booking_id ){ // booking id may not exist yet but we must have a booking reference
						// we don't necessarily need to create spaces, get_post will sort that out for us
						if( !empty($ticket_booking['spaces']) ){
							// create multiple single-space bookings here
							for( $i = 0 ; $i < $ticket_booking['spaces']; $i++ ){
								$EM_Ticket_Booking = new EM_Ticket_Booking( array(
									'ticket_id' => $this->ticket_id,
									'booking_id' => $this->booking_id,
								));
								if( $this->booking ) {
									$EM_Ticket_Booking->booking = $this->booking;
								}
								$EM_Ticket_Booking->ticket = $this->ticket;
								$this->tickets_bookings[$EM_Ticket_Booking->ticket_uuid] = $EM_Ticket_Booking;
							}
							$this->tickets_bookings_loaded = true;
						}
					}
				}
			}
		}
	}
	
	/**
	 * Returns an array of individual ticket bookings (single space attendees) for given search $args. If $count is set to true, then the number of results found is returned instead.
	 * @param $args
	 *
	 * @return EM_Ticket_Booking[]|int
	 */
	public static function get( $args, $count = false ) {
		return parent::get( $args, $count );
	}
	
	/**
	 * @param $sql
	 *
	 * @return EM_Ticket_Booking[]
	 */
	public static function get_results( $sql ) {
		global $wpdb;
		$ticket_bookings = array();
		$ticket_bookings_results = $wpdb->get_results($sql, ARRAY_A);
		foreach( $ticket_bookings_results as $ticket_booking ){
			$ticket_bookings[$ticket_booking['ticket_booking_id']] = new EM_Ticket_Booking($ticket_booking);
		}
		return $ticket_bookings;
	}
	
	public static function get_built_sql( $bookings_sql, $fields, $joins, $conditions = array() ){
		$condition = !empty($conditions) ? " WHERE " . implode(' AND ', $conditions) : '';
		return "SELECT " . implode(', ', $fields) . " FROM " . EM_TICKETS_BOOKINGS_TABLE . " tb INNER JOIN ({$bookings_sql}) b ON b.booking_id = tb.booking_id " . implode(' ', $joins). $condition;
	}
	
	public static function get_built_count_sql( $bookings_sql, $extras = array( 'joins' => [], 'conditions' => [] ) ) {
		$joins = $extras['joins'] ?? [];
		$condition = !empty($extras['conditions']) ? " WHERE " . implode(' AND ', $extras['conditions']) : '';
		return "SELECT COUNT(DISTINCT ticket_booking_id) FROM " . EM_TICKETS_BOOKINGS_TABLE . " tb INNER JOIN ({$bookings_sql}) b ON b.booking_id = tb.booking_id " . implode(' ', $joins). $condition;
	}
	
	/**
	 * @return EM_Ticket_Booking|false
	 */
	public function get_first(){
		$this->get_ticket_bookings();
		return reset($this->tickets_bookings);
	}
	
	/**
	 * Load ticket bookings if not already loaded.
	 * @param $ticket
	 *
	 * @return EM_Ticket_Booking[]
	 */
	function get_ticket_bookings( $ticket = false ){
		if( !$this->tickets_bookings_loaded && !empty($this->booking_id) ){
			global $wpdb;
			$sql = "SELECT * FROM ". EM_TICKETS_BOOKINGS_TABLE ." WHERE booking_id=%d AND ticket_id=%d";
			$sql = $wpdb->prepare( $sql, $this->booking_id, $this->ticket_id );
			$ticket_bookings = $wpdb->get_results($sql, ARRAY_A);
			foreach( $ticket_bookings as $ticket_booking ){
				$this->tickets_bookings[$ticket_booking['ticket_uuid']] = new EM_Ticket_Booking($ticket_booking);
			}
		}
		$this->tickets_bookings_loaded = true;
		return $this->tickets_bookings;
	}
	
	/**
	 * Get specific EM_Ticket_Booking properties we already know here, especially for code that assumes EM_Ticket_Booking still has more than one space and thinks this is an EM_Ticket_Booking object
	 *
	 * @param $prop
	 *
	 * @return mixed|null
	 */
	public function __get( $prop ){
		if( $prop === 'ticket_booking_price' ){
			$this->get_price();
		}elseif ( $prop === 'ticket_booking_spaces' ){
			return $this->get_spaces();
		} elseif ( $prop === 'ticket_bookings') {
			return $this->get_ticket_bookings();
		} elseif ( $prop === 'id' ){
			return $this->booking_id . '-' . $this->ticket_id;
		}
		return parent::__get( $prop );
	}
	
	public function __set( $prop, $value ) {
		if( $prop === 'ticket_bookings') {
			$this->tickets_bookings = $value;
		}
		parent::__set( $prop, $value );
	}
	
	/**
	 * Safety measure in case methods belonging to $EM_Ticket_Booking are called that aren't defined here.
	 * @param $function
	 * @param $args
	 * @return mixed
	 */
	public function __call( $function, $args ){
		$EM_Ticket_Booking = new EM_Ticket_Booking( array(
			'ticket_id' => $this->ticket_id,
			'booking_id' => $this->booking_id
		));
		// handle some functions that may cause problems if old scripts assume we're on a direct EM_Ticket_Booking
		if( $function == 'get_price_with_taxes' ){
			$price_with_taxes = 0;
			foreach( $this->tickets_bookings as $EM_Ticket_Booking ){
				$price_with_taxes += $EM_Ticket_Booking->get_price_with_taxes();
			}
			if( !empty($args[0]) ) $price_with_taxes = $this->format_price($price_with_taxes);
			return $price_with_taxes;
		} elseif( method_exists($EM_Ticket_Booking, $function) ){
			return $EM_Ticket_Booking->$function( $args );
		}
		return parent::__call( $function, $args );
	}
	
	/**
	 * Return relevant fields that will be used for storage, excluding things such as event and ticket objects that should get reloaded
	 * @return string[]
	 */
	public function __sleep(){
		$array = parent::__sleep();
		$array[] = 'ticket_id';
		return apply_filters('em_ticket_bookings_sleep', $array, $this);
	}
	
	/**
	 * @return bool
	 */
	public function get_post( $override_availability = false ){
		// first, determine how many spaces we're dealing with here and if we're adding or subtracting tickets
		$spaces = 0;
		if( !empty($_REQUEST['em_tickets'][$this->ticket_id]['spaces']) ){
			$spaces = absint($_REQUEST['em_tickets'][$this->ticket_id]['spaces']);
		}
		if( $spaces > 0 ){
			// check first if we're missing uuids, remove them already
			foreach( $this->tickets_bookings as $uuid => $EM_Ticket_Booking ){
				if( empty($_REQUEST['em_tickets'][$this->ticket_id]['ticket_bookings'][$uuid]) ){
					$this->tickets_bookings_deleted[$uuid] = $EM_Ticket_Booking;
					unset($this->tickets_bookings[$uuid]);
				}
			}
			// now if we're still short, remove some off the end of the array
			$current_spaces = $this->get_spaces(true); // recheck spaces since above may have removed some
			// adding more? add new ones to the end
			if( $spaces > $current_spaces ){
				for( $i = $current_spaces ; $i < $spaces; $i++ ){
					$EM_Ticket_Booking = new EM_Ticket_Booking( array(
						'ticket_id' => $this->ticket_id,
						'booking_id' => $this->booking_id,
					));
					$EM_Ticket_Booking->booking = $this->booking;
					$EM_Ticket_Booking->ticket = $this->ticket;
					$this->tickets_bookings[$EM_Ticket_Booking->ticket_uuid] = $EM_Ticket_Booking;
				}
			}
			// subtracting? shift stuff off the end if all uuids are provided, otherwise remove the missing uuids
			if( $spaces < $current_spaces ){
				// keep some add rest to array
				$tickets_bookings = $this->tickets_bookings;
				$this->tickets_bookings = array_slice($tickets_bookings, 0, $spaces, true);
				$this->tickets_bookings_deleted = array_merge( $this->tickets_bookings_deleted, array_slice($tickets_bookings, $spaces, null, true));
			}
			// we'll also grab the first available $_REQUEST[ticket_id][tickets_bookings][id] that's not a uuid or %n (template) and reserve it for any newly created ticket booking objects
			if( !empty($_REQUEST['em_tickets'][$this->ticket_id]['ticket_bookings']) ){
				// we'll maintain the order of these keys so ticket_booking objects can also have reordering (eventually)
				$keys = array_keys($_REQUEST['em_tickets'][$this->ticket_id]['ticket_bookings']);
				foreach( $this->tickets_bookings as $EM_Ticket_Booking ){
					if( !$EM_Ticket_Booking->ticket_booking_id && empty($_REQUEST['em_tickets'][$this->ticket_id]['ticket_bookings'][$EM_Ticket_Booking->ticket_uuid])  ){
						foreach( $keys as $index => $key ){
							if( strlen($key) !== 32 && $key !== '%n'){ //yoink
								$keys[$index] = $EM_Ticket_Booking->ticket_uuid;
								break;
							}
						}
					}
				}
				$_REQUEST['em_tickets'][$this->ticket_id]['ticket_bookings'] = array_combine( $keys, $_REQUEST['em_tickets'][$this->ticket_id]['ticket_bookings'] );
			}
			// run a get_post() on these ones too to hook any info into each ticket booking
			foreach( $this->tickets_bookings as $EM_Ticket_Booking ){
				if( !$EM_Ticket_Booking->get_post() ){
					$this->errors = array_merge( $this->errors, $EM_Ticket_Booking->errors );
				}
			}
		}else{
			// add any tickets to be deleted here and empty the array (although in theory, we'd be deleting a booking entirely in this scenario)
			$this->tickets_bookings_deleted = $this->tickets_bookings;
			$this->tickets_bookings = array();
		}
		$this->get_spaces(true);
		$this->calculate_price(true);
		return apply_filters(static::$n . '_get_post', empty($this->errors), $this);
	}
	
	public function validate( $override_availability = false ){
		if( !$this->get_booking()->get_event()->get_bookings()->ticket_exists( $this->ticket_id ) ){
			$this->errors[] = __('You are trying to book a non-existent ticket for this event.','events-manager');
		}
		$available_spaces = $this->get_ticket()->get_available_spaces();
		$spaces_needed = $this->get_spaces() - count($this->tickets_bookings_deleted); // if we're editing the booking, this is the real number of spaces we're booking
		if( $this->booking_id ){
			// we're editing the booking, meaning we need to calculate then number of spaces we deleted into the total spaces we had
			$spaces_previously_consumed = $this->get_spaces() + count($this->tickets_bookings_deleted);
			// then add those spaces back to being available spaces, as if we're booking again
			$available_spaces += $spaces_previously_consumed;
		}
		if ( !$override_availability && $available_spaces < $spaces_needed ) {
			$this->add_error( $this->get_booking()->get_option('dbem_booking_feedback_full'));
		}
		// enforce the ticket's configured min/max spaces per booking, when set, so quantities can't be tampered past the form limits
		$ticket_min = $this->get_ticket()->min;
		$ticket_max = $this->get_ticket()->max;
		if( $spaces_needed > 0 && $ticket_min > 0 && $spaces_needed < $ticket_min ){
			$this->add_error( sprintf( __('You must book at least %1$d spaces for the ticket %2$s.', 'events-manager'), $ticket_min, "'".$this->get_ticket()->name."'") );
		}
		if( $ticket_max > 0 && $spaces_needed > $ticket_max ){
			$this->add_error( sprintf( __('You cannot book more than %1$d spaces for the ticket %2$s.', 'events-manager'), $ticket_max, "'".$this->get_ticket()->name."'") );
		}
		// check if ticket is available to the user the booking is associated to
		// TODO current implementation won't work because we're trying to validate potentially a guest that beomes a user, therefore a guest ticket can be booked by someone that isn't a user yet but at this point they have a valid ID and validation fails. We need to triple check this new way without the is_available.
		// TODO I think we probably need to circumvent on the manual_booking level rather than here... or make sure we're validating in some smarter way
		$user = null;
		if( $this->get_booking()->person_id === 0 ){
			$user = false;
		}elseif( $this->get_booking()->person_id > 0 ){
			$user = $this->get_booking()->get_person();
		}
		if( !$override_availability && !$this->get_ticket()->is_available(false, false, false, $user) ){
			$message = __('The ticket %s is no longer available.', 'events-manager');
			$this->add_error( $this->get_booking()->get_option('dbem_booking_feedback_ticket_unavailable', sprintf($message, "'".$this->get_ticket()->name."'")));
		}
		return apply_filters( static::$n .'_validate', empty($this->errors), $this, $override_availability);
	}
	
	/**
	 * Counts how many spaces it has (essentially, how many EM_Ticket_Booking objects it has, since each one represents one space as of v6.1
	 * @param $force_refresh
	 * @return int
	 */
	function get_spaces( $force_refresh = false ){
		if( $force_refresh || $this->spaces == 0 ){
			if( empty($this->tickets_bookings) ) {
				$this->get_ticket_bookings();
			}
			$this->spaces = count($this->tickets_bookings);
		}
		return apply_filters( static::$n . '_get_spaces',$this->spaces,$this);
	}
	
	public function get_ticket(){
		if( !empty($this->ticket) ) {
			return $this->ticket;
		}else{
			return new EM_Ticket($this->ticket_id);
		}
	}
	
	/**
	 * Delete all ticket bookings
	 * @return boolean
	 */
	function delete(){
		global $wpdb;
		$result = $result_meta = false;
		if( $this->get_booking()->can_manage() ){
			$result_meta = $wpdb->query($wpdb->prepare("DELETE FROM ".EM_TICKETS_BOOKINGS_META_TABLE." WHERE ticket_booking_id IN (SELECT ticket_booking_id FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE booking_id = %d AND ticket_id = %d)", $this->booking_id, $this->ticket_id));
			$result = $wpdb->query($wpdb->prepare("DELETE FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE booking_id = %d AND ticket_id = %d", $this->booking_id, $this->ticket_id));
		}
		return apply_filters(static::$n . '_delete', ($result !== false && $result_meta !== false), $this);
	}
	
	public function __debugInfo(){
		$object = clone($this);
		$object->booking = !empty($this->booking_id) ? 'Booking ID #'.$this->booking_id : 'New Booking - No ID';
		$object->ticket = 'Ticket #'.$this->ticket_id . ' - ' . $this->get_ticket()->ticket_name;
		$object->fields = 'Removed for export, uncomment from __debugInfo()';
		$object->required_fields = 'Removed for export, uncomment from __debugInfo()';
		$object->shortnames = 'Removed for export, uncomment from __debugInfo()';
		$object->mime_types = 'Removed for export, uncomment from __debugInfo()';
		if( empty($object->errors) ) $object->errors = false;
		return (Array) $object;
	}
}