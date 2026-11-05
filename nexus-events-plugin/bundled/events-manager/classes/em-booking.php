<?php

use EM\Event\Timeslot;

/**
 * gets a booking in a more db-friendly manner, allows hooking into booking object right after instantiation
 * @param mixed $id
 * @param mixed $search_by
 * @return EM_Booking
 */
function em_get_booking($id = false) {
	global $EM_Booking;
	//check if it's not already global so we don't instantiate again
	if( $EM_Booking instanceof EM_Booking ){
		if( is_object($id) && $EM_Booking->booking_id == $id->booking_id ){
			return apply_filters('em_get_booking', $EM_Booking);
		}else{
			if( is_numeric($id) && $EM_Booking->booking_id == $id ){
				return apply_filters('em_get_booking', $EM_Booking);
			}elseif( is_array($id) && !empty($id['booking_id']) && $EM_Booking->booking_id == $id['booking_id'] ){
				return apply_filters('em_get_booking', $EM_Booking);
			}elseif( is_string($id) && strlen($id) == 32 && $EM_Booking->booking_uuid === $id ){
				return apply_filters('em_get_booking', $EM_Booking);
			}
		}
	}
	if( $id instanceof EM_Booking ){
		return apply_filters('em_get_booking', $id);
	}else{
		return apply_filters('em_get_booking', new EM_Booking($id));
	}
}
/**
 * Resolve a booking from a request-supplied id. Accepts only a positive integer id or a 32-character booking UUID; any other value (notably an array, which would otherwise be mass-assigned onto a new EM_Booking) returns an empty booking.
 * @param mixed $value
 * @return EM_Booking
 */
function em_get_booking_request( $value ) {
	if ( is_numeric( $value ) ) {
		return em_get_booking( absint( $value ) );
	}
	if ( is_string( $value ) && preg_match( '/^[A-Za-z0-9]{32}$/', $value ) ) {
		return em_get_booking( $value );
	}
	return em_get_booking();
}
/**
 * Contains all information and relevant functions surrounding a single booking made with Events Manager
 * @property int|false $booking_status
 * @property string $language
 * @property EM_Person $person
 * @property string|int $event_id       The event ID including timeslot ID e.g. 123 or 123:123
 */
class EM_Booking extends EM_Object{
	//DB Fields
	var $booking_id;
	var $booking_uuid;
	protected $event_id;
	var $timeslot_id;
	var $person_id;
	var $booking_price = null;
	var $booking_spaces;
	var $booking_comment;
	public $booking_status = false;
	public $booking_rsvp_status = null;
	var $booking_tax_rate = null;
	var $booking_taxes = null;
	var $booking_meta = array();
	var $fields = array(
		'booking_id' => array('name'=>'id','type'=>'%d'),
		'booking_uuid' => array('name'=>'uuid','type'=>'%s'),
		'event_id' => array('name'=>'event_id','type'=>'%d'),
		'timeslot_id' => array('name'=>'timeslot_id','type'=>'%d'),
		'person_id' => array('name'=>'person_id','type'=>'%d'),
		'booking_price' => array('name'=>'price','type'=>'%f'),
		'booking_spaces' => array('name'=>'spaces','type'=>'%d'),
		'booking_comment' => array('name'=>'comment','type'=>'%s'),
		'booking_status' => array('name'=>'status','type'=>'%d'),
		'booking_rsvp_status' => array('name'=>'rsvp_status','type'=>'%d','null'=>1),
		'booking_tax_rate' => array('name'=>'tax_rate','type'=>'%f','null'=>1),
		'booking_taxes' => array('name'=>'taxes','type'=>'%f','null'=>1),
		'booking_meta' => array('name'=>'meta','type'=>'%s')
	);
	public static $field_shortcuts = array(
		'id' => 'booking_id',
		'uuid' => 'booking_uuid',
		'price' => 'booking_price',
		'spaces' => 'booking_spaces',
		'comment' => 'booking_comment',
		'status' => 'booking_status',
		'rsvp_status' => 'booking_rsvp_status',
		'tax_rate' => 'booking_tax_rate',
		'taxes' => 'booking_taxes',
		'meta' => 'booking_meta',
		'timeslot_id' => 'timeslot_id',
	);
	//Other Vars
	/**
	 * array of notes by admins on this booking. loaded from em_meta table in construct
	 * @var array
	 */
	var $notes;
	/**
	 * Deprecated as of 5.8.2, previously used to store timestamp of booking date. Use EM_Booking->date()->getTimestamp() instead.
	 * @var int
	 */
	private $timestamp;
	/**
	 * The date of the booking, in UTC time, represented as a DATETIME mysql value.
	 * @var string
	 */
	protected $booking_date;
	/**
	 * Contains the booking date in EM_DateTime object form.
	 * @var EM_DateTime
	 */
	protected $date;
	/**
	 * @var EM_Person
	 */
	protected $person;
	var $required_fields = array('booking_id', 'event_id', 'person_id', 'booking_spaces');
	var $feedback_message = "";
	var $errors = array();
	/**
	 * when using EM_Booking::email_send(), this number is updated with sent emails
	 * @var int
	 */
	var $mails_sent = 0;
	/**
	 * Contains an array of custom fields for a booking. This is loaded from em_meta, where the booking_custom name contains arrays of data.
	 * @var array
	 */
	var $custom = array();
	/**
	 * If saved in this instance, you can see what previous approval status was.
	 * @var int
	 */
	var $previous_status = false;
	var $previous_rsvp_status;
	/**
	 * The booking approval status number corresponds to a state in this array.
	 * @var array
	 */
	var $status_array = array();
	/**
	 * @var EM_Tickets
	 */
	var $tickets;
	/**
	 * @var EM_Event
	 */
	var $event;
	/**
	 * @var Timeslot
	 */
	var $timeslot;
	/**
	 * @var EM_Tickets_Bookings
	 */
	var $tickets_bookings;
	/**
	 * If set to true, this booking can be managed by any logged in user.
	 * @var EM_Tickets_Bookings
	 */
	var $manage_override;
	
	static $rsvp_statuses = array();
	
	/**
	 * Creates booking object and retrieves booking data (default is a blank booking object). Accepts either array of booking data (from db) or a booking id.
	 * @param mixed $booking_data
	 * @return null
	 */
	function __construct( $booking_data = false ){
		//Get the person for this booking
		global $wpdb;
	  	if( $booking_data !== false ){
			//Load booking data
			$booking = array();
			if( is_array($booking_data) ){
				$booking = $booking_data;
			}elseif( is_numeric($booking_data) ){
				//Retrieving from the database
				$sql = $wpdb->prepare("SELECT * FROM ". EM_BOOKINGS_TABLE ." WHERE booking_id =%d", $booking_data);
				$booking = $wpdb->get_row($sql, ARRAY_A);
			} elseif( is_string($booking_data) && preg_match('/^[a-zA-Z0-9]{32}$/', $booking_data) ){
				$sql = $wpdb->prepare("SELECT * FROM " . EM_BOOKINGS_TABLE . " WHERE booking_uuid=%s", $booking_data);
				$booking = $wpdb->get_row($sql, ARRAY_A);
			}
			//booking meta
		    $booking['booking_meta'] = array(); // we don't use booking meta from the table anymore
		    if( !empty($booking['booking_id']) ) {
			    $sql = $wpdb->prepare("SELECT meta_key, meta_value FROM " . EM_BOOKINGS_META_TABLE . " WHERE booking_id=%d", $booking['booking_id']);
			    $booking_meta_results = $wpdb->get_results($sql, ARRAY_A);
		        $booking['booking_meta'] = $this->process_meta($booking_meta_results);
		    }
			//Save into the object
			$this->to_object($booking);
			$this->booking_status = absint($this->booking_status);
			$this->previous_status = $this->booking_status;
			$this->booking_date = !empty($booking['booking_date']) ? $booking['booking_date']:false;
		    if( empty($this->booking_uuid) ) {
			    if( !empty($this->booking_id) ){
				    $this->booking_uuid = md5($this->ticket_booking_id); // fallback, create a consistent but unique MD5 hash in case it's not saved for some reason.
			    } else {
				    $this->booking_uuid = $this->generate_uuid();
			    }
		    }
			// format status of rsvp into an int
		    $this->booking_rsvp_status = $this->booking_rsvp_status === '' || $this->booking_rsvp_status === null ? null : absint($this->booking_rsvp_status);
		}else{
		    $this->booking_uuid = $this->generate_uuid();
	    }
		//Do it here so things appear in the po file.
		$this->status_array = array(
			0 => __('Pending','events-manager'),
			1 => __('Approved','events-manager'),
			2 => __('Rejected','events-manager'),
			3 => __('Cancelled','events-manager'),
			4 => __('Awaiting Online Payment','events-manager'),
			5 => __('Awaiting Payment','events-manager'),
			6 => __('Waitlist','events-manager'),
			7 => __('Waitlist Approved','events-manager'),
			8 => __('Waitlist Expired','events-manager'),
		);
		$this->compat_keys(); //deprecating in 6.0
		//do some legacy checking here for bookings made prior to 5.4, due to how taxes are calculated
		$this->get_tax_rate();
		if( !empty($this->legacy_tax_rate) ){
			//reset booking_price, it'll be recalculated later (if you're using this property directly, don't use $this->get_price())
	    	$this->booking_price = $this->booking_taxes = null;
		}
		// typecast things
		$this->timeslot_id = is_numeric($this->timeslot_id) ? absint($this->timeslot_id) : null;
		$this->booking_id = is_numeric($this->booking_id) ? absint($this->booking_id) : null;
		$this->event_id = is_numeric($this->event_id) ? absint($this->event_id) : null;
		// allow others to intervene
		do_action('em_booking', $this, $booking_data);
	}

	
	function __get( $prop ){
	    //get the modified or created date from the DB only if requested, and save to object
	    if( $prop == 'timestamp' ){
	    	if( $this->date() === false ) return 0;
	    	return $this->date()->getTimestampWithOffset();
	    }elseif( $prop == 'language' ){
	    	if( !empty($this->booking_meta['lang']) ){
	    		return $this->booking_meta['lang'];
		    }
	    }elseif( $prop == 'person' ){
	    	return $this->get_person();
	    }elseif( $prop == 'date' ){
			return $this->date();
	    }elseif( $prop == 'uuid' ){
		    return $this->booking_uuid;
	    } elseif ( $prop === 'event_id' ) {
		    return $this->get_event_uid();
	    }
	    return null;
	}
	
	public function __set( $prop, $val ){
		if( $prop == 'timestamp' ){
			if( $this->date() !== false ) $this->date()->setTimestamp($val);
		}elseif( $prop == 'language' ){
			$this->booking_meta['lang'] = $val;
		}elseif( $prop == 'person' ){
			// prevent non EM_Person objects from being set
			if( $val instanceof EM_Person ) {
				$this->person_id = $val->ID;
				$this->person = $val;
			} else {
				$this->person = null;
			}
		} elseif ( $prop === 'event_id' ) {
			return $this->set_event_id( $val );
		}
		parent::__set( $prop, $val );
	}
	
	public function __isset( $prop ){
		if( $prop == 'timestamp' ) return $this->date()->getTimestamp() > 0;
		if( $prop == 'language' ) return !empty($this->booking_meta['lang']);
		return  parent::__isset( $prop );
	}
	
	/**
	 * Return relevant fields that will be used for storage, excluding things such as event and ticket objects that should get reloaded
	 * @return string[]
	 */
	public function __sleep(){
		$array = array('booking_id','booking_uuid','event_id','timeslot_id','person_id','booking_price','booking_spaces','booking_comment','booking_status','booking_tax_rate','booking_taxes','booking_meta','notes','booking_date','person','feedback_message','errors','mails_sent','custom','previous_status','status_array','manage_override','tickets_bookings');
		if( !empty($this->bookings) ) $array[] = 'bookings'; // EM Pro backwards compatibility
		return apply_filters('em_booking_sleep', $array, $this);
	}
	
