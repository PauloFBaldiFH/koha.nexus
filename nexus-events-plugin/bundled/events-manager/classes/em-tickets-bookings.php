<?php
/**
 * Deals with the each ticket booked in a single booking.
 * Each ticket is grouped by EM_Ticket_Bookings, which is stored as an array in the tickets_bookings object.
 *
 * You can access/add/unset the array of EM_Ticket_Bookings and its sub array of EM_Ticket_Booking objects in a few ways, with example ticket ID # 34884:
 *
 * Access the EM_Ticket_Bookings of a ticket:
 * $EM_Tickets_Bookings[34884]
 * $EM_Tickets_Bookings->tickets_bookings[34884]
 *
 * Add a new EM_Ticket_Bookings for a ticket:
 * $EM_Tickets_Bookings[1234] = new EM_Tickets_Bookings(...)
 * $EM_Tickets_Bookings->tickets_bookings[1234] = new EM_Tickets_Bookings(...)
 *
 * Add a new EM_Ticket_Booking object to existing EM_Ticket_Bookings objects
 * $EM_Tickets_Bookings[34884]['uuid'] = new EM_Ticket_Booking(...); // text key - should be a uuid
 * $EM_Tickets_Bookings->tickets_bookings[34884]['uuid'] = new EM_Ticket_Booking(...);
 * $EM_Tickets_Bookings->tickets_bookings[34884]->tickets_bookings['uuid'] = new EM_Ticket_Booking(...);
 *
 * Unset works the same way:
 * unset($EM_Tickets_Bookings[35280]);
 * unset($EM_Tickets_Bookings->tickets_bookings[34884]);
 * etc.
 *
 * @author marcus
 *
 */
class EM_Tickets_Bookings extends EM_Object implements Iterator, Countable, ArrayAccess {
	
	/**
	 * Array of EM_Ticket_Booking objects for a specific event
	 * @var EM_Ticket_Bookings[]
	 */
	public $tickets_bookings = array();
	protected $tickets_bookings_loaded;
	/**
	 * When adding existing booked tickets via add() with 0 spaces, they get slotted here for deletion during save() so they circumvent validation.
	 * @var array[EM_Ticket_Booking]
	 */
	var $tickets_bookings_deleted = array();
	/**
	 * This object belongs to this booking object
	 * @var EM_Booking
	 */
	protected $booking;
	/**
	 * The booking ID this object belongs to, saved by preference if booking object is not available, and booking object is obtained after when needed.
	 * @var float|int|string
	 */
	protected $booking_id;
	/**
	 * This object belongs to this booking object
	 * @var EM_Ticket
	 */
	var $spaces;
	var $price;
	/**
	 * Used to prefix any actions/filters on this class, so that extended classes can force their own prefix.
	 * @var string
	 */
	public static $n = 'em_tickets_bookings';
	
	public static $sortable_columns = array('ticket_name', 'ticket_description', 'ticket_spaces', 'ticket_price', 'ticket_id', 'ticket_booking_id', 'ticket_booking_spaces', 'ticket_booking_price');
	
	/**
	 * Creates an EM_Tickets instance.
	 * @note This function will eventually require an EM_Booking object. At time of writing, this means versions of Events Manager Pro < 3.0 will break.
	 * @param EM_Booking $EM_Booking
	 */
	function __construct( $EM_Booking = null ){
		if( is_object($EM_Booking) && !empty($EM_Booking->booking_uuid) ){ // all booking objects have a uuid
			$this->booking = $EM_Booking;
			$this->booking_id = $EM_Booking->booking_id;
		}elseif( is_numeric($EM_Booking) ){
			$this->booking_id = $EM_Booking;
		}
		$this->get_ticket_bookings();
		do_action( static::$n, $this, $EM_Booking);
	}
	
	public function __get( $prop ){
		if( $prop === 'booking_id' || $prop === 'id' ){
			return $this->booking_id;
		} elseif ( $prop === 'booking' ){
			return $this->get_booking();
		}
		return parent::__get($prop);
	}
	
