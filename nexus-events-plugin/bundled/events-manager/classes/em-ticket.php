<?php
/**
 * @property string $id
 * @property boolean $status
 * @property string|null $name
 * @property string|null $description
 * @property float|null $price
 * @property string|null $start @deprecated { @see EM_Ticket::start() }
 * @property string|null $end @deprecated { @see EM_Ticket::end() }
 * @property int|null $min
 * @property int|null $max
 * @property int|null $spaces
 * @property int|null $members
 * @property array|null $members_roles
 * @property int|null $guests
 * @property int|null $required
 * @property int|null $parent
 * @property string|null $meta
 * @property int|null $order
 *
 * @property EM_Event $event
 */
class EM_Ticket extends EM_Object {

	//DB Fields
	public $ticket_id;
	public $event_id;
	public $ticket_status;
	protected $ticket_name;
	protected $ticket_description;
	public $ticket_price;
	protected $ticket_start;
	protected $ticket_end;
	public $ticket_min;
	public $ticket_max;
	public $ticket_spaces = 10;
	public $ticket_members = false;
	public $ticket_members_roles = [];
	public $ticket_guests = false;
	public $ticket_required = false;
	public $ticket_meta = [];
	public $ticket_order;
	/** @var int|null ID of the parent recurring ticket, if this is an override */
	public $ticket_parent = null;
	/** @var int|null NULL = not multi-event, 0 = unlimited, >0 = N-limited */
	public $multi_event = null;
	/** @var int|null Whether booking auto-enrolls into all eligible events (1) or not (0), relevant only if $ticket_multi_event is set to 0 */
	public $multi_event_auto_enrol = null;
	/** @var int|null If multi_event is enabled, then a ticket ID is required, which is what the user will gain access to book */
	public $multi_event_ticket = null;

	public $fields = array(
		'ticket_id' => array('name'=>'id','type'=>'%d'),
		'event_id' => array('name'=>'event_id','type'=>'%d'),
		'ticket_name' => array('name'=>'name','type'=>'%s'),
		'ticket_status' => array('name'=>'status','type'=>'%d','null'=>1),
		'ticket_description' => array('name'=>'description','type'=>'%s','null'=>1),
		'ticket_price' => array('name'=>'price','type'=>'%f','null'=>1),
		'ticket_start' => array('type'=>'%s','null'=>1),
		'ticket_end' => array('type'=>'%s','null'=>1),
		'ticket_min' => array('name'=>'min','type'=>'%d','null'=>1),
		'ticket_max' => array('name'=>'max','type'=>'%d','null'=>1),
		'ticket_spaces' => array('name'=>'spaces','type'=>'%d','null'=>1),
		'ticket_members' => array('name'=>'members','type'=>'%d','null'=>1),
		'ticket_members_roles' => array('name'=>'ticket_members_roles','type'=>'%s','null'=>1),
		'ticket_guests' => array('name'=>'guests','type'=>'%d','null'=>1),
		'ticket_required' => array('name'=>'required','type'=>'%d','null'=>1),
		'ticket_parent' => array('type'=>'%d','null'=>1),
		'ticket_meta' => array('name'=>'ticket_meta','type'=>'%s','null'=>1),
		'ticket_order' => array('type'=>'%d','null'=>1),
		'multi_event' => array('type'=>'%d','null'=>1),
		'multi_event_auto_enrol' => array('type'=>'%d','null'=>1),
		'multi_event_ticket' => array('type'=>'%d','null'=>1),
	);
	// array map of $fields mapping name to key
	public static $field_shortcuts = array(
		'id' => 'ticket_id',
		'status' => 'ticket_status',
		'name' => 'ticket_name',
		'description' => 'ticket_description',
		'price' => 'ticket_price',
		'start' => 'ticket_start',
		'end' => 'ticket_end',
		'min' => 'ticket_min',
		'max' => 'ticket_max',
		'spaces' => 'ticket_spaces',
		'members' => 'ticket_members',
		'members_roles' => 'ticket_members_roles',
		'guests' => 'ticket_guests',
		'required' => 'ticket_required',
		'parent' => 'ticket_parent',
		'meta' => 'ticket_meta',
		'order' => 'ticket_order',
	);
	//Other Vars
	/**
	 * Contains only bookings belonging to this ticket.
	 * @var EM_Booking
	 */
	public $bookings = [];
	public $required_fields = array('ticket_name');
	protected $start;
	protected $end;
	/**
	 * is this ticket limited by spaces allotted to this ticket? false if no limit (i.e. the events general limit of seats)
	 * @var bool
	 */
	public $spaces_limit = true;

	/**
	 * An associative array containing event IDs as the keys and pending spaces as values.
	 * This is in array form for future-proofing since at one point tickets could be used for multiple events.
	 * @var array
	 */
	protected $pending_spaces = [];
	protected $booked_spaces = [];
	protected $bookings_count = [];
	protected $reserved_spaces = [];
	protected $status_counts = [];

	/**
	 * @var EM_Event
	 */
	protected $event;
	/**
	 * @var bool flag whether ticket is available, saved for persistence
	 */
	protected $is_available;
	/**
	 * @var EM_Ticket reference to the parent ticket object
	 */
	protected $parent_ticket;
	/**
	 * Temporary UUID used during posting ticket data, for referral before saving a ticket for the first time
	 * @var string
	 */
	public $ticket_uuid;
	/**
	 * Flag for detecting if a ticket is adhering to EM v7+ nuances, such as overriding ticket architecture in recurrences, signaling a retroactive backport can be made
	 * @var bool
	 */
	public $v7 = true;

	/**
	 * Creates ticket object and retreives ticket data (default is a blank ticket object). Accepts either array of ticket data (from db) or a ticket id.
	 * @param mixed $ticket_data
	 */
	function __construct( $ticket_data = false ){
		$this->ticket_name = __('Standard Ticket','events-manager');
		$ticket = [];
		if( $ticket_data !== false ){
			//Load ticket data
			if( is_array($ticket_data) ){
				$ticket = $ticket_data;
			}elseif( is_numeric($ticket_data) ){
				//Retreiving from the database
				global $wpdb;
				$sql = "SELECT * FROM ". EM_TICKETS_TABLE ." WHERE ticket_id ='$ticket_data'";
			  	$ticket = $wpdb->get_row($sql, ARRAY_A);
			}
			//Save into the object
			$this->to_object($ticket);
			// set value types of things that might get compared
			$this->ticket_id = $this->ticket_id !== null ? absint($this->ticket_id) : null;
			$this->ticket_parent = $this->ticket_parent !== null ? absint($this->ticket_parent) : null;
			$this->ticket_order = $this->ticket_order !== null ? absint($this->ticket_order) : null;
			$this->ticket_spaces = $this->ticket_spaces !== null ? absint($this->ticket_spaces) : null;
			$this->ticket_price = $this->ticket_price !== null ? (float) $this->ticket_price : null;
			if ( $this->ticket_parent === null && $this->ticket_price === null ) $this->ticket_price = 0;
			$this->ticket_status = $this->ticket_status !== null ? ( $this->ticket_status ? 1:0 ): null;
			// ticket status is by default enabled unless there is a parent, in which case we inherit
			if ( !$this->ticket_parent && $this->ticket_status === null ) {
				$this->ticket_status = true;
			}
			//serialized arrays
			$this->ticket_meta = ( !empty( $ticket['ticket_meta'] ) ) ? EM_Object::maybe_unserialize($ticket['ticket_meta']) : [];
			$this->ticket_members_roles = EM_Object::maybe_unserialize($this->ticket_members_roles);
			if( !is_array($this->ticket_members_roles) ) $this->ticket_members_roles = [];
			//sort out recurrence meta to save extra empty() checks, the 'true' cut-off info is here for the ticket if part of a recurring event
			if( !empty($this->ticket_meta['recurrences']) ){
				if( !array_key_exists('start_days', $this->ticket_meta['recurrences']) ) $this->ticket_meta['recurrences']['start_days'] = false;
				if( !array_key_exists('end_days', $this->ticket_meta['recurrences']) ) $this->ticket_meta['recurrences']['end_days'] = false;
				if( !array_key_exists('start_time', $this->ticket_meta['recurrences']) ) $this->ticket_meta['recurrences']['start_time'] = false;
				if( !array_key_exists('end_time', $this->ticket_meta['recurrences']) ) $this->ticket_meta['recurrences']['end_time'] = false;
				//if we have start and end times, we'll set the ticket start/end properties
				if( !empty($this->ticket_meta['recurrences']['start_time']) ){
					$this->ticket_start = date('Y-m-d ') . $this->ticket_meta['recurrences']['start_time'];
				}
				if( !empty($this->ticket_meta['recurrences']['end_time']) ){
					$this->ticket_end = date('Y-m-d ') . $this->ticket_meta['recurrences']['end_time'];
				}
				$this->v7 = !empty($this->ticket_meta['recurrences']['v7']);
			}
		} else {
			$this->ticket_price = 0;
			$this->ticket_spaces = 10;
		}
		do_action('em_ticket',$this, $ticket_data, $ticket);
	}