	/**
	 * Repopulate the ticket bookings with this object and its event reference.
	 */
	public function __wakeup(){
		// we need to do this here because the __wakeup function bubbles up from the innermost class
		$this->get_tickets_bookings()->booking = $this;
		foreach( $this->get_tickets_bookings() as $EM_Ticket_Bookings ){
			$EM_Ticket_Bookings->booking = $this;
			foreach( $EM_Ticket_Bookings as $EM_Ticket_Booking ){
				$EM_Ticket_Booking->booking = $this;
			}
		}
	}

	public function get_option( $option, $default = null ){
		return $this->get_event()->get_option( $option, $default );
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

	public function set_event_id( $event_id ) {
		if ( preg_match('/^(\d+):(\d+)$/', $event_id, $matches) ) {
			$this->event_id = absint($matches[1]);
			$this->timeslot_id = absint($matches[2]);
		} elseif ( is_numeric( $event_id )) {
			$this->event_id = absint($event_id);
		}
	}

	public function get_timeslot() {
		if ( empty( $this->timeslot ) ) {
			$this->timeslot = new Timeslot( $this->timeslot_id, $this->get_event() );
		}
		return $this->timeslot;
	}

	function get_notes(){
		global $wpdb;
		if( !is_array($this->notes) && !empty($this->booking_id) ){
		  	$notes = $wpdb->get_results($wpdb->prepare("SELECT * FROM ". EM_META_TABLE ." WHERE meta_key='booking-note' AND object_id = %d", $this->booking_id), ARRAY_A);
		  	$this->notes = array();
		  	foreach($notes as $note){
		  		$this->notes[] = self::maybe_unserialize($note['meta_value']);
		  	}
		}elseif( empty($this->booking_id) ){
			$this->notes = array();
		}
		return $this->notes;
	}
	
	/**
	 * Saves the booking into the database, whether a new or existing booking
	 * @param bool $mail whether or not to email the user and contact people
	 * @return boolean
	 */
	function save($mail = true){
		global $wpdb;
		$table = EM_BOOKINGS_TABLE;
		do_action('em_booking_save_pre',$this); // last chance to circumvent
		if( empty($this->errors) && $this->can_manage() ){
			//update prices, spaces, person_id
			$this->get_spaces(true);
			$this->calculate_price();
			$this->person_id = (empty($this->person_id)) ? $this->get_person()->ID : $this->person_id;			
			//Step 1. Save the booking
			$data = $this->to_array();
			$data['booking_meta'] = serialize($data['booking_meta']);
			//update or save
			if($this->booking_id != ''){
				$update = true;
				$where = array( 'booking_id' => $this->booking_id );  
				$result = $wpdb->update($table, $data, $where, $this->get_types($data));
				$result = ($result !== false);
				$this->feedback_message = __('Changes saved','events-manager');
			}else{
				$update = false;
				$data_types = $this->get_types($data);
				$data['booking_date'] = $this->booking_date = gmdate('Y-m-d H:i:s');
				$data_types[] = '%s';
				// first check that the uuid is unique, if not change it and repeat until unique
				while( $wpdb->get_var( $wpdb->prepare("SELECT booking_uuid FROM $table WHERE booking_uuid=%s", $this->booking_uuid) ) ){
					$this->booking_uuid = $data['booking_uuid'] = $this->generate_uuid();
				}
				// now insert
				$result = $wpdb->insert($table, $data, $data_types);
			    $this->booking_id = $wpdb->insert_id;  
				$this->feedback_message = __('Your booking has been recorded','events-manager'); 
			}
			//Step 2. Insert meta and ticket bookings for this booking id if no errors so far
			if( $result === false ){
				$this->feedback_message = __('There was a problem saving the booking.', 'events-manager');
				$this->errors[] = __('There was a problem saving the booking.', 'events-manager');
			}else{
				//Step 2a - Save booking meta
				$wpdb->delete(EM_BOOKINGS_META_TABLE, array('booking_id' => $this->booking_id));
				$meta_insert = array();
				foreach( $this->booking_meta as $meta_key => $meta_value ){
					if( is_array($meta_value) ){
						$associative = array_keys($meta_value) !== range(0, count($meta_value) - 1);
						// we go down one level of array
						foreach( $meta_value as $kk => $vv ){
							if( is_array($vv) ) $vv = serialize($vv);
							if( $associative ) {
								$meta_insert[] = $wpdb->prepare('(%d, %s, %s)', $this->booking_id, '_'.$meta_key.'|'.$kk, $vv);
							}else{
								$meta_insert[] = $wpdb->prepare('(%d, %s, %s)', $this->booking_id, '_'.$meta_key.'|', $vv);
							}
						}
					}else{
						$meta_insert[] = $wpdb->prepare('(%d, %s, %s)', $this->booking_id, $meta_key, $meta_value);
					}
				}
				if( !empty($meta_insert) ){
					$wpdb->query('INSERT INTO '. EM_BOOKINGS_META_TABLE .' (booking_id, meta_key, meta_value) VALUES '. implode(',', $meta_insert));
				}
				// Step 2b - Save Ticket Bookings
				$tickets_bookings_result = $this->get_tickets_bookings()->save();
				if( !$tickets_bookings_result ){
					if( !$update ){
						//delete the booking and tickets, instead of a transaction
						$this->delete();
					}
					$this->errors[] = __('There was a problem saving the booking.', 'events-manager');
					$this->add_error( $this->get_tickets_bookings()->get_errors() );
				} else {
					// save the ticket data back into the booking meta
				}
			}
			// Step 3. Run filter for return value before sending emails
			$this->flush_event_cache();
			$this->compat_keys();
			$return = apply_filters('em_booking_save', ( count($this->errors) == 0 ), $this, $update);
			//Final Step: email if necessary after all the saving has been done
			if ( $return  && $mail ) {
				$this->email();
			}
			if( $return && empty($update) ){
				/**
				 * When a booking has been added to an event
				 *
				 * @param EM_Booking $this The EM_Booking object just added
				 * @param boolean $mail If a mail would have been sent (if applicable)
				 */
				do_action('em_booking_added', $this, $mail);
			}
			return $return;
		}else{
			$this->feedback_message = __('There was a problem saving the booking.', 'events-manager');
			if( !$this->can_manage() ){
				$this->add_error(sprintf(__('You cannot manage this %s.', 'events-manager'),__('Booking','events-manager')));
			}
		}
		return apply_filters('em_booking_save', false, $this, false);
	}
	
	/**
	 * Drops the cached event this booking belongs to, whose bookings and spaces counts are stale as soon as one of its bookings changes.
	 */
	protected function flush_event_cache(){
		EM_Event::flush_cache( array( $this->get_event_id(), $this->get_event_uid() ) );
	}
	
	/**
	 * Gets the user meta for this booking, which may reside withih the booking context or in the user meta context.
	 *
	 * Returns null if not defined.
	 *
	 * @param $meta_key
	 *
	 * @return mixed
	 */
	public function get_user_meta( $meta_key ) {
		if( $this->person_id == 0 ) {
			$meta_value = $this->booking_meta['registration'][ $meta_key ] ?? null;
		} else {
			$meta_value = get_user_meta( $this->person_id, $meta_key, true );
			if( $meta_value === '' ) $meta_value = null;
		}
		return apply_filters('em_booking_get_user_meta', $meta_value, $meta_key, $this);
	}
	
	/**
	 * Gets meta stored in booking meta, useful especially for data that may require interception such as at a multiple booking level.
	 *
	 * @param $meta_key
	 *
	 * @return mixed|null
	 */
	public function get_meta( $meta_key ) {
		$meta_value = $this->booking_meta[$meta_key] ?? null;
		return apply_filters('em_booking_get_meta', $meta_value, $meta_key, $this);
	}
	
	public function update_user_meta( $meta_key, $meta_value ) {
		global $wpdb;
		// set the meta in booking object first
		$this->booking_meta['registration'][$meta_key] = $meta_value;
		// check if this is in no-user mode, if so we save directly to the DB, otherwise we save it directly to the usermeta table
		if( (int) $this->person_id === 0 ) {
			$meta_row_key = '_registration|' . $meta_key;
			$exists = $wpdb->get_var( $wpdb->prepare( 'SELECT COUNT(*) FROM '. EM_BOOKINGS_META_TABLE .' WHERE booking_id=%d AND meta_key=%s', $this->booking_id, $meta_row_key ) );
			if( $exists ) {
				$wpdb->update( EM_BOOKINGS_META_TABLE, array('meta_value' => $meta_value), array('booking_id' => $this->booking_id, 'meta_key' => $meta_row_key) );
			} else {
				$wpdb->insert( EM_BOOKINGS_META_TABLE, array('booking_id' => $this->booking_id, 'meta_key' => $meta_row_key, 'meta_value' => $meta_value) );
			}
		} else {
			update_user_meta( $this->person_id, $meta_key, $meta_value );
		}
	}
	
	/**
	 * Update a specific key value in the booking meta data, or create one if it doesn't exist. If set to null it'll remove that value
	 * @param $meta_key
	 * @param $meta_value
	 * @return bool
	 * @since 5.9.11
	 */
	public function update_meta( $meta_key, $meta_value, $subkey = null ) {
		global $wpdb;
		if( !$this->booking_id ) return false;
		if( $subkey !== null ) {
			// Update a specific subkey without affecting other records.
			if( !isset($this->booking_meta[$meta_key]) || !is_array($this->booking_meta[$meta_key]) )
				$this->booking_meta[$meta_key] = array();
			if( $meta_value === null ) {
				unset($this->booking_meta[$meta_key][$subkey]);
			} else {
				$this->booking_meta[$meta_key][$subkey] = $meta_value;
			}
			$booking_meta = serialize($this->booking_meta);
			$wpdb->update( EM_BOOKINGS_TABLE, array('booking_meta' => $booking_meta), array('booking_id' => $this->booking_id) );
			$meta_table_key = '_' . $meta_key . '|' . $subkey;
			if( $meta_value === null ) {
				$result = $wpdb->delete( EM_BOOKINGS_META_TABLE, array('booking_id' => $this->booking_id, 'meta_key' => $meta_table_key) );
			} else {
				$existing = $wpdb->get_var( $wpdb->prepare("SELECT COUNT(*) FROM " . EM_BOOKINGS_META_TABLE . " WHERE booking_id=%d AND meta_key=%s", $this->booking_id, $meta_table_key) );
				if( $existing ) {
					$result = $wpdb->update( EM_BOOKINGS_META_TABLE, array('meta_value' => $meta_value), array('booking_id' => $this->booking_id, 'meta_key' => $meta_table_key) );
				} else {
					$result = $wpdb->insert( EM_BOOKINGS_META_TABLE, array('booking_id' => $this->booking_id, 'meta_key' => $meta_table_key, 'meta_value' => $meta_value) );
				}
			}
		} else {
			if( $meta_value === null ) {
				unset($this->booking_meta[$meta_key]);
			}else{
				$this->booking_meta[$meta_key] = $meta_value;
			}
			// add to new meta table if not exists
			if( is_array($meta_value) ){
				// associative arrays are deleted by prefix key
				$result = $wpdb->query( $wpdb->prepare('DELETE FROM '. EM_BOOKINGS_META_TABLE .' WHERE booking_id=%d AND meta_key LIKE %s', $this->booking_id, '_' . $meta_key . '|%') );
			}else{
				$result = $wpdb->delete( EM_BOOKINGS_META_TABLE, array('booking_id' => $this->booking_id, 'meta_key' => $meta_key) );
			}
			// if null, then we already deleted it and skip this
			if( $meta_value !== null ) {
				if( is_array($meta_value) ){
					$associative = array_keys($meta_value) !== range(0, count($meta_value) - 1);
					// we go down one level of array
					$meta_insert = array();
					foreach( $meta_value as $kk => $vv ){
						if( is_array($vv) ) $vv = serialize($vv);
						if( $associative ) {
							$meta_insert[] = $wpdb->prepare('(%d, %s, %s)', $this->booking_id, '_'.$meta_key.'|'.$kk, $vv);
						}else{
							$meta_insert[] = $wpdb->prepare('(%d, %s, %s)', $this->booking_id, '_'.$meta_key.'|', $vv);
						}
					}
					if( !empty($meta_insert) ){
						$result = $wpdb->query('INSERT INTO '. EM_BOOKINGS_META_TABLE .' (booking_id, meta_key, meta_value) VALUES '. implode(',', $meta_insert));
					}
				}else{
					$result = $wpdb->insert( EM_BOOKINGS_META_TABLE, array('booking_id' => $this->booking_id, 'meta_key' => $meta_key, 'meta_value' => $meta_value));
				}
			}
		}
		$booking_meta = serialize($this->booking_meta);
		$wpdb->update( EM_BOOKINGS_TABLE, array('booking_meta' => $booking_meta), array('booking_id' => $this->booking_id) );
		// fire filter
		return apply_filters('em_booking_update_meta', $result !== false, $meta_key, $meta_value, $this);
	}
	
	/**
	 * Load a record into this object by passing an associative array of table criteria to search for.
	 * Returns boolean depending on whether a record is found or not. 
	 * @param $search
	 * @return boolean
	 */
	function get($search) {
		global $wpdb;
		$conds = array(); 
		foreach($search as $key => $value) {
			if( array_key_exists($key, $this->fields) ){
				$value = esc_sql($value);
				$conds[] = "`$key`='$value'";
			} 
		}
		$sql = "SELECT * FROM ". EM_BOOKINGS_TABLE ." WHERE " . implode(' AND ', $conds) ;
		$result = $wpdb->get_row($sql, ARRAY_A);
		if($result){
			$this->to_object($result);
			$this->person = new EM_Person($this->person_id);
			return true;
		}else{
			return false;
		}
	}
	
	/**
	 * Get posted data and save it into the object (not db)
	 * @return boolean
	 */
	function get_post( $override_availability = false ){
		if( EM_Bookings::$disable_restrictions ) $override_availability = true;
		$this->tickets_bookings = new EM_Tickets_Bookings($this);
		do_action('em_booking_get_post_pre',$this);
		$result = array();
		$this->set_event_id( $_REQUEST['event_id'] );
		if ( $this->get_event()->event_status != 1 || $this->get_event()->event_active_status != 1 ) {
			$this->add_error( __('This event is not available or has been cancelled', 'events-manager') ); // uncommon, not needed for custom error.
		}
		if( isset($_REQUEST['em_tickets']) && is_array($_REQUEST['em_tickets']) && ($_REQUEST['em_tickets'] || $override_availability) ){
			if( !$this->get_tickets_bookings()->get_post( $override_availability ) ){
				$this->add_error($this->tickets_bookings->get_errors());
			}
			$this->booking_comment = (!empty($_REQUEST['booking_comment'])) ? wp_kses_data(wp_unslash($_REQUEST['booking_comment'])):'';
			//allow editing of tax rate
			if( !empty($this->booking_id) && $this->can_manage() ){ 
			    $this->booking_tax_rate = (!empty($_REQUEST['booking_tax_rate']) && is_numeric($_REQUEST['booking_tax_rate'])) ? $_REQUEST['booking_tax_rate']:$this->booking_tax_rate; 
			}
			//recalculate spaces/price
			$this->get_spaces(true);
			$this->calculate_price();
			//get person
			$this->get_person();
			//re-run compatiblity keys function
			$this->compat_keys(); //depracating in 6.0
		}
		/*
		if( !$this->booking_id && !empty($_REQUEST['booking_intent']) && preg_match('/^[a-zA-Z0-9]{32}/', $_REQUEST['booking_intent']) ){
			$this->booking_uuid = sanitize_key($_REQUEST['booking_intent']);
		}
		*/
		return apply_filters('em_booking_get_post', empty($this->errors), $this);
	}
	
	function validate( $override_availability = false ){
		do_action( 'em_booking_validate_pre', $this, $override_availability );
		if( EM_Bookings::$disable_restrictions ) $override_availability = true;
		//step 1, basic info
		$basic = ( empty($this->event_id) || is_numeric($this->event_id)) && (empty($this->person_id) || is_numeric($this->person_id));
		if( !$basic ){
			$this->add_error('Incomplete booking information provided.');
		}
		// make sure event is not a recurring event with timeslots
		if ( !$this->timeslot_id && $this->get_event()->get_option('dbem_event_timeslots_enabled') ) {
			if ( $this->get_event()->has_timeslots() ) {
				$this->add_error('Incomplete booking information provided. No timeslot selected.');
			}
		}
		//give some errors in step 1
		if( !is_numeric($this->get_spaces()) || $this->booking_spaces == 0 ){
			$this->add_error( $this->get_option('dbem_booking_feedback_min_space'));
		}
		//step 2, tickets bookings info
		if( !$this->get_tickets_bookings()->validate( $override_availability ) ){
			$this->errors = array_merge( $this->errors, $this->get_tickets_bookings()->get_errors() );
		}
		
		if( !$override_availability ){
			// are bookings even available due to event and ticket cut-offs/restrictions? This is checked earlier in booking processes, but is relevant in checkout/cart situations where a previously-made booking is validated just before checkout
			if( $this->get_event()->rsvp_end()->getTimestamp() < time() ){
				$result = false;
				$this->add_error( $this->get_option('dbem_bookings_form_msg_closed'));
			}
			//is there enough space overall?
			if( $this->get_event()->get_bookings()->get_available_spaces() < $this->get_spaces() ){
				$result = false;
				$this->add_error( $this->get_option('dbem_booking_feedback_full'));
			}
		}
		//can we book this amount of spaces at once?
		if( $this->get_event()->event_rsvp_spaces > 0 && $this->get_spaces() > $this->get_event()->event_rsvp_spaces ){
		    $result = false;
		    $this->add_error( sprintf( $this->get_option('dbem_booking_feedback_spaces_limit'), $this->get_event()->event_rsvp_spaces));
		}
		do_action( 'em_booking_validate_after', $this, $override_availability );
		return apply_filters('em_booking_validate', empty($this->errors), $this);
	}
	
	/**
	 * Get the total number of spaces booked in THIS booking. Setting $force_refresh to true will recheck spaces, even if previously done so.
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_spaces( $force_refresh=false ){
		if($this->booking_spaces == 0 || $force_refresh == true ){
			$this->booking_spaces = $this->get_tickets_bookings()->get_spaces($force_refresh);
		}
		return apply_filters('em_booking_get_spaces',$this->booking_spaces,$this);
	}
	
	/* Price Calculations */
	
	/**
	 * Gets the total price for this whole booking, including any discounts, taxes, and any other additional items. In other words, what the person has to pay or has supposedly paid.
	 * This price shouldn't change once established, unless there's any alteration to the booking itself that'd affect the price, such as a change in ticket numbers, discount, etc.
	 * @param boolean $format
	 * @return double|string
	 */
	function get_price( $format = false, $format_depricated = null ){
	    if( $format_depricated !== null ) $format = $format_depricated; //support for old parameters, will be depricated soon
	    //recalculate price here only if price is not actually set
		if( $this->booking_price === null ){
		    $this->calculate_price();
		    /* Deprecated filter - Equivalent of em_booking_calculate_price, please use that instead */
			$this->booking_price = apply_filters('em_booking_get_price', $this->booking_price, $this);
		}
		//return booking_price, formatted or not
		if($format){
			return $this->format_price($this->booking_price);
		}
		return round($this->booking_price,2);
	}
	
	/**
	 * Total of tickets without taxes, discounts or any other modification.
	 * @param boolean $format
	 * @return double|string
	 */
	function get_price_base( $format = false ){
	    $price = apply_filters('em_booking_get_price_base', $this->get_tickets_bookings()->get_price(), $this);
		if($format){
			return $this->format_price($price);
		}
	    return $price;
	}
	
	/**
	 * Get total price of booking before taxes are applied, this includes discounts and surcharges.
	 * @param $format
	 * @param $include_adjustments
	 *
	 * @return int|string
	 */
	function get_price_pre_taxes( $format = false, $include_adjustments = true ){
	    $price = $base_price = $this->get_price_base();
	    //apply pre-tax discounts
	    if( $include_adjustments ){
		    $price -= $this->get_price_adjustments_amount('discounts', 'pre', $base_price);
		    $price += $this->get_price_adjustments_amount('surcharges', 'pre', $base_price);
	    }
	    $price = apply_filters('em_booking_get_price_pre_taxes', $price, $base_price, $this, $include_adjustments);
	    if( $price < 0 ){ $price = 0; } //no negative prices
	    //return amount of taxes applied, formatted or not
	    if( $format ) return $this->format_price($price);
	    return $price;
	}
	
	/**
	 * Gets price AFTER taxes and (optionally) post-tax discounts and surcharges have also been added.
	 * @param boolean $format
	 * @param boolean $include_adjustments If set to true discounts and surcharges won't be applied to the overall price.
	 * @return double|string
	 */
	function get_price_post_taxes( $format = false, $include_adjustments = true ){
	    //get price before taxes
	    $price = $this->get_price_pre_taxes( false, $include_adjustments );
	    //add taxes to price
	    if( $this->get_tax_rate() > 0 ){
	        $this->booking_taxes = $price * ($this->get_tax_rate()/100); //calculate and save tax amount
		    $price += $this->booking_taxes; //add taxes
		    $this->taxes_applied = true;
	    }
	    //apply post-tax discounts
	    $price_after_taxes = $price;
	    if( $include_adjustments ){
		    $price -= $this->get_price_adjustments_amount('discounts', 'post', $price_after_taxes);
		    $price += $this->get_price_adjustments_amount('surcharges', 'post', $price_after_taxes);
	    }
	    $price = apply_filters('em_booking_get_price_post_taxes', $price, $price_after_taxes, $this, $include_adjustments);
	    if( $price < 0 ){ $price = 0; } //no negative prices
	    //return amount of taxes applied, formatted or not
	    if( $format ) return $this->format_price($price);
	    return $price;
	}
	
	/**
	 * Get amount of taxes applied to this booking price.
	 * @param boolean $format
	 * @return double|string
	 */
	function get_price_taxes( $format=false ){
	    if( $this->booking_taxes !== null ){
	        $this->booking_taxes; //taxes already calculated
	    }else{
	        $this->calculate_price(); //recalculate price and taxes
	    }
		//return amount of taxes applied, formatted or not
	    if( $format ){
	        return $this->format_price($this->booking_taxes);
	    }
	    return $this->booking_taxes;
	}
	
	/**
	 * Calculates (or recalculates) the price of this booking including taxes, discounts etc., saves it to the booking_price property and writes to relevant properties booking_meta variables
	 * @return double
	 */
	function calculate_price(){
		//any programatic price adjustments should be added here, otherwise you need to run this function again
		do_action('em_booking_pre_calculate_price', $this);
	    //reset price and taxes calculations
	    $this->booking_price = $this->booking_taxes = null;
	    //get post-tax price and save it to booking_price
	    $this->booking_price = apply_filters('em_booking_calculate_price', $this->get_price_post_taxes(), $this);
	    return $this->booking_price; 
	}
	
	/* 
	 * Gets tax rate of booking
	 * @see EM_Object::get_tax_rate()
	 */
	function get_tax_rate( $decimal = false ){
	    if( $this->booking_tax_rate === null ){
	        //booking not saved or tax never defined
	        if( !empty($this->booking_id) && $this->get_option('dbem_legacy_bookings_tax', 'x') !== 'x'){ //even if 0 if defined as tax rate we still use it, delete the option entirely to stop
	            //no tax applied yet to an existing booking, or tax possibly applied (but handled separately in EM_Tickets_Bookings but in legacy < v5.4
	            //sort out MultiSite nuances
	            if( EM_MS_GLOBAL && $this->get_event()->blog_id != get_current_blog_id() ){
	            	//MultiSite AND Global tables enabled AND this event belongs to another blog - get settings for blog that published the event
					$this->booking_tax_rate = get_blog_option($this->get_event()->blog_id, 'dbem_legacy_bookings_tax');
	            }else{
	            	//get booking from current site, whether or not we're in MultiSite
	            	$this->booking_tax_rate = $this->get_option('dbem_legacy_bookings_tax');
	            }
	            $this->legacy_tax_rate = true;
	        }else{
	            //first time we're applying tax rate
	            $this->booking_tax_rate = $this->get_event()->get_tax_rate();
	        }
	    }
		if ( !is_float($this->booking_tax_rate) ) {
			$this->booking_tax_rate = str_replace(',', '.', (string) $this->booking_tax_rate);
			$this->booking_tax_rate = (float) preg_replace('/[^0-9.]/', '', $this->booking_tax_rate);
		}
	    $this->booking_tax_rate = $this->booking_tax_rate > 0 ? $this->booking_tax_rate : 0;
	    $this->booking_tax_rate = apply_filters('em_booking_get_tax_rate', $this->booking_tax_rate, $this);
	    if( $this->booking_tax_rate > 0 && $decimal ){
	    	return $this->booking_tax_rate / 100;
	    }else{
		    return $this->booking_tax_rate;
	    }
	}
	
	/* START Price Adjustment Functions */
	//now we can use one function for both discounts and surcharges, the three functions below are now deprecated.
	/**
	 * DEPRECATED. Use $this->get_price_adjustments('discounts'); instead.
	 */
	function get_price_discounts(){
		return apply_filters('em_booking_get_price_discounts', $this->get_price_adjustments('discounts'), $this);
	}
	/**
	 * DEPRECATED - Use $this->get_price_adjustments_amount('discounts', $pre_or_post, $price); instead.
	 */
	function get_price_discounts_amount( $pre_or_post = 'pre', $price = false ){
		return $this->get_price_adjustments_amount( 'discounts', $pre_or_post, $price );
	}
	/**
	 * DEPRECATED - Use get_price_discounts_summary('discounts', $pre_or_post, $price); instead.
	 */
	function get_price_discounts_summary( $pre_or_post = 'pre', $price = false ){
		return $this->get_price_adjustments_summary( 'discounts', $pre_or_post, $price );
	}
	
	/**
	 * Returns an array of discounts to be applied to a booking. Here is an example of an array item that is expected:
	 * array('name' => 'Name of Discount', 'type'=>'% or #', 'amount'=> 0.00, 'desc' => 'Comments about discount', 'tax'=>'pre/post', 'data' => 'any info for hooks to use' );
	 * About the array keys:
	 * type - # means a fixed amount of discount, % means a percentage off the base price
	 * amount - if type is a percentage, it is written as a number from 0-100, e.g. 10 = 10%
	 * tax - 'pre' means discount is applied before tax, 'post' means after tax
	 * data - any data to be stored that can be used by actions/filters
	 * @param string $type The type of adjustment you would like to retrieve. This would normally be 'discounts' or 'surcharges'.
	 * @return array
	 */
	function get_price_adjustments( $type ){
		$adjustments = array();
		if( !empty($this->booking_meta[$type]) && is_array($this->booking_meta[$type]) ){
			$adjustments = $this->booking_meta[$type];
		}
		//run this filter to be backwards compatible, e.g. em_booking_get_price_discount
		if( $type == 'discounts' ){
			$adjustments = apply_filters('em_booking_get_price_discounts', $adjustments, $this);
		}
		return apply_filters('em_booking_get_price_adjustments', $adjustments, $type, $this);
	}
	
	/**
	 * Returns a numerical amount to adjust the price by, in the context of a certain type and before or after taxes.
	 * This will be a positive number whether or not this is to be added or subtracted from the price.
	 * @param string $type The type of adjustment to get, which would normally be 'discounts' or 'surcharges'
	 * @param string $pre_or_post Adjustments limited to 'pre' (before), 'post' (after) taxes or 'both'
	 * @param float $price Price relative to be adjusted.
	 * @return float
	 */
	function get_price_adjustments_amount( $type, $pre_or_post = 'both', $price = false ){
		$adjustments = $this->get_price_adjustments_summary($type, $pre_or_post, $price);
		$adjustment_amount = 0;
		foreach($adjustments as $adjustment){
			$adjustment_amount += $adjustment['amount_adjusted'];
		}
		return $adjustment_amount;
	}
	
	/**
	 * Provides an array summary of adjustments to make to the price, in the context of a certain type and before or after taxes.
	 * @param string $type The type of adjustment to get, which would normally be 'discounts' or 'surcharges'
	 * @param string $pre_or_post Adjustments limited to 'pre' (before), 'post' (after) taxes or 'both'
	 * @param float $price Price to calculate relative to adjustments. If not supplied or if $pre_or_post is 'both', price is automatically obtained from booking instance according to pre/post taxes requirement. 
	 * @return array
	 */
	function get_price_adjustments_summary( $type, $pre_or_post = 'both', $price = false ){
		if( $pre_or_post == 'both' ){
			$adjustment_summary_pre = $this->get_price_adjustments_summary($type, 'pre');
			$adjustment_summary_post = $this->get_price_adjustments_summary($type, 'post'); 
			return $adjustment_summary = array_merge($adjustment_summary_pre, $adjustment_summary_post);
		}
		$adjustments = $this->get_price_adjustments($type);
		$adjustment_summary = array();
		if( $price === false ){
			if( $pre_or_post == 'post' ){
				$price = $this->get_price_pre_taxes() + $this->get_price_taxes();
			}else{
				$price = $this->get_price_base();
			}
		}
		foreach($adjustments as $adjustment){
			$adjustment_amount = 0;
			if( !empty($adjustment['amount']) ){
				if( !empty($adjustment['tax']) && $adjustment['tax'] == $pre_or_post ){
					if( !empty($adjustment['type']) ){
						$desc = !empty($adjustment['desc']) ? $adjustment['desc'] : '';
						$adjustment_summary_item = array('name' => $adjustment['name'], 'desc' => $desc, 'adjustment'=>'0', 'amount_adjusted'=>0, 'tax'=>$pre_or_post);
						if( $adjustment['type'] == '%' ){ //adjustment by percentage
							$adjustment_summary_item['amount_adjusted'] = round($price * ($adjustment['amount']/100),2);
							$adjustment_summary_item['amount'] = $this->format_price($adjustment_summary_item['amount_adjusted']);
							$adjustment_summary_item['adjustment'] = number_format($adjustment['amount'],2).'%';
							$adjustment_summary[] = $adjustment_summary_item;
						}elseif( $adjustment['type'] == '#' ){ //adjustment by amount
							$adjustment_summary_item['amount_adjusted'] = round($adjustment['amount'],2);
							$adjustment_summary_item['amount'] = $this->format_price($adjustment_summary_item['amount_adjusted']);
							$adjustment_summary_item['adjustment'] = $this->format_price($adjustment['amount']);
							$adjustment_summary[] = $adjustment_summary_item;
						}
					}
				}
			}
		}
		return $adjustment_summary;
	}
	/* END Price Adjustment Functions */
	
	/**
	 * When generating totals at the bottom of a booking, this creates a useful array for displaying the summary in a meaningful way. 
	 */
	function get_price_summary_array(){
	    $summary = array();
	    //get base price of bookings
	    $summary['total_base'] = $this->get_price_base();
	    //apply pre-tax discounts
	    $summary['discounts_pre_tax'] = $this->get_price_adjustments_summary('discounts', 'pre');
	    $summary['surcharges_pre_tax'] = $this->get_price_adjustments_summary('surcharges', 'pre');
	    //add taxes to price
		$summary['taxes'] = array('rate'=> 0, 'amount'=> 0);
	    if( $this->get_price_taxes() > 0 ){
		    $summary['taxes'] = array('rate'=> number_format($this->get_tax_rate(),2, $this->get_option('dbem_bookings_currency_decimal_point'), $this->get_option('dbem_bookings_currency_thousands_sep')).'%', 'amount'=> $this->get_price_taxes(true));
	    }
	    //apply post-tax discounts
	    $summary['discounts_post_tax'] = $this->get_price_adjustments_summary('discounts', 'post');
	    $summary['surcharges_post_tax'] = $this->get_price_adjustments_summary('surcharges', 'post');
	    //final price
	    $summary['total'] =  $this->get_price(true);
	    return $summary;
	}
	
	/**
	 * Returns the amount paid for this booking. By default, a booking is considered either paid in full or not at all depending on whether the booking is confirmed or not.
	 * @param boolean $format If set to true a currency-formatted string value is returned
	 * @return string|float
	 */
	function get_total_paid( $format = false ){
		$status = ($this->booking_status == 0 && !$this->get_option('dbem_bookings_approval') ) ? 1:$this->booking_status;
		$total = $status ? $this->get_price() : 0;
		$total = apply_filters('em_booking_get_total_paid', $total, $this);
		if( $format ){
			return $this->format_price($total);
		}
		return $total;
	}
	
	/**
	 * Returns the 3-character ISO-4217 currency code of this booking.
	 * NOTE!
	 * This is an in-progress feature and not recommended overriding as this will cause unexpected results. For now, it will always return the general currency setting from EM.
	 * You can, however, use this function to reference the current currency of this booking and expect that in the future if the currency varies it will be reflected here.
	 *
	 * @return string
	 */
	function get_currency(){
		$currency = $this->get_option('dbem_bookings_currency','USD');
		return apply_filters('em_booking_get_currency', $currency, $this);
	}
	
	/* Get Objects linked to booking */
	
	/**
	 * Gets the event this booking belongs to and saves a reference in the event property
	 * @return EM_Event
	 */
	function get_event(){
		global $EM_Event;
		if( ! ( $this->event instanceof EM_Event && ($this->event->event_id == $this->get_event_uid() || (EM_ML::$is_ml && !empty($this->event->event_translation) && $this->event->event_parent == $this->event_id)) ) ) {
			// do nothing, we make sure timeslots match next step
			if ( is_object( $EM_Event ) && $EM_Event->get_id() == $this->event_id && $this->event ) {
				$this->event = $EM_Event;
			} else {
				$this->event = em_get_event( $this->get_event_uid() );
			}
		}
		// convert event association with EM_Event object
		if ( $this->timeslot_id ) {
			try {
				$this->event = $this->event->convert_to_timeslot( $this->timeslot_id, false );
			} catch ( Exception $e ) {}
		}
		return apply_filters('em_booking_get_event', $this->event, $this);
	}
	
	/**
	 * Gets the ticket object this booking belongs to, saves a reference in ticket property
	 * @return EM_Tickets
	 */
	function get_tickets(){
		if( is_object($this->tickets) && get_class($this->tickets)=='EM_Tickets' ){
			return apply_filters('em_booking_get_tickets', $this->tickets, $this);
		}else{
			$this->tickets = new EM_Tickets($this);
		}
		return apply_filters('em_booking_get_tickets', $this->tickets, $this);
	}
	
	/**
	 * Gets the ticket object this booking belongs to, saves a reference in ticket property
	 * @return EM_Tickets_Bookings EM_Tickets_Bookings
	 */
	function get_tickets_bookings(){
		global $wpdb;
		if( !is_object($this->tickets_bookings) || get_class($this->tickets_bookings) != 'EM_Tickets_Bookings'){
			$this->tickets_bookings = new EM_Tickets_Bookings($this);
		}
		return apply_filters('em_booking_get_tickets_bookings', $this->tickets_bookings, $this);
	}
	
	/**
	 * @return EM_Person
	 */
	function get_person(){
		global $EM_Person;
		if( is_object($this->person) && get_class($this->person)=='EM_Person' && ($this->person->ID == $this->person_id || empty($this->person_id) ) ){
			//This person is already included, so don't do anything
		}elseif( is_object($EM_Person) && ($EM_Person->ID === $this->person_id || $this->booking_id == '') ){
			$this->person = $EM_Person;
			$this->person_id = $this->person->ID;
		}elseif( is_numeric($this->person_id) ){
			$this->person = new EM_Person($this->person_id);
		}else{
			$this->person = new EM_Person(0);
			$this->person_id = $this->person->ID;
		}
		//if this user is the parent user of disabled registrations, replace user details here:
		if( $this->person->ID === 0 && (empty($this->person->loaded_no_user) || $this->person->loaded_no_user != $this->booking_id) ){
			//override any registration data into the person objet
			if( !empty($this->booking_meta['registration']) ){
				foreach($this->booking_meta['registration'] as $key => $value){
					$this->person->$key = $value;
				}
			}
			$this->person->user_email = ( !empty($this->booking_meta['registration']['user_email']) ) ? $this->booking_meta['registration']['user_email']:$this->person->user_email;
			//if a full name is given, overwrite the first/last name values IF they are also not defined
			if( !empty($this->booking_meta['registration']['user_name']) ){
				if( is_array($this->booking_meta['registration']['user_name']) ){
					$this->booking_meta['registration']['user_name'] = reset($this->booking_meta['registration']['user_name']); // prevent fatal errors further down, this is still a problem though
				}
				if( !empty($this->booking_meta['registration']['first_name']) ){
					//if last name isn't defined, provide the rest of the name minus the first name we just removed
					if( empty($this->booking_meta['registration']['last_name']) ){
						//first name is defined, so we remove it from full name in case we need the rest for surname
						$last_name = trim(str_replace($this->booking_meta['registration']['first_name'], '', $this->booking_meta['registration']['user_name']));
						$this->booking_meta['registration']['last_name'] = $last_name;
					}
				}else{
					//no first name defined, check for last name and act accordingly
					if( !empty($this->booking_meta['registration']['last_name']) ){
						//we do opposite of above, remove last name from full name and use the rest as first name
						$first_name = trim(str_replace($this->booking_meta['registration']['last_name'], '', $this->booking_meta['registration']['user_name']));
						$this->booking_meta['registration']['first_name'] = $first_name;
					}else{
						//no defined first or last name, so we use the name and take first string for first name, second part for surname
						$name_string = explode(' ',$this->booking_meta['registration']['user_name']);
						$this->booking_meta['registration']['first_name'] = array_shift($name_string);
						$this->booking_meta['registration']['last_name'] = implode(' ', $name_string);
					}
				}
			}
			$this->person->user_firstname = ( !empty($this->booking_meta['registration']['first_name']) ) ? $this->booking_meta['registration']['first_name']:__('Guest User','events-manager');
			$this->person->first_name = $this->person->user_firstname;
			$this->person->user_lastname = ( !empty($this->booking_meta['registration']['last_name']) ) ? $this->booking_meta['registration']['last_name']:'';
			$this->person->last_name = $this->person->user_lastname;
			$this->person->phone = ( !empty($this->booking_meta['registration']['dbem_phone']) ) ? $this->booking_meta['registration']['dbem_phone']:__('Not Supplied','events-manager');
			//build display name
			$full_name = $this->person->user_firstname  . " " . $this->person->user_lastname ;
			$full_name = trim($full_name);
			$display_name = ( empty($full_name) ) ? __('Guest User','events-manager'):$full_name;
			$this->person->display_name = $display_name;
			$this->person->loaded_no_user = $this->booking_id;
		}
		return apply_filters('em_booking_get_person', $this->person, $this);
	}
	
	/**
	 * Gets personal information from the $_REQUEST array and saves it to the $EM_Booking->booking_meta['registration'] array
	 * @return boolean
	 */
	function get_person_post(){
	    $user_data = array();
	    $registration = true;
	    if( empty($this->booking_meta['registration']) ) $this->booking_meta['registration'] = array();
	    // Check the e-mail address
	    $user_email = trim(wp_unslash($_REQUEST['user_email'])); //apostrophes will not be allowed otherwise
	    if ( $user_email == '' ) {
	    	$registration = false;
	    	$this->add_error(__( '<strong>ERROR</strong>: Please type your e-mail address.', 'events-manager') );
	    } elseif ( !is_email( $user_email ) ) {
	    	$registration = false;
	    	$this->add_error( __( '<strong>ERROR</strong>: The email address isn&#8217;t correct.', 'events-manager') );
	    }elseif(email_exists( $user_email ) && !$this->get_option('dbem_bookings_registration_disable_user_emails') ){
	    	$registration = false;
	    	$this->add_error( $this->get_option('dbem_booking_feedback_email_exists') );
	    }else{
	    	$user_data['user_email'] = $user_email;
	    }
	    //Check the user name
	    if( !empty($_REQUEST['user_name']) ){
	    	//split full name up and save full, first and last names
	    	$user_data['user_name'] = wp_kses(wp_unslash($_REQUEST['user_name']), array());
	    	$name_string = explode(' ',$user_data['user_name']);
	    	$user_data['first_name'] = array_shift($name_string);
	    	$user_data['last_name'] = implode(' ', $name_string);
	    }else{
		    //Check the first/last name
		    $name_string = array();
		    if( !empty($_REQUEST['first_name']) ){
		    	$user_data['first_name'] = $name_string[] = wp_kses(wp_unslash($_REQUEST['first_name']), array()); 
		    }
		    if( !empty($_REQUEST['last_name']) ){
		    	$user_data['last_name'] = $name_string[] = wp_kses(wp_unslash($_REQUEST['last_name']), array());
		    }
		    if( !empty($name_string) ) $user_data['user_name'] = implode(' ', $name_string);
	    }
	    //Check the phone
	    if( !empty($_REQUEST['dbem_phone']) ){
	    	$user_data['dbem_phone'] = wp_kses(wp_unslash($_REQUEST['dbem_phone']), array());
	    }
	    //Add booking meta
	    if( $registration ){
		    $this->booking_meta['registration'] = array_merge($this->booking_meta['registration'], $user_data);	//in case someone else added stuff
	    }
	    $registration = apply_filters('em_booking_get_person_post', $registration, $this, $user_data);
	    if( $registration ){
	        $this->feedback_message = __('Personal details have successfully been modified.', 'events-manager');
	    }
	    return $registration;
	}
	
	/**
	 * Displays a form containing user fields, used in no-user booking mode for editing guest users within a booking
	 * @return string
	 */
	function get_person_editor(){
		ob_start();
		$name = $this->get_person()->get_name();
		$email = $this->get_person()->user_email;
		$phone = ($this->get_person()->phone != __('Not Supplied','events-manager')) ? $this->get_person()->phone:'';
		if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'booking_modify_person' ){
		    $name = !empty($_REQUEST['user_name']) ? sanitize_text_field($_REQUEST['user_name']):$name;
		    $email = !empty($_REQUEST['user_email']) ? sanitize_email($_REQUEST['user_email']):$email;
		    $phone = !empty($_REQUEST['dbem_phone']) ? sanitize_text_field($_REQUEST['dbem_phone']):$phone;
		}
		?>
		<table class="em-form-fields">
			<tr><th><?php _e('Name','events-manager'); ?> : </th><td><input type="text" name="user_name" value="<?php echo esc_attr($name); ?>" ></td></tr>
			<tr><th><?php _e('Email','events-manager'); ?> : </th><td><input type="text" name="user_email" value="<?php echo esc_attr($email); ?>" ></td></tr>
			<tr><th><?php _e('Phone','events-manager'); ?> : </th><td><input type="tel" name="dbem_phone" value="<?php echo esc_attr($phone); ?>" ></td></tr>
			<?php do_action('em_booking_get_person_editor_bottom', $this ); ?>
		</table>
		<?php
		return apply_filters('em_booking_get_person_editor', ob_get_clean(), $this );
	}