	public function __set( $prop, $val ){
		if( $prop === 'booking' && !empty($val->booking_uuid) ){
			$this->booking = $val;
			$this->booking_id = $this->booking->booking_id;
			// point all booking props to this object
			foreach( $this->tickets_bookings as $ticket_booking ) {
				$ticket_booking->booking = $this->booking;
			}
			// reload tickets
			$this->tickets_bookings_loaded = false;
			$this->get_ticket_bookings(); // refresh ticket bookings
			return;
		} elseif ( $prop === 'booking_id' ) {
			$this->booking_id = absint($val);
		}
		parent::__set( $prop, $val );
	}
	
	public function __call( $function, $args ){
		if( method_exists($this->get_booking(), $function) ){
			return $this->get_booking()->$function($args);
		}
		return parent::__call($function, $args);
	}
	
	/**
	 * Return relevant fields that will be used for storage, excluding things such as event and ticket objects that should get reloaded
	 * @return string[]
	 */
	public function __sleep(){
		$array = array('tickets_bookings','tickets_bookings_loaded');
		return apply_filters('em_tickets_bookings_sleep', $array, $this);
	}
	
	/**
	 * Returns an array of individual ticket bookings (single space attendees) for given search $args. If $count is set to true, then the number of results found is returned instead.
	 * @param $args
	 *
	 * @return EM_Ticket_Bookings[]|int
	 */
	public static function get( $args, $count = false ) {
		global $wpdb;
		// Pass this onto bookings, to generate the SQL, then wrap it into another SQL to get the ticket bookings themselves
		if( $count ) {
			$args['array'] = array('booking_id');
		}
		$args = EM_Bookings::get_default_search( $args ); // sanitize directly
		$sql_parts = EM_Bookings::get_sql( $args );
		$conditions = $orderbys =  $joins =  $fields = array();
		// quick search hack, if we're looking for what is formatted as a ticket uuid then circumvent searching the bookings
		if( preg_match('/^[a-zA-Z0-9]{32}$/D', $args['search']) ) {
			unset($sql_parts['data']['conditions']['search']);
			$conditions['search'] = "ticket_uuid = '{$args['search']}'";
			$sql_parts['statement']['where'] = 'WHERE ' . implode(' AND ', $sql_parts['data']['conditions'] ); // recreate conditions without search
		}
		// generate a bookings subquery
		$bookings_sql = static::get_bookings_subquery( $sql_parts, $count );
		// execute count or query
		if( $count ) {
			// we don't need to worry about ordering because only join or condition for ordering
			$tickets_bookings_sql = static::get_built_count_sql( $bookings_sql, array('conditions' => $conditions) );
			return $wpdb->get_var($tickets_bookings_sql);
		} else {
			// get all the Ticket_Booking fields and concat them with a tb. prefix into $fields
			$EM_Ticket_Booking = new EM_Ticket_Booking();
			foreach ( array_keys($EM_Ticket_Booking->fields) as $field ) {
				$fields[$field] = $field === 'ticket_booking_id' ? 'DISTINCT tb.' . $field : 'tb.' . $field;
			}
			// add outer ordering and potentially ordering by ticket data requiring a join
			foreach ( $sql_parts['data']['orderbys'] as $orderby ) {
				$orderby = explode(' ', $orderby); // in case we have order, remove it
				$orderby_field = $orderby[0];
				$orderbys[$orderby_field] = 'b.' . $orderby_field;
			}
			if( !empty($args['orderby']) ) {
				if( !is_array($args['orderby']) ) {
					$args['orderby'] = explode(',', str_replace(' ', '', $args['orderby']));
				}
				foreach ( $args['orderby'] as $orderby ) {
					$orderby = explode(' ', $orderby); // in case we have order, remove it
					$orderby_field = $orderby[0];
					if( in_array($orderby_field, static::$sortable_columns) ) {
						if( in_array( $orderby_field, ['ticket_id', 'ticket_booking_id', 'ticket_booking_price']) ) {
							// these fields are located in the tickets_bookings_table and do not require a join
							$orderbys[$orderby_field] = 'tb.' . $orderby_field;
						} elseif ( $orderby_field == 'ticket_booking_spaces' ) {
							// we need to group and sum, not join
							$fields['ticket_booking_spaces'] = 'SUM(ticket_booking_spaces) AS ticket_booked_spaces';
							$orderbys[$orderby_field] = 'ticket_booked_spaces';
						} else {
							// the rest require a join to the tickets table
							$orderbys[$orderby_field] = 't.' . $orderby_field;
							$joins['tickets'] = 'LEFT JOIN ' . EM_TICKETS_TABLE . ' t ON t.ticket_id = tb.ticket_id';
						}
					} elseif ( preg_match('/^attendee_/', $orderby_field) ) {
						// we search attendee metas for this field
						$field = preg_replace('/^attendee_/', '', $orderby_field);
						$joins['attendees'] = "LEFT JOIN ( SELECT ticket_booking_id, meta_value AS {$orderby_field} FROM " . EM_TICKETS_BOOKINGS_META_TABLE . " WHERE meta_key='{$field}') {$orderby_field} ON {$orderby_field}.ticket_booking_id = tb.ticket_booking_id";
						$orderbys[$orderby_field] = $orderby_field . '.' . $orderby_field;
						$fields[] = $orderby_field . '.' . $orderby_field;
					}
				}
			}
			$orderbys = self::build_sql_orderby($args, $orderbys, $args['order']);
			$orderby = !empty($orderbys) ? ' ORDER BY ' . implode( ', ', $orderbys ) : '';
			// build the SQL
			$tickets_bookings_sql = static::get_built_sql( $bookings_sql, $fields, $joins, $conditions );
			// we would also need to determine if we SHOULD join, and also make these sortable under specific views,
			$tickets_bookings_sql .= $orderby . "\n" . $sql_parts['statement']['limit'] . "\n" . $sql_parts['statement']['offset'];
			// run it
			return static::get_results( $tickets_bookings_sql );
		}
	}
	
	
	/**
	 * @param $sql
	 *
	 * @return EM_Ticket_Bookings[]
	 */
	public static function get_results( $sql ) {
		global $wpdb;
		$tickets_bookings = array();
		$tickets_bookings_results = $wpdb->get_results($sql, ARRAY_A);
		foreach( $tickets_bookings_results as $ticket_bookings ){
			unset($ticket_bookings['ticket_spaces']);
			$tickets_bookings[$ticket_bookings['booking_id'].'-'.$ticket_bookings['ticket_id']] = new EM_Ticket_Bookings($ticket_bookings);
		}
		return $tickets_bookings;
	}
	