	/**
	 * @var EM_Ticket[] Array of 'cached' EM_Ticket objects, by ID
	 */
	protected static $instances = [];

	/**
	 * Cache-friendly method to instantiate a new ticket, rather than looking up the DB each time
	 * @param array|int|object $ticket   Array or object containing ticket_id or the ticket ID itself
	 *
	 * @return EM_Ticket
	 */
	public static function get( $ticket = false ) {
		if ( is_object( $ticket ) && isset( $ticket->ticket_id ) ) {
			$ticket_id = absint( $ticket->ticket_id );
		} elseif ( is_array( $ticket ) && isset( $ticket['ticket_id'] ) ) {
			$ticket_id = absint( $ticket['ticket_id'] );
		} else {
			$ticket_id = absint( $ticket );
		}

		if ( $ticket_id > 0 ) {
			if ( isset( static::$instances[ $ticket_id ] ) ) {
				return static::$instances[ $ticket_id ];
			}

			$cached_ticket = wp_cache_get( $ticket_id, 'em_tickets' );
			if ( $cached_ticket instanceof EM_Ticket ) {
				static::$instances[ $ticket_id ] = $cached_ticket;
				return $cached_ticket;
			}
		}

		$EM_Ticket = new EM_Ticket( $ticket );
		if ( ! empty( $EM_Ticket->ticket_id ) ) {
			static::$instances[ $EM_Ticket->ticket_id ] = $EM_Ticket;
			wp_cache_set( $EM_Ticket->ticket_id, $EM_Ticket, 'em_tickets' );
		}

		return $EM_Ticket;
	}


	function __get( $prop ){
		if( $prop == 'name' || $prop == 'ticket_name' || $prop == 'description' || $prop == 'ticket_description' ){
			// check for translations
			$property = $prop == 'name' || $prop == 'description' ? 'ticket_' . $prop : $prop;
			if( EM_ML::$is_ml && !$this->ticket_parent && !empty($this->ticket_meta['langs'][EM_ML::$current_language][$property]) ){
				return $this->ticket_meta['langs'][EM_ML::$current_language][$property];
			}else{
				// let the if statement further down handle parent ticket if we're not accessing a direct property, otherwise default to parent method
				if ( $prop == 'ticket_name' || $prop == 'ticket_description' ) {
					return $this->{$prop};
				}
				$prop = str_replace('ticket_', '', $prop);
			}
		}elseif( $prop == 'event' ){
			return $this->get_event();
		}elseif( $prop == 'ticket_start' || $prop == 'ticket_end' ){
	    	return $this->{$prop};
	    }elseif( $prop == 'start' || $prop == 'end' ){
			// use start() and end() instead, these are depregated getters and setters
	    	if( !$this->{$prop}()->valid ) return 0;
	    	return $this->{$prop}()->getTimestampWithOffset();
		} elseif( $prop == 'meta' ){
			return $this->ticket_meta;
		}
		// get parent ticket if one exists and shortcut value is null
		if ( !empty( static::$field_shortcuts[ $prop ] ) && !empty( $this->ticket_parent ) ) {
			$property = static::$field_shortcuts[ $prop ];
			if ( $this->{$property} === null || ( $prop === 'members_roles' && $this->{$property} === [] ) ) {
				// we still check $prop shortcut because we may recursively check upwards to grandparents
				return $this->get_parent()->{$prop};
			}
		}
		// return default value otherwise
	    return parent::__get( $prop );
	}

	public function __set( $prop, $val ) {
		if ( in_array( $prop, [ 'name', 'ticket_name' ] ) ) {
			$this->ticket_name = $val;
		} elseif ( in_array( $prop, [ 'description', 'ticket_description' ] ) ) {
			$this->ticket_description = $val;
		} elseif ( $prop === 'event' && $val instanceof EM_Event ) {
			$this->event = $val;
			$this->event_id = $this->event->event_id;
		} elseif ( in_array( $prop, [ 'ticket_start', 'start' ] ) ) {
			$this->ticket_start = $val;
			$this->start = false;
		} elseif ( in_array( $prop, [ 'ticket_end', 'end' ] ) ) {
			$this->ticket_end = $val;
			$this->end = false;
		} elseif( $prop == 'meta' ){
			if ( is_array( $val ) ) {
				$this->ticket_meta->data = $val;
			}
		} elseif ( $prop === 'is_available' && $val === null ) {
			// reset available value so it forces a refresh
			$this->is_available = null;
		} else {
			parent::__set( $prop, $val );
		}
	}

	public function __isset( $prop ){
		if( $prop == 'ticket_start' || $prop == 'start' ){
			return !empty($this->ticket_start);
		}elseif( $prop == 'ticket_end' || $prop == 'end' ){
			return !empty($this->ticket_end);
		} elseif ( $prop === 'meta' ) {
			return $this->ticket_meta !== null;
		}
		if( $prop == 'name' || $prop == 'ticket_name' || $prop == 'ticket_description'  || $prop == 'event' ){
			$property = $prop == 'name' ? 'ticket_'.$prop : $prop;
			return !empty($this->{$property});
		}
		if( $this->ticket_parent && !empty(static::$field_shortcuts[ $prop ]) ){
			$val = $this->{$prop};
			return $val !== null;
		}
		return parent::__isset( $prop );
	}

	public function is_overridden( $check_meta = false ) {
		$fields_to_check = ['name', 'description', 'price', 'spaces', 'start', 'end', 'min', 'max', 'status'];
		foreach ( $fields_to_check as $field ) {
			if ( $this->{$field} !== null ) {
				return true;
			}
		}
		return $check_meta && !empty($this->ticket_meta);
	}

	/**
	 * @return EM_Ticket
	 */
	public function get_parent () {
		if ( isset( $this->parent_ticket ) && $this->parent_ticket instanceof EM_Ticket ) {
			return $this->parent_ticket;
		}
		$EM_Ticket = EM_Ticket::get( $this->ticket_parent ); // will return empty ticket if non-existent
		if ( $EM_Ticket->ticket_id ) {
			$this->parent_ticket = $EM_Ticket;
		}
		return $EM_Ticket;
	}