	/**
	 * Returns a string representation of the booking's status
	 * @return string
	 */
	function get_status(){
		if( $this->booking_status === false && isset($this->previous_status) ) {
			$status_text = __('Deleted', 'events-manager');
		}else{
			$status_text = $this->status_array[ $this->booking_status ];
		}
		return apply_filters('em_booking_get_status', $status_text, $this);
	}
	
	/**
	 * I wonder what this does....
	 * @return boolean
	 */
	function delete(){
		global $wpdb;
		$result = false;
		if( $this->can_manage('manage_bookings','manage_others_bookings') ){
			$this->tickets_bookings = null; // reload tickets
			$this->get_tickets_bookings(); // get this before bookings deleted from DB
			$sql = $wpdb->prepare("DELETE FROM ". EM_BOOKINGS_TABLE . " WHERE booking_id=%d", $this->booking_id);
			$result = $wpdb->query( $sql );
			if( $result !== false ){
				//delete the tickets too
				$this->get_tickets_bookings()->delete();
				$this->previous_status = $this->booking_meta['previous_status'] = $this->booking_status;
				$this->booking_status = false;
				$this->feedback_message = sprintf(__('%s deleted', 'events-manager'), __('Booking','events-manager'));
				$wpdb->delete( EM_META_TABLE, array('meta_key'=>'booking-note', 'object_id' => $this->booking_id), array('%s','%d'));
				$wpdb->delete( EM_BOOKINGS_META_TABLE, array('booking_id'=> $this->booking_id), array('%d'));
				$this->deleted = true;
				$this->flush_event_cache();
				do_action('em_booking_deleted', $this);
			}else{
				$this->add_error(sprintf(__('%s could not be deleted', 'events-manager'), __('Booking','events-manager')));
			}
		}
		do_action('em_bookings_deleted', $result, array($this->booking_id), array($this->get_event_uid()));
		return apply_filters('em_booking_delete',( $result !== false ), $this);
	}
	