	public static function get_built_sql( $bookings_sql, $fields, $joins, $conditions = array() ){
		$condition = !empty($conditions) ? " WHERE " . implode(' AND ', $conditions) : '';
		return "SELECT ". implode(', ', $fields) ." FROM " . EM_TICKETS_BOOKINGS_TABLE . " tb INNER JOIN ({$bookings_sql}) b ON b.booking_id = tb.booking_id " . implode(' ', $joins) . $condition . " GROUP BY tb.booking_id, tb.ticket_id ";
	}
	
	public static function get_built_count_sql( $bookings_sql, $extras = array( 'joins' => [], 'conditions' => [] ) ) {
		$joins = $extras['joins'] ?? [];
		$condition = !empty($extras['conditions']) ? " WHERE " . implode(' AND ', $extras['conditions']) : '';
		return "SELECT COUNT(*) FROM (SELECT b.booking_id FROM " . EM_TICKETS_BOOKINGS_TABLE . " tb INNER JOIN ({$bookings_sql}) b ON b.booking_id = tb.booking_id " . implode(' ', $joins) . $condition . " GROUP BY tb.booking_id, tb.ticket_id) bookings";
	}
	
	public static function get_bookings_subquery( $sql_parts, $count = false ) {
		global $wpdb;
		// build SQL subquery/join statement without limits, offsets, etc
		$sql_subquery_statement = $sql_parts['statement'];
		unset($sql_subquery_statement['limit'], $sql_subquery_statement['offset'], $sql_subquery_statement['orderby']);
		// execute count or query
		if( $count ) {
			$bookings_sql = implode("\n", $sql_subquery_statement);
		} else {
			// we need to add specific subquery selector fields to avoid conflicts with the outer SQL statement
			$selectors = [ EM_BOOKINGS_TABLE . '.booking_id' ];
			$fields = array();
			// first, get all fields from EM_BOOKINGS_TABLE, then all the joins, into separate array items
			$fields[EM_BOOKINGS_TABLE] = $wpdb->get_col('SHOW COLUMNS FROM '. EM_BOOKINGS_TABLE);
			foreach( $sql_parts['data']['joins'] as $table => $join ){
				if( !preg_match('/^field\./', $table) ) {
					$fields[$table] = $wpdb->get_col('SHOW COLUMNS FROM '. $table);
				} else {
					// acccount for special joins particularly when ordering
					$field_name = str_replace('field.', '', $table);
					$fields[$field_name] = array($field_name);
				}
			}
			// now, build a unique set of selectors, first finder taking precedence
			$selector_fields = array('booking_id');
			// clean orderbys in case some ASC and DESC strings made it here
			$orderbys_clean = [];
			foreach( $sql_parts['data']['orderbys'] as $orderby ) {
				$orderbys_clean[] = str_replace([' ASC', ' DESC', ' asc', ' desc'], '', $orderby);
			}
			// add orderby fields to selectors
			foreach( $fields as $table => $table_fields ){
				foreach( $table_fields as $field ){
					if ( in_array($field, $orderbys_clean) && !in_array($field, $selector_fields) ) {
						$selector_fields[] = $field;
						$selectors[] = $table . '.' . $field;
					}
				}
			}
			// now build the subquery with the selectors
			$sql_subquery_statement['select'] = 'SELECT ' . implode(', ', $selectors) . ' FROM ' . EM_BOOKINGS_TABLE;
			$bookings_sql = implode("\n", $sql_subquery_statement);
		}
		return $bookings_sql;
	}
	