	/**
	 * Saves the ticket into the database, whether a new or existing ticket
	 * @return boolean
	 */
	function save(){
		global $wpdb;
		$table = EM_TICKETS_TABLE;
		do_action('em_ticket_save_pre',$this);
		//First the person
		if($this->validate() && $this->can_manage() ){
			//Now we save the ticket
			$this->save_recurrences_v7(); // so that v7 is flagged here
			$data = $this->to_array(true); //add the true to remove the nulls
			if( !empty($data['ticket_meta']) ) $data['ticket_meta'] = serialize($data['ticket_meta']);
			if( !empty($data['ticket_members_roles']) ) $data['ticket_members_roles'] = serialize($data['ticket_members_roles']);
			if( !empty($this->ticket_meta['recurrences']) ){
				$data['ticket_start'] = $data['ticket_end'] = null;
			}
			if($this->ticket_id != ''){
				//since currently wpdb calls don't accept null, let's build the sql ourselves.
				$set_array = [];
				foreach( $this->fields as $field_name => $field ){
					if( ( !isset($data[$field_name]) || $data[$field_name] === '' ) && $field['null'] ){
						$set_array[] = "{$field_name}=NULL";
					}else{
						$set_array[] = "{$field_name}='".esc_sql($data[$field_name])."'";
					}
				}
				$sql = "UPDATE $table SET ".implode(', ', $set_array)." WHERE ticket_id={$this->ticket_id}";
				$result = $wpdb->query($sql);
				$this->feedback_message = __('Changes saved','events-manager');
			}else{
				if( isset($data['ticket_id']) && empty($data['ticket_id']) ) unset($data['ticket_id']);
				$result = $wpdb->insert($table, $data, $this->get_types($data));
			    $this->ticket_id = $wpdb->insert_id;
				$this->feedback_message = __('Ticket created','events-manager');
			}
			if( $result === false ){
				$this->feedback_message = __('There was a problem saving the ticket.', 'events-manager');
				$this->errors[] = __('There was a problem saving the ticket.', 'events-manager');
			}
			$this->compat_keys();
			$result = count($this->errors) == 0;
		}else{
			$this->feedback_message = __('There was a problem saving the ticket.', 'events-manager');
			$this->errors[] = __('There was a problem saving the ticket.', 'events-manager');
			$result = false;
		}
		$result = apply_filters('em_ticket_save', $result, $this);
		if ( $result ) {
			wp_cache_set( $this->ticket_id, $this, 'em_tickets' );
		}
		return $result;
	}

	/**
	 * Function to backport all overriding tickets to new format with default values
	 */
	public function save_recurrences_v7() {
		global $wpdb;
		if ( !$this->v7 ) {
			if ( $this->get_event()->is_recurring( true ) ) {
				//try the new way, just search tickets with the recurring ticket id stored as parent
				$sql = $wpdb->prepare( 'SELECT * FROM ' . EM_TICKETS_TABLE . " WHERE ticket_parent=%d", $this->ticket_id );
				$tickets = $wpdb->get_results( $sql, ARRAY_A );
				if ( empty( $tickets ) ) {
					// get older version of tickets, best-match
					$recurrence_set_id = $this->get_event()->get_recurrence_set()->recurrence_set_id;
					$recurrence_event_ids_sql = 'SELECT event_id FROM ' . EM_EVENTS_TABLE . ' WHERE recurrence_set_id=' . absint( $recurrence_set_id );
					//we don't have the exact ID reference for each ticket, and we can't assume changes to EM save_events will reschedule previously created events in earlier versions, we need to do it this way
					$sql_prepare = 'SELECT tickets FROM ' . EM_TICKETS_TABLE . " WHERE ticket_name=%s AND event_id IN ($recurrence_event_ids_sql)";
					$sql = $wpdb->prepare( $sql_prepare, $this->ticket_name );
					$tickets = $wpdb->get_col( $sql, ARRAY_A );
				}
				// any tickets we've found, we're going to loop through, and remove any identical settings
				if ( !empty( $tickets ) ) {
					foreach ( $tickets as $ticket ) {
						$ticket['ticket_parent'] = $this->ticket_id;

						$ticket_properties = [ 'price', 'description', 'spaces', 'start', 'end', 'min', 'max', 'required', 'members', 'members_roles', 'guests' ];
						foreach ( $ticket_properties as $prop ) {
							$property = 'ticket_' . $prop;
							if ( isset( $ticket[ $property ] ) && $ticket[ $property ] == $this->{$property} ) {
								$ticket[ $property ] = null;
							}
						}
						// update this ticket
						$wpdb->update( EM_TICKETS_TABLE, $ticket, [ 'ticket_id' => $ticket['ticket_id'] ] );
					}
				}
				// mark upgrade flag
				$this->ticket_meta['recurrences'] = $this->ticket_meta['recurrences'] ?? [];
				$this->ticket_meta['recurrences']['v7'] = true;
				$this->v7 = true;
			}
		}
	}

	/**
	 * Get posted data and save it into the object (not db)
	 * @return boolean
	 */
	function get_post($post = []){
		//We are getting the values via POST or GET
		global $allowedposttags;
		if( empty($post) ){
		    $post = $_REQUEST;
		}
		do_action('em_ticket_get_post_pre', $this, $post);
		$this->ticket_id = ( !empty($post['ticket_id']) && is_numeric($post['ticket_id']) ) ? absint($post['ticket_id']):null;
		$this->ticket_uuid = !empty($post['ticket_uuid']) && wp_is_uuid($post['ticket_uuid']) ? $post['ticket_uuid'] : wp_generate_uuid4();
		$this->ticket_status = ( isset($post['ticket_status']) && $post['ticket_status'] !== '-1' ) ? ( $post['ticket_status'] ? 1:0 ) : ( $this->ticket_parent ? null : 0 );
		$this->event_id = ( !empty($post['event_id']) && is_numeric($post['event_id']) ) ? absint($post['event_id']):null;
		$this->ticket_name = ( !empty($post['ticket_name']) ) ? wp_kses(wp_unslash($post['ticket_name']), 'em_ticket_name'):null;
		$this->ticket_description = ( !empty($post['ticket_description']) ) ? wp_kses(wp_unslash($post['ticket_description']), $allowedposttags):null;
		//spaces and limits
		$this->ticket_min = ( !empty($post['ticket_min']) && is_numeric($post['ticket_min']) ) ? absint($post['ticket_min']):null;
		$this->ticket_max = ( !empty($post['ticket_max']) && is_numeric($post['ticket_max']) ) ? absint($post['ticket_max']):null;
		if ( ( !empty($post['ticket_spaces']) && is_numeric($post['ticket_spaces']) ) ) {
			$this->ticket_spaces = absint($post['ticket_spaces']);
		} else {
			$this->ticket_spaces = $this->ticket_parent ? null : 10;
		}
		//sort out price and un-format in the event of special decimal/thousand seperators
		$price = ( !empty($post['ticket_price']) ) ? wp_kses_data($post['ticket_price']):'';
		if( preg_match('/^[0-9]*\.[0-9]+$/', $price) || preg_match('/^[0-9]+$/', $price) ){
			$this->ticket_price = (float) $price;
		} elseif ( $price === '' && $this->ticket_parent ) {
			$this->ticket_price = null;
		}else{
			$this->ticket_price = (float) str_replace( array( em_get_option('dbem_bookings_currency_thousands_sep'), em_get_option('dbem_bookings_currency_decimal_point') ), array('','.'), $price );
		}
		//Sort out date/time limits
		$this->ticket_start = ( !empty($post['ticket_start']) ) ? wp_kses_data($post['ticket_start']):'';
		$this->ticket_end = ( !empty($post['ticket_end']) ) ? wp_kses_data($post['ticket_end']):'';
		$start_time = !empty($post['ticket_start_time']) ? $post['ticket_start_time'] : $this->get_event()->start()->format('H:i');
		if( !empty($this->ticket_start) ) $this->ticket_start .= ' '. $this->sanitize_time($start_time);
		$end_time = !empty($post['ticket_end_time']) ? $post['ticket_end_time'] : $this->get_event()->start()->format('H:i');
		if( !empty($this->ticket_end) ) $this->ticket_end .= ' '. $this->sanitize_time($end_time);
		$this->start = $this->end = false; // reset start/end objects
		//sort out user availability restrictions
		$this->ticket_members = ( !empty($post['ticket_type']) && $post['ticket_type'] == 'members' ) ? 1:null;
		$this->ticket_guests = ( !empty($post['ticket_type']) && $post['ticket_type'] == 'guests' ) ? 1:null;
		$this->ticket_members_roles = [];
		if( $this->ticket_members && !empty($post['ticket_members_roles']) && is_array($post['ticket_members_roles']) ) {
			$WP_Roles = new WP_Roles();
			// set roles, and look at parent ticket in case there's a difference or defaults are requested.
			foreach ( $WP_Roles->roles as $role => $role_data ) {
				// role is either 1, 0 or default
				if ( in_array( $role, $post['ticket_members_roles'] ) ) {
					$this->ticket_members_roles[] = $role;
				}
			}
		}
		if ( !empty($post['ticket_required']) && $post['ticket_required'] !== 'default' ) {
		    $this->ticket_required = 1;
		} elseif ( ($post['ticket_required'] ?? 'default') === 'default' && $this->ticket_parent ) {
		    $this->ticket_required = null;
		} else {
		    $this->ticket_required = 0;
		}
		//if event is recurring, store start/end restrictions of this ticket, which are determined by number of days before (negative number) or after (positive number) the event start date
		if($this->get_event()->is_recurring( true )){
			if( empty($this->ticket_meta['recurrences']) ){
				$this->ticket_meta['recurrences'] = array( 'start_days'=>false, 'start_time'=>false, 'end_days'=>false, 'end_time'=>false, 'v7' => !empty($this->ticket_id) );
			}
			foreach( ['start', 'end'] as $start_or_end ){
				//start/end of ticket cut-off
				if( array_key_exists('ticket_'.$start_or_end.'_recurring_days', $post) && is_numeric($post['ticket_'.$start_or_end.'_recurring_days']) ){
					if( !empty($post['ticket_'.$start_or_end.'_recurring_when']) && $post['ticket_'.$start_or_end.'_recurring_when'] == 'after' ){
						$this->ticket_meta['recurrences'][$start_or_end.'_days'] = absint($post['ticket_'.$start_or_end.'_recurring_days']);
					}else{ //by default the start/end date is the point of reference
						$this->ticket_meta['recurrences'][$start_or_end.'_days'] = absint($post['ticket_'.$start_or_end.'_recurring_days']) * -1;
					}
					$this->ticket_meta['recurrences'][$start_or_end.'_time'] = ( !empty($post['ticket_'.$start_or_end.'_time']) ) ? $this->sanitize_time($post['ticket_'.$start_or_end.'_time']) : $this->get_event()->$start_or_end()->format('H:i');
				}else{
					unset($this->ticket_meta['recurrences'][$start_or_end.'_days']);
					unset($this->ticket_meta['recurrences'][$start_or_end.'_time']);
				}
			}
			$this->ticket_start = $this->ticket_end = null;

			// is multi-event ticket?
			$this->multi_event = ( !empty($post['multi_event']) ) ? absint($post['multi_event']) : null;
			$this->multi_event_auto_enrol = ( $this->multi_event === 0 && !empty($post['multi_event_auto_enrol']) ) ? 1:0;
			// multi-event tickets may refer ticket_ids or a temporary uuid if not defined already
			$this->multi_event_ticket = ( !empty($post['multi_event_ticket']) ) ? ( wp_is_uuid($post['multi_event_ticket']) ? $post['multi_event_ticket'] : absint($post['multi_event_ticket']) ) : null;
		}
		$this->compat_keys();
		do_action('em_ticket_get_post', $this, $post);
	}