	/**
	 * Cancel a booking
	 * @param $email
	 * param array $email_args Overloaded
	 * @return bool
	 */
	function cancel( $email = true ){
		$func_args = func_get_args();
		$email_args = !empty($func_args[1]) ? $func_args[1] : array();
		if( $this->get_person()->ID == get_current_user_id() ){
			$this->manage_override = true; //normally, users can't manage a booking, only event owners, so we allow them to mod their booking status in this case only.
		}
		return $this->set_status(3, $email, false, $email_args);
	}
	
	/**
	 * Approve a booking.
	 * @param $email
	 * param array $email_args Overloaded
	 * @return bool
	 */
	function approve($email = true, $ignore_spaces = false ){
		$func_args = func_get_args();
		$email_args = !empty($func_args[2]) ? $func_args[2] : array();
		return $this->set_status(1, $email, $ignore_spaces, $email_args);
	}
	
	/**
	 * Reject a booking and save
	 * @param $email
	 * param array $email_args Overloaded
	 * @return bool
	 */
	function reject($email = true ){
		$func_args = func_get_args();
		$email_args = !empty($func_args[1]) ? $func_args[1] : array();
		return $this->set_status(2, $email, false, $email_args);
	}
	
	/**
	 * Unapprove a booking.
	 * @param $email
	 * param array $email_args Overloaded
	 * @return bool
	 */
	function unapprove( $email = true ){
		$func_args = func_get_args();
		$email_args = !empty($func_args[1]) ? $func_args[1] : array();
		return $this->set_status(0, $email, false, $email_args);
	}
	