	/**
	 * @return EM_Ticket_Bookings|false
	 */
	public function get_first(){
		$this->get_ticket_bookings();
		return reset($this->tickets_bookings);
	}
	
	/**
	 * Return a specific EM_Ticket_Bookings object if a valid $ticket_id is supplied, or alternatively returns all EM_Ticket_Bookings objects registered to this object.
	 * If when requesting a $ticket_id and no EM_Ticket_Bookings object exists for it within the object, a new blank object is created and appended to the tickets_bookings property, with 0 spaces and 0 price.
	 * @param EM_Ticket|int $ticket
	 * @return EM_Ticket_Bookings|EM_Ticket_Bookings[]
	 */
	public function get_ticket_bookings( $ticket = false ){
		$ticket_id = is_object($ticket) ? $ticket->ticket_id : absint($ticket);
		if( !$this->tickets_bookings_loaded && !empty($this->booking_id) ){
			// we could get tickets individually via EM_Ticket_Bookings, but this is one db call vs multiple
			global $wpdb;
			$sql = $wpdb->prepare("SELECT * FROM ". EM_TICKETS_BOOKINGS_TABLE ." WHERE booking_id = %d ORDER BY ticket_booking_id ASC", $this->booking_id);
			$results = $wpdb->get_results($sql, ARRAY_A);
			//Get tickets belonging to this tickets booking.
			$tickets_bookings = array();
			foreach ($results as $ticket_booking){
				$ticket_booking['booking'] = $this->get_booking();
				$EM_Ticket_Booking = new EM_Ticket_Booking($ticket_booking);
				if( empty($tickets_bookings[$EM_Ticket_Booking->ticket_id]) ) $tickets_bookings[$EM_Ticket_Booking->ticket_id] = array();
				$tickets_bookings[$EM_Ticket_Booking->ticket_id][]= $EM_Ticket_Booking;
			}
			foreach( $tickets_bookings as $id => $ticket_bookings ){
				$this->tickets_bookings[$id] = new EM_Ticket_Bookings($ticket_bookings);
			}
		}
		$this->tickets_bookings_loaded = true;
		if( $ticket_id ){
			if( empty($this->tickets_bookings[$ticket_id]) ){
				$this->tickets_bookings[$ticket_id] = new EM_Ticket_Bookings( array('ticket_id' => $ticket_id, 'booking' => $this->get_booking() ) );
			}
			return $this->tickets_bookings[$ticket_id];
		}
		return $this->tickets_bookings;
	}
	