	/**
	 * Validates the ticket for saving. Should be run during any form submission or saving operation.
	 * @return boolean
	 */
	function validate(){
		$missing_fields = Array ();
		$this->errors = [];
		foreach ( $this->required_fields as $field ) {
			if ( $this->$field == "") {
				$missing_fields[] = $field;
			}
		}
		if( !empty($this->ticket_price) && !is_numeric($this->ticket_price) ){
			$this->add_error(esc_html__('Please enter a valid ticket price e.g. 10.50 (no currency signs)','events-manager'));
		}
		if( !empty($this->ticket_min) && !empty($this->ticket_max) && $this->ticket_max < $this->ticket_min ) {
			$error = esc_html__('Ticket %s has a higher minimum spaces requirement than the maximum spaces allowed.','events-manager');
			$this->add_error( sprintf($error, '<em>'. esc_html($this->ticket_name) .'</em>'));
		}
		if ( count($missing_fields) > 0){
			// TODO Create friendly equivelant names for missing fields notice in validation
			$this->errors[] = __ ( 'Missing fields: ' ) . implode ( ", ", $missing_fields ) . ". ";
		}
		// if this is a recurring event, validate multi-event ticket link
		if ( $this->multi_event === 0 ) {
			// check there's a real ticket, within this recurring event, that we link to the multi-event ticket
			if ( is_numeric($this->multi_event_ticket) || wp_is_uuid( $this->multi_event_ticket ) ) {
				// a link to a pre-saved ticket, or a ticket to be saved with a temp UUID, verify it exists and we're OK
				$found_ticket = !empty( $this->get_event()->get_tickets()->tickets[$this->multi_event_ticket] );
			}
		}
		return apply_filters('em_ticket_validate', count($this->errors) == 0, $this );
	}

	/**
	 * @param bool $ignore_member_restrictions  Makes a member-restricted ticket available to any user or guest
	 * @param bool $ignore_guest_restrictions   Makes a guest-restricted ticket available to any user or guest
	 * @param bool $ignore_spaces               Ignores space availability
	 * @param false|WP_User $user               The user to check ticket availability against. Accepts a user object or false for a guest. By default current logged in user (or guest) is used.
	 * @return mixed|null
	 */
	function is_available( $ignore_member_restrictions = false, $ignore_guest_restrictions = false, $ignore_spaces = false, $user = null ){
		if ( !$this->status ) {
			return apply_filters('em_ticket_is_available', false, $this, $ignore_guest_restrictions, $ignore_member_restrictions, $ignore_spaces, $user);
		}
		if( EM_Bookings::$disable_restrictions ){
			return apply_filters('em_ticket_is_available', true, $this, true, true, true, null);
		}
		// complete short-circuit, but overriding functions should beware of the $disable_restrictions flag!
		if( isset($this->is_available) && !$ignore_member_restrictions && !$ignore_guest_restrictions && !$ignore_spaces && $user === null ) return apply_filters('em_ticket_is_available',  $this->is_available, $this, false, false, false, null); //save extra queries if doing a standard check
		$is_available = false;
		$EM_Event = $this->get_event();
		if( $EM_Event->get_active_status() !== 0 ){
			if( $user === null ){
				$user = is_user_logged_in() ? wp_get_current_user() : false;
			}
			$available_spaces = $this->get_available_spaces();
			$condition_1 = empty($this->ticket_start) || $this->start()->getTimestamp() <= time();
			$condition_2 = empty($this->ticket_end) || $this->end()->getTimestamp() >= time();
			$condition_3 = $EM_Event->rsvp_end()->getTimestamp() > time(); //either defined ending rsvp time, or start datetime is used here
			$condition_4 = !$this->members || $user !== false || $ignore_member_restrictions;
			$condition_5 = true;
			if( !$ignore_member_restrictions && $this->members && !empty($this->members_roles) ){
				//check if user has the right role to use this ticket
				$condition_5 = false;
				if( $user !== false ){
					if( count(array_intersect($user->roles, $this->members_roles)) > 0 ){
						$condition_5 = true;
					}
				}
			}
			$condition_6 = !$this->guests || $user === false || $ignore_guest_restrictions;
			if( $condition_1 && $condition_2 && $condition_3 && $condition_4 && $condition_5 && $condition_6  ){
				//Time Constraints met, now quantities
				if( $available_spaces > 0 && ($available_spaces >= $this->min || empty($this->min)) ){
					$is_available = true;
				}elseif( $ignore_spaces === true ) {
					$is_available = true;
				}
			}
		}
		if( !$ignore_member_restrictions && !$ignore_guest_restrictions && !$ignore_spaces ){ //$this->is_available is only stored for the viewing user
			$this->is_available = $is_available;
		}
		return apply_filters('em_ticket_is_available', $is_available, $this, $ignore_guest_restrictions, $ignore_member_restrictions, $ignore_spaces, $user);
	}