	function uncancel( $email = true, $email_args = array() ) {
		if ( $this->can_uncancel() ) {
			// get status to uncancel to
			if ( isset($this->booking_meta['previous_status']) ) {
				$status = $this->booking_meta['previous_status'];
				if( $status == 2 ){ // we shouldn't reject an uncancelled booking!
					$status = 0;
				}
			} elseif ( defined('EM_BOOKINGS_UNCANCEL_STATUS') ) {
				$status = EM_BOOKINGS_UNCANCEL_STATUS;
			} else {
				$status = 0;
			}
			return $this->set_status( $status, $email, false, $email_args );
		} else {
			return false;
		}
	}
	
	/**
	 * Change the status of the booking. This will save to the Database too. 
	 * @param int $status
	 * @param bool $email
	 * @param bool $ignore_spaces
	 * param array $email_args Overloaded
	 * @return boolean
	 */
	function set_status($status, $email = true, $ignore_spaces = false ){
		global $wpdb;
		$action_string = strtolower($this->status_array[$status]);
		//if we're approving we can't approve a booking if spaces are full, so check before it's approved.
		// Hold a per-event lock across the full-check and the status write so two concurrent approvals can't both pass a stale space count and overbook.
		$status_lock_event_id = ( !$ignore_spaces && $status == 1 ) ? $this->get_event_id() : 0;
		$status_locked = $status_lock_event_id ? EM_Bookings::acquire_lock( $status_lock_event_id ) : false;
		if(!$ignore_spaces && $status == 1){
			if( !$this->is_reserved() && $this->get_event()->get_bookings()->get_available_spaces(true) < $this->get_spaces() && !$this->get_option('dbem_bookings_approval_overbooking') ){
				if( $status_locked ) EM_Bookings::release_lock( $status_lock_event_id );
				$this->feedback_message = sprintf(__('Not approved, spaces full.','events-manager'), $action_string);
				$this->add_error($this->feedback_message);
				return apply_filters('em_booking_set_status', false, $this);
			}
		}
		$this->previous_status = $this->booking_status;
		$this->booking_status = absint($status);
		$result = $wpdb->query($wpdb->prepare('UPDATE '.EM_BOOKINGS_TABLE.' SET booking_status=%d WHERE booking_id=%d', array($status, $this->booking_id)));
		if( $status_locked ) EM_Bookings::release_lock( $status_lock_event_id );
		if($result !== false){
			$this->flush_event_cache();
			$this->update_meta('previous_status', $this->previous_status);
			$this->feedback_message = sprintf(__('Booking %s.','events-manager'), $action_string);
			$result = apply_filters('em_booking_set_status', $result, $this); // run the filter before emails go out, in case others need to hook in first
			if( $result && $this->previous_status != $this->booking_status ){ //email if status has changed
				do_action('em_booking_status_changed', $this, array('status' => $status, 'email' => $email, 'ignore_spaces' => $ignore_spaces)); // method params passed as array
				if( $email ){
					$func_args = func_get_args();
					$email_args = !empty($func_args[3]) ? $func_args[3] : array();
					$email_args = array_merge( array('email_admin'=> true, 'force_resend' => false, 'email_attendee' => true), $email_args );
					if( $this->email( !empty($email_args['email_admin']), !empty($email_args['force_resend']), !empty($email_args['email_attendee'])) ){
					    if( $this->mails_sent > 0 ){
					        $this->feedback_message .= " ".__('Email Sent.','events-manager');
					    }
					}else{
						//extra errors may be logged by email() in EM_Object
						$this->feedback_message .= ' <span style="color:red">'.__('ERROR : Email Not Sent.','events-manager').'</span>';
						$this->add_error(__('ERROR : Email Not Sent.','events-manager'));
					}
				}
			}
		}else{
			//errors should be logged by save()
			$this->feedback_message = sprintf(__('Booking could not be %s.','events-manager'), $action_string);
			$this->add_error(sprintf(__('Booking could not be %s.','events-manager'), $action_string));
			$result =  apply_filters('em_booking_set_status', false, $this);
		}
		return $result;
	}
	