	public function get_post( $override_availability = false ){
		if( !empty($_REQUEST['em_tickets']) ){
			foreach( $_REQUEST['em_tickets'] as $ticket_id => $values){
				//make sure ticket exists
				$ticket_id = absint($ticket_id);
				if( !empty($values['spaces']) || $this->booking_id ){ // if spaces booked for first time, editing and spaces are 0 (in case we need to delete anything)
					// get an EM_Ticket_Bookings object, which will be added if non-existent, $EM_Ticket_Bookings is therefore passed by reference.
					$EM_Ticket_Bookings = $this->get_ticket_bookings($ticket_id);
					if( !$EM_Ticket_Bookings->get_post() ){
						$this->add_error($EM_Ticket_Bookings->get_errors());
					}
					// make sure things are recalculated
					$this->price = 0; //so price calculations are reset
					$this->get_spaces(true);
					$this->get_price();
				}
			}
		}
		return apply_filters( static::$n . '_get_post', empty($this->errors), $this, $override_availability );
	}
	
	public function validate( $override_availability = false ){
		if( count($this->tickets_bookings) > 0 ){
			foreach($this->tickets_bookings as $EM_Ticket_Bookings){ /* @var $EM_Ticket_Bookings EM_Ticket_Bookings */
				if ( !$EM_Ticket_Bookings->validate( $override_availability ) ){
					$this->errors = array_merge($this->errors, $EM_Ticket_Bookings->get_errors());
				}
			}
		}
		return apply_filters( static::$n . '_validate', empty($this->errors), $this, $override_availability );
	}
	
	/**
	 * Saves the ticket bookings for this booking into the database, whether a new or existing booking
	 * @return boolean
	 */
	function save(){
		do_action(static::$n . '_save_pre',$this);
		//save/update tickets
		foreach( $this->tickets_bookings as $EM_Ticket_Booking ){
			$result = $EM_Ticket_Booking->save();
			if(!$result){
				$this->errors = array_merge($this->errors, $EM_Ticket_Booking->get_errors());
			}
		}
		//delete old tickets if set to 0 in an update
		foreach($this->tickets_bookings_deleted as $EM_Ticket_Booking ){
			$result = $EM_Ticket_Booking->delete();
			if(!$result){
				$this->errors = array_merge($this->errors, $EM_Ticket_Booking->get_errors());
			}
		}
		//return result
		if( count($this->errors) > 0 ){
			$this->feedback_message = __('There was a problem saving the booking.', 'events-manager');
			$this->errors[] = __('There was a problem saving the booking.', 'events-manager');
			return apply_filters(static::$n . '_save', false, $this);
		}
		return apply_filters(static::$n . '_save', true, $this);
	}
	