	/**
	 * Checks if ticket is abailable to a specific user type based on user restrictions, other restrictions like dates, availability etc. is ignored. This can generically be guest (0 or false), registered user (true) or more specifically role (string) or a specific user ID (int).
	 * If this check is for a generic registered user, a check will not be made for role restrictions, only if the ticket is restricted to logged in users.
	 * @param int|WP_User|bool|string $user_type
	 * @return bool
	 * @since 6.1.1.1
	 */
	public function is_available_to( $user_type = 0 ){
		if ( !$this->status ) {
			return false;
		}
		if( $user_type === 0 || $user_type === false ){
			// guest
			return !$this->members;
		}elseif( $user_type === true ){
			// registered user, all but guest tickets theoretically available
			return !$this->guests;
		}elseif( is_numeric($user_type) || $user_type instanceof WP_User ){
			// real user id or
			if( $user_type instanceof WP_User ){
				$user = $user_type;
			}else{
				$user = new WP_User($user_type);
			} /*  @var WP_User $user */
			if( $this->members && !empty($this->members_roles) ) {
				// return whether roles coincide with current user roles
				return count(array_intersect($user->roles, $this->members_roles)) > 0;
			}
			// otherwise check if limited to guests, if not it doesn't matter whether it's general user logged-in limit or no limit
			return !$this->guests;
		}elseif( is_string($user_type) ){
			// user role
			if( $this->members && !empty($this->members_roles) ) {
				return in_array($user_type, $this->members_roles);
			}
			// otherwise check if limited to guests
			return !$this->guests;
		}
		return false;
	}

	/**
	 * Returns whether this ticket should be displayed based on availability and other ticket properties and general settings
	 * @param bool $ignore_member_restrictions
	 * @param bool $ignore_guest_restrictions
	 * @return boolean
	 */
	function is_displayable( $ignore_member_restrictions = false, $ignore_guest_restrictions = false ){
		$return = false;
		if( $this->is_available($ignore_member_restrictions, $ignore_guest_restrictions) ){
			$return = true;
		}else{
			if( $this->get_event()->get_option('dbem_bookings_tickets_show_unavailable') ){
				$return =  true;
				if( $this->members && !$this->get_event()->get_option('dbem_bookings_tickets_show_member_tickets') ){
					$return = false;
				}
			}
		}
		return apply_filters('em_ticket_is_displayable', $return, $this, $ignore_guest_restrictions, $ignore_member_restrictions);
	}

	/**
	 * Gets the total price for this ticket, includes tax if settings dictates that tax is added to ticket price.
	 * Use $this->ticket_price or $this->get_price_without_tax() if you definitely don't want tax included.
	 * @param boolean $format
	 * @return float
	 */
	function get_price($format = false){
		$price = $this->price;
		if( $this->get_event()->get_option('dbem_bookings_tax_auto_add') ){
			$price = $this->get_price_with_tax();
		}
		$price = apply_filters('em_ticket_get_price',$price,$this);
		if($format){
			return $this->format_price($price);
		}
		return $price;
	}

	/**
	 * Calculates how much the individual ticket costs with applicable event/site taxes included.
	 * @param boolean $format
	 * @return float|int|string
	 */
	function get_price_with_tax( $format = false ){
	    $price = $this->get_price_without_tax() * (1 + $this->get_event()->get_tax_rate( true ));
	    if( $format ) return $this->format_price($price);
	    return $price;
	}

	/**
	 * Calculates how much the individual ticket costs with taxes excluded.
	 * @param boolean $format
	 * @return float|int|string
	 */
	function get_price_without_tax( $format = false ){
	    if( $format ) return $this->format_price($this->price);
	    return apply_filters('em_ticket_get_price_without_tax', $this->price, $this);
	}

	/**
	 * Shows the ticket price which can contain long decimals but will show up to 2 decimal places and remove trailing 0s
	 * For example: 10.010230 => 10.01023 and 10 => 10.00
	 * @param bool $format If true, the number is provided with localized digit separator and padded with 0, 2 or 4 digits
	 * @return float|int|string
	 */
	function get_price_precise( $format = false ){
		$price = $this->price * 1;
		if( floor($price) == (float) $price ) $price = number_format($price, 2, '.', '');
		if( $format ){
			$digits = strlen(substr(strrchr($price, "."), 1));
			$precision = ( $digits > 2 ) ? 4 : 2;
			$price = number_format( $price, $precision, em_get_option('dbem_bookings_currency_decimal_point','.'), '');
		}
		return $price;
	}

	/**
	 * Get the total number of tickets (spaces) available, bearing in mind event-wide maxiumums and ticket priority settings.
	 * @return int
	 */
	function get_spaces(){
		$spaces = $this->spaces;
		if ( $this->get_event()->is_recurring( true ) ) {
			// add all spaces for all recurrences
			$spaces = $spaces * count( $this->get_event()->get_recurrence_sets()->get_recurrences() );
		} elseif ( $this->get_event()->has_timeslots() ) {
			$spaces = $spaces * count($this->get_event()->get_timeranges()->get_timeslots());
		}
		return apply_filters('em_ticket_get_spaces', $spaces, $this);
	}

	/**
	 * Returns the number of available spaces left in this ticket, bearing in mind event-wide restrictions, previous bookings, approvals and other tickets.
	 * @return int
	 */
	function get_available_spaces(){
		$event_available_spaces = $this->get_event()->get_bookings()->get_available_spaces();
		$ticket_available_spaces = $this->get_spaces() - $this->get_booked_spaces();
	    $ticket_available_spaces = $ticket_available_spaces - $this->get_reserved_spaces();
		$return = ($ticket_available_spaces <= $event_available_spaces) ? $ticket_available_spaces:$event_available_spaces;
		return apply_filters( 'em_ticket_get_available_spaces', $return, $this, array('event_spaces' => $event_available_spaces, 'ticket_spaces' => $ticket_available_spaces) );
	}