	public function can_cancel(){
		if( $this->get_option('dbem_bookings_user_cancellation') && !in_array($this->booking_status, array(2,3)) ){
			$cancellation_time = $this->get_option('dbem_bookings_user_cancellation_time');
			$can_cancel = $this->get_event()->start()->getTimestamp() > time(); // previously default was rsvp end
			if( is_numeric($cancellation_time) && $cancellation_time > 0 ){
				$EM_DateTime = $this->get_event()->start()->copy()->sub('PT'.$cancellation_time.'H');
				$can_cancel = time() < $EM_DateTime->getTimestamp();
			}elseif( static::is_dateinterval_string($cancellation_time) && $cancellation_time[0] !== '-' ){
				$EM_DateTime = $this->get_event()->start()->copy()->sub($cancellation_time);
				$can_cancel = time() < $EM_DateTime->getTimestamp();
			}
		}else{
			$can_cancel = false;
		}
		return apply_filters('em_booking_can_cancel', $can_cancel, $this);
	}
	
	/*
	 * Bookings that are made since
	 */
	public function can_uncancel() {
		$has_previous_status = isset( $this->booking_meta['previous_status'] ) || defined('EM_BOOKINGS_UNCANCEL_STATUS');
		$can_uncancel = $this->get_option('dbem_bookings_user_uncancellation') && $this->validate() && $has_previous_status;
		return apply_filters('em_booking_can_uncancel', $can_uncancel, $this);
	}
	
	public static function is_dateinterval_string( $string ){
		return preg_match('/^\-?P(([0-9]+[YMDW])+)?(T(([0-9]+[HMS])+))?$/', $string);
	}
	
	/**
	 * Returns true if booking is reserving a space at this event, whether confirmed or not 
	 */
	function is_reserved(){
	    $result = false;
	    if( $this->booking_status == 0 && $this->get_option('dbem_bookings_approval_reserved') ){
	        $result = true;
	    }elseif( $this->booking_status == 0 && !$this->get_option('dbem_bookings_approval') ){
	        $result = true;
	    }elseif( $this->booking_status == 1 ){
	        $result = true;
	    }
	    return apply_filters('em_booking_is_reserved', $result, $this);
	}
	
	/**
	 * Returns true if booking is associated with a non-registered user, i.e. booked as a guest 'no user mode'.
	 * @return mixed
	 */
	function is_no_user(){
		return apply_filters('em_booking_is_no_user', $this->get_person()->ID === 0, $this);
	}
	
	/**
	 * Returns true if booking is either pending but not confirmed (which is assumed pending).
	 * Pending bookings do not mean they are necessarily reserved spaces, check is_reserved() for that.
	 */
	function is_pending(){
		$result = ($this->is_reserved() || $this->booking_status == 0) && $this->booking_status != 1;
	    return apply_filters('em_booking_is_pending', $result, $this);
	}
	
	/**
	 * Returns true if booking is approved, i.e. confirmed. Takes into account that pending bookings may be auto-approved.
	 * @return bool
	 */
	function is_approved() {
		$result = $this->booking_status == 1 || ($this->booking_status == 0 && !$this->get_option('dbem_bookings_approval'));
		return apply_filters('em_booking_is_approved', $result, $this);
	}
	
	/**
	 * Set RSVP status to given number. Null sets booking to unconfirmed.
	 *
	 * @param null|int $status
	 * @param array $args
	 *
	 * @return bool
	 */
	function set_rsvp_status( $status, $args = array() ) {
		global $wpdb;
		// get status strings
		$action_string = static::get_rsvp_statuses( $status )->label;
		//if we're approving we can't approve a booking if spaces are full, so check before it's approved.
		$this->previous_rsvp_status = $this->booking_rsvp_status;
		$this->booking_rsvp_status = ( $status !== null && $status <= 2  && $status >= 0 ) ? absint($status) : null;
		if ( $this->booking_rsvp_status === null ) {
			$result = $wpdb->query($wpdb->prepare('UPDATE '.EM_BOOKINGS_TABLE.' SET booking_rsvp_status=NULL WHERE booking_id=%d', array($this->booking_id)));
		} else {
			$result = $wpdb->query($wpdb->prepare('UPDATE '.EM_BOOKINGS_TABLE.' SET booking_rsvp_status=%d WHERE booking_id=%d', array($this->booking_rsvp_status, $this->booking_id)));
		}
		if ( $result !== false ) {
			$this->feedback_message = esc_html__( sprintf(__("Booking RSVP status set to '%s'.",'events-manager'), $action_string) );
			$result = apply_filters('em_booking_set_rsvp_status', true, $this);
			if( $result && $this->previous_rsvp_status != $this->booking_rsvp_status ){ // act on booking status if there's a change in rsvp
				do_action('em_booking_rsvp_status_changed', $this, $status, $args); // method params passed as array
				if( $this->booking_rsvp_status === 0  && $this->get_option('dbem_bookings_rsvp_sync_cancel') ) {
					$this->cancel();
				} elseif ( $this->booking_rsvp_status === 1 && $this->get_option('dbem_bookings_rsvp_sync_confirm') ) {
					$this->set_status(1);
				} elseif( $this->previous_rsvp_status === 0 && $this->can_uncancel() ) {
					$this->uncancel();
				}
			}
			$this->feedback_message = static::get_rsvp_statuses($status)->confirmation;
		} else {
			//errors should be logged by save()
			$this->feedback_message = sprintf(__('Booking could not be %s.','events-manager'), $action_string);
			$this->add_error(sprintf(__('Booking could not be %s.','events-manager'), $action_string));
			$result =  apply_filters('em_booking_set_rsvp_status', false, $this, $args);
		}
		return $result;
	}
	
	/**
	 * Get RSVP Status equivalents
	 * @param $text
	 * @param $status
	 *
	 * @return int|string|null
	 */
	function get_rsvp_status( $text = false ) {
		if( $text ) {
			$status = static::get_rsvp_statuses( $this->booking_rsvp_status );
			return apply_filters('em_booking_get_rsvp_status_text', $status->label, $this, array('text' => $text, 'status' => $status));
		}
		return apply_filters('em_booking_get_rsvp_status', $this->booking_rsvp_status, $this);
	}
	
	/**
	 * Sets the RSVP status of a booking to 'Maybe' (status 2), not to be confused with the actual status of the booking.
	 * @param $args
	 *
	 * @return bool
	 */
	public function can_change_rsvp() {
		$can_change = false;
		$changeable_statuses = apply_filters( 'em_booking_statuses_rsvp_changeable', array(0,1,3), $this );
		if ( $this->get_option('dbem_bookings_rsvp_can_change') && in_array( $this->booking_status, $changeable_statuses) ) {
			if ( $this->booking_status == 3 && $this->can_uncancel()  ) {
				$can_change = true;
			} else {
				$can_change = true;
			}
		}
		return apply_filters( 'can_change_rsvp', $can_change, $this );
	}
	
	/**
	 * Returns true or false if user can RSVP a certain status, null if the current status is already the one requested.
	 * @param int|null $status
	 *
	 * @return mixed|null
	 */
	public function can_rsvp( $status ) {
		$result = false;
		if( $this->is_approved() ) {
			if( $this->get_option( 'dbem_bookings_rsvp' ) ) {
				// check if we're changing the RSVP or doing anew with a specific status
				if ( $this->booking_rsvp_status !== null && $this->can_change_rsvp() ) {
					$can_rsvp = true;
				} else {
					$rsvpable_booking_statuses = apply_filters( 'em_booking_rsvpable_booking_statuses', array( 0, 1 ) );
					if ( $this->booking_status === 3 && $this->get_option( 'dbem_bookings_rsvp_sync_cancel' ) && $this->can_uncancel() ) {
						$rsvpable_booking_statuses[] = 3;
					}
					$can_rsvp = in_array( $this->booking_status, $rsvpable_booking_statuses );
				}
				// general RSVP possible, now go deeper
				if ( $can_rsvp ) {
					if( $status !== null ) $status = absint( $status );
					if ( $status === null ) { // unconfirm
						$result = $this->can_manage(); // we cannot unconfirm unless an admin
					} elseif ( $status === 0 ) { // cancel
						if ( $this->get_option( 'dbem_bookings_rsvp_sync_cancel' ) && $this->booking_rsvp_status !== $status ) {
							$result = $this->can_cancel();
						} else {
							$result = true;
						}
					} elseif ( $status === 1 ) { // confirm
						$result = true;
					} elseif ( $status === 2 ) { // maybe
						if ( $this->get_option( 'dbem_bookings_rsvp_maybe' ) ) {
							$result = true;
						}
					}
					if( $result ){
						$result = $this->booking_rsvp_status === $status ? null : true;
					}
				}
			}
		}
		return apply_filters('em_booking_can_rsvp', $result, $this, $status );
	}
	