	/**
	 * Adds a ticket booking to the object, equivalent of adding directly to the array of tickets_bookings
	 *
	 * @param EM_Ticket_Booking $EM_Ticket_Booking
	 * @return bool
	 */
	function add( $EM_Ticket_Booking ){
		if( $EM_Ticket_Booking instanceof EM_Ticket_Booking ) {
			$this->get_ticket_bookings($EM_Ticket_Booking->ticket_id)->tickets_bookings[$EM_Ticket_Booking->ticket_uuid] = $EM_Ticket_Booking;
			return true;
		}
		return false;
	}
	
	/**
	 * Checks if this set has a specific ticket booked, returning the key of the ticket in the EM_Tickets_Bookings->ticket_bookings array
	 * @param int $ticket_id
	 * @return mixed
	 */
	function has_ticket( $ticket_id ){
		foreach ($this->tickets_bookings as $key => $EM_Ticket_Booking){
			if( $EM_Ticket_Booking->ticket_id == $ticket_id ){
				return apply_filters(static::$n . '_has_ticket',$key,$this);
			}
		}
		return apply_filters(static::$n . '_has_ticket',false,$this);
	}
	
	/**
	 * Smart event locator, saves a database read if possible. 
	 */
	function get_booking(){
		if( !$this->booking || $this->booking->booking_id !== $this->booking_id ) {
			$this->booking = new EM_Booking( $this->booking_id );
		}
		return apply_filters(static::$n . '_get_booking', $this->booking, $this);
	}
	
	/**
	 * Delete all ticket bookings
	 * @return boolean
	 */
	function delete(){
		global $wpdb;
		$result = false;
		if( $this->get_booking()->can_manage() ){
			$result_meta = $wpdb->query($wpdb->prepare("DELETE FROM ".EM_TICKETS_BOOKINGS_META_TABLE." WHERE ticket_booking_id IN (SELECT ticket_booking_id FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE booking_id = %d)", $this->booking_id));
			$result = $wpdb->query($wpdb->prepare("DELETE FROM ".EM_TICKETS_BOOKINGS_TABLE." WHERE booking_id = %d", $this->booking_id));
		}
		return apply_filters(static::$n . '_delete', ($result !== false && $result_meta !== false), $this);
	}
	
	/**
	 * Get the total number of spaces booked in this booking. Seting $force_reset to true will recheck spaces, even if previously done so.
	 * @param unknown_type $force_refresh
	 * @return mixed
	 */
	function get_spaces( $force_refresh = false ){
		if( $force_refresh || $this->spaces == 0 ){
			$spaces = 0;
			foreach( $this->tickets_bookings as $EM_Ticket_Bookings ){
				$spaces += $EM_Ticket_Bookings->get_spaces( $force_refresh );
			}
			$this->spaces = $spaces;
		}
		return apply_filters(static::$n . '_get_spaces',$this->spaces,$this);
	}
	
	/**
	 * Gets the total price for this whole booking by adding up subtotals of booked tickets. Seting $force_reset to true will recheck spaces, even if previously done so.
	 * @param boolean $format
	 * @return float
	 */
	function get_price( $format = false ){
		if( $this->price == 0 ){
			$price = $this->calculate_price( true );
			// deprecated, use the _calculate_price filter instead
			$this->price = apply_filters(static::$n . '_get_price', $price, $this);
		}
		if($format){
			return $this->format_price($this->price);
		}
		return $this->price;
	}
	
	function calculate_price( $force_refresh = false ){
		if( $this->price == null || $force_refresh ){
			$price = 0;
			foreach($this->tickets_bookings as $EM_Ticket_Bookings ){
				$price += $EM_Ticket_Bookings->calculate_price( $force_refresh );
			}
			$this->price = apply_filters(static::$n . '_calculate_price', $price, $this, $force_refresh);
		}
		return $this->price;
	}
	