	/**
	 * Get total number of pending spaces for this ticket.
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_pending_spaces( $force_refresh = false ){
		if( !array_key_exists($this->event_id, $this->pending_spaces) || $force_refresh ){
			$pending_spaces = $this->get_status_spaces( 0, $force_refresh );
			$this->pending_spaces[$this->event_id] = $pending_spaces > 0 ? $pending_spaces : 0;
			$this->pending_spaces[$this->event_id] = apply_filters('em_ticket_get_pending_spaces', $this->pending_spaces[$this->event_id], $this, $force_refresh);
		}
		return $this->pending_spaces[$this->event_id];
	}

	/**
	 * Get the total number of pending spaces for this ticket. Identical to get_pending_spaces(), but allows differentiation between a PENDING booking and a reserved booking (for example, a booking temporarily awaiting online payment)
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_reserved_spaces( $force_refresh = false ){
		if( $this->get_event()->get_option('dbem_bookings_approval_reserved')) {
			if ( !array_key_exists( $this->event_id, $this->reserved_spaces ) || $force_refresh ) {
				$reserved_spaces = $this->get_status_spaces( 0, $force_refresh );
				$reserved_spaces = $reserved_spaces > 0 ? $reserved_spaces : 0;
				$this->reserved_spaces[ $this->event_id ] = apply_filters( 'em_ticket_get_reserved_spaces', $reserved_spaces, $this, $force_refresh );
			}
			return $this->reserved_spaces[ $this->event_id ];
		}
		// if we reach here, always run the filter to allow other bookings to override other reserved spaces with bookings of different status
		return apply_filters( 'em_ticket_get_reserved_spaces', 0, $this, $force_refresh );
	}

	/**
	 * Returns the number of booked spaces in this ticket.
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_booked_spaces( $force_refresh = false ){
		if( !array_key_exists($this->event_id, $this->pending_spaces) || $force_refresh ){
			$status = !$this->get_event()->get_option('dbem_bookings_approval') ? '0,1' : 1;
			$booked_spaces = $this->get_status_spaces( $status, $force_refresh );
			$booked_spaces = $booked_spaces > 0 ? $booked_spaces : 0;
			$this->booked_spaces[$this->event_id] = apply_filters('em_ticket_get_booked_spaces', $booked_spaces, $this, $force_refresh);
		}
		return $this->booked_spaces[$this->event_id];
	}

	public function get_status_spaces( $status, $force_refresh = false ) {
		global $wpdb;
		// clean up $status
		if ( is_array($status) ) {
			$status = implode(',', $status);
		}
		$status = str_replace(' ', '', $status);
		if ( !preg_match('/[^0-9,]/', $status) ) {
			if ( !isset( $this->status_counts[ $this->event_id ][ $status ] ) || $force_refresh ) {
				$sub_sql = 'SELECT booking_id FROM '.EM_BOOKINGS_TABLE." WHERE event_id=%d AND booking_status IN ($status)";
				if ( $this->get_event()->is_timeslot() ) {
					$sub_sql .= " AND timeslot_id=" . absint($this->get_event()->timeslot_id);
				}
				$sql = 'SELECT SUM(ticket_booking_spaces) FROM '.EM_TICKETS_BOOKINGS_TABLE. " WHERE booking_id IN ($sub_sql) AND ticket_id=%d";
				$this->status_counts[ $this->event_id ][ $status ] = $wpdb->get_var( $wpdb->prepare( $sql, $this->event_id, $this->ticket_id ) );
			}
		}
		return apply_filters('em_ticket_get_status_spaces', $this->status_counts[ $this->event_id ][ $status ] ?? 0, $this, $status, $force_refresh);
	}

	/**
	 * Returns the total number of bookings of all statuses for this ticket
	 * @param int $status
	 * @param boolean $force_refresh
	 * @return int
	 */
	function get_bookings_count( $status = false, $force_refresh = false ){
		global $wpdb;
		if( !array_key_exists($this->event_id, $this->bookings_count) || $force_refresh ){
			$sub_sql = 'SELECT booking_id FROM '.EM_BOOKINGS_TABLE.' WHERE event_id=%d';
			if ( $this->get_event()->is_timeslot() ) {
				$sub_sql .= " AND timeslot_id=" . absint($this->get_event()->timeslot_id);
			}
			$sql = 'SELECT COUNT(*) FROM '.EM_TICKETS_BOOKINGS_TABLE. ' WHERE booking_id IN ('. $sub_sql .') AND ticket_id=%d';
			$bookings_count = $wpdb->get_var($wpdb->prepare($sql, $this->event_id, $this->ticket_id));
			$this->bookings_count[$this->event_id] = $bookings_count > 0 ? $bookings_count : 0;
			$this->bookings_count[$this->event_id] = apply_filters('em_ticket_get_bookings_count', $this->bookings_count[$this->event_id], $this, $force_refresh);
		}
		return $this->bookings_count[$this->event_id];
	}

	/**
	 * Returnds the event associated with this set of tickets, if there is one.
	 * @return EM_Event
	 */
	function get_event(){
		if( $this->event && $this->event->event_id == $this->event_id ){
			return $this->event;
		}
		global $EM_Event;
		if( is_object($EM_Event) && $EM_Event->event_id == $this->event_id ){
			$this->event = $EM_Event;
			return $EM_Event;
		}else{
			$this->event = em_get_event($this->event_id);
			return $this->event;
		}
	}
	/**
	 * Returns an array of EM_Booking objects that have this ticket
	 * @return EM_Bookings
	 */
	function get_bookings(){
		$bookings = [];
		foreach( $this->get_event()->get_bookings()->bookings as $EM_Booking ){
			foreach($EM_Booking->get_tickets_bookings()->tickets_bookings as $EM_Ticket_Booking){
				if( $EM_Ticket_Booking->ticket_id == $this->ticket_id ){
					$bookings[$EM_Booking->booking_id] = $EM_Booking;
				}
			}
		}
		$this->bookings = new EM_Bookings($bookings);
		return $this->bookings;
	}

	/**
	 *
	 * @return mixed|void
	 */
	public function get_recurrence_ticket_ids(){
		global $wpdb;
		$ticket_ids = [];
		if( $this->get_event()->is_recurring( true ) ){
			//try the new way, just search tickets with the recurring ticket id stored as parent
			$sql = $wpdb->prepare('SELECT ticket_id FROM '.EM_TICKETS_TABLE." WHERE ticket_parent=%d", $this->ticket_id);
			$ticket_ids = $wpdb->get_col($sql);
		}
		$ticket_ids = is_array($ticket_ids) ? $ticket_ids : [];
		foreach( $ticket_ids as $k => $v ) $ticket_ids[$k] = absint($v); //clean for SQL usage
		return apply_filters('em_ticket_get_recurrence_ticket_ids', $ticket_ids, $this);
	}

	/**
	 * Delete the ticket and subsequent child tickets. This function will not delete tickets that have bookings tied to them.
	 * If this ticket does not have bookings associated with it, but child tickets do, then base ticket data will be copied to child tickets and the child tickets will be preserved.
	 * If child tickets have children of their own, then those will be deleted recursively via their respected EM_Ticket::delete() functions. Otherwise, they will be directly deleted via SQL.
	 * Any outside functionality that wants to catch delete actions should use the em_ticket_deleted action.
	 *
	 * @return boolean
	 */
	function delete(){
		global $wpdb;
		$result = false;
		if( $this->can_manage() ){
			if( count($this->get_bookings()->bookings) == 0 ){
				// check if this ticket has children and, if so, delete those if they don't have bookings
				$child_ticket_ids = $wpdb->get_col( $wpdb->prepare( 'SELECT ticket_id FROM '. EM_TICKETS_TABLE . ' WHERE ticket_parent=%d', $this->ticket_id ) );
				if ( $child_ticket_ids ) {
					// disable the status of all these tickets in one go, so they are not available for booking anymore
					$wpdb->update( EM_TICKETS_TABLE, ['ticket_status' => 0], [ 'ticket_parent' => $this->ticket_id ], ['%d'], ['%d'] );
					// get all ticket IDs with bookings in them
					$subquery = "SELECT DISTINCT ticket_id FROM ". EM_TICKETS_BOOKINGS_TABLE . ' WHERE ticket_id IN ( SELECT ticket_id FROM '. EM_TICKETS_TABLE .' WHERE ticket_parent=' . absint($this->ticket_id) . ' ) ';
					$booked_child_ticket_ids = $wpdb->get_col( $subquery );
					// if tickets have bookings tied to them, we copy all the ticket data to it and do not delete
					if ( $booked_child_ticket_ids ) {
						// copy original ticket data to all tickets with bookings before this parent ticket gets deleted so they are not overriding tickets anymore
						$sql = static::detach_parent_sql( $this->ticket_id, $booked_child_ticket_ids);
						$wpdb->query( $sql );
						// get unbooked tickets
						$deletable_child_ticket_ids = array_diff( $child_ticket_ids, $booked_child_ticket_ids );
					} else {
						// just delete all the child tickets
						$deletable_child_ticket_ids = $child_ticket_ids;
					}
					// DELETE all tickets without current bookings in them
					if ( $deletable_child_ticket_ids ) {
						// do these ticket IDs have children? If so, we need to delete those tickets via this function recursively and repeat this whole process, otherwise we can just do a mass deletion
						$deletable_parent_ticket_ids = $wpdb->get_col( $wpdb->prepare( 'SELECT DISTINCT ticket_parent FROM '. EM_TICKETS_TABLE . ' WHERE ticket_parent IN ( ' . implode( ',', $deletable_child_ticket_ids ) . ')' ) );
						if ( $deletable_parent_ticket_ids ) {
							// again, copy original ticket data to all tickets that have children so those children can detach and copy parent data correctly
							$sql = static::detach_parent_sql( $this->ticket_id, $deletable_parent_ticket_ids);
							$wpdb->query( $sql );
							// can't delete tickets outright as they have children of their own, recursively delete via class method
							foreach( $deletable_parent_ticket_ids as $ticket_id ) {
								$EM_Ticket = EM_Ticket::get( $ticket_id );
								$EM_Ticket->delete();
							}
							// get the remaining child ticket IDs that are directly deletable
							$deletable_child_ticket_ids = array_diff( $deletable_child_ticket_ids, $deletable_parent_ticket_ids );
						}
						// delete all tickets without parents and trigger their deleted actions
						foreach ( $deletable_child_ticket_ids as $ticket_id ) {
							do_action( 'em_ticket_before_delete', $ticket_id );
						}
						$wpdb->query("DELETE FROM ". EM_TICKETS_TABLE . ' WHERE ticket_id IN ('. implode(',', $deletable_child_ticket_ids) . ')');
						foreach ( $deletable_child_ticket_ids as $ticket_id ) {
							do_action( 'em_ticket_deleted', $ticket_id );
						}
					}
				}
				// now delete this ticket
				do_action( 'em_ticket_before_delete', $this->ticket_id );
				$sql = $wpdb->prepare("DELETE FROM ". EM_TICKETS_TABLE . " WHERE ticket_id=%d", $this->ticket_id);
				$result = $wpdb->query( $sql );
				do_action('em_ticket_deleted', $this->ticket_id );
			}else{
				$this->feedback_message = __('You cannot delete a ticket that has a booking on it.','events-manager');
				$this->add_error($this->feedback_message);
				return false;
			}
		}
		// we recommend you use the em_ticket_deleted unless you want to change the result of a deletion, but bear in mind that the ticket is already deleted in the DB at this point!
		return apply_filters('em_ticket_delete', $result !== false, $this);
	}