	public static function get_rsvp_statuses( $status = false ) {
		
		if( empty(static::$rsvp_statuses) ) {
			$statuses = array(
				null => array(
					'label' => __('Unconfirmed', 'events-manager'),
					'label_action' => __('Unconfirm', 'events-manager'),
					'action' => 'unconfirm',
					'confirmation' => __('Your booking is now unconfirmed', 'events-manager'),
				),
				0 => array(
					'label' => __('Not Attending', 'events-manager'),
					'label_action' => sprintf( __('RSVP - %s', 'events-manager'), __('No') ),
					'label_answer' => __('No'),
					'confirmation' => __('You have declined your attendance.', 'events-manager'),
					'action' => 'decline',
				),
				1 => array(
					'label' => __('Attending', 'events-manager'),
					'label_action' => sprintf( __('RSVP - %s', 'events-manager'), __('Yes') ),
					'label_answer' => __('Yes'),
					'action' => 'confirm',
					'confirmation' => __('You have confirmed your attendance.', 'events-manager'),
				),
			);
			
			if( em_get_option('dbem_bookings_rsvp_sync_cancel') ) {
				$statuses[0] = array_merge( $statuses[0], array(
					'confirmation' => __('You have declined your attendance, your booking is now cancelled.', 'events-manager'),
				));
			}
			if( em_get_option('dbem_bookings_rsvp_maybe') ) {
				$statuses[2] = array(
					'label' => __('Maybe Attending', 'events-manager'),
					'label_action' => sprintf( __('RSVP - %s', 'events-manager'), __('Maybe', 'events-manager') ),
					'label_answer' => __('Maybe', 'events-manager'),
					'action' => 'maybe',
					'confirmation' => __('You have not definitively confrimed your attendance.', 'events-manager'),
				);
			}
			
			$statuses = apply_filters( 'em_booking_get_rsvp_statuses', $statuses );
			foreach( $statuses as $k => $s ) $statuses[$k] = (object) $s;
			static::$rsvp_statuses = $statuses;
		}
		
		if ( $status !== false ) {
			return !empty(static::$rsvp_statuses[$status]) ? static::$rsvp_statuses[$status] : static::$rsvp_statuses[null];
		}
		return static::$rsvp_statuses;
	}
	
	/**
	 * Add a booking note to this booking. returns wpdb result or false if use can't manage this event.
	 * @param string $note
	 * @return mixed
	 */
	function add_note( $note_text ){
		global $wpdb;
		if( $this->can_manage() ){
			$this->get_notes();
			$note = array('author'=>get_current_user_id(),'note'=>wp_kses_data($note_text),'timestamp'=>time());
			$this->notes[] = $note;
			$this->feedback_message = __('Booking note successfully added.','events-manager');
			return $wpdb->insert(EM_META_TABLE, array('object_id'=>$this->booking_id, 'meta_key'=>'booking-note', 'meta_value'=> serialize($note)),array('%d','%s','%s'));
		}
		return false;
	}

	function get_admin_url(){
		if( $this->get_option('dbem_edit_bookings_page') && (!is_admin() || !empty($_REQUEST['is_public'])) ){
			$my_bookings_page = get_permalink( $this->get_option('dbem_edit_bookings_page'));
			$bookings_link = em_add_get_params($my_bookings_page, [ 'event_id'=> $this->get_event_uid(), 'booking_id'=>$this->booking_id ], false);
		}else{
			$archetype = $this->get_event()->event_archetype;
			if( $this->get_event()->blog_id != get_current_blog_id() ){
				$bookings_link = get_admin_url($this->get_event()->blog_id, 'edit.php?post_type='.$archetype."&page=events-manager-bookings&event_id=".$this->get_event_uid()."&booking_id=".$this->booking_id);
			}else{
				$bookings_link = em_admin_url( $archetype ). "&page=events-manager-bookings&event_id=".$this->get_event_uid()."&booking_id=".$this->booking_id;
			}
		}
		return apply_filters('em_booking_get_bookings_url', $bookings_link, $this);
	}
	
	function output($format, $target="html") {
		do_action('em_booking_output_pre', $this, $format, $target);
		$output_string = $format;
		for ($i = 0 ; $i < EM_CONDITIONAL_RECURSIONS; $i++){
			preg_match_all('/\{([a-zA-Z0-9_\-,]+)\}(.+?)\{\/\1\}/s', $output_string, $conditionals);
			if( count($conditionals[0]) > 0 ){
				//Check if the language we want exists, if not we take the first language there
				foreach ($conditionals[1] as $key => $condition) {
					$show_condition = apply_filters('em_booking_output_show_condition', false, array('format' => $format, 'target' => $target, 'condition' => $condition, 'conditionals' => $conditionals, 'key' => $key), $this );
					if ($condition == 'has_rsvp_reply') { //check if there's an rsvp
						$show_condition = $this->booking_rsvp_status !== null;
					} elseif ( $condition == 'no_rsvp_reply' ) { //check if there's no rsvp
						$show_condition = $this->booking_rsvp_status === null;
					} elseif ( $condition == 'is_rsvp_reply_no' ) { //check if there's no rsvp
						$show_condition = $this->booking_rsvp_status === 0;
					} elseif ( $condition == 'is_rsvp_reply_yes' ) { //check if there's no rsvp
						$show_condition = $this->booking_rsvp_status === 1;
					} elseif ( $condition == 'is_rsvp_reply_maybe' ) { //check if there's no rsvp
						$show_condition = $this->booking_rsvp_status === 2;
					} elseif ( preg_match('/^is_rsvp_reply_([0-9]+)$/', $condition, $matches ) ) { //check if there's no rsvp
						$show_condition = $this->booking_rsvp_status == $matches[1];
					}
					if( $show_condition ){
						//calculate lengths to delete placeholders
						$placeholder_length = strlen($condition)+2;
						$replacement = substr($conditionals[0][$key], $placeholder_length, strlen($conditionals[0][$key])-($placeholder_length *2 +1));
						$output_string = str_replace($conditionals[0][$key], apply_filters('em_booking_output_condition', $replacement, $condition, $conditionals[0][$key], $this), $output_string);
					}
				}
			}
		}
		preg_match_all("/(#@?_?[A-Za-z0-9_]+)({([^}]+)})?/", $output_string, $placeholders);
		foreach( $this->get_tickets() as $EM_Ticket){ /* @var $EM_Ticket EM_Ticket */ break; } //Get first ticket for single ticket placeholders
		$replaces = array();
		foreach($placeholders[1] as $key => $result) {
			$replace = '';
			$full_result = $placeholders[0][$key];
			$placeholder_atts = array($result);
			if( !empty($placeholders[3][$key]) ) $placeholder_atts[] = $placeholders[3][$key];
			switch( $result ){
				case '#_BOOKINGID':
					$replace = $this->booking_id;
					break;
				case '#_BOOKING_UUID':
					$replace = $this->booking_uuid;
					break;
				case '#_RESPNAME' : //deprecated
				case '#_BOOKINGNAME':
					$replace = $this->get_person()->get_name();
					break;
				case '#_RESPEMAIL' : //deprecated
				case '#_BOOKINGEMAIL':
					$replace = $this->get_person()->user_email;
					break;
				case '#_RESPPHONE' : //deprecated
				case '#_BOOKINGPHONE':
					$replace = $this->get_person()->phone;
					break;
				case '#_BOOKINGSPACES':
					$replace = $this->get_spaces();
					break;
				case '#_BOOKINGDATE':
					$replace = ( $this->date() !== false ) ? $this->date()->i18n( em_get_date_format() ):'n/a';
					break;
				case '#_BOOKINGTIME':
					$replace = ( $this->date() !== false ) ?  $this->date()->i18n( em_get_hour_format() ):'n/a';
					break;
				case '#_BOOKINGDATETIME':
					$replace = ( $this->date() !== false ) ? $this->date()->i18n( em_get_date_format().' '.em_get_hour_format()):'n/a';
					break;
				case '#_BOOKINGLISTURL':
					$replace = em_get_my_bookings_url();
					break;
				case '#_COMMENT' : //deprecated
				case '#_BOOKINGCOMMENT':
					$replace = $this->booking_comment;
					break;
				case '#_BOOKINGPRICEWITHOUTTAX':
					$replace = $this->format_price($this->get_price() - $this->get_price_taxes());
					break;
				case '#_BOOKINGPRICETAX':
					$replace = $this->get_price_taxes(true);
					break;
				case '#_BOOKINGPRICEWITHTAX':
				case '#_BOOKINGPRICE':
					$replace = $this->get_price(true);
					break;
				case '#_BOOKINGTICKETNAME':
					$replace = $EM_Ticket->name;
					break;
				case '#_BOOKINGTICKETDESCRIPTION':
					$replace = $EM_Ticket->description;
					break;
				case '#_BOOKINGTICKETPRICEWITHTAX':
					$replace = $this->format_price( $EM_Ticket->get_price_without_tax() * (1+$this->get_tax_rate()/100) );
					break;
				case '#_BOOKINGTICKETPRICEWITHOUTTAX':
					$replace = $EM_Ticket->get_price_without_tax(true);
					break;
				case '#_BOOKINGTICKETTAX':
					$replace = $this->format_price( $EM_Ticket->get_price_without_tax() * ($this->get_tax_rate()/100) );
					break;
				case '#_BOOKINGTICKETPRICE':
					$replace = $EM_Ticket->get_price(true);
					break;
				case '#_BOOKINGTICKETS':
					ob_start();
					em_locate_template('emails/bookingtickets.php', true, array('EM_Booking'=>$this));
					$replace = ob_get_clean();
					break;
				case '#_BOOKINGSUMMARY':
					ob_start();
					em_locate_template('emails/bookingsummary.php', true, array('EM_Booking'=>$this));
					$replace = ob_get_clean();
					break;
				case '#_BOOKINGADMINURL':
				case '#_BOOKINGADMINLINK':
					$bookings_link = esc_url( add_query_arg('booking_id', $this->booking_id, $this->get_event()->get_bookings_url()) );
					if($result == '#_BOOKINGADMINLINK'){
						$replace = '<a href="'.$bookings_link.'">'.esc_html__('Edit Booking', 'events-manager'). '</a>';
					}else{
						$replace = $bookings_link;
					}
					break;
				case '#_BOOKINGSTATUS':
				case '#_BOOKING_STATUS':
					$replace = $this->get_status();
					break;
				case '#_BOOKINGRSVPSTATUS':
				case '#_BOOKING_RSVP_STATUS':
					$replace = $this->get_rsvp_status( true );
					break;
				default:
					$replace = $this->output_placeholder( $full_result, $placeholder_atts, $format, $target );
					break;
			}
			$replaces[$full_result] = apply_filters('em_booking_output_placeholder', $replace, $this, $full_result, $target, $placeholder_atts);
		}
		//sort out replacements so that during replacements shorter placeholders don't overwrite longer varieties.
		krsort($replaces);
		foreach($replaces as $full_result => $replacement){
			$output_string = str_replace($full_result, $replacement , $output_string );
		}
		//run event output too, since this is never run from within events and will not infinitely loop
		$EM_Event = apply_filters('em_booking_output_event', $this->get_event(), $this); //allows us to override the booking event info if it belongs to a parent or translation
		$output_string = $EM_Event->output($output_string, $target);
		return apply_filters('em_booking_output', $output_string, $this, $format, $target);	
	}
	
	/**
	 * Function mainly aimed for overriding by extending classes, avoiding the need to use a filter instead.
	 * @param string $full_result
	 * @param array $placeholder_atts
	 * @param string $format
	 * @param string $target
	 * @return string
	 */
	public function output_placeholder( $full_result, $placeholder_atts, $format, $target ){
		// $placeholder = $placeholder_atts[0]; // this is the placeholder, no atts
		return $full_result;
	}
	
	public function output_intent_html(){
		$input = '<input type="hidden" name="booking_intent" value="' . esc_attr($this->booking_uuid) .'" class="em-booking-intent" id="em-booking-intent-'. esc_attr( $this->get_event_uid() ) .'"';
		foreach( $this->get_intent_data() as $key => $value ){
			$input .= ' data-'.$key.'="'. esc_attr($value) .'"';
		}
		$input .= '>';
		return apply_filters('em_booking_output_intent_html', $input, $this);
	}
	