	/* WIP - not really used as we just use get() to split bookings into results and order by attendee meta, the main search filtering is doen at booking level
	 * @see wp-content/plugins/events-manager/classes/EM_Object#build_sql_conditions()
	 */
	public static function build_sql_conditions( $args = array() ){
		$conditions = parent::build_sql_conditions($args);
		if( is_numeric($args['status']) ){
			$conditions['status'] = 'ticket_status='.$args['status'];
		}
		return apply_filters(static::$n . '_build_sql_conditions', $conditions, $args);
	}
	
	/* Overrides EM_Object method to apply a filter to result
	 * @see wp-content/plugins/events-manager/classes/EM_Object#build_sql_orderby()
	 */
	public static function build_sql_orderby( $args, $accepted_fields, $default_order = 'ASC' ){
		return apply_filters( static::$n . '_build_sql_orderby', parent::build_sql_orderby($args, $accepted_fields, em_get_option('dbem_events_default_order')), $args, $accepted_fields, $default_order );
	}
	
	/*
	 * WIP - not really used as we just use get() to split bookings into results and order by attendee meta, the main search filtering is doen at booking level
	 * @param array $array_or_defaults may be the array to override defaults
	 * @param array $array
	 * @return array
	 * @uses EM_Object#get_default_search()
	 */
	public static function get_default_search( $array_or_defaults = array(), $array = array() ){
		$defaults = array(
			'status' => false,
			'person' => true //to add later, search by person's tickets...
		);	
		//sort out whether defaults were supplied or just the array of search values
		if( empty($array) ){
			$array = $array_or_defaults;
		}else{
			$defaults = array_merge($defaults, $array_or_defaults);
		}
		//specific functionality
		$defaults['owner'] = !current_user_can('manage_others_bookings') ? get_current_user_id():false;
		return apply_filters(static::$n . '_get_default_search', parent::get_default_search($defaults,$array), $array, $defaults);
	}

	//Iterator Implementation
	
	#[\ReturnTypeWillChange]
	/**
	 * @return void
	 */
    public function rewind(){
	    $this->get_ticket_bookings();
        reset($this->tickets_bookings);
    }
	
	#[\ReturnTypeWillChange]
	/**
	 * @return EM_Ticket_Bookings
	 */
    public function current(){
        return current($this->tickets_bookings);
    }
	#[\ReturnTypeWillChange]
	/**
	 * @return int Ticket ID
	 */
    public function key(){
        return key($this->tickets_bookings);
    }
	#[\ReturnTypeWillChange]
	/**
	 * @return EM_Ticket_Bookings
	 */
	public function next(){
        return next($this->tickets_bookings);
    }
	#[\ReturnTypeWillChange]
	public function valid(){
        $key = key($this->tickets_bookings);
        return ($key !== NULL && $key !== FALSE);
    }
    //Countable Implementation
	
	#[\ReturnTypeWillChange]
	/**
	 * @return int
	 */
	public function count(){
		return count($this->tickets_bookings);
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
			$this->tickets_bookings[] = $value;
		} else {
			$this->tickets_bookings[$offset] = $value;
		}
	}
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @return bool
	 */
	public function offsetExists($offset) {
		return isset($this->tickets_bookings[$offset]);
	}
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @return void
	 */
	public function offsetUnset($offset) {
		unset($this->tickets_bookings[$offset]);
	}
	#[\ReturnTypeWillChange]
	/**
	 * @param $offset
	 * @return EM_Ticket_Bookings|null
	 */
	public function offsetGet($offset) {
		return isset($this->tickets_bookings[$offset]) ? $this->tickets_bookings[$offset] : null;
	}
	
	public function __debugInfo(){
		$object = clone($this);
		$object->booking = !empty($this->booking_id) ? 'Booking ID #'.$this->booking_id : 'New Booking - No ID';
		$object->shortnames = 'Removed for export, uncomment from __debugInfo()';
		$object->mime_types = 'Removed for export, uncomment from __debugInfo()';
		if( empty($object->errors) ) $object->errors = false;
		return (Array) $object;
	}
}
?>