	/**
	 * Detaches the ticket from a parent ticket by copying over any inherited settings and removing the parent ticket ID.
	 * @return bool
	 */
	public function detach() {
		global $wpdb;
		if ( $this->ticket_parent ) {
			$sql = static::detach_parent_sql( $this->ticket_parent, [ $this->ticket_id ] );
			return $wpdb->query( $sql ) !== false;
		}
		return false;
	}

	/**
	 * @param $parent_id
	 * @param $ticket_ids
	 *
	 * @return string
	 */
	public static function detach_parent_sql( $parent_id, $ticket_ids ) {
		if ( !is_array($ticket_ids) ) {
			$ticket_ids = [ $ticket_ids ];
		}
		return 'UPDATE ' . EM_TICKETS_TABLE . ' AS target
				INNER JOIN ' . EM_TICKETS_TABLE . ' AS source ON source.ticket_id = ' . absint( $parent_id ) . '
				SET
				    target.ticket_status = CASE WHEN target.ticket_status IS NULL THEN source.ticket_status ELSE target.ticket_status END,
				    target.ticket_name = CASE WHEN target.ticket_name IS NULL THEN source.ticket_name ELSE target.ticket_name END,
				    target.ticket_description = CASE WHEN target.ticket_description IS NULL THEN source.ticket_description ELSE target.ticket_description END,
				    target.ticket_price = CASE WHEN target.ticket_price IS NULL THEN source.ticket_price ELSE target.ticket_price END,
				    target.ticket_min = CASE WHEN target.ticket_min IS NULL THEN source.ticket_min ELSE target.ticket_min END,
				    target.ticket_max = CASE WHEN target.ticket_max IS NULL THEN source.ticket_max ELSE target.ticket_max END,
				    target.ticket_spaces = CASE WHEN target.ticket_spaces IS NULL THEN source.ticket_spaces ELSE target.ticket_spaces END,
				    target.ticket_members = CASE WHEN target.ticket_members IS NULL THEN source.ticket_members ELSE target.ticket_members END,
				    target.ticket_members_roles = CASE WHEN target.ticket_members_roles IS NULL THEN source.ticket_members_roles ELSE target.ticket_members_roles END,
				    target.ticket_guests = CASE WHEN target.ticket_guests IS NULL THEN source.ticket_guests ELSE target.ticket_guests END,
				    target.ticket_required = CASE WHEN target.ticket_required IS NULL THEN source.ticket_required ELSE target.ticket_required END,
				    target.ticket_meta = CASE WHEN target.ticket_meta IS NULL THEN source.ticket_meta ELSE target.ticket_meta END,
				    target.ticket_parent = NULL
				WHERE source.ticket_id = ' . absint( $parent_id ) . '
				AND target.ticket_id IN ( ' . implode(',', $ticket_ids) . ');
			';
	}

	/**
	 * Detaches the ticket from a parent ticket by copying over any inherited settings and removing the parent ticket ID.
	 * @return bool
	 */
	public function attach( $ticket_parent ) {
		global $wpdb;
		$this->ticket_parent = $ticket_parent;
		$sql = static::attach_parent_sql( $this->ticket_parent, $this->ticket_id );
		return $wpdb->query( $sql ) !== false;
	}

	/**
	 * Attaches a ticket to a parent ticket
	 * @param int $parent_id
	 * @param int|int[] $ticket_ids
	 *
	 * @return bool
	 */
	public static function attach_parent_sql( $parent_id, $ticket_ids ) {
		if ( !is_array($ticket_ids) ) {
			$ticket_ids = [ $ticket_ids ];
		}
		return 'UPDATE ' . EM_TICKETS_TABLE . ' AS target
				INNER JOIN ' . EM_TICKETS_TABLE . ' AS source ON source.ticket_id = ' . absint( $parent_id ) . '
				SET
				    target.ticket_status = CASE WHEN target.ticket_status = source.ticket_status THEN NULL ELSE target.ticket_status END,
				    target.ticket_description = CASE WHEN target.ticket_description = source.ticket_description THEN NULL ELSE target.ticket_description END,
				    target.ticket_price = CASE WHEN target.ticket_price = source.ticket_price THEN NULL ELSE target.ticket_price END,
				    target.ticket_min = CASE WHEN target.ticket_min = source.ticket_min THEN NULL ELSE target.ticket_min END,
				    target.ticket_max = CASE WHEN target.ticket_max = source.ticket_max THEN NULL ELSE target.ticket_max END,
				    target.ticket_spaces = CASE WHEN target.ticket_spaces = source.ticket_spaces THEN NULL ELSE target.ticket_spaces END,
				    target.ticket_members = CASE WHEN target.ticket_members = source.ticket_members THEN NULL ELSE target.ticket_members END,
				    target.ticket_members_roles = CASE WHEN target.ticket_members_roles = source.ticket_members_roles THEN NULL ELSE target.ticket_members_roles END,
				    target.ticket_guests = CASE WHEN target.ticket_guests = source.ticket_guests THEN NULL ELSE target.ticket_guests END,
				    target.ticket_required = CASE WHEN target.ticket_required = source.ticket_required THEN NULL ELSE target.ticket_required END,
				    target.ticket_meta = CASE WHEN target.ticket_meta = source.ticket_meta THEN NULL ELSE target.ticket_meta END,
				    target.ticket_parent = source.ticket_id
				WHERE source.ticket_id = ' . absint( $parent_id ) . '
				AND target.ticket_id IN ( ' . implode(',', $ticket_ids) . ');';
	}

	/**
	 * Based on ticket minimums, whether required and if the event has more than one ticket this function will return the absolute minimum required spaces for a booking
	 */
	function get_spaces_minimum(){
	    $ticket_count = count($this->get_event()->get_bookings()->get_tickets()->tickets);
	    //count available tickets to make sure
	    $available_tickets = 0;
	    foreach($this->get_event()->get_bookings()->get_tickets()->tickets as $EM_Ticket){
	    	if($EM_Ticket->is_available()){
	    		$available_tickets++;
	    	}
	    }
	    $min_spaces = 0;
		$min = $this->min;
	    if( $ticket_count > 1 ){
	        if( $this->is_required() && $this->is_available() ){
	            $min_spaces = ($min > 0) ? $min:1;
	        }elseif( $this->is_available() && $min > 0 ){
	            $min_spaces = $min;
	        }elseif( $this->is_available() && $available_tickets == 1 ){
	            $min_spaces = 1;
	        }
	    }else{
	    	$min_spaces = $min > 0 ? $min : 1;
	    }
	    return $min_spaces;
	}