	public function get_intent_data(){
		return array(
			'uuid' => $this->booking_uuid,
			'event_id' => $this->get_event_uid(),
			'spaces' => $this->get_spaces(),
			'amount' => $this->get_price(),
			'amount_formatted' => $this->get_price( true ),
			'amount_base' => $this->get_price_base(),
			'taxes' => $this->get_price_taxes(),
			'currency' => $this->get_currency(),
		);
	}
	
	/**
	 * @param boolean $email_admin
	 * @param boolean $force_resend
	 * @param boolean $email_attendee
	 * @return boolean
	 */
	function email( $email_admin = true, $force_resend = false, $email_attendee = true ){
		$result = true;
		$this->mails_sent = 0;
		//Make sure event matches booking, and that booking used to be approved.
		if( $this->booking_status !== $this->previous_status || $force_resend ){
			// before we format dates or any other language-specific placeholders, make sure we're translating the site language, not the user profile language in the admin area (e.g. if an admin is sending a booking confirmation email), assuming this isn't a ML-enabled site.
			if( !EM_ML::$is_ml && is_admin() && EM_ML::$wplang != get_user_locale() ) EM_ML::switch_locale(EM_ML::$wplang);
			do_action('em_booking_email_before_send', $this);
			//get event info and refresh all bookings
			$EM_Event = $this->get_event(); //We NEED event details here.
			$EM_Event->get_bookings(true); //refresh all bookings
			//messages can be overridden just before being sent
			$msg = $this->email_messages();
			$filter_args = array('email_admin'=> true, 'force_resend' => $force_resend, 'email_attendee' => $email_attendee, 'msg' => $msg );

			//Send user (booker) emails
			if( !empty($msg['user']['subject']) && $email_attendee ){
				$result = $this->email_attendee( $msg, $filter_args );
			}
			
			//Send admin/contact emails if this isn't the event owner or an events admin
			if( $email_admin && !empty($msg['admin']['subject']) ){ //emails won't be sent if admin is logged in unless they book themselves
				$result = $this->email_admins( $msg );
			}
			do_action('em_booking_email_after_send', $this);
			if( !EM_ML::$is_ml && is_admin() ) EM_ML::restore_locale(); // restore the locale back for the rest of the site, which will happen if we switched it earlier
		}
		return apply_filters('em_booking_email', $result, $this, $email_admin, $force_resend, $email_attendee);
		//TODO need error checking for booking mail send
	}
	
	function email_attendee( $msg, $filter_args = null ){
		$result = true;
		if( !$filter_args ){
			$filter_args = array('email_admin'=> true, 'force_resend' => true, 'email_attendee' => false, 'msg' => $msg );
		}
		$msg['user']['subject'] = $this->output($msg['user']['subject'], 'raw');
		$msg['user']['body'] = $this->output($msg['user']['body'], 'email');
		$attachments = array();
		if( !empty($msg['user']['attachments']) && is_array($msg['user']['attachments']) ){
			$attachments = $msg['user']['attachments'];
		}
		//add extra args
		$args = array();
		if( $this->get_option('dbem_bookings_replyto_owner') && $this->get_event()->get_contact()->user_email ){
			$args['reply-to'] = $this->get_event()->get_contact()->user_email;
			$args['reply-to-name'] = $this->get_event()->get_contact()->display_name;
		}
		$args = apply_filters('em_booking_email_user_args', $args, $filter_args, $this);
		//Send to the person booking
		if( !$this->email_send( $msg['user']['subject'], $msg['user']['body'], $this->get_person()->user_email, $attachments, $args) ){
			$result = false;
		}else{
			$this->mails_sent++;
		}
		return $result;
	}
	
	function email_admins( $msg, $filter_args = null ){
		$result = true;
		$EM_Event = $this->get_event(); //We NEED event details here.
		if( !$filter_args ){
			$filter_args = array('email_admin'=> true, 'force_resend' => true, 'email_attendee' => false, 'msg' => $msg );
		}
		//get admin emails that need to be notified, hook here to add extra admin emails
		$admin_emails = str_replace(' ','',$this->get_option('dbem_bookings_notify_admin'));
		$admin_emails = apply_filters('em_booking_admin_emails', explode(',', $admin_emails), $this); //supply emails as array
		if( $this->get_option('dbem_bookings_contact_email') == 1 && !empty($EM_Event->get_contact()->user_email) ){
			//add event owner contact email to list of admin emails
			$admin_emails[] = $EM_Event->get_contact()->user_email;
		}
		foreach($admin_emails as $key => $email){ if( !is_email($email) ) unset($admin_emails[$key]); } //remove bad emails
		//add extra args
		$args = array();
		if( $this->get_option('dbem_bookings_replyto_owner_admins') && $this->get_event()->get_contact()->user_email ){
			$args['reply-to'] = $this->get_event()->get_contact()->user_email;
			$args['reply-to-name'] = $this->get_event()->get_contact()->display_name;
		}
		$args = apply_filters('em_booking_email_admin_args', $args, $filter_args, $this);
		//proceed to email admins if need be
		if( !empty($admin_emails) ){
			//Only gets sent if this is a pending booking, unless approvals are disabled.
			$msg['admin']['subject'] = $this->output($msg['admin']['subject'],'raw');
			$msg['admin']['body'] = $this->output($msg['admin']['body'], 'email');
			$attachments = array();
			if( !empty($msg['admin']['attachments']) && is_array($msg['admin']['attachments']) ){
				$attachments = $msg['admin']['attachments'];
			}
			//email admins
			if( !$this->email_send( $msg['admin']['subject'], $msg['admin']['body'], $admin_emails, $attachments, $args) && current_user_can('manage_options') ){
				$this->errors[] = __('Confirmation email could not be sent to admin. Registrant should have gotten their email (only admin see this warning).','events-manager');
				$result = false;
			}else{
				$this->mails_sent++;
			}
		}
		return $result;
	}
	
	function email_messages(){
		$msg = array( 'user'=> array('subject'=>'', 'body'=>'', 'attachments' => array()), 'admin'=> array('subject'=>'', 'body'=>'', 'attachments' => array())); //blank msg template
		//admin messages won't change whether pending or already approved
	    switch( $this->booking_status ){
	    	case 0:
	    	case 5: //TODO remove offline status from here and move to pro
	    		$msg['user']['subject'] = $this->get_option('dbem_bookings_email_pending_subject');
	    		$msg['user']['body'] = $this->get_option('dbem_bookings_email_pending_body');
	    		//admins should get something (if set to)
	    		$msg['admin']['subject'] = $this->get_option('dbem_bookings_contact_email_pending_subject');
	    		$msg['admin']['body'] = $this->get_option('dbem_bookings_contact_email_pending_body');
	    		break;
	    	case 1:
	    		$msg['user']['subject'] = $this->get_option('dbem_bookings_email_confirmed_subject');
	    		$msg['user']['body'] = $this->get_option('dbem_bookings_email_confirmed_body');
	    		//admins should get something (if set to)
	    		$msg['admin']['subject'] = $this->get_option('dbem_bookings_contact_email_confirmed_subject');
	    		$msg['admin']['body'] = $this->get_option('dbem_bookings_contact_email_confirmed_body');
	    		break;
	    	case 2:
	    		$msg['user']['subject'] = $this->get_option('dbem_bookings_email_rejected_subject');
	    		$msg['user']['body'] = $this->get_option('dbem_bookings_email_rejected_body');
	    		//admins should get something (if set to)
	    		$msg['admin']['subject'] = $this->get_option('dbem_bookings_contact_email_rejected_subject');
	    		$msg['admin']['body'] = $this->get_option('dbem_bookings_contact_email_rejected_body');
	    		break;
	    	case 3:
	    		$msg['user']['subject'] = $this->get_option('dbem_bookings_email_cancelled_subject');
	    		$msg['user']['body'] = $this->get_option('dbem_bookings_email_cancelled_body');
	    		//admins should get something (if set to)
	    		$msg['admin']['subject'] = $this->get_option('dbem_bookings_contact_email_cancelled_subject');
	    		$msg['admin']['body'] = $this->get_option('dbem_bookings_contact_email_cancelled_body');
	    		break;
	    }
	    return apply_filters('em_booking_email_messages', $msg, $this);
	}
	
	/**
	 * Returns an EM_DateTime representation of when booking was made in UTC timezone. If no valid date defined, false will be returned
	 * @param boolean $utc_timezone
	 * @return EM_DateTime
	 * @throws Exception
	 */
	public function date( $utc_timezone = false ){
		if( empty($this->date) || !$this->date->valid ){
			// a zero MySQL datetime passes empty() and parses to year -0001 rather than throwing, so it has to be rejected by hand
			if( !empty($this->booking_date) && substr($this->booking_date, 0, 4) !== '0000' ){
			    $this->date = new EM_DateTime($this->booking_date, 'UTC');
			}else{
				//we retrn a date regardless but it's not based on a 'valid' booking date
				$this->date = new EM_DateTime();
				$this->date->valid = false;
			}
		}
		//Set to UTC timezone if requested, local blog time by default
		if( $utc_timezone ){
			$timezone = 'UTC';
		}else{
			//we could set this to false but this way we might avoid creating a new timezone if it's already in this one
			$timezone = $this->get_option( 'timezone_string' );
			if( !$timezone ) $timezone = $this->get_option('gmt_offset');
		}
		$this->date->setTimezone($timezone);
		return $this->date;
	}
	
	/**
	 * Can the user manage this event? 
	 */
	function can_manage( $owner_capability = false, $admin_capability = false, $user_to_check = false ){
		return $this->get_event()->can_manage('manage_bookings','manage_others_bookings') || empty($this->booking_id) || !empty($this->manage_override);
	}
	
	/**
	 * Returns this object in the form of an array
	 * @return array
	 */
	function to_array($person = false){
		$booking = array();
		//Core Data
		$booking = parent::to_array();
		//Person Data
		if($person && is_object($this->person)){
			$person = $this->person->to_array();
			$booking = array_merge($booking, $person);
		}
		return $booking;
	}
	
	function to_api( $args = array('event' => true), $version = 'v1' ){
		$booking = array (
			'id' => $this->booking_id,
			'event_id' => $this->get_event_uid(),
			'uuid' => $this->booking_uuid,
			'person_id' => $this->person_id,
			'status' => $this->booking_status,
			'spaces' => $this->booking_spaces,
			'price' => $this->get_price(),
			'tax_rate' => $this->get_tax_rate(true), // returned as decimal/percen
			'taxes' => $this->booking_taxes,
			'comment' => $this->booking_comment,
			'meta' => $this->booking_meta,
			'tickets' => array(),
			'datetime' => $this->booking_date,
		);
		// add tickets
		foreach ( $this->get_tickets_bookings() as $EM_Ticket_Bookings ){
			$booking['tickets'][$EM_Ticket_Bookings->ticket_id] = array(
				'name' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
				'description' => $EM_Ticket_Bookings->get_ticket()->ticket_name,
				'spaces' => $EM_Ticket_Bookings->get_spaces(),
				'price' => $EM_Ticket_Bookings->get_price(),
				'attendees' => array(),
			);
			foreach ( $EM_Ticket_Bookings as $EM_Ticket_Booking ){
				$booking['tickets'][$EM_Ticket_Bookings->ticket_id]['attendees'][] = array(
					'uuid' => $EM_Ticket_Booking->ticket_uuid,
					'price' => $EM_Ticket_Booking->ticket_booking_price,
					'meta' => $EM_Ticket_Booking->meta,
				);
			}
		}
		// if event data should be sent
		if( !empty($args['event']) ) {
			$booking['event'] = $this->get_event()->to_api();
		}
		// user — a person_id of 0 is EM's guest-person model (no WP user account), so report it honestly rather than always claiming a registered user.
		$booking['person'] = array(
			'guest' => empty( $this->person_id ),
			'email' => $this->get_person()->user_email,
			'name' => $this->get_person()->get_name(),
		);
		if( $this->get_person()->phone ){
			$booking['person']['phone'] = $this->get_person()->phone;
		}
		return apply_filters('em_booking_to_api', $booking, array(), $this);
	}
}
?>