	function is_required(){
	    if( $this->required || count($this->get_event()->get_tickets()->tickets) == 1 ){
	        return true;
	    }
	    return false;
	}

	/**
	 * Get the html options for quantities to go within a <select> container
	 * @return string
	 */
	function get_spaces_options($zero_value = true, $default_value = 0){
		$available_spaces = $this->get_available_spaces();
		$max_spaces = $this->get_event()->get_option('dbem_bookings_form_max');
		if( EM_Bookings::$disable_restrictions && $max_spaces > $available_spaces ) $available_spaces = $max_spaces;
		if( $this->is_available() ) {
		    $min_spaces = $this->get_spaces_minimum();
		    if( $default_value > 0 ){
			    $default_value = $min_spaces > $default_value ? $min_spaces:absint($default_value);
		    }else{
		        $default_value = $this->is_required() ? $min_spaces:0;
		    }
			ob_start();
			$label = esc_attr__('Select number of spaces', 'events-manager');
			?>
			<select name="em_tickets[<?php echo $this->id ?>][spaces]" class="em-ticket-select" id="em-ticket-spaces-<?php echo $this->ticket_id ?>" data-ticket-id="<?php echo esc_attr($this->ticket_id); ?>" aria-label="<?php echo $label; ?>">
				<?php
					$min = ($this->min > 0) ? $this->min:1;
					$max = ($this->max > 0) ? $this->max:$max_spaces;
					if( $this->get_event()->event_rsvp_spaces > 0 && $this->get_event()->event_rsvp_spaces < $max ) $max = $this->get_event()->event_rsvp_spaces;
				?>
				<?php if($zero_value && !$this->is_required()) : ?><option>0</option><?php endif; ?>
				<?php for( $i=$min; $i<=$available_spaces && $i<=$max; $i++ ): ?>
					<option <?php if($i == $default_value){ echo 'selected="selected"'; $shown_default = true; } ?>><?php echo absint($i) ?></option>
				<?php endfor; ?>
				<?php if(empty($shown_default) && $default_value > 0 ): ?><option selected="selected"><?php echo absint($default_value); ?></option><?php endif; ?>
			</select>
			<?php
			return apply_filters('em_ticket_get_spaces_options', ob_get_clean(), $zero_value, $default_value, $this);
		}else{
			return false;
		}
	}

	/**
	 * Returns an EM_DateTime object of the ticket start date/time in local timezone of event.
	 * If no start date defined or if date is invalid, false is returned.
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime|false
	 * @see EM_Event::get_datetime()
	 */
	public function start( $utc_timezone = false ){
		return apply_filters('em_ticket_start', $this->get_datetime('start', $utc_timezone), $this);
	}

	/**
	 * Returns an EM_DateTime object of the ticket end date/time in local timezone of event.
	 * If no start date defined or if date is invalid, false is returned.
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default.
	 * @return EM_DateTime|false
	 * @see EM_Event::get_datetime()
	 */
	public function end( $utc_timezone = false ){
		return apply_filters('em_ticket_end', $this->get_datetime('end', $utc_timezone), $this);
	}

	/**
	 * Generates an EM_DateTime for the the start/end date/times of the ticket in local timezone.
	 * If ticket has no start/end date, or an invalid format, false is returned.
	 * @param string $when 'start' or 'end' date/time
	 * @param bool $utc_timezone Returns EM_DateTime with UTC timezone if set to true, returns local timezone by default. Do not use if EM_DateTime->valid is false.
	 * @return EM_DateTime|false
	 */
	public function get_datetime( $when = 'start', $utc_timezone = false ){
		if( $when != 'start' && $when != 'end') return new EM_DateTime(); //currently only start/end dates are relevant
		//Initialize EM_DateTime if not already initialized, or if previously initialized object is invalid (e.g. draft event with invalid dates being resubmitted)
		$when_date = 'ticket_'.$when;
		//we take a pass at creating a new datetime object if it's empty, invalid or a different time to the current start date
		if ( !empty($this->$when_date) ){
			if( empty($this->$when) || !$this->$when->valid ){
				$this->$when = new EM_DateTime( $this->$when_date, $this->get_event()->get_timezone() );
			}
		} elseif ( $this->$when_date === null && $this->ticket_parent !== null ) {
			// return parent ticket
			return $this->get_parent()->{$when}();
		} else {
			$this->$when = new EM_DateTime();
			$this->$when->valid = false;
		}
		//Set to UTC timezone if requested, local by default
		$tz = $utc_timezone ? 'UTC' : $this->get_event()->get_timezone();
		$this->$when->setTimezone($tz);
		return $this->$when;
	}

	/**
	 * Retrieves a value from ticket_meta or parent ticket_meta using key path.
	 *
	 * @param mixed ...$keys Sequence of keys to traverse
	 * @return mixed|null
	 */
	public function get_meta(...$keys) {
		$value = $this->ticket_meta;
		foreach ( $keys as $k ) {
			if ( !is_array( $value ) || !array_key_exists( $k, $value ) ) {
				return $this->ticket_parent ? $this->get_parent()->has_meta( ...$keys ) : null;
            }
			$value = $value[ $k ];
		}
		return $value;
	}

	/**
	 * Checks whether a meta key exists locally or in parent.
	 *
	 * @param mixed ...$keys Sequence of keys to traverse
	 * @return bool
	 */
	public function has_meta(...$keys): bool {
		$value = $this->ticket_meta;
		foreach ( $keys as $k ) {
			if ( !is_array( $value ) || !array_key_exists( $k, $value ) ) {
				return $this->ticket_parent && $this->get_parent()->has_meta( ...$keys );
            }
			$value = $value[ $k ];
		}
		return true;
	}

	/**
	 * Returns true if the value is defined in the parent but not overridden in the current ticket.
	 * Useful for checking inherited values.
	 *
	 * @param mixed ...$keys
	 * @return bool
	 */
	public function is_meta_overridden(...$keys): bool {
		$value = $this->ticket_meta;
		foreach ( $keys as $k ) {
			if ( !is_array( $value ) || !array_key_exists( $k, $value ) ) {
				return $this->get_parent()->has_meta( ...$keys );
			}
			$value = $value[ $k ];
		}
		return false;
	}

	/**
	 * Can the user manage this event?
	 */
	function can_manage( $owner_capability = false, $admin_capability = false, $user_to_check = false ){
		if( $this->ticket_id == '' && !is_user_logged_in() && $this->get_event()->get_option('dbem_events_anonymous_submissions') ){
			$user_to_check = $this->get_event()->get_option('dbem_events_anonymous_user');
		}
		return $this->get_event()->can_manage('manage_bookings','manage_others_bookings', $user_to_check);
	}

	/**
	 * Deprecated since 5.8.2, just access properties directly or use relevant functions such as $this->start() for ticket_start time - Outputs properties with formatting
	 * @param string $property
	 * @return string
	 */
	function output_property($property){
		switch($property){
			case 'start':
				$value = ( $this->start()->valid ) ? $this->start()->i18n( em_get_date_format() ) : '';
				break;
			case 'end':
				$value = ( $this->end()->valid ) ? $this->end()->i18n( em_get_date_format() ) : '';
				break;
			default:
				$value = $this->$property;
				break;
		}
		return apply_filters('em_ticket_output_property',$value,$this, $property);
	}

	/**
	 * Gets placeholder for input field of given property, which will show the parent ticket value if there is one.
	 *
	 * @param string $prop Property name such as 'ticket_price' or 'price'.
	 *
	 * @return mixed|string The property value or an empty string if not overriden by a parent.
	 */
	public function get_input_placeholder ( $property ) {
		// Resolve the short property name from shortcuts or assume it's a real property name
		if ( !empty(static::$field_shortcuts[ $property ]) ) {
			$prop = $property;
		} else {
			$prop = array_search( $property, static::$field_shortcuts, true ) ?: $property;
		}
		if ( $this->ticket_parent ) {
			$value = esc_attr($this->get_parent()->{$prop});
		}
		return $value ?? '';
	}
	
}
?>